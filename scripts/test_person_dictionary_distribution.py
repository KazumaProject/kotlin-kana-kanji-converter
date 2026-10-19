"""Replay tests for strict source-backed person distribution artifacts.

All names and evidence contents are synthetic. No test asserts anything about
actual people's occupations or appearance histories.
"""
import contextlib
import gzip
import io
import json
from pathlib import Path
import shutil
import sqlite3
import unittest

import classify_person_names as classifier
import person_dictionary_distribution as pack
import person_subclassification as person
import review_person_names as reviewer
import test_classified_distribution as base_fixture
from test_person_names import DECLARATIONS, entry


class PersonDictionaryDistributionTest(unittest.TestCase):
    def setUp(self):
        fixture = base_fixture.DistributionTest('test_freeze_is_deterministic')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        actual = Path(__file__).resolve().parents[1] / 'src/main/classification'
        # Freeze using the actual 28-category topology, with synthetic records.
        fixture.taxonomy.write_bytes((actual / 'categories.json').read_bytes())
        fixture.freeze()
        directory = self.root / 'src/main/classification'
        shutil.copyfile(actual / 'person-taxonomy.json', directory / 'person-taxonomy.json')
        self.workspace = self.root / 'workspace'
        with contextlib.redirect_stdout(io.StringIO()):
            person.prepare(self.root, self.workspace, batch_size=100)
        self.source = self.root / 'source.xml.gz'
        xml = ('<?xml version="1.0"?>' + DECLARATIONS + '<JMnedict>' +
               entry(1, ['甲'], 'あ', 'surname') +
               entry(2, ['乙'], 'い', 'person') + '</JMnedict>')
        self.source.write_bytes(gzip.compress(xml.encode(), mtime=0))
        self.classified = self.root / 'classified'
        with contextlib.redirect_stdout(io.StringIO()):
            classifier.classify(self.root, self.source, self.classified, workspace=self.workspace)
        self.metadata = self.root / 'metadata.sqlite3'
        with contextlib.closing(sqlite3.connect(self.metadata)) as connection:
            connection.executescript('CREATE TABLE batches(batch_id INTEGER,titles TEXT,status TEXT);'
                                     'CREATE TABLE responses(batch_id INTEGER,part INTEGER,http_status INTEGER,'
                                     'sha256 TEXT,payload_gzip BLOB);')
            connection.commit()
        self.reviewed = self.root / 'reviewed'
        reviewer.review(self.root, self.source, self.classified, self.workspace,
                        self.reviewed, self.metadata)
        self.notices = self.root / 'SYNTHETIC-NOTICE.txt'
        self.notices.write_text('Synthetic fixture source attribution and terms.\n')

    def build(self):
        return pack.build(self.root, self.workspace, self.source,
                          self.classified / 'proposals.jsonl', self.reviewed / 'reviews.jsonl',
                          self.classified / 'manifest.json', self.reviewed / 'source-audit.json',
                          self.metadata, [self.notices])

    def rows(self, path):
        with gzip.open(path, 'rt') as stream:
            return [line.rstrip('\n').split('\t') for line in stream]

    def refresh_outer_hash(self, directory, name):
        manifest_path = directory / 'distribution-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files'][name] = person.sha(directory / name)
        person.write_json(manifest_path, manifest)

    def test_full_partition_and_category_topology_replays(self):
        directory = self.build()
        manifest = pack.replay(self.root, directory)
        self.assertEqual(manifest['personItems'], 2)
        self.assertEqual(manifest['personCounts']['general'], 1)
        self.assertEqual(manifest['personCounts']['hold'], 1)
        standard_categories = json.loads((directory / 'categories.json').read_text())['categories']
        self.assertEqual(len(standard_categories), 51)
        self.assertNotIn('person', {v['id'] for v in standard_categories})
        self.assertNotIn('person_adult_performer', {v['id'] for v in standard_categories})
        name_categories = json.loads((directory / 'person-categories.json').read_text())['categories']
        self.assertEqual(len(name_categories), 25)
        dictionaries = directory / 'person-dictionaries'
        self.assertEqual(len(list(dictionaries.glob('person_*.tsv.gz'))), 25)
        self.assertEqual(self.rows(dictionaries / 'person_adult_performer.tsv.gz'), [])
        admitted = self.rows(directory / 'person-records.tsv.gz')
        held = self.rows(directory / 'held-records.tsv.gz')
        self.assertEqual({(r[1], r[5]) for r in admitted}, {('あ', '甲')})
        self.assertEqual({(r[1], r[5]) for r in held}, {('い', '乙')})
        self.assertEqual(self.rows(directory / 'adult-records.tsv.gz'), [])
        active = self.rows(directory / 'distribution-candidates.tsv.gz')
        self.assertFalse(any(r[0] == 'person' or r[5] == '乙' for r in active))
        self.assertEqual(next(r for r in admitted if r[5] == '甲')[2:5], ['1', '1', '100'])

    def test_updated_manifest_hash_cannot_conceal_cost_tampering(self):
        directory = self.build()
        name = 'distribution-candidates.tsv.gz'
        rows = self.rows(directory / name)
        changed = next(row for row in rows if row[0] == 'person_surname')
        changed[4] = '1234'
        pack.gzip_rows(directory / name, rows)
        self.refresh_outer_hash(directory, name)
        with self.assertRaisesRegex(ValueError, 'record partition/filter differs'):
            pack.replay(self.root, directory)

    def test_updated_outer_hash_cannot_conceal_source_xml_tampering(self):
        directory = self.build()
        name = 'evidence/JMnedict.xml.gz'
        path = directory / name
        xml = gzip.decompress(path.read_bytes()).replace(b'<reb>', b'<reb>z', 1)
        path.write_bytes(gzip.compress(xml, mtime=0))
        self.refresh_outer_hash(directory, name)
        with self.assertRaisesRegex(ValueError, 'name source changed'):
            pack.replay(self.root, directory)

    def test_generic_recipe_rejects_individual_appearance_status_before_admission(self):
        work = self.root / 'gate-input'
        work.mkdir()
        for state in ['confirmed', 'reviewed_no_evidence', 'unresolved']:
            with self.subTest(state=state):
                person.write_jsonl(work / 'proposals.jsonl', [{'item_id': 'synthetic',
                                                            'adult_appearance_status': state}])
                with self.assertRaisesRegex(ValueError, 'generic-name recipe cannot assert individual'):
                    pack.assert_name_evidence(self.root, self.root / 'absent-artifact',
                                              {'counts': {}, 'decisions': []}, work)

    def test_missing_source_sidecar_is_rejected_even_when_outer_index_is_changed(self):
        directory = self.build()
        name = 'evidence/source-matches.jsonl.gz'
        (directory / name).unlink()
        manifest_path = directory / 'distribution-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        del manifest['files'][name]
        person.write_json(manifest_path, manifest)
        with self.assertRaises((ValueError, OSError)):
            pack.replay(self.root, directory)


if __name__ == '__main__':
    unittest.main()
