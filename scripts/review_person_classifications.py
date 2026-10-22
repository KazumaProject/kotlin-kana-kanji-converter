#!/usr/bin/env python3
"""Apply source-grounded person-category reviews without changing raw model output."""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
CACHE = (Path.home() / '.cache' / 'kotlin-kana-kanji-converter' /
         'person-gemini-classification-3-1-flash-lite')
DEFAULT_SOURCE_DECISIONS = CACHE / 'recovery-sources/reclassification/source-decisions.jsonl'
DEFAULT_WIKIDATA_SPORTS = CACHE / 'sport-subclassification/wikidata-p641.jsonl'
DEFAULT_GEMINI_RESULTS = CACHE / 'results'
DEFAULT_RECOVERY_GEMINI_RESULTS = CACHE / 'recovery-sources/gemini-recovery/results'
DEFAULT_OUTPUT = CACHE / 'reviewed-classifications'
OVERRIDES = ROOT / 'src/main/classification/person-category-overrides.jsonl'
TAXONOMY = ROOT / 'src/main/classification/person-taxonomy.json'
MANUAL_ONLY_CATEGORY_IDS = {
    'adult_performer', 'adult_work_creator', 'religion', 'crime_offender', 'espionage', 'terrorism',
    'organized_crime', 'military', 'thought', 'unclassified_person',
    'surname_origin_japanese', 'surname_origin_foreign',
    'given_name_origin_japanese', 'given_name_origin_foreign',
    'personal_name_origin_japanese', 'personal_name_origin_foreign',
}
WITHHELD_CATEGORY_IDS = {'military', 'thought'}
AGGREGATE_ONLY_CATEGORY_IDS = {
    'adult_performer', 'adult_work_creator', 'religion', 'crime_offender', 'espionage', 'terrorism',
    'organized_crime',
}


def ime_candidate_issue(reading, surface):
    """Return a stable format issue for pairs unsuitable for a kana IME lexicon."""
    if not reading or not surface:
        return 'empty'
    if any(char.isspace() or unicodedata.category(char).startswith('C')
           for char in reading + surface):
        return 'whitespace_or_control'

    def is_kana_or_mark(char):
        codepoint = ord(char)
        return (
            0x3041 <= codepoint <= 0x309F
            or 0x30A1 <= codepoint <= 0x30FF
            or 0x31F0 <= codepoint <= 0x31FF
            or 0xFF66 <= codepoint <= 0xFF9D
            or unicodedata.category(char).startswith('M')
        )

    if any(not is_kana_or_mark(char) for char in reading):
        return 'non_kana_reading'
    if not any(unicodedata.category(char).startswith('L') for char in surface):
        return 'surface_without_letters'
    return None


# Wikidata P641 labels observed in the checked source snapshot, normalized into
# stable Japanese category IDs. Multiple values may apply to one person.
SPORT_LABELS = {
    'baseball': '野球',
    'softball': 'ソフトボール',
    'soccer': 'サッカー',
    'futsal': 'フットサル',
    'sumo': '相撲',
    'rugby': 'ラグビー',
    'basketball': 'バスケットボール',
    'athletics': '陸上競技',
    'volleyball': 'バレーボール',
    'judo': '柔道',
    'pro_wrestling': 'プロレス',
    'wrestling': 'レスリング',
    'handball': 'ハンドボール',
    'keirin': '競輪',
    'boat_racing': '競艇',
    'cycling': '自転車競技',
    'horse_racing': '競馬',
    'golf': 'ゴルフ',
    'swimming': '競泳',
    'diving': '飛込競技',
    'artistic_swimming': 'アーティスティックスイミング',
    'water_polo': '水球',
    'tennis': 'テニス',
    'figure_skating': 'フィギュアスケート',
    'speed_skating': 'スピードスケート',
    'winter_sports': 'スキー・冬季競技',
    'ice_hockey': 'アイスホッケー',
    'field_hockey': 'フィールドホッケー',
    'badminton': 'バドミントン',
    'table_tennis': '卓球',
    'american_football': 'アメリカンフットボール',
    'boxing': 'ボクシング',
    'mma': '総合格闘技',
    'kickboxing': 'キックボクシング',
    'karate': '空手',
    'sambo': 'サンボ',
    'aikido': '合気道',
    'combat_unspecified': '格闘技（種目未特定）',
    'motorsports': 'モータースポーツ',
    'gymnastics': '体操',
    'shooting': '射撃',
    'fencing': 'フェンシング',
    'curling': 'カーリング',
    'canoeing': 'カヌー',
    'rowing': 'ローイング',
    'triathlon': 'トライアスロン',
    'darts': 'ダーツ',
    'sailing': 'セーリング',
    'archery': 'アーチェリー',
    'squash': 'スカッシュ',
    'boccia': 'ボッチャ',
    'weightlifting': '重量挙げ',
    'lawn_bowls': 'ローンボウルズ',
    'skateboarding': 'スケートボード',
    'modern_pentathlon': '近代五種',
    'sport_climbing': 'スポーツクライミング',
    'surfing': 'サーフィン',
    'breaking': 'ブレイキン',
    'sport_unspecified': '競技未特定',
}


