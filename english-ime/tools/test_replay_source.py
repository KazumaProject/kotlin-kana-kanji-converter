import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import lexicon_pipeline as pipeline
import replay_source as replay


class ReplayContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.payload = self.root / 'payload'
        self.payload.mkdir()
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        self.source = self.root / 'original.zip'
        data = 'input_word\toutput_word\tpos_tag\tscore\ncats\tcats\tNNS\t2000\ncat\tcat\tNN\t2000\ncats\tcats\tNNS\t2500\n'
        with ZipFile(self.source, 'w') as archive:
            archive.writestr(pipeline.SOURCE_TSV, data)
        self.rows = [dict(id=f'tsv:{i + 2}', reading=w, surface=w, cost=c)
                     for i, (w, c) in enumerate([('cats', 2000), ('cat', 2000), ('cats', 2500)])]
        self.rows += [dict(id='manual:1', reading='cap', surface='cap', cost=500),
                      dict(id='manual:2', reading='bad', surface='bad', cost=900)]
        (self.payload / 'inventory.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in self.rows))
        categories = ['abbreviation', 'noun', 'noun_count_plural', 'noun_count_singular',
                      'noun_proper', 'verb', 'verb_base']
        self.table('grammar/categories.tsv', pipeline.HEADERS['categories'],
                   [[c, 'Fixture category', c] for c in categories])
        forms = [('cat-noun', 'cat', 'cat'), ('cat-noun', 'cat', 'cats'), ('cat-verb', 'cat', 'cat'),
                 ('cap-plain', 'cap', 'cap'), ('cap-acronym', 'CAP', 'CAP')]
        self.table('grammar/forms.tsv', pipeline.HEADERS['forms'],
                   [list(r) + ['https://example.org/fixture'] for r in forms])
        memberships = [('cat-noun', 'cat', ['noun', 'noun_count_singular']),
                       ('cat-noun', 'cats', ['noun', 'noun_count_plural']),
                       ('cat-verb', 'cat', ['verb', 'verb_base']),
                       ('cap-plain', 'cap', ['noun', 'noun_proper']),
                       ('cap-acronym', 'CAP', ['abbreviation'])]
        self.table('grammar/memberships.tsv', pipeline.HEADERS['memberships'],
                   [[c, k, s] for k, s, cats in memberships for c in cats])
        self.table('grammar/relations.tsv', pipeline.HEADERS['relations'], [])
        self.table('surface-corrections.tsv', pipeline.HEADERS['corrections'],
                   [['manual:1', 'cap', s, 'case_candidates', 'https://example.org/fixture']
                    for s in ['cap', 'CAP']])
        decisions = []
        for r in self.rows:
            excluded = r['id'] == 'manual:2'
            keys = '-' if excluded else ('cap-acronym,cap-plain' if r['id'] == 'manual:1' else
                                        'cat-noun,cat-verb' if r['surface'] == 'cat' else 'cat-noun')
            decisions.append([r[k] for k in ['id', 'reading', 'surface', 'cost']] +
                             ['exclude' if excluded else 'include', keys,
                              'malformed' if excluded else 'verified', 'https://example.org/fixture'])
        self.table('decisions.tsv', pipeline.HEADERS['decisions'], decisions)
        self.table('notices/LICENSE.txt', ['Fixture'], [['Public-domain test data']])
        self.files = replay.CORE | {'notices/LICENSE.txt'}
        self.manifest = dict(kind=replay.KIND, schemaVersion=1,
            files={n: replay.sha(self.payload / n) for n in self.files},
            fileBytes={n: (self.payload / n).stat().st_size for n in self.files},
            archive=dict(file=replay.ARCHIVE),
            review=dict(complete=True, inputRows=5, includedRows=4, excludedRows=1, pendingRows=0),
            sourceInputs=dict(sourceZipSha256=replay.sha(self.source),
                sourcePayloadSha256=hashlib.sha256(data.encode()).hexdigest(),
                inventorySha256=replay.sha(self.payload / 'inventory.jsonl'),
                orderedTuplesSha256=replay.tuples_digest(self.rows), inputRows=5, tsvRows=3, manualRows=2),
            model=dict(forms=5, categories=7, memberships=9, relations=0, corrections=2, caseCandidateRows=1),
            expectedOutputs={'dictionary.bin': '0' * 64})
        replay.write_archive(self.payload, self.files, self.bundle / replay.ARCHIVE)
        self.update_archive_contract()

    def table(self, name, header, rows):
        path = self.payload / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', newline='') as stream:
            writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
            writer.writerow(header)
            writer.writerows(rows)

    def update_archive_contract(self):
        archive = self.bundle / replay.ARCHIVE
        self.manifest['archive'].update(bytes=archive.stat().st_size, sha256=replay.sha(archive))
        (self.bundle / 'manifest.json').write_text(json.dumps(self.manifest))

    def unpack(self):
        return replay.unpack(self.bundle / 'manifest.json', self.root / 'unpacked', self.source)

    def malicious_archive(self, name, member_type=tarfile.REGTYPE):
        # Trust the new archive digest deliberately, exercising member checks too.
        with tarfile.open(self.bundle / replay.ARCHIVE, 'w:gz') as archive:
            item = tarfile.TarInfo(name)
            item.type = member_type
            item.linkname = '../../escape'
            archive.addfile(item, io.BytesIO())
        self.update_archive_contract()

    def test_roundtrip_preserves_homographs_case_alternatives_and_duplicate_costs(self):
        _, result = self.unpack()
        self.assertEqual((result['includedRows'], result['excludedRows'], result['caseCandidateRows']), (4, 1, 1))
        restored = pipeline.inventory(self.root / 'unpacked/inventory.jsonl')
        self.assertEqual(restored, self.rows)
        model = pipeline.Lexicon(self.root / 'unpacked/grammar')
        self.assertEqual({k for k, s in model.forms if s == 'cat'}, {'cat-noun', 'cat-verb'})
        self.assertEqual(model.forms['cat-noun', 'cats']['lemma'], 'cat')
        self.assertEqual((self.root / 'unpacked/manifest.json').read_bytes(),
                         (self.bundle / 'manifest.json').read_bytes())

    def test_pending_guard(self):
        self.manifest['review'].update(complete=False, pendingRows=1, includedRows=3)
        self.update_archive_contract()
        with self.assertRaises(ValueError):
            self.unpack()
        self.assertFalse((self.root / 'unpacked').exists())

    def test_boolean_count_is_not_zero(self):
        self.manifest['review']['pendingRows'] = False
        with self.assertRaises(ValueError):
            replay.validate_manifest(self.manifest)

    def test_archive_checksum_change(self):
        with (self.bundle / replay.ARCHIVE).open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaises(ValueError):
            self.unpack()

    def test_paths_links_duplicates_and_unexpected_members(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('/escape', tarfile.REGTYPE),
                           ('inventory.jsonl', tarfile.SYMTYPE), ('inventory.jsonl', tarfile.LNKTYPE),
                           ('unrequested.txt', tarfile.REGTYPE)]:
            with self.subTest(name=name, kind=kind):
                self.malicious_archive(name, kind)
                with self.assertRaises(ValueError):
                    self.unpack()
                self.assertFalse((self.root / 'unpacked').exists())
        self.assertFalse((self.root / 'escape').exists())

    def test_missing_source_notice(self):
        (self.bundle / replay.ARCHIVE).unlink()
        replay.write_archive(self.payload, self.files - {'notices/LICENSE.txt'}, self.bundle / replay.ARCHIVE)
        self.update_archive_contract()
        with self.assertRaises(ValueError):
            self.unpack()

    def test_duplicate_archive_member(self):
        path = self.payload / 'inventory.jsonl'
        with tarfile.open(self.bundle / replay.ARCHIVE, 'w:gz') as archive:
            for _ in range(2):
                header = tarfile.TarInfo('inventory.jsonl')
                header.size = path.stat().st_size
                with path.open('rb') as stream:
                    archive.addfile(header, stream)
        self.update_archive_contract()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.unpack()

    def test_expansion_limit_includes_pax_metadata_and_trailing_data(self):
        for kind in ['pax', 'trailing']:
            with self.subTest(kind=kind):
                with tarfile.open(self.bundle / replay.ARCHIVE, 'w:gz',
                                  pax_headers={'comment': 'x' * (2 * 1024 * 1024)} if kind == 'pax' else {}) as archive:
                    for name in sorted(self.files):
                        archive.add(self.payload / name, arcname=name, recursive=False)
                if kind == 'trailing':
                    with replay.gzip.open(self.bundle / replay.ARCHIVE, 'ab') as stream:
                        stream.write(b'x' * (2 * 1024 * 1024))
                self.update_archive_contract()
                with patch.object(replay, 'MAX_PAYLOAD', 4096):
                    with self.assertRaisesRegex(ValueError, 'Decompressed archive'):
                        self.unpack()
                self.assertFalse((self.root / 'unpacked').exists())

    def test_member_digest_and_length(self):
        for mutation in ['digest', 'length']:
            with self.subTest(mutation=mutation):
                current = copy.deepcopy(self.manifest)
                if mutation == 'digest':
                    self.manifest['files']['decisions.tsv'] = '0' * 64
                else:
                    self.manifest['fileBytes']['decisions.tsv'] += 1
                self.update_archive_contract()
                with self.assertRaises(ValueError):
                    self.unpack()
                self.manifest = current

    def test_cost_and_order_tampering_even_with_recomputed_file_hashes(self):
        for change in ['cost', 'order']:
            with self.subTest(change=change):
                current = copy.deepcopy(self.rows)
                if change == 'cost':
                    current[0]['cost'] += 1
                else:
                    current[0], current[1] = current[1], current[0]
                (self.payload / 'inventory.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in current))
                self.manifest['sourceInputs']['orderedTuplesSha256'] = replay.tuples_digest(current)
                with self.assertRaises(ValueError):
                    replay.validate_data(self.payload, self.manifest, self.source)

    def test_changed_source_zip(self):
        self.source.write_bytes(b'not the reviewed source')
        with self.assertRaises(ValueError):
            self.unpack()

    def test_existing_destination_is_preserved(self):
        destination = self.root / 'unpacked'
        destination.mkdir()
        (destination / 'keep').write_text('keep')
        with self.assertRaises(ValueError):
            self.unpack()
        self.assertEqual((destination / 'keep').read_text(), 'keep')

    def test_private_pack_refuses_unfinished_materialization_before_research_loading(self):
        directory = self.root / 'unfinished'
        directory.mkdir()
        (directory / 'manifest.json').write_text(json.dumps({'summary': {'pendingRows': 1, 'complete': False}}))
        with self.assertRaises(ValueError):
            replay.pack(directory, self.root / 'missing-audit', self.root / 'missing-gold',
                        self.root / 'output', self.source)
        self.assertFalse((self.root / 'output').exists())


if __name__ == '__main__':
    unittest.main()
