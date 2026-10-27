import gzip
import json
from pathlib import Path
import tempfile
import unittest

import person_gemini_classification as gemini
import person_name_origin_classification as origins
import review_person_classifications as reviews
import sync_person_name_origin_type_review as type_review_sync


ROOT = Path(__file__).resolve().parents[1]


class PersonNameOriginClassificationTest(unittest.TestCase):
    def test_taxonomy_has_six_provisional_categories(self):
        taxonomy, by_id = origins.taxonomy_maps(ROOT)
        self.assertEqual(len(gemini.load_taxonomy(ROOT)['categories']), 38)
        self.assertEqual(len(taxonomy['categories']), 38)
        self.assertEqual(sum(row.get('standard_enabled') is True
                             for row in taxonomy['categories']), 29)
        for source_id, targets in origins.SOURCE_CATEGORIES.items():
            self.assertTrue(all(by_id[target]['standard_enabled'] for target in targets))
            self.assertEqual(origins.target_for_code(source_id, 0), source_id)
            self.assertTrue(set(targets) <= reviews.MANUAL_ONLY_CATEGORY_IDS)
        self.assertTrue(all(code in gemini.CODE_SYMBOLS for pair in origins.ORIGIN_CODES.values()
                            for code in pair))

    def test_wrong_name_type_model_codes_remain_unconfirmed(self):
        items = [
            {'candidate_key': 'a' * 64, 'source_category_id': 'surname_origin_unconfirmed'},
            {'candidate_key': 'b' * 64, 'source_category_id': 'given_name_origin_unconfirmed'},
        ]
        rows = origins.rows_for_result(items, [33, 33], 'batch-000001')
        self.assertEqual(rows[0]['category_code'], 33)
        self.assertEqual(rows[1]['category_code'], 0)
        self.assertEqual(origins.target_for_code(rows[1]['source_category_id'], 0),
                         'given_name_origin_unconfirmed')

    def test_parser_accepts_space_separated_codes(self):
        codes, missing = gemini.parse_codes(
            {'codes': '0:P Q U P Q U P Q U P'}, 10)
        self.assertEqual(codes, [33, 34, 38, 33, 34, 38, 33, 34, 38, 33])
        self.assertEqual(missing, [])

    def test_collect_candidates_deduplicates_records_and_rejects_cross_type_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / origins.SOURCE_PATH
            path.parent.mkdir(parents=True)
            with gzip.open(path, 'wt', encoding='utf-8', newline='') as stream:
                stream.write('surname_origin_unconfirmed\tたなか\t1\t1\t8000\t田中\t\n')
                stream.write('surname_origin_unconfirmed\tたなか\t2\t2\t8100\t田中\t\n')
                stream.write('given_name_origin_unconfirmed\tはなこ\t1\t1\t8000\t花子\t\n')
            rows, record_count = origins.collect_candidates(root)
            self.assertEqual(len(rows), 2)
            self.assertEqual(record_count, 3)
            self.assertEqual({row['source_category_id'] for row in rows},
                             {'surname_origin_unconfirmed', 'given_name_origin_unconfirmed'})

    def test_fixed_mapping_manifest_hashes_and_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            taxonomy_path = root / origins.TAXONOMY_PATH
            taxonomy_path.parent.mkdir(parents=True)
            taxonomy_path.write_bytes((ROOT / origins.TAXONOMY_PATH).read_bytes())
            distribution_source = root / origins.DISTRIBUTION_SOURCE_PATH
            with gzip.open(distribution_source, 'wt', encoding='utf-8') as stream:
                stream.write('person\tかな\t1\t1\t8000\t表記\n')
            mapping_path = root / origins.MAPPING_PATH
            mapping_path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(mapping_path, 'wt', encoding='utf-8') as stream:
                stream.write('surname_origin_unconfirmed\t' + 'a' * 64 + '\tsurname_origin_japanese\n')
            manifest_path = root / origins.MANIFEST_PATH
            manifest_path.write_text(json.dumps({
                'schema_version': 1,
                'completed': True,
                'model': gemini.MODEL,
                'project_id': gemini.PROJECT,
                'prompt_version': origins.PROMPT_VERSION,
                'classification_status': 'Gemini-only provisional; not independently reviewed',
                'initial_run_free_tier_only': True,
                'taxonomy_sha256': gemini.sha(taxonomy_path),
                'distribution_source_sha256': gemini.sha(distribution_source),
                'mapping_path': origins.MAPPING_PATH,
                'mapping_sha256': gemini.sha(mapping_path),
                'unique_pairs': 1,
                'target_pair_counts': {'surname_origin_japanese': 1},
            }), encoding='utf-8')
            mapping, _ = origins.load_fixed_mapping(root)
            self.assertEqual(mapping['a' * 64],
                             ('surname_origin_unconfirmed', 'surname_origin_japanese'))

    def test_merged_inputs_are_checked_against_the_name_origin_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = origins.candidate_key('かな', '表記')
            taxonomy_path = root / origins.TAXONOMY_PATH
            taxonomy_path.parent.mkdir(parents=True)
            taxonomy_path.write_bytes((ROOT / origins.TAXONOMY_PATH).read_bytes())
            distribution_source = root / origins.DISTRIBUTION_SOURCE_PATH
            with gzip.open(distribution_source, 'wt', encoding='utf-8') as stream:
                stream.write('person\tかな\t1\t1\t8000\t表記\n')
            mapping_path = root / origins.MAPPING_PATH
            mapping_path.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(mapping_path, 'wt', encoding='utf-8') as stream:
                stream.write('surname_origin_unconfirmed\t' + key + '\tsurname_origin_japanese\n')
            source_projection = origins.mapped_distribution_source_projection(root, {key})
            taxonomy = json.loads(taxonomy_path.read_text(encoding='utf-8'))
            taxonomy_projection_hash = origins.hashlib.sha256(
                origins.json_bytes(origins.name_origin_taxonomy_projection(taxonomy))).hexdigest()
            manifest_path = root / origins.MANIFEST_PATH
            manifest_path.write_text(json.dumps({
                'schema_version': 1,
                'completed': True,
                'model': gemini.MODEL,
                'project_id': gemini.PROJECT,
                'prompt_version': origins.PROMPT_VERSION,
                'classification_status': 'Gemini-only provisional; not independently reviewed',
                'initial_run_free_tier_only': True,
                'taxonomy_sha256': 'b' * 64,
                'distribution_source_sha256': 'c' * 64,
                'mapping_path': origins.MAPPING_PATH,
                'mapping_sha256': gemini.sha(mapping_path),
                'unique_pairs': 1,
                'target_pair_counts': {'surname_origin_japanese': 1},
                'merge_compatibility': {
                    'name_origin_taxonomy_projection_sha256': taxonomy_projection_hash,
                    'mapped_distribution_source': source_projection,
                },
            }), encoding='utf-8')
            mapping, _ = origins.load_fixed_mapping(root)
            self.assertIn(key, mapping)

            with gzip.open(distribution_source, 'wt', encoding='utf-8') as stream:
                stream.write('person\tかな\t2\t1\t8000\t表記\n')
            with self.assertRaisesRegex(ValueError, 'Mapped name-origin source rows'):
                origins.load_fixed_mapping(root)

    def test_audit_corrects_name_type_without_inventing_origin(self):
        full_names = [
            ('いわもとやすひで','岩本泰英'),('おさだまさよし','長田雅喜'),('かわばたていじ','河端貞次'),
            ('かんき','韓軌'),('これかわぎんぞう','是川銀蔵'),('こんどうせいや','近藤誠也'),
            ('こんのかつこ','今野華都子'),('さいさいこう','蔡再鴻'),('とみたただすけ','冨田ただすけ'),
            ('とーますせうぇる','トーマスセウェル'),('なかとみさぶろう','中冨三郎'),
            ('なかにしすすむ','中西進'),('なかのみゆき','中野みゆき'),('ひろせさとし','廣瀬智央'),
            ('びんおんたく','閔恩沢'),('ふぁんびょんそ','黄炳瑞'),('ふうじょ','馮如'),('もろさわまさお','諸澤昌男'),
        ]
        mapping, manifest = origins.load_fixed_mapping(ROOT)
        for reading, surface in full_names:
            with self.subTest(surface=surface):
                self.assertEqual(
                    mapping[origins.candidate_key(reading, surface)],
                    ('surname_origin_unconfirmed', 'personal_name_origin_unconfirmed'))
        expected = {
            ('ねんげんろく','年限禄'): 'excluded_non_person',
            ('のーばでぃ','NOBODY'): 'excluded_non_person',
            ('とみすらふ','トミスラフ'): 'given_name_origin_foreign',
        }
        for (reading, surface), target in expected.items():
            with self.subTest(surface=surface):
                self.assertEqual(mapping[origins.candidate_key(reading, surface)],
                                 ('surname_origin_unconfirmed', target))

        review_manifest = manifest['manual_type_review']
        self.assertEqual(review_manifest['reviewed_pairs'], 21)
        self.assertEqual(review_manifest['review_target_pair_counts'], {
            'excluded_non_person': 2,
            'given_name_origin_foreign': 1,
            'personal_name_origin_unconfirmed': 18,
        })
        stale_counts = dict(review_manifest, reviewed_pairs=22)
        with self.assertRaisesRegex(ValueError, 'counts differ'):
            origins.validate_manual_type_review(ROOT, mapping, stale_counts)

    def test_type_review_sync_changes_only_category_and_drops_non_people(self):
        full_key = origins.candidate_key('いわもとやすひで', '岩本泰英')
        given_key = origins.candidate_key('とみすらふ', 'トミスラフ')
        excluded_key = origins.candidate_key('ねんげんろく', '年限禄')
        mapping = {
            full_key: ('surname_origin_unconfirmed', 'personal_name_origin_unconfirmed'),
            given_key: ('surname_origin_unconfirmed', 'given_name_origin_foreign'),
            excluded_key: ('surname_origin_unconfirmed', 'excluded_non_person'),
        }
        reviews = [
            {'candidate_key': full_key, 'reading': 'いわもとやすひで', 'surface': '岩本泰英',
             'source_category_id': 'surname_origin_unconfirmed',
             'target_category_id': 'personal_name_origin_unconfirmed',
             'previous_dictionary_category_id': 'surname_origin_foreign'},
            {'candidate_key': given_key, 'reading': 'とみすらふ', 'surface': 'トミスラフ',
             'source_category_id': 'surname_origin_unconfirmed',
             'target_category_id': 'given_name_origin_foreign',
             'previous_dictionary_category_id': 'surname_origin_foreign'},
            {'candidate_key': excluded_key, 'reading': 'ねんげんろく', 'surface': '年限禄',
             'source_category_id': 'surname_origin_unconfirmed',
             'target_category_id': 'excluded_non_person',
             'previous_dictionary_category_id': 'surname_origin_foreign'},
        ]
        source = [
            ['surname_origin_foreign', 'いわもとやすひで', '1851', '1851', '8400', '岩本泰英', ''],
            ['surname_origin_foreign', 'とみすらふ', '1851', '1851', '7890', 'トミスラフ', ''],
            ['surname_origin_foreign', 'ねんげんろく', '1851', '1851', '9441', '年限禄', ''],
            ['writer', 'やまだ', '1', '2', '8000', '山田', ''],
        ]
        result, counts = type_review_sync.apply_type_review(
            source, mapping, reviews,
            {'writer': 1, 'surname_origin_foreign': 2,
             'given_name_origin_foreign': 3, 'personal_name_origin_unconfirmed': 4},
            first_sync=True,
        )
        self.assertIn(['personal_name_origin_unconfirmed', 'いわもとやすひで', '1851',
                       '1851', '8400', '岩本泰英', ''], result)
        self.assertIn(['given_name_origin_foreign', 'とみすらふ', '1851', '1851',
                       '7890', 'トミスラフ', ''], result)
        self.assertIn(['writer', 'やまだ', '1', '2', '8000', '山田', ''], result)
        self.assertFalse(any(row[1] == 'ねんげんろく' for row in result))
        self.assertEqual(counts, {
            'reviewed_pairs': 3, 'changed_records': 2, 'excluded_records': 1,
            'records_before': 4, 'records_after': 3,
        })

        with self.assertRaisesRegex(ValueError, 'unexpected category'):
            type_review_sync.apply_type_review(
                [['surname_origin_japanese', *source[0][1:]]], mapping, reviews[:1],
                {'surname_origin_foreign': 1, 'surname_origin_japanese': 2,
                 'personal_name_origin_unconfirmed': 3}, first_sync=True,
            )


if __name__ == '__main__':
    unittest.main()
