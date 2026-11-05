import copy
import unittest

import lexicon_pipeline as pipeline
import qualified_name_fields as qualified
import test_lexicon_pipeline as fixtures


def entity():
    return dict(id='yago:Person_Fixture', wikidataIds=['wd:Q123'],
        englishWikipediaUrls=['https://en.wikipedia.org/wiki/Person_Fixture'],
        types=[dict(type='schema:Person', line=1)], paths={'schema:Person': {'schema:Person': []}},
        labels=[dict(label='Person Fixture', language='en', line=2)],
        nameFields=[dict(relation='schema:familyName', literal='Fixture_Q123', line=3)])


class QualifiedNameTests(unittest.TestCase):
    def test_only_recognized_single_name_qualifiers_are_considered(self):
        self.assertEqual('Fixture', qualified.stem('Fixture_Q123'))
        self.assertEqual('Fixture', qualified.stem('Fixture_surname'))
        for value in ['Fixture', 'Fixture_Q0', 'Fixture_Q0123', 'Fixture_Q123_more',
                      'Fixture_Family', 'Degli_Innocenti', 'Geun_Ryeong', 'Famille_De_Reviers']:
            self.assertIsNone(qualified.stem(value))

    def test_explicit_field_and_owner_spelling_preserve_case_and_name_identity(self):
        record = entity()
        record['labels'][0]['label'] = 'Person fIxture'
        model = pipeline.Lexicon(fixtures.SEED)
        qualified.attach(model, [record])
        key = next(iter(model.approved['fIxture']))
        self.assertEqual({'noun', 'noun_proper', 'name_person'}, model.members[key, 'fIxture'])
        self.assertFalse(model.approved.get('Fixture'))
        self.assertFalse(model.approved.get('fIxtures'))
        proof = model.evidence[key, 'fIxture'][0]
        self.assertEqual('Fixture_Q123', proof['nameEvidence']['literal'])
        self.assertFalse(proof['preferredCaseClaimed'])
        model.validate()

    def test_no_name_position_inference_or_substring_hyphen_apostrophe_splitting(self):
        for label in ['Person Other', 'Person Fixtures', 'Person PreFixture', 'Person Fixture-Part',
                      "Person Fixture's", 'Person Fixture_Part']:
            self.assertEqual([], qualified.spelling_witnesses('Fixture_Q123', [dict(label=label, language='en')]))

    def test_foreign_or_shared_labels_alone_do_not_decode_identifier_spelling(self):
        for language in ['fr', 'mul', None]:
            self.assertEqual([], qualified.spelling_witnesses('Fixture_Q123', [dict(label='Person Fixture', language=language)]))
        self.assertEqual('Fixture', qualified.spelling_witnesses('Fixture_surname', [dict(label='Person Fixture', language='en-gb')])[0]['spelling'])

    def test_person_identity_scope_and_field_are_required(self):
        for change in ['generic', 'wikidata', 'wikipedia', 'type', 'unrelated_path', 'field']:
            record = entity()
            if change == 'generic': record['id'] += '_generic_instance'
            elif change == 'wikidata': record['wikidataIds'] = []
            elif change == 'wikipedia': record['englishWikipediaUrls'] = []
            elif change == 'type': record['paths'] = {'schema:Book': {'schema:Book': []}}
            elif change == 'unrelated_path': record['paths'] = {'schema:Book': {'schema:Person': []}}
            elif change == 'field': record['nameFields'][0]['relation'] = 'schema:alternateName'
            model = pipeline.Lexicon(fixtures.SEED)
            qualified.attach(model, [record])
            self.assertFalse(model.approved.get('Fixture'), change)

    def test_shared_name_reuses_lexical_identity_and_keeps_independent_witnesses(self):
        first = entity()
        second = copy.deepcopy(first)
        second['id'] = 'yago:Other_Fixture'
        second['wikidataIds'] = ['wd:Q456']
        model = pipeline.Lexicon(fixtures.SEED)
        qualified.attach(model, [first, second])
        keys = model.approved['Fixture']
        self.assertEqual(1, len(keys))
        self.assertEqual(2, len(model.evidence[next(iter(keys)), 'Fixture']))

    def test_different_spelling_owner_is_not_used_to_corrobate_id(self):
        record = entity()
        record['nameFields'][0]['literal'] = 'Effi_Q123'
        record['labels'][0]['label'] = 'Effie Eitam'
        model = pipeline.Lexicon(fixtures.SEED)
        qualified.attach(model, [record])
        self.assertFalse(model.approved.get('Effi'))

    def test_optional_latin_alias_keeps_actual_name_and_only_existing_input_alias(self):
        record=entity()
        record['nameFields'][0]['literal']='Fíxture_Q123'
        record['labels'][0]['label']='Person Fíxture'
        model=pipeline.Lexicon(fixtures.SEED)
        qualified.attach(model,[record],[dict(surface='fixture')],ascii_input_aliases=True)
        key=next(iter(model.approved['Fixture']))
        self.assertEqual('Fíxture',model.forms[key,'Fixture']['lemma'])
        self.assertFalse(model.evidence[key,'Fixture'][0]['preferredAsciiSpellingClaimed'])
        model.validate()
        model=pipeline.Lexicon(fixtures.SEED)
        qualified.attach(model,[record],[],ascii_input_aliases=True)
        self.assertTrue(model.approved.get('Fíxture'))
        self.assertFalse(model.approved.get('Fixture'))
        for value in ['東京_Q123','Søren_Q123','Degli_Innocenti','Geun_Ryeong']:
            self.assertIsNone(qualified.candidate_stem(value,True))

    def test_optional_literal_field_still_needs_english_owner_spelling(self):
        self.assertEqual('Fíxture',qualified.candidate_stem('Fíxture',True))
        self.assertEqual([],qualified.spelling_witnesses('Fíxture',[dict(label='Person Other',language='en')],True))


if __name__ == '__main__':
    unittest.main()
