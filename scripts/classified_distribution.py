#!/usr/bin/env python3
"""Freeze saved classifications, or verify the frozen distribution (no model calls)."""
import argparse
import collections
import gzip
import hashlib
import io
import json
import os
import re
import tempfile
import unicodedata
from datetime import date, datetime
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
import zipfile

SOURCES = {
    'person': ('src/main/bin/names.txt', None),
    'place': ('src/main/bin/place.txt.zip', 'place.txt'),
    'wiki': ('src/main/bin/only_wiki.txt.zip', 'only_wiki.txt'),
    'neologd': ('src/main/bin/only_neologd.txt.zip', 'only_neologd.txt'),
    'web': ('src/main/bin/wiki_neologd_common.txt.zip', 'wiki_neologd_common.txt'),
}
TERM_ADDITIONS_PATH = 'src/main/classification/term-additions.tsv'
TERM_TAXONOMY_PATH = 'src/main/classification/term-taxonomy.json'
TERM_CLASSIFICATIONS_PATH = 'src/main/classification/term-classifications.tsv.gz'
TERM_CLASSIFICATIONS_MANIFEST_PATH = 'src/main/classification/term-classifications-manifest.json'
EVENT_TAXONOMY_PATH = 'src/main/classification/event-taxonomy.json'
EVENT_CLASSIFICATIONS_PATH = 'src/main/classification/event-classifications.tsv.gz'
EVENT_CLASSIFICATIONS_MANIFEST_PATH = 'src/main/classification/event-classifications-manifest.json'
MEDIA_DEMOGRAPHIC_TAXONOMY_PATH = 'src/main/classification/media-demographic-taxonomy.json'
MEDIA_DEMOGRAPHIC_LABEL_CATEGORIES = {
    'shonen': 'media_demographic/audience/shonen',
    'seinen': 'media_demographic/audience/seinen',
    'shojo': 'media_demographic/audience/shojo',
}
MEDIA_DEMOGRAPHIC_LABELS = {*MEDIA_DEMOGRAPHIC_LABEL_CATEGORIES, 'adult'}
MEDIA_DEMOGRAPHIC_LIMITATION = (
    'Media demographic labels cover source-reviewed pairs only; unreviewed media and source-linked characters '
    'are not guaranteed classified or excluded.'
)
TERM_CLASSIFICATION_PROMPT_VERSIONS = {
    'term-best-fit-15-categories-ordered-groups-10-v2',
    'term-best-fit-15-categories-ordered-code-array-v3',
}
LEGACY_PERSON_SPORT_IDS = {'mma', 'kickboxing', 'boxing'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def write_gzip(path, lines):
    with path.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped:
        with io.TextIOWrapper(zipped, encoding='utf-8', newline='\n') as text:
            for row in lines:
                text.write('\t'.join(row) + '\n')


def term_taxonomy(root):
    path = root / TERM_TAXONOMY_PATH
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schemaVersion') != 1 or data.get('id') != 'term':
        raise ValueError('Unsupported term taxonomy')
    groups = data.get('groups')
    if not isinstance(groups, list) or [group.get('id') for group in groups] != ['general', 'specialist']:
        raise ValueError('Term taxonomy must contain general then specialist groups')
    flattened = []
    group_metadata = []
    for group in groups:
        entries = group.get('categories')
        expected = 5 if group['id'] == 'general' else 10
        if not isinstance(entries, list) or len(entries) != expected:
            raise ValueError(f'Expected {expected} term categories in {group["id"]}')
        ids = []
        for category in entries:
            if (not isinstance(category.get('id'), str)
                    or not re.fullmatch(r'term/(general|specialist)/[a-z_]+', category['id'])
                    or not category['id'].startswith(f'term/{group["id"]}/')
                    or not isinstance(category.get('name'), str) or not category['name']
                    or not isinstance(category.get('definition'), str) or not category['definition']):
                raise ValueError('Invalid term leaf category')
            flattened.append({key: category[key] for key in ('id', 'name', 'definition')})
            ids.append(category['id'])
        group_metadata.append({'id': f'term/{group["id"]}', 'name': group['name'], 'categories': ids})
    ids = [category['id'] for category in flattened]
    if len(ids) != 15 or len(set(ids)) != 15:
        raise ValueError('Term taxonomy must contain 15 unique leaf categories')
    return {'id': 'term', 'name': data['name'], 'groups': group_metadata}, flattened


def event_taxonomy(root):
    path = root / EVENT_TAXONOMY_PATH
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    if (data.get('schemaVersion') != 1 or data.get('id') != 'event'
            or [group.get('id') for group in data.get('groups', [])] != ['occasion', 'incident', 'history']):
        raise ValueError('Unsupported event taxonomy')
    flattened = []
    classifier_ids = []
    group_metadata = []
    for group in data['groups']:
        entries = group.get('categories')
        if not isinstance(entries, list):
            raise ValueError('Event taxonomy group must contain categories')
        ids = []
        for category in entries:
            if (not isinstance(category.get('id'), str)
                    or not re.fullmatch(r'event/(occasion|incident|history)/[a-z_]+', category['id'])
                    or not category['id'].startswith(f'event/{group["id"]}/')
                    or not isinstance(category.get('name'), str) or not category['name']
                    or not isinstance(category.get('definition'), str) or not category['definition']
                    or type(category.get('distribution')) is not bool):
                raise ValueError('Invalid event taxonomy leaf category')
            classifier_ids.append(category['id'])
            if category['distribution']:
                flattened.append({key: category[key] for key in ('id', 'name', 'definition')})
                ids.append(category['id'])
        group_metadata.append({'id': f'event/{group["id"]}', 'name': group['name'], 'categories': ids})
    all_ids = [category_id for group in data['groups'] for category_id in
               (category['id'] for category in group['categories'])]
    ids = [category['id'] for category in flattened]
    if (len(all_ids) != 9 or len(set(all_ids)) != 9 or len(ids) != 6 or len(set(ids)) != 6
            or len(classifier_ids) != 9):
        raise ValueError('Event taxonomy must contain nine labels and six distributable categories')
    return {'id': 'event', 'name': data['name'], 'groups': group_metadata}, flattened


def media_demographic_taxonomy(root, allowed=None):
    path = root / MEDIA_DEMOGRAPHIC_TAXONOMY_PATH
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    groups = data.get('groups') if isinstance(data, dict) else None
    if (not isinstance(data, dict) or data.get('schemaVersion') != 1 or data.get('id') != 'media_demographic'
            or data.get('name') != '作品・キャラクターの対象層'
            or not isinstance(data.get('definition'), str) or not data['definition']
            or not isinstance(groups, list) or len(groups) != 1 or not isinstance(groups[0], dict)
            or [group.get('id') for group in groups] != ['audience']
            or not isinstance(groups[0].get('name'), str) or not groups[0]['name']):
        raise ValueError('Unsupported media demographic taxonomy')
    group = groups[0]
    entries = group.get('categories')
    expected_ids = {f'media_demographic/audience/{label}' for label in MEDIA_DEMOGRAPHIC_LABEL_CATEGORIES}
    if not isinstance(entries, list) or len(entries) != len(expected_ids):
        raise ValueError('Media demographic audience taxonomy must contain three categories')
    flattened = []
    ids = []
    for category in entries:
        if (not isinstance(category, dict) or not isinstance(category.get('id'), str)
                or not re.fullmatch(r'media_demographic/audience/(shonen|seinen|shojo)', category['id'])
                or not isinstance(category.get('name'), str) or not category['name']
                or not isinstance(category.get('definition'), str) or not category['definition']
                or category.get('distribution') is not True):
            raise ValueError('Invalid media demographic audience category')
        ids.append(category['id'])
        flattened.append({key: category[key] for key in ('id', 'name', 'definition')})
    excluded = data.get('excludedCategories')
    if (set(ids) != expected_ids or len(set(ids)) != len(ids)
            or not isinstance(excluded, list) or len(excluded) != 1):
        raise ValueError('Media demographic taxonomy must contain the three audience categories and one excluded label')
    adult = excluded[0]
    if (not isinstance(adult, dict) or adult.get('id') != 'adult' or adult.get('name') != '成人向け'
            or not isinstance(adult.get('definition'), str) or not adult['definition']
            or adult.get('distribution') is not False):
        raise ValueError('Adult media demographic label must be excluded from distribution')
    if allowed is not None and not set(ids) <= allowed:
        raise ValueError('Media demographic categories are absent from categories.json')
    taxonomy = {
        'id': 'media_demographic',
        'name': data['name'],
        'groups': [{'id': 'media_demographic/audience', 'name': group['name'], 'categories': ids}],
    }
    return taxonomy, flattened


def merged_categories(base, term_data, event_data=None, media_demographic_data=None):
    if term_data is None and event_data is None and media_demographic_data is None:
        return base
    categories = list(base.get('categories', []))
    ids = [category.get('id') for category in categories]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate category IDs in source taxonomy')
    structures = []
    if term_data is not None:
        structure, term_categories = term_data
        structures.append(('term', structure, term_categories))
    if event_data is not None:
        structure, event_categories = event_data
        structures.append(('event', structure, event_categories))
    if media_demographic_data is not None:
        structure, demographic_categories = media_demographic_data
        structures.append(('media_demographic', structure, demographic_categories))
    inserted_at = {}
    for parent_id, structure, leaf_categories in structures:
        leaf_ids = {category['id'] for category in leaf_categories}
        if parent_id in ids:
            insertion = ids.index(parent_id)
            inserted_at[parent_id] = insertion
            categories = [category for category in categories if category.get('id') != parent_id]
            categories[insertion:insertion] = leaf_categories
            ids = [category.get('id') for category in categories]
        elif leaf_ids <= set(ids):
            existing = {category['id']: category for category in categories}
            for category in leaf_categories:
                if existing[category['id']].get('name') != category['name']:
                    raise ValueError(f'{parent_id.title()} category name differs from taxonomy: {category["id"]}')
                existing[category['id']]['definition'] = category['definition']
            categories = [existing[category_id] for category_id in ids]
            inserted_at[parent_id] = min(ids.index(category_id) for category_id in leaf_ids)
        else:
            raise ValueError(f'Source taxonomy must contain {parent_id} or all expanded {parent_id} categories')
    result = dict(base)
    result['categories'] = categories
    result['categoryGroups'] = [structure for parent_id, structure, _ in
                                sorted(structures, key=lambda item: inserted_at[item[0]])]
    return result


def term_classification_data(root, allowed=None):
    taxonomy_data = term_taxonomy(root)
    if taxonomy_data is None:
        return None
    taxonomy, categories = taxonomy_data
    category_ids = {category['id'] for category in categories}
    if allowed is not None and not category_ids <= allowed:
        raise ValueError('Term taxonomy leaf categories are absent from categories.json')
    path = root / TERM_CLASSIFICATIONS_PATH
    metadata_path = root / TERM_CLASSIFICATIONS_MANIFEST_PATH
    if not path.is_file() or not metadata_path.is_file():
        current = root / 'src/main/classification/categories.json'
        if current.is_file():
            current_ids = {category.get('id') for category in
                           json.loads(current.read_text(encoding='utf-8')).get('categories', [])}
            if 'term' in current_ids and not any(
                    category.startswith('term/') for category in current_ids if isinstance(category, str)):
                return None
        raise ValueError('Gemini term classifications and their provenance manifest are required')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    proofs = metadata.get('freeTierProofs')
    if (metadata.get('schemaVersion') != 1 or metadata.get('model') not in (
                'gemini-3.1-flash-lite', 'gemini-3.5-flash-lite')
            or metadata.get('apiEndpoint') != 'generateContent'
            or metadata.get('projectId') != 'gen-lang-client-0548563154'
            or metadata.get('freeTierOnly') is not True or metadata.get('billingEnabled') is not False
            or metadata.get('promptVersion') not in TERM_CLASSIFICATION_PROMPT_VERSIONS
            or not isinstance(proofs, list) or not proofs
            or any(any(type(proof.get(name)) is not int or proof[name] <= 0 for name in ('rpm', 'tpm', 'rpd'))
                   or not re.fullmatch(r'[0-9a-f]{64}', proof.get('sha256', ''))
                   or not isinstance(proof.get('verifiedAt'), str)
                   or proof.get('promptVersion') not in (None, *TERM_CLASSIFICATION_PROMPT_VERSIONS)
                   or datetime.fromisoformat(proof['verifiedAt']).tzinfo is None for proof in proofs)):
        raise ValueError('Term classification manifest does not record a verified Gemini free-tier run')
    if (not re.fullmatch(r'[0-9a-f]{64}', metadata.get('sourceCandidateSha256', ''))
            or not re.fullmatch(r'[0-9a-f]{64}', metadata.get('taxonomySha256', ''))):
        raise ValueError('Term classification manifest is missing input hashes')
    results = {}
    counts = collections.Counter()
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
        for number, line in enumerate(stream, 1):
            fields = line.rstrip('\n').split('\t')
            if len(fields) != 3 or not fields[0] or not fields[1] or fields[2] not in category_ids:
                raise ValueError(f'{TERM_CLASSIFICATIONS_PATH}:{number}: invalid category result')
            pair = fields[0], fields[1]
            if pair in results:
                raise ValueError(f'{TERM_CLASSIFICATIONS_PATH}:{number}: duplicate reading/surface pair')
            results[pair] = fields[2]
            counts[fields[2]] += 1
    if (len(results) != metadata.get('uniquePairs')
            or sum(counts.values()) != metadata.get('uniquePairs')
            or set(metadata.get('categoryCounts', {})) != category_ids
            or {category: counts[category] for category in category_ids} != metadata.get('categoryCounts')):
        raise ValueError('Term classification counts differ from their manifest')
    if any(type(metadata.get(field)) is not int or metadata[field] < 1
           for field in ('sourceTermRecords', 'uniquePairs', 'batchCount')):
        raise ValueError('Term classification manifest has invalid counts')
    if metadata['sourceTermRecords'] < metadata['uniquePairs']:
        raise ValueError('Term classification record count is below its unique-pair count')
    return {'taxonomy': taxonomy, 'categories': categories, 'results': results,
            'metadata': metadata, 'categoryIds': category_ids}


def event_classification_data(root, allowed=None):
    taxonomy_data = event_taxonomy(root)
    if taxonomy_data is None:
        return None
    taxonomy, categories = taxonomy_data
    category_ids = {category['id'] for category in categories}
    if allowed is not None and not category_ids <= allowed:
        raise ValueError('Distributable event categories are absent from categories.json')
    path = root / EVENT_CLASSIFICATIONS_PATH
    metadata_path = root / EVENT_CLASSIFICATIONS_MANIFEST_PATH
    if not path.is_file() or not metadata_path.is_file():
        current = root / 'src/main/classification/categories.json'
        if current.is_file():
            current_ids = {category.get('id') for category in
                           json.loads(current.read_text(encoding='utf-8')).get('categories', [])}
            if 'event' in current_ids and not any(
                    category.startswith('event/') for category in current_ids if isinstance(category, str)):
                return None
        raise ValueError('Gemini event classifications and their provenance manifest are required')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    taxonomy_ids = {category['id'] for group in json.loads(
        (root / EVENT_TAXONOMY_PATH).read_text(encoding='utf-8'))['groups'] for category in group['categories']}
    proofs = metadata.get('freeTierProofs')
    if (metadata.get('schemaVersion') != 1 or metadata.get('model') not in (
                'gemini-3.1-flash-lite', 'gemini-3.5-flash-lite')
            or metadata.get('apiEndpoint') != 'generateContent'
            or metadata.get('projectId') != 'gen-lang-client-0548563154'
            or metadata.get('freeTierOnly') is not True or metadata.get('billingEnabled') is not False
            or metadata.get('promptVersion') != 'event-six-distributable-three-classification-only-v1'
            or metadata.get('taxonomySha256') != sha(root / EVENT_TAXONOMY_PATH)
            or not isinstance(proofs, list) or not proofs
            or any(any(type(proof.get(name)) is not int or proof[name] <= 0 for name in ('rpm', 'tpm', 'rpd'))
                   or not re.fullmatch(r'[0-9a-f]{64}', proof.get('sha256', ''))
                   or not isinstance(proof.get('verifiedAt'), str)
                   or proof.get('apiEndpoint') != 'generateContent'
                   or datetime.fromisoformat(proof['verifiedAt']).tzinfo is None for proof in proofs)):
        raise ValueError('Event classification manifest does not record a verified Gemini free-tier run')
    if (not re.fullmatch(r'[0-9a-f]{64}', metadata.get('sourcePairSha256', ''))
            or not re.fullmatch(r'[0-9a-f]{64}', metadata.get('taxonomySha256', ''))
            or not isinstance(metadata.get('sourceFiles'), dict)
            or any(not isinstance(name, str) or not re.fullmatch(r'[0-9a-f]{64}', value)
                   for name, value in metadata['sourceFiles'].items())):
        raise ValueError('Event classification manifest is missing input hashes')
    counts = metadata.get('categoryCounts')
    if (set(counts or {}) != taxonomy_ids
            or any(type(value) is not int or value < 0 for value in counts.values())
            or sum(counts.values()) != metadata.get('uniquePairs')):
        raise ValueError('Event classification category counts are invalid')
    results = {}
    row_counts = collections.Counter()
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
        for number, line in enumerate(stream, 1):
            fields = line.rstrip('\n').split('\t')
            if len(fields) != 3 or not fields[0] or not fields[1] or fields[2] not in category_ids:
                raise ValueError(f'{EVENT_CLASSIFICATIONS_PATH}:{number}: invalid category result')
            pair = fields[0], fields[1]
            if pair in results:
                raise ValueError(f'{EVENT_CLASSIFICATIONS_PATH}:{number}: duplicate reading/surface pair')
            results[pair] = fields[2]
            row_counts[fields[2]] += 1
    expected_distribution_counts = {category: counts[category] for category in category_ids}
    if ({category: row_counts[category] for category in category_ids} != expected_distribution_counts
            or len(results) != sum(expected_distribution_counts.values())):
        raise ValueError('Saved event classifications contain missing or classifier-only data')
    if (any(type(metadata.get(field)) is not int or metadata[field] < 1
            for field in ('uniquePairs', 'batchCount'))
            or metadata['batchCount'] > metadata['uniquePairs']):
        raise ValueError('Event classification manifest has invalid counts')
    return {'taxonomy': taxonomy, 'categories': categories, 'results': results,
            'metadata': metadata, 'categoryIds': category_ids, 'taxonomyIds': taxonomy_ids}


def apply_term_classifications(root, decisions, force=False, reviewed_pairs=()):
    """Replace the structural term parent with one saved Gemini leaf per admitted pair."""
    if not force:
        current = root / 'src/main/classification/categories.json'
        if current.is_file():
            current_ids = {category.get('id') for category in
                           json.loads(current.read_text(encoding='utf-8')).get('categories', [])}
            if 'term' in current_ids and not any(
                    category.startswith('term/') for category in current_ids if isinstance(category, str)):
                return {pair: list(row) for pair, row in decisions.items()}
    data = term_classification_data(root)
    if data is None:
        return {pair: list(row) for pair, row in decisions.items()}
    results = data['results']
    review_entries = reviewed_pairs if isinstance(reviewed_pairs, dict) else {}
    reviewed_pairs = set(reviewed_pairs)
    output = {}
    for pair, original in decisions.items():
        row = list(original)
        categories = set(filter(None, row[2].split(',')))
        if row[4] == 'classified' and 'term' in categories:
            if pair not in results:
                raise ValueError(f'No Gemini term category for admitted pair: {pair}')
            categories.remove('term')
            categories.add(results[pair])
            if len(categories & data['categoryIds']) != 1:
                raise ValueError(f'Each admitted term pair must have exactly one Gemini leaf category: {pair}')
            row[2] = ','.join(sorted(categories))
        elif any(category.startswith('term/') for category in categories):
            leaf_categories = categories & data['categoryIds']
            review = review_entries.get(pair)
            source_backed_addition = (
                isinstance(review, dict) and review.get('action') == 'add'
                and isinstance(review.get('added_record'), dict)
                and review.get('evidence', {}).get('kind') == 'independent_source'
            )
            if len(leaf_categories) != 1 or (pair not in results and not source_backed_addition):
                raise ValueError(f'Each admitted term pair must have one leaf category and valid provenance: {pair}')
            for category in leaf_categories:
                if pair not in reviewed_pairs and results.get(pair) != category:
                    raise ValueError(f'Frozen term category differs from Gemini result: {pair}')
        output[pair] = row
    return output


def apply_event_classifications(root, decisions, force=False, reviewed_pairs=()):
    """Replace the structural event parent with saved distributable Gemini leaves."""
    if not force:
        current = root / 'src/main/classification/categories.json'
        if current.is_file():
            current_ids = {category.get('id') for category in
                           json.loads(current.read_text(encoding='utf-8')).get('categories', [])}
            if 'event' in current_ids and not any(
                    category.startswith('event/') for category in current_ids if isinstance(category, str)):
                return {pair: list(row) for pair, row in decisions.items()}
    data = event_classification_data(root)
    if data is None:
        return {pair: list(row) for pair, row in decisions.items()}
    results = data['results']
    review_entries = reviewed_pairs if isinstance(reviewed_pairs, dict) else {}
    reviewed_pairs = set(review_entries)
    output = {}
    for pair, original in decisions.items():
        row = list(original)
        categories = set(filter(None, row[2].split(',')))
        if 'event' in categories:
            if pair not in results:
                raise ValueError(f'No saved distributable event category for retained pair: {pair}')
            categories.remove('event')
            categories.add(results[pair])
            if len(categories & data['categoryIds']) != 1:
                raise ValueError(f'Each retained event pair must have exactly one distributable category: {pair}')
            row[2] = ','.join(sorted(categories))
        elif any(category.startswith('event/') for category in categories):
            leaf_categories = categories & data['categoryIds']
            review = review_entries.get(pair)
            source_backed_addition = (
                isinstance(review, dict) and review.get('action') == 'add'
                and isinstance(review.get('added_record'), dict)
                and review.get('evidence', {}).get('kind') == 'independent_source'
            )
            if len(leaf_categories) != 1 or (pair not in results and not source_backed_addition):
                raise ValueError(f'Each retained event pair must have exactly one distributable category: {pair}')
            for category in leaf_categories:
                if pair not in reviewed_pairs and results.get(pair) != category:
                    raise ValueError(f'Frozen event category differs from Gemini result: {pair}')
        output[pair] = row
    return output


def apply_event_classifications_snapshot(root, classification_map, run_metadata):
    """Expand the event parent and redact classifier-only pairs from event snapshots."""
    import copy
    import shutil
    import tempfile
    import classification_reviews as reviews
    import luna_reclassification as luna
    import run_event_classification as event_runner

    root = Path(root).resolve()
    directory = root / 'src/main/classification'
    current_manifest = json.loads((directory / 'distribution-manifest.json').read_text(encoding='utf-8'))
    for relative, expected in current_manifest['inputs'].items():
        if sha(root / relative) != expected:
            raise ValueError(f'Input hash mismatch before event migration: {relative}')
    for name, expected in current_manifest['files'].items():
        if sha(directory / name) != expected:
            raise ValueError(f'Classification hash mismatch before event migration: {name}')
    if sha(root / 'src/main/resources/id.def') != current_manifest['idDefSha256']:
        raise ValueError('id.def hash mismatch before event migration')
    if not (directory / 'event-taxonomy.json').is_file():
        raise ValueError('Event taxonomy is missing')
    raw_taxonomy = json.loads((root / EVENT_TAXONOMY_PATH).read_text(encoding='utf-8'))
    classifier_categories = [category for group in raw_taxonomy['groups'] for category in group['categories']]
    category_ids = {category['id'] for category in classifier_categories}
    distributed_ids = {category['id'] for category in classifier_categories if category['distribution']}
    items, _, _ = event_runner.collect_items(root)
    if (set(classification_map) != set(items)
            or any(category_id not in category_ids for category_id in classification_map.values())):
        raise ValueError('Event classification results do not cover the exact event snapshot')
    counts = collections.Counter(classification_map.values())
    expected_counts = run_metadata.get('categoryCounts', {})
    if (set(expected_counts) != category_ids or
            {category: counts[category] for category in category_ids} != expected_counts or
            sum(counts.values()) != len(items)):
        raise ValueError('Event classification category totals do not match the exact input')
    excluded_pairs = {pair for pair, category in classification_map.items() if category not in distributed_ids}

    # These are separate user-reviewed dictionary sources; do not silently change them.
    for _, row in term_addition_rows(root):
        if (row[0], row[4]) in excluded_pairs:
            raise ValueError('Classifier-only pairs overlap term-addition data')
    additions_dir = directory / 'person-additions'
    if additions_dir.is_dir():
        for path in additions_dir.glob('*.jsonl'):
            with path.open(encoding='utf-8') as stream:
                for line in stream:
                    record = json.loads(line)
                    if (record.get('reading'), record.get('surface')) in excluded_pairs:
                        raise ValueError('Classifier-only pairs overlap person-addition data')

    event_metadata = dict(run_metadata)
    event_metadata.update(schemaVersion=1, taxonomySha256=sha(root / EVENT_TAXONOMY_PATH),
                          uniquePairs=len(items), categoryCounts={key: counts[key] for key in sorted(category_ids)})
    if (not event_metadata.get('freeTierOnly') or event_metadata.get('billingEnabled') is not False
            or event_metadata.get('model') not in ('gemini-3.1-flash-lite', 'gemini-3.5-flash-lite')
            or event_metadata.get('apiEndpoint') != 'generateContent'
            or event_metadata.get('projectId') != 'gen-lang-client-0548563154'):
        raise ValueError('Event classification provenance does not prove Gemini Free-tier use')

    build_root = root / 'build'
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='event-taxonomy-migration-', dir=build_root) as temporary:
        staging = Path(temporary)
        staged_directory = staging / 'src/main/classification'
        staged_directory.mkdir(parents=True)
        changed_names = {
            'categories.json', 'distribution-candidates.tsv.gz', 'distribution-decisions.tsv.gz',
            'distribution-manifest.json', EVENT_CLASSIFICATIONS_PATH.split('/')[-1],
            EVENT_CLASSIFICATIONS_MANIFEST_PATH.split('/')[-1], 'reviews', 'luna-reclassification',
        }
        for entry in directory.iterdir():
            if entry.name not in changed_names:
                target = staged_directory / entry.name
                target.symlink_to(entry.resolve(), target_is_directory=entry.is_dir())

        staged_review_dir = staged_directory / 'reviews'
        staged_review_dir.mkdir()
        selected_reviews = list(current_manifest['provenance'].get('reviews', []))
        removed_review_rows = 0
        for relative in selected_reviews:
            source = root / relative
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            retained = []
            with source.open(encoding='utf-8') as stream:
                for line in stream:
                    entry = json.loads(line)
                    if (entry.get('reading'), entry.get('surface')) in excluded_pairs:
                        removed_review_rows += 1
                    else:
                        retained.append(line)
            target.write_text(''.join(retained), encoding='utf-8')

        event_data = event_taxonomy(root)
        media_data = media_demographic_taxonomy(root)
        term_data = term_taxonomy(root)
        base_taxonomy = json.loads((directory / 'categories.json').read_text(encoding='utf-8'))
        categories = merged_categories(base_taxonomy, term_data, event_data, media_data)
        write_json(staged_directory / 'categories.json', categories)
        write_gzip(staged_directory / EVENT_CLASSIFICATIONS_PATH.split('/')[-1],
                   ((*pair, classification_map[pair]) for pair in sorted(classification_map)
                    if classification_map[pair] in distributed_ids))
        write_json(staged_directory / EVENT_CLASSIFICATIONS_MANIFEST_PATH.split('/')[-1], event_metadata)

        staged_luna = staged_directory / 'luna-reclassification'
        staged_luna.mkdir()
        luna_directory = directory / 'luna-reclassification'
        luna_manifest = json.loads((luna_directory / 'manifest.json').read_text(encoding='utf-8'))
        baseline_manifest = copy.deepcopy(luna_manifest['baselineManifest'])
        baseline_candidate_path = luna_directory / 'baseline-candidates.tsv.gz'
        baseline_candidates = []
        with gzip.open(baseline_candidate_path, 'rt', encoding='utf-8') as stream:
            for line in stream:
                fields = tuple(line.rstrip('\n').split('\t'))
                if (fields[1], fields[5]) not in excluded_pairs:
                    baseline_candidates.append(fields)
        baseline_decisions_path = luna_directory / 'baseline-decisions.tsv.gz'
        baseline_decisions = {}
        with gzip.open(baseline_decisions_path, 'rt', encoding='utf-8') as stream:
            for line in stream:
                fields = line.rstrip('\n').split('\t')
                if tuple(fields[:2]) not in excluded_pairs:
                    baseline_decisions[tuple(fields[:2])] = fields
        old_baseline_decisions = luna.decisions(baseline_decisions_path)
        removed_excluded_baseline = sum(
            pair in excluded_pairs and row[4] == 'excluded'
            for pair, row in old_baseline_decisions.items())
        baseline_manifest['excludedCandidatePairs'] = max(
            0, baseline_manifest['excludedCandidatePairs'] - removed_excluded_baseline)
        baseline_manifest['excludedClassifiedPairs'] = sum(row[4] == 'excluded'
                                                           for row in baseline_decisions.values())
        baseline_manifest['unclassifiedPairs'] = sum(row[4] == 'unclassified'
                                                      for row in baseline_decisions.values())
        baseline_manifest['noResultPairs'] = sum(row[4] == 'no_result'
                                                  for row in baseline_decisions.values())
        baseline_origins = collections.Counter(row[3] for row in baseline_decisions.values()
                                               if row[4] == 'classified')
        baseline_manifest['admittedPairsByOrigin'] = dict(baseline_origins)
        baseline_manifest['uniqueAdmittedPairs'] = sum(baseline_origins.values())
        baseline_manifest['dictionaryRows'] = len(baseline_candidates)
        baseline_category_counts = collections.Counter(row[0] for row in baseline_candidates)
        baseline_manifest['categoryRows'] = {
            category: baseline_category_counts[category]
            for category in baseline_manifest['categoryRows']
        }
        baseline_manifest['provenance']['baselineVerifiedPairs'] = sum(
            row[3] == 'verified' and row[4] == 'classified' for row in baseline_decisions.values())
        current_manifest['provenance']['baselineVerifiedPairs'] = baseline_manifest[
            'provenance']['baselineVerifiedPairs']

        # Link all unchanged repository inputs and create a writable review overlay.
        for relative in set(current_manifest['inputs']) | set(baseline_manifest['inputs']) | {
                'src/main/resources/id.def'}:
            target = staging / relative
            source = root / relative
            if target.exists() or target.is_symlink() or not source.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source.resolve(), target_is_directory=source.is_dir())

        baseline_review_paths = baseline_manifest.get('provenance', {}).get('reviews', [])
        for relative in baseline_review_paths:
            if relative in baseline_manifest['inputs']:
                baseline_manifest['inputs'][relative] = sha(staging / relative)
        baseline_review_entries = reviews.load(staging, baseline_review_paths)
        baseline_review_delta = sum(
            int(entry['action'] in ('hold', 'exclude')) -
            int(entry['baseline'] is not None and entry['baseline'][4] == 'excluded')
            for entry in baseline_review_entries.values())
        if 'reviewBaseExcludedCandidatePairs' in baseline_manifest.get('provenance', {}):
            baseline_manifest['provenance']['reviewBaseExcludedCandidatePairs'] = (
                baseline_manifest['excludedCandidatePairs'] - baseline_review_delta)
            current_manifest['provenance']['reviewBaseExcludedCandidatePairs'] = baseline_manifest[
                'provenance']['reviewBaseExcludedCandidatePairs']
        for relative in selected_reviews:
            current_manifest['inputs'][relative] = sha(staging / relative)
        review_entries = luna.subsequent_reviews(staging, current_manifest, baseline_manifest)

        write_gzip(staged_luna / 'baseline-candidates.tsv.gz', sorted(baseline_candidates))
        write_gzip(staged_luna / 'baseline-decisions.tsv.gz',
                   (baseline_decisions[pair] for pair in sorted(baseline_decisions)))
        baseline_manifest['files']['distribution-candidates.tsv.gz'] = sha(
            staged_luna / 'baseline-candidates.tsv.gz')
        baseline_manifest['files']['distribution-decisions.tsv.gz'] = sha(
            staged_luna / 'baseline-decisions.tsv.gz')

        targets = luna.jsonl(luna_directory / 'targets.jsonl.gz')
        targets = [row for row in targets if (row['reading'], row['surface']) not in excluded_pairs]
        luna.write_jsonl(staged_luna / 'targets.jsonl.gz', targets)
        redacted_target_sha256 = sha(staged_luna / 'targets.jsonl.gz')
        ledger_record = current_manifest['provenance']['lunaReclassification']
        ledger_source = root / ledger_record['path']
        if not ledger_source.is_file():
            ledger_source = root / luna.LEGACY_LEDGER_PATH
        result_ledger = luna.jsonl(ledger_source)
        result_ledger = [row for row in result_ledger
                         if (row['response']['reading'], row['response']['surface']) not in excluded_pairs]
        for result in result_ledger:
            result['batch_provenance']['target_sha256'] = redacted_target_sha256
        staged_ledger = staging / luna.LOCAL_LEDGER_PATH
        luna.write_jsonl(staged_ledger, result_ledger)
        luna_manifest['baselineManifest'] = baseline_manifest
        luna_manifest['targetCount'] = len(targets)
        luna_manifest['targetCounts'] = dict(collections.Counter(row['original_status'] for row in targets))
        luna_manifest['files'] = {
            name: sha(staged_luna / name)
            for name in ('targets.jsonl.gz', 'baseline-decisions.tsv.gz', 'baseline-candidates.tsv.gz')
        }
        write_json(staged_luna / 'manifest.json', luna_manifest)

        # Continue the saved Luna ledger from the redacted baseline, then replay reviews and taxonomies.
        decisions = {pair: list(row) for pair, row in baseline_decisions.items()}
        for result in result_ledger:
            response = result['response']
            pair = response['reading'], response['surface']
            decisions[pair] = [*pair, ','.join(result['effective_categories']), 'manual',
                               'classified' if result['effective_action'] == 'adopt' else 'excluded']
        decisions = reviews.apply(decisions, review_entries)
        for batch, person_entries in luna.person_additions_after_baseline(
                staging, current_manifest, baseline_manifest):
            for reading, surface in batch['addedPairs']:
                pair = reading, surface
                if pair in decisions or pair not in person_entries:
                    raise ValueError('Person additions conflict with redacted event baseline')
                decisions[pair] = [reading, surface, 'person', 'verified', 'classified']
        decisions = apply_term_classifications(staging, decisions, force=True, reviewed_pairs=review_entries)
        decisions = apply_event_classifications(staging, decisions, force=True, reviewed_pairs=review_entries)
        # Rebuild from every selected review so additions from the pinned baseline remain present.
        all_review_entries = reviews.load(staging, selected_reviews)
        rows = reviews.candidate_rows(staging, decisions, all_review_entries)
        write_gzip(staged_directory / 'distribution-decisions.tsv.gz',
                   (decisions[pair] for pair in sorted(decisions)))
        write_gzip(staged_directory / 'distribution-candidates.tsv.gz', sorted(rows))

        manifest = current_manifest
        manifest['schemaVersion'] = 3
        manifest['categoryGroups'] = categories.get('categoryGroups', [])
        manifest['categoryRows'] = {category['id']: 0 for category in categories['categories']}
        counts_by_category = collections.Counter(row[0] for row in rows)
        manifest['categoryRows'].update({category: counts_by_category[category]
                                        for category in manifest['categoryRows']})
        for relative in (EVENT_TAXONOMY_PATH, EVENT_CLASSIFICATIONS_PATH,
                         EVENT_CLASSIFICATIONS_MANIFEST_PATH):
            manifest['inputs'][relative] = sha(staging / relative)
        manifest['provenance']['eventClassification'] = {
            key: value for key, value in event_metadata.items() if key != 'schemaVersion'
        }
        manifest['provenance']['lunaReclassification'].update({
            'path': luna.LOCAL_LEDGER_PATH,
            'snapshotManifestSha256': sha(staged_luna / 'manifest.json'),
            'sha256': sha(staged_ledger),
            'targetSha256': luna_manifest['files']['targets.jsonl.gz'],
            'completedPairs': len(result_ledger),
            'effectiveActions': dict(collections.Counter(row['effective_action'] for row in result_ledger)),
        })
        manifest['provenance']['reviewBaseExcludedCandidatePairs'] = baseline_manifest[
            'provenance'].get('reviewBaseExcludedCandidatePairs', baseline_manifest['excludedCandidatePairs'])
        reviews.update_manifest(staging, manifest, decisions, rows, selected_reviews)
        manifest['files'] = {
            name: sha(staged_directory / name)
            for name in ('categories.json', 'distribution-candidates.tsv.gz', 'distribution-decisions.tsv.gz')
        }
        write_json(staged_directory / 'distribution-manifest.json', manifest)
        try:
            verify(staging)
        except Exception as error:
            raise ValueError(f'Staged event taxonomy verification failed ({type(error).__name__})') from None

        changed_paths = [
            'src/main/classification/categories.json',
            'src/main/classification/distribution-candidates.tsv.gz',
            'src/main/classification/distribution-decisions.tsv.gz',
            'src/main/classification/distribution-manifest.json',
            EVENT_CLASSIFICATIONS_PATH, EVENT_CLASSIFICATIONS_MANIFEST_PATH,
            'src/main/classification/luna-reclassification/manifest.json',
            'src/main/classification/luna-reclassification/targets.jsonl.gz',
            'src/main/classification/luna-reclassification/baseline-candidates.tsv.gz',
            'src/main/classification/luna-reclassification/baseline-decisions.tsv.gz',
            luna.LOCAL_LEDGER_PATH,
            *selected_reviews,
        ]
        for relative in changed_paths:
            source = staging / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            pending = target.with_name(target.name + '.event-tmp')
            shutil.copyfile(source, pending)
            os.replace(pending, target)
        (root / luna.LEGACY_LEDGER_PATH).unlink(missing_ok=True)

    return {
        'uniquePairsClassified': len(classification_map),
        'categoryCounts': {category['id']: counts[category['id']] for category in classifier_categories},
        'distributionCategoryCounts': {
            category['id']: counts[category['id']] for category in classifier_categories
            if category['distribution']
        },
        'classifierOnlyCategoryCounts': {
            category['id']: counts[category['id']] for category in classifier_categories
            if not category['distribution']
        },
        'classifierOnlyPairsRemovedFromEventData': len(excluded_pairs),
        'reviewRowsRemoved': removed_review_rows,
        'distributionPairs': manifest['uniqueAdmittedPairs'],
        'distributionRecords': manifest['dictionaryRows'],
    }


