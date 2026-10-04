import json,pathlib,sqlite3,sys,tempfile,unittest,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import gold_review as g

class BindingTests(unittest.TestCase):
 def record(self,raw,sense=1):return {'source':'JMdict','target':'JMdict:1:sense:'+str(sense),'literalOriginalEntry':raw,'rawRecord':{'entryId':'1','sense':sense,'glosses':['bridge']}}
 def case(self,y='はし',s='橋'):return {'reading':y,'surface':s}
 def test_reading_restriction_cannot_borrow_homograph(self):
  raw='<entry><ent_seq>1</ent_seq><k_ele><keb>橋</keb></k_ele><k_ele><keb>箸</keb></k_ele><r_ele><reb>はし</reb><re_restr>箸</re_restr></r_ele><sense><gloss>bridge</gloss></sense></entry>'
  with self.assertRaisesRegex(ValueError,'not bound'):g.xml_binding(self.case(),self.record(raw))
 def test_re_nokanji_excludes_spelling(self):
  raw='<entry><ent_seq>1</ent_seq><k_ele><keb>橋</keb></k_ele><r_ele><reb>はし</reb><re_nokanji/></r_ele><sense><gloss>bridge</gloss></sense></entry>'
  with self.assertRaisesRegex(ValueError,'not bound'):g.xml_binding(self.case(),self.record(raw))
 def test_selected_sense_restricts_surface(self):
  raw='<entry><ent_seq>1</ent_seq><k_ele><keb>橋</keb></k_ele><k_ele><keb>箸</keb></k_ele><r_ele><reb>はし</reb></r_ele><sense><stagk>箸</stagk><gloss>bridge</gloss></sense></entry>'
  with self.assertRaisesRegex(ValueError,'sense restrictions'):g.xml_binding(self.case(),self.record(raw))
 def test_search_only_spelling_cannot_be_positive(self):
  raw='<entry><ent_seq>1</ent_seq><k_ele><keb>橋</keb><ke_inf>&sK;</ke_inf></k_ele><r_ele><reb>はし</reb></r_ele><sense><gloss>bridge</gloss></sense></entry>'
  with self.assertRaisesRegex(ValueError,'Search-only'):g.xml_binding(self.case(),self.record(raw),require_attested=True)
 def test_original_gloss_cannot_be_replaced(self):
  raw='<entry><ent_seq>1</ent_seq><k_ele><keb>橋</keb></k_ele><r_ele><reb>はし</reb></r_ele><sense><gloss>chopsticks</gloss></sense></entry>'
  with self.assertRaisesRegex(ValueError,'differs'):g.xml_binding(self.case(),self.record(raw))
 def test_attested_variant_and_nfkc_digit_are_preserved(self):
  raw='<entry><ent_seq>1</ent_seq><k_ele><keb>７０</keb></k_ele><r_ele><reb>ななじゅう</reb></r_ele><r_ele><reb>しちじゅう</reb></r_ele><sense><pos>&num;</pos><gloss>bridge</gloss></sense></entry>'
  for y in ('ななじゅう','しちじゅう'):self.assertEqual(g.xml_binding(self.case(y,'70'),self.record(raw)),raw)
 def test_wrong_entity_id_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'target mismatch'):g.wikidata_entity(json.dumps({'id':'Q2'}),'Q1')
 def test_alias_cannot_borrow_canonical_reading(self):
  e={'id':'Q1','labels':{'ja':{'value':'東京太郎'}},'aliases':{'ja':[{'value':'東太郎'}]},'claims':{'P1814':[{'mainsnak':{'datavalue':{'value':'とうきょうたろう'}}}]}}
  self.assertEqual(g.wikidata_binding(self.case('とうきょうたろう','東太郎'),e),[])
 def test_canonical_kana_and_deprecated_claim(self):
  e={'id':'Q1','labels':{'ja':{'language':'ja','value':'アリオン'}},'claims':{'P1814':[{'rank':'deprecated','mainsnak':{'datavalue':{'value':'ありおん'}}}]}}
  self.assertTrue(g.wikidata_binding(self.case('ありおん','アリオン'),e))
  self.assertFalse(g.wikidata_binding(self.case('ありおーん','アリオン'),e))

 def test_kana_alias_is_not_an_attested_primary_name(self):
  e={'id':'Q1','labels':{'ja':{'value':'トヨタ・アリオン'}},'aliases':{'ja':[{'value':'アリオン'}]},'sitelinks':{'jawiki':{'title':'トヨタ・アリオン'}},'claims':{}}
  self.assertEqual(g.wikidata_binding(self.case('ありおん','アリオン'),e),[])
 def test_qualified_reading_cannot_be_borrowed_by_primary_name(self):
  e={'id':'Q1','labels':{'ja':{'value':'東京太郎'}},'claims':{'P1814':[{'mainsnak':{'datavalue':{'value':'あずまたろう'}},'qualifiers':{'P5168':[{'datavalue':{'value':{'language':'ja','text':'東太郎'}}}]}}]}}
  self.assertEqual(g.wikidata_binding(self.case('あずまたろう','東京太郎'),e),[])
  self.assertTrue(g.wikidata_binding(self.case('あずまたろう','東太郎'),e))
 def test_unsupported_qualifier_never_becomes_primary_reading(self):
  e={'id':'Q1','labels':{'ja':{'value':'東京太郎'}},'claims':{'P1814':[{'mainsnak':{'datavalue':{'value':'とうきょうたろう'}},'qualifiers':{'P5168':[{'datavalue':{'value':{'language':'en','text':'Tokyo Taro'}}}]}}]}}
  self.assertEqual(g.wikidata_binding(self.case('とうきょうたろう','東京太郎'),e),[])

class AssemblyTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
  self.db.executescript('CREATE TABLE candidates(id TEXT,reading TEXT,surface TEXT); CREATE TABLE documents(id TEXT,path TEXT,sha256 TEXT); CREATE TABLE facts(kind TEXT,document_id TEXT,target TEXT,reading TEXT,surface TEXT,active INTEGER);')
  self.raw='<entry><ent_seq>1</ent_seq><k_ele><keb>橋</keb></k_ele><r_ele><reb>はし</reb></r_ele><sense><gloss>bridge</gloss></sense></entry>'
  self.p=pathlib.Path(self.t.name)/'source.xml';self.p.write_text(self.raw);self.sha=hashlib.sha256(self.p.read_bytes()).hexdigest()
  self.db.execute('INSERT INTO documents VALUES(?,?,?)',('doc',str(self.p),self.sha));self.db.execute('INSERT INTO candidates VALUES(?,?,?)',('id','はし','橋'))
  for k in ('reading','meaning'):self.db.execute('INSERT INTO facts VALUES(?,?,?,?,?,1)',(k,'doc','JMdict:1:sense:1','はし','橋'))
  r={'source':'JMdict','documentId':'doc','target':'JMdict:1:sense:1','literalOriginalEntry':self.raw,'rawRecord':{'entryId':'1','sense':1,'glosses':['bridge']}}
  self.batch={'selectionCanonicalSha256':'sel','cases':[{'candidateId':'id','split':'validation','reading':'はし','surface':'橋','sourceAvailabilityStratum':'food','records':[r]}]}
  self.annotations={'selectionCanonicalSha256':'sel','inspector':'independent test reviewer','annotations':[{'caseIndex':1,'recordIndex':0,'categories':['technical'],'eligible':True}]}
 def tearDown(self):self.db.close();self.t.cleanup()
 def test_manual_categories_not_availability_stratum(self):
  result,audit=g.assemble(self.db,self.batch,self.annotations)
  self.assertEqual(result['cases'][0]['categories'],['technical']);self.assertEqual(result['cases'][0]['meaningEvidence'][0]['quotation'],self.raw)
  self.assertEqual(audit['unreviewedCandidateIds'],[]);self.assertEqual(audit['registrationRequired'],[]);self.assertFalse(audit['productionLedgerWritten'])
 def test_no_automatic_labels_for_unannotated_case(self):
  self.annotations['annotations']=[];result,audit=g.assemble(self.db,self.batch,self.annotations)
  self.assertEqual(result['cases'],[]);self.assertEqual(audit['unreviewedCandidateIds'],['id'])
 def test_negative_meaning_reference_does_not_approve_positive_reading(self):
  self.db.execute("update facts set active=0 where kind='reading'")
  self.annotations['annotations'][0]['eligible']=False
  result,audit=g.assemble(self.db,self.batch,self.annotations)
  self.assertFalse(result['cases'][0]['eligible']);self.assertEqual(audit['registrationRequired'],[])
  self.annotations['annotations'][0]['eligible']=True
  result,audit=g.assemble(self.db,self.batch,self.annotations)
  self.assertEqual([i['field'] for i in audit['registrationRequired']],['readingEvidence'])
 def test_empty_categories_only_permitted_for_negative_case(self):
  a=self.annotations['annotations'][0];a['categories']=[];a['eligible']=False
  result,audit=g.assemble(self.db,self.batch,self.annotations);self.assertEqual(result['cases'][0]['categories'],[])
  a['eligible']=True
  with self.assertRaisesRegex(ValueError,'categories'):g.assemble(self.db,self.batch,self.annotations)
 def test_search_only_kana_cannot_be_positive_reading(self):
  raw=self.raw.replace('<reb>はし</reb>','<reb>はし</reb><re_inf>&sk;</re_inf>')
  self.p.write_text(raw);self.db.execute('update documents set sha256=?',(hashlib.sha256(self.p.read_bytes()).hexdigest(),))
  self.batch['cases'][0]['records'][0]['literalOriginalEntry']=raw
  with self.assertRaisesRegex(ValueError,'Search-only'):g.assemble(self.db,self.batch,self.annotations)
 def test_changed_document_fails_closed(self):
  self.p.write_text('replaced')
  with self.assertRaisesRegex(ValueError,'checksum'):g.assemble(self.db,self.batch,self.annotations)
 def test_annotations_for_different_selection_rejected(self):
  self.annotations['selectionCanonicalSha256']='other'
  with self.assertRaisesRegex(ValueError,'another fixed'):g.assemble(self.db,self.batch,self.annotations)
 def test_external_eligible_reading_requires_registered_target_binding(self):
  self.annotations['annotations'][0]['readingEvidence']=[{'documentId':'doc','quotation':'<keb>橋</keb>'}]
  self.db.execute("delete from facts where kind='reading'")
  with self.assertRaisesRegex(ValueError,'verified pair/target'):g.assemble(self.db,self.batch,self.annotations)
 def test_inactive_reading_is_reported_without_ledger_mutation(self):
  self.db.execute("update facts set active=0 where kind='reading'");before=self.db.total_changes
  result,audit=g.assemble(self.db,self.batch,self.annotations)
  self.assertEqual(audit['registrationRequired'][0]['field'],'readingEvidence');self.assertEqual(self.db.total_changes,before)

if __name__=='__main__':unittest.main()
