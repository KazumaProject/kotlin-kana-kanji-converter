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
from datetime import date
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
        if (not re.fullmatch('[ぁ-ゖー]+', entry['reading'])
                or entry['reading'] != person_reading(entry['source_reading'])
                or entry['surface'] != ''.join(entry['source_surface'].split())
                or unicodedata.normalize('NFC', entry['surface']) != entry['surface']):
            raise ValueError(f'{path}:{number}: reading/surface differs from kana evidence')
        if entry['sport'] not in ('mma', 'kickboxing', 'boxing'):
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
    manifest['provenance'].setdefault('personAdditions', []).append({
        'path': relative, 'sha256': sha(path), 'reviewedPairs': len(entries),
        'addedPairs': [[row[0], row[4]] for row in additions], 'addedRecords': record_count,
        'addedSourceRows': len(appended),
    })
    # Validate a staged snapshot first. Invalid batches never partially edit the inputs.
    with tempfile.TemporaryDirectory(prefix='person-additions-') as temporary:
        staging = Path(temporary)
        staged_directory = staging / 'src/main/classification'
        staged_directory.mkdir(parents=True)
        for relative_path in [*manifest['inputs'], 'src/main/resources/id.def', 'src/main/classification/categories.json']:
            target = staging / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative_path != names_path:
                target.symlink_to(root / relative_path)
        (staging / names_path).write_text(names, encoding='utf-8')
        write_gzip(staged_directory / 'distribution-candidates.tsv.gz', sorted(rows))
        write_gzip(staged_directory / 'distribution-decisions.tsv.gz', (decisions[pair] for pair in sorted(decisions)))
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
    categories = json.loads(taxonomy.read_text())
    allowed = {c['id'] for c in categories['categories']}
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
    rows = set()
    matched = set()
    source_counts = collections.Counter()
    for source, row in source_rows(root):
        pair = (row[0], row[4])
        source_counts[source] += 1
        if pair not in decisions:
            continue
        matched.add(pair)
        cats, origin = decisions[pair]
        if not cats <= allowed:
            raise ValueError(f'Unknown categories for {pair}: {cats - allowed}')
        if pair not in excluded:
            rows.update((cat, *row) for cat in cats)
    if decisions.keys() - matched:
        raise ValueError(f'Classifications missing from source dictionaries: {len(decisions.keys() - matched)}')
    import classification_reviews as reviews
    baseline = {pair: [*pair, ','.join(sorted(cats)), origin,
                      'excluded' if pair in excluded else 'classified' if cats else
                      'no_result' if origin == 'no_result' else 'unclassified']
                for pair, (cats, origin) in decisions.items()}
    review_paths = reviews.paths(root)
    reviewed = reviews.apply(baseline, reviews.load(root)) if review_paths else baseline
    if review_paths:
        rows = reviews.candidate_rows(root, reviewed, reviews.load(root))
    (out / 'categories.json').write_text(json.dumps(categories, ensure_ascii=False, indent=2) + '\n')
    write_gzip(out / 'distribution-candidates.tsv.gz', sorted(rows))
    write_gzip(out / 'distribution-decisions.tsv.gz', (reviewed[pair] for pair in sorted(reviewed)))
    admitted = collections.Counter(origin for pair, (cats, origin) in decisions.items() if cats and pair not in excluded)
    category_counts = collections.Counter(row[0] for row in rows)
    inputs = {path: sha(root / path) for path, _ in SOURCES.values()}
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
        'schemaVersion': 1,
        'precedence': ['verified', 'manual', 'gemini'],
        'provenance': {
            'acceptedSha256': sha(accepted), 'dispositionsSha256': sha(dispositions),
            'databaseReadSnapshotSha256': snapshot_hash.hexdigest(), 'manualSha256': sha(manual),
            'manualCandidates': manual_count, 'baselineVerifiedPairs': verified,
            'termAdditions': term_addition_provenance,
        },
        'inputs': inputs,
        'files': {name: sha(out / name) for name in ('categories.json', 'distribution-candidates.tsv.gz', 'distribution-decisions.tsv.gz')},
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
    if len(categories) != 28 or len(set(categories)) != 28:
        raise ValueError('Expected 28 unique categories')
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
            if not values <= set(categories) or status not in ('excluded', 'classified', 'unclassified', 'no_result'):
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
    if reviews.apply(baseline_decisions, review_entries) != decision_rows:
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
        if ('term' not in decisions.get(pair, set())
                or decision_status.get(pair) != ('verified', 'classified')):
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
    print(f'Verified frozen distribution: {len(actual)} rows, {sum(origins.values())} pairs, 28 categories')


def release_manifest(root, archive, revision):
    source = json.loads((root / 'src/main/classification/distribution-manifest.json').read_text())
    with zipfile.ZipFile(archive) as z:
        assets = {name: hashlib.sha256(z.read(name)).hexdigest() for name in sorted(z.namelist()) if not name.endswith('/')}
    import specialist_distribution as specialist
    specialist_manifest = specialist.verify_files(root)
    license_file = archive.parent / 'DICTIONARY-LICENSES.txt'
    license_file.write_text(specialist.licenses(root), encoding='utf-8')
    result = {'schemaVersion': 1, 'revision': revision, 'classification': source,
              'specialist': specialist_manifest, 'categoryCount': len(source['categoryRows']) + len(specialist_manifest['categoryRows']),
              'licensesSha256': sha(license_file),
              'archiveSha256': sha(archive), 'assets': assets}
    output = archive.parent / 'dictionary-distribution-manifest.json'
    write_json(output, result)
    (archive.parent / 'DICTIONARY-SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in (archive, output, license_file)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['freeze', 'verify', 'release-manifest', 'add-person-names', 'apply-reviews', 'recover-reviews'])
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
    else:
        release_manifest(args.root, args.archive or args.root / 'release_zips/japanese_keyboard_dictionary_assets.zip', args.revision)
