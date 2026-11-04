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


if __name__=='__main__':unittest.main()
