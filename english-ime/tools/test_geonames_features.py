import io
import unittest

import geonames
import geonames_features as features
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class GeographicFeatureTests(unittest.TestCase):
    def test_english_alias_selection_keeps_accents_and_requires_explicit_labels(self):
        data = '1\t10\ten\tFixture\t1\t\t\t\t\t\n2\t20\t\tFixture\t1\t\t\t\t\t\n3\t30\ten\tFixtur\u00e9\t1\t\t\t\t\t\n4\t40\ten\tFixture\t1\t\t\t1\t\t\n'
        rows = list(features.english_aliases(io.StringIO(data), {'fixture'}))
        self.assertEqual(['10'], [r['geonameId'] for r in rows])
        self.assertEqual('Fixture', rows[0]['label'])

    def test_alias_ids_must_join_a_supported_feature_and_historic_populated_codes_are_omitted(self):
        def row(gid, cls, code):
            return '\t'.join([gid, 'name', 'ascii', 'unverified aliases', '0', '0', cls, code, 'ZZ', '', '', '', '', '', '0', '', '', 'UTC', '2026-11-04']) + '\n'
        data = row('10', 'T', 'MT') + row('20', 'P', 'PPLH') + row('30', 'X', 'unknown') + row('40', 'S', 'AIRP')
        selected = dict(features.feature_matches(io.StringIO(data), {'10', '20', '30'}))
        self.assertEqual({'10'}, set(selected))
        self.assertEqual('MT', selected['10']['featureCode'])
        self.assertEqual(1, selected['10']['featureSourceLine'])
        self.assertNotIn('label', selected['10'])

    def test_feature_metadata_cannot_invent_countability_or_accept_non_english_alias(self):
        model = pipeline.Lexicon(fixtures.SEED)
        row = {'id': '1', 'surface': 'Fixture'}
        record = {'kind': 'english_feature_alternate', 'alternateId': '10', 'geonameId': '100', 'label': 'Fixture',
                  'line': 1, 'language': 'en', 'preferred': True, 'short': False, 'featureClass': 'T', 'featureCode': 'MT',
                  'countryCode': 'ZZ', 'featureSourceLine': 10}
        geonames.attach(model, [row], [record])
        key = next(iter(model.approved['Fixture']))
        self.assertEqual({'noun', 'noun_proper', 'name_place'}, model.members[key, 'Fixture'])
        for changes in [{'language': ''}, {'historic': True}, {'featureClass': 'X'}, {'featureCode': 'PPLH'}]:
            with self.assertRaisesRegex(ValueError, 'Ineligible English geographic'):
                geonames.attach(model, [row], [dict(record, **changes)])
        model.validate()


if __name__ == '__main__':
    unittest.main()
