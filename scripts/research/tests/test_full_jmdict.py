"""Full raw JMdict restriction fixtures; no production sources or gold mutated."""
import argparse,contextlib,gzip,io,json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import full_jmdict as f,worker as w

class FullJmdictTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.path=self.root/'JMdict_e.gz'
    def tearDown(self): self.tmp.cleanup()
    def xml(self,entries,doctype=None):
        doctype=doctype or '<!DOCTYPE JMdict [<!ENTITY n "noun"><!ENTITY v1 "Ichidan verb"><!ENTITY comp "computing"><!ENTITY food "food"><!ENTITY char "character">]>'
        with gzip.open(self.path,'wb') as out: out.write(('<?xml version="1.0"?>'+doctype+'<JMdict>'+entries+'</JMdict>').encode())
    def scan(self,wanted): return list(f.scan(self.path,wanted))
    def test_reading_and_sense_restrictions_keep_separate_pairs_and_glosses(self):
        self.xml('''<entry><ent_seq>1</ent_seq><k_ele><keb>山</keb></k_ele><k_ele><keb>川</keb></k_ele>
        <r_ele><reb>やま</reb><re_restr>山</re_restr></r_ele><r_ele><reb>かわ</reb><re_restr>川</re_restr></r_ele>
        <sense><stagk>山</stagk><stagr>やま</stagr><pos>&n;</pos><field>&comp;</field><gloss>mountain</gloss></sense>
        <sense><stagk>川</stagk><stagr>かわ</stagr><field>&food;</field><gloss>river food</gloss><gloss xml:lang="ger">Fluss</gloss></sense></entry>''')
        records=self.scan({('やま','山'),('やま','川'),('かわ','川'),('かわ','山')})
        self.assertEqual([('やま','山'),('かわ','川')],[(r['reading'],r['surface']) for r in records])
        self.assertEqual(['n'],records[1]['body']['pos']);self.assertEqual([],records[1]['body']['posExplicit'])
        self.assertEqual(['river food','Fluss'],records[1]['body']['glosses'])
        self.assertEqual('ger',records[1]['body']['glossDetails'][1]['language'])
        self.assertEqual('JMdict:1:sense:2',records[1]['target'])
        self.assertTrue(all(r['categories']==[] for r in records))
    def test_re_nokanji_never_attests_the_kanji_reading(self):
        self.xml('<entry><ent_seq>1</ent_seq><k_ele><keb>山</keb></k_ele><r_ele><reb>やま</reb><re_nokanji/></r_ele><sense><pos>&n;</pos><gloss>kana</gloss></sense></entry>')
        records=self.scan({('やま','山'),('やま','やま')})
        self.assertEqual(['やま'],[r['surface'] for r in records]);self.assertTrue(records[0]['body']['re_nokanji'])
    def test_stagk_does_not_leak_kanji_sense_to_kana_form(self):
        self.xml('<entry><ent_seq>1</ent_seq><k_ele><keb>山</keb></k_ele><r_ele><reb>やま</reb></r_ele><sense><stagk>山</stagk><gloss>kanji sense</gloss></sense></entry>')
        self.assertEqual(['山'],[r['surface'] for r in self.scan({('やま','山'),('やま','やま')})])
    def test_pos_override_is_inherited_but_misc_and_field_are_sense_local(self):
        self.xml('''<entry><ent_seq>1</ent_seq><r_ele><reb>かた</reb></r_ele>
        <sense><pos>&n;</pos><misc>&char;</misc><field>&comp;</field><gloss>named character</gloss></sense>
        <sense><gloss>ordinary meaning</gloss></sense><sense><pos>&v1;</pos><gloss>verb</gloss></sense>
        <sense><gloss>second verb</gloss></sense></entry>''')
        records=self.scan({('かた','かた')})
        self.assertEqual([['n'],['n'],['v1'],['v1']],[r['body']['pos'] for r in records])
        self.assertEqual(['character'],records[0]['categories']);self.assertEqual([],records[1]['categories'])
        self.assertEqual([],records[1]['body']['misc']);self.assertEqual([],records[1]['body']['fields'])
    def test_only_existing_normalized_pairs_are_returned(self):
        self.xml('<entry><ent_seq>2</ent_seq><k_ele><keb>ＡＩ</keb></k_ele><r_ele><reb>エーアイ</reb><re_restr>ＡＩ</re_restr></r_ele><sense><stagk>ＡＩ</stagk><stagr>エーアイ</stagr><gloss>AI</gloss></sense></entry>')
        records=self.scan({('えーあい','AI')});self.assertEqual(1,len(records))
        self.assertEqual('ＡＩ',records[0]['body']['rawSurface']);self.assertEqual('AI',records[0]['surface'])
        self.assertEqual([],self.scan({('ほか','ほか')}))
    def test_invalid_restriction_and_external_resources_fail_closed(self):
        self.xml('<entry><ent_seq>1</ent_seq><k_ele><keb>山</keb></k_ele><r_ele><reb>やま</reb><re_restr>川</re_restr></r_ele><sense><gloss>bad</gloss></sense></entry>')
        with self.assertRaisesRegex(ValueError,'reading restriction'): self.scan({('やま','山')})
        self.xml('<entry><ent_seq>1</ent_seq><r_ele><reb>やま</reb></r_ele><sense><stagr>かわ</stagr><gloss>bad</gloss></sense></entry>')
        with self.assertRaisesRegex(ValueError,'sense restriction'): self.scan({('やま','やま')})
        self.xml('',doctype='<!DOCTYPE JMdict SYSTEM "https://example.org/evil.dtd">')
        with self.assertRaisesRegex(ValueError,'External XML'): self.scan(set())
    def test_search_only_forms_are_inspectable_but_never_reading_proofs(self):
        self.xml('''<entry><ent_seq>1</ent_seq><k_ele><keb>橋</keb></k_ele><k_ele><keb>箸</keb><ke_inf>&sK;</ke_inf></k_ele>
        <r_ele><reb>はし</reb></r_ele><sense><gloss>bridge</gloss></sense></entry>
        <entry><ent_seq>2</ent_seq><r_ele><reb>イントランス</reb><re_inf>&sk;</re_inf></r_ele><sense><gloss>entrance</gloss></sense></entry>
        <entry><ent_seq>3</ent_seq><r_ele><reb>かな</reb><re_inf>&ok;</re_inf></r_ele>
        <sense><misc>&obs;</misc><gloss>obsolete lexical meaning</gloss></sense><sense><misc>&arch;</misc><gloss>archaic meaning</gloss></sense><sense><misc>&rare;</misc><gloss>rare meaning</gloss></sense></entry>''',doctype='<!DOCTYPE JMdict [<!ENTITY sk "search-only kana form"><!ENTITY sK "search-only kanji form"><!ENTITY ok "outdated kana usage"><!ENTITY obs "obsolete term"><!ENTITY arch "archaic term"><!ENTITY rare "rare term">]>')
        args=argparse.Namespace(config=str(w.DEFAULT_CONFIG),documents=str(self.root/'docs'),jmdict=str(self.path))
        db=w.connect(self.root/'ledger.sqlite');db.executescript(w.SCHEMA)
        try:
            for y,surface in [('はし','橋'),('はし','箸'),('いんとらんす','イントランス'),('かな','かな')]:w.insert_candidate(db,y,surface,1,1,10)
            with contextlib.redirect_stdout(io.StringIO()):f.import_full(db,args)
            actual={(r[0],r[1]) for r in db.execute("select reading,surface from facts where active=1 and kind='reading'")}
            self.assertEqual({('はし','橋'),('かな','かな')},actual)
            self.assertEqual(6,db.execute("select count(*) from facts where active=1 and kind='meaning'").fetchone()[0])
            self.assertEqual(['arch','obs','rare'],sorted(json.loads(r[0])['misc'][0] for r in db.execute("select body from facts where kind='reading' and reading='かな'")))
            self.assertTrue(all(json.loads(r[0])['fullParserVersion']==2 for r in db.execute('select body from facts')))
        finally:db.close()
    def test_import_preserves_baseline_facts_and_never_inserts_headword_candidates(self):
        self.xml('<entry><ent_seq>1</ent_seq><r_ele><reb>やま</reb></r_ele><sense><pos>&n;</pos><gloss>mountain</gloss></sense></entry><entry><ent_seq>2</ent_seq><r_ele><reb>かわ</reb></r_ele><sense><gloss>river</gloss></sense></entry>')
        args=argparse.Namespace(config=str(w.DEFAULT_CONFIG),documents=str(self.root/'docs'),jmdict=str(self.path))
        db=w.connect(self.root/'ledger.sqlite');db.executescript(w.SCHEMA)
        try:
            cid=w.insert_candidate(db,'やま','やま',1,1,10);e=w.Evidence(db,args)
            doc=e.save('https://example.org/baseline','v1',b'baseline','CC0');baseline=e.fact('やま','やま','reading',[],'baseline',doc,{'source':'Mozc'})
            with contextlib.redirect_stdout(io.StringIO()): first=f.import_full(db,args,e);second=f.import_full(db,args,e)
            self.assertEqual(1,first['matchedPairs']);self.assertEqual(first,second)
            self.assertEqual(1,db.execute('SELECT COUNT(*) FROM candidates').fetchone()[0]);self.assertEqual(1,db.execute('SELECT active FROM facts WHERE id=?',(baseline,)).fetchone()[0])
            meanings=[json.loads(r[0]) for r in db.execute("SELECT body FROM facts WHERE kind='meaning'")]
            self.assertEqual(['mountain'],meanings[0]['glosses'])
            # Retired supplemental rows must be restored by a repeated import,
            # and new input-derived candidates must invalidate the coverage cache.
            db.execute('UPDATE facts SET active=0 WHERE id!=?',(baseline,))
            with contextlib.redirect_stdout(io.StringIO()): rebuilt=f.import_full(db,args,e)
            self.assertEqual(2,rebuilt['activeFacts'])
            w.insert_candidate(db,'かわ','かわ',1,1,10)
            with contextlib.redirect_stdout(io.StringIO()): extended=f.import_full(db,args,e)
            self.assertEqual(2,extended['matchedPairs']);self.assertEqual(2,db.execute('SELECT COUNT(*) FROM candidates').fetchone()[0])
        finally: db.close()

if __name__=='__main__': unittest.main()