def apply_term_classifications_snapshot(root):
    """Replace the frozen structural term category with its 15 Gemini leaves."""
    import shutil
    root = Path(root).resolve()
    directory = root / 'src/main/classification'
    verify(root)
    base = json.loads((directory / 'categories.json').read_text(encoding='utf-8'))
    if any(category['id'].startswith('term/') for category in base['categories']):
        raise ValueError('Term categories are already expanded')
    expanded = merged_categories(base, term_taxonomy(root),
                                 media_demographic_data=media_demographic_taxonomy(root))
    category_ids = {category['id'] for category in expanded['categories']}
    data = term_classification_data(root, category_ids)
    if data is None:
        raise ValueError('Complete Gemini term classifications are required')
    old_rows = set()
    with gzip.open(directory / 'distribution-candidates.tsv.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            old_rows.add(tuple(line.rstrip('\n').split('\t')))
    old_term_pairs = {(row[1], row[5]) for row in old_rows if row[0] == 'term'}
    if old_term_pairs != set(data['results']):
        raise ValueError('Gemini results do not cover the exact frozen term pair set')
    new_rows = set()
    for row in old_rows:
        category, reading, left, right, cost, surface = row
        if category == 'term':
            category = data['results'][(reading, surface)]
        new_rows.add((category, reading, left, right, cost, surface))
    if len(new_rows) != len(old_rows):
        raise ValueError('Term category migration changed the distribution record count')
    with gzip.open(directory / 'distribution-decisions.tsv.gz', 'rt', encoding='utf-8') as stream:
        old_decisions = {tuple(fields[:2]): fields for fields in
                         (line.rstrip('\n').split('\t') for line in stream)}
    new_decisions = apply_term_classifications(root, old_decisions, force=True)
    manifest = json.loads((directory / 'distribution-manifest.json').read_text(encoding='utf-8'))
    for path in (TERM_TAXONOMY_PATH, TERM_CLASSIFICATIONS_PATH, TERM_CLASSIFICATIONS_MANIFEST_PATH):
        manifest['inputs'][path] = sha(root / path)
    term_provenance = {key: value for key, value in data['metadata'].items()
                       if key != 'schemaVersion'}
    manifest['provenance']['termClassification'] = term_provenance
    manifest['schemaVersion'] = 2
    manifest['categoryGroups'] = expanded.get('categoryGroups', [])
    counts = collections.Counter(row[0] for row in new_rows)
    manifest['categoryRows'] = {category['id']: counts[category['id']] for category in expanded['categories']}
    manifest['dictionaryRows'] = len(new_rows)
    staging_root = root / 'build/term-classification-migration'
    staging_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='snapshot-', dir=staging_root) as temporary:
        staging = Path(temporary)
        classification = staging / 'src/main/classification'
        classification.mkdir(parents=True)
        staged_inputs = set(manifest['inputs']) | {str(Path(path)) for path, _ in SOURCES.values()}
        staged_inputs.add('src/main/resources/id.def')
        for relative in sorted(staged_inputs):
            source = root / relative
            if not source.exists():
                continue
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.symlink_to(source, target_is_directory=source.is_dir())
        if 'lunaReclassification' in manifest['provenance']:
            (classification / 'luna-reclassification').symlink_to(
                directory / 'luna-reclassification', target_is_directory=True)
        write_json(classification / 'categories.json', expanded)
        write_gzip(classification / 'distribution-candidates.tsv.gz', sorted(new_rows))
        write_gzip(classification / 'distribution-decisions.tsv.gz',
                   (new_decisions[pair] for pair in sorted(new_decisions)))
        manifest['files'] = {
            name: sha(classification / name)
            for name in ('categories.json', 'distribution-candidates.tsv.gz', 'distribution-decisions.tsv.gz')
        }
        write_json(classification / 'distribution-manifest.json', manifest)
        verify(staging)
        for name in ('categories.json', 'distribution-candidates.tsv.gz',
                     'distribution-decisions.tsv.gz', 'distribution-manifest.json'):
            temporary_path = directory / (name + '.tmp')
            shutil.copyfile(classification / name, temporary_path)
            temporary_path.replace(directory / name)
    verify(root)
    print(json.dumps({
        'term_pairs': len(data['results']),
        'term_records': sum(counts[category['id']] for category in data['categories']),
        'category_pair_counts': data['metadata']['categoryCounts'],
        'dictionary_rows': len(new_rows),
    }, ensure_ascii=False))


