import json
from pathlib import Path
import tempfile
import unittest

import export_person_dictionary_source as exporter


class PersonAdditionExportTest(unittest.TestCase):
    def test_explicit_category_and_sport_additions_are_routed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resources = root / 'src/main/resources'
            classification = root / 'src/main/classification'
            additions_dir = classification / 'person-additions'
            resources.mkdir(parents=True)
            additions_dir.mkdir(parents=True)
            (resources / 'id.def').write_text('1851 名詞,一般,*,*,*,*,*\n', encoding='utf-8')
            (classification / 'person-taxonomy.json').write_text(json.dumps({
                'categories': [
                    {'id': 'comedian', 'standard_enabled': True},
                    {'id': 'sports', 'standard_enabled': True},
                ],
                'sport_subcategories': {'baseball': '野球'},
            }), encoding='utf-8')
            common = dict(left_id=1851, right_id=1851, cost=8400,
                          source_url='https://example.org/profile', checked_on='2026-10-22')
            rows = [
                dict(reading='げいにん', surface='芸人', category_id='comedian',
                     source_surface='芸人', source_reading='げいにん', **common),
                dict(reading='やきゅうせんしゅ', surface='野球選手', sport='baseball',
                     source_surface='野球選手', source_reading='やきゅうせんしゅ', **common),
            ]
            (additions_dir / 'reviewed.jsonl').write_text(
                ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                encoding='utf-8')

            comedian_key = exporter.candidate_key('げいにん', '芸人')
            final = {comedian_key: ('げいにん', '芸人', 'actor', set())}
            exporter.apply_person_additions(root, final, {'comedian', 'sports'})

            self.assertEqual(final[comedian_key], ('げいにん', '芸人', 'comedian', set()))
            self.assertEqual(final[exporter.candidate_key('やきゅうせんしゅ', '野球選手')],
                             ('やきゅうせんしゅ', '野球選手', 'sports', {'baseball'}))


class PersonNameOriginExportTest(unittest.TestCase):
    def test_applies_origin_targets_and_preserves_dictionary_tags(self):
        reading, surface = 'たなか', '田中'
        key = exporter.candidate_key(reading, surface)
        final = {key: (reading, surface, 'surname_origin_unconfirmed', {'野球'})}
        count = exporter.apply_name_origin_mapping(
            final, {key: ('surname_origin_unconfirmed', 'surname_origin_japanese')})
        self.assertEqual(count, 1)
        self.assertEqual(final[key], (reading, surface, 'surname_origin_japanese', {'野球'}))

    def test_skips_mapping_for_candidates_already_reclassified_by_a_later_review(self):
        reading, surface = 'あやなん', 'あやなん'
        key = exporter.candidate_key(reading, surface)
        final = {key: (reading, surface, 'online_creator', set())}
        mapping = {key: ('personal_name_origin_unconfirmed', 'personal_name_origin_japanese')}
        self.assertEqual(exporter.apply_name_origin_mapping(final, mapping, {key}), 0)
        self.assertEqual(final[key][2], 'online_creator')

    def test_rejects_missing_or_mismatched_origin_source(self):
        reading, surface = 'たなか', '田中'
        key = exporter.candidate_key(reading, surface)
        final = {key: (reading, surface, 'surname_origin_unconfirmed', set())}
        with self.assertRaisesRegex(ValueError, 'do not cover unresolved'):
            exporter.apply_name_origin_mapping(final, {}, {key})
        with self.assertRaisesRegex(ValueError, 'source category'):
            exporter.apply_name_origin_mapping(
                final, {key: ('given_name_origin_unconfirmed', 'surname_origin_japanese')}, {key})


if __name__ == '__main__':
    unittest.main()
