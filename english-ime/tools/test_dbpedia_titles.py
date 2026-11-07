import unittest
import dbpedia_titles
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class DBpediaTitleTests(unittest.TestCase):
    def test_coarse_artist_and_company_labels_do_not_invent_person_or_organization_types(self):
        model = pipeline.Lexicon(fixtures.SEED)
        rows = [{'title': 'Fixture Band', 'label': 2, 'row': 1, 'file': 'train-00000-of-00001.parquet'},
                {'title': 'Fixture Brand', 'label': 0, 'row': 2, 'file': 'train-00000-of-00001.parquet'}]
        dbpedia_titles.attach(model, rows)
        for title in ['Fixture Band', 'Fixture Brand']:
            key = next(iter(model.approved[title]))
            self.assertEqual({'noun', 'noun_proper'}, model.members[key, title])
        model.validate()

    def test_explicit_human_class_is_separate_from_species_and_no_morphology_is_guessed(self):
        model = pipeline.Lexicon(fixtures.SEED)
        dbpedia_titles.attach(model, [{'title': 'Fixture', 'label': label, 'row': label, 'file': 'test-00000-of-00001.parquet'} for label in [3, 9]])
        values = {frozenset(model.members[key, 'Fixture']) for key in model.approved['Fixture']}
        self.assertEqual({frozenset({'noun', 'noun_proper', 'name_person'}), frozenset({'noun', 'domain_science'})}, values)
        self.assertEqual(2, len(model.approved['Fixture']))
        model.validate()


if __name__ == '__main__':
    unittest.main()
