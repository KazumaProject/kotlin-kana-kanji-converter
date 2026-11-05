"""Import explicitly English place labels from pinned GeoNames snapshots.

Only current preferred/short English alternate names for populated places and
explicitly English admin1 names qualify. ASCII transliterations, unlabeled names,
historic/colloquial aliases and inferred inflections are not evidence here.
"""
import argparse
from collections import Counter
import io
import json
from pathlib import Path
import tempfile
import zipfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
from wiktionary_index import Index

PINS = {
    'admin1CodesASCII.txt': '2e4867f5397acb056ea26377601b57af37cb4c81399770225018e9e439e91ad3',
    'cities500.zip': '7bea4c09f6df77df9b5bbccdeafa3d9e38873b46037e0385cc0f421a34d426e1',
    'alternateNamesV2.zip': 'bc00d3ff2a89b057f377e4277a65ad16b9bb3f5031edc5fb2e97be903ff872c2',
    'readme.txt': 'b1957379b6c1242c700c98ac9a8aa0a09f56c3c0a50ee72175527005f48ef2c5',
    'CC-BY-4.0.txt': '9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411',
}
CURRENT_POPULATED = {'PPL', 'PPLA', 'PPLA2', 'PPLA3', 'PPLA4', 'PPLC', 'PPLG', 'PPLX'}
GEOGRAPHIC_CLASSES = {'A', 'H', 'L', 'P', 'R', 'S', 'T', 'U', 'V'}
HISTORIC_POPULATED = {'PPLH', 'PPLQ', 'PPLW', 'PPLCH'}
PREPARED_SHA256 = 'a90efcad35c9a09571c5fd1fdab23afad22ca25f256dbf6a77e25b9d4118fd64'
COUNTS = {'english_admin1': 3865, 'english_alternate': 11630}
POLICY = 'verbatim explicitly English admin1 names or en preferred/short populated-place aliases; no historic/colloquial/dated aliases, ASCII transliterations, inferred corpus sense, countability or inflection'


def english_alternates(stream, features):
    for number, line in enumerate(stream, 1):
        columns = line.rstrip('\n').split('\t')
        if len(columns) != 10:
            raise ValueError('Invalid alternate-name row ' + str(number))
        alias, gid, language, label, preferred, short, colloquial, historic, start, end = columns
        feature = features.get(gid)
        if (language != 'en' or not feature or feature['featureCode'] not in CURRENT_POPULATED or
                preferred != '1' and short != '1' or colloquial == '1' or historic == '1' or start or end):
            continue
        if not alias.isdecimal() or not label.strip() or any(c in label for c in '\t\r\n'):
            raise ValueError('Invalid English name ' + str(number))
        yield {'kind': 'english_alternate', 'alternateId': alias, 'geonameId': gid, 'label': label,
               'line': number, 'language': language, 'preferred': preferred == '1', 'short': short == '1',
               'featureCode': feature['featureCode'], 'countryCode': feature['countryCode']}