def source_rows(root):
    for source, (path, member) in SOURCES.items():
        if member:
            with zipfile.ZipFile(root / path) as z, z.open(member) as raw, io.TextIOWrapper(raw, encoding='utf-8') as f:
                yield from parse_rows(f, source)
        else:
            with (root / path).open(encoding='utf-8') as f:
                yield from parse_rows(f, source)
    yield from term_addition_rows(root)


def parse_rows(lines, source):
    for number, line in enumerate(lines, 1):
        row = line.rstrip('\r\n').split('\t')
        if len(row) != 5 or not row[0] or not row[4]:
            raise ValueError(f'{source}:{number}: invalid dictionary row')
        if not all(-32768 <= int(x) <= 32767 for x in row[1:4]) or any(int(x) < 0 for x in row[1:3]):
            raise ValueError(f'{source}:{number}: invalid POS/cost')
        yield source, tuple(row)


def term_addition_rows(root):
    """Read reviewed general-term additions with their source and review date."""
    path = root / TERM_ADDITIONS_PATH
    if not path.is_file():
        return
    ids = {int(line.split(maxsplit=1)[0]) for line in
           (root / 'src/main/resources/id.def').read_text(encoding='utf-8').splitlines()}
    seen = set()
    with path.open(encoding='utf-8') as f:
        for number, line in enumerate(f, 1):
            fields = line.rstrip('\r\n').split('\t')
            if len(fields) != 7:
                raise ValueError(f'{TERM_ADDITIONS_PATH}:{number}: expected seven tab-separated fields')
            parsed = next(parse_rows(['\t'.join(fields[:5])], 'term_additions'))[1]
            reading, left, right, cost, surface = parsed
            if not re.fullmatch('[ぁ-ゖー]+', reading):
                raise ValueError(f'{TERM_ADDITIONS_PATH}:{number}: invalid reading')
            if unicodedata.normalize('NFC', surface) != surface:
                raise ValueError(f'{TERM_ADDITIONS_PATH}:{number}: surface must use NFC')
            if any(int(value) not in ids for value in (left, right)):
                raise ValueError(f'{TERM_ADDITIONS_PATH}:{number}: unknown POS ID')
            source_url = urlsplit(fields[5])
            if source_url.scheme != 'https' or not source_url.hostname or source_url.username or source_url.password:
                raise ValueError(f'{TERM_ADDITIONS_PATH}:{number}: invalid source URL')
            if date.fromisoformat(fields[6]).isoformat() != fields[6]:
                raise ValueError(f'{TERM_ADDITIONS_PATH}:{number}: invalid review date')
            record = (*parsed, fields[5], fields[6])
            if record in seen:
                raise ValueError(f'{TERM_ADDITIONS_PATH}:{number}: duplicate term addition')
            seen.add(record)
            yield 'term_additions', parsed


