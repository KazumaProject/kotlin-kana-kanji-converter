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

    def test_source_backed_addition_exports_to_thought(self):
        import json
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temporary:
            additions = Path(temporary)
            row = {
                'reading': 'かんと', 'surface': 'カント', 'category_id': 'thought',
                'classification_source_url': 'https://www.wikidata.org/wiki/Q9312',
                'classification_source_section': 'occupation statement P106: philosopher',
            }
            (additions / 'philosophers.jsonl').write_text(
                json.dumps(row, ensure_ascii=False) + '\n', encoding='utf-8')
            final = {}
            person_export.apply_person_additions(final, additions, {'thought'})
            self.assertEqual(final, {
                person_export.candidate_key('かんと', 'カント'):
                    ('かんと', 'カント', 'thought', set()),
            })


if __name__ == '__main__':
    unittest.main()
