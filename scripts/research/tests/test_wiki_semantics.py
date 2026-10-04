import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from wiki_semantics import literal_reading_binding, subject_definition, suggest, named_suggest


class WikipediaSemanticsTest(unittest.TestCase):
    def categories(self, text, surface):
        definition = subject_definition(text, surface)
        return {s['category'] for s in suggest(definition)} if definition else set()

    def test_subject_terminal_head(self):
        self.assertEqual({'general'}, self.categories("'''枕'''（まくら）は、眠るとき頭を支える寝具である。", '枕'))
        self.assertEqual({'food'}, self.categories("'''汁物'''（しるもの）は、汁を主体とした料理の一種である。", '汁物'))
        self.assertEqual({'technical'}, self.categories("'''原理'''（げんり）は、数学における定理である。", '原理'))

    def test_mentions_specialist_scopes_and_named_entities_reject(self):
        self.assertEqual(set(), self.categories("'''A社'''（えーしゃ）は、寝具を販売する会社である。", 'A社'))
        self.assertEqual(set(), self.categories("'''量'''（りょう）は、物理学で測られる心理状態である。", '量'))
        self.assertEqual(set(), self.categories("'''人'''（ひと）は、料理が好きな人物である。", '人'))
        self.assertEqual(set(), self.categories("'''歌'''（うた）は、料理を題材にした楽曲である。", '歌'))
        self.assertEqual(set(), self.categories("'''寝具'''（しんぐ）は、品物である。枕は寝具である。", '寝具'))
        self.assertEqual(set(), self.categories("'''手'''（て）は、病気の人を助ける道具という比喩である。", '手'))
        self.assertEqual(set(), self.categories("'''カメラ'''（かめら）は、SF漫画『ドラえもん』に登場するひみつ道具。", 'カメラ'))
        self.assertEqual(set(), self.categories("'''奉行'''（ぶぎょう）は、江戸幕府の役職の一つ。", '奉行'))
        self.assertEqual(set(), self.categories("'''防護服'''（ぼうごふく）は、放射線を防ぐ特殊な衣服である。", '防護服'))
        self.assertEqual(set(), self.categories("'''黒ひげ'''（くろひげ）は、タカラトミーによる玩具。", '黒ひげ'))
        self.assertEqual(set(), self.categories("'''行列'''（ぎょうれつ）は、店の前に並ぶ行列である。", '行列'))

    def test_templates_and_references_cannot_supply_head(self):
        text = "'''枕'''（まくら）は、寝具である<ref>会社についての資料</ref>{{出典|会社}}。"
        self.assertEqual({'general'}, self.categories(text, '枕'))
        self.assertEqual(set(), self.categories("'''枕'''（まくら）は、物品である{{注|寝具}}。", '枕'))

    def test_literal_independent_reading_and_target_binding(self):
        content = "'''枕'''（まくら）は、寝具である。"
        p = {'candidate': {'id': 'x', 'surface': '枕', 'reading': 'まくら'}, 'target': '枕',
             'body': {'source': 'explicit-name-reading', 'name': '枕', 'reading': 'まくら', 'quotation': "'''枕'''（まくら"}}
        self.assertTrue(literal_reading_binding(p, content, '枕'))
        self.assertFalse(literal_reading_binding(dict(p, target='枕#mentioned-name:枕'), content, '枕'))
        p['candidate']['reading'] = 'しん'
        self.assertFalse(literal_reading_binding(p, content, '枕'))
        p['candidate']['reading'] = 'まくら'
        p['body']['quotation'] = "'''枕'''（しん"
        self.assertFalse(literal_reading_binding(p, content, '枕'))

    def test_manufactured_aircraft_type_is_a_product_model(self):
        definition=subject_definition("'''空鳥'''（そらどり）は、A社が開発した無人航空機である。",'空鳥')
        self.assertEqual({'product'},{v['category'] for v in named_suggest(definition)})
        definition=subject_definition("'''空鳥'''（そらどり）は、A社が製造した機体記号JA1234の航空機である。",'空鳥')
        self.assertNotIn('product',{v['category'] for v in named_suggest(definition)})

    def test_design_evidence_stays_in_the_same_subject_paragraph(self):
        definition=subject_definition("'''空鳥'''（そらどり）は、陸軍の爆撃機である。設計・製造はA社。",'空鳥')
        self.assertEqual({'product'},{v['category'] for v in named_suggest(definition)})
        definition=subject_definition("'''空鳥'''（そらどり）は、陸軍の爆撃機である。\n\n別の機種はA社が製造した。",'空鳥')
        self.assertNotIn('product',{v['category'] for v in named_suggest(definition)})
        definition=subject_definition("'''空鳥'''（そらどり）は、陸軍の爆撃機である。別の機種はA社が製造した。",'空鳥')
        self.assertNotIn('product',{v['category'] for v in named_suggest(definition)})
        definition=subject_definition("'''空鳥'''（そらどり）は、A社が製造した航空機である。登録番号はJA1234。",'空鳥')
        self.assertNotIn('product',{v['category'] for v in named_suggest(definition)})

    def test_specific_subject_types_override_generic_ontology_types(self):
        for text,category in (
            ('国内の証券取引所である。','organization'),
            ('回転寿司のチェーン店である。','facility'),
            ('アミューズメント施設である。','facility'),
            ('A社によるフォントのパックである。','product'),
            ('二輪の電気自動車の開発プロジェクトである。','product'),
            ('情報工学における新しい研究分野である。','technical'),
            ('電子媒体のファイルシステム規格を定義したものである。','technical'),
            ('造船所で建造されたタンカーの形式であるが、名称の由来は異なる。','product'),
        ):
            with self.subTest(text=text):
                definition=subject_definition("'''対象'''（たいしょう）は、"+text,'対象')
                self.assertEqual({category},{v['category'] for v in named_suggest(definition)})


if __name__ == '__main__':
    unittest.main()
