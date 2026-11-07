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

    def test_open_ordinary_reading_does_not_erase_independently_attested_name(self):
        model = pipeline.Lexicon(fixtures.SEED)
        proof = dict(source='wiktionary', url='https://example.org/fixture', approved=True)
        model.add('unresolved-word', 'fixture', 'fixture', {'noun'}, dict(proof, approved=False), approved=False)
        model.add('named-identity', 'Fixture', 'Fixture', {'noun', 'noun_proper'}, proof, approved=True)
        row = dict(id='tsv:1', surface='fixture', reading='fixture', cost=700)
        result = variants.source_name_candidates(model, [row])
        self.assertEqual('Fixture', result[0]['target'])
        self.assertFalse(model.approved.get('fixture'))
        self.assertEqual({'noun'}, model.members['unresolved-word', 'fixture'])
        self.assertEqual(700, row['cost'])

    def test_all_attested_cases_are_retained_without_manufacturing_casing(self):
        model = pipeline.Lexicon(fixtures.SEED)
        proof = dict(source='wiktionary', url='https://example.org/fixture', approved=True)
        for word in ['Fixture', 'FIXTURE']:
            model.add(word, word, word, {'noun', 'noun_proper'}, proof, approved=True)
        result = variants.source_name_candidates(model, [dict(id='tsv:1', surface='fixture', reading='fixture')])
        self.assertEqual(['FIXTURE', 'Fixture'], [row['target'] for row in result])
        self.assertTrue(all(row['relation']=='case_candidates' for row in result))

    def test_context_only_words_ordinary_capitalizations_and_changed_readings_are_rejected(self):
        model = pipeline.Lexicon(fixtures.SEED)
        proof = dict(source='wiktionary', url='https://example.org/fixture', approved=True)
        model.add('context', 'Fixture', 'Fixture', {'noun', 'noun_proper'}, dict(proof, requiresFullNamedContext=True), approved=True)
        model.add('capital-verb', 'Action', 'Action', {'verb', 'verb_base'}, proof, approved=True)
        rows = [dict(id='tsv:1', surface='fixture', reading='fixture'), dict(id='tsv:2', surface='action', reading='action')]
        self.assertEqual([], variants.source_name_candidates(model, rows))
        model.add('independent', 'Fixture', 'Fixture', {'noun', 'noun_proper'}, proof, approved=True)
        rows[0]['reading']='other'
        self.assertEqual([], variants.source_name_candidates(model, rows))

    def test_already_approved_exact_reading_is_preserved(self):
        model = pipeline.Lexicon(fixtures.SEED)
        proof = dict(source='wiktionary', url='https://example.org/fixture', approved=True)
        for word in ['fixture', 'Fixture']:
            model.add(word, word, word, {'noun', 'noun_proper'}, proof, approved=True)
        self.assertEqual([], variants.source_name_candidates(model, [dict(id='tsv:1', surface='fixture', reading='fixture')]))

if __name__ == '__main__': unittest.main()
