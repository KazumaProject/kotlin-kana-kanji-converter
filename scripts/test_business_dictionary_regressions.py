import gzip
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import classified_distribution as distribution  # noqa: E402
import person_name_origin_classification as name_origins  # noqa: E402


READING_CORRECTIONS = {
    ('ぎょう', 'サービス業'): 'さーびすぎょう',
    ('ざんぎょう', 'みなし残業'): 'みなしざんぎょう',
    ('せい', 'フレックスタイム制'): 'ふれっくすたいむせい',
    ('せいど', 'キャリアコンサルティング制度'): 'きゃりあこんさるてぃんぐせいど',
    ('せいど', 'メンター制度'): 'めんたーせいど',
    ('せき', 'けん責'): 'けんせき',
    ('つうきん', 'マイカー通勤'): 'まいかーつうきん',
    ('ひょう', 'シフト表'): 'しふとひょう',
    ('ろうどうしゃ', 'パートタイム労働者'): 'ぱーとたいむろうどうしゃ',
}

TERM_TARGETS = {
    ('はいそうかんり', '配送管理'): 'term/specialist/transport_safety_defense',
    ('みしゅうしゅうえき', '未収収益'): 'term/specialist/economics_management',
    ('かくていきゅうふねんきん', '確定給付年金'): 'term/specialist/law_politics',
    ('こうたいきんむ', '交替勤務'): 'term/specialist/economics_management',
    ('しょうびょうてあてきん', '傷病手当金'): 'term/specialist/law_politics',
    ('ひじょうさいがい', '非常災害'): 'term/specialist/transport_safety_defense',
    ('こうせいねんきんほけん', '厚生年金保険'): 'term/specialist/law_politics',
    ('げんきんすいとうちょう', '現金出納帳'): 'term/specialist/economics_management',
    ('きょうぎょうひしぎむ', '競業避止義務'): 'term/specialist/law_politics',
    ('こくみんねんきんほけん', '国民年金保険'): 'term/specialist/law_politics',
    ('へんけいろうどうじかんせい', '変形労働時間制'): 'term/specialist/law_politics',
    ('きかいせつび', '機械設備'): 'term/specialist/engineering_technology',
    ('きんゆうきかん', '金融機関'): 'term/specialist/economics_management',
    ('しょうけんそうごうこうざ', '証券総合口座'): 'term/specialist/economics_management',
    ('すいどうこうねつひ', '水道光熱費'): 'term/specialist/economics_management',
    ('つうか', '通貨'): 'term/specialist/economics_management',
    ('とりひきさき', '取引先'): 'term/specialist/economics_management',
    ('よちょきんこうざ', '預貯金口座'): 'term/specialist/economics_management',
    ('しょうかせつび', '消火設備'): 'term/specialist/transport_safety_defense',
    ('たなおろししさん', '棚卸資産'): 'term/specialist/economics_management',
    ('ねんげんろく', '年限禄'): 'term/specialist/humanities_social_sciences',
}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


class BusinessDictionaryRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = ROOT / 'src/main/classification'
        with gzip.open(directory / 'distribution-decisions.tsv.gz', 'rt', encoding='utf-8') as stream:
            cls.decisions = {
                tuple(row[:2]): row for row in
                (line.rstrip('\n').split('\t') for line in stream)
            }
        with gzip.open(directory / 'distribution-candidates.tsv.gz', 'rt', encoding='utf-8') as stream:
            cls.candidates = [line.rstrip('\n').split('\t') for line in stream]
        with gzip.open(directory / 'person-dictionary-candidates.tsv.gz', 'rt', encoding='utf-8') as stream:
            cls.person_candidates = [line.rstrip('\n').split('\t') for line in stream]
        cls.corrections = read_jsonl(
            directory / 'reviews/2026-10-27-business-mhlw-reading-corrections.jsonl')
        cls.history = read_jsonl(directory / 'reviews/2026-10-26-business-mhlw.jsonl')

    def test_mhlw_wrong_partial_reads_are_removed_and_full_reads_keep_original_pos_cost(self):
        correction_by_pair = {(row['reading'], row['surface']): row for row in self.corrections}
        history_by_pair = {(row['reading'], row['surface']): row for row in self.history}
        for (wrong_reading, surface), correct_reading in READING_CORRECTIONS.items():
            with self.subTest(surface=surface):
                wrong_pair = (wrong_reading, surface)
                correct_pair = (correct_reading, surface)
                old_review = history_by_pair[wrong_pair]
                hold = correction_by_pair[wrong_pair]
                add = correction_by_pair[correct_pair]

                self.assertEqual(hold['action'], 'hold')
                self.assertEqual(hold['added_record'], old_review['added_record'])
                self.assertEqual(hold['evidence']['sourceRowIds'], old_review['evidence']['sourceRowIds'])
                self.assertEqual(hold['evidence']['sourceSha256'], old_review['evidence']['sourceSha256'])
                self.assertEqual(self.decisions[wrong_pair][4], 'excluded')
                self.assertFalse(any(row[1] == wrong_reading and row[5] == surface
                                     for row in self.candidates))

                self.assertEqual(add['action'], 'add')
                self.assertEqual(add['added_record'], old_review['added_record'])
                components = add['evidence']['readingComponents']
                self.assertEqual(''.join(component['surface'] for component in components), surface)
                self.assertEqual(''.join(component['reading'] for component in components), correct_reading)
                self.assertEqual(add['evidence']['sourceRowIds'], old_review['evidence']['sourceRowIds'])
                self.assertEqual(add['evidence']['sourceSha256'], old_review['evidence']['sourceSha256'])
                self.assertEqual(self.decisions[correct_pair][4], 'classified')
                self.assertEqual(self.decisions[correct_pair][2], 'term/specialist/law_politics')
                expected = add['added_record']
                found = [row for row in self.candidates if row[1] == correct_reading and row[5] == surface
                         and row[2:5] == [str(expected['left_id']), str(expected['right_id']),
                                          str(expected['cost'])]]
                self.assertEqual(len(found), 1)

    def test_term_semantics_and_holds_are_separate_from_source_publisher(self):
        for pair, category in TERM_TARGETS.items():
            with self.subTest(surface=pair[1]):
                source = 'verified' if pair == ('ねんげんろく', '年限禄') else 'manual'
                self.assertEqual(self.decisions[pair][2:5], [category, source, 'classified'])
                self.assertTrue(any(row[1] == pair[0] and row[5] == pair[1] and row[0] == category
                                    for row in self.candidates))

        held_pair = ('ようけんていぎ', '要件定義')
        self.assertEqual(self.decisions[held_pair][4], 'excluded')
        self.assertFalse(any(row[1] == held_pair[0] and row[5] == held_pair[1]
                             for row in self.candidates))

        nobody = self.decisions[('のーばでぃ', 'NOBODY')]
        self.assertEqual(nobody[2:5], ['organization', 'verified', 'classified'])
        self.assertTrue(any(row[0] == 'organization' and row[1] == 'のーばでぃ' and row[5] == 'NOBODY'
                            for row in self.candidates))
        self.assertFalse(any(row[0] == 'person' and row[1] == 'のーばでぃ' and row[5] == 'NOBODY'
                             for row in self.candidates))

    def test_confirmed_full_names_are_not_distributed_as_surnames(self):
        names = [
            ('いわもとやすひで','岩本泰英'),('おさだまさよし','長田雅喜'),('かわばたていじ','河端貞次'),
            ('かんき','韓軌'),('これかわぎんぞう','是川銀蔵'),('こんどうせいや','近藤誠也'),
            ('こんのかつこ','今野華都子'),('さいさいこう','蔡再鴻'),('とみたただすけ','冨田ただすけ'),
            ('とーますせうぇる','トーマスセウェル'),('なかとみさぶろう','中冨三郎'),
            ('なかにしすすむ','中西進'),('なかのみゆき','中野みゆき'),('ひろせさとし','廣瀬智央'),
            ('びんおんたく','閔恩沢'),('ふぁんびょんそ','黄炳瑞'),('ふうじょ','馮如'),('もろさわまさお','諸澤昌男'),
        ]
        pages = ROOT / 'docs/classified-dictionary-catalog/person'
        surname_text = '\n'.join(
            path.read_text(encoding='utf-8')
            for category in pages.glob('surname_origin_*')
            for path in category.glob('page-*.md'))
        full_name_text = '\n'.join(path.read_text(encoding='utf-8')
                                    for path in (pages / 'personal_name_origin_unconfirmed').glob('page-*.md'))
        for reading, surface in names:
            with self.subTest(surface=surface):
                key = f'<code>{reading}</code> | <code>{surface}</code>'
                self.assertIn(key, full_name_text)
                self.assertNotIn(key, surname_text)

        for pair in [('ねんげんろく', '年限禄'), ('のーばでぃ', 'NOBODY')]:
            key = f'<code>{pair[0]}</code> | <code>{pair[1]}</code>'
            self.assertNotIn(key, surname_text)

    def test_person_dictionary_applies_type_review_without_changing_pos_or_cost(self):
        expected_costs = {
            ('いわもとやすひで','岩本泰英'): '8400', ('おさだまさよし','長田雅喜'): '8400',
            ('かわばたていじ','河端貞次'): '8400', ('かんき','韓軌'): '8400',
            ('これかわぎんぞう','是川銀蔵'): '8400', ('こんどうせいや','近藤誠也'): '8400',
            ('こんのかつこ','今野華都子'): '9431', ('さいさいこう','蔡再鴻'): '8400',
            ('とみたただすけ','冨田ただすけ'): '9425', ('とーますせうぇる','トーマスセウェル'): '8400',
            ('なかとみさぶろう','中冨三郎'): '8400', ('なかにしすすむ','中西進'): '7980',
            ('なかのみゆき','中野みゆき'): '8400', ('ひろせさとし','廣瀬智央'): '9423',
            ('びんおんたく','閔恩沢'): '8400', ('ふぁんびょんそ','黄炳瑞'): '8441',
            ('ふうじょ','馮如'): '8400', ('もろさわまさお','諸澤昌男'): '9400',
        }
        for (reading, surface), cost in expected_costs.items():
            with self.subTest(surface=surface):
                matches = [row for row in self.person_candidates
                           if row[1] == reading and row[5] == surface]
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0][0], 'personal_name_origin_unconfirmed')
                self.assertEqual(matches[0][2:5], ['1851', '1851', cost])

        tomislav = [row for row in self.person_candidates
                    if row[1] == 'とみすらふ' and row[5] == 'トミスラフ']
        self.assertEqual(len(tomislav), 1)
        self.assertEqual(tomislav[0][0], 'given_name_origin_foreign')
        self.assertEqual(tomislav[0][2:5], ['1851', '1851', '7890'])
        for pair in [('ねんげんろく', '年限禄'), ('のーばでぃ', 'NOBODY')]:
            self.assertFalse(any(row[1] == pair[0] and row[5] == pair[1]
                                 for row in self.person_candidates))
        self.assertFalse(any(row[0] == 'surname_origin_foreign'
                             and (row[1], row[5]) in expected_costs
                             for row in self.person_candidates))

        manifest = json.loads((ROOT / 'src/main/classification/person-name-origin-classification-manifest.json')
                              .read_text(encoding='utf-8'))
        review = manifest['manual_type_review']
        artifact = review['dictionary_artifact']
        # This artifact describes the result at the time of that review. Later
        # source-backed additions can legitimately change the current file.
        self.assertEqual(artifact['records_before'], manifest['source_dictionary_records_after_japanese_origin_review'])
        self.assertEqual(artifact['previous_sha256'], manifest['source_dictionary_sha256_after_japanese_origin_review'])
        self.assertEqual(artifact['records'], artifact['records_before'] - artifact['excluded_records'])
        self.assertEqual(artifact['changed_records'], 19)
        self.assertEqual(artifact['excluded_records'], 2)
        self.assertRegex(artifact['sha256'], r'^[0-9a-f]{64}$')
        review_path = ROOT / review['review_path']
        self.assertEqual(review['review_sha256'], hashlib.sha256(review_path.read_bytes()).hexdigest())

    def test_manifest_counts_match_generated_rows(self):
        manifest = json.loads((ROOT / 'src/main/classification/distribution-manifest.json')
                              .read_text(encoding='utf-8'))
        self.assertEqual(manifest['dictionaryRows'], len(self.candidates))
        self.assertEqual(manifest['uniqueAdmittedPairs'],
                         len({(row[1], row[5]) for row in self.candidates}))


if __name__ == '__main__':
    unittest.main()
