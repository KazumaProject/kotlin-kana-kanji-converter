import unittest
import named_case_variants as variants
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures

class NamedCaseTests(unittest.TestCase):
    def test_verified_name_casing_keeps_the_original_surface_and_independent_identity(self):
        model = pipeline.Lexicon(fixtures.SEED)
        proof = {'source': 'wiktionary', 'url': 'https://example.org/name', 'approved': True}
        model.add('software-name', 'FixtureCase', 'FixtureCase', {'noun', 'noun_proper', 'name_product'}, proof, approved=True)
        model.add('ordinary-verb', 'fixturecase', 'fixturecase', {'verb', 'verb_base'}, proof, approved=True)
        added = variants.attach(model, [{'id': 'manual:1', 'surface': 'Fixturecase'}])
        self.assertEqual({'manual:1'}, added)
        self.assertEqual({'software-name'}, model.approved['Fixturecase'])
        self.assertEqual('FixtureCase', model.forms['software-name','Fixturecase']['lemma'])
        self.assertNotIn('verb_base', model.members['software-name', 'Fixturecase'])
        model.validate()

    def test_ordinary_words_unverified_names_and_new_spellings_are_not_invented(self):
        model = pipeline.Lexicon(fixtures.SEED)
        proof = {'source': 'wiktionary', 'url': 'https://example.org/verb', 'approved': True}
        model.add('ordinary-verb', 'react', 'react', {'verb','verb_base'}, proof, approved=True)
        model.add('name', 'FixtureCase', 'FixtureCase', {'noun','noun_proper'}, proof, approved=True)
        rows = [{'id':'manual:1','surface':'React'}, {'id':'manual:2','surface':'FixtureCases'},
                {'id':'tsv:3','surface':'Fixturecase'}, {'id':'manual:3','surface':'Fixture Case'}]
        self.assertEqual(set(), variants.attach(model, rows))

if __name__ == '__main__': unittest.main()
