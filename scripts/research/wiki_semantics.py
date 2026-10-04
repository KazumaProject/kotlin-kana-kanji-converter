"""Audit subject-bound Wikipedia definitions without writing the research ledger.

The source_review suggestions are deliberately separate from independent gold.
Incomplete dump staging is readable for research, but never release evidence.
"""
import argparse
import collections
import hashlib
import html
import json
import pathlib
import re
import sqlite3
import unicodedata

HEADS = {
    'general': {
        'ordinary-object': '道具 用具 日用品 生活用品 家具 衣服 衣類 寝具 筆記具 食器 玩具 文房具 建具',
        'ordinary-social-relationship': '人間関係 社会関係 親族関係 親族 婚姻関係',
        'ordinary-feeling': '感情 気持ち 心理状態',
        'ordinary-practice': '慣習 習慣 風習 遊び 娯楽 生活文化',
        'ordinary-human-role': '職業 職種',
    },
    'technical': {
        'clinical-condition': '病気 疾患 病状 症候群 感染症 腫瘍 がん 悪性腫瘍 炎症 精神疾患',
        'clinical-intervention': '治療法 医療行為 手術 医薬品 薬剤 ワクチン 抗生物質 検査法',
        'chemical-entity': '化合物 有機化合物 無機化合物 化学物質 元素 同位体 錯体 高分子 アミノ酸 脂肪酸 酵素 タンパク質 抗体 ホルモン',
        'mathematical-entity': '方程式 微分方程式 代数方程式 定理 公式 多項式 関数 数列 行列 位相空間 ベクトル空間 群 代数幾何学',
        'computing-concept': 'アルゴリズム データ構造 通信プロトコル 暗号方式 符号化方式 文字コード コンピュータネットワーク',
        'physical-entity': '素粒子 物理量 光学現象 電磁波 放射線',
    },
    'food': {
        'prepared-food': '料理 郷土料理 麺料理 鍋料理 食品 食べ物 食材 調味料 菓子 洋菓子 和菓子 パン 汁物 スープ 漬物 加工食品',
        'drink': '飲料 清涼飲料 酒 酒類 蒸留酒 醸造酒 カクテル 茶',
    },
}
SPECIALIST_GENERAL = re.compile(
    '数学|物理|化学|生物学|医学|医療|法律|法学|法令|憲法|税法|刑法|民法|会計|金融|証券|株式|保険|'
    '情報工学|計算機|コンピュータ|プログラミング|軍事|軍隊|軍人|軍官|宗教|仏教|神道|神職|'
    '天文学|天体|地質|地理学|経済学|心理学|哲学|論理学|専門|特殊|儀式|祭祀|'
    '刑罰|拷問|風水|皇帝|幕府|豊臣政権|忍者|国家公務員|自衛隊|放射線|放射性|'
    '鉄道車両|スクーバダイビング|サーフィン|水中土木|サルベージ|Law of the Game|競技者|競技規則')
NAMED_ENTITY = re.compile('登場人物|架空|キャラクター|漫画作品|アニメ作品|小説|映画|テレビドラマ|'
                         'テレビ番組|楽曲|アルバム|登場する|登場した|ひみつ道具|による玩具|商品名|商標|ブランド|会社|企業|株式会社|財団法人|'
                         '行政機関|自治体|地方公共団体|人物|生まれ|出身|プロ野球選手|プロサッカー選手')
