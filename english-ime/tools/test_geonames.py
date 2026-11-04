import io
import json
from pathlib import Path
import tempfile
import unittest

import geonames
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class GeoNamesTests(unittest.TestCase):
    def test_only_explicit_current_english_populated_aliases_qualify(self):
        features = {'10': {'featureCode': 'PPL', 'countryCode': 'ZZ'},
                    '20': {'featureCode': 'PPLH', 'countryCode': 'ZZ'}}
        def row(identifier, **changes):
            data = dict(alias=str(identifier), gid='10', lang='en', label='Fixture', preferred='1',
                        short='', colloquial='', historic='', start='', end='')
            data.update(changes)
            return '\t'.join(data.values()) + '\n'
        text = ''.join([row(1), row(2, lang='fr'), row(3, lang=''), row(4, historic='1'),
                        row(5, colloquial='1'), row(6, gid='20'), row(7, start='1900'),
                        row(8, end='2000'), row(9, preferred='', short=''), row(10, gid='30'),
                        row(11, preferred='', short='1', label='Short Fixture')])
        names = list(geonames.english_alternates(io.StringIO(text), features))
        self.assertEqual(['1', '11'], [r['alternateId'] for r in names])
        self.assertEqual([1, 11], [r['line'] for r in names])
        self.assertEqual('Fixture', names[0]['label'])

    def test_place_identity_has_no_invented_countability_inflection_or_input_alias(self):
        model = pipeline.Lexicon(fixtures.SEED)
        rows = [{'id': 'manual:1', 'reading': 'fixture', 'surface': 'fixture', 'cost': 700}]
        names = [{'kind': 'english_admin1', 'geonameId': '10', 'label': 'Fixture', 'line': 1, 'adminCode': 'ZZ.1'}]
        counts = geonames.attach(model, rows, names)
        self.assertEqual(1, counts['english_admin1'])
        self.assertFalse(model.approved.get('fixture'))
        key = next(iter(model.approved['Fixture']))
        self.assertEqual({'noun', 'noun_proper', 'name_place'}, model.members[key, 'Fixture'])
        self.assertTrue(all(r['relation'] != 'input_alias' for r in model.relations))
        model.validate()

    def test_changed_source_and_existing_preparation_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / 'admin1CodesASCII.txt').write_text('changed source')
            with self.assertRaisesRegex(ValueError, 'Changed GeoNames source'):
                geonames.prepare(source, source / 'out')
            with self.assertRaisesRegex(ValueError, 'Preserve existing'):
                geonames.prepare(source, source)

    def test_wrong_preparation_policy_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'manifest.json').write_text(json.dumps({'schemaVersion': 1, 'sourcePins': geonames.PINS, 'policy': 'allow all names'}))
            with self.assertRaisesRegex(ValueError, 'Unrecognized'):
                geonames.load(directory)


if __name__ == '__main__':
    unittest.main()
