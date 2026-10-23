#!/usr/bin/env python3
"""Create source-backed media demographic reviews from downloaded public CSV snapshots."""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classification_reviews as reviews
import classified_distribution as distribution


LABELS = {
    'Shounen': 'shonen',
    'Seinen': 'seinen',
    'Shoujo': 'shojo',
    'Josei': 'josei',
    'Kids': 'kids',
}
LABEL_NAMES = {
    'shonen': '少年向け', 'seinen': '青年向け', 'shojo': '少女向け',
    'josei': '女性向け', 'kids': '子ども向け',
    'mixed': '複数対象層', 'unspecified': '対象層タグなし',
    'source_unverified': '出典未確認・対象層未確定',
    'adult': '成人向け',
}
KAGGLE_URL = 'https://www.kaggle.com/datasets/patelris/anime-and-manga-dataset-2026'
CHARACTERS_URL = 'https://huggingface.co/datasets/fadhilakbar/anime-characters-dataset'
REVIEW_PATH = 'src/main/classification/reviews/2026-10-23-media-demographics-complete.jsonl'
DATASETS = {
    'anime': {
        'url': KAGGLE_URL,
        'version': 'Kaggle dataset version 6; snapshot updated 2026-05-14',
        'license': 'CC BY 4.0',
        'file': 'anime_dataset.csv',
    },
    'manga': {
        'url': KAGGLE_URL,
        'version': 'Kaggle dataset version 6; snapshot updated 2026-05-14',
        'license': 'CC BY 4.0',
        'file': 'manga_dataset.csv',
    },
    'characters': {
        'url': CHARACTERS_URL,
        'version': 'CSV snapshot downloaded 2026-10-23; file SHA-256 pins its content',
        'license': 'CC BY 4.0',
        'file': 'anime-characters-dataset.csv',
    },
}


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as source:
        yield from csv.DictReader(source)


def normalize(value):
    value = unicodedata.normalize('NFKD', unicodedata.normalize('NFKC', value).casefold())
    return ''.join(char for char in value if not unicodedata.combining(char) and char.isalnum())


KANA = {
    **dict(zip('あいうえお', ('a', 'i', 'u', 'e', 'o'))),
    **dict(zip('かきくけこ', ('ka', 'ki', 'ku', 'ke', 'ko'))),
    **dict(zip('さしすせそ', ('sa', 'shi', 'su', 'se', 'so'))),
    **dict(zip('たちつてと', ('ta', 'chi', 'tsu', 'te', 'to'))),
    **dict(zip('なにぬねの', ('na', 'ni', 'nu', 'ne', 'no'))),
    **dict(zip('はひふへほ', ('ha', 'hi', 'fu', 'he', 'ho'))),
    **dict(zip('まみむめも', ('ma', 'mi', 'mu', 'me', 'mo'))),
    **dict(zip('やゆよ', ('ya', 'yu', 'yo'))),
    **dict(zip('らりるれろ', ('ra', 'ri', 'ru', 're', 'ro'))),
    **dict(zip('わゐゑを', ('wa', 'i', 'e', 'wo'))),
    'ん': 'n', 'が': 'ga', 'ぎ': 'gi', 'ぐ': 'gu', 'げ': 'ge', 'ご': 'go',
    'ざ': 'za', 'じ': 'ji', 'ず': 'zu', 'ぜ': 'ze', 'ぞ': 'zo',
    'だ': 'da', 'ぢ': 'ji', 'づ': 'zu', 'で': 'de', 'ど': 'do',
    'ば': 'ba', 'び': 'bi', 'ぶ': 'bu', 'べ': 'be', 'ぼ': 'bo',
    'ぱ': 'pa', 'ぴ': 'pi', 'ぷ': 'pu', 'ぺ': 'pe', 'ぽ': 'po', 'ゔ': 'vu',
}
YOON = {
    row + small: consonant + vowel
    for row, consonant in (('き', 'ky'), ('ぎ', 'gy'), ('し', 'sh'), ('じ', 'j'),
                           ('ち', 'ch'), ('ぢ', 'j'), ('に', 'ny'), ('ひ', 'hy'),
                           ('び', 'by'), ('ぴ', 'py'), ('み', 'my'), ('り', 'ry'))
    for small, vowel in (('ゃ', 'a'), ('ゅ', 'u'), ('ょ', 'o'))
}
FOREIGN_KANA = {
    'てぃ': 'ti', 'でぃ': 'di', 'とぅ': 'tu', 'どぅ': 'du', 'つぁ': 'tsa',
    'つぃ': 'tsi', 'つぇ': 'tse', 'つぉ': 'tso', 'ちぇ': 'che', 'しぇ': 'she',
    'じぇ': 'je', 'すぃ': 'si', 'くぁ': 'kwa', 'ぐぁ': 'gwa',
}