END = r'(?:の(?:一種|ひとつ|一つ|総称|名称))?(?:である|であった|です|を指す|をいう|を言う|を意味する|とされる)?[。．]?\s*$'
NAMED_HEADS={
    'facility':'城 城郭 山城 平山城 平城 建物 建築物 寺院 神社 祠 博物館 美術館 商業施設 アミューズメント施設 店舗 書店 雑貨店 飲食店 寿司店 チェーン店 映画館チェーン 劇場 映画館 シネマコンプレックス シネコン 空港 病院 橋 トンネル ダム 信号場',
    'station':'駅 鉄道駅 停留所 バス停',
    'organization':'会社 株式会社 有限会社 企業 鉄道事業者 学校 大学 団体 協会 組織 証券取引所',
    'product':'ソフトウェア アプリケーション アプリ メールクライアント ウェブブラウザ ブランド 商標 商品 製品 車種 型番 モデル 船型 航空機モデル フォント フォント集 フォントパッケージ',
    'technical':'電子書類フォーマット 電子文書フォーマット 文書フォーマット ファイル形式 ファイルフォーマット プログラミング言語 形式言語 通信プロトコル 文字コード 技術規格 工業規格 通信規格 標準規格 API',
    'food':'料理 郷土料理 麺料理 鍋料理 食品 食べ物 食材 調味料 菓子 洋菓子 和菓子 パン 汁物 スープ 漬物 加工食品 飲料 清涼飲料 酒 酒類 蒸留酒 醸造酒 カクテル',
    'event':'祭り 祭礼 大会 競技大会 音楽祭 映画祭 戦争 戦闘 合戦 事件 事故 災害',
    'general':'道具 用具 日用品 生活用品 家具 衣服 衣類 寝具 筆記具 食器 玩具 文房具 建具 タイヤ 都市伝説 陰謀論',
}


def named_suggest(definition):
    """An exact named subject's explicit grammatical type, never a mentioned type."""
    result=[];predicate=definition['predicate'];paragraph=definition.get('paragraph',predicate)
    production_attribution=any(re.match(r'\s*(?:設計|開発|製造|生産)(?:・(?:設計|開発|製造|生産))*は',sentence)
        for sentence in paragraph.split('。')[1:4])
    if ((re.search('(?:開発|設計|製造|生産)(?:さ|し|す|を)',predicate) or production_attribution)
            and not re.search('(?:個体|登録機|機体記号|航空機登録|登録番号|号機|愛称)',paragraph)
            and re.search('(?:航空機|飛行機|飛行艇|爆撃機|戦闘機|練習機|ヘリコプター)'+END,predicate)):
        return [{'category':'product','head':'製造または開発された航空機種','rule':'explicit-manufactured-aircraft-design','method':'source_review'}]
    if re.search('(?:自動車|航空機|飛行機|車両)の開発プロジェクト'+END,predicate):
        return [{'category':'product','head':'乗り物の開発プロジェクト','rule':'explicit-vehicle-development-design','method':'source_review'}]
    if re.search('(?:船型|船舶|タンカー|油槽船|貨物船|客船)の形式である(?:が[、,]|[。．])',predicate):
        return [{'category':'product','head':'船舶の形式','rule':'explicit-ship-design-type','method':'source_review'}]
    if re.search('フォントのパック'+END,predicate):
        return [{'category':'product','head':'フォントのパック','rule':'explicit-font-package','method':'source_review'}]
    if re.search('(?:ファイルシステム|通信|電子文書|画像)(?:規格|形式)を定義したもの'+END,predicate):
        return [{'category':'technical','head':'電子媒体の規格定義','rule':'explicit-computing-standard-definition','method':'source_review'}]
    if (re.search('(?:計算機科学|情報工学|物理学|化学|数学|医学|工学)における',predicate)
            and re.search('(?:学問領域|研究分野)'+END,predicate)):
        return [{'category':'technical','head':'明示された科学・工学の研究分野','rule':'explicit-stem-research-field','method':'source_review'}]
    for category,heads in NAMED_HEADS.items():
        if category=='general' and (SPECIALIST_GENERAL.search(predicate) or NAMED_ENTITY.search(predicate) or re.search('発売|販売|製造',predicate)):continue
        for head in sorted(heads.split(),key=len,reverse=True):
            match=re.search(re.escape(head)+END,predicate)
            if match and (not match.start() or not re.match(r'[一-龥々ァ-ヶA-Za-z0-9]',predicate[match.start()-1])):
                result.append({'category':category,'head':head,'rule':'explicit-named-subject-terminal-type','method':'source_review'});break
    return result


def name_key(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value))


def reading_key(value):
    value = unicodedata.normalize('NFKC', value)
    return ''.join(chr(ord(c)-96) if 'ァ' <= c <= 'ヶ' else c for c in value)


