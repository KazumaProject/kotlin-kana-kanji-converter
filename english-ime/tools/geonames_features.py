"""Verify English geographic labels against the complete GeoNames feature table.

Preparation is local and bound to the immutable input inventory. A preferred
English alias alone cannot establish the feature class; both pinned tables must
agree on the numeric place ID. No coordinates or transliterations are imported.
"""
import argparse
from collections import Counter
import io
import json
from pathlib import Path
import tempfile
import zipfile

import extend_lexicon as extension
import geonames
import lexicon_pipeline as pipeline
import resolve_pending
from wiktionary_index import Index

ALL_COUNTRIES_SHA256 = '9b3844727e366dea09925adff8edec5e0f78e50df0965934a9598d0c00de67ce'
PINS = {name: geonames.PINS[name] for name in ['alternateNamesV2.zip', 'readme.txt', 'CC-BY-4.0.txt']}
POLICY = 'verbatim en preferred/short names joined by geonameId to complete feature table; known geographic class; no historic populated features, historic/colloquial/dated aliases, ASCII transliterations or inferred corpus sense/morphology'


def english_aliases(stream, wanted):
    for number, line in enumerate(stream, 1):
        fields = line.rstrip('\n').split('\t')
        if len(fields) != 10:
            raise ValueError('Invalid alternate row ' + str(number))
        aid, gid, language, label, preferred, short, colloquial, historic, start, end = fields
        if (language != 'en' or label.lower() not in wanted or preferred != '1' and short != '1' or
                colloquial == '1' or historic == '1' or start or end):
            continue
        if not aid.isdecimal() or not gid.isdecimal() or not label.strip():
            raise ValueError('Invalid English geographic alias')
        yield {'kind': 'english_feature_alternate', 'alternateId': aid, 'geonameId': gid, 'label': label,
               'line': number, 'language': language, 'preferred': preferred == '1', 'short': short == '1',
               'colloquial': False, 'historic': False, 'start': '', 'end': ''}


def feature_matches(stream, wanted):
    for number, line in enumerate(stream, 1):
        fields = line.rstrip('\n').split('\t')
        if len(fields) != 19:
            raise ValueError('Invalid feature row ' + str(number))
        if fields[0] not in wanted:
            continue
        if fields[6] not in geonames.GEOGRAPHIC_CLASSES or fields[7] in geonames.HISTORIC_POPULATED:
            continue
        yield fields[0], {'featureClass': fields[6], 'featureCode': fields[7],
                          'countryCode': fields[8], 'featureSourceLine': number}


def source_pins():
    return dict(PINS, **{'allCountries.zip': ALL_COUNTRIES_SHA256})


def prepare(args):
    if args.out.exists():
        raise ValueError('Preserve existing GeoNames preparation')
    pipeline.verify(args.base)
    for name, expected in source_pins().items():
        if pipeline.digest(args.sources / name) != expected:
            raise ValueError('Changed GeoNames feature source: ' + name)
    rows = pipeline.inventory(args.base / 'inventory.jsonl')
    with zipfile.ZipFile(args.sources / 'alternateNamesV2.zip') as archive:
        with io.TextIOWrapper(archive.open('alternateNamesV2.txt'), encoding='utf-8') as stream:
            aliases = list(english_aliases(stream, {row['surface'].lower() for row in rows}))
    wanted = {record['geonameId'] for record in aliases}
    with zipfile.ZipFile(args.sources / 'allCountries.zip') as archive:
        with io.TextIOWrapper(archive.open('allCountries.txt'), encoding='utf-8') as stream:
            features = {}
            for identifier, feature in feature_matches(stream, wanted):
                if identifier in features:
                    raise ValueError('Duplicate geographic feature ID')
                features[identifier] = feature
    names = [dict(record, **features[record['geonameId']]) for record in aliases if record['geonameId'] in features]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.geographic-features-', dir=args.out.parent) as temporary:
        staging = Path(temporary) / 'prepared'
        staging.mkdir()
        pipeline.jsonl(staging / 'english-names.jsonl', names)
        for name in ['readme.txt', 'CC-BY-4.0.txt']:
            (staging / name).write_bytes((args.sources / name).read_bytes())
        manifest = {'schemaVersion': 1, 'sourcePins': source_pins(), 'policy': POLICY,
                    'inventorySha256': pipeline.digest(args.base / 'inventory.jsonl'),
                    'counts': {'labels': len(names), 'featureIds': len(features),
                               'featureClasses': dict(Counter(r['featureClass'] for r in names))},
                    'files': {n: pipeline.digest(staging / n) for n in ['english-names.jsonl', 'readme.txt', 'CC-BY-4.0.txt']}}
        (staging / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        staging.rename(args.out)
    print(json.dumps(manifest, sort_keys=True))


def load(directory, inventory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if (manifest['schemaVersion'] != 1 or manifest['sourcePins'] != source_pins() or manifest['policy'] != POLICY or
            manifest['inventorySha256'] != pipeline.digest(inventory)):
        raise ValueError('Changed geographic feature source, policy or inventory')
    for name, expected in manifest['files'].items():
        if pipeline.digest(directory / name) != expected:
            raise ValueError('Changed prepared geographic labels')
    names = [json.loads(line) for line in (directory / 'english-names.jsonl').read_text().splitlines()]
    if len(names) != manifest['counts']['labels']:
        raise ValueError('Incomplete geographic feature preparation')
    return names, manifest


def extend(args):
    names, manifest = load(args.prepared, args.base / 'inventory.jsonl')
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    counts = geonames.attach(model, rows, names)
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    states = [json.loads(line) for line in (args.base / 'status.jsonl').read_text().splitlines()]
    unresolved = [row for row, state in zip(rows, states) if state['decision'] == 'pending' or row['id'] in reopened]
    index = Index(args.index)
    try:
        exact = {row['word'] for _, row in index.lookup({r['surface'] for r in unresolved})}
    finally:
        index.close()
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    corrections += resolve_pending.cases(model, unresolved, exact)
    sources['geonamesFeatures'] = manifest
    notices['GEONAMES-README.txt'] = (args.prepared / 'readme.txt').read_bytes()
    notices['CC-BY-4.0.txt'] = (args.prepared / 'CC-BY-4.0.txt').read_bytes()
    notices['GEONAMES-FEATURE-CHANGES.txt'] = b'GeoNames, https://www.geonames.org/, CC BY 4.0. Selected verbatim English geographic labels from the 2026-11-04 public dumps, with numeric IDs joined to complete feature records. No coordinates, ASCII transliterations or inferred inflections imported. Labels do not disambiguate the original corpus sense.\n'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.geographic-review-', dir=args.out.parent) as temporary:
        review = Path(temporary) / 'review.tsv'
        pipeline.table(review, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=review, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, reopenedMachineExclusions=len(reopened),
        **{k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('prepare')
    for name in ['base', 'sources', 'out']:
        command.add_argument('--' + name, type=Path, required=True)
    command = commands.add_parser('extend')
    for name in ['base', 'seed', 'prepared', 'index', 'out']:
        command.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args)
    else:
        extend(args)
