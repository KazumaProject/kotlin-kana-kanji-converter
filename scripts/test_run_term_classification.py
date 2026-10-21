import datetime
import json
from pathlib import Path
import tempfile
import unittest

import run_term_classification as c


class TermClassificationTest(unittest.TestCase):
    def proof(self, **changes):
        now = datetime.datetime.now(datetime.timezone.utc)
        return {
            'project_id': c.PROJECT,
            'model': c.MODEL,
            'free_tier': True,
            'billing_enabled': False,
            'api_project_verified': True,
            'api_quota_verified': True,
            'rpm': 15,
            'tpm': 250000,
            'rpd': 500,
            'verified_at': now.isoformat(),
            **changes,
        }

    def test_only_fresh_free_tier_proof_is_accepted(self):
        c.verify_free_project(self.proof())
        with self.assertRaisesRegex(ValueError, 'Free-tier proof'):
            c.verify_free_project(self.proof(billing_enabled=True))
        old = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=25)
        with self.assertRaisesRegex(ValueError, 'older than 24 hours'):
            c.verify_free_project(self.proof(verified_at=old.isoformat()))

    def test_codes_require_exact_coverage_and_known_categories(self):
        self.assertEqual(c.parse_codes('{"codes":["0","1","A","B","C","D","E"]}', 7),
                         ([0, 1, 10, 11, 12, 13, 14], []))
        self.assertEqual(c.parse_codes('{"codes":[' + ','.join('"' + code + '"' for code in '0123456789') + ']}', 10),
                         (list(range(10)), []))
        for response in ('{"codes":["0"]}', '{"codes":["0","1","Z"]}',
                         '{"codes":["0","1"," "]}', '{"codes":["0","00"]}',
                         '{"codes":"0123456789"}',
                         '{"codes":["0","1"],"extra":true}'):
            with self.subTest(response=response), self.assertRaises(ValueError):
                c.parse_codes(response, 2 if '"codes":["0","1"]' in response else 3)

    def test_generate_content_request_uses_structured_json(self):
        root = Path(__file__).resolve().parents[1]
        _, categories = c.load_taxonomy(root)
        body = c.request_body([{'reading': 'かさ', 'surface': '傘'}], categories)
        self.assertEqual(body['generationConfig']['thinkingConfig']['thinkingLevel'], 'minimal')
        self.assertEqual(body['generationConfig']['responseFormat']['text']['mimeType'], 'APPLICATION_JSON')
        schema = body['generationConfig']['responseFormat']['text']['schema']
        self.assertEqual(schema['required'], ['codes'])
        self.assertEqual(schema['properties']['codes']['minItems'], 1)
        self.assertEqual(schema['properties']['codes']['maxItems'], 1)
        self.assertEqual(schema['properties']['codes']['items']['enum'], list(c.SYMBOLS))
        self.assertGreaterEqual(body['generationConfig']['maxOutputTokens'], 512)

    def test_generate_content_response_text_is_read(self):
        response = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [
            {'text': '{"codes":["A"]}'}]}}]}
        self.assertEqual(c.response_text(response), '{"codes":["A"]}')

    def test_daily_request_budget_never_reserves_above_free_tier_limit(self):
        budget = c.FreeTierRequestBudget(2)
        self.assertTrue(budget.reserve())
        self.assertTrue(budget.reserve())
        self.assertFalse(budget.reserve())
        self.assertEqual(budget.count, 2)

    def test_run_request_cap_includes_retries(self):
        budget = c.FreeTierRequestBudget(500, 1)
        self.assertTrue(budget.reserve())
        self.assertFalse(budget.reserve())
        self.assertEqual(budget.count, budget.run_limit)

    def test_request_budget_is_project_daily_and_persistent(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / 'api-request-ledger.jsonl'
            budget = c.FreeTierRequestBudget(5, 2, used_today=3, ledger_path=ledger)
            self.assertTrue(budget.reserve())
            self.assertTrue(budget.reserve())
            self.assertTrue(budget.exhausted)
            next_run = c.FreeTierRequestBudget(5, used_today=5, ledger_path=ledger)
            self.assertFalse(next_run.reserve())
            self.assertEqual(len(list(c.read_jsonl(ledger))), 2)

    def test_request_usage_resets_at_midnight_pacific(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / 'api-request-ledger.jsonl'
            c.write_jsonl(ledger, [
                {'timestamp': '2026-10-21T06:30:00+00:00'},
                {'timestamp': '2026-10-21T07:15:00+00:00'},
            ])
            now = datetime.datetime.fromisoformat('2026-10-21T06:45:00+00:00')
            used, resolved_ledger = c.free_tier_requests_used_today(temporary, now=now)
            self.assertEqual(used, 1)
            self.assertEqual(resolved_ledger, ledger)

    def test_taxonomy_has_five_general_and_ten_specialist_leaves(self):
        root = Path(__file__).resolve().parents[1]
        _, categories = c.load_taxonomy(root)
        self.assertEqual(len(categories), 15)
        self.assertEqual(sum(category['id'].startswith('term/general/') for category in categories), 5)
        self.assertEqual(sum(category['id'].startswith('term/specialist/') for category in categories), 10)

    def test_saved_batch_result_must_match_every_input_key_once_in_order(self):
        categories = [{'id': f'term/general/c{index}'} for index in range(15)]
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            items = [
                {'candidate_key': 'a' * 64, 'reading': 'あ', 'surface': '亜'},
                {'candidate_key': 'b' * 64, 'reading': 'い', 'surface': '伊'},
            ]
            (workspace / 'batches').mkdir()
            (workspace / 'results').mkdir()
            c.write_jsonl(workspace / 'batches/batch-000001.jsonl', items)
            manifest = {'batch_count': 1}
            good_rows = [
                {'batch_id': 'batch-000001', 'candidate_key': item['candidate_key'],
                 'category_code': index, 'category_id': categories[index]['id'],
                 'model': c.MODEL, 'api_endpoint': c.API_ENDPOINT, 'free_only': True}
                for index, item in enumerate(items)
            ]
            c.write_jsonl(workspace / 'results/batch-000001.jsonl', good_rows)
            self.assertEqual(len(c.completed_batches(workspace, manifest, categories)), 1)
            c.write_jsonl(workspace / 'results/batch-000001.jsonl', [good_rows[0], good_rows[0]])
            with self.assertRaisesRegex(ValueError, 'do not match batch'):
                c.completed_batches(workspace, manifest, categories)


if __name__ == '__main__':
    unittest.main()
