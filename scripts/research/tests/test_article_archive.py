import bz2,hashlib,json,pathlib,sqlite3,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));import article_archive as a

def base36(value):
 alphabet='0123456789abcdefghijklmnopqrstuvwxyz';out=''
 while value: value,r=divmod(value,36);out=alphabet[r]+out
 return out or'0'
def page(pid=1,title='原本',text='原本の全文',ns=0,redirect=None,sha=None,export_lf=False):
 digest=sha or base36(int(hashlib.sha1(text.encode()).hexdigest(),16));red='<redirect title="先"/>'if redirect else'';export=text+'\n'if export_lf else text
 return f'<page><title>{title}</title><ns>{ns}</ns><id>{pid}</id>{red}<revision><id>{pid+100}</id><timestamp>2026-10-01T00:00:00Z</timestamp><text bytes="{len(export.encode())}">{export}</text><sha1>{digest}</sha1></revision></page>'
class ArchiveTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.dump=self.root/'source.xml.bz2';self.out=self.root/'archive.sqlite'
 def tearDown(self):self.temp.cleanup()
 def source(self,pages,closing=True):
  raw=bz2.compress(('<mediawiki xmlns="urn:wiki">'+pages+('</mediawiki>'if closing else'')).encode());self.dump.write_bytes(raw);return len(raw),hashlib.sha1(raw).hexdigest()
 def run_archive(self,pages,**kw):
  size,sha=self.source(pages);return a.archive(self.dump,self.out,size,sha,**kw)
 def receipt(self):
  with sqlite3.connect(self.out)as db:return json.loads(db.execute("select value from meta where key='source'").fetchone()[0])
 def test_every_main_page_and_redirect_without_candidate_filters(self):
  result=self.run_archive(page()+page(2,'転送','転送文',redirect=True)+page(3,'非本文','秘密',ns=1,sha='0'));self.assertTrue(result['complete']);self.assertEqual(2,result['counts']['mainPagesArchived'])
  with sqlite3.connect(self.out)as db:self.assertEqual([(1,'原本の全文',None),(2,'転送文','先')],db.execute('select page_id,content,redirect from pages order by page_id').fetchall())
 def test_restores_only_crypto_proven_legacy_terminal_lf(self):
  result=self.run_archive(page(export_lf=True));self.assertEqual(1,result['counts']['exportTerminalLfRecovered'])
 def test_empty_text_hash_is_checked(self):self.assertTrue(self.run_archive(page(text=''))['complete'])
 def test_invalid_revision_sha_is_incomplete(self):
  with self.assertRaises(ValueError):self.run_archive(page(sha='0'))
  self.assertFalse(self.receipt()['complete'])
 def test_missing_revision_sha_is_incomplete(self):
  with self.assertRaises(ValueError):self.run_archive(page().replace('<sha1>'+base36(int(hashlib.sha1('原本の全文'.encode()).hexdigest(),16))+'</sha1>',''))
  self.assertFalse(self.receipt()['complete'])
 def test_compressed_sha_mismatch_is_incomplete(self):
  size,sha=self.source(page())
  with self.assertRaises(ValueError):a.archive(self.dump,self.out,size,'0'*40)
  self.assertFalse(self.receipt()['complete'])
 def test_truncated_source_is_finite_and_incomplete(self):
  size,sha=self.source(page());self.dump.write_bytes(self.dump.read_bytes()[:-5])
  with self.assertRaises((ValueError,EOFError)):a.archive(self.dump,self.out,size,sha)
  self.assertFalse(self.receipt()['complete'])
 def test_xml_eof_required(self):
  size,sha=self.source(page(),closing=False)
  with self.assertRaises(Exception):a.archive(self.dump,self.out,size,sha)
  self.assertFalse(self.receipt()['complete'])
 def test_duplicate_page_ids_fail(self):
  with self.assertRaises(sqlite3.IntegrityError):self.run_archive(page()+page())
  self.assertFalse(self.receipt()['complete'])
 def test_complete_reuse_pinned_receipt(self):
  one=self.run_archive(page());two=a.archive(self.dump,self.out,one['expectedBytes'],one['expectedSha1']);self.assertEqual(one,two)
 def test_incomplete_restart_same_source_has_no_stale_rows(self):
  size,sha=self.source(page()+page(2,'別記事','別の原文'))
  def stop(value):raise KeyboardInterrupt()
  with self.assertRaises(KeyboardInterrupt):a.archive(self.dump,self.out,size,sha,progress_every=1,emit=stop)
  with sqlite3.connect(self.out)as db:db.execute("insert into pages values(999,'stale','999','x','0','stale',null,null,0)")
  result=a.archive(self.dump,self.out,size,sha);self.assertTrue(result['complete'])
  with sqlite3.connect(self.out)as db:self.assertEqual([1,2],[r[0]for r in db.execute('select page_id from pages order by page_id')])
 def test_invalid_unbounded_wait_rejected(self):
  size,sha=self.source(page())
  for seconds in(float('inf'),float('nan'),61,-1):
   with self.assertRaises(ValueError):a.archive(self.dump,self.out,size,sha,wait_seconds=seconds)
 def test_other_source_receipt_is_preserved(self):
  result=self.run_archive(page())
  with self.assertRaises(ValueError):a.archive(self.dump,self.out,result['expectedBytes'],'0'*40)
  self.assertEqual(result,self.receipt())
 def test_interrupt_preserves_incomplete(self):
  size,sha=self.source(page())
  def stop(value):raise KeyboardInterrupt()
  with self.assertRaises(KeyboardInterrupt):a.archive(self.dump,self.out,size,sha,progress_every=1,emit=stop)
  self.assertFalse(self.receipt()['complete']);self.assertIn('KeyboardInterrupt',self.receipt()['error'])
if __name__=='__main__':unittest.main()
