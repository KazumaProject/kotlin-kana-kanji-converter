import argparse
import contextlib
import io
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import batch_research as b
import wikidata_review as r
import worker as w


def statement(qid,prop,target,rank='normal'):
    return {'id':qid+'$'+prop+target,'rank':rank,'mainsnak':{'snaktype':'value','datavalue':{'value':{'id':target}}}}
def entity(qid,label,p31=(),p279=(),ja=None,y=None,**extra):
    claims={}
    for prop,ids in [('P31',p31),('P279',p279)]:
        if ids:claims[prop]=[statement(qid,prop,v)for v in ids]
    if y:claims['P1814']=[{'id':qid+'$reading','rank':'normal','mainsnak':{'snaktype':'value','datavalue':{'value':y}}}]
    return {'id':qid,'labels':{'en':{'value':label},**({'ja':{'value':ja}}if ja else {})},'claims':claims,**extra}


class WikidataReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.tmp.name)/'catalog.sqlite'
        self.rows=[];self.catalogs=[]
    def tearDown(self):
        for c in self.catalogs:c.close()
        self.tmp.cleanup()
    def catalog(self,values):
        db=sqlite3.connect(self.path)
        try:
            db.execute('CREATE TABLE entities(id TEXT PRIMARY KEY,body TEXT)')
            for value in values:db.execute('INSERT INTO entities VALUES(?,?)',(value['id'],json.dumps(value,ensure_ascii=False)))
            db.commit()
        finally:db.close()
        c=r.RawCatalog(self.path,w.sha(self.path));self.catalogs.append(c);return c
    def categories(self,c,q='Q1',**kwargs):
        return {v['category']for v in r.classify(c,c.record(q),**kwargs)[0]}
    def test_raw_path_and_definition_are_literal(self):
        values=[entity('Q1','Example',p31=['Q2']),entity('Q2','university in Japan',p279=['Q3918']),entity('Q3918','university')]
        c=self.catalog(values);p,issues,_,_=r.classify(c,c.record('Q1'))
        self.assertEqual({'organization'},self.categories(c));self.assertEqual(['P31','P279'],[e['property']for e in p[0]['path']])
        self.assertEqual(w.canonical(values[1]['claims']['P279'][0]),p[0]['path'][1]['quotation'])
        self.assertEqual('university',p[0]['rootDefinition']['labels']['en']['value']);self.assertEqual([],issues)
    def test_changed_or_unlabeled_root_does_not_inherit_old_category(self):
        c=self.catalog([entity('Q1','x',p31=['Q431289']),entity('Q431289','Brand village')])
        self.assertFalse(self.categories(c));self.assertIn('class-definition-missing-or-changed:Q431289',r.classify(c,c.record('Q1'))[1])
    def test_old_brand_city_id_is_not_a_product_rule(self):
        c=self.catalog([entity('Q1','x',p31=['Q897716']),entity('Q897716','Brand')]);self.assertFalse(self.categories(c))
    def test_broad_concept_has_no_general_fallback(self):
        c=self.catalog([entity('Q1','x',p31=['Q151885']),entity('Q151885','concept')]);self.assertFalse(self.categories(c));self.assertNotIn('general',{v['category']for v in r.ROOTS.values()})
    def test_station_suppresses_facility_and_place(self):
        c=self.catalog([entity('Q1','x',p31=['Q55488']),entity('Q55488','railway station',p279=['Q41176','Q2221906']),entity('Q41176','building'),entity('Q2221906','geographic location')])
        self.assertEqual({'station'},self.categories(c));self.assertEqual(2,len(r.classify(c,c.record('Q1'))[2]))
    def test_school_is_organization_not_its_building(self):
        c=self.catalog([entity('Q1','x',p31=['Q3914']),entity('Q3914','school',p279=['Q43229','Q41176']),entity('Q43229','organization'),entity('Q41176','building')]);self.assertEqual({'organization'},self.categories(c))
    def test_castle_is_a_facility_despite_its_geographical_superclass(self):
        c=self.catalog([entity('Q1','x',p31=['Q92026']),entity('Q92026','Japanese castle',p279=['Q2221906']),entity('Q2221906','geographic location')])
        self.assertEqual({'facility'},self.categories(c))
    def test_named_historical_battle_is_an_event(self):
        c=self.catalog([entity('Q1','x',p31=['Q178561']),entity('Q178561','battle')])
        self.assertEqual({'event'},self.categories(c))
    def test_separate_explicit_food_and_organization_roles_remain(self):
        c=self.catalog([entity('Q1','x',p31=['Q2095','Q43229']),entity('Q2095','food'),entity('Q43229','organization')]);self.assertEqual({'food','organization'},self.categories(c))
    def test_town_is_place_despite_built_structure_ontology(self):
        c=self.catalog([entity('Q1','x',p31=['Q3957']),entity('Q3957','town',p279=['Q486972']),entity('Q486972','human settlement',p279=['Q811979']),entity('Q811979','built structure')]);self.assertEqual({'place'},self.categories(c))
    def test_municipality_does_not_inherit_company_sense(self):
        c=self.catalog([entity('Q1','x',p31=['Q15284']),entity('Q15284','municipality',p279=['Q56061','Q43229']),entity('Q56061','administrative territorial entity'),entity('Q43229','organization')]);self.assertEqual({'place'},self.categories(c))
    def test_musical_production_does_not_inherit_event_sense(self):
        c=self.catalog([entity('Q1','x',p31=['Q43099500']),entity('Q43099500','performing arts production',p279=['Q1656682']),entity('Q1656682','planned event')]);self.assertEqual({'work'},self.categories(c))
    def test_meteorite_does_not_inherit_product_sense(self):
        c=self.catalog([entity('Q1','x',p31=['Q60186']),entity('Q60186','meteorite',p279=['Q6999','Q2424752']),entity('Q6999','astronomical object'),entity('Q2424752','product')]);self.assertEqual({'astronomy'},self.categories(c))
    def test_itinerary_is_not_a_product_model(self):
        c=self.catalog([entity('Q1','x',p31=['Q2']),entity('Q2','transport service itinerary',p279=['Q2424752']),entity('Q2424752','product')]);self.assertFalse(self.categories(c))
    def test_voice_type_is_not_a_named_event(self):
        c=self.catalog([entity('Q1','x',p31=['Q2']),entity('Q2','voice type',p279=['Q1656682']),entity('Q1656682','planned event')]);self.assertFalse(self.categories(c))
    def test_explicit_literary_award_is_event(self):
        c=self.catalog([entity('Q1','x',p31=['Q2']),entity('Q2','literary award',p279=['Q1656682']),entity('Q1656682','planned event')]);self.assertEqual({'event'},self.categories(c))
    def test_sport_competition_does_not_inherit_sport_sense(self):
        c=self.catalog([entity('Q1','x',p31=['Q13406554']),entity('Q13406554','sports competition',p279=['Q349']),entity('Q349','sport')]);self.assertEqual({'event'},self.categories(c))
    def test_shipwreck_does_not_inherit_facility_sense(self):
        c=self.catalog([entity('Q1','x',p31=['Q852190']),entity('Q852190','shipwreck',p279=['Q13226383']),entity('Q13226383','facility')]);self.assertEqual({'transport'},self.categories(c))
    def test_fictional_type_human_ancestor_is_not_two_conflicting_assertions(self):
        c=self.catalog([entity('Q1','x',p31=['Q15632617']),entity('Q15632617','fictional human',p279=['Q5']),entity('Q5','human')]);self.assertEqual({'character'},self.categories(c))
    def test_human_and_fictional_contradiction_is_unresolved(self):
        c=self.catalog([entity('Q1','x',p31=['Q5','Q15632617']),entity('Q5','human'),entity('Q15632617','fictional human')]);self.assertFalse(self.categories(c));self.assertIn('contradictory-real-human-and-fictional-or-deity-classes',r.classify(c,c.record('Q1'))[1])
    def test_person_does_not_inherit_organism_role(self):
        c=self.catalog([entity('Q1','x',p31=['Q5']),entity('Q5','human',p279=['Q7239']),entity('Q7239','organism')]);self.assertEqual({'person'},self.categories(c))
    def test_anatomy_is_not_whole_organism(self):
        c=self.catalog([entity('Q1','x',p31=['Q2']),entity('Q2','anatomical structure',p279=['Q7239']),entity('Q7239','organism')]);self.assertFalse(self.categories(c))
    def test_real_taxon_remains_organism(self):
        c=self.catalog([entity('Q1','x',p31=['Q16521']),entity('Q16521','taxon')]);self.assertEqual({'organism'},self.categories(c))
    def test_programming_language_is_technical_not_product(self):
        c=self.catalog([entity('Q1','x',p31=['Q9143']),entity('Q9143','programming language',p279=['Q2424752']),entity('Q2424752','product')]);self.assertEqual({'technical'},self.categories(c))
    def test_named_software_is_product(self):
        c=self.catalog([entity('Q1','x',p31=['Q7397']),entity('Q7397','software',p279=['Q47461344']),entity('Q47461344','written work')]);self.assertEqual({'product'},self.categories(c))
    def test_generic_compiler_concept_is_technical(self):
        c=self.catalog([entity('Q1','x',p279=['Q2']),entity('Q2','compiler',p279=['Q7397']),entity('Q7397','software')]);self.assertEqual({'technical'},self.categories(c))
    def test_transport_product_superclass_does_not_create_model_sense(self):
        c=self.catalog([entity('Q1','x',p31=['Q11446']),entity('Q11446','ship',p279=['Q42889','Q2424752']),entity('Q42889','vehicle'),entity('Q2424752','product')]);self.assertEqual({'transport'},self.categories(c))
    def test_explicit_vehicle_model_is_product(self):
        c=self.catalog([entity('Q1','x',p31=['Q2']),entity('Q2','automobile model',p279=['Q42889','Q2424752']),entity('Q42889','vehicle'),entity('Q2424752','product')]);self.assertEqual({'product'},self.categories(c))
    def test_deprecated_claims_do_not_supply_semantics(self):
        e=entity('Q1','x',p31=['Q5']);e['claims']['P31'][0]['rank']='deprecated';c=self.catalog([e,entity('Q5','human')]);self.assertFalse(self.categories(c))
    def test_missing_and_novalue_claims_do_not_supply_semantics(self):
        e=entity('Q1','x',p31=['Q5']);e['claims']['P31'][0]['mainsnak']['snaktype']='novalue';c=self.catalog([e,entity('Q5','human')]);self.assertFalse(self.categories(c))
    def test_ancestry_cycles_are_bounded(self):
        c=self.catalog([entity('Q1','x',p31=['Q2']),entity('Q2','x',p279=['Q3']),entity('Q3','y',p279=['Q2','Q5']),entity('Q5','human')]);self.assertEqual({'person'},self.categories(c))
    def test_node_bound_returns_unresolved_without_guessing(self):
        c=self.catalog([entity('Q1','x',p31=['Q5']),entity('Q5','human',p279=['Q2']),entity('Q2','entity')]);self.assertFalse(self.categories(c,max_nodes=1));self.assertIn('ancestry-node-bound-reached',r.classify(c,c.record('Q1'),max_nodes=1)[1])
    def test_depth_bound_preserves_explicit_positive_and_records_limit(self):
        c=self.catalog([entity('Q1','x',p31=['Q5']),entity('Q5','human',p279=['Q2']),entity('Q2','entity',p279=['Q3']),entity('Q3','object')]);self.assertEqual({'person'},self.categories(c,max_depth=1));self.assertTrue(any(v.startswith('ancestry-depth-bound')for v in r.classify(c,c.record('Q1'),max_depth=1)[1]))
    def test_catalog_hash_is_required(self):
        self.catalog([entity('Q1','x')])
        with self.assertRaisesRegex(ValueError,'checksum'):r.RawCatalog(self.path,'0'*64)
    def test_alias_cannot_borrow_primary_reading(self):
        e=entity('Q1','x',ja='別人',y='やまだ',aliases={'ja':[{'value':'山田'}]});c=self.catalog([e]);self.assertFalse(r.named_reading(c.record('Q1'),{'id':'x','surface':'山田','reading':'やまだ'}))
    def test_readonly_recommendation_and_class_package(self):
        e=entity('Q1','Yamada',p31=['Q5'],ja='山田',y='やまだ');c=self.catalog([e,entity('Q5','human')])
        db=w.connect(pathlib.Path(self.tmp.name)/'ledger.sqlite');db.executescript(w.SCHEMA)
        w.insert_candidate(db,'やまだ','山田',1,1,10)
        args=argparse.Namespace(config=str(w.DEFAULT_CONFIG),documents=str(pathlib.Path(self.tmp.name)/'documents'))
        evidence=w.Evidence(db,args);row=dict(db.execute('SELECT * FROM candidates').fetchone());record=c.record('Q1')
        b.materialize(db,evidence,e,record['raw'],[row],b.strict_matches(e,[row]),{'catalogSha256':c.sha256})
        before=db.total_changes;cases,sources,counts,cats,failures=r.recommendations(db,c)
        self.assertEqual(before,db.total_changes);self.assertEqual({'person':1},cats);self.assertEqual(1,len(cases));self.assertFalse(cases[0]['importReady']);self.assertEqual('source_review',cases[0]['roles'][0]['method']);self.assertIn('Q5',sources)
        self.assertEqual(w.digest(sources['Q5']['raw'].encode()),sources['Q5']['entityRecordSha256']);self.assertFalse(sources['Q5']['revisionKnown']);self.assertFalse(failures);db.close()
    def test_same_spelling_reading_of_other_target_is_not_reused(self):
        c=self.catalog([entity('Q1','x',ja='山田',y='やまだ'),entity('Q2','x',ja='山田',y='やまた')]);self.assertFalse(r.named_reading(c.record('Q2'),{'id':'x','surface':'山田','reading':'やまだ'}))

    def inspection_fixture(self,values):
        catalog=self.catalog(values);base=pathlib.Path(self.tmp.name)
        db=w.connect(base/'ledger.sqlite');db.executescript(w.SCHEMA)
        w.insert_candidate(db,'かな','カナ',1,1,10)
        args=argparse.Namespace(config=str(w.DEFAULT_CONFIG),documents=str(base/'documents'),
            source_package=str(base/'class-sources.json'),recommendations=str(base/'recommendations.jsonl'),
            review_path=str(base/'current-review.json'),max_cases=None)
        evidence=w.Evidence(db,args);row=dict(db.execute('SELECT * FROM candidates').fetchone())
        for value in values:
            matches=b.strict_matches(value,[row])
            if matches:b.materialize(db,evidence,value,catalog.record(value['id'])['raw'],[row],matches,{'catalogSha256':catalog.sha256})
        cases,sources,_,_,_=r.recommendations(db,catalog)
        pathlib.Path(args.source_package).write_text(w.canonical({'catalogSha256':catalog.sha256,'rulesSha256':w.digest(w.canonical(r.ROOTS)),'sources':sources}))
        pathlib.Path(args.recommendations).write_text(''.join(w.canonical(c)+'\n' for c in cases))
        w.info(db,'goldFrozen',{'sha256':'a'*64,'cases':[]})
        w.info(db,'rawWikidataCatalog:'+catalog.sha256+':1',{'complete':True});db.commit()
        self.addCleanup(db.close);return db,args,cases

    def test_inspected_kana_and_two_targets_merge_without_losing_roles(self):
        db,args,_=self.inspection_fixture([entity('Q1','person',ja='カナ',p31=['Q5']),entity('Q2','program',ja='カナ',p31=['Q7397']),entity('Q5','human'),entity('Q7397','software')])
        with contextlib.redirect_stdout(io.StringIO()):result=r.apply_inspected(db,args)
        decision=json.loads(db.execute('SELECT decision FROM candidates').fetchone()[0])
        self.assertEqual({('person','Q1'),('product','Q2')},{(x['category'],x['target']) for x in decision['roles']})
        self.assertEqual(2,result['counts']['reviewed']);self.assertEqual(0,result['modelsCalled'])
        with contextlib.redirect_stdout(io.StringIO()):repeat=r.apply_inspected(db,args)
        self.assertEqual(0,repeat['counts'].get('reviewed',0))

    def test_inspection_rejects_tampered_path_and_unfrozen_gold(self):
        db,args,cases=self.inspection_fixture([entity('Q1','person',ja='カナ',p31=['Q5']),entity('Q5','human')])
        db.execute("DELETE FROM info WHERE key='goldFrozen'")
        with self.assertRaisesRegex(ValueError,'Freeze independent'):r.apply_inspected(db,args)
        w.info(db,'goldFrozen',{'sha256':'a'*64,'cases':[]})
        cases[0]['roles'][0]['path'][0]['to']='Q2'
        pathlib.Path(args.recommendations).write_text(w.canonical(cases[0])+'\n')
        with self.assertRaisesRegex(ValueError,'Unbound class path'):r.apply_inspected(db,args)
        self.assertIsNone(db.execute('SELECT decision FROM candidates').fetchone()[0])

    def test_inspected_generic_software_class_has_literal_technical_proof(self):
        db,args,_=self.inspection_fixture([entity('Q1','x',ja='カナ',p279=['Q2']),entity('Q2','compiler',p279=['Q7397']),entity('Q7397','software')])
        with contextlib.redirect_stdout(io.StringIO()):result=r.apply_inspected(db,args)
        decision=json.loads(db.execute('SELECT decision FROM candidates').fetchone()[0])
        self.assertEqual({('technical','Q1')},{(v['category'],v['target']) for v in decision['roles']})
        self.assertEqual(1,result['counts']['reviewed'])

    def native_reading_fixture(self,kind=('Q5','human'),text="'''山田'''（やまだ）は人物。"):
        values=[entity('Q1','Yamada',ja='山田',p31=[kind[0]]),entity(*kind)]
        db,args,_=self.inspection_fixture(values);catalog=self.catalogs[-1]
        w.insert_candidate(db,'やまだ','山田',1,1,10)
        row=dict(db.execute("SELECT * FROM candidates WHERE surface='山田'").fetchone())
        e=w.Evidence(db,args);qid='Q1';title='山田'
        native_quote="(12,'wikibase_item','Q1',NULL)"
        did=e.save('https://dumps.wikimedia.org/jawiki/20261001/jawiki-page_props.sql','20261001',native_quote.encode(),'CC-BY-SA')
        identity=e.fact('やまだ','山田','context',[],qid,did,dict(source='Wikipedia-page-identity',pageId=12,qid=qid,title=title,quotation=native_quote,sourceSha256=w.digest(native_quote)))
        page={'query':{'pages':{'12':{'pageid':12,'title':title,'revisions':[{'revid':34,'slots':{'main':{'*':text}}}]}}}}
        did=e.save('https://ja.wikipedia.org/w/api.php','34',w.canonical(page).encode(),'CC-BY-SA')
        read=e.fact('やまだ','山田','reading',[],qid,did,dict(source='explicit-name-reading',name=title,revision='34',componentFacts=[identity],quotation="'''山田'''（やまだ）",acquisition={'sourceDumpSha256':'b'*64,'sourcePageId':12}))
        subject=catalog.record(qid);did=e.save('https://www.wikidata.org/wiki/Special:EntityData/Q1.json','sha256:'+subject['sha256'],subject['raw'].encode(),'CC0')
        e.fact('やまだ','山田','context',[],qid,did,dict(source='Wikidata',id=qid,label=title,types=[kind[0]],acquisition={'catalogSha256':catalog.sha256}))
        package={'catalogSha256':catalog.sha256,'rulesSha256':w.digest(w.canonical(r.ROOTS)),'sources':{kind[0]:r.source_package(catalog.record(kind[0]),catalog)}}
        pathlib.Path(args.source_package).write_text(w.canonical(package));db.commit()
        return db,args,row,read,identity,package

    def test_native_article_reading_classifies_without_borrowing_entity_reading(self):
        db,args,row,_,_,package=self.native_reading_fixture()
        self.assertFalse(b.strict_matches(self.catalogs[-1].record('Q1')['entity'],[row]))
        with contextlib.redirect_stdout(io.StringIO()):result=r.apply_inspected(db,args,r.saved_named_cases(db,package))
        decision=json.loads(db.execute('SELECT decision FROM candidates WHERE id=?',(row['id'],)).fetchone()[0])
        self.assertEqual({('person','Q1')},{(v['category'],v['target']) for v in decision['roles']})
        self.assertEqual(1,result['counts']['reviewed'])

    def test_native_kana_title_is_bound_to_its_own_item_and_revision(self):
        db,args,_,_,_,package=self.native_reading_fixture()
        e=w.Evidence(db,args);cid=w.insert_candidate(db,'かな','カナ',1,1,10)
        native="(12,'wikibase_item','Q1',NULL)"
        did=e.save('https://dumps.wikimedia.org/jawiki/20261001/jawiki-page_props.sql','20261001',native.encode(),'CC-BY-SA')
        identity=e.fact('かな','カナ','context',[],'Q1',did,dict(source='Wikipedia-page-identity',pageId=12,qid='Q1',title='カナ',quotation=native,sourceSha256=w.digest(native)))
        page={'query':{'pages':{'12':{'pageid':12,'title':'カナ','revisions':[{'revid':34,'slots':{'main':{'*':"'''カナ'''は人物。"}}}]}}}}
        did=e.save('https://ja.wikipedia.org/w/api.php','34',w.canonical(page).encode(),'CC-BY-SA')
        fid=e.fact('かな','カナ','reading',[],'Q1',did,dict(source='attested-canonical-kana',name='カナ',revision='34',componentFacts=[identity],acquisition={'sourceDumpSha256':'b'*64,'sourcePageId':12}))
        row=dict(db.execute('SELECT * FROM candidates WHERE id=?',(cid,)).fetchone());fact=dict(db.execute('SELECT * FROM facts WHERE id=?',(fid,)).fetchone())
        self.assertTrue(r.wikipedia_name_reading(db,row,fact))
        self.assertFalse(r.wikipedia_name_reading(db,{**row,'reading':'かんな'},fact))
        self.assertFalse(r.wikipedia_name_reading(db,row,{**fact,'body':w.canonical({**json.loads(fact['body']),'revision':'35'})}))

    def test_reading_inspection_parses_only_its_native_page(self):
        import source_rounds
        db,args,row,read,_,_=self.native_reading_fixture();e=w.Evidence(db,args)
        text="'''山田'''（やまだ）は人物。"
        page={'query':{'pages':{'12':{'pageid':12,'title':'山田','revisions':[{'revid':34,'slots':{'main':{'*':text}}}]},
            '99':{'pageid':99,'title':'別頁','revisions':[{'revid':100,'slots':{'main':{'*':'無関係な本文'*10000}}}]}}}}
        did=e.save('https://ja.wikipedia.org/w/api.php','34',w.canonical(page).encode(),'CC-BY-SA')
        db.execute('UPDATE facts SET document_id=? WHERE id=?',(did,read))
        fact=dict(db.execute('SELECT * FROM facts WHERE id=?',(read,)).fetchone())
        with mock.patch.object(source_rounds,'full_body_reading_bindings',wraps=source_rounds.full_body_reading_bindings) as inspect:
            self.assertTrue(r.wikipedia_name_reading(db,row,fact))
            inspect.assert_called_once_with(text)

    def test_native_identity_tuple_cannot_be_relabelled_to_another_item(self):
        db,_,row,read,identity,_=self.native_reading_fixture()
        body=json.loads(db.execute('SELECT body FROM facts WHERE id=?',(identity,)).fetchone()[0]);body['quotation']="(12,'wikibase_item','Q2',NULL)"
        db.execute('UPDATE facts SET body=? WHERE id=?',(w.canonical(body),identity))
        fact=db.execute('SELECT * FROM facts WHERE id=?',(read,)).fetchone()
        self.assertFalse(r.wikipedia_name_reading(db,row,fact))

    def test_primary_article_definition_distinguishes_facility_from_its_operator(self):
        text="'''山田'''（やまだ）は株式会社別会社が運営する日本のシネマコンプレックス。"
        db,args,row,read,_,package=self.native_reading_fixture(('Q43229','organization'),text)
        with contextlib.redirect_stdout(io.StringIO()):r.apply_inspected(db,args,r.saved_named_cases(db,package))
        decision=json.loads(db.execute('SELECT decision FROM candidates WHERE id=?',(row['id'],)).fetchone()[0])
        self.assertEqual({'facility'},{v['category'] for v in decision['roles']})
        quotation=next(v['quotation'] for v in decision['citations'] if v['evidenceId']==read)
        self.assertEqual(text,quotation)

    def test_new_class_rules_replace_previous_inferred_category(self):
        db,args,_=self.inspection_fixture([entity('Q1','castle',ja='カナ',p31=['Q92026']),entity('Q92026','Japanese castle')])
        with contextlib.redirect_stdout(io.StringIO()):r.apply_inspected(db,args)
        old=json.loads(db.execute('SELECT decision FROM candidates').fetchone()[0]);old['roles'][0]['category']='place'
        db.execute('UPDATE candidates SET decision=?',(w.canonical(old),));db.commit()
        with contextlib.redirect_stdout(io.StringIO()):result=r.apply_inspected(db,args)
        decision=json.loads(db.execute('SELECT decision FROM candidates').fetchone()[0])
        self.assertEqual({'facility'},{v['category'] for v in decision['roles']})
        self.assertEqual(1,result['counts']['reclassifiedTargets'])

if __name__=='__main__':unittest.main()