def key(reading, surface):
    return hashlib.sha256((reading + '\0' + surface).encode()).hexdigest()


def person_dictionary_exclusions(manifest):
    value = manifest.get('provenance', {}).get('personDictionaryExclusions')
    if value is None:
        return set()
    if (not isinstance(value, dict)
            or set(value) != {'categoryIds', 'candidateKeys', 'uniquePairs'}
            or value['categoryIds'] != ['military', 'thought']
            or type(value['uniquePairs']) is not int
            or not isinstance(value['candidateKeys'], list)
            or any(not isinstance(item, str) or not re.fullmatch('[0-9a-f]{64}', item)
                   for item in value['candidateKeys'])
            or len(value['candidateKeys']) != len(set(value['candidateKeys']))
            or value['uniquePairs'] != len(value['candidateKeys'])):
        raise ValueError('Invalid person dictionary exclusion provenance')
    return set(value['candidateKeys'])


def person_reading(value):
    """Only mechanical kana normalization; never transliterate Latin names."""
    value = unicodedata.normalize('NFC', value)
    value = re.sub(r'([うウ])[\u3099\u309b]', lambda match: 'ゔ' if match[1] == 'う' else 'ヴ', value)
    return ''.join(chr(ord(c) - 0x60) if '\u30a1' <= c <= '\u30f6' else c
                   for c in value if not c.isspace() and c not in '・＝“”「」')


