import unittest
import roman_numerals as roman
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class RomanNumeralTests(unittest.TestCase):
    def test_normative_boundary_and_subtractive_representations(self):
        self.assertEqual('i',roman.render(1));self.assertEqual('mmmcmxcix',roman.render(3999))
        self.assertEqual('xlviii',roman.render(48));self.assertEqual('cmxlix',roman.render(949))
        self.assertEqual(3999,len(roman.VALUES));self.assertNotIn('iiii',roman.VALUES);self.assertNotIn('ic',roman.VALUES)
        for number in [0,4000]:
            with self.assertRaises(ValueError):roman.render(number)

    def test_english_homograph_and_numeric_value_never_pool_grammar_flags(self):
        model=pipeline.Lexicon(fixtures.SEED)
        model.add('english-mix','mix','mix',{'verb','verb_base'},{'source':'wiktionary','url':'https://example.org/mix'},approved=True)
        rows=[{'id':'tsv:1','surface':'mix'},{'id':'tsv:2','surface':'XLVIII'},{'id':'tsv:3','surface':'Mix'},{'id':'tsv:4','surface':'iiii'}]
        self.assertEqual({'tsv:1','tsv:2'},roman.attach(model,rows))
        self.assertEqual({'numeral','numeral_roman'},model.members['roman-standard-1009','mix'])
        self.assertEqual({'verb','verb_base'},model.members['english-mix','mix'])
        self.assertFalse(model.approved.get('Mix'));self.assertFalse(model.approved.get('iiii'))
        model.validate()


if __name__=='__main__':unittest.main()
