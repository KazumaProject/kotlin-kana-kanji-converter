import gzip
import json
from pathlib import Path
import unittest

import person_gemini_classification as gemini
import review_person_classifications as reviews


ROOT = Path(__file__).resolve().parents[1]


class PersonTaxonomyPolicyTest(unittest.TestCase):
    def test_military_and_thought_are_withheld_from_standard_person_data(self):
        taxonomy, _, _ = reviews.taxonomy_maps(
            ROOT / 'src/main/classification/person-taxonomy.json')
        categories = {row['id']: row for row in taxonomy['categories']}
        self.assertFalse(categories['military']['standard_enabled'])
        self.assertFalse(categories['thought']['standard_enabled'])
        self.assertEqual(taxonomy['policy']['standard_dictionary_withheld_categories'],
                         ['military', 'thought'])
        self.assertIn(22, gemini.MANUAL_ONLY_CODES)
        self.assertIn(30, gemini.MANUAL_ONLY_CODES)

    def test_person_dictionary_snapshot_and_overrides_omit_withheld_categories(self):
        path = ROOT / 'src/main/classification/person-dictionary-candidates.tsv.gz'
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            rows = [line.rstrip('\n').split('\t') for line in stream]
        self.assertTrue(rows)
        self.assertFalse(any(row[0] in {'military', 'thought'} for row in rows))

        overrides = ROOT / 'src/main/classification/person-category-overrides.jsonl'
        records = [json.loads(line) for line in overrides.read_text(encoding='utf-8').splitlines()]
        self.assertFalse(any(row.get('target_category_id') in {'military', 'thought'}
                             for row in records))


if __name__ == '__main__':
    unittest.main()