def plain(value):
    value = re.sub(r'<!--.*?-->', '', value, flags=re.S)
    value = re.sub(r'<ref\b[^>]*(?:/>|>.*?</ref>)', '', value, flags=re.S | re.I)
    value = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]+)\]\]', r'\1', value)
    # Remove balanced templates rather than allowing their internal headings to classify.
    for _ in range(20):
        new = re.sub(r'\{\{[^{}]*\}\}', '', value)
        if new == value:
            break
        value = new
    value = re.sub(r'<[^>]+>', '', value)
    return html.unescape(value.replace("'''", '').replace("''", '')).strip()


def subject_definition(content, surface):
    """Only a bold exact subject's first paragraph and first grammatical sentence."""
    for match in re.finditer(r"'''([^'\n]+)'''", content[:24000]):
        if name_key(plain(match[1])) != name_key(surface):
            continue
        raw = content[match.start():].split('\n\n', 1)[0].split('\n==', 1)[0]
        if len(raw) > 8000:
            return None
        text = plain(raw)
        # Parenthetical readings/citations do not supply a semantic head.
        for _ in range(20):
            new = re.sub(r'（[^（）]*）|\([^()]*\)', '', text)
            if new == text:
                break
            text = new
        paragraph=text
        text = text.split('。', 1)[0].strip() + '。'
        prefix = re.escape(plain(match[1]))
        predicate = re.match(prefix + r'\s*(?:とは|は)[、,\s]*(.*)', text)
        if not predicate:
            return None
        return {'quotation': raw, 'definition': text, 'predicate': predicate[1], 'paragraph': paragraph}
    return None


def suggest(definition):
    """Only enumerated semantic heads at the definition's grammatical terminus."""
    predicate = definition['predicate']
    if NAMED_ENTITY.search(predicate):
        return []
    result = []
    for category, families in HEADS.items():
        if category == 'general' and (SPECIALIST_GENERAL.search(predicate)
                or re.search('発売|販売|製造', predicate)):
            continue
        for family, heads in families.items():
            for head in sorted(heads.split(), key=len, reverse=True):
                match = re.search(re.escape(head) + END, predicate)
                if not match:
                    continue
                if family == 'mathematical-entity' and head in ('群', '関数', '行列') and not re.search(
                        '数学|代数|幾何|数値|ベクトル|位相|正方|行要素|列要素|関数値|逆関数|変数|整数|実数|複素数|演算', predicate):
                    continue
                # A suffix embedded within a larger unknown compound is not a head.
                if match.start() and re.match(r'[一-龥々ァ-ヶA-Za-z0-9]', predicate[match.start()-1]):
                    continue
                result.append({'category': category, 'rule': family, 'head': head,
                               'method': 'source_review'})
                break
    return result


def literal_reading_binding(proof, content, title):
    candidate, body = proof['candidate'], proof['body']
    if proof['target'] != title or name_key(body.get('name', '')) != name_key(candidate['surface']):
        return False
    if body.get('source') == 'attested-canonical-kana':
        return (name_key(title) == name_key(candidate['surface'])
                and re.fullmatch('[ぁ-ゖァ-ヶー]+', title) is not None
                and reading_key(title) == reading_key(candidate['reading']))
    quotation = body.get('quotation', '')
    if body.get('source') != 'explicit-name-reading' or not quotation or quotation not in content:
        return False
    # Independent literal inspection of printed subject and parenthetical reading.
    match = re.fullmatch(r"(?:'''|\[\[)?(.+?)(?:'''|\]\])?[ （(]+([^（）()]+)", quotation)
    return bool(match and name_key(plain(match[1])) == name_key(candidate['surface'])
                and reading_key(match[2].strip()) == reading_key(candidate['reading']))


