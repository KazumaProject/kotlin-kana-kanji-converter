import bz2,collections,hashlib,json,pathlib,sqlite3,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import wiki_dump as d

class DumpTests(unittest.TestCase):
    def test_raw_html_quote_is_recovered_without_accepting_invented_quote(self):
        text="'''山田'''<small>（やまだ）</small>は作家。"
        self.assertEqual(text,d.literal_quote(text,'山田（やまだ'))
        self.assertIsNone(d.literal_quote(text,'田中（たなか'))
    def row(self,name,y): return {'id':name+'-'+y,'surface':name,'reading':y}
    def index(self,*rows):
        index=collections.defaultdict(list)
        for row in rows: index[d.name_key(row['surface'])].append(row)
        return index
    def test_whole_name_and_different_reading(self):
        index=self.index(self.row('井上太郎','いのうえたろう'),self.row('太郎','いのうえたろう'),self.row('井上太郎','いのうえじろう'))
        found=d.bindings_for_page('井上太郎',"'''井上太郎'''（いのうえ たろう）は作家。",index)
        self.assertEqual([(f[0]['surface'],f[1]) for f in found],[('井上太郎','井上太郎')])
    def test_disambiguation_primary_and_mentioned_name(self):
        index=self.index(self.row('風間','かざま'),self.row('山田','やまだ'))
        found=d.bindings_for_page('風間 (人物)',"'''風間'''（かざま）は、山田（やまだ）と共演。",index)
        self.assertEqual({f[1] for f in found},{'風間 (人物)','風間 (人物)#mentioned-name:山田'})
    def test_kana_name_requires_primary_subject(self):
        row=self.row('アニメイト','あにめいと');index=self.index(row)
        self.assertEqual(d.bindings_for_page('映画',"アニメイトが登場。",index),[])
        self.assertEqual(len(d.bindings_for_page('アニメイト','企業。',index)),1)
    def test_infobox_name_is_not_main_subject(self):
        index=self.index(self.row('山田','やまだ'))
        found=d.bindings_for_page('映画',"{{人物|名前=山田|ふりがな=やまだ}}",index)
        self.assertTrue(all('#mentioned-name:' in f[1] for f in found))
    def test_redirect_searches_literal_readings_without_kana_self_approval(self):
        index=self.index(self.row('山田','やまだ'),self.row('アニメイト','あにめいと'))
        found=d.bindings_for_page('アニメイト','#REDIRECT [[山田]]\n山田（やまだ）',index,redirect=True)
        self.assertEqual([f[0]['surface'] for f in found],['山田'])
        self.assertTrue(all('#mentioned-name:' in f[1] for f in found))
    def test_verified_staging_and_wrong_checksum(self):
        raw=b'<mediawiki xmlns="urn:wiki"><page><title>Test</title><ns>0</ns><id>1</id><revision><id>3</id><timestamp>2026-10-01</timestamp><text>Test</text></revision></page></mediawiki>'
        data=bz2.compress(raw)
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'wiki.bz2';path.write_bytes(data);stage=pathlib.Path(folder)/'source.sqlite'
            result=d.stage(path,stage,self.index(self.row('Test','test')),len(data),hashlib.sha1(data).hexdigest())
            self.assertTrue(result['complete']);self.assertEqual(result['counts']['contextPairs'],1)
            other=pathlib.Path(folder)/'bad.sqlite'
            with self.assertRaisesRegex(ValueError,'checksum mismatch'): d.stage(path,other,{},len(data),'0'*40)
            with sqlite3.connect(other) as db: self.assertFalse(json.loads(db.execute("SELECT value FROM meta WHERE key='source'").fetchone()[0])['complete'])
    def test_incomplete_dump_is_finite_and_not_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            data=bz2.compress(b'<mediawiki/>');path=pathlib.Path(folder)/'partial';path.write_bytes(data[:-1])
            with self.assertRaises(ValueError): d.stage(path,pathlib.Path(folder)/'source.sqlite',{},len(data),'0'*40)
    def test_cohort_mismatch_rejects_cached_stage(self):
        data=bz2.compress(b'<mediawiki/>')
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'wiki';path.write_bytes(data);stage=pathlib.Path(folder)/'source.sqlite'
            d.stage(path,stage,{},len(data),hashlib.sha1(data).hexdigest())
            with self.assertRaisesRegex(ValueError,'cohort mismatch'): d.stage(path,stage,self.index(self.row('A','a')),len(data),hashlib.sha1(data).hexdigest())
    def test_export_newline_recovery_requires_exact_revision_hash(self):
        text='subject';value=int(hashlib.sha1(text.encode()).hexdigest(),16);digits='0123456789abcdefghijklmnopqrstuvwxyz';encoded=''
        while value: value,n=divmod(value,36);encoded=digits[n]+encoded
        self.assertEqual(d.verified_page_text(text+'\n',encoded,len(text)),text)
        self.assertEqual(d.verified_page_text(text+'\n',encoded,len(text)+1),text)
        with self.assertRaises(ValueError): d.verified_page_text(text+'x\n',encoded,len(text)+1)

if __name__=='__main__': unittest.main()
