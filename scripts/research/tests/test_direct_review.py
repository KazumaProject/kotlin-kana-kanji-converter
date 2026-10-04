import argparse, contextlib, copy, gzip, io, json, pathlib, sqlite3, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import worker as w
import direct_review as d
import source_rounds


class DirectReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = pathlib.Path(self.tmp.name)
        self.args = argparse.Namespace(config=str(w.DEFAULT_CONFIG), ledger=str(self.root/'ledger.sqlite'),
            documents=str(self.root/'docs'), batch_size=100, pilot_size=100, max_batches=None,
            online=False, id=None, surface=None, output=str(self.root/'reviews.json'), input=None)
        self.db = w.connect(self.args.ledger); self.db.executescript(w.SCHEMA)
        w.pin_config(self.db, self.args); w.info(self.db, 'prepared', True); w.info(self.db, 'bulkComplete', True)
        self.e = w.Evidence(self.db, self.args)
        self.doc = self.e.save('https://example.org/names', 'v1', '山田（やまだ） surname; 切嗣（きりつぐ） fictional'.encode(), 'CC0')
        self.cid = w.insert_candidate(self.db, 'やまだ', '山田', 1, 1, 10)
        self.read = self.e.fact('やまだ','山田','reading',[],'JMnedict:1',self.doc,{'source':'JMnedict','reading':'やまだ','surface':'山田','entryId':'1'})
        self.mean = self.e.fact('やまだ','山田','meaning',['person'],'JMnedict:1:0',self.doc,{'source':'JMnedict','nameTypes':['surname'],'entryId':'1','sense':0})
        self.db.commit()

    def tearDown(self):
        self.db.close(); self.tmp.cleanup()

    def row(self, cid=None):
        return dict(self.db.execute('SELECT * FROM candidates WHERE id=?',(cid or self.cid,)).fetchone())

    def state(self, cid=None):
        return self.row(cid)['state']

    def review(self):
        return {'candidateId':self.cid,'evidenceSha256':d.fingerprint(self.db,self.row()),'state':'reviewed',
                'readingEvidence':[self.read],'roles':[{'category':'person','target':'JMnedict:1:0','sense':'surname','evidenceIds':[self.mean],'method':'direct'}],
                'normalizationEvidence':[],'exclusionEvidence':[],'reason':'raw name entry checked',
                'citations':[{'evidenceId':i,'documentId':self.doc,'sha256':self.db.execute('SELECT sha256 FROM documents WHERE id=?',(self.doc,)).fetchone()[0],'quotation':'山田（やまだ） surname'} for i in (self.read,self.mean)]}

    def import_cases(self, cases):
        self.args.input=str(self.root/'import.json')
        pathlib.Path(self.args.input).write_text(json.dumps({'schemaVersion':1,'cases':cases}))
        with contextlib.redirect_stdout(io.StringIO()): d.import_reviews(self.db,self.args)

    def run(self, *args, **kwargs):
        # unittest's runner calls run(result); do not shadow it with a worker helper.
        return super().run(*args, **kwargs)

    def execute(self):
        with contextlib.redirect_stdout(io.StringIO()): return d.run(self.db,self.args)

    def test_direct_fact_completes_without_model_or_network(self):
        with mock.patch.object(w,'request_json',side_effect=AssertionError('network/model invoked')),mock.patch.object(w,'inference',side_effect=AssertionError('model invoked')):
            self.assertEqual(0,self.execute())
        self.assertEqual('reviewed',self.state())
        self.assertEqual('direct',json.loads(self.row()['decision'])['classificationRoute'])

    def test_complete_source_search_resolves_direct_evidence_and_only_closes_exhausted_rows(self):
        unresolved = w.insert_candidate(self.db, 'みなと', '港', 1, 1, 10)
        blocked = w.insert_candidate(self.db, 'たなか', '田中', 1, 1, 10)
        self.db.execute("UPDATE candidates SET state='needs_review',reason='source-review-required' WHERE id=?", (self.cid,))
        self.db.execute("UPDATE candidates SET state='needs_review',reason='meaning-or-target-unresolved' WHERE id=?", (unresolved,))
        self.db.execute("UPDATE candidates SET state='blocked',error='permanent parse failure',error_count=3 WHERE id=?", (blocked,))
        rows = list(self.db.execute('SELECT id,reading,surface FROM candidates ORDER BY id'))
        cohort, count = source_rounds.cohort_hash(rows)
        tracker = source_rounds.CorpusRoundTracker(cohort, count, 'a' * 64)
        for strategy in source_rounds.STRATEGIES:
            tracker.observe(strategy, '山田', '1', '山田（やまだ）', matches=1)
        proof = tracker.finish(eof=True, source_checksum_verified=True, main_articles_scanned=1)
        metadata = {'complete': True, 'sha256': 'a' * 64, 'completedSearchProof': proof}
        staging = self.root / 'complete.sqlite'
        stage = sqlite3.connect(staging)
        try:
            stage.execute('CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT)')
            stage.execute('INSERT INTO meta VALUES(?,?)', ('source', w.canonical(metadata)))
            stage.commit()
        finally:
            stage.close()
        w.info(self.db, 'wikiDump:' + 'a' * 64 + ':2', {'complete': True, 'source': metadata})
        self.args.source_staging = str(staging)

        result = d.complete_source_search(self.db, self.args)

        self.assertEqual(3, result)  # blocked failures remain visible
        self.assertEqual('reviewed', self.state())  # supported direct evidence is rechecked
        self.assertEqual(('not_distributed', 2), tuple(self.db.execute('SELECT state,research_round FROM candidates WHERE id=?', (unresolved,)).fetchone()))
        self.assertEqual(('blocked', 0, 'permanent parse failure'), tuple(self.db.execute('SELECT state,research_round,error FROM candidates WHERE id=?', (blocked,)).fetchone()))
        decision = json.loads(self.row(unresolved)['decision'])
        self.assertEqual(proof['cohortSha256'], self.db.execute('SELECT cohort_sha256 FROM completed_source_searches').fetchone()[0])
        self.assertEqual(w.digest(w.canonical(proof)), decision['sourceSearchProofSha256'])

    def test_raw_xml_constraint_marker_cannot_promote_a_noun_to_general(self):
        self.db.execute('DELETE FROM facts WHERE surface=?',('山田',))
        body={'source':'JMdict','entryId':'12345','reading':'やまだ','surface':'山田',
              'evidence':'https://www.edrdg.org/jmdict/edict_doc.html#entry-12345-sense-2',
              'categories':['general'],'classificationPolicy':4,'pos':['n'],'fields':[],'misc':[]}
        self.e.fact('やまだ','山田','reading',[],'12345',self.doc,{**body})
        self.e.fact('やまだ','山田','meaning',['general'],'JMdict:12345:sense:2',self.doc,body)
        with mock.patch.object(w,'request_json',side_effect=AssertionError('network/model invoked')),mock.patch.object(w,'inference',side_effect=AssertionError('model invoked')):
            self.assertEqual(3,self.execute())
        decision=json.loads(self.row()['decision'])
        self.assertEqual([],decision['roles'])
        self.assertEqual('needs_review',self.state())

    def test_reading_cannot_be_created_by_semantic_fact(self):
        self.db.execute('DELETE FROM facts WHERE id=?',(self.read,))
        self.assertEqual(3,self.execute()); self.assertEqual('needs_review',self.state())

    def test_kana_citation_selects_its_own_page_title(self):
        page={'query':{'pages':{'12':{'pageid':12,'title':'カナ','revisions':[{'revid':34,'slots':{'main':{'*':'本文'*10000}}}]}}}}
        doc=self.e.save('https://ja.wikipedia.org/w/api.php','34',w.canonical(page).encode(),'CC-BY-SA')
        fid=self.e.fact('かな','カナ','reading',[],'Q1',doc,dict(source='attested-canonical-kana',name='カナ',revision='34',acquisition={'sourcePageId':12}))
        fact=dict(self.db.execute('SELECT * FROM facts WHERE id=?',(fid,)).fetchone())
        self.assertEqual('"title":"カナ"',d.fact_citation(self.db,fact)['quotation'])
        changed=dict(fact,body=w.canonical({**json.loads(fact['body']),'revision':'35'}))
        self.assertEqual(w.canonical(page),d.fact_citation(self.db,changed)['quotation'])

    def test_withdrawing_pos_taxonomy_preserves_separate_name_role(self):
        legacy=self.e.fact('やまだ','山田','meaning',['general'],'JMdict:12345:sense:1',self.doc,
            {'source':'JMdict','classificationPolicy':4,'pos':['n'],'categories':['general']})
        decision=self.review();decision['roles'].append({'category':'general','target':'JMdict:12345:sense:1',
            'sense':'legacy noun','method':'direct','evidenceIds':[legacy]})
        decision['classificationRoute']='direct'
        d.write_decision(self.db,self.row(),'reviewed','fixture',decision)
        d.retire_legacy_jmdict_categories(self.db)
        final=json.loads(self.row()['decision'])
        self.assertEqual('reviewed',self.state())
        self.assertEqual([('person','JMnedict:1:0')],[(r['category'],r['target']) for r in final['roles']])
        self.assertEqual(1,w.info(self.db,'legacyJmdictTaxonomyWithdrawn')['roles'])
        self.assertEqual(1,self.db.execute('SELECT COUNT(*) FROM decision_history').fetchone()[0])

    def test_broad_place_tag_is_not_automatic_place_classification(self):
        self.db.execute("UPDATE facts SET categories='[\"place\"]',body=? WHERE id=?",(json.dumps({'source':'JMnedict','nameTypes':['place']}),self.mean))
        self.assertEqual(3,self.execute()); self.assertEqual('needs_review',self.state())

    def test_precise_jmnedict_geographic_sense_resolves_with_same_entry_reading(self):
        cid=w.insert_candidate(self.db,'あいおんとう','アイオン島',1,1,10)
        document=self.e.save('https://example.org/jmnedict/aion','v1','<entry>アイオン島 あいおんとう Ostrov Aion (island)</entry>'.encode(),'CC0')
        self.e.fact('あいおんとう','アイオン島','reading',[],'JMnedict:5008476',document,
                    {'source':'JMnedict','entryId':'5008476','reading':'あいおんとう','surface':'アイオン島','re_restr':['アイオン島']})
        self.e.fact('あいおんとう','アイオン島','meaning',['place'],'JMnedict:5008476:0',document,
                    {'source':'JMnedict','entryId':'5008476','sense':0,'nameTypes':['place'],
                     'translations':[['Ostrov Aion (island)']]})
        self.assertTrue(d.resolve(self.db,self.row(cid)))
        decision=json.loads(self.row(cid)['decision'])
        self.assertEqual('reviewed',self.state(cid))
        self.assertEqual([('place','JMnedict:5008476:0')],[(r['category'],r['target']) for r in decision['roles']])

    def test_jmnedict_myth_tag_needs_explicit_individual_definition(self):
        cid=w.insert_candidate(self.db,'じょか','女媧',1,1,10)
        document=self.e.save('https://example.org/jmnedict/nuwa','v1','<entry>女媧 じょか Nüwa (mother goddess of Chinese mythology)</entry>'.encode(),'CC0')
        self.e.fact('じょか','女媧','reading',[],'JMnedict:5740220',document,
                    {'source':'JMnedict','entryId':'5740220','reading':'じょか','surface':'女媧','re_restr':['女媧']})
        self.e.fact('じょか','女媧','meaning',[],'JMnedict:5740220:0',document,
                    {'source':'JMnedict','entryId':'5740220','sense':0,'nameTypes':['myth'],
                     'translations':[['Nüwa (mother goddess of Chinese mythology)']]})
        self.assertTrue(d.resolve(self.db,self.row(cid)))
        decision=json.loads(self.row(cid)['decision'])
        self.assertEqual([('character','JMnedict:5740220:0')],[(r['category'],r['target']) for r in decision['roles']])

    def test_jmnedict_exact_geographic_rule_does_not_adopt_derived_spelling(self):
        cid=w.insert_candidate(self.db,'あいおんとう','アイオン島',1,1,10)
        self.db.execute("UPDATE candidates SET normalization='derived-parenthesis-removal' WHERE id=?",(cid,))
        document=self.e.save('https://example.org/jmnedict/aion-derived','v1','<entry>アイオン島 あいおんとう Ostrov Aion (island)</entry>'.encode(),'CC0')
        self.e.fact('あいおんとう','アイオン島','reading',[],'JMnedict:5008476',document,
                    {'source':'JMnedict','entryId':'5008476','reading':'あいおんとう','surface':'アイオン島','re_restr':['アイオン島']})
        self.e.fact('あいおんとう','アイオン島','meaning',['place'],'JMnedict:5008476:0',document,
                    {'source':'JMnedict','entryId':'5008476','sense':0,'nameTypes':['place'],
                     'translations':[['Ostrov Aion (island)']]})
        self.assertFalse(d.resolve(self.db,self.row(cid)))
        self.assertEqual('needs_review',self.state(cid))
        self.assertEqual([],json.loads(self.row(cid)['decision'])['roles'])

    def test_jmnedict_rule_version_invalidates_only_bound_geographic_pairs(self):
        cid=w.insert_candidate(self.db,'あいおんとう','アイオン島',1,1,10)
        document=self.e.save('https://example.org/jmnedict/aion-invalidation','v1','<entry>Ostrov Aion (island)</entry>'.encode(),'CC0')
        self.e.fact('あいおんとう','アイオン島','reading',[],'JMnedict:5008476',document,
                    {'source':'JMnedict','entryId':'5008476','reading':'あいおんとう','surface':'アイオン島','re_restr':['アイオン島']})
        self.e.fact('あいおんとう','アイオン島','meaning',['place'],'JMnedict:5008476:0',document,
                    {'source':'JMnedict','entryId':'5008476','sense':0,'nameTypes':['place'],
                     'translations':[['Ostrov Aion (island)']]})
        old=w.configuration(self.args)[-1]; new=copy.deepcopy(old)
        old['stages']['directRules']=5; new['stages']['directRules']=6
        d.invalidate_configuration(self.db,old,new)
        self.assertEqual(1,w.info(self.db,'lastInvalidation')['candidates'])
        self.assertEqual('queued',self.row(cid)['state'])

    def test_fictional_name_is_character_not_real_person(self):
        cid=w.insert_candidate(self.db,'きりつぐ','切嗣',1,1,10)
        self.e.fact('きりつぐ','切嗣','reading',[],'JMnedict:2',self.doc,{'source':'JMnedict'})
        self.e.fact('きりつぐ','切嗣','meaning',['character'],'JMnedict:2:0',self.doc,{'source':'JMnedict','nameTypes':['masc','fict']})
        self.execute(); self.assertEqual(['character'],[r['category'] for r in json.loads(self.row(cid)['decision'])['roles']])

    def test_wikidata_human_type_needs_exact_name_and_same_item_reading(self):
        self.db.execute('DELETE FROM facts WHERE id IN (?,?)',(self.read,self.mean))
        self.e.fact('やまだ','山田','reading',[],'Q100',self.doc,
                    {'source':'explicit-name-reading','name':'山田','reading':'やまだ'})
        self.e.fact('','山田','context',[],'Q100',self.doc,
                    {'source':'Wikidata','id':'Q100','label':'山田','title':'山田',
                     'nameBoundReadings':{'山田':['やま だ']},'types':['Q5']})
        self.assertEqual(0,self.execute())
        decision=json.loads(self.row()['decision'])
        self.assertEqual([('person','Q100')],[(r['category'],r['target']) for r in decision['roles']])

    def test_wikidata_fictional_character_type_overrides_human_type(self):
        self.db.execute('DELETE FROM facts WHERE id IN (?,?)',(self.read,self.mean))
        self.e.fact('やまだ','山田','reading',[],'Q101',self.doc,
                    {'source':'explicit-name-reading','name':'山田','reading':'やまだ'})
        self.e.fact('','山田','context',[],'Q101',self.doc,
                    {'source':'Wikidata','id':'Q101','label':'山田','title':'山田',
                     'nameBoundReadings':{'山田':['やまだ']},'types':['Q5','Q95074']})
        self.assertEqual(0,self.execute())
        decision=json.loads(self.row()['decision'])
        self.assertEqual([('character','Q101')],[(r['category'],r['target']) for r in decision['roles']])

    def test_wikidata_type_without_same_item_reading_stays_pending(self):
        self.db.execute('DELETE FROM facts WHERE id IN (?,?)',(self.read,self.mean))
        self.e.fact('やまだ','山田','reading',[],'OtherItem',self.doc,
                    {'source':'JMdict','reading':'やまだ','surface':'山田'})
        self.e.fact('','山田','context',[],'Q102',self.doc,
                    {'source':'Wikidata','id':'Q102','label':'山田','title':'山田',
                     'nameBoundReadings':{'山田':['やまだ']},'types':['Q5']})
        self.assertEqual(3,self.execute())
        self.assertEqual('needs_review',self.state())
        self.assertEqual([],json.loads(self.row()['decision'])['roles'])

    def test_transformation_needs_its_own_candidate_bound_proof(self):
        self.db.execute("UPDATE candidates SET normalization='split' WHERE id=?",(self.cid,))
        self.assertEqual(3,self.execute()); self.assertEqual('needs_review',self.state())
        self.e.fact('やまだ','山田','normalization',[],'another-id',self.doc,{'originalSurface':'山田(本町)'})
        self.assertFalse(d.resolve(self.db,self.row()))
        self.e.fact('やまだ','山田','normalization',[],self.cid,self.doc,{'originalSurface':'山田(本町)'})
        self.assertTrue(d.resolve(self.db,self.row()))

    def test_confirmed_invalid_structure_needs_no_model(self):
        self.e.fact('やまだ','山田','invalid',[],self.cid,self.doc,{'issue':'postal-annotation-not-independent-candidate'})
        self.assertEqual(0,self.execute()); self.assertEqual('excluded_confirmed',self.state())

    def test_status_reading_discovery_uses_only_active_exact_pair_facts(self):
        self.db.execute('INSERT INTO pilot VALUES(?,?)',(self.cid,'fixture'))
        baseline={'cases':[{'id':self.cid,'readingEvidenceIds':[]}]}
        self.assertEqual(1,d.reading_discoveries(self.db,baseline))
        self.db.execute('UPDATE facts SET active=0 WHERE id=?',(self.read,))
        self.assertEqual(0,d.reading_discoveries(self.db,baseline))
        self.assertIsNone(d.reading_discoveries(self.db,{'cases':[]}))

    def test_fact_pair_lookup_uses_surface_reading_index(self):
        plan=self.db.execute('EXPLAIN QUERY PLAN '+w.FACT_ROWS_SQL,('やまだ','山田')).fetchall()
        self.assertIn('fact_pair',' '.join(row[3] for row in plan))
        self.assertEqual({self.read,self.mean},{f['id'] for f in w.fact_rows(self.db,self.row())})

    def test_permanent_parse_failure_is_blocked_and_worker_returns(self):
        self.db.execute('DELETE FROM facts WHERE id=?',(self.mean,)); self.args.online=True
        with mock.patch.object(w,'research',side_effect=ValueError('unsupported document')) as fetch,mock.patch.object(d.time,'sleep',side_effect=AssertionError('waiting forever')):
            self.assertEqual(3,self.execute()); self.assertEqual('blocked',self.state())
            self.assertEqual(3,self.execute()); self.assertEqual(1,fetch.call_count)

    def test_transient_failure_has_three_attempt_limit(self):
        self.db.execute('DELETE FROM facts WHERE id=?',(self.mean,)); self.args.online=True
        with mock.patch.object(w,'research',side_effect=OSError('connection stopped')) as fetch:
            for attempt in range(3):
                self.db.execute('UPDATE candidates SET next_retry=0 WHERE id=?',(self.cid,))
                self.assertEqual(3,self.execute())
            self.assertEqual('blocked',self.state()); self.assertEqual(3,fetch.call_count)
            self.execute(); self.assertEqual(3,fetch.call_count)

    def test_future_retry_returns_immediately_without_http(self):
        self.db.execute('DELETE FROM facts WHERE id=?',(self.mean,)); self.args.online=True
        self.db.execute("UPDATE candidates SET state='error',next_retry=99999999999 WHERE id=?",(self.cid,))
        with mock.patch.object(w,'research',side_effect=AssertionError('early retry')):
            self.assertEqual(3,self.execute())

    def test_http_success_with_service_error_is_transient_and_not_cached(self):
        url='https://ja.wikipedia.org/w/api.php?action=query'
        response=mock.MagicMock();response.__enter__.return_value=response;response.url=url
        response.read.return_value=b'{"error":{"code":"maxlag","info":"temporary replication lag"}}'
        opener=mock.Mock();opener.open.return_value=response
        with mock.patch.object(w,'check_public_url'),mock.patch.object(w.urllib.request,'build_opener',return_value=opener),mock.patch.object(w.time,'sleep'):
            with self.assertRaises(OSError):self.e.fetch(url,self.cid,1)
        self.assertEqual(0,self.db.execute("SELECT COUNT(*) FROM attempts WHERE result='success' AND url=?",(url,)).fetchone()[0])
        self.assertEqual(1,self.db.execute("SELECT COUNT(*) FROM attempts WHERE result='error' AND url=?",(url,)).fetchone()[0])
        self.assertEqual('error',d.mark_error(self.db,self.cid,OSError('maxlag')))

    def test_old_temporary_api_cache_can_recover_without_discarding_document(self):
        url='https://ja.wikipedia.org/w/api.php?action=query'
        did=self.e.save(url,'v1',b'{"error":{"code":"maxlag"}}','CC0')
        self.db.execute('INSERT INTO attempts(candidate_id,round,url,result,document_id) VALUES(?,?,?,?,?)',(self.cid,1,url,'success',did))
        response=mock.MagicMock();response.__enter__.return_value=response;response.url=url;response.read.return_value=b'{"query":{"search":[]}}'
        opener=mock.Mock();opener.open.return_value=response
        with mock.patch.object(w,'check_public_url'),mock.patch.object(w.urllib.request,'build_opener',return_value=opener),mock.patch.object(w.time,'sleep'):
            recovered,data=self.e.fetch(url,self.cid,1)
        self.assertNotEqual(did,recovered);self.assertIn(b'query',data)
        self.assertEqual(1,self.db.execute("SELECT COUNT(*) FROM attempts WHERE result='invalid-api' AND document_id=?",(did,)).fetchone()[0])
        self.assertIsNotNone(self.db.execute('SELECT 1 FROM documents WHERE id=?',(did,)).fetchone())

    def test_stopping_and_resuming_does_not_reprocess_completed_candidate(self):
        second=w.insert_candidate(self.db,'やまだ','山田',2,2,10)
        self.args.batch_size=1;self.args.max_batches=1
        self.assertEqual(3,self.execute())
        self.assertEqual(0,self.execute())
        with mock.patch.object(d,'resolve',side_effect=AssertionError('completed case reprocessed')):
            self.assertEqual(0,self.execute())
        self.assertEqual('reviewed',self.state(second))

    def test_packaging_and_logging_fingerprint_change_preserves_progress(self):
        d.resolve(self.db,self.row());old=w.info(self.db,'configuration');old['worker']='old byte hash';w.info(self.db,'configuration',old)
        w.pin_config(self.db,self.args);self.assertEqual('reviewed',self.state())
        self.assertEqual(0,w.info(self.db,'lastInvalidation')['candidates'])

    def test_model_change_does_not_reset_direct_resolution(self):
        d.resolve(self.db,self.row());old=w.info(self.db,'configuration');old['models']['proposer']['digest']='other';w.info(self.db,'configuration',old)
        w.pin_config(self.db,self.args);self.assertEqual('reviewed',self.state())

    def test_publication_change_invalidates_acceptance_only(self):
        d.resolve(self.db,self.row());w.info(self.db,'acceptance',{'passed':True})
        old=w.info(self.db,'configuration');old['stages']['publication']=1;w.info(self.db,'configuration',old)
        w.pin_config(self.db,self.args);self.assertEqual('reviewed',self.state());self.assertIsNone(w.info(self.db,'acceptance'))

    def test_publication_floor_change_preserves_judgments_and_gold(self):
        d.resolve(self.db,self.row());w.info(self.db,'goldFrozen',{'sha256':'fixture','cases':[]})
        w.info(self.db,'acceptance',{'passed':True})
        old=w.info(self.db,'configuration');old['taxonomy']['categories'][0]['minimum']+=1
        w.info(self.db,'configuration',old);w.pin_config(self.db,self.args)
        self.assertEqual('reviewed',self.state());self.assertIsNotNone(w.info(self.db,'goldFrozen'))
        self.assertIsNone(w.info(self.db,'acceptance'))

    def test_direct_rule_change_invalidates_mixed_manual_resolution(self):
        d.resolve(self.db,self.row());decision=json.loads(self.row()['decision'])
        decision['classificationRoute']='source_review';decision['roles'].append({**decision['roles'][0], 'method':'source_review'})
        self.db.execute('UPDATE candidates SET decision=? WHERE id=?',(w.canonical(decision),self.cid))
        old=w.info(self.db,'configuration');old['stages']['directRules']=0;w.info(self.db,'configuration',old)
        w.pin_config(self.db,self.args);self.assertEqual('queued',self.state())

    def test_wikidata_type_rule_requeues_only_exact_name_and_reading_pairs(self):
        second=w.insert_candidate(self.db,'きりつぐ','切嗣',1,1,10)
        self.e.fact('やまだ','山田','reading',[],'Q103',self.doc,
                    {'source':'explicit-name-reading','name':'山田','reading':'やまだ'})
        self.e.fact('','山田','context',[],'Q103',self.doc,
                    {'source':'Wikidata','id':'Q103','label':'山田','title':'山田',
                     'nameBoundReadings':{'山田':['やまだ']},'types':['Q5']})
        self.e.fact('きりつぐ','切嗣','reading',[],'Q104',self.doc,
                    {'source':'explicit-name-reading','name':'切嗣','reading':'きりつぐ'})
        self.e.fact('','切嗣','context',[],'Q104',self.doc,
                    {'source':'Wikidata','id':'Q104','label':'切嗣','title':'切嗣',
                     'nameBoundReadings':{'切嗣':['きりつぐ']},'types':['Q5']})
        self.db.execute("UPDATE candidates SET state='reviewed',decision=? WHERE id=?",
                        (json.dumps({'classificationRoute':'direct','roles':[]}),self.cid))
        self.db.execute("UPDATE candidates SET state='reviewed',decision=? WHERE id=?",
                        (json.dumps({'classificationRoute':'source_review','roles':[]}),second))
        old=w.info(self.db,'configuration');old['stages']['directRules']=1
        w.info(self.db,'configuration',old)
        w.pin_config(self.db,self.args)
        self.assertEqual('queued',self.state())
        self.assertEqual('reviewed',self.state(second))
        self.assertEqual(1,w.info(self.db,'lastInvalidation')['candidates'])

    def test_verified_jmdict_rule_requeues_only_supported_unresolved_pairs(self):
        manual=w.insert_candidate(self.db,'きりつぐ','切嗣',1,1,10)
        unrelated=w.insert_candidate(self.db,'あゆみ','歩',1,1,10)
        for y,s,entry in [('やまだ','山田','12345'),('きりつぐ','切嗣','67890')]:
            body={'source':'JMdict','entryId':entry,'reading':y,'surface':s,'classificationPolicy':4,
                  'evidence':f'https://www.edrdg.org/jmdict/edict_doc.html#entry-{entry}-sense-1',
                  'categories':['general'],'pos':['n'],'fields':[],'misc':[]}
            self.e.fact(y,s,'reading',[],entry,self.doc,body)
            self.e.fact(y,s,'meaning',['general'],f'JMdict:{entry}:sense:1',self.doc,body)
        self.db.execute("UPDATE candidates SET state='needs_review',reason='meaning-or-target-unresolved'")
        self.db.execute("UPDATE candidates SET state='reviewed',decision=? WHERE id=?",
                        (json.dumps({'classificationRoute':'source_review','roles':[]}),manual))
        self.db.execute("UPDATE candidates SET state='reviewed',decision='{}' WHERE id=?",(unrelated,))
        old=w.info(self.db,'configuration');old['stages']['directRules']=4
        new=copy.deepcopy(old);new['stages']['directRules']=5
        d.invalidate_configuration(self.db,old,new)
        self.assertEqual('queued',self.state())
        self.assertEqual('reviewed',self.state(manual))
        self.assertEqual('reviewed',self.state(unrelated))
        self.assertEqual(1,w.info(self.db,'lastInvalidation')['candidates'])

    def test_parser_change_only_invalidates_its_own_pairs(self):
        second=w.insert_candidate(self.db,'きりつぐ','切嗣',1,1,10)
        self.e.fact('きりつぐ','切嗣','reading',[],'Q2',self.doc,{'source':'explicit-name-reading'})
        self.db.execute("UPDATE candidates SET state='reviewed',decision='{}' WHERE id=?",(second,))
        d.resolve(self.db,self.row());old=w.info(self.db,'configuration');old['stages']['onlineReadingParser']=3;w.info(self.db,'configuration',old)
        w.pin_config(self.db,self.args);self.assertEqual('reviewed',self.state());self.assertEqual('queued',self.state(second))
        self.assertGreater(self.db.execute('SELECT COUNT(*) FROM decision_history').fetchone()[0],0)

    def test_import_with_real_bound_quotes(self):
        self.import_cases([self.review()]);self.assertEqual('reviewed',self.state())

    def wiki_source_review(self):
        target='テスト作品#mentioned-name:山田'
        quote='山田（やまだ）は本作の登場人物。'
        content='== 登場人物 ==\n'+quote+'\n'
        payload={'query':{'pages':{'123':{'pageid':123,'title':'テスト作品','revisions':[{'revid':456,'slots':{'main':{'*':content}}}]}}}}
        url='https://dumps.wikimedia.org/jawiki/20261001/test.xml.bz2#matched-pages-123-123'
        doc=self.e.save(url,'dump-revision',gzip.compress(json.dumps(payload,ensure_ascii=False).encode()),'Wikimedia dump')
        read=self.e.fact('やまだ','山田','reading',[],target,doc,
                         {'source':'explicit-name-reading','name':'山田','reading':'やまだ','quotation':'山田（やまだ）'})
        item={'target':target,'documentId':doc,
              'sha256':self.db.execute('SELECT sha256 FROM documents WHERE id=?',(doc,)).fetchone()[0],
              'source':'Wikipedia','title':'テスト作品','pageId':123,'revision':456,'quotation':quote}
        source_fact=d.validate_source_facts(self.db,self.row(),[item])[0]
        case=self.review()
        case.update(evidenceSha256=d.fingerprint(self.db,self.row()),readingEvidence=[read],
                    roles=[{'category':'character','target':target,'sense':'登場人物','evidenceIds':[source_fact['id']],
                            'method':'source_review'}],
                    citations=[{'evidenceId':read,'documentId':doc,'sha256':item['sha256'],'quotation':'山田（やまだ）'},
                               {'evidenceId':source_fact['id'],'documentId':doc,'sha256':item['sha256'],'quotation':quote}],
                    sourceFacts=[item])
        return case,source_fact['id']

    def test_import_adds_page_bound_wikipedia_context_fact(self):
        case,fid=self.wiki_source_review()
        self.import_cases([case])
        self.assertEqual('reviewed',self.state())
        fact=self.db.execute('SELECT * FROM facts WHERE id=?',(fid,)).fetchone()
        self.assertIsNotNone(fact)
        decision=json.loads(self.row()['decision'])
        self.assertEqual(d.fingerprint(self.db,self.row()),decision['evidenceSha256'])
        self.assertEqual('source_review',decision['classificationRoute'])

    def test_invalid_new_source_fact_does_not_partially_import(self):
        case,_=self.wiki_source_review();case['sourceFacts'][0]['revision']=999
        with self.assertRaisesRegex(ValueError,'revision'):
            self.import_cases([case])
        self.assertEqual('queued',self.state())
        self.assertEqual(0,self.db.execute("SELECT COUNT(*) FROM facts WHERE kind='context' AND surface='山田'").fetchone()[0])

    def test_reading_parser_change_preserves_wikidata_primary_kana(self):
        cid=w.insert_candidate(self.db,'すがやあゆみ','すがやあゆみ',1,1,10)
        fid=self.e.fact('すがやあゆみ','すがやあゆみ','reading',[],'Q1',self.doc,
                        {'source':'attested-canonical-kana','binding':'Wikidata primary Japanese name'})
        self.db.execute("UPDATE candidates SET state='needs_review',decision='{}' WHERE id=?",(cid,))
        old=w.info(self.db,'configuration');old['stages']['onlineReadingParser']=3;w.info(self.db,'configuration',old)
        w.pin_config(self.db,self.args)
        self.assertEqual(1,self.db.execute('SELECT active FROM facts WHERE id=?',(fid,)).fetchone()[0])
        self.assertEqual('needs_review',self.state(cid))

    def test_replaced_provider_only_requeues_related_candidates(self):
        d.resolve(self.db,self.row())
        cid=w.insert_candidate(self.db,'きりつぐ','切嗣',1,1,10)
        self.db.execute("UPDATE candidates SET state='reviewed',decision='{}' WHERE id=?",(cid,))
        self.db.execute('UPDATE candidates SET research_round=2,error_count=2 WHERE id=?',(self.cid,))
        d.retire_provider(self.db,'JMnedict')
        self.assertEqual('queued',self.state());self.assertEqual('reviewed',self.state(cid))
        self.assertEqual(2,self.row()['research_round']);self.assertEqual(2,self.row()['error_count'])
        self.assertEqual(0,self.db.execute('SELECT active FROM facts WHERE id=?',(self.read,)).fetchone()[0])
        self.assertGreater(self.db.execute('SELECT COUNT(*) FROM decision_history').fetchone()[0],0)

    def test_new_inconclusive_evidence_does_not_erase_operational_failure(self):
        self.db.execute('DELETE FROM facts WHERE id=?',(self.mean,));d.resolve(self.db,self.row())
        d.mark_error(self.db,self.cid,ValueError('parser failure'))
        self.e.fact('やまだ','山田','context',[],'Q1',self.doc,{'source':'unrelated-context'})
        d.resolve(self.db,self.row())
        self.assertIsNotNone(self.row()['error']);self.assertEqual('blocked',self.state())

    def test_retired_component_invalidates_dependent_boundaries_only(self):
        cid=w.insert_candidate(self.db,'かせっと','カセット',1,1,10,normalization='split')
        fid=self.e.fact('かせっと','カセット','normalization',[],cid,self.doc,
                        {'componentFacts':[self.read],'originalSurface':'山田(カセット)'})
        self.db.execute("UPDATE candidates SET state='reviewed',decision='{}' WHERE id=?",(cid,))
        other=w.insert_candidate(self.db,'あゆみ','あゆみ',1,1,10)
        self.db.execute("UPDATE candidates SET state='reviewed',decision='{}' WHERE id=?",(other,))
        d.retire_provider(self.db,'JMnedict')
        self.assertEqual(0,self.db.execute('SELECT active FROM facts WHERE id=?',(fid,)).fetchone()[0])
        self.assertEqual('queued',self.state(cid));self.assertEqual('reviewed',self.state(other))

    def test_online_first_round_proof_stops_further_research(self):
        self.db.execute('DELETE FROM facts WHERE id=?',(self.mean,));self.args.online=True
        def research(db,args,row,proposal,round_no):
            self.e.fact('やまだ','山田','meaning',['person'],'JMnedict:1:0',self.doc,
                        {'source':'JMnedict','nameTypes':['surname'],'entryId':'1','sense':0})
            db.execute('UPDATE candidates SET research_round=? WHERE id=?',(round_no,self.cid))
        with mock.patch.object(w,'research',side_effect=research) as fetch:
            self.assertEqual(0,self.execute());self.assertEqual(1,fetch.call_count)
        self.assertEqual(1,self.row()['research_round'])

    def test_obsolete_underlying_proof_cannot_support_a_boundary(self):
        self.db.execute("UPDATE candidates SET normalization='split' WHERE id=?",(self.cid,))
        other=self.e.fact('きりつぐ','切嗣','reading',[],'Q2',self.doc,{'source':'obsolete-reference'})
        self.e.fact('やまだ','山田','normalization',[],self.cid,self.doc,{'componentFacts':[other]})
        self.db.execute('UPDATE facts SET active=0 WHERE id=?',(other,))
        self.assertEqual(3,self.execute());self.assertEqual('blocked',self.state())

    def test_rebuilding_boundaries_cannot_substitute_different_original_input(self):
        import rescue
        self.args.source_dir=str(self.root);(self.root/'place.txt.zip').write_bytes(b'changed source')
        w.info(self.db,'inputs',{'sources':{'place':'0'*64}})
        self.db.execute('INSERT INTO origins VALUES(?,?,?,?,?,?,?,?,?)',('o1','place',1,'やまだ','山田(その他)',1,1,10,'raw'))
        self.db.execute('INSERT INTO normalization VALUES(?,?,?,?,?,?,?,?,?)',('place',1,'やまだ','山田',1,1,10,'ok','split'))
        with self.assertRaisesRegex(ValueError,'checksum changed'):
            rescue.apply(self.db,self.args,self.e,w.insert_candidate,w.info,w.emit)

    def test_reparse_corrupt_source_blocks_one_pair_and_continues(self):
        # The saved-document parser must not abort the whole ledger at one bad article.
        cid=w.insert_candidate(self.db,'きりつぐ','切嗣',1,1,10)
        doc=self.e.save('https://example.org/bad-json','v1',b'{bad-json','CC0')
        self.e.fact('きりつぐ','切嗣','context',[],'Q2',doc,{'source':'Wikipedia'})
        w.info(self.db,'onlineReadingsNeedReparse',True)
        d.reparse_saved_readings(self.db,self.args)
        self.assertEqual('blocked',self.state(cid));self.assertEqual('queued',self.state())
        self.assertTrue(d.resolve(self.db,self.row()))

    def test_fabricated_quote_and_stale_evidence_are_rejected(self):
        case=self.review();case['citations'][0]['quotation']='fabricated quote'
        with self.assertRaisesRegex(ValueError,'quotation'):self.import_cases([case])
        case=self.review();self.e.fact('やまだ','山田','context',[],'JMnedict:1:0',self.doc,{'additional':'data'})
        with self.assertRaisesRegex(ValueError,'Stale'):self.import_cases([case])

    def test_inferred_labels_cannot_claim_direct_method(self):
        case=self.review();self.db.execute('UPDATE facts SET body=? WHERE id=?',(json.dumps({'source':'official-profile'}),self.mean))
        case['evidenceSha256']=d.fingerprint(self.db,self.row())
        with self.assertRaisesRegex(ValueError,'direct provenance'):self.import_cases([case])
        case['roles'][0]['method']='source_review';self.import_cases([case]);self.assertEqual('source_review',json.loads(self.row()['decision'])['classificationRoute'])

    def test_review_cannot_adopt_without_reading_or_exclusion_proof(self):
        case=self.review();case['readingEvidence']=[];case['citations']=case['citations'][1:]
        with self.assertRaisesRegex(ValueError,'independent reading'):self.import_cases([case])
        case=self.review();case['state']='excluded_confirmed'
        with self.assertRaisesRegex(ValueError,'invalidity proof'):self.import_cases([case])

    def test_non_distribution_requires_completed_research_and_no_failures(self):
        case=self.review();case['state']='not_distributed'
        with self.assertRaisesRegex(ValueError,'two completed'):self.import_cases([case])
        self.db.execute("UPDATE candidates SET research_round=2,state='blocked' WHERE id=?",(self.cid,));case['evidenceSha256']=d.fingerprint(self.db,self.row())
        with self.assertRaisesRegex(ValueError,'Operational failure'):self.import_cases([case])

    def test_inconclusive_import_cannot_launder_operational_failure(self):
        self.db.execute("UPDATE candidates SET research_round=2,state='blocked',error='permanent parser failure' WHERE id=?",(self.cid,))
        case=self.review();case.update(state='needs_review',readingEvidence=[],roles=[],citations=[])
        with self.assertRaisesRegex(ValueError,'Inconclusive'):self.import_cases([case])
        self.assertEqual('blocked',self.state());self.assertIsNotNone(self.row()['error'])

    def test_import_is_atomic_when_later_case_is_invalid(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):self.import_cases([self.review(),self.review()])
        self.assertEqual('queued',self.state())

    def test_raw_document_corruption_blocks_adoption(self):
        doc=self.db.execute('SELECT path FROM documents WHERE id=?',(self.doc,)).fetchone()[0]
        pathlib.Path(doc).write_text('corrupt')
        self.assertEqual(3,self.execute());self.assertEqual('blocked',self.state())

    def test_review_export_can_be_edited_and_imported(self):
        self.args.id=self.cid
        with contextlib.redirect_stdout(io.StringIO()):d.export_reviews(self.db,self.args)
        value=json.loads(pathlib.Path(self.args.output).read_text());case=value['cases'][0];case.update(self.review())
        self.import_cases([case]);self.assertEqual('reviewed',self.state())

    def test_inconclusive_inspection_persists_citations_and_reason(self):
        review=self.review()
        review.update(state='needs_review',readingEvidence=[],roles=[],inspectionEvidence=[self.read,self.mean],
                      reason='JMnedict marks the target unclassified; category is unresolved')
        self.import_cases([review])
        self.assertEqual('needs_review',self.state())
        decision=json.loads(self.row()['decision'])
        self.assertIsNone(decision['classificationRoute'])
        self.assertEqual([self.read,self.mean],decision['inspectionEvidence'])
        self.assertEqual(2,len(decision['citations']))
        self.args.id=self.cid
        with contextlib.redirect_stdout(io.StringIO()):d.export_reviews(self.db,self.args)
        exported=json.loads(pathlib.Path(self.args.output).read_text())['cases'][0]
        self.assertEqual(decision['inspectionEvidence'],exported['inspectionEvidence'])
        self.assertEqual(decision['citations'],exported['citations'])
        self.assertEqual('JMnedict marks the target unclassified; category is unresolved',exported['reason'])

    def test_inspection_only_citations_cannot_complete_a_review(self):
        review=self.review()
        review.update(state='reviewed',readingEvidence=[],roles=[],inspectionEvidence=[self.read,self.mean],
                      reason='Inspection alone is not classification')
        self.args.input=str(self.root/'invalid-inspection-only.json')
        pathlib.Path(self.args.input).write_text(json.dumps({'schemaVersion':1,'cases':[review]}))
        with self.assertRaisesRegex(ValueError,'Inspection-only evidence cannot complete'):
            d.import_reviews(self.db,self.args)
        self.assertEqual('queued',self.state())

    def test_reason_batch_cursor_advances_without_discarding_unresolved_cases(self):
        ids=[self.cid]
        for n in range(2): ids.append(w.insert_candidate(self.db,'な'+str(n),'名'+str(n),1,1,10))
        self.db.execute("UPDATE candidates SET state='needs_review',reason='reading-evidence-insufficient'")
        ids.sort();self.args.reason='reading-evidence-insufficient';self.args.batch_size=1
        found=[]
        for _ in range(3):
            with contextlib.redirect_stdout(io.StringIO()):d.export_reviews(self.db,self.args)
            case=json.loads(pathlib.Path(self.args.output).read_text())['cases'][0]
            found.append(case['candidateId']);self.args.after_id=case['candidateId']
        self.assertEqual(ids,found)
        self.assertEqual(3,self.db.execute("SELECT COUNT(*) FROM candidates WHERE state='needs_review'").fetchone()[0])


if __name__ == '__main__': unittest.main()
