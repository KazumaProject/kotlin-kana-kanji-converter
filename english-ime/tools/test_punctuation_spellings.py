import unittest
import punctuation_spellings as spellings
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class PunctuationTests(unittest.TestCase):
    def test_only_attested_same_key_candidates_preserve_raw_rows_and_ambiguity(self):
        model = pipeline.Lexicon(fixtures.SEED)
        proof = {'source': 'wiktionary', 'url': 'https://example.org/fixture', 'approved': True}
        for word in ['sign-in', 'call-in']:
            model.add('noun-' + word, word, word, {'noun'}, proof, approved=True)
        model.add('verb-call', 'call', 'call', {'verb'}, proof)
        model.add('verb-call', 'call', "callin'", {'verb', 'verb_ing'}, proof, approved=True)
        rows = [{'id': word, 'surface': word, 'reading': word, 'cost': 456} for word in ['signin', 'callin', 'singin', 'sign']]
        corrections = spellings.corrections_for(model, rows, set())
        self.assertEqual({'signin': ('sign-in',), 'callin': ('call-in', "callin'")},
                         pipeline.correction_targets(corrections, rows, model))
        self.assertEqual([], spellings.corrections_for(model, rows, {'signin', 'callin'}))
        bad = [dict(corrections[0], target='call-in')]
        with self.assertRaisesRegex(ValueError, 'Invalid or duplicate'):
            pipeline.correction_targets(bad, rows, model)
        model.validate()


if __name__ == '__main__':
    unittest.main()
