import unittest
import contraction_case
import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_wiktionary as resolver
import test_lexicon_pipeline as fixtures


class ContractionCaseTests(unittest.TestCase):
    def test_source_labeled_auxiliary_contractions_never_invent_an_infinitive(self):
        model = pipeline.Lexicon(fixtures.SEED)
        records = [(1, {'word':"needn't", 'pos':'verb', 'forms':[],
            'head_templates':[{'name':'head','args':{'2':'verb form'}}],
            'senses':[{'tags':['auxiliary','formal'], 'categories':['English contractions']}]}),
            (2, {'word':'finna', 'pos':'verb', 'forms':[],
            'head_templates':[{'name':'en-head','args':{'1':'contr'}}],
            'senses':[{'tags':['auxiliary'], 'categories':['English contractions']}]}),
            (3, {'word':'unresolved-form-fixture','pos':'verb','forms':[],
            'head_templates':[{'name':'head','args':{'2':'verb form'}}],
            'senses':[{'tags':['auxiliary']}]})]
        resolver.import_records(model, records, set(), [])
        for surface in ["needn't", 'finna']:
            values = model.members[next(iter(model.approved[surface])), surface]
            self.assertIn('contraction', values)
            self.assertIn('verb', values)
            self.assertNotIn('verb_base', values)
            self.assertNotIn('verb_present_non3sg', values)
        self.assertFalse(model.approved.get('unresolved-form-fixture'))
        model.validate()

    def test_initial_capital_copies_only_the_contraction_sense_and_original_lemma(self):
        model = pipeline.Lexicon(fixtures.SEED)
        extension.ensure_categories(model, {'contraction'})
        proof = {'source':'esdb','url':'https://example.org/contraction','approved':True}
        model.add('contracted', "fixture'nt", "fixture'nt", {'contraction'}, proof, approved=True)
        model.add('ordinary', "fixture'nt", "fixture'nt", {'noun'}, proof, approved=True)
        result = contraction_case.attach(model, [{'id':'manual:1','surface':"Fixture'nt"},
            {'id':'manual:2','surface':"Fixture'NT"}, {'id':'tsv:1','surface':"Fixture'nt"}])
        self.assertEqual({'manual:1'}, result)
        self.assertEqual({'contracted'}, model.approved["Fixture'nt"])
        self.assertEqual("fixture'nt", model.forms['contracted',"Fixture'nt"]['lemma'])
        model.validate()


if __name__ == '__main__': unittest.main()
