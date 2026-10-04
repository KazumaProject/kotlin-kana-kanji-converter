import gzip,hashlib,json,pathlib,sqlite3,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import page_identity as p
import worker as w

class IdentityTests(unittest.TestCase):
    def test_literal_sql_escapes_are_data(self):
        self.assertEqual(['1',"a'b",'Q1',None],p.parse_sql_tuple("1,'a\\'b','Q1',NULL"))
        self.assertEqual(["a'b",'line\nnext','\\'],p.parse_sql_tuple("'a''b','line\\nnext','\\\\'"))
        with self.assertRaises(ValueError):p.parse_sql_tuple("'unterminated")

    def test_binary_properties_and_source_checksum(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);source=root/'jawiki-20261001-page_props.sql.gz';index=root/'index.sqlite'
            raw=b"CREATE TABLE `page_props` ();\nINSERT INTO `page_props` VALUES\n(1,'binary','\xff',NULL),\n(2,'wikibase_item','Q123',NULL);\n"
            source.write_bytes(gzip.compress(raw));h=hashlib.sha1(source.read_bytes()).hexdigest()
            result=p.build(source,index,h,'https://example.org/source');self.assertTrue(result['complete'])
            with sqlite3.connect(index) as db:self.assertEqual([(2,'Q123',"(2,'wikibase_item','Q123',NULL)")],db.execute('SELECT * FROM page_identity').fetchall())
            self.assertIn("(2,'wikibase_item','Q123',NULL)",w.source_text(source))
            with self.assertRaisesRegex(ValueError,'checksum'):p.build(source,root/'wrong.sqlite','0'*40,'https://example.org/source')
            self.assertFalse((root/'wrong.sqlite').exists())

    def test_invalid_identity_never_completes_index(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);source=root/'source.gz';index=root/'index.sqlite'
            source.write_bytes(gzip.compress(b"INSERT INTO `page_props` VALUES\n(2,'wikibase_item','Qbroken',NULL);\n"))
            with self.assertRaisesRegex(ValueError,'Invalid Wikibase'):p.build(source,index,hashlib.sha1(source.read_bytes()).hexdigest(),'https://example.org/source')
            with sqlite3.connect(index) as db:self.assertFalse(json.loads(db.execute("SELECT value FROM meta WHERE key='source'").fetchone()[0])['complete'])

    def test_other_binary_documents_still_reject_invalid_text(self):
        with tempfile.TemporaryDirectory() as folder:
            source=pathlib.Path(folder)/'unknown';source.write_bytes(b'anything\xff')
            with self.assertRaises(UnicodeDecodeError):w.source_text(source)

if __name__=='__main__':unittest.main()
