import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import reading_patch as p
import wiki_dump as d

class ReadingPatchTests(unittest.TestCase):
    def binding(self,title,text,surface,reading):
        row={'id':'fixture','surface':surface,'reading':reading}
        return p.corrected_bindings(title,text,{d.name_key(surface):[row]})
    def test_adjacent_alias_has_both_printed_readings(self):
        text="'''東京圏輸送管理システム'''（とうきょうけんゆそうかんりシステム、通称'''ATOS'''（エイトス、アトス））とは管理システム。"
        found=self.binding('東京圏輸送管理システム',text,'ATOS','あとす')
        self.assertEqual(1,len(found));self.assertEqual('declared-adjacent-primary-alias',found[0][1]['binding'])
        self.assertIn(found[0][1]['quotation'],text)
    def test_another_person_alias_is_not_attached(self):
        text="'''田中'''（たなか）は、山田（通称'''ATOS'''（アトス））と共演。"
        self.assertEqual([],self.binding('田中',text,'ATOS','あとす'))
    def test_citation_at_reading_boundary_preserves_literal_quote(self):
        for ref in ('{{Sfn|source|2020}}','<ref>出典</ref>'):
            text="'''田舎荘子'''（いなかそうじ"+ref+'）は書籍。'
            found=self.binding('田舎荘子',text,'田舎荘子','いなかそうじ')
            self.assertEqual(1,len(found));self.assertIn(found[0][1]['quotation'],text)
    def test_quoted_name_does_not_guess_another_reading(self):
        text="『'''本'''』（ほん）は本。"
        self.assertEqual(1,len(self.binding('本',text,'本','ほん')))
        self.assertEqual([],self.binding('本',text,'本','ぼん'))
    def test_primary_company_prints_bare_name_reading(self):
        for name in ('株式会社篠崎屋','篠崎屋株式会社'):
            found=self.binding('篠崎屋',"'''"+name+"'''（しのざきや）は会社。",'篠崎屋','しのざきや')
            self.assertEqual(1,len(found));self.assertEqual('literal-primary-company-legal-name-boundary',found[0][1]['binding'])
    def test_legal_designation_reading_is_not_added(self):
        self.assertEqual([],self.binding('篠崎屋',"'''株式会社篠崎屋'''（しのざきや）は会社。",'篠崎屋','かぶしきがいしゃしのざきや'))
    def test_other_company_mention_cannot_become_primary(self):
        self.assertEqual([],self.binding('別会社',"'''別会社'''は株式会社。'''株式会社篠崎屋'''（しのざきや）と取引。",'篠崎屋','しのざきや'))
    def test_self_closing_reference_does_not_consume_following_reading(self):
        text="'''株式会社エフエム徳島'''<ref name=\"company\"/>（エフエムとくしま、英語名<ref>資料</ref>）は会社。"
        self.assertIn('エフエムとくしま',p.visible_source(text))
        self.assertNotIn('資料',p.visible_source(text))
    def test_literal_kana_separators_never_merge_alternative_readings(self):
        self.assertIn('そるぎひょん',p.quoted_phonetic_text('ソル・ギヒョン'))
        self.assertIn('かたんすいけいてっきょう',p.quoted_phonetic_text('かたんすいけい-てっきょう'))
        self.assertEqual('えいとす、あとす',p.quoted_phonetic_text('エイトス、アトス'))
        self.assertEqual('あーる',p.quoted_phonetic_text('アール'))

if __name__=='__main__':unittest.main()
