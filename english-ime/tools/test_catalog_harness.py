import argparse
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import catalog_harness as c
import vocabulary_harness as h


def target(word, kind='lexical', proofs=True, tier='core'):
    return dict(id=c.identity([word, kind]), surface=word, kind=kind, topics=['technology.test'], tier=tier,
        formKind='head', sourceEntry=None, proofs=[dict(id='proof-' + word, source='fixture',
            url='https://example.org/source', sha256='a' * 64, license='MIT')] if proofs else [])

def form(word, identifier=None, members=()):
    return dict(lexeme_id=identifier or 'form-' + word, lemma=word, surface=word,
        evidence='https://example.org/existing', memberships=set(members))

TOPICS = {'technology.test': dict(id='technology.test', category='topic_technology_test', domain='technology',
    label='Test vocabulary', definition='Source-attested surface vocabulary, not sense disambiguation.', examples='word')}


class CatalogHarnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_existing_words_receive_only_metadata(self):
        rows, ops = c.audit([target('algorithm')], TOPICS, {('algorithm', 'algorithm')},
            {'algorithm': [form('algorithm', members={'noun'})]}, set())
        self.assertEqual('metadata_only', rows[0]['status'])
        self.assertEqual([], ops[0]['entries'])
        self.assertEqual('form-algorithm', ops[0]['metadata'][0]['lexeme_id'])
        self.assertNotIn('noun', ops[0]['metadata'][0]['categories'])

    def test_existing_reviewed_data_can_support_topics_but_never_a_new_word(self):
        rows, ops = c.audit([target('known', proofs=False), target('unknown', proofs=False)], TOPICS,
            {('known', 'known')}, {'known': [form('known')]}, set())
        self.assertEqual(['metadata_only', 'blocked_evidence'], [r['status'] for r in rows])
        self.assertEqual('reviewed_existing', ops[0]['proofs'][0]['source'])

    def test_person_binding_prefers_the_existing_person_analysis(self):
        rows, ops = c.audit([target('Anderson', 'person', proofs=False)], TOPICS, {('anderson', 'Anderson')},
            {'Anderson': [form('Anderson', 'a-place', {'name_place'}), form('Anderson', 'z-person', {'name_person'})]}, set())
        self.assertEqual('metadata_only', rows[0]['status'])
        self.assertEqual('z-person', ops[0]['metadata'][0]['lexeme_id'])
        rows, _ = c.audit([target('Anderson', 'person', proofs=False)], TOPICS, {('anderson', 'Anderson')},
            {'Anderson': [form('Anderson', 'a-place', {'name_place'})]}, set())
        self.assertEqual('blocked_evidence', rows[0]['status'])

    def test_case_variant_and_new_spelling_are_separate(self):
        rows, ops = c.audit([target('RAM'), target('new term')], TOPICS, {('ram', 'ram')}, {}, set())
        self.assertEqual(['case_variant', 'new_spelling'], [r['status'] for r in rows])
        self.assertEqual(['RAM', 'new term'], [r['entries'][0]['surface'] for r in ops])

    def test_new_unsupported_labels_remain_targets_and_are_never_rewritten(self):
        rows, ops = c.audit([target('.NET SDK'), target('C++')], TOPICS, set(), {}, set())
        self.assertEqual(2, len(rows))
        self.assertTrue(all(r['status'] == 'blocked_format' for r in rows))
        self.assertEqual([], ops)

    def test_already_encoded_punctuation_can_receive_metadata_without_new_readings(self):
        rows, ops = c.audit([target('C++', 'language')], TOPICS, {('cpp', 'C++')},
            {'C++': [form('C++', members={'identifier_computer_language'})]}, set())
        self.assertTrue(rows[0]['registered'])
        self.assertEqual([], ops[0]['entries'])

    def test_exclusions_cannot_be_bypassed_by_case(self):
        rows, ops = c.audit([target('Rejected')], TOPICS, set(), {}, {'rejected'})
        self.assertEqual('blocked_base_or_reading', rows[0]['status'])
        self.assertFalse(ops)

    def test_scope_does_not_inherit_title_case_or_footer_links(self):
        source = self.root / 'sources'; source.mkdir()
        lexical = self.root / 'lexical'; lexical.mkdir()
        (lexical / 'cask.json').write_text('[]')
        (lexical / 'cask-analytics.json').write_text('{"items": []}')
        (lexical / 'dictionary-sources.json').write_text('{}')
        taxonomy = self.root / 'taxonomy.json'
        scopes = self.root / 'scopes.json'
        h.dump(taxonomy, dict(schemaVersion=2, topics=list(TOPICS.values())))
        h.dump(scopes, dict(schemaVersion=2, basicLists=False, productRankLimit=0,
            scopes=[dict(topic='technology.test', kind='lexical', tier='core', sources=['python'], terms=['algorithm'])]))
        notice = source / 'LICENSE.txt'; notice.write_text('Fixture license')
        document = dict(file='fixture.rst', url='https://example.org/glossary', sha256='a' * 64,
            notice='LICENSE.txt', noticeUrl='https://example.org/license', noticeSha256=h.replay.sha(notice),
            license='MIT', attribution='Fixture contributors')
        sources = dict(documents={'python': document}, texts={'python': 'Algorithm heading; unrelated footer text'},
            words={}, paradigms={}, wordnet={}, mdnLabels={}, pages=[], languages=set(), pins={}, legacy={})
        args = argparse.Namespace(source_dir=source, lexical_source_dir=lexical, esdb_dir=self.root,
            taxonomy=taxonomy, scopes=scopes)
        with patch.object(c, 'load_sources', return_value=sources):
            rows, _, _ = c.compile_targets(args)
        self.assertEqual(['algorithm'], [r['surface'] for r in rows])
        self.assertEqual('scope-declared-lowercase', rows[0]['proofs'][0]['casePolicy'])
        self.assertNotIn('Algorithm', {r['surface'] for r in rows})

    def test_attestation_requires_complete_literal_terms(self):
        self.assertFalse(c.attested('ram', 'program'))
        self.assertFalse(c.attested('large language model', 'large language models'))
        self.assertTrue(c.attested('regular expression', 'A regular expression, here.'))
        self.assertTrue(c.attested('regular expression', 'Regular Expression', True))
        self.assertFalse(c.attested('RAM', 'Ram'))
        self.assertEqual('real text', c.plain('<script>invented term</script><p>real text</p>'))

    def test_attested_noun_head_does_not_inherit_an_unrelated_verb_paradigm(self):
        source = self.root / 'sources'; source.mkdir()
        lexical = self.root / 'lexical'; lexical.mkdir()
        (lexical / 'cask.json').write_text('[]')
        (lexical / 'cask-analytics.json').write_text('{"items": []}')
        (lexical / 'dictionary-sources.json').write_text('{}')
        taxonomy = self.root / 'taxonomy.json'; scopes = self.root / 'scopes.json'
        h.dump(taxonomy, dict(schemaVersion=2, topics=list(TOPICS.values())))
        h.dump(scopes, dict(schemaVersion=2, basicLists=False, productRankLimit=0, scopes=[
            dict(topic='technology.test', kind='lexical', tier='core', sources=['esdb', 'wiktionary'], terms=['kerning'])]))
        sources = dict(documents={}, texts={}, words={'kerning': [dict(word='kerning', lemma='kern',
            pos_class='', pos='vg', base_pos='v', word_id=1, lemma_id=2)]}, paradigms={2: {'vg'}},
            wordnet={}, mdnLabels={}, pages=[], languages=set(), pins={'esdb': {'databaseSha256': 'a' * 64}}, legacy={})
        proof = dict(source='wiktionary', revision=42, headRole='noun', url='https://en.wiktionary.org/wiki/kerning')
        args = argparse.Namespace(source_dir=source, lexical_source_dir=lexical, esdb_dir=self.root, taxonomy=taxonomy, scopes=scopes)
        with patch.object(c, 'load_sources', return_value=sources), \
             patch.object(c, 'roles_for', return_value={'verb'}), patch.object(c, 'categories_for', return_value={'verb', 'verb_ing'}), \
             patch.object(c.world_sources, 'matching', return_value=[proof]):
            targets, _, _ = c.compile_targets(args)
        self.assertEqual(dict(lemma='kerning', categories=['noun'], source_ref='wiktionary:42'), targets[0]['sourceEntry'])
        self.assertEqual('head', targets[0]['formKind'])

    def test_unknown_topics_and_providers_are_rejected(self):
        taxonomy = self.root / 'taxonomy.json'; scopes = self.root / 'scopes.json'
        h.dump(taxonomy, dict(schemaVersion=2, topics=list(TOPICS.values())))
        scope = dict(topic='technology.test', kind='lexical', tier='core', sources=['unlicensed-provider'], terms=['word'])
        h.dump(scopes, dict(schemaVersion=2, scopes=[scope]))
        with self.assertRaisesRegex(ValueError, 'Invalid scope'):
            c.registry(taxonomy, scopes)

    def test_source_and_license_snapshots_cannot_change(self):
        records = {}
        for name, (filename, url, notice, notice_url, license_id, author) in c.DOCUMENTS.items():
            (self.root / filename).write_text('Fixture ' + name)
            (self.root / notice).write_text('Fixture notice ' + name)
            records[name] = dict(file=filename, url=url, sha256=h.replay.sha(self.root / filename), notice=notice,
                noticeUrl=notice_url, noticeSha256=h.replay.sha(self.root / notice), license=license_id, attribution=author)
        h.dump(self.root / 'catalog-sources.json', dict(schemaVersion=2, sources=records))
        c.verify_documents(self.root)
        (self.root / records['python']['notice']).write_text('Modified license')
        with self.assertRaisesRegex(ValueError, 'Changed source or notice'):
            c.verify_documents(self.root)

    def run_fixture(self):
        run = self.root / 'run'; run.mkdir()
        assets = self.root / 'assets'; assets.mkdir()
        (assets / 'token.dat').write_bytes(b'fixture dictionary')
        targets = [target('known'), target('new one'), target('new two'), target('new three'), target('.NET SDK')]
        pairs, analyses = {('known', 'known')}, {'known': [form('known')]}
        before, operations = c.audit(targets, TOPICS, pairs, analyses, set())
        for name, values in [('targets', targets), ('before', before), ('candidates', operations)]:
            h.write_lines(run / (name + '.jsonl'), values)
        base = run / 'base-inputs'; base.mkdir()
        (base / 'decisions.tsv').write_text('surface\tdecision\n')
        config = dict(schemaVersion=1, sourceProfile=c.PROFILE, sources={'catalogV2': {'taxonomySha256': 'a' * 64}},
            targetsSha256=h.replay.sha(run / 'targets.jsonl'), candidatesSha256=h.replay.sha(run / 'candidates.jsonl'),
            assets=str(assets), assetHashes=h.asset_hashes(assets), sourcePaths={}, topics=TOPICS)
        h.dump(run / 'run.json', config)
        with sqlite3.connect(run / 'state.sqlite3') as db:
            db.execute('create table candidates(id text,position int,payload text,proposal text,decision text,result text)')
            db.executemany('insert into candidates values(?,?,?,null,null,null)',
                [(r['id'], i, json.dumps(r)) for i, r in enumerate(operations)])
        args = argparse.Namespace(work_dir=run, cli=self.root / 'cli', batch_size=2)
        return args, targets, pairs, analyses, config

    def test_batched_adoption_checkpoints_resume_and_do_not_double_adopt(self):
        args, targets, pairs, analyses, config = self.run_fixture()
        original = h.write_lines
        calls = 0
        def interrupted(path, rows):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('simulated interruption')
            original(path, rows)
        with patch.object(c, 'compile_targets', return_value=(targets, TOPICS, config['sources'])), \
             patch.object(c, 'inventory', return_value=(pairs, analyses)), patch.object(h, 'write_lines', interrupted):
            with self.assertRaisesRegex(OSError, 'interruption'):
                c.adopt(args)
        with sqlite3.connect(args.work_dir / 'state.sqlite3') as db:
            self.assertEqual(2, db.execute("select count(*) from candidates where decision='include'").fetchone()[0])
        with patch.object(c, 'compile_targets', return_value=(targets, TOPICS, config['sources'])), \
             patch.object(c, 'inventory', return_value=(pairs, analyses)):
            self.assertEqual({'include': 2}, c.adopt(args)['decisions'])
            self.assertEqual({}, c.adopt(args)['decisions'])

    def test_report_keeps_blocked_targets_in_its_denominator(self):
        args, targets, pairs, analyses, _ = self.run_fixture()
        args.out = self.root / 'report'; args.assets = None
        with patch.object(c, 'inventory', return_value=(pairs, analyses)):
            result = c.report(args)
        self.assertEqual(5, result['totals']['targets'])
        self.assertEqual(1, result['totals']['registeredAfter'])
        self.assertEqual(5, result['totals']['unresolved'])
        self.assertEqual(1, result['totals']['blockedFormat'])
        report = h.replay.read_json(args.out / 'report.json')
        self.assertEqual(5, len(report['unresolved']))

    def test_metadata_completion_does_not_count_as_new_vocabulary(self):
        args, _, pairs, analyses, _ = self.run_fixture()
        args.out = self.root / 'after'; args.assets = None
        analyses['known'][0]['memberships'] |= {'domain_technology', 'topic_technology_test'}
        with patch.object(c, 'inventory', return_value=(pairs, analyses)):
            result = c.report(args)
        self.assertEqual(0, result['newRegisteredSpellings'])
        self.assertEqual(1, result['totals']['topicCompleteAfter'])

    def test_membership_merge_preserves_prior_tags_and_rejects_lemma_conflicts(self):
        row = dict(lexeme_id='word', surface='word', lemma='word', categories='noun,domain_daily', domain='daily',
            evidence='https://example.org/word', source_ref='fixture')
        later = dict(row, categories='topic_technology_test,domain_technology')
        result = h.merge_memberships([row, later])
        self.assertEqual({'noun', 'domain_daily', 'domain_technology', 'topic_technology_test'}, set(result[0]['categories'].split(',')))
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            h.merge_memberships([row, dict(later, lemma='other')])


if __name__ == '__main__':
    unittest.main()
