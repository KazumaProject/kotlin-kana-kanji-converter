import unittest
import reference_repairs as r,resolve_wiktionary as w
import lexicon_pipeline as p
import test_lexicon_pipeline as f


def entry(word,pos,sense,forms=()):return {'word':word,'pos':pos,'senses':[sense],'forms':list(forms)}


class ReferenceRepairTests(unittest.TestCase):
    def test_proper_variant_retains_own_unrestricted_head_without_inheriting_target_sense(self):
        source=entry('Fixtureworld','name',{'tags':['alt-of'],'alt_of':[{'word':'Fixture World'}],
            'glosses':['Alternative spelling of Fixture World.'],'categories':['English proper nouns']})
        source['head_templates']=[{'name':'en-proper noun','args':{}}]
        target=entry('Fixture World','noun',{'tags':['derogatory'],'glosses':['A metaphorical place.']})
        m=p.Lexicon(f.SEED);r.attach_direct(m,[(1,source),(2,target)],{'Fixtureworld'},[])
        key=next(iter(m.approved['Fixtureworld']));self.assertEqual({'noun','noun_proper'},m.members[key,'Fixtureworld'])
        self.assertFalse(m.approved.get('Fixture World'));m.validate()
        for change in [dict(head_templates=[]),dict(senses=[dict(source['senses'][0],tags=['alt-of','obsolete'])]),
                       dict(senses=[dict(source['senses'][0],categories=['English nouns'])]),
                       dict(senses=[dict(source['senses'][0],categories=['English proper nouns','English nouns'])])]:
            model=p.Lexicon(f.SEED);r.attach_direct(model,[(1,dict(source,**change))],{'Fixtureworld'},[])
            self.assertFalse(model.approved.get('Fixtureworld'))

    def test_bare_link_needs_an_independent_same_role_english_head_before_comment_repair(self):
        variant=entry('seabass','noun',{'alt_of':[{'word':'sea bass'},{'word':'used especially in compound terms'}],
            'links':[['sea bass','sea bass']],'glosses':['Alternative form of sea bass, used especially in compound terms.']})
        self.assertEqual(0,r.normalized([(1,variant)])[1])
        fixed,count=r.normalized([(1,variant),(2,entry('sea bass','noun',{'glosses':['A fish.']}))])
        self.assertEqual(1,count)
        self.assertEqual([{'word':'sea bass'}],fixed[0][1]['senses'][0]['alt_of'])
        self.assertEqual({'sea bass':[2]},fixed[0][1]['senses'][0]['_referenceRepair']['bareLinkEnglishHeadEntries'])
        self.assertEqual(0,r.normalized([(1,variant),(2,entry('sea bass','adj',{'glosses':['A fixture.']}))])[1])

    def test_inconsistent_extracted_pos_needs_agreeing_english_head_and_unique_category(self):
        source=entry('variant','noun',{'tags':['alt-of'],'alt_of':[{'word':'good'}],'categories':['English adjectives'],'links':[['good','good#English']]})
        source['head_templates']=[{'name':'en-adj','args':{}}]
        fixed,count=r.normalized([(42,source)])
        self.assertEqual('adj',fixed[0][1]['pos']);self.assertEqual(1,count)
        self.assertEqual('noun',source['pos'])
        proof=w.provenance(42,fixed[0][1],fixed[0][1]['senses'][0],1)
        self.assertEqual('noun',proof['headRoleRepair']['originalPos'])
        source['senses'][0]['categories'].append('English nouns')
        self.assertEqual('noun',r.normalized([(42,source)])[0][0][1]['pos'])
        source['senses'][0]['categories']=['English adjectives'];source['head_templates']=[]
        self.assertEqual('noun',r.normalized([(42,source)])[0][0][1]['pos'])

    def test_pronunciation_spelling_uses_own_head_and_verified_phrase_components(self):
        source=entry('alotta','adj',{'tags':['alt-of','pronunciation-spelling'],'alt_of':[{'word':'a lot'}],
            'glosses':['Pronunciation spelling of a lot.'],'links':[['a','a#English'],['lot','lot#English']]})
        source['head_templates']=[{'name':'en-adj','args':{}}]
        m=p.Lexicon(f.SEED)
        r.attach_direct(m,[(42,source)],{'alotta'},[]);self.assertFalse(m.approved.get('alotta'))
        m.add('fixture-lot','lot','lot',{'noun'},{'source':'curated_seed','url':'https://example.org/lot'},approved=True)
        r.attach_direct(m,[(42,source)],{'alotta'},[])
        key=next(iter(m.approved['alotta']));self.assertEqual({'adjective'},m.members[key,'alotta'])
        self.assertFalse(m.approved.get('a lot'));m.validate()

    def test_new_independent_literal_reading_retains_all_old_name_candidates(self):
        m=p.Lexicon(f.SEED);proof={'source':'curated_seed','url':'https://example.org/fixture'}
        m.add('fixture-word','fixture','fixture',{'adjective'},proof,approved=True)
        m.add('fixture-name','Fixture','Fixture',{'noun','noun_proper'},proof,approved=True)
        rows=[dict(id='tsv:1',reading='fixture',surface='fixture',cost=700)]
        corrections=[dict(id='tsv:1',source='fixture',target='Fixture',relation='case_correction',evidence=proof['url'])]
        self.assertEqual(1,r.retain_original_readings(m,rows,corrections))
        self.assertEqual(('Fixture','fixture'),p.correction_targets(corrections,rows,m)['tsv:1'])
        self.assertEqual(0,r.retain_original_readings(m,rows,corrections))
        with self.assertRaises(ValueError):p.correction_targets([corrections[-1]],rows,m)

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

    def test_abbreviation_keeps_own_declared_role_without_expansion_head(self):
        m=p.Lexicon(f.SEED)
        row=entry('FIX','noun',{'tags':['abbreviation','alt-of','initialism'],'alt_of':[{'word':'fixture phrase'}],'glosses':['Initialism of fixture phrase.']})
        row['head_templates']=[{'name':'en-noun','args':{}}]
        r.attach_direct(m,[(1,row)],{'FIX'},[])
        key=next(iter(m.approved['FIX']))
        self.assertEqual({'noun','abbreviation'},m.members[key,'FIX'])
        self.assertEqual('FIX',m.forms[key,'FIX']['lemma'])
        self.assertFalse(m.approved.get('fixture phrase'));m.validate()

    def test_missing_or_conflicting_head_template_cannot_supply_abbreviation_pos(self):
        for head in [[],[{'name':'en-adj','args':{}}]]:
            m=p.Lexicon(f.SEED)
            row=entry('FIX','noun',{'tags':['abbreviation','alt-of'],'alt_of':[{'word':'fixture'}],'glosses':['Abbreviation of fixture.']});row['head_templates']=head
            r.attach_direct(m,[(1,row)],{'FIX'},[])
            self.assertFalse(m.approved.get('FIX'))

    def test_symbol_expansion_does_not_turn_symbol_into_noun_or_name(self):
        m=p.Lexicon(f.SEED)
        row=entry('fsym','symbol',{'tags':['alt-of','symbol'],'alt_of':[{'word':'fixture units ago'}],'glosses':['Symbol for fixture units ago.']});row['head_templates']=[{'name':'head','args':{'1':'en','2':'symbol'}}]
        r.attach_direct(m,[(1,row)],{'fsym'},[]);key=next(iter(m.approved['fsym']))
        self.assertEqual({'symbol'},m.members[key,'fsym']);m.validate()

    def test_plain_link_needs_independently_approved_english_verb_for_agent_noun(self):
        row=entry('unifier','noun',{'tags':['agent','form-of'],'form_of':[{'word':'unify'}],'links':[['unify','unify']],'glosses':['Agent noun of unify; one who unifies.']})
        m=p.Lexicon(f.SEED);r.attach_direct(m,[(1,row)],{'unifier'},[]);self.assertFalse(m.approved.get('unifier'))
        m.add('fixture-unify','unify','unify',{'verb','verb_base'},{'source':'curated_seed','url':'https://example.org/unify'},approved=True)
        r.attach_direct(m,[(1,row)],{'unifier'},[]);key=next(iter(m.approved['unifier']))
        self.assertEqual({'noun'},m.members[key,'unifier']);m.validate()

    def test_alternative_table_cannot_override_explicit_misspelling_label(self):
        m=p.Lexicon(f.SEED);pending=[]
        records=[(1,entry('fixture','noun',{'glosses':['A fixture.']},[{'form':'fixturre','tags':['alternative']}])) ,
            (2,entry('fixturre','noun',{'tags':['alt-of','misspelling'],'alt_of':[{'word':'fixture'}],'glosses':['Misspelling of fixture.']}))]
        w.import_records(m,records,{'fixture','fixturre'},pending)
        r.attach_direct(m,records,{'fixturre'},pending)
        self.assertFalse(m.approved.get('fixturre'))
        self.assertTrue(any(x.get('reason')=='canonical_alternative_table_conflicts_with_explicit_restriction' for x in pending))


if __name__=='__main__':unittest.main()
