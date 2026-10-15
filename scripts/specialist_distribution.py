#!/usr/bin/env python3
"""Explicit upstream acquisition; deterministic offline freeze/verification of specialist data."""
import argparse
import collections
import csv
import gzip
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import unicodedata
import urllib.request
import zipfile

import classified_distribution as distribution

DIRECTORY = 'src/main/specialist'
NOUN = '名詞,一般,*,*,*,*,*'
COST = 9000
HIRA = set('あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんぁぃぅぇぉゃゅょゎっゔーがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ')
KATA = {chr(ord(c) + 0x60) if '\u3041' <= c <= '\u3094' else c for c in HIRA}
RULES = dict(version=2, key='normalized_reading+NFC_surface', reading='trim,NFKC,katakana-to-hiragana',
             surface='trim,NFC; internal spaces/case/width/variants preserved',
             readingPattern='[ぁ-ゖー]+', categoryPriority=['kampo', 'medical'], cost=COST, pos=NOUN,
             readingAccuracy='upstream automatic readings and optional Gemini inference; not independently verified',
             supplement='manbyo missing readings only; source row and original surface must match',
             kanaSurface='must equal the current TokenArray sentinel reconstruction')


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def compressed_json(values):
    raw = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as zipped:
        for value in values:
            zipped.write(json_bytes(value))
    return raw.getvalue()