def kana_to_romaji(value):
    text = unicodedata.normalize('NFKC', value)
    text = ''.join(chr(ord(char) - 0x60) if '\u30a1' <= char <= '\u30f6' else char
                   for char in text)
    output = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == 'っ':
            output.append('!')
            index += 1
            continue
        if char == 'ー':
            previous = ''.join(output)
            vowel = next((letter for letter in reversed(previous) if letter in 'aeiou'), '')
            if vowel:
                output.append(vowel)
            index += 1
            continue
        pair = text[index:index + 2]
        if pair in FOREIGN_KANA:
            token, index = FOREIGN_KANA[pair], index + 2
        elif pair in YOON:
            token, index = YOON[pair], index + 2
        elif char in KANA:
            token, index = KANA[char], index + 1
            if char == 'ん' and index < len(text) and text[index] in 'あいうえおやゆよ':
                token = "n'"
        elif char in 'ぁぃぅぇぉゃゅょ':
            token, index = char, index + 1
        else:
            token, index = char, index + 1
        if output and output[-1] == '!':
            output.pop()
            first = token[:1]
            if token.startswith('ch'):
                output.append('t')
            elif first not in 'aeiou' and first.isalpha():
                output.append(first)
        output.append(token)
    return ''.join(output)


def romanization_keys(value):
    base = normalize(value)
    if not base:
        return set()
    variants = {base}
    for pattern, replacement in ((r'([aeiou])\1', r'\1'), (r'ou', 'o'), (r'ei', 'e')):
        current = base
        while True:
            updated = re.sub(pattern, replacement, current)
            if updated == current:
                break
            variants.add(updated)
            current = updated
    return variants


def candidate_keys(reading, surface):
    keys = {normalize(reading), normalize(surface)}
    reading_text = unicodedata.normalize('NFKC', reading)
    reading_text = ''.join(chr(ord(char) - 0x60) if '\u30a1' <= char <= '\u30f6' else char
                           for char in reading_text)
    if reading_text and all('\u3040' <= char <= '\u309f' or char in 'ー・ ' for char in reading_text):
        keys.update(romanization_keys(kana_to_romaji(reading_text)))
    return keys - {''}


def source_status(domain, row):
    demographics = {part.strip() for part in row.get('demographics', '').split('|') if part.strip()}
    tagged = [LABELS[value] for value in demographics if value in LABELS]
    genres = {part.strip().casefold() for part in row.get('genres', '').split('|') if part.strip()}
    adult = 'hentai' in genres or (domain == 'anime' and row.get('rating', '').startswith('Rx'))
    if adult:
        return 'adult'
    if len(tagged) == 1 and len(demographics) == 1:
        return tagged[0]
    if len(tagged) > 1 and len(tagged) == len(demographics):
        return 'mixed'
    if not demographics:
        return 'unspecified'
    return None


def mal_reference(domain, mal_id):
    return f'https://myanimelist.net/{domain}/{mal_id}'


def add_alias(index, alias, record_id):
    for key in {normalize(alias), *romanization_keys(kana_to_romaji(alias))}:
        if key:
            index[key].add(record_id)


