import copy,unittest
import named_components as n
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


def entity():
    return {'id':'yago:Fixture_Place','wikidataIds':['wd:Q123'],'englishWikipediaUrls':['https://en.wikipedia.org/wiki/Fixture'],
        'labels':[{'label':'Phnom Penh','language':'en'}],'types':[{'type':'schema:Place'}],
        'paths':{'schema:Place':{'schema:Place':[]}},'classPaths':{},'descriptions':[],
        'matches':[{'label':'Phnom Penh','component':'Phnom','componentPosition':0,'matchingMode':'whole_whitespace_delimited_named_component','asciiAlias':None,'predicate':'rdfs:label','language':'en'}]}


class NamedComponentTests(unittest.TestCase):
    def test_contextual_component_keeps_full_name_proof_without_standalone_place_or_pos(self):
        model=pipeline.Lexicon(fixtures.SEED)
        n.attach(model,[{'id':'tsv:1','surface':'phnom'}],[entity()])
        key=next(key[0] for key in model.forms if key[1]=='phnom')
        self.assertFalse(model.approved.get('phnom'))
        self.assertEqual({'identifier_named_component'},model.members[key,'phnom'])
        self.assertTrue(model.evidence[key,'phnom'][0]['requiresFullNamedContext'])
        self.assertEqual('Phnom Penh',model.evidence[key,'phnom'][0]['nameEvidence']['label'])
        self.assertFalse(model.approved.get('phnoms'));self.assertFalse(model.approved.get('hnom'));model.validate()

    def test_no_substrings_camelcase_punctuation_or_lowercase_function_word(self):
        for label,token in [('PhnomPenh','Phnom'),('Phnom Penh','hnom'),('Phnom Penh,','Penh'),('City of Fixture','of')]:
            match={'label':label,'component':token,'componentPosition':0 if token!='of' else 1,'matchingMode':'whole_whitespace_delimited_named_component','asciiAlias':None}
            with self.assertRaises(ValueError):n.component(match)

    def test_alias_vandalism_and_known_misspellings_cannot_resurrect_invalid_inputs(self):
        record=entity();record['matches'][0]['predicate']='schema:alternateName'
        model=pipeline.Lexicon(fixtures.SEED);n.attach(model,[{'id':'tsv:1','surface':'phnom'}],[record])
        self.assertFalse(model.approved.get('phnom'))
        record=entity();n.attach(model,[{'id':'tsv:1','surface':'phnom'}],[record],{'phnom'})
        self.assertFalse(model.approved.get('phnom'))

    def test_generic_class_or_unverified_entity_cannot_support_components(self):
        record=entity();record['paths']={};record['classPaths']={'schema:Place':{'schema:Place':[]}}
        model=pipeline.Lexicon(fixtures.SEED);n.attach(model,[{'id':'tsv:1','surface':'phnom'}],[record]);self.assertFalse(model.approved.get('phnom'))
        record=entity();record['englishWikipediaUrls']=[]
        n.attach(model,[{'id':'tsv:1','surface':'phnom'}],[record]);self.assertFalse(model.approved.get('phnom'))


if __name__=='__main__':unittest.main()
