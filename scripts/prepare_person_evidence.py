#!/usr/bin/env python3
"""Extract existing person provenance for real subagent research, without classifying.

The immutable cache covers every adopted person pair. Historical AI decisions and
reasons are explicitly unverified hints. Even previously source-backed additions
need fresh identity, appearance and independent review before general admission.
No network/model calls, no guessed occupations, no new adoption or adult decisions.
"""
import argparse
import collections
import gzip
import io
import json
from pathlib import Path
import zipfile

import classified_distribution as distribution
import person_subclassification as person


def jsonl(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def original_source_rows(root):
    # Extraction is independent of optional build-time id.def downloads. These
    # are frozen provenance hints, not a new source-to-dictionary certification.
    for source, (relative, member) in distribution.SOURCES.items():
        if member:
            with zipfile.ZipFile(root / relative) as archive, archive.open(member) as raw:
                with io.TextIOWrapper(raw, encoding='utf-8') as stream:
                    yield from distribution.parse_rows(stream, source)
        else:
            with (root / relative).open(encoding='utf-8') as stream:
                yield from distribution.parse_rows(stream, source)
    additions = root / distribution.TERM_ADDITIONS_PATH
    if additions.exists():
        with additions.open(encoding='utf-8') as stream:
            rows = ('\t'.join(line.rstrip('\n').split('\t')[:5]) for line in stream)
            yield from distribution.parse_rows(rows, 'term_additions')


def build(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    person.require(not output.exists(), 'evidence cache already exists; refusing overwrite')
    person.require(not output.is_relative_to(root / 'src') and not output.is_relative_to(root / 'docs'),
                   'evidence build must not target production assets')
    base = root / person.BASE
    items = person.collect_items(root)
    by_pair = {(x['reading'], x['surface']): x for x in items}
    hints = {pair: {'item_id': x['item_id'], 'reading': pair[0], 'surface': pair[1],
                    'records': x['records'], 'source_rows': [], 'frozen_decision': None,
                    'historical_ai_hints': [], 'target_hints': [], 'existing_reviews': [],
                    'public_source_records': []}
             for pair, x in by_pair.items()}
    sources = set(root / person.BASE / name for name in person.SOURCES)
    sources.add(Path(distribution.__file__).resolve())
    for path, _ in distribution.SOURCES.values():
        sources.add(root / path)
    if (root / distribution.TERM_ADDITIONS_PATH).exists():
        sources.add(root / distribution.TERM_ADDITIONS_PATH)
    for source, row in original_source_rows(root):
        entry = hints.get((row[0], row[4]))
        if entry is not None:
            entry['source_rows'].append([source, *row])
    with gzip.open(base / 'distribution-decisions.tsv.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            row = line.rstrip('\n').split('\t')
            entry = hints.get((row[0], row[1]))
            if entry is not None:
                person.require(entry['frozen_decision'] is None, 'duplicate frozen decision')
                entry['frozen_decision'] = {'categories': row[2].split(','), 'origin': row[3],
                                            'status': row[4], 'verification': 'frozen_adoption_only'}
    result_path = base / 'luna-reclassification/results.jsonl.gz'
    if result_path.exists():
        sources.add(result_path)
        for record in jsonl(result_path):
            response = record['response']
            entry = hints.get((response['reading'], response['surface']))
            if entry is not None:
                entry['historical_ai_hints'].append({
                    'verification': 'unverified_ai_hint', 'effective_action': record['effective_action'],
                    'effective_categories': record['effective_categories'], 'effective_reason': record['effective_reason'],
                    'response': response, 'batch_provenance': record.get('batch_provenance'),
                    'representation_error': record.get('representation_error')})
    target_path = base / 'luna-reclassification/targets.jsonl.gz'
    if target_path.exists():
        sources.add(target_path)
        for record in jsonl(target_path):
            entry = hints.get((record['reading'], record['surface']))
            if entry is not None:
                entry['target_hints'].append({'verification': 'unverified_historical_hint',
                                              'hints': record.get('hints', []),
                                              'original_origin': record.get('original_origin'),
                                              'original_status': record.get('original_status')})
    for path in sorted((base / 'reviews').glob('*.jsonl')):
        sources.add(path)
        for record in jsonl(path):
            entry = hints.get((record['reading'], record['surface']))
            if entry is not None:
                entry['existing_reviews'].append({'path': str(path.relative_to(root)),
                                                  'verification': 'prior_category_review_not_person_subclassification',
                                                  'record': record})
    for path in sorted((base / 'person-additions').glob('*.jsonl')):
        sources.add(path)
        for record in jsonl(path):
            entry = hints.get((record['reading'], record['surface']))
            if entry is not None:
                entry['public_source_records'].append({'path': str(path.relative_to(root)),
                                                       'verification': 'existing_source_record_recheck_required',
                                                       'record': record})
    hashes = {str(path.relative_to(root)): person.sha(path) for path in sorted(sources)}
    cache_id = person.digest({'schema_version': 1, 'source_hashes': hashes,
                              'extractor_sha256': person.sha(Path(__file__)),
                              'person_engine_sha256': person.sha(Path(person.__file__))})
    counts = collections.Counter()
    source_counts = collections.Counter()
    origin_counts = collections.Counter()
    output.mkdir(parents=True)
    cache_path = output / 'person-evidence.jsonl.gz'
    with cache_path.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped:
        with io.TextIOWrapper(zipped, encoding='utf-8', newline='\n') as stream:
            for pair, entry in hints.items():
                entry['source_rows'].sort()
                entry['cache_id'] = cache_id
                entry['classification_status'] = 'research_required'
                counts['items'] += 1
                counts['records'] += len(entry['records'])
                for field in ('source_rows', 'historical_ai_hints', 'target_hints', 'existing_reviews', 'public_source_records'):
                    counts[field + '_items'] += bool(entry[field])
                    counts[field + '_records'] += len(entry[field])
                if entry['frozen_decision']:
                    origin_counts[entry['frozen_decision']['origin']] += 1
                for source in {row[0] for row in entry['source_rows']}:
                    source_counts[source] += 1
                stream.write(person.canonical(entry).decode() + '\n')
    manifest = {'schema_version': 1, 'cache_id': cache_id, 'counts': dict(counts),
                'source_pair_counts': dict(source_counts), 'frozen_origin_counts': dict(origin_counts),
                'source_hashes': hashes, 'extractor_sha256': person.sha(Path(__file__)),
                'person_engine_sha256': person.sha(Path(person.__file__)),
                'files': {'person-evidence.jsonl.gz': person.sha(cache_path)},
                'policy': 'Existing AI/category records are hints; no person identity, occupation or adult status is newly verified.',
                'production_release': False}
    person.write_json(output / 'manifest.json', manifest)
    return manifest


def verify(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    person.require(manifest['schema_version'] == 1 and manifest['production_release'] is False, 'invalid evidence manifest')
    person.require(manifest['extractor_sha256'] == person.sha(Path(__file__)), 'extractor changed')
    person.require(manifest['person_engine_sha256'] == person.sha(Path(person.__file__)), 'person engine changed')
    for name, expected in manifest['source_hashes'].items():
        path = Path(name)
        person.require(not path.is_absolute() and '..' not in path.parts, 'invalid source path')
        person.require(person.sha(root / path) == expected, 'source changed: ' + name)
    person.require(manifest['cache_id'] == person.digest({
        'schema_version': 1, 'source_hashes': manifest['source_hashes'],
        'extractor_sha256': manifest['extractor_sha256'], 'person_engine_sha256': manifest['person_engine_sha256']}), 'invalid cache ID')
    for name, expected in manifest['files'].items():
        person.require(name == 'person-evidence.jsonl.gz', 'unexpected evidence filename')
        person.require(person.sha(output / name) == expected, 'cache file changed')
    items = person.collect_items(root)
    records = iter(jsonl(output / 'person-evidence.jsonl.gz'))
    for item in items:
        entry = next(records, None)
        person.require(entry is not None and all(entry[k] == item[k] for k in ('item_id', 'reading', 'surface', 'records')),
                       'cache universe mismatch')
        person.require(entry['cache_id'] == manifest['cache_id'] and entry['classification_status'] == 'research_required', 'invalid cache status')
    person.require(next(records, None) is None, 'extra evidence item')
    person.require(manifest['counts']['items'] == len(items) and
                   manifest['counts']['records'] == sum(len(x['records']) for x in items), 'cache count mismatch')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'verify'))
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = build(args.root, args.output) if args.command == 'build' else verify(args.root, args.output)
        print(json.dumps({k: manifest[k] for k in ('cache_id', 'counts', 'source_pair_counts', 'frozen_origin_counts')}, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f'error: {error}\n')


if __name__ == '__main__':
    main()
