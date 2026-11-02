import collections
import csv
import gzip
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_HEAD = '4cb2eab83bc8f65c4da78895fafb7b0f9c13635b'
LEDGER = ROOT / 'src/main/classification/person-name-origin-single-placement-reviews/2026-11-02-residual-216.jsonl'
REPORT = ROOT / 'docs/person-name-origin-single-placement-review-216.md'
REPORT_PAGES = ROOT / 'docs/person-name-origin-single-placement-review-216'


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def rows_by_pair(path):
    result = collections.defaultdict(list)
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as source:
        for row in csv.reader(source, delimiter='\t'):
            if len(row) >= 6:
                result[(row[1], row[5])].append(row)
    return result


def mappings_by_key(path):
    result = collections.defaultdict(list)
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as source:
        for row in csv.reader(source, delimiter='\t'):
            if len(row) == 3:
                result[row[1]].append(row)
    return result


class SinglePlacementReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = read_jsonl(LEDGER)
        cls.dictionary = rows_by_pair(ROOT / 'src/main/classification/person-dictionary-candidates.tsv.gz')
        cls.mappings = mappings_by_key(ROOT / 'src/main/classification/person-name-origin-classifications.tsv.gz')

    def test_all_216_keys_have_one_placement_and_review_basis(self):
        self.assertEqual(len(self.records), 216)
        keys = [record['candidate_key'] for record in self.records]
        self.assertEqual(len(set(keys)), 216)
        for record in self.records:
            with self.subTest(key=record['candidate_key']):
                self.assertEqual(record['baseline_head'], BASELINE_HEAD)
                self.assertEqual(
                    record['candidate_key'],
                    hashlib.sha256((record['reading'] + '\0' + record['surface']).encode('utf-8')).hexdigest(),
                )
                placement = record['operational_placement']['single_placement']
                self.assertIn(placement, {'japanese_person', 'foreign_person', 'nonperson'})
                self.assertTrue(record['operational_placement']['rationale'])
                self.assertTrue(record['evidence']['supporting_review_records'])
                self.assertFalse(record['operational_placement']['automatic_apply'])

    def test_human_report_links_to_all_216_item_details_in_bounded_pages(self):
        index = REPORT.read_text(encoding='utf-8')
        pages = sorted(REPORT_PAGES.glob('[0-9][0-9][0-9]-[0-9][0-9][0-9].md'))
        self.assertEqual(len(pages), 12)
        self.assertEqual(index.count('person-name-origin-single-placement-review-216/'), 12)
        detail_count = 0
        for page in pages:
            contents = page.read_text(encoding='utf-8')
            detail_count += contents.count('<summary>')
            self.assertIn('../person-name-origin-single-placement-review-216.md', contents)
            self.assertLess(len(contents.encode('utf-8')), 100_000)
        self.assertEqual(detail_count, 216)

    def test_origin_certainty_is_separate_from_placement_confidence(self):
        supported = [r for r in self.records if r['origin_assessment']['status'] == 'source_supported']
        self.assertEqual(len(supported), 3)
        for record in self.records:
            fact_asserted = record['operational_placement']['origin_fact_asserted']
            self.assertEqual(fact_asserted, record['origin_assessment']['status'] == 'source_supported')
            self.assertEqual(fact_asserted, record['operational_placement']['confidence'] == 'source_supported')
            if record['operational_placement']['confidence'] == 'low':
                self.assertFalse(fact_asserted)

    def test_post_patch_rows_match_repository_and_unpatched_rows_are_unchanged(self):
        patched = [r for r in self.records if r['implementation']['origin_or_type_classification_changed']]
        self.assertEqual(len(patched), 10)
        self.assertEqual(sum(r['implementation']['status'] == 'applied_verified_change_in_this_stack' for r in patched), 10)
        for record in self.records:
            key = record['candidate_key']
            expected_rows = record['post_patch_state']['person_dictionary_rows']
            actual_rows = self.dictionary[(record['reading'], record['surface'])]
            self.assertEqual(sorted(actual_rows), sorted(expected_rows), record['surface'])
            expected_mapping = record['post_patch_state']['origin_classification_mapping_rows'] or []
            self.assertEqual(sorted(self.mappings.get(key, [])), sorted(expected_mapping), record['surface'])
            if not record['implementation']['origin_or_type_classification_changed']:
                self.assertEqual(record['baseline']['person_dictionary_rows'], expected_rows, record['surface'])
                self.assertEqual(
                    record['baseline']['origin_classification_mapping_rows'],
                    record['post_patch_state']['origin_classification_mapping_rows'],
                    record['surface'],
                )

    def test_reading_review_is_separate_and_no_reading_was_changed(self):
        self.assertEqual(sum(r['separate_reading_review'] is not None for r in self.records), 28)
        self.assertTrue(all(r['separate_reading_review'] is None or not r['separate_reading_review']['changed_in_this_stack'] for r in self.records))


if __name__ == '__main__':
    unittest.main()
