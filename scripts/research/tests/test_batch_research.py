import argparse
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import batch_research as b
import worker as w


def entity(qid='Q1', label='山田', y='やまだ', title=None, qualifiers=None, rank='normal'):
    statement = {'id': qid + '$reading', 'rank': rank,
                 'mainsnak': {'snaktype': 'value', 'datavalue': {'value': y}}}
    if qualifiers is not None:
        statement['qualifiers'] = {'P5168': qualifiers}
    result = {'id': qid, 'labels': {'ja': {'value': label}} if label else {},
              'aliases': {}, 'claims': {'P1814': [statement]},
              'sitelinks': {'jawiki': {'title': title}} if title else {}}
    return result


class BatchResearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = pathlib.Path(self.tmp.name)
        self.db = w.connect(self.root / 'ledger.sqlite'); self.db.executescript(w.SCHEMA)
        self.args = argparse.Namespace(config=str(w.DEFAULT_CONFIG), documents=str(self.root / 'documents'))
        self.cid = w.insert_candidate(self.db, 'やまだ', '山田', 1, 1, 10)
        self.db.execute("UPDATE candidates SET state='needs_review',research_round=0")
        self.db.commit()
        self.catalog = self.root / 'catalog.sqlite'

    def tearDown(self):
        self.db.close(); self.tmp.cleanup()

    def catalog_rows(self, values):
        with sqlite3.connect(self.catalog) as source:
            source.execute('CREATE TABLE entities(id TEXT PRIMARY KEY,body TEXT NOT NULL)')
            for value in values:
                source.execute('INSERT INTO entities VALUES(?,?)', (value['id'], json.dumps(value, ensure_ascii=False)))

    def matches(self, value, surface='山田', reading='やまだ'):
        return b.strict_matches(value, [{'id': 'candidate', 'surface': surface, 'reading': reading}])

    def test_primary_label_reading(self):
        self.assertEqual(1, len(self.matches(entity())))

    def test_reading_of_primary_label_cannot_transfer_to_article_title(self):
        self.assertFalse(self.matches(entity(label='別名', title='山田')))

    def test_title_fallback_only_without_japanese_label(self):
        self.assertEqual(1, len(self.matches(entity(label=None, title='山田'))))

    def test_alias_does_not_inherit_reading(self):
        value = entity(label='別名'); value['aliases'] = {'ja': [{'value': '山田'}]}
        self.assertFalse(self.matches(value))
        self.assertIn('山田', b.observed_names(value))

    def test_japanese_qualified_reading(self):
        q = [{'datavalue': {'value': {'language': 'ja', 'text': '山田'}}}]
        self.assertEqual(1, len(self.matches(entity(label='別名', qualifiers=q))))

    def test_non_japanese_qualifier_does_not_fall_back_to_primary_label(self):
        q = [{'datavalue': {'value': {'language': 'en', 'text': 'Yamada'}}}]
        self.assertFalse(self.matches(entity(qualifiers=q)))

    def test_no_value_qualifier_does_not_fall_back(self):
        self.assertFalse(self.matches(entity(qualifiers=[{'snaktype': 'novalue'}])))

    def test_deprecated_and_mismatching_readings_are_rejected(self):
        self.assertFalse(self.matches(entity(rank='deprecated')))
        self.assertFalse(self.matches(entity(y='やまた')))

    def test_japanese_name_spacing_is_formatting_not_substring(self):
        self.assertEqual(1, len(self.matches(entity(label='山 田', y='やま だ'))))
        self.assertFalse(self.matches(entity(label='田中山田', y='やまだ')))

    def test_primary_kana_needs_independent_name_attestation(self):
        value = entity(label='ヤマダ', y=None); value['claims'] = {}
        self.assertEqual(1, len(self.matches(value, surface='ヤマダ')))
        value['labels'] = {'ja': {'value': '別名'}}; value['aliases'] = {'ja': [{'value': 'ヤマダ'}]}
        self.assertFalse(self.matches(value, surface='ヤマダ'))

    def test_import_pins_literal_source_and_unknown_revision(self):
        value = entity(); self.catalog_rows([value])
        with mock.patch.object(w, 'request_json', side_effect=AssertionError('Network must not be called')):
            report = b.import_catalog(self.db, self.args, self.catalog)
        self.assertTrue(report['complete']); self.assertEqual(1, report['counts']['newReadingCandidates'])
        fact = self.db.execute("SELECT * FROM facts WHERE kind='reading'").fetchone(); body = json.loads(fact['body'])
        doc = self.db.execute('SELECT * FROM documents WHERE id=?', (fact['document_id'],)).fetchone()
        raw = pathlib.Path(doc['path']).read_bytes()
        with sqlite3.connect(self.catalog) as source:
            original = source.execute('SELECT body FROM entities').fetchone()[0].encode()
        self.assertEqual(original, raw)
        self.assertEqual('sha256:' + w.digest(raw), doc['revision'])
        self.assertFalse(body['acquisition']['revisionKnown'])
        self.assertEqual(w.sha(self.catalog), body['acquisition']['catalogSha256'])
        self.assertEqual(0, self.db.execute('SELECT research_round FROM candidates').fetchone()[0])
        self.assertEqual('needs_review', self.db.execute('SELECT state FROM candidates').fetchone()[0])
        self.assertEqual([], json.loads(self.db.execute("SELECT categories FROM facts WHERE kind='context'").fetchone()[0]))

    def test_known_revision_is_preserved(self):
        value = entity(); value['lastrevid'] = 1234; self.catalog_rows([value])
        b.import_catalog(self.db, self.args, self.catalog)
        self.assertEqual('1234', self.db.execute('SELECT revision FROM documents').fetchone()[0])

    def test_resume_and_idempotence(self):
        self.catalog_rows([entity(), entity(qid='Q2', y='やまた')])
        first = b.import_catalog(self.db, self.args, self.catalog, max_entities=1)
        self.assertFalse(first['complete'])
        second = b.import_catalog(self.db, self.args, self.catalog)
        self.assertTrue(second['complete']); self.assertEqual(2, second['counts']['entitiesScanned'])
        self.assertEqual(1, second['counts']['newReadingCandidates'])
        before = self.db.execute('SELECT COUNT(*) FROM facts').fetchone()[0]
        self.assertEqual(second, b.import_catalog(self.db, self.args, self.catalog))
        self.assertEqual(before, self.db.execute('SELECT COUNT(*) FROM facts').fetchone()[0])

    def test_audit_makes_no_ledger_or_document_changes(self):
        self.catalog_rows([entity()]); before = self.db.total_changes
        with mock.patch.object(w, 'Evidence', side_effect=AssertionError('Audit must not create Evidence')):
            report = b.import_catalog(self.db, self.args, self.catalog, audit=True)
        self.assertEqual(1, report['counts']['newReadingCandidates'])
        self.assertEqual(before, self.db.total_changes)
        self.assertFalse((self.root / 'documents').exists())

    def test_slim_metadata_is_rejected(self):
        self.catalog_rows([{'id': 'Q1', 'names': ['山田'], 'readings': ['やまだ']}])
        with self.assertRaisesRegex(ValueError, 'source claims'):
            b.import_catalog(self.db, self.args, self.catalog)
        self.assertEqual(0, self.db.execute('SELECT COUNT(*) FROM facts').fetchone()[0])

    def test_catalog_hash_mismatch_is_rejected_before_changes(self):
        self.catalog_rows([entity()])
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            b.import_catalog(self.db, self.args, self.catalog, expected_sha256='0' * 64)
        self.assertEqual(0, self.db.execute('SELECT COUNT(*) FROM facts').fetchone()[0])

    def test_empty_source_claims_and_labels_may_be_omitted(self):
        source = {'id': 'Q1', 'type': 'item', 'labels': {'ja': {'value': '山田'}}}
        self.catalog_rows([source, {'id': 'Q2', 'type': 'item'}])
        report = b.import_catalog(self.db, self.args, self.catalog)
        self.assertTrue(report['complete'])
        self.assertEqual(2, report['counts']['entitiesScanned'])
        self.assertEqual(0, self.db.execute("SELECT COUNT(*) FROM facts WHERE kind='reading'").fetchone()[0])

    def test_malformed_source_claim_shape_is_rejected(self):
        source = entity(); source['claims'] = []
        self.catalog_rows([source])
        with self.assertRaisesRegex(ValueError, 'field shape'):
            b.import_catalog(self.db, self.args, self.catalog)

    def test_deleted_entity_aliases_are_not_reading_or_context_evidence(self):
        self.catalog_rows([{'id': 'Q1', 'missing': '', 'aliases': {'ja': [{'value': '山田'}]}}])
        report = b.import_catalog(self.db, self.args, self.catalog)
        self.assertEqual(1, report['counts']['missingEntities'])
        self.assertEqual(0, report['counts']['relevantEntities'])
        self.assertEqual(0, self.db.execute('SELECT COUNT(*) FROM facts').fetchone()[0])

    def test_negative_exact_lookup_is_not_a_completed_research_round(self):
        self.catalog_rows([entity(label='別名')])
        with sqlite3.connect(self.catalog) as source:
            source.execute('CREATE TABLE titles(title TEXT PRIMARY KEY,entity_ids TEXT,fetched_at INTEGER)')
            source.execute('INSERT INTO titles VALUES(?,?,?)', ('山田', '[]', 123456))
        report = b.import_catalog(self.db, self.args, self.catalog)
        saved = self.db.execute('SELECT * FROM source_exact_lookups').fetchone()
        self.assertEqual('no-exact-title-match', saved['result'])
        self.assertEqual(123456, saved['source_fetched_at'])
        self.assertEqual(1, report['exactTitleCoverage']['no-exact-title-match'])
        self.assertEqual(('needs_review', 0), tuple(self.db.execute('SELECT state,research_round FROM candidates').fetchone()))

    def test_absent_exact_lookup_is_unchecked(self):
        self.catalog_rows([entity()])
        with sqlite3.connect(self.catalog) as source:
            source.execute('CREATE TABLE titles(title TEXT PRIMARY KEY,entity_ids TEXT,fetched_at INTEGER)')
        report = b.import_catalog(self.db, self.args, self.catalog)
        saved = self.db.execute('SELECT * FROM source_exact_lookups').fetchone()
        self.assertEqual('unchecked', saved['result'])
        self.assertIsNone(saved['source_fetched_at'])
        self.assertIsNone(saved['entity_ids'])
        self.assertEqual(1, report['exactTitleCoverage']['unchecked'])

    def test_explicit_source_redirect_uses_canonical_entity_target(self):
        value = entity(qid='Q2'); value['redirects'] = {'from': 'Q1', 'to': 'Q2'}
        self.catalog_rows([value])
        with sqlite3.connect(self.catalog) as source:
            source.execute("UPDATE entities SET id='Q1'")
        b.import_catalog(self.db, self.args, self.catalog)
        target, raw = self.db.execute("SELECT target,body FROM facts WHERE kind='reading'").fetchone()
        self.assertEqual('Q2', target)
        self.assertEqual('Q1', json.loads(raw)['acquisition']['catalogEntityKey'])

    def test_entity_id_mismatch_without_explicit_redirect_is_rejected(self):
        self.catalog_rows([entity(qid='Q2')])
        with sqlite3.connect(self.catalog) as source:
            source.execute("UPDATE entities SET id='Q1'")
        with self.assertRaisesRegex(ValueError, 'ID mismatch'):
            b.import_catalog(self.db, self.args, self.catalog)

    def test_historical_projection_report_does_not_claim_to_verify_current_catalog(self):
        self.catalog_rows([entity()])
        report_path = self.root / 'source-report.json'
        report_path.write_text(json.dumps({'outputCatalogSha256': 'f' * 64, 'dumpSha256': 'a' * 64,
                                          'notes': ['Selected-field projection']}))
        meta = b.source_metadata(self.catalog, provenance_paths=[report_path])
        source = meta['provenanceFiles'][0]
        self.assertFalse(source['catalogHashMatchesReport'])
        self.assertEqual('a' * 64, source['reportedSource']['dumpSha256'])
        self.assertEqual(w.sha(report_path), source['sha256'])
        self.assertEqual(w.sha(self.catalog), meta['catalogSha256'])

    def test_no_new_candidates_or_negative_rounds_from_unmatched_entity(self):
        self.catalog_rows([entity(label='無関係', y='むかんけい')])
        report = b.import_catalog(self.db, self.args, self.catalog)
        self.assertEqual(0, report['counts']['relevantEntities'])
        self.assertEqual(1, self.db.execute('SELECT COUNT(*) FROM candidates').fetchone()[0])
        self.assertEqual(0, self.db.execute('SELECT COUNT(*) FROM facts').fetchone()[0])
        self.assertEqual(0, self.db.execute('SELECT research_round FROM candidates').fetchone()[0])


if __name__ == '__main__':
    unittest.main()