def person_entries(root, path):
    ids = {int(line.split(maxsplit=1)[0]) for line in
           (root / 'src/main/resources/id.def').read_text(encoding='utf-8').splitlines()}
    taxonomy_path = root / 'src/main/classification/person-taxonomy.json'
    if taxonomy_path.is_file():
        taxonomy = json.loads(taxonomy_path.read_text(encoding='utf-8'))
        allowed_sports = set(taxonomy.get('sport_subcategories', {}))
        enabled_categories = {category['id'] for category in taxonomy.get('categories', [])
                              if category.get('standard_enabled') is True}
    else:
        # Older minimal snapshots and verification fixtures predate taxonomy
        # metadata. Restrict their fallback to the original three sport IDs.
        allowed_sports = LEGACY_PERSON_SPORT_IDS
        enabled_categories = set()
    entries = {}
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        entry = json.loads(line)
        required = ('reading', 'surface', 'left_id', 'right_id', 'cost',
                    'source_url', 'source_surface', 'source_reading', 'checked_on')
        if not isinstance(entry, dict) or any(k not in entry for k in required):
            raise ValueError(f'{path}:{number}: missing person entry/evidence fields')
        if ('sport' in entry) == ('category_id' in entry):
            raise ValueError(f'{path}:{number}: expected exactly one of sport or category_id')
        for field in ('reading', 'surface', 'source_url', 'source_surface', 'source_reading', 'checked_on'):
            if not isinstance(entry[field], str) or not entry[field] or any(c in entry[field] for c in '\t\r\n\0'):
                raise ValueError(f'{path}:{number}: invalid {field}')
        if 'sport' in entry and (not isinstance(entry['sport'], str) or not entry['sport']):
            raise ValueError(f'{path}:{number}: invalid sport')
        if 'category_id' in entry:
            if (entry['category_id'] not in enabled_categories
                    or entry['category_id'] == 'sports' or 'sport' in entry):
                raise ValueError(f'{path}:{number}: invalid category-specific person evidence')
            if entry['category_id'] == 'thought':
                if (not isinstance(entry.get('classification_source_section'), str)
                        or not entry['classification_source_section']):
                    raise ValueError(f'{path}:{number}: invalid category-specific person evidence')
                category_source = urlsplit(entry.get('classification_source_url', ''))
                if (category_source.scheme != 'https' or not category_source.hostname
                        or category_source.username or category_source.password):
                    raise ValueError(f'{path}:{number}: invalid classification_source_url')
        if ('source_section' in entry and
                (not isinstance(entry['source_section'], str) or not entry['source_section'])):
            raise ValueError(f'{path}:{number}: invalid source_section')
        if ('source_sha256' in entry and
                (not isinstance(entry['source_sha256'], str)
                 or not re.fullmatch('[0-9a-f]{64}', entry['source_sha256']))):
            raise ValueError(f'{path}:{number}: invalid source_sha256')
        if (not re.fullmatch('[ぁ-ゖー]+', entry['reading'])
                or entry['reading'] != person_reading(entry['source_reading'])
                or entry['surface'] != ''.join(entry['source_surface'].split())
                or unicodedata.normalize('NFC', entry['surface']) != entry['surface']):
            raise ValueError(f'{path}:{number}: reading/surface differs from kana evidence')
        if 'sport' in entry:
            sport_tags = entry.get('sports', [entry['sport']])
            if (not isinstance(sport_tags, list) or not sport_tags
                    or any(not isinstance(sport, str) or sport not in allowed_sports
                           for sport in sport_tags)
                    or len(sport_tags) != len(set(sport_tags))
                    or entry['sport'] not in sport_tags):
                raise ValueError(f'{path}:{number}: invalid sport')
        url = urlsplit(entry['source_url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError(f'{path}:{number}: invalid evidence URL')
        if date.fromisoformat(entry['checked_on']).isoformat() != entry['checked_on']:
            raise ValueError(f'{path}:{number}: invalid confirmation date')
        if (any(type(entry[k]) is not int or entry[k] not in ids or not 0 < entry[k] <= 32767
                for k in ('left_id', 'right_id'))
                or type(entry['cost']) is not int or not -32768 <= entry['cost'] <= 32767):
            raise ValueError(f'{path}:{number}: invalid POS/cost')
        pair = entry['reading'], entry['surface']
        if pair in entries and entries[pair] != entry:
            raise ValueError(f'{path}:{number}: conflicting duplicate person entry')
        entries[pair] = entry
    if not entries:
        raise ValueError('Empty person entries')
    return entries


def add_person_names(root, path):
    """Add reviewed names to the frozen snapshot without reopening AI history."""
    root = root.resolve()
    path = path.resolve()
    relative = str(path.relative_to(root))  # Evidence must remain available in a clean checkout.
    if not relative.startswith('src/main/classification/') or path.suffix != '.jsonl':
        raise ValueError('Person entries must be a JSONL file under src/main/classification')
    verify(root)
    entries = person_entries(root, path)
    directory = root / 'src/main/classification'
    category_additions = dict(entries)
    person_dictionary_path = directory / 'person-dictionary-candidates.tsv.gz'
    manifest = json.loads((directory / 'distribution-manifest.json').read_text())
    with gzip.open(directory / 'distribution-decisions.tsv.gz', 'rt', encoding='utf-8') as f:
        decisions = {tuple(row[:2]): row for row in (line.rstrip('\n').split('\t') for line in f)}
    with gzip.open(directory / 'distribution-candidates.tsv.gz', 'rt', encoding='utf-8') as f:
        rows = {tuple(line.rstrip('\n').split('\t')) for line in f}
    sources_by_pair = collections.defaultdict(set)
    names_rows = set()
    for source, row in source_rows(root):
        sources_by_pair[(row[0], row[4])].add(row)
        if source == 'person': names_rows.add(row)
    additions = []
    appended = []
    already_admitted_person_pairs = set()
    previous_rows = len(rows)
    for pair, entry in sorted(entries.items()):
        prior = decisions.get(pair)
        if prior is not None:
            if prior[4] == 'classified' and 'person' in prior[2].split(','):
                already_admitted_person_pairs.add(pair)
                continue
            raise ValueError(f'Existing classification/exclusion conflicts with person entry: {pair}')
        row = (pair[0], str(entry['left_id']), str(entry['right_id']), str(entry['cost']), pair[1])
        additions.append(row)
        if row not in names_rows: appended.append(row)
        # A previously undecided pair may already have several source POS/cost variants.
        # Admit those unchanged as well, as required by the source-to-distribution verifier.
        rows.update(('person', *existing) for existing in sources_by_pair[pair] | {row})
        decisions[pair] = [*pair, 'person', 'verified', 'classified']
    category_row_records = set()
    already_categorized_pairs = set()
    categorized_rows = None
    if category_additions:
        if not person_dictionary_path.is_file():
            raise ValueError('Category additions require the existing person dictionary snapshot')
        with gzip.open(person_dictionary_path, 'rt', encoding='utf-8') as stream:
            categorized_rows = {tuple(line.rstrip('\n').split('\t')) for line in stream}
        for pair, entry in category_additions.items():
            variants = set(sources_by_pair[pair])
            if pair not in already_admitted_person_pairs:
                variants.add((pair[0], str(entry['left_id']), str(entry['right_id']),
                              str(entry['cost']), pair[1]))
            category_id = 'sports' if 'sport' in entry else entry['category_id']
            sport_ids = sorted(entry.get('sports', [entry['sport']])) if 'sport' in entry else []
            expected_rows = {(category_id, *variant, ','.join(sport_ids)) for variant in variants}
            if not expected_rows:
                raise ValueError(f'No person dictionary source rows exist for category addition: {pair}')
            existing = {row for row in categorized_rows
                        if len(row) in (6, 7) and row[0] in (category_id, 'personal_name_origin_unconfirmed')
                        and (row[1], row[5]) == pair}
            legacy_rows = {row for row in existing if row[0] == category_id and len(row) == 6}
            categorized_rows.difference_update(legacy_rows)
            existing.difference_update(legacy_rows)
            target_rows = {row for row in existing if row[0] == category_id}
            if pair in already_admitted_person_pairs and target_rows:
                if not expected_rows <= target_rows:
                    raise ValueError(f'Existing person category does not cover source rows: {pair}')
                already_categorized_pairs.add(pair)
                continue
            if existing and existing != expected_rows:
                if {row[0] for row in existing} != {'personal_name_origin_unconfirmed'}:
                    raise ValueError(f'Person dictionary category conflicts with category addition: {pair}')
                categorized_rows.difference_update(existing)
            category_row_records.update(expected_rows)
            categorized_rows.update(expected_rows)
        category_additions = {
            pair: entry for pair, entry in category_additions.items()
            if pair not in already_categorized_pairs
        }
    if not additions and not category_additions:
        print('Person additions: 0 (all names already admitted)')
        return
    if any(item['path'] == relative for item in manifest['provenance'].get('personAdditions', [])):
        raise ValueError('Use a new evidence file for a subsequent person addition batch')
    names_path = SOURCES['person'][0]
    names = (root / names_path).read_text(encoding='utf-8')
    if names and not names.endswith('\n'):
        names += '\n'
    names += ''.join('\t'.join(row) + '\n' for row in appended)
    count = len(additions)
    record_count = len(rows) - previous_rows
    manifest['sourceRows']['person'] += len(appended)
    manifest['admittedPairsByOrigin']['verified'] = manifest['admittedPairsByOrigin'].get('verified', 0) + count
    manifest['uniqueAdmittedPairs'] += count
    manifest['categoryRows']['person'] += record_count
    manifest['dictionaryRows'] += record_count
    manifest['inputs'][relative] = sha(path)
    taxonomy_path = 'src/main/classification/person-taxonomy.json'
    taxonomy_file = root / taxonomy_path
    if taxonomy_file.is_file():
        manifest['inputs'][taxonomy_path] = sha(taxonomy_file)
    manifest['provenance'].setdefault('personAdditions', []).append({
        'path': relative, 'sha256': sha(path), 'reviewedPairs': len(entries),
        'addedPairs': [[row[0], row[4]] for row in additions], 'addedRecords': record_count,
        'addedSourceRows': len(appended),
        'appendedPairs': [[row[0], row[4]] for row in appended],
        'categoryPairs': [['sports' if 'sport' in entry else entry['category_id'], pair[0], pair[1]]
                          for pair, entry in sorted(category_additions.items())],
        'categoryRecords': len(category_row_records),
    })
    # Validate a staged snapshot first. Invalid batches never partially edit the inputs.
    with tempfile.TemporaryDirectory(prefix='person-additions-') as temporary:
        staging = Path(temporary)
        staged_directory = staging / 'src/main/classification'
        staged_directory.mkdir(parents=True)
        staged_paths = list(dict.fromkeys([
            *manifest['inputs'], 'src/main/resources/id.def',
            'src/main/classification/categories.json']))
        if taxonomy_file.is_file() and taxonomy_path not in staged_paths:
            staged_paths.append(taxonomy_path)
        person_dictionary_relative = 'src/main/classification/person-dictionary-candidates.tsv.gz'
        if person_dictionary_path.is_file() and person_dictionary_relative not in staged_paths:
            staged_paths.append(person_dictionary_relative)
        for relative_path in staged_paths:
            target = staging / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative_path != names_path:
                target.symlink_to(root / relative_path)
        (staging / names_path).write_text(names, encoding='utf-8')
        write_gzip(staged_directory / 'distribution-candidates.tsv.gz', sorted(rows))
        write_gzip(staged_directory / 'distribution-decisions.tsv.gz', (decisions[pair] for pair in sorted(decisions)))
        if category_additions:
            write_gzip(staged_directory / 'person-dictionary-candidates.tsv.gz', sorted(categorized_rows))
        if 'lunaReclassification' in manifest['provenance']:
            (staged_directory / 'luna-reclassification').symlink_to(
                directory / 'luna-reclassification', target_is_directory=True)
        manifest['inputs'][names_path] = sha(staging / names_path)
        for filename in manifest['files']:
            manifest['files'][filename] = sha(staged_directory / filename)
        write_json(staged_directory / 'distribution-manifest.json', manifest)
        verify(staging)
        for relative_path in [names_path, 'src/main/classification/distribution-candidates.tsv.gz',
                              'src/main/classification/distribution-decisions.tsv.gz',
                              'src/main/classification/distribution-manifest.json']:
            (root / relative_path).write_bytes((staging / relative_path).read_bytes())
        if category_additions:
            person_dictionary_path.write_bytes(
                (staged_directory / 'person-dictionary-candidates.tsv.gz').read_bytes())
    print(f'Person additions: {count} new pairs, {record_count} records, {len(entries) - count} already admitted')


def freeze(root, accepted, dispositions, database, manual, taxonomy):
    out = root / 'src/main/classification'
    out.mkdir(parents=True, exist_ok=True)
    prior_manifest_path = out / 'distribution-manifest.json'
    prior_manifest = json.loads(prior_manifest_path.read_text()) if prior_manifest_path.exists() else {}
    prior_batches = prior_manifest.get('provenance', {}).get('personAdditions', [])
    person_exclusions = person_dictionary_exclusions(prior_manifest)
    term_tax = term_taxonomy(root)
    event_tax = event_taxonomy(root)
    media_demographic_tax = media_demographic_taxonomy(root)
    term_data = term_classification_data(root)
    event_data = event_classification_data(root)
    categories = merged_categories(json.loads(taxonomy.read_text()), term_tax,
                                   event_tax if event_data is not None else None,
                                   media_demographic_tax)
    allowed = {c['id'] for c in categories['categories']}
    term_data = term_classification_data(root, allowed)
    event_data = event_classification_data(root, allowed)
    if term_taxonomy(root) is not None and term_data is None:
        raise ValueError('Cannot freeze expanded term categories without complete Gemini results')
    if event_taxonomy(root) is not None and event_data is None and not any(
            category['id'] == 'event' for category in json.loads(taxonomy.read_text())['categories']):
        raise ValueError('Cannot freeze expanded event categories without complete Gemini results')
    decisions = {}
    excluded = set()
    with gzip.open(dispositions, 'rt') as f:
        for line in f:
            row = line.rstrip('\n').split('\t')
            if row[0] == 'excluded':
                excluded.add((row[3], row[4]))
    with gzip.open(accepted, 'rt') as f:
        for line in f:
            row = line.rstrip('\n').split('\t')
            pair = (row[2], row[6])
            decisions.setdefault(pair, (set(), 'verified'))[0].add(row[0])
    verified = len(decisions)
    snapshot_hash = hashlib.sha256()
    conflicts = collections.Counter()
    # One read transaction: concurrent source reviews cannot split the snapshot.
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as con:
        con.execute('BEGIN')
        for table in ('candidates', 'references_data'):
            for data, in con.execute(f'SELECT data FROM {table} ORDER BY k'):
                snapshot_hash.update((data + '\n').encode())
                row = json.loads(data)
                pair = (row['reading'], row['surface'])
                if row['candidate_key'] != key(*pair):
                    raise ValueError(f'Invalid candidate key: {pair}')
                certified = row.get('source_validated_categories')
                if certified and row.get('independent_reading_confirmed'):
                    cats, origin = set(certified), 'verified'
                else:
                    history = [x for x in row.get('history', []) if x.get('model', '').lower().startswith('gemini')]
                    if not history:
                        if row.get('processing_state') == 'attempted_no_result':
                            decisions.setdefault(pair, (set(), 'no_result'))
                        continue
                    cats, origin = set(history[-1]['proposal']['categories']), 'gemini'
                if pair in decisions and decisions[pair][1] == 'verified':
                    if cats != decisions[pair][0]:
                        conflicts['verified_over_gemini'] += 1
                else:
                    decisions[pair] = (cats, origin)
        con.commit()
    manual_count = 0
    with manual.open() as manual_stream:
        for line in manual_stream:
            row = json.loads(line)
            pair = (row['reading'], row['surface'])
            if row['candidate_key'] != key(*pair):
                raise ValueError(f'Invalid manual candidate key: {pair}')
            manual_count += 1
            cats = set(row['categories'])
            prior = decisions.get(pair)
            if prior and prior[1] == 'verified':
                if cats != prior[0]:
                    conflicts['verified_over_manual'] += 1
            else:
                if prior and prior[0] != cats:
                    conflicts['manual_over_gemini'] += 1
                decisions[pair] = (cats, 'manual')
    term_additions = [row for _, row in term_addition_rows(root)]
    for row in term_additions:
        pair = (row[0], row[4])
        if pair in excluded:
            raise ValueError(f'Term addition conflicts with an exclusion: {pair}')
        prior = decisions.get(pair)
        if prior and prior[0]:
            if 'term' not in prior[0]:
                raise ValueError(f'Term addition conflicts with an existing classification: {pair}')
            raise ValueError(f'Term addition is already classified: {pair}')
        decisions[pair] = ({'term'}, 'verified')
    # Preserve independently reviewed later additions when rebuilding the older
    # AI snapshot, before applying hold/restoration overlays to their baselines.
    for batch in prior_batches:
        path = root / batch['path']
        if sha(path) != batch['sha256']:
            raise ValueError('Person addition evidence changed: ' + batch['path'])
        reviewed_people = person_entries(root, path)
        for pair in map(tuple, batch['addedPairs']):
            if pair not in reviewed_people:
                raise ValueError('Person addition pair missing from evidence')
            decisions[pair] = ({'person'}, 'verified')
    matched = set()
    source_counts = collections.Counter()
    for source, row in source_rows(root):
        pair = (row[0], row[4])
        source_counts[source] += 1
        if pair not in decisions:
            continue
        matched.add(pair)
        cats, origin = decisions[pair]
        source_allowed = allowed | ({'term'} if term_data is not None else set()) \
            | ({'event'} if event_data is not None else set())
        if not cats <= source_allowed:
            raise ValueError(f'Unknown categories for {pair}: {cats - source_allowed}')
    if decisions.keys() - matched:
        raise ValueError(f'Classifications missing from source dictionaries: {len(decisions.keys() - matched)}')
    import classification_reviews as reviews
    baseline = {pair: [*pair, ','.join(sorted(cats)), origin,
                      'excluded' if pair in excluded else 'classified' if cats else
                      'no_result' if origin == 'no_result' else 'unclassified']
                for pair, (cats, origin) in decisions.items()}
    review_paths = reviews.paths(root)
    review_entries = reviews.load(root) if review_paths else {}
    reviewed = reviews.apply(baseline, review_entries) if review_paths else baseline
    reviewed = apply_term_classifications(root, reviewed, force=term_data is not None,
                                          reviewed_pairs=review_entries)
    reviewed = apply_event_classifications(root, reviewed, force=event_data is not None,
                                           reviewed_pairs=review_entries)
    for pair in list(reviewed):
        if key(*pair) in person_exclusions:
            row = reviewed[pair]
            remaining = set(filter(None, row[2].split(','))) - {'person'}
            if remaining:
                row[2] = ','.join(sorted(remaining))
            else:
                del reviewed[pair]
    rows = reviews.candidate_rows(root, reviewed, review_entries)
    (out / 'categories.json').write_text(json.dumps(categories, ensure_ascii=False, indent=2) + '\n')
    write_gzip(out / 'distribution-candidates.tsv.gz', sorted(rows))
    write_gzip(out / 'distribution-decisions.tsv.gz', (reviewed[pair] for pair in sorted(reviewed)))
    admitted = collections.Counter(row[3] for row in reviewed.values() if row[4] == 'classified')
    category_counts = collections.Counter(row[0] for row in rows)
    inputs = {path: sha(root / path) for path, _ in SOURCES.values()}
    if media_demographic_tax is not None:
        inputs[MEDIA_DEMOGRAPHIC_TAXONOMY_PATH] = sha(root / MEDIA_DEMOGRAPHIC_TAXONOMY_PATH)
    term_classification_provenance = None
    if term_data is not None:
        for path in (TERM_TAXONOMY_PATH, TERM_CLASSIFICATIONS_PATH, TERM_CLASSIFICATIONS_MANIFEST_PATH):
            inputs[path] = sha(root / path)
        term_classification_provenance = {
            key: value for key, value in term_data['metadata'].items()
            if key not in ('schemaVersion', 'categoryCounts', 'freeTierProofs')
        }
        term_classification_provenance['categoryCounts'] = term_data['metadata']['categoryCounts']
        term_classification_provenance['freeTierProofs'] = term_data['metadata']['freeTierProofs']
    event_classification_provenance = None
    if event_data is not None:
        for path in (EVENT_TAXONOMY_PATH, EVENT_CLASSIFICATIONS_PATH,
                     EVENT_CLASSIFICATIONS_MANIFEST_PATH):
            inputs[path] = sha(root / path)
        event_classification_provenance = {
            key: value for key, value in event_data['metadata'].items()
            if key != 'schemaVersion'
        }
    term_addition_provenance = []
    if (root / TERM_ADDITIONS_PATH).is_file():
        inputs[TERM_ADDITIONS_PATH] = sha(root / TERM_ADDITIONS_PATH)
        if term_additions:
            term_addition_provenance.append({
                'path': TERM_ADDITIONS_PATH,
                'sha256': inputs[TERM_ADDITIONS_PATH],
                'pairs': [list(pair) for pair in sorted({(row[0], row[4]) for row in term_additions})],
            })
    manifest = {
        'schemaVersion': 3 if event_data is not None else 2 if term_data is not None else 1,
        'precedence': ['verified', 'manual', 'gemini'],
        'provenance': {
            'acceptedSha256': sha(accepted), 'dispositionsSha256': sha(dispositions),
            'databaseReadSnapshotSha256': snapshot_hash.hexdigest(), 'manualSha256': sha(manual),
            'manualCandidates': manual_count, 'baselineVerifiedPairs': verified,
            'termAdditions': term_addition_provenance,
        },
        'inputs': inputs,
        'files': {name: sha(out / name) for name in ('categories.json', 'distribution-candidates.tsv.gz', 'distribution-decisions.tsv.gz')},
        'categoryGroups': categories.get('categoryGroups', []),
        'idDefSha256': sha(root / 'src/main/resources/id.def'),
        'sourceRows': dict(source_counts),
        'admittedPairsByOrigin': dict(admitted),
        'uniqueAdmittedPairs': sum(admitted.values()),
        'excludedCandidatePairs': len(excluded),
        'excludedClassifiedPairs': sum(row[4] == 'excluded' for row in reviewed.values()),
        'unclassifiedPairs': sum(row[4] == 'unclassified' for row in reviewed.values()),
        'noResultPairs': sum(row[4] == 'no_result' for row in reviewed.values()),
        'conflicts': dict(conflicts),
        'categoryRows': {c['id']: category_counts[c['id']] for c in categories['categories']},
        'dictionaryRows': len(rows),
        'limitations': ['Gemini and manual classifications include provisional categories and unverified readings. IME runtime behavior is not verified.'],
    }
    if media_demographic_tax is not None:
        manifest['limitations'].append(MEDIA_DEMOGRAPHIC_LIMITATION)
    if term_classification_provenance is not None:
        manifest['provenance']['termClassification'] = term_classification_provenance
    if event_classification_provenance is not None:
        manifest['provenance']['eventClassification'] = event_classification_provenance
    if person_exclusions:
        manifest['provenance']['personDictionaryExclusions'] = {
            'categoryIds': ['military', 'thought'],
            'candidateKeys': sorted(person_exclusions),
            'uniquePairs': len(person_exclusions),
        }
    if prior_batches:
        manifest['provenance']['personAdditions'] = prior_batches
        manifest['inputs'].update({batch['path']: batch['sha256'] for batch in prior_batches})
    if review_paths:
        reviews.update_manifest(root, manifest, reviewed, rows, review_paths)
    write_json(out / 'distribution-manifest.json', manifest)
    print(json.dumps({k: manifest[k] for k in ('uniqueAdmittedPairs', 'admittedPairsByOrigin', 'dictionaryRows', 'unclassifiedPairs')}, ensure_ascii=False))


def verify(root, allow_pending_reviews=False):
    import classification_reviews as reviews
    directory = root / 'src/main/classification'
    manifest = json.loads((directory / 'distribution-manifest.json').read_text())
    selected_reviews = manifest['provenance'].get('reviews', [])
    person_exclusions = person_dictionary_exclusions(manifest)
    if not allow_pending_reviews and selected_reviews != reviews.paths(root):
        raise ValueError('Review history changed: run apply-reviews before building')
    for path, expected in manifest['inputs'].items():
        if sha(root / path) != expected:
            raise ValueError(f'Input hash mismatch: {path}')
    for name, expected in manifest['files'].items():
        if allow_pending_reviews and name == 'categories.json':
            continue
        if sha(directory / name) != expected:
            raise ValueError(f'Classification hash mismatch: {name}')
    if sha(root / 'src/main/resources/id.def') != manifest['idDefSha256']:
        raise ValueError('id.def changed: regenerate and review distribution input')
    categories = [c['id'] for c in json.loads((directory / 'categories.json').read_text())['categories']]
    review_entries = reviews.load(root, selected_reviews)
    if len(categories) != len(set(categories)) or not categories:
        raise ValueError('Expected unique category IDs')
    expanded_terms = any(category.startswith('term/') for category in categories)
    term_data = term_classification_data(root, set(categories)) if expanded_terms else None
    expanded_events = any(category.startswith('event/') for category in categories)
    event_data = event_classification_data(root, set(categories)) if expanded_events else None
    expanded_demographics = any(category.startswith('media_demographic/') for category in categories)
    media_demographic_data = media_demographic_taxonomy(root, set(categories)) if expanded_demographics else None
    if expanded_demographics and media_demographic_data is None:
        raise ValueError('Expanded media demographic categories require their taxonomy')
    if media_demographic_data is not None and not allow_pending_reviews:
        if manifest['inputs'].get(MEDIA_DEMOGRAPHIC_TAXONOMY_PATH) != sha(root / MEDIA_DEMOGRAPHIC_TAXONOMY_PATH):
            raise ValueError('Media demographic taxonomy is absent from distribution inputs')
        if MEDIA_DEMOGRAPHIC_LIMITATION not in manifest.get('limitations', []):
            raise ValueError('Media demographic review coverage limitation is absent from the manifest')
    saved_taxonomy = json.loads((directory / 'categories.json').read_text(encoding='utf-8'))
    if term_data is not None:
        if manifest.get('schemaVersion') not in (2, 3):
            raise ValueError('Expanded term categories require distribution manifest schema 2 or 3')
    if expanded_events and event_data is None:
        raise ValueError('Expanded event categories require complete Gemini classifications')
    if event_data is not None and manifest.get('schemaVersion') != 3:
        raise ValueError('Expanded event categories require distribution manifest schema 3')
    if term_data is not None or event_data is not None or media_demographic_data is not None:
        expected_groups = []
        groups = []
        if event_data is not None:
            groups.append((min(categories.index(category['id']) for category in event_data['categories']),
                           event_data['taxonomy']))
        if term_data is not None:
            groups.append((min(categories.index(category['id']) for category in term_data['categories']),
                           term_data['taxonomy']))
        if media_demographic_data is not None:
            groups.append((min(categories.index(category['id']) for category in media_demographic_data[1]),
                           media_demographic_data[0]))
        expected_groups = [group for _, group in sorted(groups, key=lambda item: item[0])]
        if (not allow_pending_reviews and (saved_taxonomy.get('categoryGroups') != expected_groups
                or manifest.get('categoryGroups') != expected_groups)):
            raise ValueError('Classified dictionary category hierarchy differs from its taxonomy')
    decisions = {}
    decision_status = {}
    decision_rows = {}
    origins = collections.Counter()
    excluded = unclassified = no_result = 0
    with gzip.open(directory / 'distribution-decisions.tsv.gz', 'rt') as f:
        for line in f:
            reading, surface, cats, origin, status = line.rstrip('\n').split('\t')
            pair = (reading, surface)
            if pair in decisions or origin not in [*manifest['precedence'], 'no_result']:
                raise ValueError('Duplicate decision or invalid origin')
            values = set(cats.split(',')) if cats else set()
            if (key(reading, surface) in person_exclusions
                    and ('person' in values or not values)):
                raise ValueError('Withheld person dictionary pair appears in frozen decisions')
            allowed = set(categories) | ({'term', 'event'} if status == 'excluded' else set())
            if not values <= allowed or status not in ('excluded', 'classified', 'unclassified', 'no_result'):
                raise ValueError('Invalid decision')
            if (status == 'classified' and not values or status in ('unclassified', 'no_result') and values
                    or origin == 'no_result' and status not in ('no_result', 'excluded')
                    or status == 'no_result' and origin != 'no_result'):
                raise ValueError('Invalid classification status')
            decisions[pair] = values if status == 'classified' else set()
            decision_status[pair] = (origin, status)
            decision_rows[pair] = [reading, surface, cats, origin, status]
            if status == 'classified': origins[origin] += 1
            if status == 'excluded': excluded += 1
            if status == 'unclassified': unclassified += 1
            if status == 'no_result': no_result += 1
    expected = set()
    matched = set()
    source_counts = collections.Counter()
    for source, row in source_rows(root):
        source_counts[source] += 1
        pair = (row[0], row[4])
        if pair in decisions:
            matched.add(pair)
            expected.update((cat, *row) for cat in decisions[pair])
    if decisions.keys() - matched:
        added_pairs = {(r[0], r[4]) for r in reviews.added_rows(review_entries)}
        if decisions.keys() - matched - added_pairs:
            raise ValueError('Decision missing from dictionary sources')
    for row in reviews.added_rows(review_entries):
        expected.update((cat, *row) for cat in decisions[(row[0], row[4])])
    baseline_decisions = reviews.restore(decision_rows, review_entries)
    replayed_decisions = reviews.apply(baseline_decisions, review_entries)
    replayed_decisions = apply_term_classifications(root, replayed_decisions, force=term_data is not None,
                                                    reviewed_pairs=review_entries)
    replayed_decisions = apply_event_classifications(root, replayed_decisions, force=event_data is not None,
                                                     reviewed_pairs=review_entries)
    for pair in list(replayed_decisions):
        if key(*pair) in person_exclusions:
            row = replayed_decisions[pair]
            remaining = set(filter(None, row[2].split(','))) - {'person'}
            if remaining:
                row[2] = ','.join(sorted(remaining))
            else:
                del replayed_decisions[pair]
    if replayed_decisions != decision_rows:
        raise ValueError('Frozen decisions differ from saved review history')
    actual = set()
    with gzip.open(directory / 'distribution-candidates.tsv.gz', 'rt') as f:
        for line in f:
            row = tuple(line.rstrip('\n').split('\t'))
            if len(row) != 6 or row in actual:
                raise ValueError('Invalid or duplicate distribution row')
            actual.add(row)
    if actual != expected:
        raise ValueError(f'Distribution differs from sources: missing={len(expected-actual)}, extra={len(actual-expected)}')
    adult_pairs = {pair for pair, entry in review_entries.items()
                   if entry.get('media_demographic') == 'adult'}
    if (any(pair not in decision_rows or decision_rows[pair][4] != 'excluded' for pair in adult_pairs)
            or any((row[1], row[5]) in adult_pairs for row in actual)):
        raise ValueError('Adult-classified media must be excluded from every dictionary category')
    term_additions = [row for _, row in term_addition_rows(root)]
    term_pairs = sorted({(row[0], row[4]) for row in term_additions})
    expected_term_provenance = ([{
        'path': TERM_ADDITIONS_PATH,
        'sha256': sha(root / TERM_ADDITIONS_PATH),
        'pairs': [list(pair) for pair in term_pairs],
    }] if term_pairs else [])
    if manifest['provenance'].get('termAdditions', []) != expected_term_provenance:
        raise ValueError('Term addition provenance differs from input')
    for pair in term_pairs:
        pair_categories = decisions.get(pair, set())
        term_membership = bool(pair_categories & (term_data['categoryIds'] if term_data else {'term'}))
        if (not term_membership or decision_status.get(pair) != ('verified', 'classified')):
            raise ValueError(f'Term addition is not classified in term: {pair}')
    categorized_person_rows = None
    for batch in manifest['provenance'].get('personAdditions', []):
        if manifest['inputs'].get(batch['path']) != batch['sha256']:
            raise ValueError('Person evidence hash differs from recorded input')
        reviewed = person_entries(root, root / batch['path'])
        pairs = {tuple(pair) for pair in batch['addedPairs']}
        baseline_person_pairs = {pair for pair, row in baseline_decisions.items()
                                 if row[3:] == ['verified', 'classified'] and 'person' in row[2].split(',')}
        baseline_person_rows = {('person', *row) for _, row in source_rows(root)
                                if (row[0], row[4]) in pairs and (row[0], row[4]) in baseline_person_pairs}
        if (len(pairs) != len(batch['addedPairs'])
                or len(baseline_person_rows) != batch['addedRecords']
                or len(reviewed) != batch['reviewedPairs'] or not pairs <= reviewed.keys()
                or not pairs <= baseline_person_pairs):
            raise ValueError('Person addition provenance differs from decisions')
        for pair in pairs:
            entry = reviewed[pair]
            if ('person', pair[0], str(entry['left_id']), str(entry['right_id']), str(entry['cost']), pair[1]) not in baseline_person_rows:
                raise ValueError(f'Person addition differs from reviewed POS/cost: {pair}')
        category_pairs = batch.get('categoryPairs', [])
        category_records = batch.get('categoryRecords', 0)
        if (not isinstance(category_pairs, list)
                or any(not isinstance(pair, list) or len(pair) != 3
                       or any(not isinstance(value, str) for value in pair)
                       for pair in category_pairs)
                or type(category_records) is not int
                or category_records < 0):
            raise ValueError('Person category-addition provenance is invalid')
        if len(category_pairs) != len({tuple(pair) for pair in category_pairs}):
            raise ValueError('Person category-addition provenance contains duplicates')
        if category_pairs and categorized_person_rows is None:
            candidate_path = directory / 'person-dictionary-candidates.tsv.gz'
            if not candidate_path.is_file():
                raise ValueError('Person category additions require the categorized person dictionary')
            with gzip.open(candidate_path, 'rt', encoding='utf-8') as stream:
                categorized_person_rows = {tuple(line.rstrip('\n').split('\t')) for line in stream}
        for category_id, reading, surface in category_pairs:
            entry = reviewed.get((reading, surface))
            entry_category = 'sports' if entry and 'sport' in entry else entry.get('category_id') if entry else None
            if entry is None or entry_category != category_id:
                raise ValueError('Person category-addition provenance differs from evidence')
        category_by_pair = {(reading, surface): category_id
                            for category_id, reading, surface in category_pairs}
        category_tags = {
            pair: ','.join(sorted(entry.get('sports', [entry['sport']]))) if 'sport' in entry else ''
            for pair, entry in reviewed.items() if pair in category_by_pair
        }
        category_pair_keys = set(category_by_pair)
        expected_category_rows = {
            (category_by_pair[(row[1], row[5])], *row[1:], category_tags[(row[1], row[5])]) for row in actual
            if row[0] == 'person' and (row[1], row[5]) in category_by_pair
        }
        expected_category_pairs = {(row[1], row[5]) for row in expected_category_rows}
        if (category_records != len(expected_category_rows)
                or category_pair_keys != expected_category_pairs
                or (category_pairs and not expected_category_rows <= categorized_person_rows)):
            raise ValueError('Person category additions differ from dictionary candidates')
    counts = collections.Counter(row[0] for row in actual)
    expected_category_rows = ({c: counts[c] for c in manifest['categoryRows']} if allow_pending_reviews
                              else {c: counts[c] for c in categories})
    if (expected_category_rows != manifest['categoryRows'] or len(actual) != manifest['dictionaryRows']
            or dict(origins) != manifest['admittedPairsByOrigin'] or sum(origins.values()) != manifest['uniqueAdmittedPairs']
            or dict(source_counts) != manifest['sourceRows']
            or excluded != manifest['excludedClassifiedPairs'] or unclassified != manifest['unclassifiedPairs'] or no_result != manifest['noResultPairs']):
        raise ValueError('Manifest counts mismatch')
    if term_data is not None:
        for category, expected_count in term_data['metadata']['categoryCounts'].items():
            if category not in term_data['categoryIds'] or type(expected_count) is not int or expected_count < 0:
                raise ValueError('Invalid term category count in classifier provenance')
        expected_term_provenance = {key: value for key, value in term_data['metadata'].items()
                                    if key != 'schemaVersion'}
        if manifest['provenance'].get('termClassification') != expected_term_provenance:
            raise ValueError('Gemini term classification provenance differs from its manifest')
        source_pairs = {(row[0], row[4]) for _, row in source_rows(root)}
        if term_data['results'].keys() - source_pairs:
            raise ValueError('Gemini term classification contains pairs absent from dictionary sources')
    elif 'termClassification' in manifest['provenance']:
        raise ValueError('Term classification provenance exists without expanded term categories')
    if event_data is not None:
        for category, expected_count in event_data['metadata']['categoryCounts'].items():
            if category not in event_data['taxonomyIds'] or type(expected_count) is not int or expected_count < 0:
                raise ValueError('Invalid event category count in classifier provenance')
        expected_event_provenance = {key: value for key, value in event_data['metadata'].items()
                                     if key != 'schemaVersion'}
        if manifest['provenance'].get('eventClassification') != expected_event_provenance:
            raise ValueError('Gemini event classification provenance differs from its manifest')
        source_pairs = {(row[0], row[4]) for _, row in source_rows(root)}
        if event_data['results'].keys() - source_pairs:
            raise ValueError('Gemini event classification contains pairs absent from dictionary sources')
    elif 'eventClassification' in manifest['provenance']:
        raise ValueError('Event classification provenance exists without expanded event categories')
    import luna_reclassification
    ledger_verified = luna_reclassification.verify_ledger(root)
    ledger_status = 'Luna ledger verified' if ledger_verified else 'local Luna ledger unavailable; audit skipped'
    print(f'Verified frozen distribution: {len(actual)} rows, {sum(origins.values())} pairs, '
          f'{len(categories)} categories; {ledger_status}')


def release_manifest(root, archive, revision):
    source = json.loads((root / 'src/main/classification/distribution-manifest.json').read_text())
    with zipfile.ZipFile(archive) as z:
        assets = {name: hashlib.sha256(z.read(name)).hexdigest() for name in sorted(z.namelist()) if not name.endswith('/')}
    import specialist_distribution as specialist
    specialist_manifest = specialist.verify_files(root)
    license_file = archive.parent / 'DICTIONARY-LICENSES.txt'
    license_file.write_text(specialist.licenses(root), encoding='utf-8')
    result = {'schemaVersion': 2, 'revision': revision, 'classification': source,
              'specialist': specialist_manifest, 'categoryCount': len(source['categoryRows']) + len(specialist_manifest['categoryRows']),
              'licensesSha256': sha(license_file),
              'archiveSha256': sha(archive), 'assets': assets}
    output = archive.parent / 'dictionary-distribution-manifest.json'
    write_json(output, result)
    (archive.parent / 'DICTIONARY-SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in (archive, output, license_file)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['freeze', 'verify', 'release-manifest', 'add-person-names',
                                       'apply-reviews', 'recover-reviews', 'apply-term-classifications'])
    p.add_argument('--commit', action='store_true', help='Apply reviewed data; otherwise show a dry-run summary')
    p.add_argument('--root', type=Path, default=Path('.'))
    for name in ('accepted', 'dispositions', 'database', 'manual', 'taxonomy', 'archive', 'entries'):
        p.add_argument('--' + name, type=Path)
    p.add_argument('--revision', default='local')
    args = p.parse_args()
    if args.command == 'freeze':
        for name in ('accepted', 'dispositions', 'database', 'manual', 'taxonomy'):
            if getattr(args, name) is None: p.error('--' + name + ' is required')
        freeze(args.root, args.accepted, args.dispositions, args.database, args.manual, args.taxonomy)
    elif args.command == 'verify':
        verify(args.root)
    elif args.command == 'add-person-names':
        if args.entries is None: p.error('--entries is required')
        add_person_names(args.root, args.entries)
    elif args.command == 'apply-reviews':
        import classification_reviews as reviews
        reviews.apply_saved(args.root, commit=args.commit)
    elif args.command == 'recover-reviews':
        import classification_reviews as reviews
        reviews.recover(args.root)
    elif args.command == 'apply-term-classifications':
        apply_term_classifications_snapshot(args.root)
    else:
        release_manifest(args.root, args.archive or args.root / 'release_zips/japanese_keyboard_dictionary_assets.zip', args.revision)