def audit(staging, gold_selection, sample_size=100):
    frozen = json.loads(pathlib.Path(gold_selection).read_text())
    excluded = {case['candidateId'] for case in frozen['cases']}
    db = sqlite3.connect(pathlib.Path(staging).resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    db.execute('BEGIN')
    metadata = json.loads(db.execute("SELECT value FROM meta WHERE key='source'").fetchone()[0])
    counts = collections.Counter()
    category_ids = collections.defaultdict(set)
    samples = collections.defaultdict(list)
    head_counts = collections.Counter()
    for page in db.execute('SELECT page_id,title,revision,text_sha1,substr(content,1,24000) AS content,proofs,contexts FROM pages ORDER BY page_id'):
        counts['retainedPages'] += 1
        contexts = {item['id'] for item in json.loads(page['contexts'])}
        for proof in json.loads(page['proofs']):
            candidate = proof['candidate']
            if candidate['id'] in excluded:
                counts['goldBindingsExcluded'] += 1
                continue
            if candidate['id'] not in contexts or not literal_reading_binding(proof, page['content'], page['title']):
                continue
            counts['literalPrimaryBindings'] += 1
            definition = subject_definition(page['content'], candidate['surface'])
            if not definition:
                continue
            counts['subjectDefinitions'] += 1
            terminal = re.search(r'([一-龥々ァ-ヶ]{2,25})' + END, definition['predicate'])
            if terminal:
                head_counts[terminal[1]] += 1
            suggestions = suggest(definition)
            for category in {item['category'] for item in suggestions}:
                category_ids[category].add(candidate['id'])
                if len(samples[category]) < sample_size:
                    samples[category].append({'candidateId': candidate['id'], 'reading': candidate['reading'],
                        'surface': candidate['surface'], 'target': page['title'], 'sourcePageId': page['page_id'],
                        'sourceRevision': page['revision'], 'sourceTextSha1': page['text_sha1'],
                        'readingQuotation': proof['body'].get('quotation', page['title']),
                        **definition, 'suggestions': suggestions})
    chosen = []
    seen = set()
    for category, quota in [('general', 40), ('technical', 35), ('food', 25)]:
        for case in samples[category]:
            if case['candidateId'] not in seen:
                chosen.append(case)
                seen.add(case['candidateId'])
                if sum(any(s['category'] == category for s in c['suggestions']) for c in chosen) >= quota:
                    break
    for case in chosen:
        content = db.execute('SELECT content FROM pages WHERE page_id=?', (case['sourcePageId'],)).fetchone()[0]
        case['computedTextSha1'] = hashlib.sha1(content.encode()).hexdigest()
        case['contentSha256'] = hashlib.sha256(content.encode()).hexdigest()
        case['sourceChecksumVerified'] = case['computedTextSha1'] == format(int(case['sourceTextSha1'], 36), '040x')
        if not case['sourceChecksumVerified'] or case['quotation'] not in content:
            raise ValueError('Raw source checksum/quotation mismatch')
    db.close()
    return {'schemaVersion': 1, 'purpose': 'Read-only raw Wikipedia subject audit; not independent gold or production classifications',
        'sourceMetadata': metadata, 'dumpFullyVerified': bool(metadata.get('complete')),
        'goldCandidateIdsExcluded': len(excluded), 'counts': dict(counts),
        'candidateSuggestionsByCategory': {c: len(ids) for c, ids in category_ids.items()},
        'closedSemanticHeadFamilies': HEADS, 'terminalDefinitionHeadFrequencies': head_counts.most_common(150),
        'cases': chosen, 'independentGoldCases': 0, 'productionApplied': False,
        'publicationFloors': {'general': 10000, 'technical': 1500, 'food': 250},
        'limitations': ['Suggestions retain the source_review precision gate.',
                       'Definition counts are inspection ceilings, not generic-category labels.',
                       'Staging corpus changes as scan proceeds; snapshot counts are not final.',
                       'Complete official dump checksum verification is required before ledger import.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staging', required=True)
    parser.add_argument('--gold-selection', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = audit(args.staging, args.gold_selection)
    pathlib.Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('dumpFullyVerified', 'counts', 'candidateSuggestionsByCategory')}, ensure_ascii=False))
    print('Raw-inspected sample:', len(report['cases']))


if __name__ == '__main__':
    main()
