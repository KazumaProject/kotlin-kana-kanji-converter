import unittest
import human_typo_lists as lists
import explicit_misspellings as typos
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class HumanTypoListTests(unittest.TestCase):
    def test_annotated_variants_unlinked_false_positives_and_queries_are_not_exclusions(self):
        text='* {{search link|"typpofixture"|typpofixture|ns0}} ([[correctionfixture]])\n* variantfixture (correctionfixture) (acceptable variant)\n* {{search link|variantfixture}} (correctionfixture) (British variant)\n* u (you) (false positives)\n* {{search link|bad.*query}} (correctionfixture)\n'
        rows=list(lists.pairs_in(text));self.assertEqual(1,len(rows))
        self.assertEqual(('typpofixture',['correctionfixture']),rows[0][:2])

    def test_space_insertion_requires_every_correction_word_and_preserves_original_data(self):
        model=pipeline.Lexicon(fixtures.SEED);row={'id':'tsv:1','reading':'ofthefixture','surface':'ofthefixture','cost':123}
        proof={'source':'wikipedia_misspelling_list','url':'https://example.org/pinned-typo-page','revision':42}
        result=typos.exclusions(model,[row],{'ofthefixture':{'of the'}},{},[],provenance={'ofthefixture':proof},allow_word_sequences=True)
        self.assertEqual(1,len(result));self.assertEqual(123,result[0]['cost']);self.assertEqual(proof['url'],result[0]['evidence'])
        self.assertEqual([],typos.exclusions(model,[row],{'ofthefixture':{'unknown correction'}},{},[],provenance={'ofthefixture':proof},allow_word_sequences=True))


if __name__=='__main__':unittest.main()
