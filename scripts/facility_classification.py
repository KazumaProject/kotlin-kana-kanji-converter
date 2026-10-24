#!/usr/bin/env python3
"""Deterministic high-precision rules and boundary hints for facility pairs."""
import gzip
import json
import re
import unicodedata
from pathlib import Path

import classified_distribution as distribution


# Ordered from specific to broad. A rule is a strong facility-use cue, not a
# final-character guess; each rule documents why its cue identifies a use.
RULES = [
    ('healthcare_hospital', 'healthcare/hospital', r'大学病院|病院|医療センター|総合医療センター|がんセンター|医療機関',
     '病院・医療センターの名称語を優先し、大学名を含んでも医療用途と判定。'),
    ('healthcare_clinic', 'healthcare/clinic', r'診療所|医院|クリニック|歯科医院|歯科診療所|健診センター|検診センター',
     '診療所・医院・クリニックなど外来診療の名称語に一致。'),
    ('healthcare_care', 'healthcare/care', r'介護|老人ホーム|養護老人|特別養護|福祉作業所|障害者支援施設|福祉施設|療養所',
     '介護・高齢者・福祉サービスを示す名称語に一致。'),
    ('transport_railway', 'transport/railway_facility', r'信号場|車両基地|車両センター|車両所|車庫|操車場|検車区|鉄道変電所|転車台|機関区|鉄道施設',
     '信号場・車両基地・車庫など列車運行を支える設備語に一致。軍事基地とは区別する。'),
    ('transport_road_access', 'transport/road_facility', r'出入口$|インターチェンジ|ジャンクション|ＩＣ$|JCT$',
     '道路の出入口・インターチェンジ・ジャンクションを示す施設語に一致。'),
    ('military_base', 'military/base', r'基地|駐屯地|駐屯所|航空団基地|海軍基地|軍港|防衛拠点',
     '軍隊・防衛組織の常設拠点を示す名称語に一致。'),
    ('military_training', 'military/training_ground', r'演習場|訓練場|射撃場|射爆場|演習施設',
     '軍事訓練・演習の用途を示す名称語に一致。'),
    ('military_garrison', 'military/garrison', r'兵営|弾薬庫|軍事施設|防衛施設',
     '兵営・弾薬庫など防衛の固定施設を示す名称語に一致。'),
    ('religious_church', 'religious/church', r'教会|礼拝堂|チャペル|聖堂|モスク|礼拝所',
     '教会・礼拝堂など宗教礼拝の名称語に一致。'),
    ('religious_monastery', 'religious/monastery', r'修道院|僧院|神学校|神学院|修道場',
     '修道院・僧院など宗教者の共同生活・養成施設を示す名称語に一致。'),
    ('religious_shrine', 'religious/shrine', r'神社|神宮(?!寺)|大社|鎮守社|天満宮|八幡宮|稲荷社',
     '神社・神宮・大社など神道の祭祀施設を示す名称語に一致。'),
    ('religious_temple', 'religious/temple', r'寺院|仏閣|(?:寺|別院|本願寺|大師堂|観音堂)$|寺(?:別院|本坊|境内)',
     '寺院・仏堂の名称語に一致。「病院」は先行する医療規則で判定。'),
    ('heritage_castle', 'heritage/castle', r'城郭|城跡|城址|城趾|城$|城天守|天守閣|宮殿|御殿跡|砦(?:跡)?$',
     '城郭・城跡・宮殿を示す名称語に一致。現用途の商業施設等を表す語は各用途規則を優先。'),
    ('heritage_archaeological', 'heritage/archaeological_site', r'古墳|遺跡|遺構|史跡|貝塚|古窯跡|住居跡',
     '古墳・遺跡・史跡など考古学的遺構の名称語に一致。'),
    ('heritage_residence', 'heritage/historic_residence', r'旧宅|旧邸|武家屋敷|歴史的住宅|旧家住宅',
     '歴史的住宅・旧邸・武家屋敷を示す名称語に一致。'),
    ('education_preschool', 'education/preschool', r'保育所|保育園|幼稚園|こども園|認定こども園|乳児院',
     '保育・就学前教育を示す名称語に一致。'),
    ('education_school', 'education/school', r'小学校|中学校|高等学校|高校|高等専門学校|特別支援学校|専門学校|学校|学園|高等学院|看護学院|助産師学院|自動車学院|職業訓練校',
     '学校教育施設を示す名称語に一致。学校法人等の組織名とは区別する。'),
    ('education_university', 'education/university', r'大学院|大学|短期大学|短大|高等教育機関',
     '大学・高等教育施設を示す名称語に一致。大学病院は先行する医療規則で判定。'),
    ('education_research', 'education/research', r'研究所|研究センター|研究施設|試験研究所|学術研究所',
     '研究を主目的とする施設を示す名称語に一致。生産設備・発電所は産業規則を優先。'),
    ('public_police_fire', 'public/police_fire', r'警察署|交番|駐在所|消防署|消防本部|消防出張所|防災センター|消防団詰所',
     '警察・消防・防災サービスの施設名に一致。警察学校は先行する教育規則で判定。'),
    ('public_judicial', 'public/judicial', r'裁判所|検察庁|刑務所|拘置所|少年院|矯正施設',
     '司法・矯正サービスの施設名に一致。'),
    ('public_postal', 'public/postal', r'郵便局|郵便集配局|郵便物取扱所',
     '郵便サービス施設の名称語に一致。'),
    ('public_government', 'public/government', r'県庁|都庁|府庁|市役所|区役所|町役場|村役場|役場|庁舎|合同庁舎|行政センター|行政サービスセンター|税務署|保健所|年金事務所',
     '行政窓口・官公庁庁舎を示す名称語に一致。運営組織そのものとは区別する。'),
    ('cultural_library', 'cultural/library', r'図書館|図書室|文書館|公文書館|資料保存館',
     '図書・文書の閲覧または保存を主目的とする名称語に一致。'),
    ('cultural_art_museum', 'cultural/art_museum', r'美術館|美術ギャラリー|画廊|アートセンター|絵画館',
     '美術作品の展示・公開を主目的とする名称語に一致。'),
    ('cultural_museum', 'cultural/museum', r'博物館|資料館|科学館|郷土館|考古館|自然史館|展示館|記念館|文学館|歴史館',
     '資料の収集・保存・展示を示す名称語に一致。劇場・運動施設は含めない。'),
    ('cultural_memorial', 'cultural/memorial', r'文化会館|文化センター|文化交流館|市民会館|公会堂|文化ホール',
     '文化交流・公演等に用いる文化会館・公会堂を示す名称語に一致。'),
    ('entertainment_cinema', 'entertainment/cinema', r'映画館|シネマコンプレックス|シネマ|劇場型映画施設',
     '映画上映施設を示す名称語に一致。'),
    ('entertainment_theater', 'entertainment/theater', r'劇場|演芸場|寄席|能楽堂|歌舞伎座|演舞場|オペラハウス',
     '舞台・演芸公演施設を示す名称語に一致。'),
    ('entertainment_live', 'entertainment/live_venue', r'ライブハウス|ライブ会場|コンサートホール|イベントホール|音楽ホール|興行場',
     '音楽・興行イベントを主目的とする施設語に一致。競技場は別規則で扱う。'),
    ('entertainment_amusement', 'entertainment/amusement', r'遊園地|テーマパーク|遊技場|ゲームセンター|娯楽施設|カジノ|レジャーランド',
     '遊戯・娯楽サービスの施設語に一致。動物園・自然公園は別規則で扱う。'),
    ('sports_ski', 'sports/ski', r'スキー場|スノーパーク|スノーボード場|スキーリゾート',
     'スキー・雪上競技を主目的とする名称語に一致。'),
    ('sports_golf', 'sports/golf', r'ゴルフ場|ゴルフコース|ゴルフ倶楽部|ゴルフクラブ|ゴルフ練習場',
     'ゴルフ競技・練習施設の名称語に一致。'),
    ('sports_aquatic', 'sports/aquatic', r'競泳プール|水泳場|屋内プール|屋外プール|市民プール|ボート競技場|ヨットハーバー',
     '水泳・水上競技の施設語に一致。温泉浴場は宿泊・温浴を優先。'),
    ('sports_stadium', 'sports/stadium', r'球場|競技場|スタジアム|陸上競技場|サッカー場|野球場|アリーナ|武道館|相撲場|競輪場|競馬場|競艇場|オートレース場',
     '競技・観戦を主目的とする施設語に一致。公演にも使われる施設は競技用途の明示を優先。'),
    ('sports_gymnasium', 'sports/gymnasium', r'体育館|運動場|運動公園|スポーツセンター|トレーニングセンター|スポーツ施設|道場',
     '運動・スポーツ練習の施設語に一致。'),
    ('commercial_shopping', 'commercial/shopping', r'ショッピングモール|ショッピングセンター|アウトレットモール|百貨店|デパート|商店街|専門店街|ショッピングプラザ|モール|大型商業施設',
     '買物・小売を主目的とする商業施設の名称語に一致。'),
    ('commercial_market', 'commercial/market', r'卸売市場|青果市場|魚市場|市場|商店|百貨店市場',
     '市場・小売店舗を示す名称語に一致。'),
    ('commercial_restaurant', 'commercial/restaurant', r'ラーメン|らーめん|らぁ麺|中華そば|麺屋|麺処|食堂|レストラン|飲食店|喫茶|カフェ|珈琲|コーヒー|蕎麦|そば店|うどん店|寿司|焼肉店|居酒屋|料亭|料理店',
     '飲食物の提供を主目的とする店舗語に一致。会社名・ブランド名だけの語は個別店舗とはみなさない。'),
    ('hospitality_hot_spring', 'hospitality/hot_spring', r'温泉|温浴|スパ|銭湯|浴場|サウナ|健康ランド',
     '入浴・温浴サービスの施設語に一致。スキー等の競技施設はスポーツ規則を優先。'),
    ('hospitality_inn', 'hospitality/inn', r'旅館|民宿|宿坊|ペンション|山荘|保養所',
     '旅館・民宿等の宿泊施設語に一致。'),
    ('hospitality_hotel', 'hospitality/hotel', r'ホテル|宿泊施設|リゾート施設|宿泊リゾート',
     'ホテル等の宿泊施設語に一致。旅館・温浴施設には各専用分類を優先。'),
    ('transport_airport', 'transport/airport', r'空港|飛行場|航空基地|ヘリポート|航空ターミナル',
     '航空機の発着・運航を支える施設語に一致。軍用基地は先行する軍事規則で判定。'),
    ('transport_harbor', 'transport/harbor', r'港湾|埠頭|ふ頭|船客ターミナル|フェリーターミナル|港ターミナル|貨物埠頭|^(?!道の駅).*港$',
     '船舶交通・港湾荷役を支える施設語に一致。'),
    ('transport_road', 'transport/road_facility', r'サービスエリア|パーキングエリア|道の駅|料金所|道路管理所|道路管制センター|自動車ターミナル',
     '道路交通の休憩・管理・料金徴収施設語に一致。道路・路線自体は含めない。'),
    ('transport_parking', 'transport/parking', r'駐車場|立体駐車場|駐輪場|自動車車庫|地下駐車場',
     '車両の駐車・保管施設語に一致。'),
    ('infrastructure_bridge', 'infrastructure/bridge', r'橋梁|吊橋|歩道橋|跨線橋|陸橋|橋$',
     '橋・橋梁の構造物名に一致。施設としての橋を分類し、河川・地名は対象外。'),
    ('infrastructure_tunnel', 'infrastructure/tunnel', r'トンネル|隧道|ずい道',
     '道路・鉄道等のトンネル構造物を示す名称語に一致。'),
    ('infrastructure_dam', 'infrastructure/dam', r'ダム|堰堤|砂防堰|堰$',
     '貯水・治水・砂防のダム・堰構造物に一致。発電所建屋は発電用途を優先。'),
    ('infrastructure_water', 'infrastructure/water_control', r'水門|閘門|用水路|排水機場|揚水機場|水路|放水路|河口堰',
     '水利・治水を支える水門・水路等の構造物語に一致。自然河川そのものは対象外。'),
    ('industrial_power', 'industrial/power', r'発電所|火力発電|水力発電|原子力発電|風力発電|太陽光発電|変電所|変電設備|ガス供給所|ガス基地|石油基地|エネルギーセンター',
     '発電・変電・燃料供給の設備語に一致。鉄道変電所は鉄道設備を優先。'),
    ('industrial_factory', 'industrial/factory', r'工場|製作所|製造所|製錬所|製鉄所|製紙所|精錬所|精油所|採石場|鉱山|浄水場|下水処理場|清掃工場|ごみ処理施設',
     '製造・加工・資源採掘・処理設備の名称語に一致。発電所は専用分類を優先。'),
    ('industrial_logistics', 'industrial/logistics', r'物流センター|配送センター|物流拠点|物流倉庫|倉庫|貨物ターミナル|貨物駅|集配センター',
     '貨物保管・配送を主目的とする施設語に一致。旅客駅とは区別する。'),
    ('industrial_communications', 'industrial/communications', r'通信局|通信所|通信センター|放送局舎|送信所|中継局|電波塔|無線塔|放送設備|通信設備',
     '固定通信・放送設備の名称語に一致。放送局という組織だけを表す語は組織候補として要確認。'),
    ('recreation_zoo', 'recreation/zoo_aquarium', r'動物園|水族館|海洋館|鳥類園|サファリパーク',
     '動植物の飼育・展示を主目的とする施設語に一致。'),
    ('recreation_park', 'recreation/park_garden', r'植物園|庭園|公園|緑地|自然公園|国定公園|国立公園|森林公園|植物園',
     '公園・庭園・植物展示の施設語に一致。地名・自然地形のみの名称は対象外。'),
    ('recreation_outdoor', 'recreation/outdoor_nature', r'キャンプ場|自然体験|野外活動センター|青少年自然の家|自然の家|牧場|森林体験施設|遊歩道|散策路',
     '屋外自然体験・キャンプ等の施設語に一致。スキー場や競技施設はスポーツ分類を優先。'),
    ('residential_complex', 'residential/housing_complex', r'住宅団地|団地|ニュータウン|住宅街区|公営住宅群',
     '複数住戸の住宅団地・住宅群を示す名称語に一致。'),
    ('residential_condominium', 'residential/condominium', r'マンション|アパート|集合住宅|コーポラス|団地住宅',
     '集合住宅を示す名称語に一致。複合商業ビルは商業用途を優先。'),
    ('residential_mixed_use', 'residential/mixed_use_building', r'複合ビル|複合施設|複合タワー|再開発ビル|ツインタワー',
     '単一用途が示されない複合建築物の名称語に一致。商業施設名が明確なら商業分類を優先。'),
]

