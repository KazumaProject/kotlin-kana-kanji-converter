import unittest
import reference_repairs as r,resolve_wiktionary as w
import lexicon_pipeline as p
import test_lexicon_pipeline as f


def entry(word,pos,sense,forms=()):return {'word':word,'pos':pos,'senses':[sense],'forms':list(forms)}


class ReferenceRepairTests(unittest.TestCase):
    def test_usage_commentary_is_not_a_second_lemma_and_never_supplies_inflection(self):
        rows=[(1,entry('luh','verb',{'tags':['alt-of','pronunciation-spelling'],'alt_of':[{'word':'love'},{'word':'representing African-American Vernacular English'}],'links':[['love','love#English']],'glosses':['Pronunciation spelling of love, representing African-American Vernacular English']}))]
        fixed,count=r.normalized(rows);self.assertEqual(1,count);self.assertEqual([{'word':'love'}],fixed[0][1]['senses'][0]['alt_of'])
        self.assertEqual(2,len(rows[0][1]['senses'][0]['alt_of']))
        m=p.Lexicon(f.SEED);m.add('fixture-love','love','love',{'verb','verb_base'},{'source':'curated_seed','url':'https://example.org/love'},approved=True)
        w.import_records(m,fixed,{'luh'},[],bootstrap_approved=True)
        key=next(iter(m.approved['luh']));self.assertEqual({'verb'},m.members[key,'luh']);m.validate()
        self.assertFalse(m.evidence[key,'luh'][0]['referenceRepair']['targetMorphologyInherited'])

    def test_two_real_targets_are_not_silently_collapsed(self):
        rows=[(1,entry('variant','noun',{'alt_of':[{'word':'color'},{'word':'colour'}],'links':[['color','color#English'],['colour','colour#English']]}))]
        fixed,count=r.normalized(rows);self.assertEqual(0,count);self.assertEqual(rows,fixed)

    def test_split_reference_needs_both_exact_english_link_and_literal_gloss(self):
        rows=[(1,entry('LARPing','verb',{'form_of':[{'word':'LAR','extra':'P — live action role-playing'}],'links':[['LARP','LARP#English']],'glosses':['present participle and gerund of LARP — live action role-playing']}))]
        fixed,count=r.normalized(rows);self.assertEqual(1,count);self.assertEqual('LARP',fixed[0][1]['senses'][0]['form_of'][0]['word'])
        rows[0][1]['senses'][0]['links']=[];self.assertEqual(0,r.normalized(rows)[1])

    def test_agent_noun_does_not_become_verb_or_inherit_inflections(self):
        m=p.Lexicon(f.SEED);m.add('fixture-unify','unify','unify',{'verb','verb_base'},{'source':'curated_seed','url':'https://example.org/unify'},approved=True)
        rows=[(1,entry('unifier','noun',{'tags':['agent','form-of'],'form_of':[{'word':'unify'}],'links':[['unify','unify#English']],'glosses':['Agent noun of unify; one who unifies.']}))]
        r.attach_direct(m,rows,{'unifier'},[]);key=next(iter(m.approved['unifier']));self.assertEqual({'noun'},m.members[key,'unifier']);self.assertEqual('unifier',m.forms[key,'unifier']['lemma']);m.validate()

    def test_source_attested_past_syncretism_without_inventing_bare_verb(self):
        m=p.Lexicon(f.SEED);rows=[(1,entry('five','num',{'glosses':['The number five.']})),(2,entry('fived','verb',{'tags':['form-of','past','participle'],'form_of':[{'word':'five'}],'links':[['five','five#English']],'glosses':['simple past and past participle of five']}))]
        r.attach_direct(m,rows,{'fived'},[]);key=next(iter(m.approved['fived']));self.assertEqual({'verb','verb_past','verb_past_participle'},m.members[key,'fived']);self.assertNotIn('verb_base',m.members[key,'five']);m.validate()

    def test_canonical_alternative_table_proves_adverb_without_adjective_guess(self):
        m=p.Lexicon(f.SEED);rows=[(1,entry('single-handedly','adv',{'glosses':['Alone; without assistance.']},[{'form':'singlehandedly','tags':['alternative']}])),(2,entry('singlehandedly','adj',{'tags':['alt-of'],'alt_of':[{'word':'single-handedly'}],'links':[['single-handedly','single-handedly#English']]}))]
        w.import_records(m,rows,{'singlehandedly'},[]);r.attach_direct(m,rows,{'singlehandedly'},[])
        self.assertTrue(m.approved['singlehandedly']);self.assertTrue(all(m.members[key,'singlehandedly']=={'adverb'} for key in m.approved['singlehandedly']));m.validate()


if __name__=='__main__':unittest.main()