def prepare(sources, output):
    if output.exists():
        raise ValueError('Preserve existing prepared source: ' + str(output))
    for name, expected in PINS.items():
        if pipeline.digest(sources / name) != expected:
            raise ValueError('Changed GeoNames source or notice: ' + name)
    names = []
    with (sources / 'admin1CodesASCII.txt').open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            code, label, ascii_name, gid = line.rstrip('\n').split('\t')
            if not gid.isdecimal() or not label.strip():
                raise ValueError('Invalid admin1 row')
            names.append({'kind': 'english_admin1', 'geonameId': gid, 'label': label, 'line': number, 'adminCode': code})
    features = {}
    with zipfile.ZipFile(sources / 'cities500.zip') as archive:
        with io.TextIOWrapper(archive.open('cities500.txt'), encoding='utf-8') as stream:
            for line in stream:
                fields = line.rstrip('\n').split('\t')
                if len(fields) != 19 or fields[6] != 'P' or not fields[0].isdecimal():
                    raise ValueError('Invalid populated-place feature')
                if fields[0] in features:
                    raise ValueError('Duplicate place feature')
                features[fields[0]] = {'featureCode': fields[7], 'countryCode': fields[8]}
    with zipfile.ZipFile(sources / 'alternateNamesV2.zip') as archive:
        with io.TextIOWrapper(archive.open('alternateNamesV2.txt'), encoding='utf-8') as stream:
            names.extend(english_alternates(stream, features))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.geonames-', dir=output.parent) as temporary:
        staging = Path(temporary) / 'prepared'
        staging.mkdir()
        pipeline.jsonl(staging / 'english-names.jsonl', names)
        if pipeline.digest(staging / 'english-names.jsonl') != PREPARED_SHA256 or dict(Counter(row['kind'] for row in names)) != COUNTS:
            raise ValueError('Unexpected English-name preparation')
        for name in ['readme.txt', 'CC-BY-4.0.txt']:
            (staging / name).write_bytes((sources / name).read_bytes())
        manifest = {'schemaVersion': 1, 'sourcePins': PINS, 'policy': POLICY,
                    'counts': dict(Counter(row['kind'] for row in names)),
                    'files': {name: pipeline.digest(staging / name) for name in ['english-names.jsonl', 'readme.txt', 'CC-BY-4.0.txt']}}
        (staging / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        staging.rename(output)
    print(json.dumps(manifest, sort_keys=True))


def load(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['schemaVersion'] != 1 or manifest['sourcePins'] != PINS or manifest['policy'] != POLICY:
        raise ValueError('Unrecognized GeoNames preparation')
    if manifest['counts'] != COUNTS or manifest['files'].get('english-names.jsonl') != PREPARED_SHA256:
        raise ValueError('Unexpected English-name index')
    for name, expected in manifest['files'].items():
        if pipeline.digest(directory / name) != expected:
            raise ValueError('Changed prepared GeoNames data')
    names = [json.loads(line) for line in (directory / 'english-names.jsonl').read_text().splitlines()]
    if dict(Counter(row['kind'] for row in names)) != manifest['counts']:
        raise ValueError('Incomplete GeoNames preparation')
    return names, manifest


def attach(model, rows, names):
    wanted = {row['surface'].lower() for row in rows}
    counts = Counter()
    for record in names:
        label = record['label']
        if label.lower() not in wanted:
            continue
        if record['kind'] not in {'english_admin1', 'english_alternate', 'english_feature_alternate'}:
            raise ValueError('Unknown place evidence type')
        if record['kind'] == 'english_alternate' and (record['language'] != 'en' or
                not (record['preferred'] or record['short']) or record['featureCode'] not in CURRENT_POPULATED):
            raise ValueError('Ineligible English place alias')
        if record['kind'] == 'english_feature_alternate' and (record['language'] != 'en' or
                not (record['preferred'] or record['short']) or record['featureClass'] not in GEOGRAPHIC_CLASSES or
                record['featureCode'] in HISTORIC_POPULATED or record.get('colloquial') or
                record.get('historic') or record.get('start') or record.get('end')):
            raise ValueError('Ineligible English geographic-feature alias')
        key = 'geonames-' + record['geonameId'] + '-' + record.get('alternateId', 'admin1')
        proof = dict(record, source='geonames', url='https://www.geonames.org/' + record['geonameId'] + '/',
                     sourceFile='admin1CodesASCII.txt' if record['kind'] == 'english_admin1' else 'alternateNamesV2.zip',
                     scope='English_place_label_not_original_corpus_sense', approved=True)
        model.add(key, label, label, {'name_place', 'noun_proper'}, proof, approved=True)
        counts[record['kind']] += 1
    return counts


def extend(args):
    names, manifest = load(args.prepared)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    counts = attach(model, rows, names)
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    states = [json.loads(line) for line in (args.base / 'status.jsonl').read_text().splitlines()]
    unresolved = [row for row, state in zip(rows, states) if state['decision'] == 'pending' or row['id'] in reopened]
    index = Index(args.index)
    try:
        exact = {row['word'] for _, row in index.lookup({row['surface'] for row in unresolved})}
    finally:
        index.close()
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    corrections += resolve_pending.cases(model, unresolved, exact)
    sources['geonames'] = manifest
    notices['GEONAMES-README.txt'] = (args.prepared / 'readme.txt').read_bytes()
    notices['CC-BY-4.0.txt'] = (args.prepared / 'CC-BY-4.0.txt').read_bytes()
    notices['GEONAMES-CHANGES.txt'] = ('GeoNames, https://www.geonames.org/, CC BY 4.0. Selected verbatim English place labels from the 2026-11-04 public dumps. Original IDs retained. No unlabeled/ASCII transliterations, historic/colloquial/dated aliases or inferred inflections imported. Original corpus sense is not disambiguated.\n').encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.geonames-review-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'
        pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, reopenedMachineExclusions=len(reopened),
        **{key: summary[key] for key in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('prepare')
    for name in ['sources', 'out']:
        command.add_argument('--' + name, type=Path, required=True)
    command = commands.add_parser('extend')
    for name in ['base', 'seed', 'prepared', 'index', 'out']:
        command.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.sources, args.out)
    else:
        extend(args)
