import copy,unittest
import yago_name_variants as y
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


def entity():
    return {'id':'yago:Fixture_Person','wikidataIds':['wd:Q123'],'englishWikipediaUrls':['https://en.wikipedia.org/wiki/Fixture'],
        'labels':[{'label':'Fíxture','language':'en','line':1}],
        'types':[{'type':'schema:Person','line':2}],'paths':{'schema:Person':{'schema:Person':[]}},'classPaths':{},
        'descriptions':[], 'matches':[{'label':'Fíxture','language':'en','matchingMode':'existing_ascii_diacritic_input','asciiAlias':'Fixture'}]}


class VariantTests(unittest.TestCase):
    def test_only_decomposable_latin_diacritics_and_no_letter_or_punctuation_guess(self):
        self.assertEqual('Beyonce',y.ascii_name('Beyoncé'))
        self.assertIsNone(y.ascii_name('東京'));self.assertIsNone(y.ascii_name('Søren'))
        self.assertEqual('Fixture-A',y.ascii_name('Fíxture-A'))
        self.assertEqual('Fixture',y.ascii_name('Fixture'))

    def test_existing_alias_keeps_source_lemma_and_no_invented_rows_or_morphology(self):
        model=pipeline.Lexicon(fixtures.SEED)
        y.attach(model,[{'id':'tsv:1','surface':'fixture'}],[entity()])
        key=next(iter(model.approved['fixture']))
        self.assertEqual('Fíxture',model.forms[key,'fixture']['lemma'])
        self.assertEqual({'noun','noun_proper','name_person'},model.members[key,'fixture'])
        self.assertFalse(model.approved.get('fixtures'));model.validate()
        proof=model.evidence[key,'fixture'][0];self.assertFalse(proof['preferredAsciiSpellingClaimed'])
        self.assertEqual('derived_existing_latin_diacritic_input_alias',proof['relation'])

    def test_generic_classes_do_not_become_names_and_fictional_scope_requires_description(self):
        record=entity();record['paths']={};record['classPaths']={'yago:Video_Game_Character':{'yago:Video_Game_Character':[]}}
        self.assertEqual(set(),y.categories(record))
        record['descriptions']=[{'label':'Pokémon species','language':'en'}]
        self.assertEqual({'noun','noun_proper','name_fictional'},y.categories(record))
        record['classPaths']={'schema:Person':{'schema:Person':[]}}
        self.assertEqual(set(),y.categories(record))

    def test_missing_identity_or_generic_instance_is_never_adopted(self):
        for change in ['id','scope','generic']:
            record=entity()
            if change=='id':record['wikidataIds']=[]
            elif change=='scope':record['englishWikipediaUrls']=[]
            else:record['id']+='_generic_instance'
            model=pipeline.Lexicon(fixtures.SEED);y.attach(model,[{'id':'tsv:1','surface':'fixture'}],[record])
            self.assertFalse(model.approved.get('fixture'))


if __name__=='__main__':unittest.main()
