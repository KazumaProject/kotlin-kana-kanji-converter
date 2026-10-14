#!/usr/bin/env python3
"""Freeze saved classifications, or verify the frozen distribution (no model calls)."""
import argparse
import collections
import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import zipfile

SOURCES = {
    'person': ('src/main/bin/names.txt', None),
    'place': ('src/main/bin/place.txt.zip', 'place.txt'),
    'wiki': ('src/main/bin/only_wiki.txt.zip', 'only_wiki.txt'),
    'neologd': ('src/main/bin/only_neologd.txt.zip', 'only_neologd.txt'),
    'web': ('src/main/bin/wiki_neologd_common.txt.zip', 'wiki_neologd_common.txt'),
}


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


def parse_rows(lines, source):
    for number, line in enumerate(lines, 1):
        row = line.rstrip('\r\n').split('\t')
        if len(row) != 5 or not row[0] or not row[4]:
            raise ValueError(f'{source}:{number}: invalid dictionary row')
        if not all(-32768 <= int(x) <= 32767 for x in row[1:4]) or any(int(x) < 0 for x in row[1:3]):
            raise ValueError(f'{source}:{number}: invalid POS/cost')
        yield source, tuple(row)


def key(reading, surface):
    return hashlib.sha256((reading + '\0' + surface).encode()).hexdigest()


def freeze(root, accepted, dispositions, database, manual, taxonomy):
    out = root / 'src/main/classification'
    out.mkdir(parents=True, exist_ok=True)
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
    (out / 'categories.json').write_text(json.dumps(categories, ensure_ascii=False, indent=2) + '\n')
    write_gzip(out / 'distribution-candidates.tsv.gz', sorted(rows))
    write_gzip(out / 'distribution-decisions.tsv.gz', (
        (*pair, ','.join(sorted(cats)), origin, 'excluded' if pair in excluded else 'classified' if cats else 'no_result' if origin == 'no_result' else 'unclassified')
        for pair, (cats, origin) in sorted(decisions.items())
    ))
    admitted = collections.Counter(origin for pair, (cats, origin) in decisions.items() if cats and pair not in excluded)
    category_counts = collections.Counter(row[0] for row in rows)
    manifest = {
        'schemaVersion': 1,
        'precedence': ['verified', 'manual', 'gemini'],
        'provenance': {
            'acceptedSha256': sha(accepted), 'dispositionsSha256': sha(dispositions),
            'databaseReadSnapshotSha256': snapshot_hash.hexdigest(), 'manualSha256': sha(manual),
            'manualCandidates': manual_count, 'baselineVerifiedPairs': verified,
        },
        'inputs': {path: sha(root / path) for path, _ in SOURCES.values()},
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
    write_json(out / 'distribution-manifest.json', manifest)
    print(json.dumps({k: manifest[k] for k in ('uniqueAdmittedPairs', 'admittedPairsByOrigin', 'dictionaryRows', 'unclassifiedPairs')}, ensure_ascii=False))


def verify(root):
    directory = root / 'src/main/classification'
    manifest = json.loads((directory / 'distribution-manifest.json').read_text())
    for path, expected in manifest['inputs'].items():
        if sha(root / path) != expected:
            raise ValueError(f'Input hash mismatch: {path}')
    for name, expected in manifest['files'].items():
        if sha(directory / name) != expected:
            raise ValueError(f'Classification hash mismatch: {name}')
    if sha(root / 'src/main/resources/id.def') != manifest['idDefSha256']:
        raise ValueError('id.def changed: regenerate and review distribution input')
    categories = [c['id'] for c in json.loads((directory / 'categories.json').read_text())['categories']]
    if len(categories) != 28 or len(set(categories)) != 28:
        raise ValueError('Expected 28 unique categories')
    decisions = {}
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
            if status == 'classified': origins[origin] += 1
            if status == 'excluded': excluded += 1
            if status == 'unclassified': unclassified += 1
            if status == 'no_result': no_result += 1
    expected = set()
    matched = set()
    for _, row in source_rows(root):
        pair = (row[0], row[4])
        if pair in decisions:
            matched.add(pair)
            expected.update((cat, *row) for cat in decisions[pair])
    if decisions.keys() - matched:
        raise ValueError('Decision missing from dictionary sources')
    actual = set()
    with gzip.open(directory / 'distribution-candidates.tsv.gz', 'rt') as f:
        for line in f:
            row = tuple(line.rstrip('\n').split('\t'))
            if len(row) != 6 or row in actual:
                raise ValueError('Invalid or duplicate distribution row')
            actual.add(row)
    if actual != expected:
        raise ValueError(f'Distribution differs from sources: missing={len(expected-actual)}, extra={len(actual-expected)}')
    counts = collections.Counter(row[0] for row in actual)
    if ({c: counts[c] for c in categories} != manifest['categoryRows'] or len(actual) != manifest['dictionaryRows']
            or dict(origins) != manifest['admittedPairsByOrigin'] or sum(origins.values()) != manifest['uniqueAdmittedPairs']
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
    p.add_argument('command', choices=['freeze', 'verify', 'release-manifest'])
    p.add_argument('--root', type=Path, default=Path('.'))
    for name in ('accepted', 'dispositions', 'database', 'manual', 'taxonomy', 'archive'):
        p.add_argument('--' + name, type=Path)
    p.add_argument('--revision', default='local')
    args = p.parse_args()
    if args.command == 'freeze':
        for name in ('accepted', 'dispositions', 'database', 'manual', 'taxonomy'):
            if getattr(args, name) is None: p.error('--' + name + ' is required')
        freeze(args.root, args.accepted, args.dispositions, args.database, args.manual, args.taxonomy)
    elif args.command == 'verify':
        verify(args.root)
    else:
        release_manifest(args.root, args.archive or args.root / 'release_zips/japanese_keyboard_dictionary_assets.zip', args.revision)
