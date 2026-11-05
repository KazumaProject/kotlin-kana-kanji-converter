import unittest
import expressive_orthography as e
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class ExpressiveTests(unittest.TestCase):
    def test_only_narrow_letter_run_changes_not_typo_repair_or_arbitrary_edits(self):
        self.assertCountEqual(['loong','long'],e.bases('loooong'))
        self.assertEqual(['sh','shh'],e.bases('shhhh'))
        for word in ['commmit','foo-bar','COOOOL','sooo1','hahaha','thee']:
            self.assertEqual([],e.bases(word))

    def test_derived_verb_keeps_identity_without_base_or_tense_flags(self):
        model=pipeline.Lexicon(fixtures.SEED)
        model.add('fixture-love','love','love',{'verb','verb_base'},{'source':'curated_seed','url':'https://example.org/love'},approved=True)
        e.attach(model,[{'id':'tsv:1','surface':'loooove'}],{'tsv:1'})
        self.assertEqual({'verb','register_informal','orthography_expressive_lengthening'},model.members['fixture-love','loooove'])
        self.assertFalse(model.evidence['fixture-love','loooove'][0]['individuallyAttestedVariantClaimed']);model.validate()

    def test_multiple_roots_retained_and_names_identifiers_or_excluded_rows_not_stretched(self):
        model=pipeline.Lexicon(fixtures.SEED)
        for key,word in [('one','loser'),('two','looser')]:
            model.add(key,word,word,{'noun'},{'source':'curated_seed','url':'https://example.org/'+key},approved=True)
        model.add('name','Google','Google',{'noun','noun_proper'},{'source':'curated_seed','url':'https://example.org/name'},approved=True)
        e.attach(model,[{'id':'tsv:1','surface':'looooser'},{'id':'tsv:2','surface':'gooooogle'},{'id':'tsv:3','surface':'loooserrrr'}],{'tsv:1','tsv:2'})
        self.assertEqual({'one','two'},model.approved['looooser'])
        self.assertFalse(model.approved.get('gooooogle'));self.assertFalse(model.approved.get('loooserrrr'));model.validate()


if __name__=='__main__':unittest.main()
