import contextlib
import gzip
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile

import classified_distribution as d


class DistributionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'src/main/resources').mkdir(parents=True)
        (self.root / 'src/main/resources/id.def').write_text('0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n')
        self.taxonomy = self.root / 'taxonomy.json'
        ids = ['person', 'place', 'term'] + [f'category_{i}' for i in range(25)]
        self.taxonomy.write_text(json.dumps({'categories': [{'id': i} for i in ids]}))
        self.rows = [('あ', '1', '1', '100', '甲'), ('い', '1', '1', '200', '乙'),
                     ('う', '1', '1', '300', '丙'), ('え', '1', '1', '400', '丁'),
                     ('お', '1', '1', '500', '戊')]
        text = ''.join('\t'.join(r) + '\n' for r in self.rows)
        for path, member in d.SOURCES.values():
            p = self.root / path
            p.parent.mkdir(parents=True, exist_ok=True)
            if member:
                with zipfile.ZipFile(p, 'w') as z: z.writestr(member, text)
            else: p.write_text(text)
        self.accepted = self.root / 'accepted.gz'
        d.write_gzip(self.accepted, [('person', 'person', 'あ', '1', '1', '100', '甲', '[]')])
        self.dispositions = self.root / 'dispositions.gz'
        d.write_gzip(self.dispositions, [('excluded', '{}', 'person', 'え', '丁')])
        self.database = self.root / 'run.sqlite3'
        with sqlite3.connect(self.database) as con:
            for table in ['candidates', 'references_data']:
                con.execute(f'CREATE TABLE {table}(k TEXT PRIMARY KEY,data TEXT)')
            for reading, _, _, _, surface in self.rows:
                row = dict(reading=reading, surface=surface, candidate_key=d.key(reading, surface),
                           history=[{'model': 'gemini-test', 'proposal': {'categories': ['term']}}])
                con.execute('INSERT INTO candidates VALUES (?,?)', (row['candidate_key'], json.dumps(row)))
        self.manual = self.root / 'manual.jsonl'
        self.manual.write_text(''.join(json.dumps(dict(reading=r, surface=s, candidate_key=d.key(r,s), categories=c)) + '\n'
                                      for r,s,c in [('あ','甲',['place']),('い','乙',['place','person']),('お','戊',[])]))

    def freeze(self):
        with contextlib.redirect_stdout(io.StringIO()):
            d.freeze(self.root,self.accepted,self.dispositions,self.database,self.manual,self.taxonomy)

    def verify(self):
        with contextlib.redirect_stdout(io.StringIO()): d.verify(self.root)

    def test_precedence_multicategory_exclusion_and_original_values(self):
        self.freeze()
        self.verify()
        with gzip.open(self.root / 'src/main/classification/distribution-candidates.tsv.gz','rt') as f:
            rows = set(tuple(l.rstrip('\n').split('\t')) for l in f)
        self.assertEqual(rows, {('person',*self.rows[0]),('place',*self.rows[1]),('person',*self.rows[1]),('term',*self.rows[2])})
        manifest=json.loads((self.root/'src/main/classification/distribution-manifest.json').read_text())
        self.assertEqual(manifest['admittedPairsByOrigin'],{'verified':1,'manual':1,'gemini':1})
        self.assertEqual(manifest['dictionaryRows'],4)  # identical rows from five inputs collapse

    def test_changed_input_is_rejected(self):
        self.freeze()
        (self.root/'src/main/bin/names.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Input hash mismatch'):self.verify()

    def test_missing_candidate_is_rejected(self):
        self.manual.write_text(json.dumps(dict(reading='か',surface='外',candidate_key=d.key('か','外'),categories=['term'])))
        with self.assertRaisesRegex(ValueError,'missing from source'):self.freeze()

    def test_unknown_category_is_rejected(self):
        self.manual.write_text(json.dumps(dict(reading='い',surface='乙',candidate_key=d.key('い','乙'),categories=['wrong'])))
        with self.assertRaisesRegex(ValueError,'Unknown categories'):self.freeze()

    def test_changed_data_is_rejected_even_when_hash_is_updated(self):
        self.freeze()
        directory=self.root/'src/main/classification'
        candidates=directory/'distribution-candidates.tsv.gz'
        d.write_gzip(candidates,[('person','あ','1','1','999','甲')])
        manifest=json.loads((directory/'distribution-manifest.json').read_text())
        manifest['files'][candidates.name]=d.sha(candidates)
        d.write_json(directory/'distribution-manifest.json',manifest)
        with self.assertRaisesRegex(ValueError,'differs from sources'):self.verify()

    def test_freeze_is_deterministic(self):
        self.freeze()
        p=self.root/'src/main/classification/distribution-candidates.tsv.gz'
        first=p.read_bytes()
        self.freeze()
        self.assertEqual(first,p.read_bytes())

    def test_failed_results_are_counted_and_not_admitted(self):
        with sqlite3.connect(self.database) as con:
            k=d.key('う','丙')
            row=json.loads(con.execute('SELECT data FROM candidates WHERE k=?',(k,)).fetchone()[0])
            row.update(history=[],processing_state='attempted_no_result')
            con.execute('UPDATE candidates SET data=? WHERE k=?',(json.dumps(row),k))
        self.freeze()
        self.verify()
        manifest=json.loads((self.root/'src/main/classification/distribution-manifest.json').read_text())
        self.assertEqual(manifest['noResultPairs'],1)
        self.assertEqual(manifest['uniqueAdmittedPairs'],2)

    def test_independent_source_review_overrides_manual_and_gemini(self):
        with sqlite3.connect(self.database) as con:
            k=d.key('い','乙')
            row=json.loads(con.execute('SELECT data FROM candidates WHERE k=?',(k,)).fetchone()[0])
            row.update(source_validated_categories=['term'],independent_reading_confirmed=True)
            con.execute('UPDATE candidates SET data=? WHERE k=?',(json.dumps(row),k))
        self.freeze()
        self.verify()
        with gzip.open(self.root/'src/main/classification/distribution-candidates.tsv.gz','rt') as f:
            rows=set(tuple(l.rstrip('\n').split('\t')) for l in f)
        self.assertIn(('term',*self.rows[1]),rows)
        self.assertNotIn(('place',*self.rows[1]),rows)

    def person_file(self, entries=None):
        entry = dict(reading='かくとうか', surface='格闘家', sport='mma', left_id=1, right_id=1, cost=8400,
                     source_url='https://example.org/fighters/test', source_surface='格闘家',
                     source_reading='カクトウカ', checked_on='2026-10-14')
        path = self.root / 'src/main/classification/person-test.jsonl'
        path.write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in (entries or [entry])), encoding='utf-8')
        return path, entry

    def add_people(self, path):
        with contextlib.redirect_stdout(io.StringIO()): d.add_person_names(self.root, path)

    def snapshot(self):
        paths = [self.root / p for p, _ in d.SOURCES.values()]
        paths += list((self.root / 'src/main/classification').glob('distribution-*'))
        return {p: p.read_bytes() for p in paths}

    def test_person_additions_preserve_baseline_and_are_idempotent(self):
        self.freeze()
        path, entry = self.person_file()
        path.write_text((json.dumps(entry, ensure_ascii=False) + '\n') * 2, encoding='utf-8')
        original = self.snapshot()
        self.add_people(path)
        self.verify()
        current = self.snapshot()
        self.add_people(path)
        self.assertEqual(current, self.snapshot())
        self.assertTrue((self.root / 'src/main/bin/names.txt').read_bytes().startswith(original[self.root / 'src/main/bin/names.txt']))
        for name in ('distribution-candidates.tsv.gz', 'distribution-decisions.tsv.gz'):
            p = self.root / 'src/main/classification' / name
            before = set(gzip.decompress(original[p]).splitlines())
            after = set(gzip.decompress(current[p]).splitlines())
            self.assertTrue(before <= after)
            self.assertEqual(len(after - before), 1)
        manifest = json.loads((self.root / 'src/main/classification/distribution-manifest.json').read_text())
        self.assertEqual(manifest['provenance']['personAdditions'][0]['addedRecords'], 1)
        self.assertEqual(manifest['provenance']['personAdditions'][0]['reviewedPairs'], 1)
        self.assertEqual(manifest['categoryRows']['person'], 3)

    def test_already_admitted_person_is_not_changed(self):
        self.freeze()
        _, entry = self.person_file()
        entry.update(reading='あ', surface='甲', source_reading='ア', source_surface='甲')
        path, _ = self.person_file([entry])
        before = self.snapshot()
        self.add_people(path)
        self.assertEqual(before, self.snapshot())

    def test_invalid_person_batch_does_not_mutate_snapshot(self):
        self.freeze()
        _, entry = self.person_file()
        cases = [('left_id', 2), ('right_id', -1), ('cost', 32768), ('cost', True),
                 ('source_url', ''), ('source_url', 'http://example.org/'),
                 ('source_reading', 'Kakutouka'), ('source_reading', 'カク'),
                 ('source_surface', '別人'), ('sport', 'unknown'), ('checked_on', 'invalid')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                invalid = {**entry, field: value}
                path, _ = self.person_file([entry, {**invalid, 'surface': invalid['surface']}])
                before = self.snapshot()
                with self.assertRaises(ValueError): self.add_people(path)
                self.assertEqual(before, self.snapshot())
        missing = dict(entry)
        del missing['source_reading']
        path, _ = self.person_file([missing])
        with self.assertRaisesRegex(ValueError, 'missing'): self.add_people(path)

    def test_person_conflicts_and_exclusions_do_not_mutate_snapshot(self):
        self.freeze()
        for reading, surface in [('う', '丙'), ('え', '丁'), ('お', '戊')]:
            _, entry = self.person_file()
            entry.update(reading=reading, surface=surface, source_reading=reading, source_surface=surface)
            path, _ = self.person_file([entry])
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, 'conflicts'): self.add_people(path)
            self.assertEqual(before, self.snapshot())

    def test_existing_undecided_source_values_are_preserved_when_reviewed(self):
        # No decision or AI history for this existing source row.
        self.rows.append(('か', '1', '1', '700', '己'))
        with (self.root / 'src/main/bin/names.txt').open('a') as f:
            f.write('\t'.join(self.rows[-1]) + '\n')
        self.freeze()
        _, entry = self.person_file()
        entry.update(reading='か', surface='己', source_reading='カ', source_surface='己')
        path, _ = self.person_file([entry])
        self.add_people(path)
        self.verify()
        with gzip.open(self.root / 'src/main/classification/distribution-candidates.tsv.gz', 'rt') as f:
            rows = {tuple(line.strip().split('\t')) for line in f}
        self.assertIn(('person', 'か', '1', '1', '700', '己'), rows)
        self.assertIn(('person', 'か', '1', '1', '8400', '己'), rows)

    def test_reviewed_person_cost_is_verified_even_after_source_hash_update(self):
        self.freeze()
        path, _ = self.person_file()
        self.add_people(path)
        source = self.root / 'src/main/bin/names.txt'
        source.write_text(source.read_text().replace('8400', '8401'))
        directory = self.root / 'src/main/classification'
        rows = gzip.decompress((directory / 'distribution-candidates.tsv.gz').read_bytes()).decode().replace('8400', '8401')
        d.write_gzip(directory / 'distribution-candidates.tsv.gz', (r.split('\t') for r in rows.splitlines()))
        manifest = json.loads((directory / 'distribution-manifest.json').read_text())
        manifest['inputs']['src/main/bin/names.txt'] = d.sha(source)
        manifest['files']['distribution-candidates.tsv.gz'] = d.sha(directory / 'distribution-candidates.tsv.gz')
        d.write_json(directory / 'distribution-manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'reviewed POS/cost'): self.verify()

    def test_person_evidence_hash_and_counts_are_verified(self):
        self.freeze()
        path, _ = self.person_file()
        self.add_people(path)
        manifest_path = self.root / 'src/main/classification/distribution-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['provenance']['personAdditions'][0]['addedRecords'] = 2
        d.write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, 'provenance'): self.verify()
        manifest['provenance']['personAdditions'][0]['addedRecords'] = 1
        d.write_json(manifest_path, manifest)
        path.write_text(path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'Input hash mismatch'): self.verify()

    def test_person_kana_normalization_preserves_long_vowels(self):
        self.assertEqual(d.person_reading('ジョージ・サン ピエール'), 'じょーじさんぴえーる')
        self.assertEqual(d.person_reading('キムラ“フィリップ”ミノル'), 'きむらふぃりっぷみのる')


if __name__ == '__main__':unittest.main()
