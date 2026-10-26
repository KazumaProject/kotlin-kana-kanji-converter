import gzip
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import classified_distribution as distribution
import run_business_specificity_review as review
import run_term_classification as common


class BusinessSpecificityReviewTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'root'
        self.workspace = Path(self.temporary.name) / 'workspace'
        classification = self.root / 'src/main/classification'
        classification.mkdir(parents=True)
        (classification / distribution.BUSINESS_TAXONOMY_PATH.rsplit('/', 1)[-1]).write_bytes(
            Path('src/main/classification/business-taxonomy.json').read_bytes())
        distribution.write_gzip(classification / distribution.BUSINESS_CLASSIFICATIONS_PATH.rsplit('/', 1)[-1], [
            ('あんけん', '案件', 'business/sales_crm'),
            ('りんぎ', '稟議', 'business/common'),
            ('そと', '外', 'business/outside'),
        ])
        distribution.write_gzip(classification / distribution.TERM_CLASSIFICATIONS_PATH.rsplit('/', 1)[-1], [
            ('あんけん', '案件', 'term/specialist/economics_management'),
            ('りんぎ', '稟議', 'term/specialist/economics_management'),
            ('そと', '外', 'term/general/other_general'),
        ])
        (self.root / 'src/main/classification').mkdir(parents=True, exist_ok=True)
        (self.root / 'src/main/classification/business-classifications-manifest.json').write_text('{}')

    def test_prepare_snapshots_only_business_predictions_with_category_context(self):
        review.prepare(self.root, self.workspace, batch_size=1)

        manifest = json.loads((self.workspace / 'manifest.json').read_text(encoding='utf-8'))
        items = list(common.read_jsonl(self.workspace / 'items.jsonl'))

        self.assertEqual(len(items), 2)
        self.assertEqual(manifest['unique_pairs'], 2)
        self.assertEqual(manifest['batch_count'], 2)
        self.assertEqual(items[1]['proposed_category'], 'business/common')
        self.assertTrue(items[0]['category_definition'])
        self.assertEqual(manifest['category_ids'], ['business/keep', 'business/outside'])

    def test_prompt_applies_a_conservative_business_specificity_gate(self):
        prompt = review.prompt([
            {'reading': 'りんぎ', 'surface': '稟議', 'proposed_category': 'business/common',
             'category_name': 'ビジネス共通語', 'category_definition': '承認や報告'},
            {'reading': 'あだちくちょう', 'surface': '足立区長', 'proposed_category': 'business/government_procedures',
             'category_name': '官公庁・行政手続き', 'category_definition': '企業が行う手続き'},
        ], review.review_categories())

        self.assertIn('候補カテゴリと語の意味が合わない場合', prompt)
        self.assertIn('実用性と適合性を重視', prompt)
        self.assertIn('足立区長', prompt)
        self.assertIn('ゆず風呂', prompt)
        self.assertIn('外部検索も使わず', prompt)

    def test_prepare_rejects_existing_it_specialist_overlap(self):
        classification = self.root / 'src/main/classification'
        distribution.write_gzip(classification / 'business-classifications.tsv.gz', [
            ('たようそにんしょう', '多要素認証', 'business/it_security'),
        ])
        distribution.write_gzip(classification / 'term-classifications.tsv.gz', [
            ('たようそにんしょう', '多要素認証', 'term/specialist/information_communications'),
        ])

        with self.assertRaisesRegex(ValueError, 'IT specialist term'):
            review.prepare(self.root, self.workspace, batch_size=1)

    def test_export_writes_sorted_decisions_and_free_tier_provenance(self):
        review.prepare(self.root, self.workspace, batch_size=2)
        manifest, items = review.load_workspace(self.root, self.workspace)
        name = common.batch_id(1)
        results = []
        for item, code in zip(items, (0, 1)):
            results.append({
                'batch_id': name, 'candidate_key': item['candidate_key'],
                'reading': item['reading'], 'surface': item['surface'],
                'category_code': code,
                'category_id': review.review_categories()[code]['id'],
                'model': common.MODEL, 'api_endpoint': common.API_ENDPOINT, 'free_only': True,
            })
        common.write_jsonl(self.workspace / 'results' / (name + '.jsonl'), results)
        common.save_json(self.workspace / 'free-tier-runs.json', [{
            'model': common.MODEL, 'api_endpoint': common.API_ENDPOINT,
            'prompt_version': review.PROMPT_VERSION, 'project_id': common.PROJECT,
            'free_tier': True, 'billing_enabled': False, 'proof_sha256': 'a' * 64,
            'verified_at': '2026-10-26T12:03:41+00:00', 'rpm': 15, 'tpm': 250000, 'rpd': 500,
        }])

        review.export(SimpleNamespace(root=self.root, workspace=self.workspace))

        output = self.root / review.OUTPUT_PATH
        with gzip.open(output, 'rt', encoding='utf-8') as stream:
            rows = [line.rstrip('\n').split('\t') for line in stream]
        metadata = json.loads((self.root / review.OUTPUT_MANIFEST_PATH).read_text(encoding='utf-8'))
        self.assertEqual([row[3] for row in rows], ['business/keep', 'business/outside'])
        self.assertEqual(metadata['candidatePairs'], 2)
        self.assertEqual(metadata['keepPairs'], 1)
        self.assertEqual(metadata['outsidePairs'], 1)
        self.assertEqual(metadata['sourceSha256'], distribution.sha(self.root / review.SOURCE_MAP_PATH))


if __name__ == '__main__':
    unittest.main()
