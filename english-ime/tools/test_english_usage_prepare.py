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

    def test_quote_limit_is_applied_after_filtering_components_and_identifiers(self):
        records, heads, counts = defaultdict(list), [], Counter()
        entry = dict(lang_code='en', word='unrelated', senses=[dict(examples=[
            dict(text='Fixture Group followed example.test.', type='quotation', ref='2000, Fixture'),
            dict(text='The band Fixture performed', type='quotation', ref='2001, Fixture'),
            dict(text='The band Fixture toured', type='example'),
            dict(text='The band Fixture won', type='quotation', ref='2002, Fixture')])])
        usage.witnesses(1, entry, {'fixture', 'example'}, defaultdict(set, fixture={'fixture group'}), records, heads, counts,
            max_per_form=1, identified_standalone_only=True)
        self.assertEqual(1, len(records['fixture']))
        self.assertEqual('The band ', records['fixture'][0]['contextBefore'])
        self.assertFalse(records['example'])
        self.assertEqual(3, counts['englishQuotations'])


if __name__ == '__main__':
    unittest.main()