COMPILED_RULES = [(rule_id, category, re.compile(pattern), rationale)
                  for rule_id, category, pattern, rationale in RULES]

MANUAL_OVERRIDES = {
    ('とふろむやえす', 'TOFROM YAESU'): {
        'category': 'facility/commercial/shopping',
        'method': 'manual_review',
        'reviewState': 'official_source_reviewed',
        'ruleId': 'official_mixed_use_commercial_complex',
        'rationale': '公式施設案内が大規模複合施設と明示し、60超のショップ・飲食店舗を中心とする商業ゾーンを案内しているため、主用途を商業施設と判定。読み・正式表記も公式ページに記載。',
        'evidenceUrl': 'https://tofrom-yaesu.com/',
    },
    ('きょうがくいん', '教学院'): {
        'category': 'facility/education/research',
        'method': 'manual_review',
        'reviewState': 'organization_boundary_review',
        'ruleId': 'official_buddhist_studies_institute_best_fit',
        'rationale': '公式サイトは浄土宗の仏教学研究機関として説明している。個別の物理施設か組織かは確認できないため、既存採用を維持したうえで研究機能に最も近い葉へ暫定分類し、organizationへの移動候補とする。',
        'evidenceUrl': 'https://acad.jodo.or.jp/',
    },
    ('さんがくいん', '三学院'): {
        'category': 'facility/religious/temple',
        'method': 'manual_review',
        'reviewState': 'official_source_reviewed',
        'ruleId': 'official_temple_review',
        'rationale': '蕨市公式資料が真言宗智山派の末寺と明記しているため、宗教施設の寺院に分類。',
        'evidenceUrl': 'https://www.city.warabi.saitama.jp/shogaigakushu/bunka/1011692/bunkazai/1003478.html',
    },
    ('せいがくいん', '清学院'): {
        'category': 'facility/cultural/museum',
        'method': 'manual_review',
        'reviewState': 'official_source_reviewed',
        'ruleId': 'official_current_museum_use_review',
        'rationale': '堺市公式資料は修験道寺院としての歴史を記載し、現在は堺市立町家歴史館として公開している。現行の主用途を展示・公開と判断し、博物館・資料館に分類。',
        'evidenceUrl': 'https://www.city.sakai.lg.jp/kanko/rekishi/bunkazai/bunkazai/torokuseido/seigakuin.html',
    },
}