def labels_for_sport():
    labels = {}

    def add(tag, *values):
        for value in values:
            labels[value] = tag

    add('baseball', '野球', '女子野球')
    add('softball', 'ソフトボール')
    add('soccer', 'サッカー', 'ビーチサッカー')
    add('futsal', 'フットサル')
    add('sumo', '相撲')
    add('rugby', 'ラグビー', 'ラグビーユニオン', '7人制ラグビー')
    add('basketball', 'バスケットボール', '車いすバスケットボール')
    add('athletics', '陸上競技', 'パラ陸上競技', 'トラック&フィールド',
        'クロスカントリー走', 'ロードレース (陸上競技)')
    add('volleyball', 'バレーボール', 'ビーチバレーボール')
    add('judo', '柔道')
    add('pro_wrestling', 'プロレス', '女子プロレス')
    add('wrestling', 'アマチュアレスリング', 'レスリング', 'フリースタイルレスリング',
        'グレコローマン・レスリング', 'サブミッションレスリング')
    add('handball', 'ハンドボール')
    add('keirin', '競輪')
    add('boat_racing', '競艇')
    add('cycling', '自転車競技', '自転車ロードレース', 'トラックレース', 'マウンテンバイキング')
    add('golf', 'ゴルフ')
    add('swimming', '競泳')
    add('diving', '飛込競技')
    add('artistic_swimming', 'アーティスティックスイミング')
    add('water_polo', '水球')
    add('tennis', 'テニス', '車いすテニス')
    add('figure_skating', 'フィギュアスケート', 'アイスダンス')
    add('speed_skating', 'スピードスケート', 'ショートトラックスピードスケート')
    add('winter_sports', 'スキージャンプ', 'アルペンスキー', 'クロスカントリースキー',
        'スキー', 'ノルディック複合', 'フリースタイルスキー', 'スノーボード',
        'バイアスロン', 'リュージュ', 'スケルトン')
    add('ice_hockey', 'アイスホッケー')
    add('field_hockey', 'フィールドホッケー')
    add('badminton', 'バドミントン', 'パラバドミントン')
    add('table_tennis', '卓球', 'パラ卓球')
    add('american_football', 'アメリカンフットボール', 'カナディアン・フットボール')
    add('boxing', 'ボクシング')
    add('mma', '総合格闘技')
    add('kickboxing', 'キックボクシング')
    add('karate', '空手')
    add('sambo', 'サンボ')
    add('aikido', '合気道')
    add('motorsports', 'オートレース', 'モトクロス')
    add('gymnastics', '体操競技', '体操', '新体操')
    add('shooting', '射撃競技', 'ブルズアイ・シューティング')
    add('fencing', 'フェンシング')
    add('curling', 'カーリング')
    add('canoeing', 'カヌーイングおよびカヤッキング')
    add('rowing', 'ローイング競技')
    add('triathlon', 'トライアスロン')
    add('darts', 'ダーツ')
    add('sailing', 'セーリング')
    add('archery', 'アーチェリー')
    add('squash', 'スカッシュ')
    add('boccia', 'ボッチャ')
    add('weightlifting', '重量挙げ')
    add('lawn_bowls', 'ローンボウルズ')
    add('skateboarding', 'スケートボード')
    add('modern_pentathlon', '近代五種')
    add('sport_climbing', 'スポーツクライミング')
    add('surfing', 'サーフィン')
    add('breaking', 'ブレイキン')
    add('combat_unspecified', '格闘技')
    return labels


