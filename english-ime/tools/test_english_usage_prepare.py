from collections import Counter, defaultdict
import unittest

import english_usage_prepare as usage


class UsagePreparationTests(unittest.TestCase):
    def test_foreign_quotes_names_identifiers_and_possessives_remain_unapproved_leads(self):
        records, heads, counts = defaultdict(list), [], Counter()
        entry = dict(lang_code='en', word='unrelated', pos='verb', senses=[dict(examples=[
            dict(text='Nicki Minaj met Radiohead’s singer at example.test.', type='quotation', ref='2000, Fixture')])])
        usage.witnesses(1, entry, {'minaj', 'radiohead', 'example'}, defaultdict(set, minaj={'nicki minaj'}), records, heads, counts)
        self.assertEqual(['nicki minaj'], records['minaj'][0]['inKnownFullName'])
        self.assertTrue(records['radiohead'][0]['possessive'])
        self.assertTrue(records['example'][0]['embeddedInIdentifier'])
        self.assertNotIn('approved', records['radiohead'][0])
        self.assertNotIn('categories', records['radiohead'][0])
        self.assertEqual(1, counts['englishExamples'])
        entry['lang_code'] = 'fr'
        usage.witnesses(2, entry, {'minaj'}, defaultdict(set), records, heads, counts)
        self.assertEqual(1, len(records['minaj']))

    def test_per_form_cap_does_not_turn_quotes_into_frequency_evidence(self):
        records, heads, counts = defaultdict(list), [], Counter()
        entry = dict(lang_code='en', word='fixture', pos='noun', senses=[dict(examples=[dict(text='Fixture ' * 30)])])
        usage.witnesses(1, entry, {'fixture'}, defaultdict(set), records, heads, counts)
        self.assertEqual(24, len(records['fixture']))
        self.assertEqual('fixture', heads[0]['word'])


if __name__ == '__main__':
    unittest.main()
