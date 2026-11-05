import unittest
import explicit_misspellings as typos
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class ExplicitMisspellingTests(unittest.TestCase):
    def test_ascii_input_match_retains_exact_source_label_and_reopenable_guards(self):
        source={'Typofixture':{'correctionfixture'}}
        row=dict(id='tsv:1',surface='typofixture',reading='typofixture',cost=42)
        pairs,proof=typos.ascii_input_pairs([row],source);audit=[]
        result=typos.exclusions(self.model(),[row],pairs,{},audit,proof)
        self.assertEqual(1,len(result));self.assertEqual('Typofixture',audit[0]['evidence']['listedSpelling'])
        self.assertTrue(audit[0]['evidence']['asciiInputCasefoldMatch']);self.assertNotIn('typofixture',source)
        modern={'typofixture':[dict(word='Typofixture',pos='noun',senses=[dict(glosses=['A modern noun.'])])]}
        self.assertEqual([],typos.exclusions(self.model(),[row],pairs,modern,[],proof))

    def test_casefold_does_not_infer_manual_aliases_or_changed_input_spellings(self):
        for change in [dict(id='manual:1'),dict(reading='other'),dict(surface='Typofixture')]:
            row=dict(id='tsv:1',surface='typofixture',reading='typofixture',cost=42);row.update(change)
            pairs,proof=typos.ascii_input_pairs([row],{'TYPOFIXTURE':{'correctionfixture'}})
            self.assertFalse(proof);self.assertNotIn(row['surface'],pairs)

    def model(self):
        model = pipeline.Lexicon(fixtures.SEED)
        model.add('verified-correction', 'correctionfixture', 'correctionfixture', {'noun'},
            {'source': 'wiktionary', 'url': 'https://example.org/correction', 'approved': True}, approved=True)
        return model

    def test_explicit_typo_and_verified_correction_record_a_reopenable_machine_decision(self):
        model = self.model(); audit = []
        row = {'id': 'tsv:1', 'surface': 'typo-fixture', 'reading': 'typofixture', 'cost': 42}
        result = typos.exclusions(model, [row], {'typo-fixture': {'correctionfixture'}}, {}, audit)
        self.assertEqual(1, len(result))
        self.assertEqual('malformed', result[0]['reason'])
        self.assertEqual(42, result[0]['cost'])
        self.assertEqual('source_label_exclusion', audit[0]['reason'])
        self.assertEqual(['correctionfixture'], audit[0]['evidence']['independentlyVerifiedCorrections'])

    def test_independent_name_modern_sense_or_extraction_error_blocks_exclusion(self):
        for kind in ['name', 'sense', 'error', 'empty']:
            with self.subTest(kind=kind):
                model = self.model(); exact = {}
                if kind == 'name':
                    model.add('person', 'Typofixture', 'Typofixture', {'noun','noun_proper','name_person'},
                        {'source': 'census_surname', 'url': 'https://example.org/name'}, approved=True)
                elif kind == 'sense': exact = {'typofixture': [{'word': 'typofixture', 'pos': 'noun', 'senses': [{'glosses': ['A modern noun.']}]}]}
                elif kind == 'error': exact = {'typofixture': [{'word': 'typofixture', 'pos': 'noun', 'senses': [{'tags': ['misspelling','no-gloss']}]}]}
                else: exact = {'typofixture': [{'word': 'typofixture', 'pos': 'noun', 'senses': []}]}
                self.assertEqual([], typos.exclusions(model, [{'id': 'tsv:1', 'surface': 'typofixture'}],
                    {'typofixture': {'correctionfixture'}}, exact, []))

    def test_unlisted_strings_and_unverified_corrections_are_not_rejected(self):
        self.assertEqual([], typos.exclusions(self.model(), [{'id': 'tsv:1', 'surface': 'unlisted'}], {}, {}, []))
        self.assertEqual([], typos.exclusions(self.model(), [{'id': 'tsv:1', 'surface': 'typo'}], {'typo': {'unknown'}}, {}, []))


if __name__ == '__main__': unittest.main()
