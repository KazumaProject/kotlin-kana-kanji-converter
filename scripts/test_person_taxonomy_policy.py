import gzip
import json
from pathlib import Path
import tempfile
import unittest

import export_person_dictionary_source as person_export
import person_gemini_classification as gemini
import review_person_classifications as reviews


ROOT = Path(__file__).resolve().parents[1]


class PersonTaxonomyPolicyTest(unittest.TestCase):
    def test_thought_is_standard_enabled_and_military_remains_withheld(self):
        taxonomy, _, _ = reviews.taxonomy_maps(
            ROOT / 'src/main/classification/person-taxonomy.json')
        categories = {row['id']: row for row in taxonomy['categories']}
        self.assertFalse(categories['military']['standard_enabled'])
        self.assertTrue(categories['thought']['standard_enabled'])
        self.assertEqual(categories['thought']['label'], '哲学者・思想家')
        self.assertEqual(taxonomy['policy']['standard_dictionary_withheld_categories'],
                         ['military'])
        self.assertIn(22, gemini.MANUAL_ONLY_CODES)
        self.assertIn(30, gemini.MANUAL_ONLY_CODES)

    def test_person_dictionary_snapshot_includes_thought_but_omits_military(self):
        path = ROOT / 'src/main/classification/person-dictionary-candidates.tsv.gz'
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            rows = [line.rstrip('\n').split('\t') for line in stream]
        self.assertTrue(rows)
        self.assertTrue(any(row[0] == 'thought' for row in rows))
        self.assertFalse(any(row[0] == 'military' for row in rows))

        overrides = ROOT / 'src/main/classification/person-category-overrides.jsonl'
        records = [json.loads(line) for line in overrides.read_text(encoding='utf-8').splitlines()]
        self.assertFalse(any(row.get('target_category_id') == 'military'
                             for row in records))

    def test_board_sport_labels_are_available_for_person_classification(self):
        taxonomy, _, _ = reviews.taxonomy_maps(
            ROOT / 'src/main/classification/person-taxonomy.json')
        sports = taxonomy['sport_subcategories']
        self.assertEqual(sports['skateboarding'], 'スケートボード')
        self.assertEqual(sports['snowboarding'], 'スノーボード')
        self.assertEqual(sports['breaking'], 'ブレイクダンス（ブレイキン）')
        labels = reviews.labels_for_sport()
        self.assertEqual(labels['スケートボード'], 'skateboarding')
        self.assertEqual(labels['スノーボード'], 'snowboarding')
        self.assertEqual(labels['ブレイクダンス'], 'breaking')
        self.assertEqual(labels['ブレイキン'], 'breaking')

    def test_source_backed_addition_exports_to_thought(self):
        import json
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            id_def = root / 'src/main/resources/id.def'
            id_def.parent.mkdir(parents=True)
            id_def.write_text('1851 test\n', encoding='utf-8')
            taxonomy_path = root / 'src/main/classification/person-taxonomy.json'
            taxonomy_path.parent.mkdir(parents=True)
            taxonomy_path.write_text(json.dumps({
                'categories': [{'id': 'thought', 'standard_enabled': True}],
                'sport_subcategories': {},
            }), encoding='utf-8')
            additions = root / 'src/main/classification/person-additions'
            additions.mkdir(parents=True)
            row = {
                'reading': 'かんと', 'surface': 'カント', 'category_id': 'thought',
                'left_id': 1851, 'right_id': 1851, 'cost': 8400,
                'source_url': 'https://www.wikidata.org/wiki/Q9312',
                'source_surface': 'カント', 'source_reading': 'カント',
                'checked_on': '2026-10-22',
                'classification_source_url': 'https://www.wikidata.org/wiki/Q9312',
                'classification_source_section': 'occupation statement P106: philosopher',
            }
            (additions / 'philosophers.jsonl').write_text(
                json.dumps(row, ensure_ascii=False) + '\n', encoding='utf-8')
            final = {}
            person_export.apply_person_additions(root, final, {'thought'})
            self.assertEqual(final, {
                person_export.candidate_key('かんと', 'カント'):
                    ('かんと', 'カント', 'thought', set()),
            })


if __name__ == '__main__':
    unittest.main()
