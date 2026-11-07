import unittest
import initial_capitals as c
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class InitialCapitalsTests(unittest.TestCase):
    def test_apostrophe_case_keeps_verified_ordinary_roles_without_promoting_named_references(self):
        model=pipeline.Lexicon(fixtures.SEED)
        model.add('fixture-address',"ma'am","ma'am",{'noun'},{'source':'wiktionary','url':'https://example.org/address'},approved=True)
        model.add('fixture-loan','fixture','fixture',{'noun'},{'source':'reviewed_wikipedia','url':'https://example.org/ordinary'},approved=True)
        model.add('fixture-name','named','named',{'noun','noun_proper'},{'source':'reviewed_wikipedia','url':'https://example.org/name'},approved=True)
        rows=[dict(id='raw:'+str(i),surface=s) for i,s in enumerate(["Ma'am",'Fixture','Named'])]
        c.attach(model,rows,{r['id'] for r in rows})
        self.assertEqual({'noun','orthography_initial_capital'},model.members['fixture-address',"Ma'am"])
        self.assertTrue(model.approved.get('Fixture'));self.assertFalse(model.approved.get('Named'))

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