def read_json_gzip(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def normalize_reading(value):
    value = unicodedata.normalize('NFKC', value.strip())
    return unicodedata.normalize('NFC', ''.join(chr(ord(c)-0x60) if '\u30a1' <= c <= '\u30f6' else c for c in value))


def normalize_surface(value):
    return unicodedata.normalize('NFC', value.strip())


def key(reading, surface):
    return normalize_reading(reading), normalize_surface(surface)


def hira_to_kata(value):
    # Deliberately matches Extenstions.kt, including its current ゔ limitation.
    return ''.join(chr(ord(c)+0x60) if '\u3041' <= c <= '\u3093' else c for c in value)


def invalid_reason(raw_reading, raw_surface, reading, surface):
    if not reading or not surface or reading in ('-1', '-', 'NA') or surface in ('-1', '-', 'NA'):
        return 'missing_or_placeholder'
    if any(unicodedata.category(c).startswith('C') for c in raw_reading + raw_surface):
        return 'control_character'
    if not re.fullmatch('[ぁ-ゖー]+', reading):
        return 'non_kana_reading'
    if len(reading.encode('utf-16-le')) // 2 > 32767:
        return 'reading_length_overflow'
    if (set(surface) <= HIRA and surface != reading or
            set(surface) <= KATA and surface != hira_to_kata(reading)):
        return 'unsupported_kana_surface'
    return None


def extract_pairs(data, spec):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        text = archive.read(spec['member']).decode(spec['encoding'])
    reader = csv.DictReader(io.StringIO(text, newline=''))
    if not {spec['surfaceColumn'], spec['readingColumn']} <= set(reader.fieldnames or []):
        raise ValueError('Required CSV columns missing: ' + spec['id'])
    for number, row in enumerate(reader, 2):
        if None in row or row[spec['surfaceColumn']] is None or row[spec['readingColumn']] is None:
            raise ValueError(f'Malformed CSV record: {spec["id"]}:{number}')
        yield dict(row=number, reading=row[spec['readingColumn']], surface=row[spec['surfaceColumn']])


class NoticeText(HTMLParser):
    def __init__(self):
        super().__init__(); self.hidden = 0; self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
        if tag in ('p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'br'): self.text.append('\n')
        if tag == 'a' and not self.hidden:
            for name, value in attrs:
                if name == 'href' and value.startswith('https://creativecommons.org/'):
                    self.text.append(' [' + value + '] ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden: self.text.append(data)


def request(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'kana-kanji-dictionary-source/1.0'}), timeout=60) as response:
        return response.read()


def fetch(root):
    directory = root / DIRECTORY
    config = json.loads((directory / 'sources.json').read_text(encoding='utf-8'))
    cache = root / 'build/specialist/upstream'
    cache.mkdir(parents=True, exist_ok=True)
    snapshots = directory / 'sources'; snapshots.mkdir(exist_ok=True)
    notices = directory / 'notices'; notices.mkdir(exist_ok=True)
    for spec in config['sources']:
        raw_path = cache / (spec['id'] + '.zip')
        if not raw_path.exists():
            url = spec['download']
            if not url.endswith('.zip'):
                page = request(url).decode('utf-8')
                match = re.search(r'data-downloadurl="([^"]+)"', page)
                if not match: raise ValueError('No download link on ' + url)
                url = match.group(1).replace('&amp;', '&')
            raw_path.write_bytes(request(url))
        if distribution.sha(raw_path) != spec['archiveSha256']:
            raise ValueError('Upstream archive changed; review and explicitly update sources.json: ' + spec['id'])
        pairs = list(extract_pairs(raw_path.read_bytes(), spec))
        (snapshots / (spec['id'] + '.jsonl.gz')).write_bytes(compressed_json(pairs))
        parser = NoticeText(); parser.feed(request(spec['notice']).decode('utf-8'))
        text = '\n'.join(line.strip() for line in ''.join(parser.text).splitlines() if line.strip())
        (notices / (spec['id'] + '.txt')).write_text('Source: ' + spec['notice'] + '\n\n' + text + '\n', encoding='utf-8')
        print(f'Acquired {spec["id"]}: {len(pairs)} source rows')
    for name, url in [('CC-BY-4.0', 'https://creativecommons.org/licenses/by/4.0/legalcode.txt'),
                      ('CC-BY-SA-2.1-JP', 'https://creativecommons.org/licenses/by-sa/2.1/jp/legalcode')]:
        raw = request(url).decode('utf-8')
        if '<html' in raw.lower() or '<!doctype' in raw.lower():
            parser = NoticeText(); parser.feed(raw)
            raw = '\n'.join(line.strip() for line in ''.join(parser.text).splitlines() if line.strip())
        (notices / (name + '.txt')).write_text('Source: ' + url + '\n\n' + raw + '\n', encoding='utf-8')


def load_inventory(path):
    existing = collections.defaultdict(set)
    for row in read_json_gzip(path):
        existing[key(row['reading'], row['surface'])].add(row['dictionary'])
    return existing


def prepare(root, inventory):
    directory = root / DIRECTORY
    config = json.loads((directory / 'sources.json').read_text(encoding='utf-8'))
    categories = json.loads((directory / 'categories.json').read_text(encoding='utf-8'))['categories']
    if [c['id'] for c in categories] != ['kampo', 'medical']:
        raise ValueError('Expected kampo, medical categories in priority order')
    ids = [s['id'] for s in config['sources']]
    if len(set(ids)) != len(ids) or any(s['category'] not in ('kampo', 'medical') for s in config['sources']):
        raise ValueError('Invalid source configuration')
    pos = [line.split(maxsplit=1) for line in (root / 'src/main/resources/id.def').read_text().splitlines()]
    matches = [int(i) for i, name in pos if name == NOUN]
    if len(matches) != 1 or not 0 <= matches[0] <= 32767: raise ValueError('Missing or invalid noun context')
    existing = load_inventory(inventory)
    adopted = {}; provenance = []; source_counts = {}; counts = collections.Counter()
    supplement_path = directory / 'gemini-readings.jsonl.gz'
    supplements = {}
    if supplement_path.exists():
        for entry in read_json_gzip(supplement_path):
            number = entry['sourceRow']
            if entry['source'] != 'manbyo' or entry['readingStatus'] != 'gemini_inferred_unverified' or number in supplements:
                raise ValueError('Invalid or duplicate Gemini source row')
            if entry['model'] != 'gemini-3.5-flash-lite' or not all(re.fullmatch('[0-9a-f]{64}', entry[k]) for k in ('requestSha256','responseSha256')):
                raise ValueError('Invalid Gemini provenance')
            supplements[number] = entry
    used_supplements = set(); origins = collections.Counter()
    inputs = {str(p.relative_to(root)): distribution.sha(p) for p in sorted(directory.glob('notices/*.txt'))}
    if supplement_path.exists(): inputs[str(supplement_path.relative_to(root))] = distribution.sha(supplement_path)
    report_path = directory / 'gemini-run.json'
    if report_path.exists(): inputs[str(report_path.relative_to(root))] = distribution.sha(report_path)
    for name in ('categories.json', 'sources.json'):
        inputs[str((directory / name).relative_to(root))] = distribution.sha(directory / name)
    ordered = sorted(config['sources'], key=lambda s: (RULES['categoryPriority'].index(s['category']), s['id']))
    for spec in ordered:
        path = directory / 'sources' / (spec['id'] + '.jsonl.gz')
        inputs[str(path.relative_to(root))] = distribution.sha(path)
        by_status = collections.Counter(); row_count = 0
        for row in read_json_gzip(path):
            row_count += 1
            original_reason = invalid_reason(row['reading'], row['surface'], *key(row['reading'], row['surface']))
            inferred = supplements.get(row['row']) if spec['id'] == 'manbyo' else None
            raw_reading = row['reading']
            if inferred:
                if original_reason != 'missing_or_placeholder' or inferred['surface'] != row['surface']:
                    raise ValueError('Gemini supplement does not match a missing source reading')
                raw_reading = inferred['reading']; used_supplements.add(row['row'])
            reading, surface = key(raw_reading, row['surface']); pair = reading, surface
            reason = invalid_reason(raw_reading, row['surface'], reading, surface)
            record = dict(source=spec['id'], sourceRow=row['row'], originalReading=row['reading'],
                          originalSurface=row['surface'], reading=reading, surface=surface, category=spec['category'])
            record['readingOrigin'] = 'gemini_inferred_unverified' if inferred else 'upstream_unverified'
            if inferred: record['inference'] = inferred
            if reason:
                status = reason
            elif pair in existing:
                status = 'existing_duplicate'; record['existingDictionaries'] = sorted(existing[pair])
            elif pair in adopted:
                record['retainedCategory'] = adopted[pair]
                status = 'cross_category_duplicate' if adopted[pair] != spec['category'] else 'source_duplicate'
            else:
                adopted[pair] = spec['category']; status = 'adopted'; origins[record['readingOrigin']] += 1
            record['status'] = status; provenance.append(record)
            by_status[status] += 1; counts[status] += 1
        source_counts[spec['id']] = dict(rows=row_count, dispositions=dict(sorted(by_status.items())))
    if used_supplements != set(supplements): raise ValueError('Unknown Gemini source row')
    records = sorted((category, reading, str(matches[0]), str(matches[0]), str(COST), surface)
                     for (reading, surface), category in adopted.items())
    import feedback_data as feedback
    feedback_requests = [(path, entry) for path, entry in feedback.requests(root)
                         if any(op['dictionary'] in ('categories/kampo', 'categories/medical') for op in entry['operations'])]
    if feedback_requests:
        records = feedback.specialist_rows(root, records, existing)
        inputs.update({path: distribution.sha(root / path) for path, _ in feedback_requests})
        retained = {(row[0], row[1], row[5]) for row in records}
        for record in provenance:
            if record['status'] == 'adopted' and (record['category'], record['reading'], record['surface']) not in retained:
                record['status'] = 'feedback_excluded'
                counts['adopted'] -= 1; counts['feedback_excluded'] += 1
                source_dispositions = source_counts[record['source']]['dispositions']
                source_dispositions['adopted'] -= 1
                source_dispositions['feedback_excluded'] = source_dispositions.get('feedback_excluded', 0) + 1
        known = {(r['category'], r['reading'], r['surface']) for r in provenance if r['status'] == 'adopted'}
        for path, entry in feedback_requests:
            for op in entry['operations']:
                identity = (op['dictionary'].split('/')[-1], op['reading'], op['surface'])
                if identity in retained and identity not in known:
                    provenance.append(dict(source='owner_feedback', sourceRow=entry['issue'], category=identity[0],
                                           reading=identity[1], surface=identity[2], originalReading=identity[1],
                                           originalSurface=identity[2], readingOrigin='user_confirmation',
                                           status='adopted', reference=entry['issueUrl'], request=path))
                    known.add(identity)
                    counts['adopted'] += 1
                    source_counts.setdefault('owner_feedback', dict(rows=0, dispositions=dict(adopted=0)))
                    source_counts['owner_feedback']['rows'] += 1
                    source_counts['owner_feedback']['dispositions']['adopted'] += 1
        origins = collections.Counter(record['readingOrigin'] for record in provenance if record['status'] == 'adopted')
    candidates = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=candidates, mode='wb', mtime=0) as gz:
        gz.write(''.join('\t'.join(row)+'\n' for row in records).encode())
    data = {'distribution-candidates.tsv.gz': candidates.getvalue(), 'provenance.jsonl.gz': compressed_json(provenance)}
    manifest = dict(schemaVersion=1, rules=RULES, inputs=inputs,
                    idDefSha256=distribution.sha(root/'src/main/resources/id.def'),
                    existingInventorySha256=distribution.sha(inventory),
                    existingDictionaryIds=sorted({name for names in existing.values() for name in names}),
                    existingUniquePairs=len(existing), sourceRows=source_counts, dispositions=dict(sorted(counts.items())),
                    categoryRows={c['id']: sum(r[0] == c['id'] for r in records) for c in categories},
                    dictionaryRows=len(records), uniqueAdmittedPairs=len({(r[1], r[5]) for r in records}), readingOrigins=dict(sorted(origins.items())),
                    files={name: hashlib.sha256(raw).hexdigest() for name, raw in data.items()},
                    limitations=['Upstream readings include automatic readings; Gemini supplements are inferred. Neither is independently verified.',
                                 'POS and cost are assigned by this project. IME behavior and ranking are not verified.',
                                 'Kana surfaces incompatible with the current sentinel encoding are withheld.'])
    return data, manifest