SPORT_LABEL_TO_ID = labels_for_sport()
OCCUPATION_SPORTS = [
    ('baseball', re.compile(r'野球')),
    ('soccer', re.compile(r'サッカー選手|サッカー指導者|サッカー審判員')),
    ('futsal', re.compile(r'フットサル選手')),
    ('sumo', re.compile(r'力士')),
    ('rugby', re.compile(r'ラグビー')),
    ('basketball', re.compile(r'バスケットボール')),
    ('volleyball', re.compile(r'バレーボール')),
    ('athletics', re.compile(r'陸上競技|短距離走|長距離走|マラソン|競歩|ハードル走|やり投げ|円盤投げ|ハンマー投げ')),
    ('judo', re.compile(r'柔道家')),
    ('pro_wrestling', re.compile(r'プロレスラー')),
    ('wrestling', re.compile(r'アマチュアレスラー|レスリング選手')),
    ('keirin', re.compile(r'競輪選手')),
    ('boat_racing', re.compile(r'競艇選手')),
    ('cycling', re.compile(r'自転車競技選手')),
    ('horse_racing', re.compile(r'騎手')),
    ('golf', re.compile(r'ゴルファー')),
    ('swimming', re.compile(r'競泳選手|水泳指導者|水泳選手')),
    ('tennis', re.compile(r'テニス選手')),
    ('figure_skating', re.compile(r'フィギュアスケート選手|アイスダンス選手')),
    ('speed_skating', re.compile(r'スピードスケート選手|ショートトラックスピードスケーター')),
    ('winter_sports', re.compile(r'スキージャンプ選手|アルペンスキー選手|クロスカントリースキー選手|スノーボード選手|ノルディック複合選手|フリースタイルスキー選手|スキー選手|リュージュ選手|バイアスロン選手')),
    ('ice_hockey', re.compile(r'アイスホッケー選手')),
    ('field_hockey', re.compile(r'フィールドホッケー選手')),
    ('badminton', re.compile(r'バドミントン選手')),
    ('table_tennis', re.compile(r'卓球選手')),
    ('american_football', re.compile(r'アメリカンフットボール選手')),
    ('boxing', re.compile(r'ボクサー|ボクシング')),
    ('mma', re.compile(r'総合格闘家')),
    ('kickboxing', re.compile(r'キックボクサー')),
    ('karate', re.compile(r'空手家')),
    ('motorsports', re.compile(r'カーレーサー|レーシングドライバー|F1ドライバー|レース・カー・ドライバー|オートレース選手')),
    ('horse_racing', re.compile(r'騎手')),
    ('gymnastics', re.compile(r'体操選手|器械体操選手|新体操選手')),
    ('shooting', re.compile(r'射撃選手')),
    ('fencing', re.compile(r'フェンシング選手')),
    ('curling', re.compile(r'カーリング選手')),
    ('canoeing', re.compile(r'カヌー選手')),
    ('rowing', re.compile(r'ローイング選手')),
    ('triathlon', re.compile(r'トライアスロン選手')),
    ('darts', re.compile(r'ダーツ選手')),
    ('archery', re.compile(r'アーチェリー選手')),
    ('modern_pentathlon', re.compile(r'近代五種選手|近代五種')),
    ('sport_climbing', re.compile(r'スポーツクライミング選手|スポーツクライマー')),
    ('surfing', re.compile(r'サーファー|サーフィン選手')),
    ('breaking', re.compile(r'ブレイキン選手|ブレイクダンサー')),
    ('weightlifting', re.compile(r'重量挙げ選手')),
    ('lawn_bowls', re.compile(r'ローンボウルズ選手')),
    ('skateboarding', re.compile(r'スケートボーダー')),
]

ADDITIONAL_OCCUPATION_CATEGORIES = [
    (6, re.compile(r'シンガーソングライター')),
    (14, re.compile(r'俳人')),
    (19, re.compile(r'エンジニア|大学人|精神科医|経営理論家|美術史家')),
    (17, re.compile(r'陶芸家')),
    (21, re.compile(r'銀行家')),
    (22, re.compile(r'侍')),
    (18, re.compile(r'ダンサー|振付師')),
    (9, re.compile(r'レースクイーン')),
    (24, re.compile(r'宗教家|宗教指導者|宗教学者|仏教学者|神学者|宗教哲学者|僧侶|比丘|修道士|神父|司祭|司教|牧師|宣教師|伝道者|theologian|religious leader|religious scholar|monk|priest|pastor|imam|rabbi', re.I)),
    (30, re.compile(r'哲学者|思想家|philosopher|thinker', re.I)),
    (12, re.compile(r'野球|サッカー|ラグビー|バスケットボール|バレーボール|柔道|陸上競技|力士|相撲|プロレス|レスラー|競輪|競艇|競馬|騎手|フィギュアスケート|ゴルフ|自転車競技|競泳|短距離走|長距離走|テニス|スピードスケート|スキージャンプ|スキー選手|卓球|ボクサー|ボクシング|格闘家|キックボクサー|空手家|フェンシング|カーリング|体操選手|器械体操選手|ハンドボール|アイスホッケー|バドミントン|アメリカンフットボール|フットサル|オートレース|レース・カー・ドライバー|カーレーサー|レーシングドライバー|F1ドライバー|レスリング|スケートボーダー')),
]

