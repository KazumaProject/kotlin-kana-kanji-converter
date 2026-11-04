import unittest
import brand_names as brands
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class BrandNameTests(unittest.TestCase):
    def test_explicit_aliases_and_existing_manual_spacing_do_not_invent_inflections(self):
        model = pipeline.Lexicon(fixtures.SEED)
        rows = [{'id':'manual:1','surface':'FixtureCloud'}, {'id':'tsv:1','surface':'fixturecloud'},
            {'id':'manual:2','surface':'FixtureClouds'}, {'id':'manual:3','surface':'Fixture Cloud'}]
        records = [{'title':'Fixture Cloud','source':'https://example.org/brand','aliases':{'aka':['FC'],'old':['UnverifiedOldLabel']}}]
        brands.attach(model, rows, records)
        key = next(iter(model.approved['FixtureCloud']))
        self.assertEqual('Fixture Cloud', model.forms[key, 'FixtureCloud']['lemma'])
        self.assertEqual({'noun','noun_proper','name_brand'}, model.members[key, 'FixtureCloud'])
        self.assertEqual({key}, model.approved['FC'])
        for surface in ['fixturecloud', 'FixtureClouds', 'UnverifiedOldLabel']:
            self.assertFalse(model.approved.get(surface))
        model.validate()

    def test_shared_alias_keeps_separate_brands_and_ordinary_verb_identity(self):
        model = pipeline.Lexicon(fixtures.SEED)
        model.add('ordinary', 'fixture', 'fixture', {'verb','verb_base'},
            {'url':'https://example.org/verb','source':'wiktionary'}, approved=True)
        records = [{'title':title,'source':'https://example.org/' + str(i), 'aliases':{'aka':['fixture']}}
            for i, title in enumerate(['Fixture A','Fixture B'])]
        brands.attach(model, [], records)
        self.assertEqual(3, len(model.approved['fixture']))
        for key in model.approved['fixture'] - {'ordinary'}:
            self.assertNotIn('verb_base', model.members[key, 'fixture'])
            self.assertNotIn('name_organization', model.members[key, 'fixture'])
            self.assertNotIn('name_product', model.members[key, 'fixture'])
        model.validate()


if __name__ == '__main__': unittest.main()