def freeze(root, inventory):
    data, manifest = prepare(root, inventory)
    directory = root / DIRECTORY
    for name, raw in data.items(): (directory / name).write_bytes(raw)
    distribution.write_json(directory / 'distribution-manifest.json', manifest)
    print(json.dumps({'categoryRows': manifest['categoryRows'], 'dispositions': manifest['dispositions']}, ensure_ascii=False))


def verify_files(root):
    directory = root / DIRECTORY
    manifest = json.loads((directory / 'distribution-manifest.json').read_text(encoding='utf-8'))
    if manifest['rules'] != RULES: raise ValueError('Specialist selection rules changed: regenerate input')
    for path, expected in manifest['inputs'].items():
        if distribution.sha(root / path) != expected: raise ValueError('Specialist input hash mismatch: ' + path)
    for name, expected in manifest['files'].items():
        if distribution.sha(directory / name) != expected: raise ValueError('Specialist output hash mismatch: ' + name)
    if distribution.sha(root/'src/main/resources/id.def') != manifest['idDefSha256']:
        raise ValueError('Specialist id.def changed')
    return manifest


def verify(root, inventory):
    saved = verify_files(root)
    if distribution.sha(inventory) != saved['existingInventorySha256']:
        raise ValueError('Existing dictionary inventory changed: refreeze specialist inputs after review')
    data, wanted = prepare(root, inventory)
    if saved != wanted: raise ValueError('Specialist manifest differs from recomputed source selection')
    for name, raw in data.items():
        if (root / DIRECTORY / name).read_bytes() != raw:
            raise ValueError('Specialist selection differs from source snapshots: ' + name)
    print(f'Verified specialists: {saved["dictionaryRows"]} rows; no existing or cross-category duplicates')


