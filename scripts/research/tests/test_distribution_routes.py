"""Offline synthetic fixtures for route validation; never production gold."""
import argparse,contextlib,io,json,pathlib,sqlite3,sys,tempfile,unittest
from unittest import mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import distribution,worker

class DistributionRoutesTest(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.db.execute('CREATE TABLE candidates(id TEXT PRIMARY KEY,state TEXT,decision TEXT)')
        self.db.execute("CREATE TABLE facts(id TEXT PRIMARY KEY,active INTEGER,kind TEXT DEFAULT 'reading',body TEXT DEFAULT '{}',target TEXT)")
        self.gold={'sha256':'a'*64,'cases':[]};self.serial=0
    def tearDown(self): self.db.close()
    def add(self,method='direct',count=1,gold=True,category='person',wrong=False,state='reviewed',legacy=False):
        for _ in range(count):
            self.serial+=1;cid=str(self.serial);target='target:'+cid
            role={'method':method,'category':category if not wrong else 'work','target':target,'evidenceIds':['m'+cid]}
            decision={'roles':[role],'readingEvidence':['r'+cid]}
            self.db.executemany('INSERT INTO facts(id,active) VALUES(?,1)',[('r'+cid,),('m'+cid,)])
            self.db.execute("UPDATE facts SET kind='meaning',target=? WHERE id=?",(target,'m'+cid))
            if legacy: decision['classificationRoute']=role.pop('method')
            self.db.execute('INSERT INTO candidates VALUES(?,?,?)',(cid,state,json.dumps(decision)))
            if gold: self.gold['cases'].append({'candidateId':cid,'split':'validation','eligible':True,'categories':[category],'target':target})
        return cid
    def gate(self,active=None):
        return distribution.precision(self.db,lambda db,key:self.gold,worker.confidence_lower,worker.canonical,active)
    def test_direct_only_needs_no_artificial_model_sample(self):
        self.add();gate=self.gate()
        self.assertEqual({'correct':1,'n':1,'population':1},gate['precision']['direct'])
        self.assertEqual(0,gate['precision']['ai']['n']);self.assertEqual(0,gate['precision']['source_review']['n'])
        distribution.verify_precision_report(gate,{'direct':1})
    def test_source_review_can_pass_without_models(self):
        self.add('source_review',300);gate=self.gate()
        self.assertGreaterEqual(gate['precision']['source_review']['lower95'],.99)
        distribution.verify_precision_report(gate,{'source_review':300})
    def test_models_retain_the_existing_precision_gate(self):
        self.add('ai',300);distribution.verify_precision_report(self.gate(),{'ai':300})
    def test_precision_rejects_inactive_selected_proof_before_gold_scoring(self):
        self.add();self.db.execute("UPDATE facts SET active=0 WHERE id='r1'")
        with self.assertRaisesRegex(ValueError,'inactive selected evidence'): self.gate()
        self.db.execute("UPDATE facts SET active=1 WHERE id='r1'")
        self.db.execute("UPDATE facts SET active=0 WHERE id='m1'")
        with self.assertRaisesRegex(ValueError,'inactive selected evidence'): self.gate()
    def test_selected_quality_proof_must_also_be_active(self):
        cid=self.add();self.db.execute("INSERT INTO facts(id,active) VALUES('normalization',0)")
        decision=json.loads(self.db.execute('SELECT decision FROM candidates WHERE id=?',(cid,)).fetchone()[0])
        decision['normalizationEvidence']=['normalization']
        self.db.execute('UPDATE candidates SET decision=? WHERE id=?',(json.dumps(decision),cid))
        with self.assertRaisesRegex(ValueError,'inactive selected evidence'): self.gate()
    def test_active_normalization_cannot_depend_on_retired_reading(self):
        self.add();self.db.execute("UPDATE facts SET active=0 WHERE id='r1'")
        self.db.execute('INSERT INTO facts(id,active,kind,body) VALUES(?,?,?,?)',('boundary',1,'normalization',json.dumps({'componentFacts':['r1']})))
        with self.assertRaisesRegex(ValueError,'inactive selected evidence'):
            distribution.require_active_selected_facts(self.db,'fixture',{'normalizationEvidence':['boundary']})

    def test_reading_and_context_require_active_identity_dependencies(self):
        self.add();self.db.execute("INSERT INTO facts(id,active,kind,body) VALUES('identity',0,'context','{}')")
        for kind in ('reading','context'):
            self.db.execute('INSERT OR REPLACE INTO facts(id,active,kind,body) VALUES(?,?,?,?)',('bound',1,kind,json.dumps({'componentFacts':['identity']})))
            with self.assertRaisesRegex(ValueError,'inactive selected evidence'):
                distribution.require_active_selected_facts(self.db,'fixture',{'readingEvidence':['bound']})
    def test_nested_quality_dependencies_and_each_reference_field_are_checked(self):
        self.add();self.db.execute("UPDATE facts SET active=0 WHERE id='r1'")
        for field in ('fullAddressEvidence','outputEvidence','prefixEvidence','addressFact','sourceEvidence'):
            with self.subTest(field=field):
                self.db.execute('INSERT OR REPLACE INTO facts(id,active,kind,body) VALUES(?,?,?,?)',('nested',1,'normalization',json.dumps({field:'r1'})))
                self.db.execute('INSERT OR REPLACE INTO facts(id,active,kind,body) VALUES(?,?,?,?)',('exclusion',1,'invalid',json.dumps({'sourceEvidence':'nested'})))
                with self.assertRaisesRegex(ValueError,'inactive selected evidence'):
                    distribution.require_active_selected_facts(self.db,'fixture',{'exclusionEvidence':['exclusion']})
    def test_active_dependency_chain_passes_and_cycle_is_rejected(self):
        self.add()
        self.db.execute('INSERT INTO facts(id,active,kind,body) VALUES(?,?,?,?)',('boundary',1,'normalization',json.dumps({'componentFacts':['r1','m1']})))
        self.db.execute('INSERT INTO facts(id,active,kind,body) VALUES(?,?,?,?)',('exclusion',1,'invalid',json.dumps({'addressFact':'boundary'})))
        distribution.require_active_selected_facts(self.db,'fixture',{'exclusionEvidence':['exclusion']})
        self.db.execute('UPDATE facts SET body=? WHERE id=?',(json.dumps({'sourceEvidence':'exclusion'}),'boundary'))
        with self.assertRaisesRegex(ValueError,'Cyclic selected evidence'):
            distribution.require_active_selected_facts(self.db,'fixture',{'exclusionEvidence':['exclusion']})
    def test_export_rejects_stale_reading_meaning_and_exclusion_proofs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);db=worker.connect(root/'ledger.sqlite');db.executescript(worker.SCHEMA)
            try:
                args=argparse.Namespace(config=str(worker.DEFAULT_CONFIG),documents=str(root/'docs'),output=str(root/'snapshot.sqlite'),candidate=True)
                evidence=worker.Evidence(db,args);doc=evidence.save('https://example.org/fixture','v1',b'fixture names','CC0')
                cid=worker.insert_candidate(db,'やまだ','山田',1,1,10)
                read=evidence.fact('やまだ','山田','reading',[],'JMnedict:1',doc,{'source':'JMnedict'})
                meaning=evidence.fact('やまだ','山田','meaning',['person'],'JMnedict:1:0',doc,{'source':'JMnedict','nameTypes':['surname']})
                decision={'readingEvidence':[read],'roles':[{'category':'person','target':'JMnedict:1:0','sense':'surname','method':'direct','evidenceIds':[meaning]}]}
                db.execute("UPDATE candidates SET state='reviewed',decision=? WHERE id=?",(json.dumps(decision),cid))
                excluded=worker.insert_candidate(db,'ふろあ','フロア(1階)',1,1,10)
                invalid=evidence.fact('ふろあ','フロア(1階)','invalid',[],excluded,doc,{'issue':'annotation'})
                db.execute("UPDATE candidates SET state='excluded_confirmed',decision=? WHERE id=?",(json.dumps({'readingEvidence':[],'roles':[],'exclusionEvidence':[invalid]}),excluded))
                worker.info(db,'inputs',{'sources':{'person':'0'*64}});worker.info(db,'baseIdDefSha256','1'*64)
                cfg=worker.configuration(args);cfg=(cfg[0],{'categories':[{'id':'person','core':True,'minimum':1}]},*cfg[2:])
                for fid in (read,meaning,invalid):
                    with self.subTest(evidence=fid):
                        db.execute('UPDATE facts SET active=1');db.execute('UPDATE facts SET active=0 WHERE id=?',(fid,))
                        with mock.patch.object(distribution,'precision',return_value={}),contextlib.redirect_stdout(io.StringIO()):
                            with self.assertRaisesRegex(ValueError,'Missing'):
                                distribution.export(db,args,lambda args:cfg,worker.info,worker.confidence_lower,worker.canonical,worker.digest,worker.sha,worker.emit)
                        self.assertFalse(pathlib.Path(args.output).exists())
                # An active exclusion may conceal a retired lower-level reading;
                # the export guard must follow that edge even when scoring is mocked.
                underlying=evidence.fact('べつ','別','reading',[],'fixture:component',doc,{'source':'fixture'})
                db.execute('UPDATE facts SET active=1')
                db.execute('UPDATE facts SET active=0 WHERE id=?',(underlying,))
                db.execute('UPDATE facts SET body=? WHERE id=?',(json.dumps({'sourceEvidence':underlying}),invalid))
                with mock.patch.object(distribution,'precision',return_value={}),contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(ValueError,'inactive selected evidence'):
                        distribution.export(db,args,lambda args:cfg,worker.info,worker.confidence_lower,worker.canonical,worker.digest,worker.sha,worker.emit)
                self.assertFalse(pathlib.Path(args.output).exists())
            finally: db.close()
    def test_each_inferred_route_needs_adequate_validation(self):
        self.add('source_review',150);self.add('ai',150)
        with self.assertRaisesRegex(ValueError,'source_review precision'): self.gate()
    def test_100_flawless_reviews_do_not_satisfy_confidence(self):
        self.add('source_review',100)
        with self.assertRaisesRegex(ValueError,'confidence'): self.gate()
    def test_accuracy_and_confidence_are_both_required(self):
        self.add('source_review',299);self.add('source_review',wrong=True)
        with self.assertRaisesRegex(ValueError,'confidence'): self.gate()
    def test_precision_below_995_percent_is_rejected(self):
        self.add('source_review',298);self.add('source_review',2,wrong=True)
        with self.assertRaisesRegex(ValueError,'source_review precision'): self.gate()
    def test_population_route_absent_from_gold_is_not_zero_use(self):
        self.add();self.add('source_review',gold=False)
        with self.assertRaisesRegex(ValueError,'source_review precision'): self.gate()
    def test_other_referent_is_reported_outside_exact_target_sample(self):
        self.add('source_review',300);cid=self.add()
        decision=json.loads(self.db.execute('SELECT decision FROM candidates WHERE id=?',(cid,)).fetchone()[0])
        self.db.execute("INSERT INTO facts(id,active,kind,target) VALUES('other',1,'context','independent-other-target')")
        decision['roles'].append({'method':'source_review','category':'work','target':'independent-other-target','evidenceIds':['other']})
        self.db.execute('UPDATE candidates SET decision=? WHERE id=?',(json.dumps(decision),cid))
        gate=self.gate()
        self.assertEqual(300,gate['precision']['source_review']['n'])
        self.assertEqual(301,gate['precision']['source_review']['population'])
        self.assertEqual(1,gate['unassessedTargetsInSelectedCandidates']['source_review'])
    def test_wrong_referent_cannot_disappear_outside_the_sample(self):
        self.add('source_review',300);cid=self.add('source_review')
        decision=json.loads(self.db.execute('SELECT decision FROM candidates WHERE id=?',(cid,)).fetchone()[0]);decision['roles'][0]['target']='wrong'
        self.db.execute('UPDATE candidates SET decision=? WHERE id=?',(json.dumps(decision),cid))
        with self.assertRaisesRegex(ValueError,'Unbound predicted target'):self.gate()
    def test_known_meaning_with_unproved_reading_is_still_classification_truth(self):
        self.add('source_review',300);self.add('source_review')
        self.gold['cases'][-1]['eligible']=False
        gate=self.gate()
        self.assertEqual(301,gate['precision']['source_review']['correct'])
        self.assertEqual(300,gate['eligible'])
    def test_empty_meaning_labels_cannot_be_hidden_by_ineligible_flag(self):
        self.add('source_review',299);self.add('source_review')
        self.gold['cases'][-1].update(eligible=False,categories=[])
        with self.assertRaisesRegex(ValueError,'confidence'):self.gate()
    def test_inactive_category_cannot_hide_unvalidated_inference(self):
        self.add();self.add('ai',gold=False,category='technical')
        with self.assertRaisesRegex(ValueError,'ai precision'): self.gate(active=['person'])
    def test_inactive_category_is_still_measured(self):
        self.add('source_review',300,category='technical')
        self.add('direct',300)
        # Keep each gold candidate adoptable in an active category while also
        # validating its inferred role below another category's publication floor.
        for cid in map(str,range(1,301)):
            decision=json.loads(self.db.execute('SELECT decision FROM candidates WHERE id=?',(cid,)).fetchone()[0])
            decision['roles'].append({'method':'direct','category':'person','target':'target:'+cid})
            self.db.execute('UPDATE candidates SET decision=? WHERE id=?',(json.dumps(decision),cid))
            self.gold['cases'][int(cid)-1]['categories'].append('person')
        gate=self.gate(active=['person'])
        self.assertEqual(300,gate['precision']['source_review']['n'])
    def test_invalid_methods_fail_even_outside_gold(self):
        self.add();self.add('unchecked',gold=False)
        with self.assertRaisesRegex(ValueError,'Invalid classification'): self.gate()
    def test_legacy_route_is_supported_but_missing_or_null_method_is_not(self):
        self.add(legacy=True);self.assertEqual(1,self.gate()['precision']['direct']['n'])
        cid=self.add(None)
        with self.assertRaisesRegex(ValueError,'Invalid classification'): self.gate()
        self.db.execute('UPDATE candidates SET decision=? WHERE id=?',(json.dumps({'roles':[{'category':'person','target':'target:'+cid}]}),cid))
        with self.assertRaisesRegex(ValueError,'Invalid classification'): self.gate()
    def test_all_nonterminal_states_stop_distribution(self):
        for state in ('blocked','needs_review','error','queued'):
            with self.subTest(state=state):
                self.db.execute('DELETE FROM candidates');self.gold['cases']=[];self.add(state=state)
                with self.assertRaisesRegex(ValueError,'Unfinished'): self.gate()
    def test_independent_gold_and_adoption_coverage_remain_required(self):
        self.add();gold=self.gold;self.gold=None
        with self.assertRaisesRegex(ValueError,'not frozen'): self.gate()
        self.gold=gold;self.add(wrong=True)
        with self.assertRaisesRegex(ValueError,'adoption rate'): self.gate()
    def test_published_source_review_cannot_claim_zero_population(self):
        self.add();gate=self.gate()
        with self.assertRaisesRegex(ValueError,'population'): distribution.verify_precision_report(gate,{'source_review':1})
    def test_offline_report_rejects_missing_method_stats_or_gold(self):
        self.add();gate=self.gate();gate['precision'].pop('source_review')
        with self.assertRaisesRegex(ValueError,'methods'): distribution.verify_precision_report(gate,{'direct':1})
        gate=self.gate();gate.pop('goldSha256')
        with self.assertRaisesRegex(ValueError,'gold checksum'): distribution.verify_precision_report(gate,{'direct':1})
    def test_offline_inferred_report_requires_actual_sample_and_confidence(self):
        self.add('source_review',300);gate=self.gate()
        for n,correct,lower in ((0,0,0.0),(300,300,.98),(300,298,.999),(300,300,True)):
            with self.subTest(n=n,correct=correct,lower=lower):
                broken=json.loads(json.dumps(gate));broken['precision']['source_review'].update(n=n,correct=correct,lower95=lower)
                with self.assertRaisesRegex(ValueError,'confidence'): distribution.verify_precision_report(broken,{'source_review':300})
    def test_exported_unknown_method_fails_closed(self):
        self.add()
        with self.assertRaisesRegex(ValueError,'methods'): distribution.verify_precision_report(self.gate(),{'unchecked':1})

if __name__=='__main__': unittest.main()
