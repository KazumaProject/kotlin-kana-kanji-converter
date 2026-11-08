import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import catalog_harness as c
import gemini_acquisition as g


class GeminiAcquisitionTest(unittest.TestCase):
    def response(self, rows, **changes):
        value = dict(modelVersion=g.h.MODEL, candidates=[dict(finishReason='STOP', content={'parts': [
            {'text': json.dumps(dict(items=rows))}]})], usageMetadata={'totalTokenCount': 10})
        value.update(changes)
        return json.dumps(value).encode()

    def fixture(self, root, rows):
        directory = root / 'run'; directory.mkdir()
        (directory / 'baseline.jsonl').write_text('{}\n')
        topics = [dict(topic='daily.home', kind='lexical', label='Home', definition='Daily vocabulary',
                       existingCount=0, existingSpellings=[]),
                  dict(topic='organizations.general', kind='organization', label='Organizations',
                       definition='Organizations', existingCount=0, existingSpellings=[])]
        plan = dict(schemaVersion=1, model=g.h.MODEL, promptSha256=hashlib.sha256(g.PROMPT.encode()).hexdigest(),
            schema=g.SCHEMA, policy={'suggestionsPerTopic': 100}, topics=topics, batches=[topics],
            baselineSha256=g.h.replay.sha(directory / 'baseline.jsonl'))
        g.h.dump(directory / 'plan.json', plan)
        request = directory / 'request-000.json'; g.h.dump(request, g.request_payload(plan, topics))
        response = directory / 'response-000.json'; response.write_bytes(self.response(rows))
        g.h.dump(directory / 'attempts.json', [dict(batch=0, status='completed',
            requestSha256=g.h.replay.sha(request), responseSha256=g.h.replay.sha(response))])
        return directory, plan

    def test_sparse_selection_counts_unique_real_candidates_not_supporting_forms(self):
        topics = {'daily.home': dict(category='topic_home', label='Home', definition='Home'),
                  'daily.health': dict(category='topic_health', label='Health', definition='Health')}
        analyses = {'sample': [{'memberships': {'topic_home'}}, {'memberships': {'topic_home'}}],
                    'grammar only': [{'memberships': {'topic_health'}}]}
        rule = dict(topics=[dict(topic=t, kind='lexical') for t in topics], maximumExistingSpellings=1)
        selected = g.sparse_topics(topics, analyses, {'sample'}, rule)
        self.assertEqual([('daily.health', 0), ('daily.home', 1)], [(r['topic'], r['existingCount']) for r in selected])

    def test_unexpected_topics_duplicates_and_incomplete_generations_are_rejected(self):
        row = dict(topic='daily.home', surface='sample', wikipediaTitle='')
        batch = [dict(topic='daily.home', kind='lexical')]
        self.assertEqual([row], g.parse_response(self.response([row]), batch, 100)[0])
        self.assertEqual([row], g.parse_response(self.response([row, row]), batch, 100)[0])
        self.assertEqual([], g.parse_response(self.response([dict(row, surface='')]), batch, 100)[0])
        self.assertEqual([row], g.parse_response(self.response([dict(row, wikipediaTitle='Unused hint')]), batch, 100)[0])
        for raw in [self.response([dict(row, topic='unknown')]),
                    self.response([dict(row, surface='sample\n')]), self.response([row], modelVersion='other-model'),
                    self.response([row], candidates=[dict(finishReason='MAX_TOKENS')])]:
            with self.assertRaises(ValueError): g.parse_response(raw, batch, 100)
        self.assertNotIn('minItems', g.response_schema(batch, 100)['properties']['items'])

    def test_model_only_proposal_cannot_annotate_an_existing_candidate(self):
        target = dict(id='lead', surface='known', kind='lexical', topics=['daily.home'], proofs=[], requireIndependentProof=True)
        forms = {'known': [dict(lexeme_id='existing', lemma='known', evidence='https://example.org/source', memberships=set())]}
        result, operations = c.audit([target], {'daily.home': dict(category='topic_home', domain='daily')},
                                    {('known', 'known')}, forms, set())
        self.assertEqual('blocked_evidence', result[0]['status'])
        self.assertEqual([], operations)

    def test_failed_request_is_reserved_before_sending_and_never_silently_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory, plan = self.fixture(root, [])
            for name in ['response-000.json', 'attempts.json']: (directory / name).unlink()
            proof_path = root / 'proof.json'; proof_path.write_text('{}')
            proof = dict(project_id='fixture-project', rpm=15, rpd=500, tpm=250000)
            args = argparse.Namespace(work_dir=directory, free_proof=proof_path, quota_dir=root / 'quota',
                max_requests=1, daily_requests=20, retry_failed=False, wait=False)
            def failed(payload, key):
                self.assertEqual('inflight', json.loads((directory / 'attempts.json').read_text())[0]['status'])
                db = next((root / 'quota').rglob('quota.sqlite3'))
                with sqlite3.connect(db) as connection:
                    self.assertEqual(1, connection.execute('select count(*) from requests').fetchone()[0])
                raise TimeoutError('No reply')
            with patch.object(g.h, 'free_project', return_value=proof), patch.object(g, 'credential', return_value='fixture-secret'):
                with self.assertRaises(TimeoutError): g.propose(args, failed)
                with self.assertRaisesRegex(ValueError, 'failed/inflight'): g.propose(args, failed)
            journal = (directory / 'attempts.json').read_text()
            self.assertNotIn('fixture-secret', journal)
            self.assertEqual('failed', json.loads(journal)[0]['status'])

    def test_cached_completed_response_never_calls_the_model_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); directory, _ = self.fixture(root, [])
            args = argparse.Namespace(work_dir=directory, free_proof=root / 'proof', quota_dir=root / 'quota',
                                      max_requests=1, daily_requests=20, retry_failed=False, wait=False)
            with patch.object(g.h, 'free_project', return_value={'project_id': 'fixture-project'}), \
                 patch.object(g, 'credential', return_value='fixture-secret'):
                result = g.propose(args, lambda *_: self.fail('Unexpected model call'))
            self.assertEqual(0, result['requests'])

    def test_explicit_revalidation_recovers_saved_output_without_a_new_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); directory, _ = self.fixture(root, [dict(topic='daily.home', surface='sample', wikipediaTitle='')])
            attempts = json.loads((directory / 'attempts.json').read_text())
            attempts[0].update(status='failed', errorType='ValueError')
            g.h.dump(directory / 'attempts.json', attempts)
            args = argparse.Namespace(work_dir=directory, free_proof=root / 'proof', quota_dir=root / 'quota',
                                      max_requests=1, daily_requests=20, retry_failed=True, wait=False)
            with patch.object(g.h, 'free_project', return_value={'project_id': 'fixture-project'}), \
                 patch.object(g, 'credential', return_value='fixture-secret'):
                result = g.propose(args, lambda *_: self.fail('Saved response should be revalidated'))
                self.assertEqual(0, result['requests'])
                attempts = json.loads((directory / 'attempts.json').read_text())
                self.assertEqual('completed', attempts[0]['status'])
                self.assertIn('revalidatedAt', attempts[0])
                attempts[0]['status'] = 'failed'; g.h.dump(directory / 'attempts.json', attempts)
                (directory / 'response-000.json').write_bytes(self.response([dict(topic='daily.home', surface='changed', wikipediaTitle='')]))
                with self.assertRaisesRegex(ValueError, 'Changed saved model response'):
                    g.propose(args, lambda *_: self.fail('Tampered response must not trigger a request'))

    def test_source_errors_remain_pending_and_never_create_spelling_proofs(self):
        import urllib.error
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory, _ = self.fixture(root, [dict(topic='daily.home', surface='sample', wikipediaTitle=''),
                dict(topic='organizations.general', surface='Example Company', wikipediaTitle='Example Company')])
            args = argparse.Namespace(work_dir=directory, source_dir=root, lexical_source_dir=root, esdb_dir=root)
            with patch.object(c, 'load_sources', return_value=dict(words={}, wordnet={}, pins={})), \
                 patch.object(g.download, 'download', side_effect=urllib.error.HTTPError('https://example.org', 429, 'Rate limit', {}, None)), \
                 patch.object(g.time, 'sleep'):
                result = g.fetch_evidence(args)
            self.assertFalse(result['complete'])
            self.assertEqual(2, result['pendingSourceBatches'])
            targets, manifest, _ = g.collect(directory)
            self.assertEqual(2, len(targets))
            self.assertTrue(all(not t['proofs'] for t in targets))
            self.assertFalse(manifest['complete'])

    def test_source_resume_preserves_model_results_and_previous_snapshot(self):
        import urllib.error
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory, _ = self.fixture(root, [dict(topic='daily.home', surface='sample', wikipediaTitle='')])
            args = argparse.Namespace(work_dir=directory, source_dir=root, lexical_source_dir=root, esdb_dir=root, out=root / 'resumed')
            with patch.object(c, 'load_sources', return_value=dict(words={}, wordnet={}, pins={})), \
                 patch.object(g.download, 'download', side_effect=urllib.error.HTTPError('https://example.org', 429, 'Rate limit', {}, None)), \
                 patch.object(g.time, 'sleep'):
                g.fetch_evidence(args)
            old_hash = g.h.replay.sha(directory / 'acquisition.json')
            def downloaded(url, path, maximum):
                path.write_text(json.dumps({'query': {'pages': {'1': dict(ns=0, title='sample', revisions=[dict(
                    revid=10, slots={'main': {'*': '==English==\n{{en-noun}}\n'}})])}}}))
            with patch.object(c, 'load_sources', return_value=dict(words={}, wordnet={}, pins={})), \
                 patch.object(g.download, 'download', downloaded), patch.object(g.time, 'sleep'), \
                 patch.object(g.h, 'gemini_request', side_effect=AssertionError('No model calls on source resume')):
                result = g.resume_evidence(args)
            self.assertTrue(result['complete'])
            self.assertEqual(old_hash, g.h.replay.sha(directory / 'acquisition.json'))
            self.assertFalse(g.verify(directory)['complete'])
            self.assertTrue(g.collect(root / 'resumed')[0][0]['proofs'])
            self.assertEqual((directory / 'response-000.json').read_bytes(), (root / 'resumed/response-000.json').read_bytes())

    def test_name_review_preserves_spellings_and_blocks_generic_article_headings(self):
        leads = [dict(surface='Softbox', kind='product', topics=['products.imaging'], proofs=[{'source': 'fixture'}], entity='original'),
                 dict(surface='Example Company', kind='product', topics=['products.home'], proofs=[{'source': 'fixture'}], entity='company')]
        decisions = [dict(surface='Softbox', kind='lexical', topics=['media.photography'], decision='defer'),
                     dict(surface='Example Company', kind='organization', topics=['organizations.technology'], decision='keep')]
        result = g.apply_name_review(leads, decisions)
        self.assertEqual('Softbox', result[0]['surface'])
        self.assertEqual('product', result[0]['kind'])
        self.assertTrue(result[0]['deferredByNameReview'])
        self.assertEqual(leads[0]['proofs'], result[0]['proofs'])
        self.assertEqual('organization', result[1]['kind'])
        target = dict(id='heading', surface='Softbox', kind='product', topics=['media.photography'],
                      proofs=[{'source': 'fixture'}], deferredByNameReview=True)
        rows, operations = c.audit([target], {'media.photography': dict(category='topic_photo', domain='technology')}, set(), {}, set())
        self.assertEqual('blocked_named_review', rows[0]['status'])
        self.assertEqual([], operations)

    def test_operator_name_decisions_cannot_invent_words_or_accept_generic_names(self):
        rows = [dict(surface='Example', kind='brand', topics=['products.home'], decision='keep')]
        correction = dict(surface='Example', kind='brand', topics=['technology.hardware'], decision='keep', reason='Computing brand')
        self.assertEqual(['technology.hardware'], g.operator_name_decisions(rows, [correction])[0]['topics'])
        for bad in [dict(correction, surface='Invented'), dict(correction, topics=['unknown']), dict(correction, kind='lexical')]:
            with self.assertRaises(ValueError): g.operator_name_decisions(rows, [bad])

    def test_kind_merges_deduplicate_identical_proofs_without_losing_other_sources(self):
        proof = dict(source='wikidata', url='https://www.wikidata.org/wiki/Q1', license='CC0-1.0', sha256='a' * 64)
        other = dict(proof, source='another-source', url='https://example.org/source')
        rows = c.canonical_proofs([proof, dict(proof), other])
        self.assertEqual(2, len(rows))
        self.assertEqual(2, len({r['id'] for r in rows}))
        self.assertEqual(rows, c.canonical_proofs(rows))

    def test_english_section_and_real_nonhuman_entity_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [dict(topic='daily.home', surface=s, wikipediaTitle='') for s in ['English sample', 'French sample']]
            rows += [dict(topic='organizations.general', surface=s, wikipediaTitle=s) for s in ['Example Company', 'A Person']]
            directory, _ = self.fixture(root, rows)
            def download(url, path, maximum):
                if 'wiktionary' in url:
                    pages = {str(i): dict(ns=0, title=surface, revisions=[dict(revid=i, slots={'main': {
                        '*': f'=={language}==\n{{{{en-noun}}}}\n'}})])
                        for i, (surface, language) in enumerate([('English sample', 'English'), ('French sample', 'French')], 1)}
                    value = {'query': {'pages': pages}}
                else:
                    entities = {}
                    for i, (surface, cls) in enumerate([('Example Company', 'Q4830453'), ('A Person', 'Q5')], 1):
                        entities[str(i)] = dict(id='Q' + str(i), lastrevid=i, labels={'en': {'value': surface}},
                            sitelinks={'enwiki': {'title': surface}}, claims={'P31': [dict(rank='normal', mainsnak={
                                'datavalue': {'value': {'id': cls}}})]})
                    value = {'entities': entities}
                path.write_text(json.dumps(value))
            args = argparse.Namespace(work_dir=directory, source_dir=root, lexical_source_dir=root, esdb_dir=root)
            with patch.object(c, 'load_sources', return_value=dict(words={}, wordnet={}, pins={})), \
                 patch.object(g.download, 'download', download), patch.object(g.time, 'sleep'):
                result = g.fetch_evidence(args)
            self.assertTrue(result['complete'])
            targets, _, _ = g.collect(directory)
            proofs = {r['surface']: r['proofs'] for r in targets}
            self.assertTrue(proofs['English sample'])
            self.assertTrue(proofs['Example Company'])
            self.assertEqual([], proofs['French sample'])
            self.assertEqual([], proofs['A Person'])
            (directory / 'response-000.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'changed proposal batch'):
                g.verify(directory)


if __name__ == '__main__':
    unittest.main()