FILM_OCCUPATION = re.compile(r'撮影監督|撮影技師|音響監督|アニメ監督|美術監督|CMディレクター|編集技師|助監督')
SPORT_MEDIA = re.compile(r'スポーツライター|解説者')
SPORTS_ROLE = re.compile(r'選手|力士|レスラー|格闘家|騎手|指導者|コーチ|監督|審判|競技者|アスリート|スポーツ役員|スポーツ選手')


def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f'{path}:{number}: invalid JSONL') from error


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
                         encoding='utf-8')
    os.replace(temporary, path)


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')
    os.replace(temporary, path)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def taxonomy_maps(path):
    taxonomy = json.loads(Path(path).read_text(encoding='utf-8'))
    by_code = {row['number']: row for row in taxonomy['categories']}
    by_id = {row['id']: row['number'] for row in taxonomy['categories']}
    policy = taxonomy.get('policy', {})
    excluded_categories = AGGREGATE_ONLY_CATEGORY_IDS | WITHHELD_CATEGORY_IDS
    if set(policy.get('standard_dictionary_excluded_categories', [])) != excluded_categories:
        raise ValueError('Taxonomy must exclude restricted and withheld categories from standard dictionaries')
    if set(policy.get('standard_dictionary_withheld_categories', [])) != WITHHELD_CATEGORY_IDS:
        raise ValueError('Taxonomy must identify the withheld person categories')
    if policy.get('restricted_category_records') != 'aggregate_counts_only':
        raise ValueError('Taxonomy must keep restricted category records as aggregate counts only')
    disabled_ids = {row['id'] for row in taxonomy['categories']
                    if row.get('standard_enabled') is False}
    expected_disabled_ids = excluded_categories | {'unclassified_person'}
    if disabled_ids != expected_disabled_ids:
        raise ValueError('Restricted, withheld and non-classified categories must be disabled for standard distribution')
    if policy.get('unreviewed_distribution') != 'excluded':
        raise ValueError('Unreviewed person candidates must be excluded from standard distribution')
    if policy.get('adult_distribution') != {
            'adult_performer': 'metadata_only',
            'adult_work_creator': 'metadata_only'}:
        raise ValueError('Adult performer and creator distribution policies are inconsistent')
    if policy.get('adult_related_hold', {}).get('distribution') != 'metadata_only':
        raise ValueError('Adult-related hold data must be metadata only')
    for tag, label in SPORT_LABELS.items():
        if taxonomy.get('sport_subcategories', {}).get(tag) != label:
            raise ValueError(f'Taxonomy is missing sport subcategory {tag}')
    return taxonomy, by_code, by_id


def wikidata_sports_by_qid(path):
    sports = {}
    for row in read_jsonl(path):
        qid = row.get('qid')
        if not isinstance(qid, str) or not re.fullmatch(r'Q[1-9][0-9]*', qid):
            raise ValueError(f'Invalid Wikidata QID in {path}: {qid!r}')
        sports[qid] = {value['label'] for value in row.get('sports', [])
                       if isinstance(value.get('label'), str) and value['label']}
    return sports


def occupation_sport_tags(occupations):
    tags = {tag for occupation in occupations
            for tag, pattern in OCCUPATION_SPORTS if pattern.search(occupation)}
    if any(re.search(r'格闘家|古武道', occupation) for occupation in occupations):
        tags.add('combat_unspecified')
    specific_combat = {'boxing', 'mma', 'kickboxing', 'karate', 'judo', 'wrestling',
                       'pro_wrestling', 'sambo', 'aikido'}
    if tags & specific_combat:
        tags.discard('combat_unspecified')
    return tags


