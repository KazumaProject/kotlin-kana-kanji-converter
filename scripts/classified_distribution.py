#!/usr/bin/env python3
"""Freeze saved classifications, or verify the frozen distribution (no model calls)."""
import argparse
import collections
import gzip
import hashlib
import io
import json
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


def merged_categories(base, term_data):
    if term_data is None:
        return base
    structure, term_categories = term_data
    categories = list(base.get('categories', []))
    ids = [category.get('id') for category in categories]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate category IDs in source taxonomy')
    if 'term' in ids:
        insertion = ids.index('term')
        categories = [category for category in categories if category.get('id') != 'term']
        categories[insertion:insertion] = term_categories
    elif set(category['id'] for category in term_categories) <= set(ids):
        existing = {category['id']: category for category in categories}
        for category in term_categories:
            if existing[category['id']].get('name') != category['name']:
                raise ValueError(f'Term category name differs from taxonomy: {category["id"]}')
    else:
        raise ValueError('Source taxonomy must contain term or all 15 expanded term categories')
    result = dict(base)
    result['categories'] = categories
    result['categoryGroups'] = [structure]
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
            if len(leaf_categories) != 1 or pair not in results:
                raise ValueError(f'Each admitted term pair must have exactly one Gemini leaf category: {pair}')
            for category in leaf_categories:
                if pair not in reviewed_pairs and results.get(pair) != category:
                    raise ValueError(f'Frozen term category differs from Gemini result: {pair}')
        output[pair] = row
    return output


def apply_term_classifications_snapshot(root):
    """Replace the frozen structural term category with its 15 Gemini leaves."""
    import shutil
    root = Path(root).resolve()
    directory = root / 'src/main/classification'
    verify(root)
    base = json.loads((directory / 'categories.json').read_text(encoding='utf-8'))
    if any(category['id'].startswith('term/') for category in base['categories']):
        raise ValueError('Term categories are already expanded')
    expanded = merged_categories(base, term_taxonomy(root))
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


def person_reading(value):
    """Only mechanical kana normalization; never transliterate Latin names."""
    value = unicodedata.normalize('NFC', value)
    return ''.join(chr(ord(c) - 0x60) if '\u30a1' <= c <= '\u30f6' else c
                   for c in value if not c.isspace() and c not in '・“”「」')


def person_entries(root, path):
    ids = {int(line.split(maxsplit=1)[0]) for line in
           (root / 'src/main/resources/id.def').read_text(encoding='utf-8').splitlines()}
    taxonomy_path = root / 'src/main/classification/person-taxonomy.json'
    if taxonomy_path.is_file():
        taxonomy = json.loads(taxonomy_path.read_text(encoding='utf-8'))
        allowed_sports = set(taxonomy.get('sport_subcategories', {}))
    else:
        # Older minimal snapshots and verification fixtures predate taxonomy
        # metadata. Restrict their fallback to the original three sport IDs.
        allowed_sports = LEGACY_PERSON_SPORT_IDS
    entries = {}
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        entry = json.loads(line)
        required = ('reading', 'surface', 'sport', 'left_id', 'right_id', 'cost',
                    'source_url', 'source_surface', 'source_reading', 'checked_on')
        if not isinstance(entry, dict) or any(k not in entry for k in required):
            raise ValueError(f'{path}:{number}: missing person entry/evidence fields')
        for field in ('reading', 'surface', 'sport', 'source_url', 'source_surface', 'source_reading', 'checked_on'):
            if not isinstance(entry[field], str) or not entry[field] or any(c in entry[field] for c in '\t\r\n\0'):
                raise ValueError(f'{path}:{number}: invalid {field}')
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
        if entry['sport'] not in allowed_sports:
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
    previous_rows = len(rows)
    for pair, entry in sorted(entries.items()):
        prior = decisions.get(pair)
        if prior is not None:
            if prior[4] == 'classified' and 'person' in prior[2].split(','):
                continue
            raise ValueError(f'Existing classification/exclusion conflicts with person entry: {pair}')
        row = (pair[0], str(entry['left_id']), str(entry['right_id']), str(entry['cost']), pair[1])
        additions.append(row)
        if row not in names_rows: appended.append(row)
        # A previously undecided pair may already have several source POS/cost variants.
        # Admit those unchanged as well, as required by the source-to-distribution verifier.
        rows.update(('person', *existing) for existing in sources_by_pair[pair] | {row})
        decisions[pair] = [*pair, 'person', 'verified', 'classified']
    if not additions:
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
        for relative_path in staged_paths:
            target = staging / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative_path != names_path:
                target.symlink_to(root / relative_path)
        (staging / names_path).write_text(names, encoding='utf-8')
        write_gzip(staged_directory / 'distribution-candidates.tsv.gz', sorted(rows))
        write_gzip(staged_directory / 'distribution-decisions.tsv.gz', (decisions[pair] for pair in sorted(decisions)))
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
    print(f'Person additions: {count} new pairs, {record_count} records, {len(entries) - count} already admitted')


