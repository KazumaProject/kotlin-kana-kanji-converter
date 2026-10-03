import argparse,contextlib,gzip,io,json,pathlib,sqlite3,tempfile,unittest,unittest.mock as mock,zipfile,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import worker,distribution

class ResearchTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)
        self.db=worker.connect(self.root/'ledger.sqlite');self.db.executescript(worker.SCHEMA)
        self.args=argparse.Namespace(config=str(worker.DEFAULT_CONFIG),documents=str(self.root/'docs'),ledger=str(self.root/'ledger.sqlite'),output=str(self.root/'snapshot.sqlite'),candidate=False)
        worker.info(self.db,'prepared',True);worker.pin_config(self.db,self.args)
        self.e=worker.Evidence(self.db,self.args);self.doc=self.e.save('https://example.org/source','v1','山田（やまだ） 実在人物'.encode(),'CC0')
        self.cid=worker.insert_candidate(self.db,'やまだ','山田',1,1,10,'accepted','person')
        self.fid=self.e.fact('やまだ','山田','reading',[],'Q1',self.doc,{'source':'explicit-name-reading','quotation':'山田（やまだ）'})
        self.mean=self.e.fact('やまだ','山田','meaning',['person'],'Q1',self.doc,{'source':'official-profile'})
        self.row=dict(self.db.execute('SELECT * FROM candidates').fetchone());self.db.commit()
    def tearDown(self): self.db.close();self.temp.cleanup()
    def value(self):
        return {'id':self.cid,'quality':'appropriate','roles':[{'category':'person','target':'Q1','sense':'実在人','evidenceIds':[self.mean]}],
                'evidenceIds':[self.fid,self.mean],'missing':[],'searchTerms':[],'corrections':[]}
    def model_inventory(self,url):
        if url.endswith('/api/tags'):
            models=worker.configuration(self.args)[0]
            return {'models':[models[r] for r in ('proposer','reviewer')]}
        if url.endswith('/api/ps'): return {'models':[]}
        return None
    def validate(self,v): worker.validate_output(v,[self.row],{self.cid:worker.fact_rows(self.db,self.row)},['person'])
    def test_pair_proof_is_independent_of_classification(self):
        v=self.value();worker.decide(self.db,self.row,v,v)
        self.assertEqual('reviewed',self.db.execute('SELECT state FROM candidates').fetchone()[0])
        self.db.execute("DELETE FROM facts WHERE kind='reading'")
        worker.decide(self.db,self.row,v,v)
        state,reason=self.db.execute('SELECT state,reason FROM candidates').fetchone()
        self.assertEqual('not_distributed',state);self.assertIn('reading-evidence-insufficient',reason)
    def test_semantic_agreement_cannot_create_reading(self):
        self.db.execute('DELETE FROM facts');v=self.value();v['roles'][0]['evidenceIds']=[]
        worker.decide(self.db,self.row,v,v)
        self.assertEqual('not_distributed',self.db.execute('SELECT state FROM candidates').fetchone()[0])
    def test_reviewer_is_blind_to_old_classification(self):
        captured=[]
        def api(url,body=None,**kwargs):
            inventory=self.model_inventory(url)
            if inventory is not None: return inventory
            captured.append(body);payload=json.loads(body['messages'][1]['content'])['candidates'][0];v=self.value();v['id']=payload['id'];v['evidenceIds']=[f['evidenceId'] for f in payload['facts']];v['roles'][0]['evidenceIds']=[f['evidenceId'] for f in payload['facts'] if f['kind']=='meaning'];return {'message':{'content':json.dumps({'results':[v]})},'eval_count':10}
        with mock.patch.object(worker,'request_json',side_effect=api): worker.inference(self.db,self.args,[self.row],'reviewer',worker.configuration(self.args))
        user=captured[0]['messages'][1]['content']
        self.assertNotIn('old_categories',user);self.assertNotIn('old_status',user);self.assertNotIn('proposal',user)
        stored=self.db.execute('SELECT request,response,aliases FROM model_calls').fetchone()
        self.assertEqual(captured[0],json.loads(gzip.decompress(stored[0])))
        self.assertIn('results',json.loads(json.loads(gzip.decompress(stored[1]))['message']['content']))
        self.assertEqual('c0',json.loads(stored[2])['candidates'][self.cid])
    def test_loopback_only(self):
        for url in ['https://api.example.org','http://127.0.0.1.example.org:11434','http://user@127.0.0.1','http://127.0.0.1/path','https://localhost','http://localhost?x=1']:
            with self.assertRaises(ValueError): worker.local_url(url)
        self.assertEqual('http://127.0.0.1:11434',worker.local_url('http://127.0.0.1:11434'))
    def test_fake_url_or_fact_rejected(self):
        v=self.value();v['evidenceIds']=['https://invented.example.org']
        with self.assertRaises(ValueError): self.validate({'results':[v]})
    def test_fake_target_rejected(self):
        v=self.value();v['roles'][0]['target']='Q999999'
        with self.assertRaises(ValueError): self.validate({'results':[v]})
    def test_ids_must_be_exact_and_once(self):
        for value in [{'results':[]},{'results':[self.value(),self.value()]}]:
            with self.assertRaises(ValueError): self.validate(value)
    def test_normalized_entry_requires_separate_proof(self):
        self.row['normalization']='split-or-remove-annotation';v=self.value()
        worker.decide(self.db,self.row,v,v)
        self.assertIn('normalization-evidence-insufficient',self.db.execute('SELECT reason FROM candidates').fetchone()[0])
    def test_model_failure_remains_retryable(self):
        with mock.patch.object(worker,'request_json',side_effect=OSError('model stopped')):
            with self.assertRaises(OSError): worker.inference(self.db,self.args,[self.row],'proposer',worker.configuration(self.args))
        self.assertEqual('error',self.db.execute('SELECT state FROM candidates').fetchone()[0])
        self.assertIsNone(self.db.execute('SELECT decision FROM candidates').fetchone()[0])
    def test_invalid_json_is_not_a_non_distribution_decision(self):
        def api(url,body=None,**kwargs): return self.model_inventory(url) or {'message':{'content':'broken JSON'}}
        with mock.patch.object(worker,'request_json',side_effect=api):
            with self.assertRaises(ValueError): worker.inference(self.db,self.args,[self.row],'proposer',worker.configuration(self.args))
        self.assertEqual('error',self.db.execute('SELECT state FROM candidates').fetchone()[0])
    def test_model_digest_is_pinned(self):
        with mock.patch.object(worker,'request_json',return_value={'models':[]}):
            with self.assertRaises(ValueError): worker.validate_models(*[worker.configuration(self.args)[i] for i in (0,3)])
    def test_confidence_threshold_cannot_be_met_with_100_cases(self):
        self.assertLess(worker.confidence_lower(100,100),.99)
        self.assertAlmostEqual(worker.confidence_lower(100,100),.05**.01,places=10)
        self.assertGreater(worker.confidence_lower(300,300),.99)
    def test_finalize_rejects_unprocessed(self):
        with self.assertRaisesRegex(ValueError,'Unfinished'): distribution.precision(self.db,worker.info,worker.confidence_lower,worker.canonical)
    def test_storage_full_is_an_error_not_a_decision(self):
        self.e.limit=1
        with self.assertRaises(OSError): self.e.save('https://example.org/new','v1',b'too large','CC0')
        self.assertEqual('queued',self.db.execute('SELECT state FROM candidates').fetchone()[0])
    def test_new_fact_invalidates_only_affected_candidates(self):
        other=worker.insert_candidate(self.db,'べつ','別',1,1,10)
        self.db.execute("UPDATE candidates SET state='reviewed',decision='{}'")
        self.e.fact('やまだ','山田','context',[],'Q1',self.doc,{'new':True})
        self.assertEqual('queued',self.db.execute('SELECT state FROM candidates WHERE id=?',(self.cid,)).fetchone()[0])
        self.assertEqual('reviewed',self.db.execute('SELECT state FROM candidates WHERE id=?',(other,)).fetchone()[0])
    def test_gzip_export_cannot_run_before_quality_gates(self):
        with self.assertRaises(ValueError): worker.export(self.args)
        self.assertFalse(pathlib.Path(self.args.output).exists())
    def test_jmnedict_reading_restrictions_and_names(self):
        other=worker.insert_candidate(self.db,'かせん','山田',1,1,10)
        xml='''<?xml version="1.0"?><!DOCTYPE JMnedict [<!ENTITY surname "surname"><!ENTITY place "place name">]><JMnedict><entry><ent_seq>1</ent_seq><k_ele><keb>山田</keb></k_ele><k_ele><keb>河川</keb></k_ele><r_ele><reb>かせん</reb><re_restr>河川</re_restr></r_ele><trans><name_type>&place;</name_type><trans_det>River</trans_det></trans></entry><entry><ent_seq>2</ent_seq><k_ele><keb>山田</keb></k_ele><r_ele><reb>やまだ</reb></r_ele><trans><name_type>&surname;</name_type><trans_det>Yamada</trans_det></trans></entry></JMnedict>'''
        path=self.root/'JMnedict.xml.gz';self.args.jmnedict=str(path)
        with gzip.open(path,'wb') as f: f.write(xml.encode())
        with contextlib.redirect_stdout(io.StringIO()): worker.import_jmnedict(self.db,self.args,self.e)
        self.assertFalse(self.db.execute("SELECT 1 FROM facts WHERE reading='かせん' AND surface='山田'").fetchone())
        self.assertTrue(self.db.execute("SELECT 1 FROM facts WHERE surface='山田' AND target='JMnedict:2:0' AND categories='[\"person\"]'").fetchone())
    def test_held_originals_are_not_lost_after_splitting(self):
        self.db.execute('INSERT INTO origins VALUES(?,?,?,?,?,?,?,?,?)',('o','place',1,'やまだかわ','山田(川)',1,1,10,'raw'))
        self.db.execute('INSERT INTO normalization VALUES(?,?,?,?,?,?,?,?,?)',('place',1,'やまだ','山田',1,1,10,'','split-with-unresolved-alias'))
        self.db.execute('INSERT INTO origin_candidates VALUES(?,?)',('o',self.cid));worker.augment_originals(self.db)
        rows=self.db.execute('SELECT surface FROM candidates').fetchall()
        self.assertIn('山田(川)',[r[0] for r in rows]);self.assertEqual(2,self.db.execute('SELECT COUNT(*) FROM origin_candidates').fetchone()[0])
    def test_explicit_surname_is_not_overruled_by_model_uncertainty(self):
        self.e.fact('やまだ','山田','meaning',['person'],'JMnedict:1:0',self.doc,{'source':'JMnedict','nameTypes':['surname'],'sense':0})
        v=self.value();v['quality']='uncertain';v['roles']=[]
        worker.decide(self.db,self.row,v,v)
        result=json.loads(self.db.execute('SELECT decision FROM candidates').fetchone()[0])
        self.assertEqual('reviewed',self.db.execute('SELECT state FROM candidates').fetchone()[0])
        self.assertEqual('direct',result['roles'][0]['method'])
    def test_broad_lexical_labels_are_not_direct_category_proof(self):
        for source,category,extra in [('JMnedict','place',{'nameTypes':['place']}),('JMdict','general',{'pos':['n'],'misc':[]}),('JMdict','technical',{'fields':['astron'],'misc':[]})]:
            f={'kind':'meaning','body':json.dumps({'source':source,**extra})}
            self.assertFalse(worker.direct_category_fact(f,category))
    def test_homonym_reading_conflict_is_scoped_to_its_target(self):
        self.e.fact('','山田','context',[],'Q999',self.doc,{'source':'Wikidata','label':'山田','nameBoundReadings':{'山田':['さんでん']}})
        facts=worker.fact_rows(self.db,self.row)
        self.assertTrue(worker.target_supported(self.value()['roles'][0],facts))
        role={'target':'Q999','evidenceIds':[f['id'] for f in facts if f['target']=='Q999']}
        self.assertFalse(worker.target_supported(role,facts))
    def test_original_parenthesized_name_is_not_a_transformation(self):
        self.row['normalization']='original:meaningful-parentheses'
        v=self.value();worker.decide(self.db,self.row,v,v)
        self.assertEqual('reviewed',self.db.execute('SELECT state FROM candidates').fetchone()[0])
    def test_inactive_old_parser_evidence_does_not_support_adoption(self):
        self.db.execute("UPDATE facts SET active=0 WHERE kind='reading'")
        v=self.value();worker.decide(self.db,self.row,v,v)
        self.assertEqual('not_distributed',self.db.execute('SELECT state FROM candidates').fetchone()[0])
        self.assertEqual(2,self.db.execute('SELECT COUNT(*) FROM facts').fetchone()[0])
    def test_schema4_export_retains_bound_proofs_and_input_map(self):
        v=self.value();worker.decide(self.db,self.row,v,v)
        self.db.execute('INSERT INTO origins VALUES(?,?,?,?,?,?,?,?,?)',('o','person',1,'やまだ','山田',1,1,10,'raw'))
        self.db.execute('INSERT INTO origin_candidates VALUES(?,?)',('o',self.cid))
        worker.info(self.db,'inputs',{'sources':{'person':'0'*64}});worker.info(self.db,'baseIdDefSha256','1'*64);self.args.candidate=True
        cfg=worker.configuration(self.args);cfg=(cfg[0],{'categories':[{'id':'person','core':True,'minimum':1}]},*cfg[2:])
        gate={'eligible':300,'adoptable':300,'precision':{'ai':{'correct':300,'n':300,'lower95':.99}}}
        with mock.patch.object(distribution,'precision',return_value=gate),contextlib.redirect_stdout(io.StringIO()):
            distribution.export(self.db,self.args,lambda args:cfg,worker.info,worker.confidence_lower,worker.canonical,worker.digest,worker.sha,worker.emit)
        with sqlite3.connect(self.args.output) as snapshot:
            self.assertEqual('adopted',snapshot.execute('SELECT status FROM resolutions').fetchone()[0])
            self.assertEqual(self.fid,snapshot.execute('SELECT id FROM reading_facts').fetchone()[0])
            self.assertEqual(self.mean,snapshot.execute('SELECT id FROM semantic_facts').fetchone()[0])
            self.assertEqual(('person',1,self.cid),snapshot.execute('SELECT * FROM source_map').fetchone())
            manifest=json.loads(snapshot.execute("SELECT value FROM info WHERE key='manifest'").fetchone()[0])
            self.assertFalse(manifest['research']['releaseReady'])

    def test_quality_evidence_does_not_cross_input_contexts(self):
        self.row['normalization']='split'
        self.e.fact('やまだ','山田','normalization',[],'another-candidate',self.doc,{'source':'verified-boundary'})
        self.e.fact('やまだ','山田','invalid',[],'another-candidate',self.doc,{'source':'postal-instruction'})
        v=self.value();worker.decide(self.db,self.row,v,v)
        self.assertEqual('not_distributed',self.db.execute('SELECT state FROM candidates').fetchone()[0])
        self.assertIn('normalization-evidence-insufficient',self.db.execute('SELECT reason FROM candidates').fetchone()[0])

    def test_explicit_ruby_and_infobox_bindings(self):
        source='{{Ruby|山田|やまだ}} <ruby>山田<rp>（</rp><rt>やまだ</rt><rp>）</rp></ruby> {{人物\n|名前=山田\n|ふりがな=やまだ\n}}'
        self.db.execute("DELETE FROM facts WHERE kind='reading'")
        worker.extract_readings(self.db,self.e,self.row,self.doc,source,'Q1')
        self.assertEqual(4,self.db.execute("SELECT COUNT(*) FROM facts WHERE kind='reading'").fetchone()[0])
        ambiguous='{{人物\n|名前=山田\n|名前=別人\n|ふりがな=やまだ\n}}'
        self.assertEqual([],worker.explicit_reading_bindings(ambiguous))
        self.assertTrue(worker.article_primary_name("'''山田'''（やまだ）は人物。",'山田'))
        self.assertFalse(worker.article_primary_name("'''別人'''は山田の友人。",'山田'))

    def test_unqualified_wikidata_reading_is_not_alias_pronunciation(self):
        import wikidata
        self.db.execute('DELETE FROM facts')
        self.e.fact('','山田','context',[],'Q1',self.doc,{'source':'seed'})
        entity={'lastrevid':1,'labels':{'ja':{'value':'本名'}},'sitelinks':{'jawiki':{'title':'山田'}},'claims':{'P1814':[{'mainsnak':{'datavalue':{'value':'やまだ'}}}]}}
        with mock.patch.object(self.e,'fetch',return_value=(self.doc,json.dumps({'entities':{'Q1':entity}}).encode())):
            wikidata.fetch(self.db,self.args,self.e,self.row,1,worker.pair,worker.reading,worker.extract_readings)
        self.assertFalse(self.db.execute("SELECT 1 FROM facts WHERE kind='reading'").fetchone())
        role={'target':'Q1','evidenceIds':[f['id'] for f in worker.fact_rows(self.db,self.row)]}
        self.assertFalse(worker.target_supported(role,worker.fact_rows(self.db,self.row)))

    def test_large_candidate_is_reviewed_by_source_units(self):
        for n in range(45):
            self.e.fact('やまだ','山田','meaning',['person'],'JMnedict:'+str(n),self.doc,{'source':'JMnedict','nameTypes':['surname'],'description':'対象の説明'*80})
        calls=[]
        def api(url,body=None,**kwargs):
            inventory=self.model_inventory(url)
            if inventory is not None: return inventory
            calls.append(body);payload=json.loads(body['messages'][1]['content'])['candidates'][0]
            facts=[f for f in payload['facts'] if f['kind']=='meaning']
            v=self.value();v['id']=payload['id'];v['roles']=[{'category':'person','target':f['target'],'sense':'姓','evidenceIds':[f['evidenceId']]} for f in facts];v['evidenceIds']=[]
            return {'message':{'content':json.dumps({'results':[v]})},'eval_count':10}
        with mock.patch.object(worker,'request_json',side_effect=api):
            result=worker.inference(self.db,self.args,[self.row],'reviewer',worker.configuration(self.args))
        self.assertEqual(46,len(result[self.cid]['roles']))
        self.assertEqual(46,len(calls))
        self.assertEqual(len(calls),self.db.execute('SELECT COUNT(*) FROM model_calls').fetchone()[0])

    def test_compressed_html_and_japanese_web_charset(self):
        page='<html><meta charset="Shift_JIS"><body>山田Ⅰ</body></html>'
        data=page.encode('cp932')
        self.assertEqual(page,worker.decode_official_page(data))
        self.assertEqual(page,worker.decode_official_page(gzip.compress(data)))
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            worker.decode_official_page(gzip.compress(b'%PDF-1.4 source'))

    def test_research_parser_upgrade_archives_old_bindings(self):
        cfg=worker.info(self.db,'configuration');cfg['researchParserVersion']=1;worker.info(self.db,'configuration',cfg)
        self.e.fact('やまだ','山田','reading',[],'JapanPost:1',self.doc,{'source':'Japan Post','row':1})
        worker.pin_config(self.db,self.args)
        self.assertEqual(0,self.db.execute('SELECT active FROM facts WHERE id=?',(self.fid,)).fetchone()[0])
        self.assertEqual(1,self.db.execute("SELECT active FROM facts WHERE target='JapanPost:1'").fetchone()[0])

    def test_direct_subject_is_prioritized_and_unrelated_official_link_is_not_followed(self):
        import wikidata,urllib.parse
        self.db.execute('DELETE FROM facts')
        self.e.fact('','山田','context',[],'Q1',self.doc,{'source':'seed','directTitle':False})
        self.e.fact('','山田','context',[],'Q2',self.doc,{'source':'seed','directTitle':True})
        fetched=[]
        def get(url,*args,**kwargs):
            q=urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['ids'][0];fetched.append(q)
            entity={'lastrevid':1,'labels':{'ja':{'value':'山田' if q=='Q2' else '無関係'}},'claims':{'P856':[{'mainsnak':{'datavalue':{'value':'https://example.org/'+q}}}]}}
            return self.doc,json.dumps({'entities':{q:entity}}).encode()
        with mock.patch.object(self.e,'fetch',side_effect=get):
            websites=wikidata.fetch(self.db,self.args,self.e,self.row,1,worker.pair,worker.reading,worker.extract_readings)
        self.assertEqual(['Q2','Q1'],fetched)
        self.assertEqual(['https://example.org/Q2'],websites)

    def test_dns_failure_is_logged_and_remains_unprocessed(self):
        with mock.patch.object(worker,'check_public_url',side_effect=OSError('DNS unavailable')):
            with self.assertRaises(OSError): self.e.fetch('https://example.org/profile',self.cid,1)
        attempt=self.db.execute('SELECT url,result,error FROM attempts ORDER BY id DESC LIMIT 1').fetchone()
        self.assertEqual(('https://example.org/profile','error','DNS unavailable'),tuple(attempt))
        self.assertEqual('queued',self.db.execute('SELECT state FROM candidates').fetchone()[0])

    def test_official_floor_structure_does_not_require_bad_floor_pronunciation(self):
        import bulk
        surface='赤坂赤坂Bizタワー(31階)'
        cid=worker.insert_candidate(self.db,'あかさかあかさかびずたわーさんじゅういっかい',surface,1,1,10,normalization='original:floor')
        self.db.execute('INSERT INTO origins VALUES(?,?,?,?,?,?,?,?,?)',('o','place',1,'あかさかあかさかびずたわーさんじゅういっかい',surface,1,1,10,'raw'))
        self.db.execute('INSERT INTO origin_candidates VALUES(?,?)',('o',cid))
        self.e.fact('あかさかあかさかびずたわー(31かい)',surface,'address-structure',[],'JapanPost:floor',self.doc,{'source':'Japan Post'})
        with contextlib.redirect_stdout(io.StringIO()): bulk.normalization(self.db,self.e,worker.fact_rows,worker.canonical,worker.info,worker.emit)
        self.assertTrue(self.db.execute("SELECT 1 FROM facts WHERE kind='invalid' AND target=?",(cid,)).fetchone())

if __name__=='__main__': unittest.main()
