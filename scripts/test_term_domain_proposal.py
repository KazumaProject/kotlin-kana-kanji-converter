import csv
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest

import term_domain_proposal as proposal


def compressed_tsv(rows):
    text = io.StringIO(newline='')
    writer = csv.DictWriter(text, fieldnames=proposal.COLUMNS, delimiter='\t', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return gzip.compress(text.getvalue().encode('utf-8'), mtime=0)


class TermDomainProposalTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = self.root / proposal.DIRECTORY
        self.directory.mkdir(parents=True)
        self.taxonomy = dict(
            domains=[dict(id='term_general', name='一般語・日常表現', definition='一般語'),
                     dict(id='term_medicine', name='医学・医療', definition='医療')],
            tags=[dict(id='term_tag_abbreviation', name='略語', definition='略語')],
            assignmentMethods=['local_model', 'reference_field'])
        # Two POS/cost variants for the same reading/surface must survive exports.
        self.source = [('term', 'しーてぃーけんさ', '1', '2', '100', 'CT検査'),
                       ('term', 'しーてぃーけんさ', '3', '4', '-20', 'CT検査'),
                       ('term', 'ことば', '1', '1', '500', '語<&|>'),
                       ('person', 'たろう', '1', '1', '100', '太郎')]
        self.assignments = [
            dict(reading='しーてぃーけんさ', surface='CT検査', category='term_medicine',
                 confidence='low', tags='term_tag_abbreviation', method='reference_field',
                 evidence='Ambiguous reference domain', reference_ids='123,456'),
            dict(reading='ことば', surface='語<&|>', category='term_general', confidence='medium',
                 tags='', method='local_model', evidence='Local provisional inference', reference_ids='')]
        self.write_source()
        self.freeze()

    def write_source(self):
        raw = ''.join('\t'.join(row) + '\n' for row in self.source).encode('utf-8')
        (self.root / proposal.SOURCE).write_bytes(gzip.compress(raw, mtime=0))

    def freeze(self):
        (self.directory / 'taxonomy.json').write_text(json.dumps(self.taxonomy, ensure_ascii=False), encoding='utf-8')
        (self.directory / 'assignments.tsv.gz').write_bytes(compressed_tsv(self.assignments))
        rows = proposal.source_rows(self.root)
        counts, _ = proposal.summarize(rows, iter(self.assignments), self.taxonomy)
        self.manifest = dict(schemaVersion=1, status='provisional', semanticAccuracyVerified=False,
                             source=dict(revision='test-revision', termRecordsSha256=proposal.term_digest(rows)),
                             files={name: proposal.sha(self.directory / name)
                                    for name in ('taxonomy.json', 'assignments.tsv.gz')}, counts=counts)
        self.write_manifest()

    def write_manifest(self):
        (self.directory / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def write_assignments_with_valid_hash(self):
        path = self.directory / 'assignments.tsv.gz'
        path.write_bytes(compressed_tsv(self.assignments))
        self.manifest['files'][path.name] = proposal.sha(path)
        self.write_manifest()

    def test_exact_coverage_counts_overlap_and_pos_cost_preservation(self):
        manifest, _taxonomy, rows, indexed = proposal.verify(self.root)
        self.assertEqual(manifest['counts']['sourcePairs'], 2)
        self.assertEqual(manifest['counts']['sourceRecords'], 3)
        self.assertEqual(manifest['counts']['unassigned'], 0)
        self.assertEqual(manifest['counts']['tagPairs']['term_tag_abbreviation'], 1)
        self.assertEqual(manifest['counts']['tagRecords']['term_tag_abbreviation'], 2)
        self.assertEqual(set(indexed), {('しーてぃーけんさ', 'CT検査'), ('ことば', '語<&|>')})
        output = self.root / 'export'
        result = proposal.export(self.root, output)
        self.assertEqual(result['dictionaries'], 3)
        for ident in ('term_medicine', 'term_tag_abbreviation'):
            exported = (output / (ident + '.tsv')).read_text(encoding='utf-8').splitlines()
            self.assertEqual(sorted(line.split('\t')[1:] for line in exported),
                             sorted(list(row) for row in rows if row[4] == 'CT検査'))
        self.assertNotIn('太郎', ''.join(p.read_text(encoding='utf-8') for p in output.glob('*.tsv')))

    def test_rejects_source_cost_change_but_allows_other_category_changes(self):
        self.source[-1] = ('person', 'じろう', '8', '9', '10', '次郎')
        self.write_source()
        proposal.verify(self.root)
        self.source[0] = ('term', 'しーてぃーけんさ', '1', '2', '999', 'CT検査')
        self.write_source()
        with self.assertRaisesRegex(ValueError, 'Source term records changed'):
            proposal.verify(self.root)

    def test_rejects_removed_added_duplicate_or_unknown_assignments(self):
        baseline = [dict(row) for row in self.assignments]
        mutations = [('Missing assignments', lambda rows: rows.pop()),
                     ('outside source', lambda rows: rows[0].update(surface='追加語')),
                     ('Duplicate assignment', lambda rows: rows.append(dict(rows[0]))),
                     ('Unknown primary category', lambda rows: rows[0].update(category='unassigned')),
                     ('Unknown confidence', lambda rows: rows[0].update(confidence='verified')),
                     ('Unknown or duplicate tags', lambda rows: rows[0].update(tags='unknown')),
                     ('Unknown or duplicate tags', lambda rows: rows[0].update(tags='term_tag_abbreviation,term_tag_abbreviation')),
                     ('Invalid assignment evidence', lambda rows: rows[0].update(method='invented')),
                     ('Invalid assignment evidence', lambda rows: rows[0].update(evidence=''))]
        for message, mutate in mutations:
            with self.subTest(message=message):
                self.assignments = [dict(row) for row in baseline]
                mutate(self.assignments)
                self.write_assignments_with_valid_hash()
                with self.assertRaisesRegex(ValueError, message):
                    proposal.verify(self.root)

    def test_rejects_hash_and_count_tampering_and_accuracy_claim(self):
        path = self.directory / 'assignments.tsv.gz'
        original = path.read_bytes()
        path.write_bytes(original + b'changed')
        with self.assertRaisesRegex(ValueError, 'Proposal hash differs'):
            proposal.verify(self.root)
        path.write_bytes(original)
        self.manifest['counts']['sourcePairs'] = 99
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'Proposal counts differ'):
            proposal.verify(self.root)
        self.manifest['semanticAccuracyVerified'] = True
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'must not claim verified semantic accuracy'):
            proposal.verify(self.root)

    def test_taxonomy_ids_cannot_escape_output_or_overlap(self):
        for bad_id in ('../escape', '/absolute', 'term_general'):
            with self.subTest(bad_id=bad_id):
                taxonomy = json.loads(json.dumps(self.taxonomy))
                taxonomy['tags'][0]['id'] = bad_id
                with self.assertRaisesRegex(ValueError, 'taxonomy IDs'):
                    proposal.summarize(proposal.source_rows(self.root), iter(self.assignments), taxonomy)

    def test_existing_output_is_preserved(self):
        output = self.root / 'export'
        output.mkdir()
        marker = output / 'keep.txt'
        marker.write_text('keep', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'must be a new directory'):
            proposal.export(self.root, output)
        self.assertEqual(marker.read_text(encoding='utf-8'), 'keep')

    def test_export_and_report_are_deterministic_and_report_uncertainty(self):
        a, b = self.root / 'a', self.root / 'b'
        proposal.export(self.root, a)
        proposal.export(self.root, b)
        self.assertEqual({p.name: p.read_bytes() for p in a.iterdir()},
                         {p.name: p.read_bytes() for p in b.iterdir()})
        text = proposal.render_report(self.manifest, self.taxonomy)
        self.assertIn('低確信度の推定 **1組**', text)
        self.assertIn('未分類は0組', text)
        self.assertIn('全件確認済みを意味しません', text)
        self.assertEqual(text, proposal.render_report(self.manifest, self.taxonomy))


if __name__ == '__main__':
    unittest.main()
