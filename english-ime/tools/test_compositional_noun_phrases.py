import unittest
import compositional_noun_phrases as p
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


def model():
    m=pipeline.Lexicon(fixtures.SEED)
    for word in ['wire','number','relay','yarn','build','three','phase']:
        m.add('fixture-'+word,word,word,{'noun'}|({'numeral'} if word=='three' else set()),{'source':'curated_seed','url':'https://example.org/'+word},approved=True)
    return m


class PhraseTests(unittest.TestCase):
    def test_existing_noun_compound_has_constituents_and_no_fixed_expression_or_number_guess(self):
        m=model();row={'id':'manual:1','reading':'wire number','surface':'wire number','cost':12000}
        p.attach(m,[row],{'manual:1'},set(),{('wire number','wire number',12000):42})
        key=next(iter(m.approved['wire number']));self.assertEqual({'noun','phrase_noun_compositional'},m.members[key,'wire number'])
        self.assertFalse(m.evidence[key,'wire number'][0]['wholePhraseAttestedInExternalLexiconClaimed']);m.validate()

    def test_commands_numbers_missing_words_and_unprovided_new_phrases_are_rejected(self):
        for surface in ['yarn build','three phase','unknown relay','wire relay']:
            m=model();row={'id':'manual:1','reading':surface,'surface':surface,'cost':12000}
            literals={} if surface=='wire relay' else {(surface,surface,12000):42}
            p.attach(m,[row],{'manual:1'},{'yarn'},literals);self.assertFalse(m.approved.get(surface))

    def test_title_case_preserves_original_words_and_canonical_noun_phrase_identity(self):
        m=model();row=dict(id='manual:1',surface='Wire Number',reading='wire number',cost=12000)
        literals={('wire number','Wire Number',12000):42}
        p.attach(m,[row],{row['id']},set(),literals);self.assertFalse(m.approved.get('Wire Number'))
        review=dict(row,analysis=['wire','number'],reviewer='implementation_agent',rationale='Checked existing electrical label and its independent noun constituents.')
        p.attach(m,[row],{row['id']},set(),literals,[review])
        key=next(iter(m.approved['Wire Number']))
        self.assertEqual('wire number',m.forms[key,'Wire Number']['lemma'])
        self.assertNotIn('noun_proper',m.members[key,'Wire Number'])
        m.validate()
        row['surface']='WireNumber';p.attach(m,[row],{row['id']},set(),{('wire number','WireNumber',12000):42})
        self.assertFalse(m.approved.get('WireNumber'))

    def test_compound_modifier_requires_explicit_row_review_and_independent_adjective(self):
        m=model();m.add('fixture-fast','fast-acting','fast-acting',{'adjective'},
            dict(source='wiktionary',url='https://example.org/fast'),approved=True)
        row=dict(id='manual:1',surface='fast acting relay',reading='fast acting relay',cost=9000)
        literal={(row['reading'],row['surface'],row['cost']):42}
        p.attach(m,[row],{row['id']},{'fast'},literal);self.assertFalse(m.approved.get(row['surface']))
        review=dict(row,analysis=['fast-acting','relay'],reviewer='implementation_agent',rationale='Explicit compound adjective and noun-head analysis of the original spaced manual label.')
        p.attach(m,[row],{row['id']},{'fast'},literal,[review]);self.assertTrue(m.approved[row['surface']])
        for changed in [dict(cost=1),dict(analysis=['fast','relay']),dict(analysis=['unknown','relay'])]:
            with self.assertRaises(ValueError):p.attach(m,[row],{row['id']},{'fast'},literal,[dict(review,**changed)])


if __name__=='__main__':unittest.main()
