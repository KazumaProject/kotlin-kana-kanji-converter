import gzip,hashlib,json,pathlib,sqlite3,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));import article_archive_export as a
class ExportTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();p=pathlib.Path(self.temp.name);self.archive=p/'all.sqlite';self.identity=p/'ids.sqlite';self.out=p/'pack.json.gz';self.quote="(1,'wikibase_item','Q1',NULL)";self.sql=p/'jawiki-20261001-page_props.sql.gz';self.sql.write_bytes(gzip.compress(('INSERT INTO page_props VALUES '+self.quote+';').encode()))
  db=sqlite3.connect(self.archive);db.executescript('create table meta(key text primary key,value text);create table pages(page_id integer,title text,revision text,timestamp text,text_sha1 text,content text,redirect text,declared_bytes text,export_terminal_lf_recovered integer);');meta={'complete':True,'eof':True,'sourceChecksumVerified':True,'file':'jawiki-20261001-pages.xml.bz2','sha256':'a'*64};db.execute('insert into meta values(?,?)',('source',json.dumps(meta)));db.execute('insert into pages values(?,?,?,?,?,?,?,?,?)',(1,'原本','12','2026-10-01T00:00:00Z',format(int(hashlib.sha1('全文'.encode()).hexdigest(),16),'x'),'全文',None,'6',0));db.commit();db.close()
  # MediaWiki SHA1 is base36, including when digits happen to be hex letters.
  import test_article_archive as t;db=sqlite3.connect(self.archive);db.execute('update pages set text_sha1=?',(t.base36(int(hashlib.sha1('全文'.encode()).hexdigest(),16)),));db.commit();db.close()
  db=sqlite3.connect(self.identity);db.executescript('create table meta(key text primary key,value text);create table page_identity(page_id integer,qid text,quotation text);');db.execute('insert into meta values(?,?)',('source',json.dumps({'complete':True,'source':str(self.sql),'sha256':hashlib.sha256(self.sql.read_bytes()).hexdigest()})));db.execute('insert into page_identity values(?,?,?)',(1,'Q1',self.quote));db.commit();db.close();self.requests=[{'page_id':1,'qid':'Q1','quotation':self.quote}]
 def tearDown(self):self.temp.cleanup()
 def test_exports_literal_content_and_identity(self):
  report=a.export(self.archive,self.identity,self.requests,self.out);pack=json.loads(gzip.decompress(self.out.read_bytes()));self.assertTrue(report['usableForEvidence']);self.assertEqual('全文',pack['query']['pages']['1']['revisions'][0]['slots']['main']['*']);self.assertEqual('Q1',pack['query']['pages']['1']['sourceIdentity']['qid'])
 def test_no_unverified_archive_evidence(self):
  with sqlite3.connect(self.archive)as db:db.execute('update meta set value=?',(json.dumps({'complete':False,'file':'jawiki-20261001-pages.xml.bz2','expectedSha256':'a'*64}),))
  with self.assertRaises(ValueError):a.export(self.archive,self.identity,self.requests,self.out)
  report=a.export(self.archive,self.identity,self.requests,self.out,provisional=True);self.assertFalse(report['usableForEvidence']);self.assertTrue(report['evaluationDraftOnly']);self.assertIsNone(report['sourceDumpSha256'])
 def test_mismatched_qid_fails(self):
  with self.assertRaises(ValueError):a.export(self.archive,self.identity,[{'page_id':1,'qid':'Q2'}],self.out)
 def test_changed_revision_fails(self):
  with sqlite3.connect(self.archive)as db:db.execute("update pages set content='改変'")
  with self.assertRaises(ValueError):a.export(self.archive,self.identity,self.requests,self.out)
 def test_changed_identity_source_fails(self):
  self.sql.write_bytes(b'changed')
  with self.assertRaises(ValueError):a.export(self.archive,self.identity,self.requests,self.out)
if __name__=='__main__':unittest.main()