def build_work_source(path, domain):
    aliases = collections.defaultdict(set)
    records = {}
    source_info = DATASETS[domain]
    for row in read_csv(path):
        mal_id = row.get('mal_id', '').strip()
        if not mal_id.isdigit():
            continue
        record_id = str(int(mal_id))
        label = source_status(domain, row)
        current = records.get(record_id)
        if current is None:
            records[record_id] = {
                'label': label,
                'aliases': set(),
                'reference': mal_reference(domain, record_id),
                'domain': domain,
                'source': row.get('source', '').strip(),
                'sourceDemographics': row.get('demographics', '').strip(),
                'classificationSource': (
                    'mal_explicit_adult_tag' if label == 'adult'
                    else 'mal_demographics_unspecified' if label == 'unspecified'
                    else 'mal_demographics' if label else None
                ),
                'supportingReferences': [],
                'supportingIds': [],
                'supportingDomains': [],
            }
        elif current['label'] == 'adult' or label == 'adult':
            current['label'] = 'adult'
            current['classificationSource'] = 'mal_explicit_adult_tag'
        elif current['label'] != label:
            current['label'] = None
            current['classificationSource'] = None
        names = [row.get(name, '') for name in ('title', 'title_english', 'title_japanese')]
        for name in names:
            if name and name.strip():
                records[record_id]['aliases'].add(name.strip())
        for name in records[record_id]['aliases']:
            add_alias(aliases, name, record_id)
    return {'records': records, 'aliases': aliases, 'path': path, 'info': source_info,
            'sha256': digest(path)}


def infer_anime_demographics_from_manga(anime_source, manga_source):
    counts = collections.Counter()
    allowed_sources = {'Manga', 'Web manga', '4-koma manga'}
    for anime_id, record in anime_source['records'].items():
        if (record['label'] not in (None, 'unspecified') or record['sourceDemographics']
                or record['source'] not in allowed_sources):
            continue
        keys = set()
        for alias in record['aliases']:
            keys.update(candidate_keys('', alias))
        matches = {record_id: manga_source['records'][record_id]
                   for record_id in find_records(manga_source['aliases'], keys)}
        labels = {match['label'] for match in matches.values() if match['label'] is not None}
        concrete = labels - {'unspecified'}
        if 'adult' in concrete:
            label = 'adult'
        elif 'mixed' in concrete or len(concrete) > 1:
            label = 'mixed'
        elif len(concrete) == 1:
            label = next(iter(concrete))
        elif 'unspecified' in labels:
            label = 'unspecified'
        else:
            counts['anime_manga_relation_unlabelled' if matches else 'anime_manga_relation_no_match'] += 1
            continue
        supporting = [match for match in matches.values()
                      if match['label'] == label or label == 'mixed' and
                      match['label'] not in ('unspecified', None)]
        record['label'] = label
        record['classificationSource'] = 'adapted_manga_source_and_title'
        record['supportingReferences'] = sorted({match['reference'] for match in supporting})
        record['supportingIds'] = sorted({record_id for record_id, match in matches.items()
                                          if match['label'] == label})
        record['supportingDomains'] = ['manga']
        counts['anime_inherited_' + label] += 1
    return counts


def anime_id_from_url(value):
    parsed = urlsplit(value)
    match = re.fullmatch(r'/anime/(\d+)(?:/.*)?', parsed.path)
    return str(int(match.group(1))) if parsed.hostname == 'myanimelist.net' and match else None


def build_character_source(path, anime_source):
    appearances = collections.defaultdict(set)
    aliases = collections.defaultdict(set)
    identity_urls = {}
    anime_by_id = anime_source['records']
    for row in read_csv(path):
        anime_id = anime_id_from_url(row.get('anime_source', ''))
        identity = row.get('character_source', '').strip()
        if not anime_id or not identity:
            continue
        parsed = urlsplit(identity)
        if parsed.scheme != 'https' or not parsed.hostname:
            continue
        identity = identity.rstrip('/')
        identity_urls[identity] = identity
        if anime_id not in anime_by_id:
            appearances[identity].add((anime_id, None))
        else:
            appearances[identity].add((anime_id, anime_by_id[anime_id]['label']))
        for field in ('character_name', 'japanese_name'):
            name = row.get(field, '').strip()
            if name:
                for key in {normalize(name), *romanization_keys(kana_to_romaji(name))}:
                    if key:
                        aliases[key].add(identity)
    records = {}
    for identity, rows in appearances.items():
        known = {label for _, label in rows if label is not None}
        concrete = known - {'unspecified'}
        if 'adult' in concrete:
            label = 'adult'
        elif 'mixed' in concrete or len(concrete) > 1:
            label = 'mixed'
        elif len(concrete) == 1:
            label = next(iter(concrete))
        elif 'unspecified' in known:
            label = 'unspecified'
        else:
            label = None
        anime_ids = sorted({anime_id for anime_id, value in rows
                            if value is not None and (value == label or
                               label == 'mixed' and value not in ('adult', 'unspecified') or
                               label == 'adult' and value == 'adult')})
        refs = {mal_reference('anime', anime_id) for anime_id in anime_ids}
        manga_ids = set()
        for anime_id in anime_ids:
            anime_record = anime_by_id.get(anime_id)
            if anime_record:
                refs.update(anime_record.get('supportingReferences', []))
                manga_ids.update(anime_record.get('supportingIds', []))
        supporting_domains = {'anime'}
        if manga_ids:
            supporting_domains.add('manga')
        records[identity] = {
            'label': label,
            'reference': identity,
            'domain': 'characters',
            'supportingReferences': sorted(refs)[:20],
            'supportingIds': anime_ids[:10],
            'supportingMangaIds': sorted(manga_ids)[:10],
            'supportingDomains': sorted(supporting_domains),
        }
    return {'records': records, 'aliases': aliases, 'path': path, 'info': DATASETS['characters'],
            'sha256': digest(path)}