def freeze(root, accepted, dispositions, database, manual, taxonomy):
    out = root / 'src/main/classification'
    out.mkdir(parents=True, exist_ok=True)
    prior_manifest_path = out / 'distribution-manifest.json'
    prior_batches = (json.loads(prior_manifest_path.read_text()).get('provenance', {}).get('personAdditions', [])
                     if prior_manifest_path.exists() else [])
    categories = merged_categories(json.loads(taxonomy.read_text()), term_taxonomy(root))
    allowed = {c['id'] for c in categories['categories']}
    term_data = term_classification_data(root, allowed)
    if term_taxonomy(root) is not None and term_data is None:
        raise ValueError('Cannot freeze expanded term categories without complete Gemini results')
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
        source_allowed = allowed | ({'term'} if term_data is not None else set())
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
    rows = reviews.candidate_rows(root, reviewed, review_entries)
    (out / 'categories.json').write_text(json.dumps(categories, ensure_ascii=False, indent=2) + '\n')
    write_gzip(out / 'distribution-candidates.tsv.gz', sorted(rows))
    write_gzip(out / 'distribution-decisions.tsv.gz', (reviewed[pair] for pair in sorted(reviewed)))
    admitted = collections.Counter(origin for pair, (cats, origin) in decisions.items() if cats and pair not in excluded)
    category_counts = collections.Counter(row[0] for row in rows)
    inputs = {path: sha(root / path) for path, _ in SOURCES.values()}
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
        'schemaVersion': 2 if term_data is not None else 1,
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
        'excludedClassifiedPairs': sum(pair in excluded for pair in decisions),
        'unclassifiedPairs': sum(not cats and pair not in excluded and origin != 'no_result' for pair, (cats, origin) in decisions.items()),
        'noResultPairs': sum(origin == 'no_result' and pair not in excluded for pair, (_, origin) in decisions.items()),
        'conflicts': dict(conflicts),
        'categoryRows': {c['id']: category_counts[c['id']] for c in categories['categories']},
        'dictionaryRows': len(rows),
        'limitations': ['Gemini and manual classifications include provisional categories and unverified readings. IME runtime behavior is not verified.'],
    }
    if term_classification_provenance is not None:
        manifest['provenance']['termClassification'] = term_classification_provenance
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
    if not allow_pending_reviews and selected_reviews != reviews.paths(root):
        raise ValueError('Review history changed: run apply-reviews before building')
    for path, expected in manifest['inputs'].items():
        if sha(root / path) != expected:
            raise ValueError(f'Input hash mismatch: {path}')
    for name, expected in manifest['files'].items():
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
    if term_data is not None:
        if manifest.get('schemaVersion') != 2:
            raise ValueError('Expanded term categories require distribution manifest schema 2')
        saved_taxonomy = json.loads((directory / 'categories.json').read_text(encoding='utf-8'))
        if (saved_taxonomy.get('categoryGroups') != [term_data['taxonomy']]
                or manifest.get('categoryGroups') != saved_taxonomy['categoryGroups']):
            raise ValueError('Term category hierarchy differs from its taxonomy')
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
            allowed = set(categories) | ({'term'} if status == 'excluded' else set())
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
    counts = collections.Counter(row[0] for row in actual)
    if ({c: counts[c] for c in categories} != manifest['categoryRows'] or len(actual) != manifest['dictionaryRows']
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
    import luna_reclassification
    luna_reclassification.verify_ledger(root)
    print(f'Verified frozen distribution: {len(actual)} rows, {sum(origins.values())} pairs, {len(categories)} categories')


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