def source_review(rows, sport_qids, category_by_code,
                  aggregate_only_category_ids=AGGREGATE_ONLY_CATEGORY_IDS):
    reviewed = []
    changes = collections.Counter()
    tag_keys = collections.defaultdict(set)
    examples = collections.defaultdict(list)
    before = collections.Counter()
    after = collections.Counter()

    for source_row in rows:
        row = dict(source_row)
        old_code = row.get('category_code')
        if old_code is not None:
            if old_code not in category_by_code:
                raise ValueError(f'Unknown source category code: {old_code!r}')
            row['category_id'] = category_by_code[old_code]['id']
            before[old_code] += 1
        occupations = row.get('source_occupations', [])
        qids = row.get('source_items', [])
        sport_labels = {label for qid in qids for label in sport_qids.get(qid, set())}
        target = old_code
        reason = None
        tags = set()

        # Reclassifications that can be decided from the exact Wikidata name,
        # reading, and occupation evidence already attached to each source row.
        if old_code == 12 and not sport_labels:
            if any(FILM_OCCUPATION.search(value) for value in occupations):
                target, reason = 16, '映像制作の職業名が一致し、Wikidata の競技値がない。'
            elif any(SPORT_MEDIA.search(value) for value in occupations) and not any(
                    SPORTS_ROLE.search(value) for value in occupations):
                if any('ライター' in value for value in occupations):
                    target, reason = 14, 'スポーツ執筆者の職業名が一致し、競技者・指導者等の職業値がない。'
                else:
                    target, reason = 9, 'スポーツ解説者の職業名が一致し、競技者・指導者等の職業値がない。'
            elif occupations == ['監督']:
                target, reason = 25, '職業値が「監督」のみで競技を特定できない。'
        if old_code == 12 and 'ポーカー' in sport_labels and not (sport_labels - {'ポーカー'}):
            target, reason = 13, 'Wikidata の競技値はポーカーで、競技ゲームに分類する。'

        # The previous source resolver placed unmatched but identified occupations
        # in category 25. These explicit occupation labels identify a better fit.
        if old_code == 25:
            targets = {code for code, pattern in ADDITIONAL_OCCUPATION_CATEGORIES
                       if any(pattern.search(value) for value in occupations)}
            if 24 in targets or 30 in targets:
                target = 24 if 24 in targets else 30
                reason = 'Wikidata の読み一致人物に付く宗教・思想関連の職業名がカテゴリを特定する。'
            elif len(targets) == 1:
                target = next(iter(targets))
                reason = 'Wikidata の読み一致人物に付く職業名がカテゴリを特定する。'

        if target != old_code:
            row['original_category_code'] = old_code
            row['original_category_id'] = category_by_code[old_code]['id']
            row['category_code'] = target
            row['category_id'] = category_by_code[target]['id']
            row['review_status'] = 'source_occupation_reclassified'
            row['review_reason'] = reason
            changes[(old_code, target)] += 1

        # Adult-performer records are intentionally left out of Gemini and out
        # of this occupational sports-tagging pass.
        if target not in (None, 11):
            if target == 12:
                if sport_labels:
                    tags = {SPORT_LABEL_TO_ID[label] for label in sport_labels
                            if label in SPORT_LABEL_TO_ID}
                    if not tags:
                        tags = {'sport_unspecified'}
                else:
                    tags = occupation_sport_tags(occupations)
                    if not tags and any(re.search(r'コーチ|監督|審判員|スポーツ選手|アスリート|オリンピック選手', value)
                                        for value in occupations):
                        tags = {'sport_unspecified'}
            elif old_code == 25 and target == 25:
                # Retain a sport as a secondary tag when the person also has a
                # distinct occupation and the source does not establish a primary role.
                tags = occupation_sport_tags(occupations)
            elif old_code not in (None, 11) and target != 12:
                tags = occupation_sport_tags(occupations)
            elif target == 12 and old_code == 25:
                tags = occupation_sport_tags(occupations)

        if tags:
            row['sport_subcategories'] = sorted(tags)
            for tag in tags:
                tag_keys[tag].add(row['candidate_key'])
                if (row.get('category_id') not in aggregate_only_category_ids
                        and len(examples[tag]) < 3):
                    examples[tag].append(f"{row['reading']} → {row['surface']}")
        elif 'sport_subcategories' in row:
            row.pop('sport_subcategories')

        if row.get('category_code') is not None:
            after[row['category_code']] += 1
        reviewed.append(row)

    return reviewed, changes, before, after, tag_keys, examples


