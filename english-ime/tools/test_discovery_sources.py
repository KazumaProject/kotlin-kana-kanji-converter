import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import discovery_sources as d


class DiscoverySourcesTest(unittest.TestCase):
    def selector(self):
        return dict(id='physicists', provider='wikidata', topic='people.science', kind='person',
                    classes=['Q169470'], minimumSitelinks=40)

    def row(self, qid, name):
        return dict(item={'value': 'http://www.wikidata.org/entity/' + qid}, links={'value': '50'},
                    article={'value': 'https://en.wikipedia.org/wiki/' + name.replace(' ', '_')}, label={'value': name})

    def fixture(self, root):
        rules = root / 'policy.json'
        rules.write_text(json.dumps(dict(schemaVersion=1, pageSize=2, selectors=[self.selector()])))
        source = root / 'sources'
        calls = []
        def downloaded(url, path, maximum):
            from urllib.parse import parse_qs, urlparse
            query = parse_qs(urlparse(url).query)['query'][0]
            offset = int(re.search(r'OFFSET (\d+)', query)[1])
            rows = [self.row('Q1', 'First Person'), self.row('Q2', 'Second Person')] if offset == 0 else [self.row('Q3', 'Third Person')]
            calls.append(offset)
            path.write_text(json.dumps(dict(results={'bindings': rows})))
        with patch.object(d.download, 'download', downloaded), patch.object(d.time, 'sleep'):
            manifest = d.fetch(source, rules)
        return source, rules, manifest, calls

    def test_discovers_past_first_page_and_reuses_the_sealed_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, rules, manifest, calls = self.fixture(Path(tmp))
            self.assertEqual([0, 2], calls)
            self.assertEqual(3, manifest['counts']['physicists'])
            targets, _, _ = d.collect(source, rules)
            self.assertEqual({'First Person', 'Second Person', 'Third Person'}, {r['surface'] for r in targets})
            self.assertEqual({'people.science'}, {t for r in targets for t in r['topics']})
            with patch.object(d.download, 'download', side_effect=AssertionError('No network on replay')):
                self.assertEqual(manifest, d.fetch(source, rules))

    def test_incomplete_pagination_is_not_reported_as_source_exhaustion(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, rules, manifest, _ = self.fixture(Path(tmp))
            removed = manifest['pages'].pop()
            del manifest['files'][removed['file']]
            manifest['counts']['physicists'] = 2
            d.h.dump(source / 'discovery.json', manifest)
            with self.assertRaisesRegex(ValueError, 'before source exhaustion'):
                d.verify(source, rules)

    def test_tampered_source_and_policy_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, rules, manifest, _ = self.fixture(Path(tmp))
            (source / manifest['pages'][0]['file']).write_text('{}')
            with self.assertRaises((ValueError, KeyError)):
                d.verify(source, rules)

    def test_request_checkpoint_is_explicit_and_can_resume_without_refetching_prior_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, rules, manifest, _ = self.fixture(root)
            # Reuse only the first cached page in a new snapshot with no second-page request allowed.
            first = root / 'first'; first.mkdir()
            page = manifest['pages'][0]
            import shutil
            shutil.copyfile(source / page['file'], first / page['file'])
            with patch.object(d.download, 'download', side_effect=TimeoutError('source unavailable')):
                partial = d.fetch(first, rules)
            self.assertFalse(partial['complete'])
            self.assertEqual(2, partial['counts']['physicists'])
            self.assertEqual(2, partial['states']['physicists']['nextOffset'])
            self.assertEqual(2, len(d.collect(first, rules)[0]))
            self.assertIn('source unavailable', partial['states']['physicists']['pendingReason'])
            def resumed(url, path, maximum):
                from urllib.parse import parse_qs, urlparse
                self.assertIn('OFFSET 2', parse_qs(urlparse(url).query)['query'][0])
                path.write_text(json.dumps(dict(results={'bindings': [self.row('Q3', 'Third Person')]})))
            with patch.object(d.download, 'download', resumed), patch.object(d.time, 'sleep'):
                complete = d.fetch(root / 'resumed', rules, resume_from=first)
            self.assertTrue(complete['complete'])
            self.assertEqual(3, complete['counts']['physicists'])
            self.assertEqual(1, complete['sourceRequests'])
            self.assertFalse(d.verify(first, rules)['complete'])

    def test_wiktionary_continuation_retains_exact_headwords_and_separate_identity(self):
        from urllib.parse import parse_qs, urlparse
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rules = root / 'policy.json'
            selector = dict(id='physics', provider='wiktionary', topic='science.physics', kind='lexical',
                            category='Category:en:Physics')
            rules.write_text(json.dumps(dict(schemaVersion=1, pageSize=500, selectors=[selector])))
            calls = []
            def downloaded(url, path, maximum):
                args = parse_qs(urlparse(url).query)
                calls.append(args)
                payload = dict(query={'categorymembers': [dict(pageid=2, ns=0, title='thermal expansion')]})
                if 'cmcontinue' not in args:
                    payload = dict(query={'categorymembers': [dict(pageid=1, ns=0, title='Planck constant')]},
                                   **{'continue': {'cmcontinue': 'next-token', 'continue': '-||'}})
                path.write_text(json.dumps(payload))
            with patch.object(d.download, 'download', downloaded), patch.object(d.time, 'sleep'):
                manifest = d.fetch(root / 'source', rules)
            targets, _, _ = d.collect(root / 'source', rules)
            self.assertTrue(manifest['complete'])
            self.assertEqual(['next-token'], calls[1]['cmcontinue'])
            self.assertEqual({'wiktionary:1', 'wiktionary:2'}, {r['entity'] for r in targets})
            self.assertEqual({'Planck constant', 'thermal expansion'}, {r['surface'] for r in targets})
            self.assertTrue(all(p['license'] == 'CC-BY-SA-4.0' for r in targets for p in r['proofs']))

    def test_invalid_page_budget_is_rejected_before_fetching(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rules = root / 'policy.json'
            rules.write_text(json.dumps(dict(schemaVersion=1, pageSize=0, selectors=[self.selector()])))
            with self.assertRaisesRegex(ValueError, 'page size'):
                d.policy(rules)
            with self.assertRaisesRegex(ValueError, 'per-selector'):
                d.fetch(root / 'source', rules, max_new_pages_per_selector=-1)

    def test_query_binds_human_occupation_and_paginates_before_label_lookup(self):
        query = d.query(self.selector(), 1000, 500)
        self.assertIn('wdt:P31 wd:Q5; wdt:P106 wd:Q169470', query)
        self.assertIn('FILTER(?links >= 40)', query)
        self.assertLess(query.index('LIMIT 500 OFFSET 1000'), query.index('OPTIONAL'))
        product = dict(self.selector(), kind='product', classes=['Q22645'])
        self.assertIn('wdt:P31 wd:Q22645', d.query(product, 0, 500))


if __name__ == '__main__':
    unittest.main()
