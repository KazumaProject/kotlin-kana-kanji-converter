import unittest

import apostrophe_inputs as apostrophes
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class ApostropheInputTests(unittest.TestCase):
    def model(self):
        model=pipeline.Lexicon(fixtures.SEED)
        model.add('family','family',"family's",{'noun'},{'source':'esdb','url':'https://example.org/esdb'},approved=True)
        return model

    def test_only_exact_letter_sequence_with_recorded_apostrophe_positions(self):
        self.assertEqual('familys',apostrophes.input_key("family's"))
        for spelling in ['familys','family-s',"family's room","fam1ly's"]:
            self.assertIsNone(apostrophes.input_key(spelling))
        model=self.model();corrections=[];audit=[]
        apostrophes.attach(model,[dict(id='tsv:1',surface='familys',reading='familys',cost=700)],{"family's"},corrections,audit)
        self.assertEqual("family's",corrections[0]['target']);self.assertEqual('input_spelling_correction',corrections[0]['relation'])
        self.assertFalse(model.approved.get('familys'));self.assertFalse(audit[0]['rawSpellingAttestationClaimed'])

    def test_no_invented_genitive_unapproved_form_or_current_restriction(self):
        for state in ['not-recorded','unapproved','restricted']:
            model=pipeline.Lexicon(fixtures.SEED);corrections=[]
            if state!='not-recorded':model.add('family','family',"family's",{'noun'},{'source':'esdb','url':'https://example.org/esdb'},approved=state!='unapproved')
            apostrophes.attach(model,[dict(id='tsv:1',surface='familys',reading='familys')],{"family's"},corrections,[],{"family's"} if state=='restricted' else set())
            self.assertEqual([],corrections)

    def test_existing_readings_and_citations_remain_while_missing_letters_never_change(self):
        model=self.model();model.add('other','familys','familys',{'noun'},{'source':'curated_seed','url':'https://example.org/other'},approved=True)
        corrections=[]
        apostrophes.attach(model,[dict(id='tsv:1',surface='familys',reading='familys'),dict(id='tsv:2',surface='familys',reading='family'),
                                  dict(id='tsv:3',surface='famlys',reading='famlys')],{"family's"},corrections,[])
        self.assertEqual({'familys',"family's"},{r['target'] for r in corrections})
        self.assertTrue(all(r['id']=='tsv:1' for r in corrections));self.assertTrue(all(r['relation']=='input_spelling_candidates' for r in corrections))


if __name__=='__main__':unittest.main()
