import argparse
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import dictionary_sources as catalog
import vocabulary_harness as h


class DictionaryCatalogTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / 'sources'
        self.source.mkdir()
        self.esdb = self.root / 'esdb'
        self.esdb.mkdir()
        with sqlite3.connect(self.esdb / 'esdb.db') as c:
            c.executescript('''create table entries(word_id int,group_id int,lemma_id int,lemma text,
                word text,base_pos text,pos text,pos_class text,usage_note text);
                create table scowl_(word_id int,size int,variant_level int,group_rank text,
                entry_rank text,usage_note text,tag text);''')
            rows = [(1, 1, 1, 'go', 'go', 'v', 'v0', '', ''),
                (2, 1, 1, 'go', 'went', 'v', 'vd', '', ''),
                (3, 1, 1, 'go', 'going', 'v', 'vg', '', ''),
                (4, 2, 2, 'child', 'child', 'n', 'n0', '', ''),
                (5, 2, 2, 'child', 'children', 'n', 'ns', '', ''),
                (6, 3, 3, 'Alice', 'Alice', 'n', 'n0', 'person', ''),
                (7, 3, 3, 'Alice', "Alice's", 'n', 'np', 'person', ''),
                (8, 4, 4, 'August', 'August', 'n', 'n0', '', ''),
                (9, 5, 5, 'false', 'false', 'aj', 'aj0', '', ''),
                (10, 6, 6, 'brain', 'braining', 'v', 'vg', '', ''),
                (11, 7, 7, 'hide', 'hided', 'v', 'vd', '', '')]
            c.executemany('insert into entries values(?,?,?,?,?,?,?,?,?)', rows)
            c.executemany('insert into scowl_ values(?,10,0,"","","","")', [(r[0],) for r in rows])
        basics = {'ngsl-stats.csv': 'Lemma,Rank\ngo,1\nchild,2\nFALSE,3\nbrain,4\nhide,5\n',
            'ngsl-spoken-stats.csv': 'Lemma,Rank\ngo,1\n', 'ngsl-supplementary.csv': 'August,Augusts\n'}
        self.basic_pins = {}
        for name, content in basics.items():
            (self.source / name).write_text(content)
            self.basic_pins[name] = ('https://example.org/' + name, h.replay.sha(self.source / name),
                len(content.splitlines()) - (0 if 'supplementary' in name else 1))
        html = '\n'.join('<a href="/en-US/docs/Glossary/Term_' + str(i) + '">Term ' + str(i) + '</a>' for i in range(100))
        (self.source / 'mdn-glossary.html').write_text(html)
        (self.source / 'cask.json').write_text(json.dumps([
            dict(token='widget', name=['Widget Pro', 'C++ Builder'], tap_git_head='a' * 40),
            dict(token='retired', name=['Retired App'], tap_git_head='b' * 40, deprecated=True)]))
        (self.source / 'cask-analytics.json').write_text(json.dumps(dict(start_date='2026-01-01',
            end_date='2026-03-31', items=[dict(cask='widget', number=1)])))
        (self.source / 'ewt-train.conllu').write_text('\n'.join(
            '\t'.join([str(i), word, lemma, pos, '_', '_', '0', 'root', '_', '_'])
            for i, (word, lemma, pos) in enumerate([('went', 'go', 'VERB'), ('went', 'go', 'VERB'),
                ('children', 'child', 'NOUN'), ('children', 'child', 'NOUN'),
                ('brain', 'brain', 'NOUN'), ('brain', 'brain', 'NOUN'),
                ('hid', 'hide', 'VERB'), ('hid', 'hide', 'VERB')], 1)))
        for name in ['mdn-license.md', 'homebrew-license.txt', 'homebrew-analytics-license.txt',
                'NGSL-DICTIONARY-NOTICE.txt', 'MDN-DICTIONARY-NOTICE.txt']:
            (self.source / name).write_text('fixture notice')
        files = {p.name: dict(sha256=h.replay.sha(p), bytes=p.stat().st_size) for p in self.source.iterdir()
                 if p.name not in basics and p.name != 'ewt-train.conllu'}
        for name, url in [('mdn-glossary.html', catalog.MDN), ('cask.json', catalog.CATALOG), ('cask-analytics.json', catalog.ANALYTICS)]:
            files[name]['url'] = url
        self.manifest = dict(schemaVersion=1, profile=catalog.PROFILE, files=files,
            basicPins={name: value[1] for name, value in self.basic_pins.items()},
            licenses={k: dict(id=v) for k, v in dict(esdb='LicenseRef-ESDB', ngsl='CC-BY-SA-4.0',
                mdn='CC-BY-SA-2.5-or-later', homebrew='BSD-2-Clause', homebrew_analytics='BSD-2-Clause').items()})
        h.dump(self.source / 'dictionary-sources.json', self.manifest)
        self.patches = [patch.object(catalog, 'BASIC', self.basic_pins),
            patch.object(catalog.lexical, 'source_files', return_value={'esdb': dict(databaseSha256=h.replay.sha(self.esdb / 'esdb.db'))}),
            patch.object(catalog.lexical, 'wordnet', return_value={}),
            patch.object(catalog.lexical, 'corpus_words', return_value={})]
        for p in self.patches:
            p.start()
        self.categories = {'domain_daily', 'domain_technology', 'noun', 'noun_proper', 'name_person', 'name_product',
            'verb', 'verb_base', 'verb_past', 'verb_ing', 'noun_count_singular', 'noun_count_plural', 'adjective', 'adjective_base'}
        self.existing = {'go', 'going', 'child', 'alice', 'august', 'false'}

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temporary.cleanup()

    def collect(self, **kwargs):
        return catalog.collect(self.source, self.esdb, self.categories, self.existing, kwargs.get('excluded', set()),
            audit_dir=kwargs.get('audit_dir'))

    def test_source_paradigms_preserve_irregular_forms_and_lemma_identity(self):
        rows, _ = self.collect()
        by_surface = {r['surface']: r for r in rows}
        went = by_surface['went']['entries'][0]
        children = by_surface['children']['entries'][0]
        self.assertEqual('go', went['lemma'])
        self.assertIn('verb_past', went['categories'])
        self.assertNotIn('verb_base', went['categories'])
        self.assertEqual('child', children['lemma'])
        self.assertIn('noun_count_plural', children['categories'])
        self.assertNotIn('childs', by_surface)
        self.assertIn('inflection', by_surface['went']['facets'])

    def test_case_variants_are_collected_without_inventing_source_case(self):
        rows, _ = self.collect()
        by_surface = {r['surface']: r for r in rows}
        self.assertIn('August', by_surface)
        self.assertIn('orthography', by_surface['August']['facets'])
        self.assertNotIn('FALSE', by_surface)
        self.assertNotIn('false', by_surface)

    def test_person_names_have_name_roles_without_generated_possessives(self):
        rows, _ = self.collect()
        by_surface = {r['surface']: r for r in rows}
        self.assertIn('name_person', by_surface['Alice']['entries'][0]['categories'])
        self.assertIn('person', by_surface['Alice']['facets'])
        self.assertNotIn("Alice's", by_surface)

    def test_a_basic_noun_does_not_automatically_license_a_rare_verb_inflection(self):
        rows, _ = self.collect(audit_dir=self.root)
        self.assertNotIn('braining', {r['surface'] for r in rows})
        withheld = h.json_lines(self.root / 'dictionary-withheld.jsonl')
        record = next(r for r in withheld if r['surface'] == 'braining')
        self.assertEqual('inflection-needs-usage-review', record['reason'])
        self.assertEqual(0, record['proof']['lemmaPosOccurrences'])

    def test_a_common_verb_does_not_license_an_unobserved_secondary_paradigm(self):
        rows, _ = self.collect(audit_dir=self.root)
        self.assertNotIn('hided', {r['surface'] for r in rows})
        withheld = h.json_lines(self.root / 'dictionary-withheld.jsonl')
        record = next(r for r in withheld if r['surface'] == 'hided')
        self.assertEqual(2, record['proof']['lemmaPosOccurrences'])
        self.assertEqual(0, record['proof']['formPosOccurrences'])

    def test_technical_labels_do_not_infer_lexical_pos_or_morphology(self):
        rows, _ = self.collect()
        entry = next(r for r in rows if r['surface'] == 'Term 5')['entries'][0]
        self.assertEqual('domain_technology', entry['categories'])
        self.assertEqual(entry['surface'], entry['lemma'])
        self.assertEqual('https://developer.mozilla.org/en-US/docs/Glossary/Term_5', entry['evidence'])

    def test_products_keep_display_names_and_popularity_provenance(self):
        rows, _ = self.collect()
        by_surface = {r['surface']: r for r in rows}
        self.assertIn('Widget Pro', by_surface)
        self.assertNotIn('widget', by_surface)
        self.assertNotIn('Retired App', by_surface)
        proof = by_surface['Widget Pro']['proofs'][0]
        self.assertEqual('name', proof['field'])
        self.assertEqual(1, proof['catalogRank'])
        self.assertEqual('BSD-2-Clause', proof['licenseId'])
        self.assertNotIn('inflection', by_surface['Widget Pro']['facets'])

    def test_unsupported_spelling_is_withheld_and_never_rewritten(self):
        rows, manifest = self.collect(audit_dir=self.root)
        self.assertNotIn('C++ Builder', {r['surface'] for r in rows})
        self.assertNotIn('C Builder', {r['surface'] for r in rows})
        withheld = h.json_lines(self.root / 'dictionary-withheld.jsonl')
        self.assertTrue(any(r['surface'] == 'C++ Builder' and r['reason'] == 'unsupported-format' for r in withheld))
        self.assertGreater(manifest['dictionaryCatalog']['withheldReasons']['unsupported-format'], 0)

    def test_base_exclusions_also_block_case_variants(self):
        rows, _ = self.collect(excluded={'alice'})
        self.assertNotIn('Alice', {r['surface'] for r in rows})

    def test_license_ids_and_complete_notice_hashes_are_required(self):
        catalog.verify(self.source)
        self.manifest['licenses']['mdn']['id'] = 'MIT'
        h.dump(self.source / 'dictionary-sources.json', self.manifest)
        with self.assertRaisesRegex(ValueError, 'license policy'):
            catalog.verify(self.source)

    def test_modified_source_or_license_is_rejected(self):
        (self.source / 'mdn-license.md').write_text('changed notice')
        with self.assertRaisesRegex(ValueError, 'Changed dictionary source or notice'):
            self.collect()

    def test_short_glossary_extraction_is_not_treated_as_a_complete_catalog(self):
        (self.source / 'mdn-glossary.html').write_text('<a href="/en-US/docs/Glossary/one">one</a>')
        self.manifest['files']['mdn-glossary.html'].update(sha256=h.replay.sha(self.source / 'mdn-glossary.html'),
            bytes=(self.source / 'mdn-glossary.html').stat().st_size)
        h.dump(self.source / 'dictionary-sources.json', self.manifest)
        with self.assertRaisesRegex(ValueError, 'extraction incomplete'):
            self.collect()

    def test_selection_keeps_categories_separate_and_does_not_fill_with_names(self):
        def candidate(identifier, facet, rank):
            return dict(id=identifier, facets=[facet], priority=[rank, 0, identifier])
        rows = [candidate('person-' + str(i), 'person', i) for i in range(100)]
        rows += [candidate('basic', 'basic', 1), candidate('technical', 'technology', 1), candidate('product', 'product', 1)]
        selected = catalog.balanced(rows, 14)
        self.assertEqual({'basic', 'technical', 'product', 'person-0', 'person-1'}, {r['id'] for r in selected})
        self.assertEqual(selected, catalog.balanced(rows, 14))

    def test_facet_priorities_prevent_another_sense_from_promoting_an_obscure_product(self):
        rows = [dict(id='old', facets=['product'], priority=[0, 0, 'old'], facetPriorities={'product': [1, 500, 'old']}),
            dict(id='popular', facets=['product'], priority=[1, 1, 'popular'], facetPriorities={'product': [1, 1, 'popular']})]
        self.assertEqual('popular', catalog.balanced(rows, 1)[0]['id'])

    def test_adoption_reextracts_sources_and_is_idempotent_without_model_calls(self):
        rows, manifest = self.collect()
        rows = catalog.balanced(rows, 21)
        run = self.root / 'run'
        run.mkdir()
        h.write_lines(run / 'candidates.jsonl', rows)
        h.write_lines(run / 'baseline.jsonl', [dict(surface=s) for s in sorted(self.existing)])
        inputs = run / 'base-inputs/grammar'
        inputs.mkdir(parents=True)
        (inputs / 'categories.tsv').write_text('category\n' + '\n'.join(sorted(self.categories)) + '\n')
        (inputs.parent / 'decisions.tsv').write_text('surface\tdecision\n')
        assets = self.root / 'assets'
        assets.mkdir()
        (assets / 'token.dat').write_bytes(b'fixture')
        config = dict(schemaVersion=1, sourceProfile=catalog.PROFILE, candidatesSha256=h.replay.sha(run / 'candidates.jsonl'),
            assets=str(assets), assetHashes=h.asset_hashes(assets), sources=manifest)
        h.dump(run / 'run.json', config)
        with sqlite3.connect(run / 'state.sqlite3') as c:
            c.executescript('create table candidates(id text,position int,payload text,decision text,result text,proposal text);')
            c.executemany('insert into candidates values(?,?,?,null,null,null)',
                [(r['id'], i, json.dumps(r)) for i, r in enumerate(rows)])
        args = argparse.Namespace(work_dir=run, source_dir=self.source, esdb_dir=self.esdb)
        result = catalog.adopt(args)
        self.assertEqual(len(rows), result['adopted'])
        self.assertEqual(0, result['apiCalls'])
        self.assertEqual(0, catalog.adopt(args)['adopted'])


if __name__ == '__main__':
    unittest.main()
