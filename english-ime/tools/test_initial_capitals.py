import unittest
import initial_capitals as c
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class InitialCapitalsTests(unittest.TestCase):
    def test_same_ordinary_identity_without_invented_name_or_base_flags(self):
        model=pipeline.Lexicon(fixtures.SEED)
        model.add('fixture-compose','compose','compose',{'verb','verb_base'},{'source':'curated_seed','url':'https://example.org/compose'},approved=True)
        c.attach(model,[{'id':'tsv:1','surface':'Compose'}],{'tsv:1'})
        self.assertEqual({'verb','orthography_initial_capital'},model.members['fixture-compose','Compose'])
        self.assertEqual('compose',model.forms['fixture-compose','Compose']['lemma']);model.validate()
        self.assertFalse(model.evidence['fixture-compose','Compose'][0]['preferredNameCaseClaimed'])

    def test_names_mixed_case_acronyms_and_unresolved_roots_are_not_normalized(self):
        model=pipeline.Lexicon(fixtures.SEED)
        model.add('fixture-name','fixture','fixture',{'noun','noun_proper'},{'source':'curated_seed','url':'https://example.org/name'},approved=True)
        rows=[{'id':'tsv:'+str(i),'surface':s} for i,s in enumerate(['Fixture','Unknown','COMPOSE','ReGexp'])]
        c.attach(model,rows,{r['id'] for r in rows})
        for row in rows:self.assertFalse(model.approved.get(row['surface']))


if __name__=='__main__':unittest.main()
