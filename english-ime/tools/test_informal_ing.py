import unittest
import informal_ing as i
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class InformalTests(unittest.TestCase):
    def test_only_verified_ing_inflection_loses_final_written_g(self):
        m=pipeline.Lexicon(fixtures.SEED)
        for surface,categories in [('drink',{'verb','verb_base'}),('drinking',{'verb','verb_ing'})]:
            m.add('fixture-drink','drink',surface,categories,{'source':'curated_seed','url':'https://example.org/drink'},approved=True)
        m.add('fixture-king','king','king',{'noun'},{'source':'curated_seed','url':'https://example.org/king'},approved=True)
        i.attach(m,[{'id':'tsv:1','surface':'drinkin'},{'id':'tsv:2','surface':'kin'},{'id':'tsv:3','surface':'drin'}])
        self.assertIn('verb_ing',m.members['fixture-drink','drinkin']);self.assertEqual('drink',m.forms['fixture-drink','drinkin']['lemma'])
        self.assertFalse(m.approved.get('kin'));self.assertFalse(m.approved.get('drin'));m.validate()

    def test_established_words_do_not_gain_speculative_informal_participle_flags(self):
        m=pipeline.Lexicon(fixtures.SEED)
        for surface,categories in [('rue',{'verb','verb_base'}),('ruing',{'verb','verb_ing'})]:
            m.add('fixture-rue','rue',surface,categories,{'source':'curated_seed','url':'https://example.org/rue'},approved=True)
        m.add('fixture-ruin','ruin','ruin',{'noun'},{'source':'curated_seed','url':'https://example.org/ruin'},approved=True)
        i.attach(m,[{'id':'tsv:1','surface':'ruin'},{'id':'tsv:2','surface':'smh'}],{'tsv:2'})
        self.assertNotIn(('fixture-rue','ruin'),m.forms)
        self.assertTrue(m.approved.get('smh'));m.validate()

    def test_direct_abbreviation_facts_do_not_invent_expansions_or_unattested_slugs(self):
        m=pipeline.Lexicon(fixtures.SEED)
        i.attach(m,[{'id':'tsv:1','surface':'smh'},{'id':'tsv:2','surface':'inventedabbr'}]);key='internet-abbreviation-smh'
        self.assertEqual({'abbreviation','register_informal'},m.members[key,'smh']);self.assertFalse(m.approved.get('inventedabbr'));m.validate()
        self.assertNotIn('expansion',m.evidence[key,'smh'][0])


if __name__=='__main__':unittest.main()