def load_overrides(path, category_by_id,
                   aggregate_only_category_ids=AGGREGATE_ONLY_CATEGORY_IDS):
    overrides = {}
    for row in read_jsonl(path):
        key = row.get('candidate_key')
        if not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{64}', key):
            raise ValueError(f'Invalid candidate key in override file: {key!r}')
        if key in overrides:
            raise ValueError(f'Duplicate reviewed override: {key}')
        category_id = row.get('target_category_id')
        if category_id not in category_by_id:
            raise ValueError(f'Unknown override category ID: {category_id!r}')
        if category_id in aggregate_only_category_ids:
            raise ValueError('Restricted categories cannot have named source overrides')
        sport_tags = row.get('sport_subcategories')
        if sport_tags is not None:
            if (category_id != 'sports' or not isinstance(sport_tags, list)
                    or not all(isinstance(tag, str) for tag in sport_tags)
                    or not sport_tags or len(set(sport_tags)) != len(sport_tags)
                    or not set(sport_tags) <= set(SPORT_LABELS)):
                raise ValueError(f'Invalid sport subcategories in override: {key}')
        source_hash = row.get('source_sha256')
        if source_hash is not None and (not isinstance(source_hash, str)
                                        or not re.fullmatch(r'[0-9a-f]{64}', source_hash)):
            raise ValueError(f'Invalid source SHA-256 in override: {key}')
        for field in ('reading', 'surface', 'source_url', 'reason', 'checked_on'):
            if not isinstance(row.get(field), str) or not row[field]:
                raise ValueError(f'Override is missing {field}: {key}')
        overrides[key] = row
    if not overrides:
        raise ValueError('Reviewed override file is empty')
    return overrides


def apply_source_overrides(rows, overrides, category_by_id, category_by_code,
                           changes, after, tag_keys=None, examples=None):
    applied = []
    matched = collections.Counter()
    for row in rows:
        override = overrides.get(row.get('candidate_key'))
        if not override:
            continue
        if (row.get('reading'), row.get('surface')) != (override['reading'], override['surface']):
            raise ValueError(f'Override pair differs from source decision: {override["candidate_key"]}')
        old_code = row.get('category_code')
        if old_code not in category_by_code:
            raise ValueError(f'Source override has no known original category: {override["candidate_key"]}')
        target_code = category_by_id[override['target_category_id']]
        row['original_category_code'] = old_code
        row['original_category_id'] = category_by_code[old_code]['id']
        row['category_code'] = target_code
        row['category_id'] = override['target_category_id']
        row['review_status'] = 'manual_source_override'
        row['review_reason'] = override['reason']
        row['review_evidence'] = {
            'source_url': override['source_url'],
            'reason': override['reason'],
            'checked_on': override['checked_on'],
        }
        if override.get('source_section'):
            row['review_evidence']['source_section'] = override['source_section']
        sport_tags = set(row.get('sport_subcategories', []))
        sport_tags.update(override.get('sport_subcategories', []))
        if sport_tags:
            row['sport_subcategories'] = sorted(sport_tags)
            for tag in sport_tags:
                if tag_keys is not None:
                    tag_keys[tag].add(override['candidate_key'])
                if (examples is not None and len(examples[tag]) < 3
                        and f"{row['reading']} → {row['surface']}" not in examples[tag]):
                    examples[tag].append(f"{row['reading']} → {row['surface']}")
        if old_code != target_code:
            after[old_code] -= 1
            after[target_code] += 1
            changes[(old_code, target_code)] += 1
        matched[override['candidate_key']] += 1
        applied.append({
            'candidate_key': override['candidate_key'],
            'reading': row['reading'], 'surface': row['surface'],
            'original_category_code': old_code,
            'target_category_code': target_code,
            'target_category_id': override['target_category_id'],
            'source_url': override['source_url'],
        })
    if any(count != 1 for count in matched.values()):
        raise ValueError('Each source override must match at most one source decision row')
    return applied


