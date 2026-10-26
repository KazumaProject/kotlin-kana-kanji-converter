import datetime
import gzip
import tempfile
from pathlib import Path
import unittest

import person_gemini_classification as gemini
import review_japanese_name_origins as review


class JapaneseOriginReviewTest(unittest.TestCase):
    def test_collect_candidates_deduplicates_japanese_pairs_and_keeps_name_type(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / review.SOURCE_PATH
            source.parent.mkdir(parents=True)
            with gzip.open(source, 'wt', encoding='utf-8', newline='') as stream:
                stream.write('surname_origin_japanese\tたなか\t1\t1\t8000\t田中\t\n')
                stream.write('surname_origin_japanese\tたなか\t2\t2\t8100\t田中\t\n')
                stream.write('given_name_origin_japanese\tはなこ\t1\t1\t8000\t花子\t\n')
                stream.write('surname_origin_foreign\tり\t1\t1\t8000\t李\t\n')
            items, records = review.collect_candidates(root)
            self.assertEqual((len(items), records), (2, 3))
            self.assertEqual({item['source_category_id'] for item in items}, {
                'surname_origin_unconfirmed', 'given_name_origin_unconfirmed'})

    def test_prompt_names_name_type_and_forbids_external_reference_sources(self):
        items = [
            {'candidate_key': 'a' * 64, 'source_category_id': 'surname_origin_unconfirmed',
             'reading': 'り', 'surface': '李'},
            {'candidate_key': 'b' * 64, 'source_category_id': 'given_name_origin_unconfirmed',
             'reading': 'れい', 'surface': '玲'},
        ]
        prompt = review.origin_prompt(items)
        self.assertIn('姓、名、姓名', prompt)
        self.assertIn('中国・韓国', prompt)
        self.assertNotIn('JMdict', prompt)
        self.assertNotIn('JMnedict', prompt)

    def test_two_pass_agreement_moves_only_matching_foreign_results(self):
        first = [
            {'candidate_key': 'a' * 64, 'source_category_id': 'surname_origin_unconfirmed',
             'category_code': 34},
            {'candidate_key': 'b' * 64, 'source_category_id': 'given_name_origin_unconfirmed',
             'category_code': 36},
            {'candidate_key': 'c' * 64, 'source_category_id': 'personal_name_origin_unconfirmed',
             'category_code': 0},
        ]
        second = [
            {'candidate_key': 'a' * 64, 'source_category_id': 'surname_origin_unconfirmed',
             'category_code': 34},
            {'candidate_key': 'b' * 64, 'source_category_id': 'given_name_origin_unconfirmed',
             'category_code': 35},
        ]
        self.assertEqual(review.confirmed_foreign_candidates(first, second), {'a' * 64})

    def test_two_pass_coverage_and_name_type_must_match(self):
        first = [{'candidate_key': 'a' * 64, 'source_category_id': 'surname_origin_unconfirmed',
                  'category_code': 34}]
        with self.assertRaisesRegex(ValueError, 'exactly'):
            review.confirmed_foreign_candidates(first, [])
        wrong_type = [{'candidate_key': 'a' * 64, 'source_category_id': 'given_name_origin_unconfirmed',
                       'category_code': 36}]
        with self.assertRaisesRegex(ValueError, 'name type'):
            review.confirmed_foreign_candidates(first, wrong_type)

    def test_mapping_target_changes_keep_original_source_type_and_reviewed_name_type(self):
        key = 'a' * 64
        mapping = {key: ('surname_origin_unconfirmed', 'personal_name_origin_japanese')}
        first = {key: {'source_category_id': 'personal_name_origin_unconfirmed'}}
        self.assertEqual(review.reclassify_mapping_targets(mapping, first, {key}), 1)
        self.assertEqual(mapping[key],
                         ('surname_origin_unconfirmed', 'personal_name_origin_foreign'))

    def test_non_origin_model_codes_stay_unconfirmed(self):
        items = [{'candidate_key': 'a' * 64, 'source_category_id': 'surname_origin_unconfirmed'}]
        rows = review.rows_for_result(items, [4], 'batch-000001')
        self.assertEqual(rows[0]['category_code'], 0)

    def test_free_tier_proof_must_match_requested_model_and_be_recent(self):
        now = datetime.datetime(2026, 10, 26, tzinfo=datetime.timezone.utc)
        proof = {
            'project_id': review.PROJECT,
            'model': review.MODEL,
            'free_tier': True,
            'billing_enabled': False,
            'api_project_verified': True,
            'api_quota_verified': True,
            'verified_at': now.isoformat(),
            'rpm': 15,
            'tpm': 250000,
            'rpd': 500,
        }
        self.assertIsNone(gemini.verify_free_project(proof, now=now, model=review.MODEL))
        with self.assertRaisesRegex(ValueError, 'model'):
            gemini.verify_free_project(proof, now=now, model=gemini.MODEL)

    def test_request_body_uses_explicit_model_without_changing_existing_default(self):
        self.assertEqual(gemini.request_body([], 'prompt', review.MODEL)['model'], review.MODEL)
        self.assertEqual(gemini.request_body([], 'prompt')['model'], gemini.MODEL)


if __name__ == '__main__':
    unittest.main()
