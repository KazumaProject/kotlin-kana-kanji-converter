import gzip
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import classified_distribution as distribution
import classification_reviews as reviews
import run_business_classification as business


class BusinessClassificationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'root'
        self.workspace = Path(self.temporary.name) / 'workspace'
        classification = self.root / 'src/main/classification'
        classification.mkdir(parents=True)
        (classification / 'business-taxonomy.json').write_bytes(
            Path('src/main/classification/business-taxonomy.json').read_bytes())
        distribution.write_gzip(classification / 'term-classifications.tsv.gz', [
            ('けっさい', '決裁', 'term/specialist/economics_management'),
            ('りんぎ', '稟議', 'term/specialist/economics_management'),
            ('たようそにんしょう', '多要素認証', 'term/specialist/information_communications'),
        ])
        (classification / distribution.BUSINESS_CURATED_CLASSIFICATIONS_PATH.rsplit('/', 1)[-1]).write_text(
            'けっさい\t決裁\tbusiness/common\n', encoding='utf-8')

    def write_business_fixture(self, provisional, specificity):
        classification = self.root / 'src/main/classification'
        taxonomy, leaves = distribution.business_taxonomy(self.root)
        source_pairs = set()
        source_categories = {}
        with gzip.open(classification / 'term-classifications.tsv.gz', 'rt', encoding='utf-8') as stream:
            for line in stream:
                reading, surface, category = line.rstrip('\n').split('\t')
                source_pairs.add((reading, surface))
                source_categories[(reading, surface)] = category
        self.assertEqual(set(provisional), source_pairs)
        business_ids = {leaf['id'] for leaf in leaves}
        candidate_pairs = {pair for pair, category in provisional.items() if category in business_ids}
        self.assertEqual(set(specificity), candidate_pairs)

        with tempfile.TemporaryDirectory() as temp:
            provisional_path = Path(temp) / 'provisional.tsv.gz'
            distribution.write_gzip(provisional_path, ((*pair, provisional[pair]) for pair in sorted(provisional)))
            provisional_hash = distribution.sha(provisional_path)

        specificity_path = classification / distribution.BUSINESS_SPECIFICITY_REVIEW_PATH.rsplit('/', 1)[-1]
        specificity_rows = [(*pair, provisional[pair], specificity[pair])
                            for pair in sorted(candidate_pairs)]
        distribution.write_gzip(specificity_path, specificity_rows)
        keep_pairs = sum(result == 'business/keep' for result in specificity.values())
        rejected_pairs = sum(result == 'business/outside' for result in specificity.values())
        proof = {'sha256': 'a' * 64, 'verifiedAt': '2026-10-26T12:03:41+00:00',
                 'rpm': 15, 'tpm': 250000, 'rpd': 500}
        specificity_manifest = {
            'schemaVersion': 1, 'model': business.common.MODEL,
            'apiEndpoint': business.common.API_ENDPOINT, 'projectId': business.common.PROJECT,
            'promptVersion': 'business-specificity-practical-high-precision-v2',
            'freeTierOnly': True, 'billingEnabled': False,
            'sourcePath': distribution.BUSINESS_CLASSIFICATIONS_PATH,
            'sourceSha256': provisional_hash, 'candidatePairs': len(candidate_pairs),
            'keepPairs': keep_pairs, 'outsidePairs': rejected_pairs,
            'resultSha256': distribution.sha(specificity_path), 'freeTierProofs': [proof],
        }
        specificity_manifest_path = classification / distribution.BUSINESS_SPECIFICITY_REVIEW_MANIFEST_PATH.rsplit('/', 1)[-1]
        specificity_manifest_path.write_text(json.dumps(specificity_manifest), encoding='utf-8')

        curated = {pair: category for pair, category in provisional.items()
                   if category != 'business/outside'}
        curated_path = classification / distribution.BUSINESS_CURATED_CLASSIFICATIONS_PATH.rsplit('/', 1)[-1]
        curated_path.write_text(''.join(
            f'{reading}\t{surface}\t{category}\n'
            for (reading, surface), category in sorted(curated.items())), encoding='utf-8')
        final = {pair: 'business/outside' for pair in provisional}
        final.update(curated)
        result_path = classification / distribution.BUSINESS_CLASSIFICATIONS_PATH.rsplit('/', 1)[-1]
        distribution.write_gzip(result_path, ((*pair, final[pair]) for pair in sorted(final)))
        source_pair_hash = hashlib.sha256(''.join(
            reading + '\t' + surface + '\n' for reading, surface in sorted(source_pairs)
        ).encode('utf-8')).hexdigest()
        counts = {leaf['id']: sum(category == leaf['id'] for category in final.values()) for leaf in leaves}
        it_pairs = sum(category == 'term/specialist/information_communications'
                       for category in source_categories.values())
        metadata = {
            'schemaVersion': 1, 'taxonomySha256': distribution.sha(classification / 'business-taxonomy.json'),
            'sourcePath': business.SOURCE_PATH,
            'sourceSha256': distribution.sha(classification / 'term-classifications.tsv.gz'),
            'resultSha256': distribution.sha(result_path), 'model': business.common.MODEL,
            'apiEndpoint': business.common.API_ENDPOINT, 'projectId': business.common.PROJECT,
            'freeTierOnly': True, 'billingEnabled': False, 'promptVersion': business.PROMPT_VERSION,
            'sourcePairSha256': source_pair_hash, 'uniquePairs': len(source_pairs),
            'outsideBusinessPairs': sum(category == 'business/outside' for category in final.values()),
            'categoryCounts': counts, 'itSecurityOverlapPolicy': business.IT_SECURITY_OVERLAP_POLICY,
            'curatedClassifications': {
                'path': distribution.BUSINESS_CURATED_CLASSIFICATIONS_PATH,
                'sha256': distribution.sha(curated_path), 'pairCount': len(curated),
            },
            'existingItSpecialistPairsForcedOutsideBusiness': it_pairs, 'freeTierProofs': [proof],
            'specificityReview': {
                'path': distribution.BUSINESS_SPECIFICITY_REVIEW_PATH,
                'manifestPath': distribution.BUSINESS_SPECIFICITY_REVIEW_MANIFEST_PATH,
                'sha256': distribution.sha(specificity_path),
                'manifestSha256': distribution.sha(specificity_manifest_path),
                'sourceMapSha256': provisional_hash, 'candidatePairs': len(candidate_pairs),
                'keepPairs': keep_pairs, 'outsidePairs': rejected_pairs,
                'model': business.common.MODEL,
                'promptVersion': specificity_manifest['promptVersion'],
                'freeTierOnly': True, 'billingEnabled': False,
            },
            'sourceRestrictions': ['No JMdict or JMnedict input.'],
        }
        (classification / distribution.BUSINESS_CLASSIFICATIONS_MANIFEST_PATH.rsplit('/', 1)[-1]).write_text(
            json.dumps(metadata), encoding='utf-8')
        return metadata

    def test_prepare_snapshots_unique_existing_pairs_and_all_fourteen_leaves(self):
        business.prepare(self.root, self.workspace, batch_size=1)

        manifest = json.loads((self.workspace / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['source_term_records'], 3)
        self.assertEqual(manifest['unique_pairs'], 3)
        self.assertEqual(manifest['batch_count'], 3)
        self.assertEqual(len(manifest['category_ids']), 15)  # 14 business leaves + outside
        self.assertEqual(manifest['source_path'], business.SOURCE_PATH)
        self.assertNotIn('JMdict', manifest['source_path'])

    def test_prompt_keeps_general_it_out_of_business_security(self):
        prompt = business.business_prompt(business.collect_items(self.root), business.load_categories(self.root))
        self.assertIn('既存IT専門辞書に残すため「業務用語ではない」', prompt)
        self.assertIn('企業の運用・統制に限ります', prompt)

    def test_pending_business_data_does_not_change_unexpanded_distribution(self):
        categories_path = self.root / 'src/main/classification/categories.json'
        categories = json.loads(Path('src/main/classification/categories.json').read_text(encoding='utf-8'))
        categories['categories'] = [category for category in categories['categories']
                                    if not category['id'].startswith('business/')]
        categories['categoryGroups'] = [group for group in categories['categoryGroups']
                                        if group['id'] != 'business']
        categories_path.write_text(json.dumps(categories), encoding='utf-8')
        decisions = {('りんぎ', '稟議'): ['りんぎ', '稟議',
                                       'term/specialist/economics_management', 'gemini', 'classified']}

        applied = distribution.apply_business_classifications(self.root, decisions)

        self.assertEqual(applied, decisions)

    def test_source_backed_business_additions_keep_verified_origin(self):
        for kind in ('business_glossary_source', 'business_dictionary_seed'):
            entry = {'action': 'add', 'baseline': None, 'evidence': {'kind': kind}}
            self.assertEqual(reviews.resulting_origin(entry), 'verified')

    def test_business_result_map_requires_exact_pair_coverage_and_free_provenance(self):
        classification = self.root / 'src/main/classification'
        taxonomy_path = classification / 'business-taxonomy.json'
        source_path = classification / 'term-classifications.tsv.gz'
        results_path = classification / 'business-classifications.tsv.gz'
        metadata_path = classification / 'business-classifications-manifest.json'
        taxonomy, leaves = distribution.business_taxonomy(self.root)
        pairs = [('けっさい', '決裁'), ('たようそにんしょう', '多要素認証'), ('りんぎ', '稟議')]
        source_pair_hash = hashlib.sha256(''.join(
            reading + '\t' + surface + '\n' for reading, surface in sorted(pairs)
        ).encode('utf-8')).hexdigest()
        provisional = {
            ('けっさい', '決裁'): 'business/common',
            ('たようそにんしょう', '多要素認証'): 'business/outside',
            ('りんぎ', '稟議'): 'business/outside',
        }
        metadata = self.write_business_fixture(provisional, {('けっさい', '決裁'): 'business/keep'})
        counts = metadata['categoryCounts']

        loaded = distribution.business_classification_data(self.root)
        self.assertEqual(loaded['results'][('けっさい', '決裁')], 'business/common')
        self.assertEqual(loaded['results'][('りんぎ', '稟議')], 'business/outside')
        self.assertEqual(loaded['results'][('たようそにんしょう', '多要素認証')], 'business/outside')

        # The frozen business map may not duplicate a term already owned by the IT specialist leaf.
        distribution.write_gzip(results_path, [
            ('けっさい', '決裁', 'business/common'),
            ('たようそにんしょう', '多要素認証', 'business/common'),
            ('りんぎ', '稟議', 'business/outside'),
        ])
        curated_path = classification / distribution.BUSINESS_CURATED_CLASSIFICATIONS_PATH.rsplit('/', 1)[-1]
        curated_path.write_text('けっさい\t決裁\tbusiness/common\nたようそにんしょう\t多要素認証\tbusiness/common\n',
                                encoding='utf-8')
        counts['business/common'] = 2
        metadata['outsideBusinessPairs'] = 1
        metadata['categoryCounts'] = counts
        metadata['curatedClassifications'] = {
            'path': distribution.BUSINESS_CURATED_CLASSIFICATIONS_PATH,
            'sha256': distribution.sha(curated_path), 'pairCount': 2,
        }
        metadata['resultSha256'] = distribution.sha(results_path)
        metadata_path.write_text(json.dumps(metadata), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Curated business terms may not overlap'):
            distribution.business_classification_data(self.root)

        with self.assertRaisesRegex(ValueError, 'do not cover'):
            distribution.write_gzip(results_path, [('けっさい', '決裁', 'business/common')])
            metadata['resultSha256'] = distribution.sha(results_path)
            metadata_path.write_text(json.dumps(metadata), encoding='utf-8')
            distribution.business_classification_data(self.root)

    def test_business_reclassification_preserves_unrelated_category_memberships(self):
        classification = self.root / 'src/main/classification'
        results_path = classification / 'business-classifications.tsv.gz'
        metadata_path = classification / 'business-classifications-manifest.json'
        taxonomy, leaves = distribution.business_taxonomy(self.root)
        metadata = self.write_business_fixture({
            ('けっさい', '決裁'): 'business/accounting_finance',
            ('たようそにんしょう', '多要素認証'): 'business/outside',
            ('りんぎ', '稟議'): 'business/common',
        }, {
            ('けっさい', '決裁'): 'business/keep',
            ('りんぎ', '稟議'): 'business/keep',
        })
        decisions = {
            ('けっさい', '決裁'): ['けっさい', '決裁',
                                   'person,term/specialist/economics_management', 'manual', 'classified'],
            ('たようそにんしょう', '多要素認証'): ['たようそにんしょう', '多要素認証',
                                                 'term/specialist/information_communications', 'manual', 'classified'],
        }

        applied = distribution.apply_business_classifications(self.root, decisions, force=True)

        self.assertEqual(applied[('けっさい', '決裁')][2], 'business/accounting_finance,person')
        self.assertEqual(applied[('けっさい', '決裁')][3], 'manual')
        self.assertEqual(applied[('たようそにんしょう', '多要素認証')][2],
                         'term/specialist/information_communications')

    def test_export_requires_complete_specificity_review_and_freezes_final_map(self):
        business.prepare(self.root, self.workspace, batch_size=3)
        manifest = json.loads((self.workspace / 'manifest.json').read_text(encoding='utf-8'))
        items = list(business.common.read_jsonl(self.workspace / 'items.jsonl'))
        categories = business.load_categories(self.root)
        mapping = {
            ('けっさい', '決裁'): 'business/common',
            ('たようそにんしょう', '多要素認証'): 'business/it_security',
            ('りんぎ', '稟議'): 'business/outside',
        }
        rows = [{
            'batch_id': 'batch-000001', 'candidate_key': item['candidate_key'],
            'reading': item['reading'], 'surface': item['surface'],
            'category_code': next(i for i, category in enumerate(categories)
                                  if category['id'] == mapping[(item['reading'], item['surface'])]),
            'category_id': mapping[(item['reading'], item['surface'])],
            'model': business.common.MODEL, 'api_endpoint': business.common.API_ENDPOINT, 'free_only': True,
        } for item in items]
        business.common.write_jsonl(self.workspace / 'results' / 'batch-000001.jsonl', rows)
        business.common.save_json(self.workspace / 'free-tier-runs.json', [{
            'model': business.common.MODEL, 'api_endpoint': business.common.API_ENDPOINT,
            'prompt_version': business.PROMPT_VERSION, 'project_id': business.common.PROJECT,
            'free_tier': True, 'billing_enabled': False, 'proof_sha256': 'a' * 64,
            'verified_at': '2026-10-26T12:03:41+00:00', 'rpm': 15, 'tpm': 250000, 'rpd': 500,
        }])
        initial_map = {
            ('けっさい', '決裁'): 'business/common',
            ('たようそにんしょう', '多要素認証'): 'business/outside',
            ('りんぎ', '稟議'): 'business/outside',
        }
        with tempfile.TemporaryDirectory() as temporary:
            provisional = Path(temporary) / 'provisional.tsv.gz'
            distribution.write_gzip(provisional, ((*pair, initial_map[pair]) for pair in sorted(initial_map)))
            source_sha = distribution.sha(provisional)
        specificity_path = self.root / distribution.BUSINESS_SPECIFICITY_REVIEW_PATH
        distribution.write_gzip(specificity_path, [
            ('けっさい', '決裁', 'business/common', 'business/keep'),
        ])
        specificity_manifest = {
            'schemaVersion': 1, 'model': business.common.MODEL,
            'apiEndpoint': business.common.API_ENDPOINT, 'projectId': business.common.PROJECT,
            'promptVersion': 'business-specificity-practical-high-precision-v2',
            'freeTierOnly': True, 'billingEnabled': False,
            'sourcePath': business.OUTPUT_PATH, 'sourceSha256': source_sha,
            'candidatePairs': 1, 'keepPairs': 1, 'outsidePairs': 0,
            'resultSha256': distribution.sha(specificity_path),
            'freeTierProofs': [{'sha256': 'b' * 64, 'verifiedAt': '2026-10-26T12:03:41+00:00',
                                'rpm': 15, 'tpm': 250000, 'rpd': 500}],
        }
        (self.root / distribution.BUSINESS_SPECIFICITY_REVIEW_MANIFEST_PATH).write_text(
            json.dumps(specificity_manifest), encoding='utf-8')
        proof_path = self.root / 'free-tier-proof.json'
        proof_path.write_text(json.dumps({'verified_at': '2026-10-26T12:03:41+00:00',
                                          'free_tier': True, 'billing_enabled': False}), encoding='utf-8')

        business.export(SimpleNamespace(root=self.root, workspace=self.workspace, free_proof=proof_path))

        loaded = distribution.business_classification_data(self.root)
        self.assertEqual(loaded['results'][('けっさい', '決裁')], 'business/common')
        self.assertEqual(loaded['results'][('たようそにんしょう', '多要素認証')], 'business/outside')
        self.assertEqual(loaded['metadata']['specificityReview']['candidatePairs'], 1)

    def test_final_business_assignments_follow_the_curated_list_not_gemini_keep_labels(self):
        metadata = self.write_business_fixture(
            {('けっさい', '決裁'): 'business/common',
             ('たようそにんしょう', '多要素認証'): 'business/outside',
             ('りんぎ', '稟議'): 'business/outside'},
            {('けっさい', '決裁'): 'business/outside'},
        )

        loaded = distribution.business_classification_data(self.root)

        self.assertEqual(loaded['results'][('けっさい', '決裁')], 'business/common')
        self.assertEqual(metadata['specificityReview']['keepPairs'], 0)

    def test_business_taxonomy_builds_a_top_level_group_with_leaf_categories(self):
        taxonomy = json.loads(Path('src/main/classification/categories.json').read_text(encoding='utf-8'))
        data = distribution.business_taxonomy(self.root)
        merged = distribution.merged_categories(taxonomy, None, business_data=data)

        group = next(group for group in merged['categoryGroups'] if group['id'] == 'business')
        self.assertEqual(group['categories'], [leaf['id'] for leaf in data[1]])
        business_ids = [leaf['id'] for leaf in data[1]]
        self.assertEqual([leaf['id'] for leaf in merged['categories'][-14:]], business_ids)
        self.assertEqual(len([leaf for leaf in merged['categories'] if leaf['id'].startswith('business/')]), 14)

    def test_review_manifest_expands_categories_and_records_business_provenance(self):
        classification = self.root / 'src/main/classification'
        _, leaves = distribution.business_taxonomy(self.root)
        resources = self.root / 'src/main/resources'
        resources.mkdir(parents=True)
        (resources / 'id.def').write_text('0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n')
        category_data = json.loads(Path('src/main/classification/categories.json').read_text(encoding='utf-8'))
        (classification / 'categories.json').write_text(json.dumps(category_data), encoding='utf-8')
        results_path = classification / 'business-classifications.tsv.gz'
        metadata = self.write_business_fixture({
            ('けっさい', '決裁'): 'business/common',
            ('たようそにんしょう', '多要素認証'): 'business/outside',
            ('りんぎ', '稟議'): 'business/outside',
        }, {('けっさい', '決裁'): 'business/keep'})
        manifest = {'schemaVersion': 4, 'inputs': {}, 'categoryRows': {}, 'excludedCandidatePairs': 0,
                    'provenance': {'reviews': []}}
        decisions = {('けっさい', '決裁'): ['けっさい', '決裁', 'business/common', 'gemini', 'classified']}
        rows = {('business/common', 'けっさい', '1', '1', '8400', '決裁')}

        expanded = reviews.update_manifest(self.root, manifest, decisions, rows, [])

        self.assertEqual(manifest['schemaVersion'], 5)
        self.assertEqual(manifest['inputs']['src/main/classification/business-taxonomy.json'],
                         distribution.sha(classification / 'business-taxonomy.json'))
        self.assertEqual(manifest['categoryRows']['business/common'], 1)
        self.assertEqual(next(group for group in manifest['categoryGroups'] if group['id'] == 'business')['id'],
                         'business')
        self.assertEqual([row['id'] for row in expanded['categories'][-14:]], [leaf['id'] for leaf in leaves])


if __name__ == '__main__':
    unittest.main()