def classify_with_rules(reading, surface):
    """Return one high-confidence leaf, or None if meaning needs best-fit review."""
    reviewed = MANUAL_OVERRIDES.get((reading, surface))
    if reviewed is not None:
        return dict(reviewed)
    normalized = unicodedata.normalize('NFKC', surface)
    for rule_id, suffix, pattern, rationale in COMPILED_RULES:
        if pattern.search(normalized):
            return {
                'category': 'facility/' + suffix,
                'method': 'rule_high',
                'reviewState': 'rule_matched',
                'ruleId': rule_id,
                'rationale': rationale,
                'evidenceUrl': '',
            }
    return None


def boundary_hint(reading, surface):
    """Return a conservative cross-dictionary review suggestion; do not alter admission."""
    normalized = unicodedata.normalize('NFKC', surface)
    patterns = [
        ('station', re.compile(r'(?:駅|停留所|電停|バス停)$'), '旅客駅・停留所カテゴリの候補'),
        ('transport_route', re.compile(r'(?:高速道路|自動車道|鉄道|軌道|路線)$'), '交通路線カテゴリの候補'),
        ('organization', re.compile(r'(?:株式会社|有限会社|学校法人|医療法人|協会|連盟|公社|機構|本社|支社|本部)$'), '組織カテゴリの候補'),
        ('place', re.compile(r'(?:山|岳|川|河|湖|沼|島|岬|湾|海岸|渓谷)$'), '地名・自然地形カテゴリの候補'),
        ('term', re.compile(r'(?:センター|会館|タワー|ビル|施設)$'), '名称だけでは物理施設・組織・建物の主用途を要確認'),
    ]
    for category, pattern, reason in patterns:
        if pattern.search(normalized):
            return {'suggestedCategory': category, 'reason': reason}
    return None