def licenses(root):
    directory = root / DIRECTORY
    config = json.loads((directory / 'sources.json').read_text(encoding='utf-8'))
    parts = ['Dictionary data notices and licenses\n\nCode and third-party dictionary data have separate licenses.\n']
    for path in ('LICENSE', 'LICENSE-DATA.md', 'src/main/resources/THIRD-PARTY-NOTICES.md'):
        parts.append('\n=== ' + path + ' ===\n' + (root / path).read_text(encoding='utf-8'))
    feedback_license = root / 'src/main/dictionary-feedback/mozc/LICENSE'
    if feedback_license.exists():
        parts.append('\n=== Mozc inflection rules used for owner additions ===\n' + feedback_license.read_text())
        parts.append('\nOwner additions are recorded as user confirmations with their Issue URLs; they are not upstream or independently verified readings.\n')
    parts.append('\n=== Specialist dictionaries ===\nMedical: CC BY 4.0. Kampo: CC BY-SA 2.1 Japan.\n'
                 'Changes: field extraction, reading/surface normalization, duplicate filtering, optional Gemini inference of missing medical readings, assigned POS/cost, binary encoding.\n'
                 'Original readings include automatic readings; supplementary readings are Gemini inferences. Accuracy and IME ranking are not verified.\n')
    for spec in config['sources']:
        parts.append('\n' + spec['attribution'] + '\nSource: ' + spec['page'] + '\nLicense: ' + spec['license'] + '\n')
    for path in sorted(directory.glob('notices/*.txt')):
        parts.append('\n=== ' + path.name + ' ===\n' + path.read_text(encoding='utf-8'))
    for path in sorted((root / 'src/main/resources/third-party').iterdir()):
        if path.is_file():
            try: text = path.read_text(encoding='utf-8')
            except UnicodeDecodeError: continue
            parts.append('\n=== ' + path.name + ' ===\n' + text)
    return '\n'.join(parts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['fetch', 'freeze', 'verify'])
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--existing-index', type=Path, default=Path('build/specialist/existing-pairs.jsonl.gz'))
    args = parser.parse_args()
    if args.command == 'fetch': fetch(args.root)
    elif args.command == 'freeze': freeze(args.root, args.existing_index)
    else: verify(args.root, args.existing_index)
