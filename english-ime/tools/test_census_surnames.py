import unittest
import census_surnames
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class CensusSurnameTests(unittest.TestCase):
    def test_source_case_is_retained_without_inventing_title_case_or_morphology(self):
        model = pipeline.Lexicon(fixtures.SEED)
        census_surnames.attach(model, [{'surface': 'fixturefamily'}],
            [{'name': 'FIXTUREFAMILY', 'rank': 123, 'count': 100}], {})
        self.assertTrue(model.approved['FIXTUREFAMILY'])
        self.assertFalse(model.approved.get('Fixturefamily'))
        key = next(iter(model.approved['FIXTUREFAMILY']))
        self.assertEqual({'noun', 'noun_proper', 'name_person'}, model.members[key, 'FIXTUREFAMILY'])
        self.assertFalse(model.evidence[key, 'FIXTUREFAMILY'][0]['preferredCaseClaimed'])

    def test_separately_documented_case_is_preserved_and_unrelated_names_not_added(self):
        model = pipeline.Lexicon(fixtures.SEED)
        count = census_surnames.attach(model, [{'surface': 'mcfixture'}],
            [{'name': 'MCFIXTURE', 'rank': 123, 'count': 100}, {'name': 'OTHER', 'rank': 124, 'count': 100}],
            {'mcfixture': [('McFixture', 456)]})
        self.assertEqual(1, count)
        self.assertTrue(model.approved['McFixture'])
        self.assertFalse(model.approved.get('MCFIXTURE'))
        self.assertFalse(model.approved.get('OTHER'))
        model.validate()


if __name__ == '__main__':
    unittest.main()