def collect_facility_pairs(root):
    """Read unique adopted pairs without changing or deduplicating source records."""
    path = Path(root) / 'src/main/classification/distribution-candidates.tsv.gz'
    source_additions = independent_leaf_additions(root)
    pairs = set()
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
        for number, line in enumerate(stream, 1):
            fields = line.rstrip('\n').split('\t')
            if len(fields) != 6:
                raise ValueError(f'{path}:{number}: expected six candidate fields')
            if fields[0] == 'facility' or fields[0].startswith('facility/'):
                pair = (fields[1], fields[5])
                if pair not in source_additions:
                    pairs.add(pair)
    if not pairs:
        raise ValueError('No adopted facility pairs found')
    return sorted(pairs)


def independent_leaf_additions(root):
    """Return source-backed review additions that already carry a facility leaf."""
    directory = Path(root) / 'src/main/classification/reviews'
    pairs = set()
    if not directory.is_dir():
        return pairs
    for path in sorted(directory.glob('*.jsonl')):
        with path.open(encoding='utf-8') as stream:
            for number, line in enumerate(stream, 1):
                entry = json.loads(line)
                categories = entry.get('categories', [])
                if (entry.get('baseline') is None and isinstance(entry.get('added_record'), dict)
                        and entry.get('evidence', {}).get('kind') == 'independent_source'
                        and isinstance(categories, list)
                        and any(isinstance(category, str) and category.startswith('facility/')
                                for category in categories)):
                    reading, surface = entry.get('reading'), entry.get('surface')
                    if not isinstance(reading, str) or not isinstance(surface, str):
                        raise ValueError(f'{path}:{number}: facility addition has no reading/surface')
                    pairs.add((reading, surface))
    return pairs


def possible_boundary_suggestions(pairs):
    return [(reading, surface, hint) for reading, surface in pairs
            if (hint := boundary_hint(reading, surface)) is not None]