def find_records(index, keys):
    found = set()
    for key in keys:
        found.update(index.get(key, ()))
    return found


def resolve_work(indices, keys):
    found = [(index, record_id, key) for index in indices for key in keys
             for record_id in index['aliases'].get(key, ())]
    if not found:
        return None, 'no_match'
    unique_records = {(id(index), record_id): (index, record_id) for index, record_id, _ in found}
    records = [index['records'][record_id] for index, record_id in unique_records.values()]
    adult_records = [record for record in records if record['label'] == 'adult']
    if adult_records:
        label = 'adult'
        selected = adult_records
    else:
        if any(record['label'] is None for record in records):
            return None, 'conflict'
        labels = {record['label'] for record in records if record['label'] is not None}
        concrete = labels - {'unspecified'}
        if 'mixed' in concrete or len(concrete) > 1:
            label = 'mixed'
        elif len(concrete) == 1:
            label = next(iter(concrete))
        elif 'unspecified' in labels:
            label = 'unspecified'
        else:
            return None, 'conflict' if any(record['label'] is None for record in records) else 'unlabelled'
        selected = ([record for record in records if record['label'] not in ('unspecified', None)]
                    if label == 'mixed'
                    else [record for record in records if record['label'] in (label, 'unspecified')])
    return {'label': label, 'records': selected}, 'matched'


def resolve_character(index, keys):
    found = find_records(index['aliases'], keys)
    if not found:
        return None, 'no_match'
    if len(found) != 1:
        return None, 'ambiguous_identity'
    record = index['records'][next(iter(found))]
    if record['label'] is None:
        return None, 'unlabelled_or_conflicting_sources'
    return {'label': record['label'], 'records': [record]}, 'matched'


def read_decisions(root):
    path = root / 'src/main/classification/distribution-decisions.tsv.gz'
    with gzip.open(path, 'rt', encoding='utf-8') as source:
        return {tuple(row[:2]): row for row in
                (line.rstrip('\n').split('\t') for line in source)}


def active_media_pairs(root):
    path = root / 'src/main/classification/distribution-candidates.tsv.gz'
    active = collections.defaultdict(set)
    with gzip.open(path, 'rt', encoding='utf-8') as source:
        for line in source:
            row = line.rstrip('\n').split('\t')
            if len(row) == 6 and row[0] in ('work_anime', 'work_manga', 'character'):
                active[(row[1], row[5])].add(row[0])
    return active


