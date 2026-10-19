"""Adversarial tests for independent JMnedict generic-name classification.

Fixtures have synthetic names. These tests validate source matching and routing,
not real people's occupations or adult appearance histories.
"""
import contextlib
import gzip
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import classify_person_names as classifier
import review_person_names as reviewer
import person_subclassification as core
import test_classified_distribution as base_fixture

DECLARATIONS = '''<!DOCTYPE JMnedict [
<!ENTITY surname "family or surname">
<!ENTITY given "given name or forename, gender not specified">
<!ENTITY fem "female given name or forename">
<!ENTITY masc "male given name or forename">
<!ENTITY unclass "unclassified name">
<!ENTITY person "full name of a particular person">
<!ENTITY company "company name">
]>'''


def entry(seq, surface, reading, *types, restrictions=()):
    spellings = ''.join('<k_ele><keb>' + s + '</keb></k_ele>' for s in surface)
    restrict = ''.join('<re_restr>' + s + '</re_restr>' for s in restrictions)
    kinds = ''.join('<name_type>&' + t + ';</name_type>' for t in types)
    return (f'<entry><ent_seq>{seq}</ent_seq>{spellings}'
            f'<r_ele><reb>{reading}</reb>{restrict}</r_ele>'
            f'<trans>{kinds}<trans_det>Synthetic fixture</trans_det></trans></entry>')


class PersonNamesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def source(self, entries, name='source.xml.gz'):
        path = self.directory / name
        xml = '<?xml version="1.0"?>' + DECLARATIONS + '<JMnedict>' + ''.join(entries) + '</JMnedict>'
        path.write_bytes(gzip.compress(xml.encode('utf-8'), mtime=0))
        return path

    def both(self, source, pairs):
        return (classifier.match_source(source, set(pairs)),
                reviewer.parse_source(source, set(pairs)))

    def verdicts(self, matches):
        category, _ = classifier.category_for(matches)
        assessment = reviewer.assess_match(matches)
        return category, assessment

    def test_internal_dtd_entities_and_generic_types(self):
        source = self.source([entry(1, ['架姓'], 'かせい', 'surname'),
                              entry(2, ['架名'], 'かな', 'given'),
                              entry(3, ['架名二'], 'かなに', 'fem', 'masc')])
        pairs = {('かせい', '架姓'), ('かな', '架名'), ('かなに', '架名二')}
        for parsed in self.both(source, pairs):
            for pair, expected in [(('かせい', '架姓'), 'surname'),
                                   (('かな', '架名'), 'given_name'),
                                   (('かなに', '架名二'), 'given_name')]:
                category, assessment = self.verdicts(parsed[pair])
                self.assertEqual(category, expected)
                self.assertTrue(assessment['eligible'])
                self.assertIn(expected, assessment['categories'])

    def test_specific_person_is_never_a_generic_name(self):
        source = self.source([entry(1, ['架空実名'], 'かくうじつめい', 'person')])
        for parsed in self.both(source, {('かくうじつめい', '架空実名')}):
            category, assessment = self.verdicts(parsed[('かくうじつめい', '架空実名')])
            self.assertIsNone(category)
            self.assertFalse(assessment['eligible'])

    def test_same_pair_person_sense_blocks_generic_sense(self):
        source = self.source([entry(1, ['重名'], 'じゅうめい', 'surname'),
                              entry(2, ['重名'], 'じゅうめい', 'person')])
        for parsed in self.both(source, {('じゅうめい', '重名')}):
            category, assessment = self.verdicts(parsed[('じゅうめい', '重名')])
            self.assertIsNone(category)
            self.assertFalse(assessment['eligible'])

    def test_missing_type_on_shared_source_entry_prevents_generic_adoption(self):
        source = self.source([entry(1, ['重名'], 'じゅうめい', 'surname'),
                              entry(2, ['重名'], 'じゅうめい')])
        for parsed in self.both(source, {('じゅうめい', '重名')}):
            category, assessment = self.verdicts(parsed[('じゅうめい', '重名')])
            self.assertIsNone(category)
            self.assertFalse(assessment['eligible'])

    def test_external_xml_entity_is_rejected_without_expansion(self):
        xml = ('<?xml version="1.0"?><!DOCTYPE JMnedict ['
               '<!ENTITY surname SYSTEM "https://example.invalid/not-an-evidence-source">]>'
               '<JMnedict>' + entry(1, ['架姓'], 'かせい', 'surname') + '</JMnedict>')
        source = self.directory / 'external.xml.gz'
        source.write_bytes(gzip.compress(xml.encode(), mtime=0))
        for parse in [classifier.match_source, reviewer.parse_source]:
            with self.assertRaises(ValueError):
                parse(source, {('かせい', '架姓')})

    def test_nonexact_reading_or_surface_does_not_match(self):
        source = self.source([entry(1, ['架姓'], 'かせい', 'surname')])
        for parsed in self.both(source, {('がせい', '架姓'), ('かせい', '別姓')}):
            self.assertFalse(parsed.get(('がせい', '架姓')))
            self.assertFalse(parsed.get(('かせい', '別姓')))

    def test_reading_restriction_prevents_cross_product(self):
        source = self.source([entry(1, ['甲乙', '甲丁'], 'こうおつ', 'surname', restrictions=['甲乙'])])
        pairs = {('こうおつ', '甲乙'), ('こうおつ', '甲丁')}
        for parsed in self.both(source, pairs):
            self.assertTrue(parsed.get(('こうおつ', '甲乙')))
            self.assertFalse(parsed.get(('こうおつ', '甲丁')))

    def test_kana_only_entry_and_missing_source_entry(self):
        source = self.source([entry(1, [], 'あい', 'given')])
        for parsed in self.both(source, {('あい', 'あい'), ('あい', '愛'), ('みち', '未知')}):
            self.assertTrue(parsed.get(('あい', 'あい')))
            self.assertFalse(parsed.get(('あい', '愛')))
            self.assertFalse(parsed.get(('みち', '未知')))

    def test_surname_given_collision_holds_but_unclassified_does_not_override(self):
        source = self.source([entry(1, ['重姓'], 'じゅうせい', 'surname', 'given'),
                              entry(2, ['単姓'], 'たんせい', 'surname', 'unclass')])
        for parsed in self.both(source, {('じゅうせい', '重姓'), ('たんせい', '単姓')}):
            category, assessment = self.verdicts(parsed[('じゅうせい', '重姓')])
            self.assertIsNone(category)
            self.assertFalse(assessment['eligible'])
            category, assessment = self.verdicts(parsed[('たんせい', '単姓')])
            self.assertEqual(category, 'surname')
            self.assertTrue(assessment['eligible'])

    def test_non_name_or_missing_type_holds(self):
        source = self.source([entry(1, ['架社'], 'かしゃ', 'company'), entry(2, ['無型'], 'むけい')])
        for parsed in self.both(source, {('かしゃ', '架社'), ('むけい', '無型')}):
            for pair in [('かしゃ', '架社'), ('むけい', '無型')]:
                category, assessment = self.verdicts(parsed.get(pair, []))
                self.assertIsNone(category)
                self.assertFalse(assessment['eligible'])

    def integration(self, source_entries=None):
        fixture = base_fixture.DistributionTest('test_freeze_is_deterministic')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.freeze()
        root = fixture.root
        taxonomy_dir = root / 'src/main/classification'
        shutil.copyfile(Path(__file__).resolve().parents[1] / 'src/main/classification/person-taxonomy.json',
                        taxonomy_dir / 'person-taxonomy.json')
        workspace = root / 'workspace'
        with contextlib.redirect_stdout(io.StringIO()):
            core.prepare(root, workspace, batch_size=2)
        source = self.source(source_entries if source_entries is not None else
                             [entry(1, ['甲'], 'あ', 'surname'), entry(2, ['乙'], 'い', 'given')])
        classified = root / 'classified'
        with contextlib.redirect_stdout(io.StringIO()):
            classifier.classify(root, source, classified, workspace=workspace)
        return root, workspace, source, classified

    def run_review(self, root, workspace, source, classified, output, metadata=None):
        command = [sys.executable, str(Path(reviewer.__file__)), '--root', str(root),
                   '--source', str(source), '--classifier-output', str(classified),
                   '--workspace', str(workspace), '--output', str(output)]
        if metadata:
            command.extend(['--metadata-db', str(metadata)])
        return subprocess.run(command, text=True, capture_output=True)

    def metadata(self, categories, corrupt=False, incomplete=False):
        database = self.directory / 'metadata.sqlite3'
        with sqlite3.connect(database) as connection:
            connection.executescript('CREATE TABLE batches(batch_id INTEGER,titles TEXT,status TEXT);'
                                     'CREATE TABLE responses(batch_id INTEGER,part INTEGER,http_status INTEGER,'
                                     'sha256 TEXT,payload_gzip BLOB);')
            raw = {'query': {'pages': {'1': {'pageid': 1, 'title': '甲',
                   'categories': [{'title': label} for label in categories]}}}}
            if incomplete:
                raw['continue'] = {'clcontinue': '1|next', 'continue': '||'}
            encoded = json.dumps(raw, ensure_ascii=False).encode()
            import hashlib
            digest = hashlib.sha256(encoded).hexdigest()
            if corrupt:
                digest = '0' * 64
            connection.execute('INSERT INTO batches VALUES(?,?,?)', (0, '["甲"]', 'complete'))
            connection.execute('INSERT INTO responses VALUES(?,?,?,?,?)',
                               (0, 0, 200, digest, gzip.compress(encoded, mtime=0)))
        return database

    def test_independent_review_happy_path_is_source_supported(self):
        root, workspace, source, classified = self.integration()
        output = root / 'reviewed'
        result = self.run_review(root, workspace, source, classified, output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        reviews = [json.loads(line) for line in (output / 'reviews.jsonl').read_text().splitlines()]
        self.assertEqual(len(reviews), 2)
        self.assertEqual({row['decision'] for row in reviews}, {'approve'})

    def test_positive_raw_metadata_blocks_generic_shared_form(self):
        root, workspace, source, classified = self.integration()
        metadata = self.metadata(['Category:日本のAV女優'])
        blocked, digest = reviewer.metadata_blockers(metadata)
        self.assertEqual(blocked, {'甲'})
        self.assertIsInstance(digest, str)
        output = root / 'blocked-review'
        result = self.run_review(root, workspace, source, classified, output, metadata)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        items = {item['item_id']: item for item in core.load_workspace(root, workspace)[2]}
        reviews = {items[row['item_id']]['surface']: row for row in
                   map(json.loads, (output / 'reviews.jsonl').read_text().splitlines())}
        self.assertEqual(reviews['甲']['decision'], 'hold')
        self.assertEqual(reviews['乙']['decision'], 'approve')
        self.assertIn('requires_review', reviews['甲']['reason'])

    def test_metadata_tampering_is_rejected(self):
        metadata = self.metadata(['Category:日本のAV女優'], corrupt=True)
        with self.assertRaises(ValueError):
            reviewer.metadata_blockers(metadata)

    def test_incomplete_metadata_continuation_is_rejected(self):
        metadata = self.metadata(['Category:日本のAV女優'], incomplete=True)
        with self.assertRaises(ValueError):
            reviewer.metadata_blockers(metadata)

    def test_nonoccupational_adult_word_does_not_claim_person_appearance(self):
        metadata = self.metadata(['Category:アダルトゲーム', 'Category:アダルトゲームの登場人物'])
        blocked, _ = reviewer.metadata_blockers(metadata)
        self.assertEqual(blocked, set())

    def test_independent_review_accepts_held_nongeneric_and_typeless_matches(self):
        root, workspace, source, classified = self.integration(
            [entry(1, ['甲'], 'あ', 'company'), entry(2, ['乙'], 'い')])
        output = root / 'nongeneric-review'
        result = self.run_review(root, workspace, source, classified, output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        reviews = [json.loads(line) for line in (output / 'reviews.jsonl').read_text().splitlines()]
        self.assertEqual(len(reviews), 2)
        self.assertEqual({row['decision'] for row in reviews}, {'hold'})

    def test_independent_review_rejects_source_tampering(self):
        root, workspace, source, classified = self.integration()
        changed = self.source([entry(1, ['甲'], 'あ', 'company')], name='tampered.xml.gz')
        result = self.run_review(root, workspace, changed, classified, root / 'tampered-review')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_proposal_is_not_silently_reviewed(self):
        root, workspace, source, classified = self.integration()
        proposal = classified / 'proposals.jsonl'
        rows = proposal.read_text().splitlines()
        self.assertGreaterEqual(len(rows), 2)
        proposal.write_text('\n'.join(rows[:-1]) + '\n')
        result = self.run_review(root, workspace, source, classified, root / 'missing-review')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