def review_gemini_results(input_dir, output_dir, overrides, category_by_id,
                          category_by_code, require_all,
                          aggregate_only_category_ids=AGGREGATE_ONLY_CATEGORY_IDS):
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if not input_dir.is_dir():
        raise ValueError(f'Gemini result directory does not exist: {input_dir}')
    matched = collections.Counter()
    applied = []
    demoted = collections.Counter()
    files = sorted(input_dir.glob('*.jsonl'))
    if not files:
        raise ValueError(f'No Gemini result files found in {input_dir}')
    for path in files:
        out_rows = []
        for row in read_jsonl(path):
            code = row.get('category_code')
            if code:
                if code not in category_by_code:
                    raise ValueError(f'Unknown Gemini category code: {code!r}')
                row['category_id'] = category_by_code[code]['id']
            else:
                row['category_id'] = None
            override = overrides.get(row.get('candidate_key'))
            if override:
                if (row.get('reading'), row.get('surface')) != (override['reading'], override['surface']):
                    raise ValueError(f'Override pair differs from model result: {override["candidate_key"]}')
                target_code = category_by_id[override['target_category_id']]
                if row.get('classification') != 'source_reviewed_override':
                    if row.get('category_id') in aggregate_only_category_ids:
                        # A reviewed ordinary category may replace a model-only
                        # restricted proposal, but the named row must not retain
                        # that restricted label or provenance.
                        demoted[row['category_id']] += 1
                    else:
                        row['model_category_code'] = row.get('category_code')
                        row['model_category_id'] = row.get('category_id')
                row['category_code'] = target_code
                row['category_id'] = override['target_category_id']
                row['classification'] = 'source_reviewed_override'
                row['review_evidence'] = {
                    'source_url': override['source_url'],
                    'reason': override['reason'],
                    'checked_on': override['checked_on'],
                }
                if override.get('source_section'):
                    row['review_evidence']['source_section'] = override['source_section']
                sport_tags = set(row.get('sport_subcategories', []))
                sport_tags.update(override.get('sport_subcategories', []))
                if sport_tags:
                    row['sport_subcategories'] = sorted(sport_tags)
                matched[override['candidate_key']] += 1
                applied.append({
                    'candidate_key': override['candidate_key'],
                    'reading': row['reading'], 'surface': row['surface'],
                    'original_category_code': row.get('model_category_code'),
                    'target_category_code': target_code,
                    'target_category_id': override['target_category_id'],
                })
            elif row.get('category_code') in category_by_code and category_by_code[
                    row['category_code']]['id'] in aggregate_only_category_ids:
                # Retain only an aggregate count for restricted categories.
                # Their candidate names must not be written to reviewed outputs.
                demoted[row['category_id']] += 1
                continue
            elif row.get('category_code') in category_by_code and category_by_code[
                    row['category_code']]['id'] in MANUAL_ONLY_CATEGORY_IDS:
                row['model_category_code'] = row.get('category_code')
                row['model_category_id'] = row.get('category_id')
                row['category_code'] = 0
                row['category_id'] = None
                row['classification'] = 'manual_category_unverified'
                row['review_reason'] = '手動カテゴリは出典確認が必要なため、Gemini提案だけでは分類を確定しない。'
                demoted[row['model_category_id']] += 1
            out_rows.append(row)
        write_jsonl(output_dir / path.name, out_rows)
    if any(value != 1 for value in matched.values()):
        raise ValueError('Each reviewed override must match at most one Gemini result row per dataset')
    if require_all and set(matched) != set(overrides):
        missing = sorted(set(overrides) - set(matched))
        raise ValueError(f'Overrides missing from complete Gemini result set: {missing}')
    return applied, demoted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--source-decisions', type=Path, default=DEFAULT_SOURCE_DECISIONS)
    parser.add_argument('--wikidata-sports', type=Path, default=DEFAULT_WIKIDATA_SPORTS)
    parser.add_argument('--gemini-results', type=Path, default=DEFAULT_GEMINI_RESULTS)
    parser.add_argument('--recovery-gemini-results', type=Path,
                        default=DEFAULT_RECOVERY_GEMINI_RESULTS)
    parser.add_argument('--overrides', type=Path, default=OVERRIDES)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output_dir.resolve()
    if root == output or root in output.parents:
        parser.error('--output-dir must be outside the repository')

    taxonomy, category_by_code, category_by_id = taxonomy_maps(root / TAXONOMY.relative_to(ROOT))
    source_path = args.source_decisions.resolve()
    sports_path = args.wikidata_sports.resolve()
    override_path = args.overrides.resolve()
    source_rows = list(read_jsonl(source_path))
    qid_sports = wikidata_sports_by_qid(sports_path)
    reviewed, changes, before, after, tag_keys, tag_examples = source_review(
        source_rows, qid_sports, category_by_code, AGGREGATE_ONLY_CATEGORY_IDS)
    overrides = load_overrides(override_path, category_by_id, AGGREGATE_ONLY_CATEGORY_IDS)
    source_keys = {row['candidate_key'] for row in reviewed}
    source_overrides = {key: value for key, value in overrides.items() if key in source_keys}
    source_applied = apply_source_overrides(
        reviewed, source_overrides, category_by_id, category_by_code,
        changes, after, tag_keys, tag_examples)
    gemini_output = output / 'gemini-results'
    initial_applied, initial_demoted = review_gemini_results(
        args.gemini_results, gemini_output, overrides, category_by_id,
        category_by_code, require_all=True)
    recovery_applied, recovery_demoted = review_gemini_results(
        args.recovery_gemini_results, output / 'gemini-recovery-results', overrides,
        category_by_id, category_by_code, require_all=False)
    if set(source_overrides) != {row['candidate_key'] for row in source_applied}:
        raise ValueError('A source override was not applied to its source decision')
    write_jsonl(output / 'source-decisions-reviewed.jsonl', (
        row for row in reviewed if row.get('category_id') not in AGGREGATE_ONLY_CATEGORY_IDS))

    category_counts = lambda counts: {
        category_by_code[code]['id']: count for code, count in sorted(counts.items())
    }
    sport_summary = {
        tag: {'candidate_pairs': len(keys), 'examples': tag_examples[tag]}
        for tag, keys in sorted(tag_keys.items(), key=lambda item: (-len(item[1]), item[0]))
    }
    change_examples = collections.defaultdict(list)
    for row in reviewed:
        if row.get('review_status') in ('source_occupation_reclassified', 'manual_source_override'):
            pair = (row['original_category_code'], row['category_code'])
            if (row.get('original_category_id') not in AGGREGATE_ONLY_CATEGORY_IDS
                    and row.get('category_id') not in AGGREGATE_ONLY_CATEGORY_IDS
                    and len(change_examples[pair]) < 3):
                change_examples[pair].append(f"{row['reading']} → {row['surface']}")
    summary = {
        'source_file_sha256': file_sha256(source_path),
        'wikidata_sports_file_sha256': file_sha256(sports_path),
        'override_file_sha256': file_sha256(override_path),
        'source_decision_pairs': len(source_rows),
        'category_counts_before': category_counts(before),
        'category_counts_after': category_counts(after),
        'category_reclassifications': [
            {'from': category_by_code[old]['id'], 'to': category_by_code[new]['id'],
             'pairs': count, 'examples': change_examples[(old, new)]}
            for (old, new), count in sorted(changes.items())
        ],
        'sports_primary_category_pairs': after[12],
        'sports_tagged_pairs': len(set().union(*tag_keys.values()) if tag_keys else set()),
        'sports_subcategories': sport_summary,
        'adult_performer_pairs_unchanged': after[11],
        'manual_source_override_rows_applied': source_applied,
        'initial_gemini_override_rows_applied': initial_applied,
        'recovery_gemini_override_rows_applied': recovery_applied,
        'initial_gemini_manual_only_rows_demoted': initial_demoted,
        'recovery_gemini_manual_only_rows_demoted': recovery_demoted,
        'classification_policy': 'Reviewed outputs omit person-level rows in restricted categories and retain aggregate counts only. Military and thought records are excluded from the standard person dictionary export; raw source corpora remain unchanged. Raw source and Gemini workspaces are external to the repository; future Gemini runs require an external restricted-category hash exclusion file.',
        'taxonomy_version': taxonomy['taxonomy_version'],
    }
    write_json(output / 'summary.json', summary)
    print(json.dumps({
        'output_dir': str(output),
        'source_decision_pairs': len(source_rows),
        'reclassifications': summary['category_reclassifications'],
        'sports_primary_category_pairs': summary['sports_primary_category_pairs'],
        'sports_tagged_pairs': summary['sports_tagged_pairs'],
        'sports_subcategories': len(sport_summary),
        'manual_source_override_rows_applied': source_applied,
        'initial_gemini_override_count': len(initial_applied),
        'recovery_gemini_override_count': len(recovery_applied),
        'initial_gemini_manual_only_rows_demoted': sum(initial_demoted.values()),
        'recovery_gemini_manual_only_rows_demoted': sum(recovery_demoted.values()),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
