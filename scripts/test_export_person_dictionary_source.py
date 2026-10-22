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


if __name__ == '__main__':
    unittest.main()