def review_entry(pair, baseline, current_categories, classification_origin, result, source_indexes,
                 match_method, added_record=None):
    label = result['label']
    categories = [] if label == 'adult' else sorted({
        *current_categories,
        distribution.MEDIA_DEMOGRAPHIC_LABEL_CATEGORIES[label],
    })
    if label == 'source_unverified':
        if not source_indexes:
            raise ValueError(f'Missing source datasets for unverified media pair: {pair}')
        datasets = [{
            'sourceDataset': index['info']['url'],
            'sourceDatasetVersion': index['info']['version'],
            'sourceDatasetLicense': index['info']['license'],
            'sourceDatasetFile': index['info']['file'],
            'sourceDatasetSha256': index['sha256'],
        } for index in source_indexes]
        detail = {
            'no_source_match': '候補名・読みから一意な出典作品を照合できませんでした',
            'ambiguous_character_match': 'キャラクター名が複数の出典IDに一致しました',
            'source_record_without_supported_demographic': '出典候補は見つかりましたが対象層を示す対応タグがありません',
            'conflicting_source_labels': '作品とキャラクターの出典で対象層が一致しません',
        }.get(result.get('resolutionStatus'), '対象層の根拠を一意に確定できませんでした')
        evidence = {
            'kind': 'media_demographic_source_search',
            'reading': pair[0],
            'surface': pair[1],
            'categories': categories,
            'reference': datasets[0]['sourceDataset'],
            'searchedDatasets': datasets,
            'matchMethod': match_method,
            'resolutionStatus': result['resolutionStatus'],
        }
        if result.get('candidateReferences'):
            evidence['candidateReferences'] = sorted(set(result['candidateReferences']))[:20]
        reason = (f"{'、'.join(dataset['sourceDatasetFile'] for dataset in datasets)}を照合。{detail}。"
                  '出典未確認・対象層未確定カテゴリに収録します。この分類は全年齢向けを意味しません。')
        entry = {
            'action': 'reclassify',
            'baseline': baseline,
            'candidate_key': distribution.key(*pair),
            'categories': categories,
            'classification_origin': classification_origin,
            'evidence': evidence,
            'media_demographic': label,
            'reading': pair[0],
            'reason': reason,
            'surface': pair[1],
        }
        if added_record is not None:
            entry['added_record'] = added_record
        return entry
    work_refs = sorted({record['reference'] for record in result['records']})
    supports = sorted({reference for record in result['records']
                       for reference in record.get('supportingReferences', [])})
    supporting_anime_ids = sorted({record_id for record in result['records']
                                   for record_id in record.get('supportingIds', [])})
    supporting_manga_ids = sorted({record_id for record in result['records']
                                   for record_id in record.get('supportingMangaIds', [])})
    primary = result['records'][0]
    source_index = next((index for index in source_indexes
                         if index['info']['file'] == DATASETS[primary['domain']]['file']), None)
    if source_index is None:
        source_index = source_indexes[0]
    info = source_index['info']
    label_name = LABEL_NAMES[label]
    if label == 'adult':
        if primary.get('classificationSource') == 'adapted_manga_source_and_title':
            reason = ('アニメの出典が漫画と記録され、同名の原作漫画でHentaiタグを確認。'
                      '成人向けとして全カテゴリから除外。')
        else:
            reason = ('MyAnimeList由来データでHentaiまたはRx（Hentai）と記録されているため、'
                      '成人向けとして全カテゴリから除外。')
        action = 'exclude'
    elif label == 'unspecified':
        if primary['domain'] == 'characters':
            reason = ('架空キャラクターの出典IDと対象アニメを照合。対象作品のMyAnimeList demographics欄が空のため、'
                      '対象層タグなしカテゴリに収録。')
        elif primary.get('classificationSource') == 'adapted_manga_source_and_title':
            reason = ('アニメの出典が漫画と記録され、同名の原作漫画を照合。'
                      '原作のMyAnimeList demographics欄が空のため、対象層タグなしカテゴリに収録。')
        else:
            reason = (f"{info['file']}で対象タイトルを照合。MyAnimeList demographics欄に対象層タグがないため、"
                      '対象層タグなしカテゴリに収録。')
        action = 'reclassify'
    elif label == 'mixed':
        tags = sorted({part for record in result['records']
                       for part in record.get('sourceDemographics', '').split('|') if part.strip()})
        detail = f"対象層タグ（{'、'.join(tags)}）" if tags else '出典間で異なる対象層'
        reason = f"{info['file']}で複数の{detail}を確認。複数対象層カテゴリに収録。"
        action = 'reclassify'
    elif primary['domain'] == 'characters':
        anime_file = next(index['info']['file'] for index in source_indexes if index['info']['file'] == 'anime_dataset.csv')
        reason = (f"{info['file']} のキャラクターIDと出典アニメIDを照合し、関連アニメの{anime_file}"
                  f"またはその漫画原作のdemographics欄で{label_name}と確認。"
                  'キャラクターは出典作品の対象層を継承。')
        action = 'reclassify'
    elif primary.get('classificationSource') == 'adapted_manga_source_and_title':
        reason = (f"{info['file']} で出典が漫画と記録され、同名の原作漫画を一意に照合。"
                  f"{label_name}（MyAnimeList demographics）をアニメ作品の対象層として継承。")
        action = 'reclassify'
    else:
        source_label = next(k for k, v in LABELS.items() if v == label)
        reason = (f"{info['file']} のdemographics欄で{label_name}（{source_label}）と記録。")
        if 'character' in current_categories:
            reason += 'キャラクターは出典作品の対象層を継承。'
        action = 'reclassify'
    evidence = {
        'kind': 'media_demographic_source',
        'reading': pair[0],
        'surface': pair[1],
        'categories': categories,
        'reference': primary['reference'],
        'sourceDataset': info['url'],
        'sourceDatasetVersion': info['version'],
        'sourceDatasetLicense': info['license'],
        'sourceDatasetFile': info['file'],
        'sourceDatasetSha256': source_index['sha256'],
        'matchMethod': match_method,
    }
    additional_refs = [reference for reference in work_refs if reference != primary['reference']]
    if additional_refs:
        evidence['supportingReferences'] = additional_refs[:20]
    other_datasets = [
        {'sourceDataset': index['info']['url'], 'sourceDatasetVersion': index['info']['version'],
         'sourceDatasetLicense': index['info']['license'], 'sourceDatasetFile': index['info']['file'],
         'sourceDatasetSha256': index['sha256']}
        for index in source_indexes if index is not source_index
    ]
    if other_datasets:
        evidence['supportingDatasets'] = other_datasets
    anime_refs = [reference for reference in supports if '/anime/' in urlsplit(reference).path]
    manga_refs = [reference for reference in supports if '/manga/' in urlsplit(reference).path]
    if anime_refs:
        evidence['supportingAnimeReferences'] = anime_refs[:10]
    if manga_refs:
        evidence['supportingMangaReferences'] = manga_refs[:10]
    if supporting_anime_ids:
        evidence['supportingAnimeIds'] = supporting_anime_ids[:10]
    if supporting_manga_ids:
        evidence['supportingMangaIds'] = supporting_manga_ids[:10]
    entry = {
        'action': action,
        'baseline': baseline,
        'candidate_key': distribution.key(*pair),
        'categories': categories,
        'classification_origin': classification_origin,
        'evidence': evidence,
        'media_demographic': label,
        'reading': pair[0],
        'reason': reason,
        'surface': pair[1],
    }
    if added_record is not None:
        entry['added_record'] = added_record
    return entry


