"""Synthetic, temporary provenance fixtures for immutable gold selection workflow."""
import argparse,contextlib,copy,io,json,pathlib,sys,tempfile,unittest
from unittest import mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import worker as w

class GoldSelectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.args=argparse.Namespace(config=str(w.DEFAULT_CONFIG),ledger=str(self.root/'ledger.sqlite'),documents=str(self.root/'docs'),input=str(self.root/'selection.json'),gold=str(self.root/'gold.json'))
        cfg=w.configuration(self.args);taxonomy={'categories':[{'id':'person','core':False,'minimum':0}]}
        identity=copy.deepcopy(cfg[-1]);identity['taxonomy']=taxonomy
        self.config=mock.patch.object(w,'configuration',return_value=(cfg[0],taxonomy,*cfg[2:-1],identity));self.config.start()
        self.db=w.connect(self.args.ledger);self.db.executescript(w.SCHEMA);w.pin_config(self.db,self.args)
        self.e=w.Evidence(self.db,self.args)
        raw='\n'.join('名%d（な%d） person'%(n,n) for n in range(100))
        doc=self.e.save('https://example.org/gold-fixture','v1',raw.encode(),'CC0')
        digest=self.db.execute('SELECT sha256 FROM documents WHERE id=?',(doc,)).fetchone()[0]
        self.cases=[]
        for n in range(100):
            y='な'+str(n);surface='名'+str(n);cid=w.insert_candidate(self.db,y,surface,1,1,10);target='target:'+cid
            read=self.e.fact(y,surface,'reading',[],target,doc,{'source':'fixture'})
            meaning=self.e.fact(y,surface,'meaning',['person'],target,doc,{'source':'fixture'})
            reference={'documentId':doc,'sha256':digest,'quotation':'名%d（な%d） person'%(n,n)}
            case={'candidateId':cid,'split':'calibration' if n<50 else 'validation','categories':['person'],'target':target,'eligible':True,'readingEvidence':[reference],'meaningEvidence':[reference]}
            self.cases.append(case)
            decision={'classificationRoute':'direct','readingEvidence':[read],'roles':[{'method':'direct','category':'person','target':target,'sense':'fixture','evidenceIds':[meaning]}]}
            self.db.execute('UPDATE candidates SET decision=? WHERE id=?',(json.dumps(decision),cid))
        self.db.commit();self.write_selection();self.write_gold()
    def tearDown(self): self.db.close();self.config.stop();self.tmp.cleanup()
    def write_selection(self,cases=None):
        labels=self.cases if cases is None else cases
        value={'schemaVersion':1,'cases':[{'candidateId':c['candidateId'],'split':c['split']} for c in labels]}
        pathlib.Path(self.args.input).write_text(json.dumps(value))
    def write_gold(self,cases=None): pathlib.Path(self.args.gold).write_text(json.dumps({'cases':self.cases if cases is None else cases}))
    def selection(self):
        with contextlib.redirect_stdout(io.StringIO()): return w.select_gold(self.args)
    def freeze(self):
        with contextlib.redirect_stdout(io.StringIO()): w.freeze_gold(self.args)
    def source_only(self): self.db.execute("UPDATE candidates SET state='reviewed'");self.db.commit()
    def inferred(self,history=False):
        cid=self.cases[0]['candidateId'];decision={'classificationRoute':'source_review','roles':[{'method':'source_review'}]}
        if history:
            self.db.execute('INSERT INTO decision_history(candidate_id,state,decision,change,created) VALUES(?,?,?,?,?)',(cid,'reviewed',json.dumps(decision),'reset',0))
        else: self.db.execute("UPDATE candidates SET decision=?,state='reviewed' WHERE id=?",(json.dumps(decision),cid))
        self.db.commit()
    def test_original_pre_full_freeze_still_checks_real_provenance(self):
        self.freeze();frozen=w.info(self.db,'goldFrozen');selection=w.info(self.db,'goldSelection')
        self.assertEqual('pre-full-gold',selection['mode']);self.assertEqual(selection['selectionSha256'],frozen['selectionSha256'])
        self.assertEqual(w.sha(self.args.gold),frozen['sha256'])
    def test_late_source_only_requires_selection_before_loading_labels(self):
        self.source_only()
        with mock.patch.object(w,'validate_gold',side_effect=AssertionError('labels read too early')):
            with self.assertRaisesRegex(ValueError,'separately recorded'): self.freeze()
    def test_late_source_only_can_record_selection_and_then_freeze(self):
        self.source_only();selection=self.selection();self.freeze()
        self.assertEqual('independent-selection',selection['mode']);self.assertEqual(w.sha(self.args.input),selection['fileSha256'])
        self.assertEqual(selection['selectionSha256'],w.info(self.db,'goldFrozen')['selectionSha256'])
    def test_selection_is_immutable_and_identical_rerecord_is_read_only(self):
        selection=self.selection();self.assertEqual(selection,self.selection())
        changed=copy.deepcopy(self.cases);changed[0]['split']='validation';self.write_selection(changed)
        with self.assertRaisesRegex(ValueError,'immutable'): self.selection()
        self.assertEqual(selection,w.info(self.db,'goldSelection'))
    def test_labels_must_match_all_selected_candidates_and_splits(self):
        self.selection()
        for change in ('missing','split'):
            with self.subTest(change=change):
                cases=copy.deepcopy(self.cases)
                if change=='missing': cases.pop()
                else: cases[0]['split']='validation'
                self.write_gold(cases)
                with self.assertRaisesRegex(ValueError,'frozen candidate/split'): self.freeze()
    def test_selection_cannot_include_labels_or_duplicate_candidates(self):
        value={'schemaVersion':1,'cases':copy.deepcopy(self.cases)};pathlib.Path(self.args.input).write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'never labels'): self.selection()
        self.write_selection(self.cases+[self.cases[0]])
        with self.assertRaisesRegex(ValueError,'duplicate'): self.selection()
    def test_late_selection_rejects_current_and_archived_inferred_decisions(self):
        for history in (False,True):
            with self.subTest(history=history):
                self.db.execute("UPDATE candidates SET decision=NULL,state='queued'");self.db.execute('DELETE FROM decision_history');self.inferred(history)
                with self.assertRaisesRegex(ValueError,'inferred full'): self.selection()
    def test_late_selection_rejects_failed_model_calls_and_inferences(self):
        cid=self.cases[0]['candidateId']
        self.db.execute('INSERT INTO inferences(candidate_id,error) VALUES(?,?)',(cid,'model failure'));self.db.commit()
        with self.assertRaisesRegex(ValueError,'inferred full'): self.selection()
        self.db.execute('DELETE FROM inferences');self.db.execute('INSERT INTO model_calls(aliases,error) VALUES(?,?)',(json.dumps({'candidates':{cid:'c0'}}),'failed call'));self.db.commit()
        with self.assertRaisesRegex(ValueError,'inferred full'): self.selection()
    def test_pilot_inference_does_not_block_pre_full_workflow(self):
        cid=self.cases[0]['candidateId'];self.db.execute('INSERT INTO pilot VALUES(?,?)',(cid,'fixture'));self.inferred()
        self.selection();self.freeze();self.assertIsNotNone(w.info(self.db,'goldFrozen'))
    def test_inferred_full_decision_after_selection_still_blocks_freeze(self):
        self.selection();self.inferred()
        with self.assertRaisesRegex(ValueError,'before inferred full'): self.freeze()
    def test_frozen_gold_cannot_be_replaced_with_a_new_cohort(self):
        self.freeze();changed=copy.deepcopy(self.cases);changed.pop();self.write_selection(changed)
        with self.assertRaisesRegex(ValueError,'immutable'): self.selection()

    def individual_review(self, surface='別名', target='separate-target', history=False):
        cid=w.insert_candidate(self.db,'べつめい',surface,0,0,0,'pending','')
        decision={'classificationRoute':'source_review','roles':[{'method':'source_review','category':'person','target':target}],
                  'reviewFileSha256':'a'*64,'evidenceSha256':'b'*64,
                  'citations':[{'quotation':'individually inspected source'}]}
        if history:
            self.db.execute('INSERT INTO decision_history(candidate_id,state,decision,change,created) VALUES(?,?,?,?,?)',
                            (cid,'reviewed',json.dumps(decision),'inspection',w.info(self.db,'goldSelection')['recordedAt']+1))
        else:self.db.execute("UPDATE candidates SET state='reviewed',decision=? WHERE id=?",(json.dumps(decision),cid))
        self.db.commit();return cid

    def test_preselected_gold_can_follow_disjoint_individual_cited_reviews(self):
        self.selection();self.individual_review();self.freeze()
        self.assertIn('disjoint',w.info(self.db,'goldFrozen')['priorInspectionBasis'])

    def test_disjoint_candidate_ids_cannot_hide_selected_name_or_target_leakage(self):
        for name,target,history in [('名0','separate-target',False),('別名',self.cases[0]['target'],False),('別名',self.cases[0]['target'],True)]:
            with self.subTest(name=name,target=target,history=history):
                self.selection();cid=self.individual_review(name,target,history)
                with self.assertRaisesRegex(ValueError,'before inferred full'):self.freeze()
                self.db.execute('DELETE FROM decision_history WHERE candidate_id=?',(cid,))
                self.db.execute('DELETE FROM candidates WHERE id=?',(cid,));self.db.commit()

    def test_disjoint_review_cannot_hide_outside_pilot_model_inference(self):
        self.selection();cid=self.individual_review()
        self.db.execute('INSERT INTO inferences(candidate_id,error) VALUES(?,?)',(cid,'model failure'));self.db.commit()
        with self.assertRaisesRegex(ValueError,'before inferred full'):self.freeze()
    def test_same_cohort_changed_labels_cannot_replace_frozen_evaluation(self):
        self.freeze();frozen=copy.deepcopy(w.info(self.db,'goldFrozen'));history=copy.deepcopy(w.info(self.db,'goldFrozenHistory'))
        changed=copy.deepcopy(self.cases);changed[0]['eligible']=False;self.write_gold(changed)
        with self.assertRaisesRegex(ValueError,'labels are immutable'): self.freeze()
        self.assertEqual(frozen,w.info(self.db,'goldFrozen'));self.assertEqual(history,w.info(self.db,'goldFrozenHistory'))
    def test_identical_label_file_is_idempotent_even_after_full_inference(self):
        self.freeze();history=copy.deepcopy(w.info(self.db,'goldFrozenHistory'));self.inferred()
        self.freeze();self.assertEqual(history,w.info(self.db,'goldFrozenHistory'))
    def test_archived_frozen_records_are_deduplicated_by_both_hashes(self):
        self.freeze();frozen=w.info(self.db,'goldFrozen');w.archive_frozen_gold(self.db,frozen)
        self.assertEqual(1,len(w.info(self.db,'goldFrozenHistory')))
        revised={**frozen,'selectionSha256':'b'*64};w.archive_frozen_gold(self.db,revised)
        self.assertEqual(2,len(w.info(self.db,'goldFrozenHistory')))
    def test_label_source_quotation_validation_is_not_weakened(self):
        self.source_only();self.selection();cases=copy.deepcopy(self.cases);cases[0]['readingEvidence'][0]['quotation']='fabricated';self.write_gold(cases)
        with self.assertRaisesRegex(ValueError,'quotation'): self.freeze()
        self.assertIsNone(w.info(self.db,'goldFrozen'))

if __name__=='__main__': unittest.main()
