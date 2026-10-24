import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest

import classified_distribution as distribution
import facility_classification as rules
import run_facility_classification as runner


ROOT = Path(__file__).resolve().parents[1]


class FacilityClassificationTest(unittest.TestCase):
    def test_taxonomy_has_sixteen_defined_groups_and_no_catch_all_leaf(self):
        structure, leaves = distribution.facility_taxonomy(ROOT)
        self.assertEqual(len(structure['groups']), 16)
        self.assertTrue(all(group['name'] and group['definition'] for group in structure['groups']))
        self.assertTrue(all(leaf['name'] and leaf['definition'] for leaf in leaves))
        self.assertFalse(any(leaf['id'].rsplit('/', 1)[-1] in {
            'other', 'unclassified', 'unknown', 'review'
        } for leaf in leaves))

    def test_priority_and_requested_examples(self):
        examples = {
            ('あいちけんがんせんたー', '愛知県がんセンター'): 'facility/healthcare/hospital',
            ('だいがくびょういん', '大学病院'): 'facility/healthcare/hospital',
            ('あいおいしょうがっこう', '相生小学校'): 'facility/education/school',
            ('あいちけんびじゅつかん', '愛知県美術館'): 'facility/cultural/art_museum',
            ('あいちけんごこくじんじゃ', '愛知県護国神社'): 'facility/religious/shrine',
            ('いおんもーるくさつ', 'イオンモール草津'): 'facility/commercial/shopping',
            ('まるぬまこうげんすきーじょう', '丸沼高原スキー場'): 'facility/sports/ski',
            ('あいかわかりょくはつでんしょ', '相川火力発電所'): 'facility/industrial/power',
            ('よつぎばし', '四ツ木橋'): 'facility/infrastructure/bridge',
            ('えぐちじょう', '江口城'): 'facility/heritage/castle',
        }
        for (reading, surface), expected in examples.items():
            with self.subTest(surface=surface):
                result = rules.classify_with_rules(reading, surface)
                self.assertIsNotNone(result)
                self.assertEqual(result['category'], expected)
                self.assertEqual(result['method'], 'rule_high')

    def test_hospital_is_never_matched_by_temple_suffix(self):
        self.assertEqual(
            rules.classify_with_rules('びょういん', '病院')['category'],
            'facility/healthcare/hospital',
        )
        self.assertEqual(
            rules.classify_with_rules('よこすかきちびょういん', '横須賀基地病院')['category'],
            'facility/healthcare/hospital',
        )

    def test_railway_signal_yard_is_not_a_passenger_station(self):
        self.assertEqual(
            rules.classify_with_rules('あいたにしんごうじょう', '相谷信号場')['category'],
            'facility/transport/railway_facility',
        )

    def test_specific_facility_cues_override_generic_best_fit(self):
        examples = {
            ('あおいこうとうがくいん', '葵高等学院'): 'facility/education/school',
            ('あおみこーひー', '青海珈琲'): 'facility/commercial/restaurant',
            ('あかざきゆうほどう', '赤崎遊歩道'): 'facility/recreation/outdoor_nature',
            ('あいうらこう', '相浦港'): 'facility/transport/harbor',
            ('あいなでぐち', '藍那出入口'): 'facility/transport/road_facility',
            ('しゃりょうきち', '車両基地'): 'facility/transport/railway_facility',
            ('どうのえきよつくらこう', '道の駅よつくら港'): 'facility/transport/road_facility',
            ('じえいたいきち', '自衛隊基地'): 'facility/military/base',
        }
        for (reading, surface), expected in examples.items():
            with self.subTest(surface=surface):
                self.assertEqual(rules.classify_with_rules(reading, surface)['category'], expected)

    def test_individual_reviews_keep_their_evidence_and_boundary_state(self):
        reviewed = {
            ('きょうがくいん', '教学院'): ('facility/education/research', 'organization_boundary_review'),
            ('さんがくいん', '三学院'): ('facility/religious/temple', 'official_source_reviewed'),
            ('せいがくいん', '清学院'): ('facility/cultural/museum', 'official_source_reviewed'),
        }
        for pair, (category, review_state) in reviewed.items():
            with self.subTest(surface=pair[1]):
                result = rules.classify_with_rules(*pair)
                self.assertEqual(result['category'], category)
                self.assertEqual(result['method'], 'manual_review')
                self.assertEqual(result['reviewState'], review_state)
                self.assertTrue(result['evidenceUrl'].startswith('https://'))

    def test_boundary_hint_does_not_force_a_classification(self):
        self.assertEqual(rules.boundary_hint('とうきょうえき', '東京駅')['suggestedCategory'], 'station')
        self.assertIsNone(rules.classify_with_rules('とうきょうえき', '東京駅'))

    def test_pair_collection_is_deterministic_and_preserves_distinct_source_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'src/main/classification/distribution-candidates.tsv.gz'
            path.parent.mkdir(parents=True)
            rows = [
                ('facility', 'あいおいしょうがっこう', '1', '2', '300', '相生小学校'),
                ('facility', 'あいおいしょうがっこう', '1', '2', '301', '相生小学校'),
                ('facility/commercial/restaurant', 'らーめんてん', '3', '4', '500', 'らーめん店'),
                ('person', 'あいおいしょうがっこう', '1', '2', '300', '相生小学校'),
            ]
            with gzip.open(path, 'wt', encoding='utf-8', newline='\n') as stream:
                for row in rows:
                    stream.write('\t'.join(row) + '\n')
            digest_before = distribution.sha(path)
            self.assertEqual(rules.collect_facility_pairs(root), [
                ('あいおいしょうがっこう', '相生小学校'),
                ('らーめんてん', 'らーめん店'),
            ])
            self.assertEqual(distribution.sha(path), digest_before)

    def test_free_runner_uses_compact_batches_and_aggregate_rate_limit(self):
        self.assertEqual(runner.DEFAULT_BATCH_SIZE, 50)
        self.assertEqual(runner.safe_request_interval(4.1, 1, 15), 4.1)
        self.assertEqual(runner.safe_request_interval(4.1, 2, 15), 8.2)

    def test_frozen_results_cover_the_adopted_source_snapshot(self):
        pairs, records = runner.collect_source(ROOT)
        data = distribution.facility_classification_data(ROOT)
        self.assertEqual(set(pairs), set(data['results']))
        self.assertEqual(len(pairs), data['metadata']['uniquePairs'])
        self.assertEqual(len(records), data['metadata']['sourceRecords'])
        record_hash = hashlib.sha256(''.join('\t'.join(row) + '\n' for row in records).encode()).hexdigest()
        self.assertEqual(record_hash, data['metadata']['sourceRecordSha256'])
        self.assertEqual(sum(data['metadata']['classificationCounts'].values()), len(pairs))
        self.assertEqual(data['metadata']['unclassifiedPairs'], 0)
        self.assertEqual(data['metadata']['otherCategoryPairs'], 0)
        boundary_count = len(rules.possible_boundary_suggestions(pairs))
        self.assertEqual(boundary_count, data['metadata']['boundaryReviewPairs'])
        for pair, frozen in data['results'].items():
            current_rule = rules.classify_with_rules(*pair)
            with self.subTest(pair=pair):
                if current_rule is None:
                    self.assertNotEqual(frozen['method'], 'rule_high')
                else:
                    self.assertEqual(frozen['method'], current_rule['method'])
                    self.assertEqual(frozen['category'], current_rule['category'])


if __name__ == '__main__':
    unittest.main()