def generate(root, anime_path, manga_path, character_path, review_path, write):
    manga = build_work_source(manga_path, 'manga')
    anime = build_work_source(anime_path, 'anime')
    inference_counts = infer_anime_demographics_from_manga(anime, manga)
    characters = build_character_source(character_path, anime)
    selected = reviews.load(root)
    decisions = read_decisions(root)
    active = active_media_pairs(root)
    work_indexes = {'anime': anime, 'manga': manga}
    counts = collections.Counter(inference_counts)
    new_entries = []
    for pair in active:
        row = decisions.get(pair)
        if row is None or row[4] != 'classified':
            continue
        cats = set(filter(None, row[2].split(',')))
        domains = []
        if 'work_anime' in cats:
            domains.append('anime')
        if 'work_manga' in cats:
            domains.append('manga')
        is_character = 'character' in cats
        if not domains and not is_character:
            continue
        counts['candidates'] += 1
        previous = selected.get(pair)
        if previous and previous.get('media_demographic'):
            counts['already_media_reviewed'] += 1
            continue
        original = previous['baseline'] if previous else row
        added_record = previous.get('added_record') if previous else None
        if original is None and added_record is None or original is not None and original[4] != 'classified':
            counts['existing_addition_or_exclusion'] += 1
            continue
        origin = reviews.resulting_origin(previous) if previous else original[3]
        keys = candidate_keys(pair[0], pair[1])
        results = []
        methods = set()
        reasons = []
        statuses = []
        candidate_references = []
        if domains:
            candidate_references.extend(
                work_indexes[domain]['records'][record_id]['reference']
                for domain in domains
                for record_id in find_records(work_indexes[domain]['aliases'], keys)
            )
            resolved, status = resolve_work([work_indexes[domain] for domain in domains], keys)
            counts['work_' + status] += 1
            statuses.append(('work', status))
            if resolved:
                results.append(resolved)
                methods.add('normalized-title-or-kana-reading')
                if any(record.get('classificationSource') == 'adapted_manga_source_and_title'
                       for record in resolved['records']):
                    methods.add('anime-source-and-manga-title-demographics')
            else:
                reasons.append(status)
        if is_character:
            candidate_references.extend(
                characters['records'][identity]['reference']
                for identity in find_records(characters['aliases'], keys)
            )
            resolved, status = resolve_character(characters, keys)
            counts['character_' + status] += 1
            statuses.append(('character', status))
            if resolved:
                results.append(resolved)
                methods.add('unique-character-identity-and-source-anime')
            elif not domains:
                reasons.append(status)
        labels = {result['label'] for result in results}
        records = [record for result in results for record in result['records']]
        if 'adult' in labels:
            combined = {'label': 'adult', 'records': [record for record in records if record['label'] == 'adult']}
        elif ('conflict' in reasons or len(labels) > 1 or not labels
              or any(status in ('ambiguous_identity', 'unlabelled_or_conflicting_sources')
                     for _, status in statuses)):
            if len(labels) > 1:
                resolution_status = 'conflicting_source_labels'
                counts['cross_type_conflict'] += 1
            elif any(status == 'ambiguous_identity' for _, status in statuses):
                resolution_status = 'ambiguous_character_match'
            elif any(status in ('conflict', 'unlabelled_or_conflicting_sources') for _, status in statuses):
                resolution_status = 'source_record_without_supported_demographic'
            else:
                resolution_status = 'no_source_match'
            combined = {
                'label': 'source_unverified',
                'records': records,
                'resolutionStatus': resolution_status,
                'candidateReferences': candidate_references,
            }
        else:
            combined = {'label': next(iter(labels)), 'records': records}
        used_domains = {record['domain'] for record in combined['records']}
        if combined['label'] == 'source_unverified':
            searched_domains = set(domains)
            if is_character:
                searched_domains.update(('characters', 'anime'))
            if 'anime' in searched_domains or 'characters' in searched_domains:
                searched_domains.add('manga')
            source_indexes = [work_indexes[domain] for domain in ('anime', 'manga')
                              if domain in searched_domains]
            if 'characters' in searched_domains:
                source_indexes.append(characters)
        else:
            source_indexes = [work_indexes[domain] for domain in ('anime', 'manga')
                              if domain in used_domains]
        for domain in ('anime', 'manga'):
            if any(domain in record.get('supportingDomains', []) for record in combined['records']):
                if domain not in used_domains:
                    source_indexes.append(work_indexes[domain])
        if 'characters' in used_domains and combined['label'] != 'source_unverified':
            source_indexes.append(characters)
            if 'anime' not in used_domains:
                source_indexes.append(anime)
            if 'manga' not in used_domains and any(
                    'manga' in record.get('supportingDomains', []) for record in combined['records']):
                source_indexes.append(manga)
        method = '+'.join(sorted(methods)) or 'normalized-title-or-kana-reading-no-unique-match'
        new_entries.append(review_entry(pair, original, cats, origin, combined, source_indexes,
                                        method, added_record))
        counts['new_' + combined['label']] += 1
    new_entries.sort(key=lambda entry: (entry['reading'], entry['surface']))
    if write:
        old_lines = review_path.read_text(encoding='utf-8').splitlines() if review_path.exists() else []
        lines = [*old_lines, *(json.dumps(entry, ensure_ascii=False, sort_keys=True) for entry in new_entries)]
        review_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = review_path.with_suffix(review_path.suffix + '.tmp')
        temporary.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')
        temporary.replace(review_path)
    return counts, new_entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--anime-csv', required=True, type=Path)
    parser.add_argument('--manga-csv', required=True, type=Path)
    parser.add_argument('--characters-csv', required=True, type=Path)
    parser.add_argument('--review-ledger', type=Path)
    parser.add_argument('--write', action='store_true', help='write new source-backed reviews to the ledger')
    args = parser.parse_args()
    root = args.root.resolve()
    review_path = args.review_ledger or root / REVIEW_PATH
    counts, entries = generate(root, args.anime_csv, args.manga_csv, args.characters_csv,
                               review_path, args.write)
    result = dict(counts)
    result['sourceSha256'] = {
        'anime': digest(args.anime_csv),
        'manga': digest(args.manga_csv),
        'characters': digest(args.characters_csv),
    }
    result['generatedReviews'] = len(entries)
    result['written'] = args.write
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
