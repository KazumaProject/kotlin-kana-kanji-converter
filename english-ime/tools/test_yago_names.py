import copy
import unittest
import yago_names as yago
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


def entity():
    return {'id':'yago:Fixture_Software','wikidataIds':['wd:Q123'],
        'englishWikipediaUrls':['https://en.wikipedia.org/wiki/Fixture_Software'],
        'labels':[{'label':'Fixture Software','language':'en','line':1}],
        'types':[{'type':'schema:Book','line':2}],
        'paths':{'schema:Book':{'schema:Book':[]}},
        'matches':[{'label':'Fixture Software','language':'en','predicate':'rdfs:label','line':1}]}


class YagoNameTests(unittest.TestCase):
    def test_turtle_literals_preserve_unicode_and_escaped_backslashes(self):
        self.assertEqual(('Beyoncé','en'), yago.literal('"Beyonc\\u00e9"@en'))
        self.assertEqual(('A\\u0042','en'), yago.literal('"A\\\\u0042"@en'))
        self.assertEqual(('A😀','en-gb'), yago.literal('"A\\U0001f600"@en-gb'))
        self.assertIsNone(yago.literal('"unsafe\\tfield"@en'))
        self.assertIsNone(yago.literal('"foreign"^^xsd:string'))
        with self.assertRaises(ValueError): yago.literal('"bad\\uD800"@en')
        self.assertTrue(yago.name_language('en-gb'))
        self.assertTrue(yago.name_language('mul'))
        self.assertFalse(yago.name_language('fr'))

    def test_type_paths_terminate_on_cycles_and_do_not_infer_unrelated_named_types(self):
        parents={'yago:Program':[('schema:Book',9),('yago:Loop',8)],'yago:Loop':[('yago:Program',7)]}
        self.assertEqual({'schema:Book'}, set(yago.path_to_root('yago:Program',parents)))
        self.assertEqual([{'child':'yago:Program','parent':'schema:Book','line':9}],yago.path_to_root('yago:Program',parents)['schema:Book'])
        self.assertEqual({}, yago.path_to_root('schema:BioChemEntity',parents))

    def test_specific_work_keeps_manual_alias_and_independent_identity_without_inflections(self):
        model=pipeline.Lexicon(fixtures.SEED)
        yago.attach(model,[{'id':'manual:1','surface':'FixtureSoftware'},{'id':'tsv:1','surface':'fixturesoftware'}],[entity()])
        key=next(iter(model.approved['FixtureSoftware']))
        self.assertEqual('Fixture Software',model.forms[key,'FixtureSoftware']['lemma'])
        self.assertEqual({'noun','noun_proper','name_work'},model.members[key,'FixtureSoftware'])
        self.assertFalse(model.approved.get('fixturesoftware'))
        self.assertFalse(model.approved.get('FixtureSoftwares'))
        model.validate()

    def test_broad_creative_work_concepts_are_not_proper_names_and_formats_do_not_gain_pos(self):
        model=pipeline.Lexicon(fixtures.SEED)
        concept=entity();concept['paths']={'yago:Higher_order_function':{'schema:CreativeWork':[]}}
        yago.attach(model,[],[concept]);self.assertFalse(model.approved.get('Fixture Software'))
        form=entity();form['paths']={'yago:File_Format_Family':{'yago:File_Format_Family':[]}}
        yago.attach(model,[],[form]);key=next(iter(model.approved['Fixture Software']))
        self.assertEqual({'identifier_data_format','domain_technology'},model.members[key,'Fixture Software'])
        model.validate()

    def test_generic_instances_missing_id_scope_and_unproved_type_are_never_adopted(self):
        for kind in ['generic','id','scope','type']:
            with self.subTest(kind=kind):
                record=entity()
                if kind=='generic':record['id']='yago:Fixture_Software_generic_instance'
                elif kind=='id':record['wikidataIds']=[]
                elif kind=='scope':record['englishWikipediaUrls']=[]
                else:record['paths']={}
                model=pipeline.Lexicon(fixtures.SEED);yago.attach(model,[],[record])
                self.assertFalse(model.approved.get('Fixture Software'))

    def test_name_component_requires_explicit_person_field_and_never_splits_full_names(self):
        record=entity();record['matches']=[{'label':'Surnamefixture','language':None,'predicate':'schema:familyName','line':4}]
        model=pipeline.Lexicon(fixtures.SEED);yago.attach(model,[],[record])
        self.assertFalse(model.approved.get('Surnamefixture'))
        record['paths']={'schema:Person':{'schema:Person':[]}};record['types']=[{'type':'schema:Person','line':5}]
        yago.attach(model,[],[record]);key=next(iter(model.approved['Surnamefixture']))
        self.assertEqual({'noun','noun_proper','name_person'},model.members[key,'Surnamefixture'])
        self.assertFalse(model.approved.get('Fixture'))
        another=copy.deepcopy(record);another['id']='yago:Another_Person';another['wikidataIds']=['wd:Q456']
        yago.attach(model,[],[another])
        self.assertEqual({key},model.approved['Surnamefixture'])
        self.assertEqual(2,len(model.evidence[key,'Surnamefixture']))
        model.validate()


if __name__=='__main__':unittest.main()
