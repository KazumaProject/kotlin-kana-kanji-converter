"""Join aggregate, independently attested given-name spellings offline.

The pinned CC0 historical repack covers 1880--2017, not the current SSA ZIP.
Only literal name spellings and aggregate occurrence witnesses are retained;
no sex, demographics, person identity, corpus intent or inflections are inferred.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
from wiktionary_index import Index

REVISION = '4391c25ea10b8b0589cdbab63067de3bc8b3a628'
URL = 'https://github.com/hadley/babynames/blob/' + REVISION + '/data/babynames.rda'
PINS = {
    'babynames.rda': '1d5c601fa3c5177f4d9edb4c8c2f08fddc8d9bf04372b8a40dc6aecf92bfa324',
    'DESCRIPTION': '2f50b2c8d52212c9ecf6d5a2dcb1465a82278a6a07a7f0ed3436f44923e3882a',
    'names.R': '6713653569f58dc89cae65bf20654c82532e4ecb3e645a4cb11de978a11fba2d',
}
PREPARED_SHA = 'f182178e7c558f135c818961af152945ddd1feeed83fe4be19429d9327daf6e5'


def validate_sources(directory):
    for name, expected in PINS.items():
        if pipeline.digest(directory / name) != expected:
            raise ValueError('Changed historical SSA repack: ' + name)
    if '\nLicense: CC0\n' not in (directory / 'DESCRIPTION').read_text():
        raise ValueError('Historical repack lacks declared CC0 license')


def aggregate(records):
    names = {}
    for ordinal, (year, name, count) in enumerate(records):
        year, count = int(year), int(count)
        if not 1880 <= year <= 2017 or count < 5 or not isinstance(name, str) or not name or any(c in name for c in '\t\r\n'):
            raise ValueError('Unexpected aggregate given-name row')
        row = names.setdefault(name, dict(name=name, firstYear=year, lastYear=year,
            aggregateOccurrences=0, publishedRows=0, witnessRows=[]))
        row['firstYear'] = min(row['firstYear'], year)
        row['lastYear'] = max(row['lastYear'], year)
        row['aggregateOccurrences'] += count
        row['publishedRows'] += 1
        if len(row['witnessRows']) < 3:
            row['witnessRows'].append(ordinal)
    return [names[name] for name in sorted(names)]


def prepare(args):
    validate_sources(args.sources)
    import rdata  # Optional source preparation dependency; never a runtime API.
    data = rdata.read_rda(args.sources / 'babynames.rda')
    if list(data) != ['babynames']:
        raise ValueError('Unexpected R dataset')
    frame = data['babynames']
    if list(frame) != ['year', 'sex', 'name', 'n', 'prop'] or len(frame) != 1924665:
        raise ValueError('Unexpected historical table schema')
    values = aggregate(frame[['year', 'name', 'n']].itertuples(index=False, name=None))
    encoded = ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in values).encode()
    if hashlib.sha256(encoded).hexdigest() != PREPARED_SHA or len(values) != 97310:
        raise ValueError('Unexpected historical extraction')
    if args.out.exists():
        raise ValueError('Output exists')
    args.out.mkdir(parents=True)
    (args.out / 'given-names.jsonl').write_bytes(encoded)


def load(directory, prepared):
    validate_sources(directory)
    if pipeline.digest(prepared / 'given-names.jsonl') != PREPARED_SHA:
        raise ValueError('Changed prepared historical given names')
    return list(map(json.loads, (prepared / 'given-names.jsonl').open()))


def attach(model, rows, values):
    wanted = {row['surface'].casefold() for row in rows}
    count = 0
    for value in values:
        surface = value['name']
        if surface.casefold() not in wanted:
            continue
        key = 'ssa-given-' + hashlib.sha256(surface.encode()).hexdigest()[:24]
        proof = dict(source='historical_ssa_given_name', url=URL, revision=REVISION,
            sourcePins=PINS, preparedSha256=PREPARED_SHA, aggregateNameFact=value,
            approved=True, preferredCaseClaimed=False, individualPersonClaimed=False,
            scope='literal independently attested given-name spelling only; historical CC0 repack, not the current official SSA ZIP; no gender, demographics, corpus sense/frequency or morphology')
        model.add(key, surface, surface, {'noun', 'noun_proper', 'name_person'}, proof, approved=True)
        count += 1
    return count


def extend(args):
    values = load(args.sources, args.prepared)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    states = list(map(json.loads, (args.base / 'status.jsonl').open()))
    selected = [row for row, state in zip(rows, states) if state['decision'] in {'pending', 'exclude'}]
    count = attach(model, selected, values)
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    selected = [row for row, state in zip(rows, states) if state['decision'] == 'pending' or row['id'] in reopened]
    index = Index(args.index)
    try:
        records = list(index.lookup({row['surface'] for row in selected}))
    finally:
        index.close()
    additions = resolve_pending.cases(model, selected, {entry['word'] for _, entry in records},
        resolve_pending.ineligible_exact_words(records))
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    existing = {row['id'] for row in corrections}
    corrections += [row for row in additions if row['id'] not in existing]
    sources['historicalSsaGivenNames'] = dict(revision=REVISION, sourcePins=PINS, preparedSha256=PREPARED_SHA,
        license='CC0', years=[1880, 2017], originalRows=1924665, distinctNames=len(values),
        currentOfficialZipObtained=False,
        policy='literal standalone given-name spellings, selected existing rows only; preserve exact modern English readings and all existing case candidates; no full-name-component admission, preferred case, demographic or corpus-intent inference')
    notices['HISTORICAL-SSA-GIVEN-NAMES-NOTICE.txt'] = (
        'hadley/babynames, pinned revision ' + REVISION + ', CC0.\n' + URL + '\n'
        'Historical aggregate U.S. SSA-derived name data, 1880--2017. The current official ZIP was not obtained.\n'
        'Official catalog: https://catalog.data.gov/dataset/baby-names-from-social-security-card-applications-national-data\n'
        'Changes: extract literal name spellings and aggregate occurrence witnesses only; select existing dictionary inputs; classify name identities. No sex, demographics, individual identity, corpus sense/frequency, preferred spelling or inflections imported.\n'
        'Classification conclusions are the implementer\'s, not SSA\'s or the repack authors\'.\n').encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.given-name-review-', dir=args.out.parent) as temp:
        reviewed = Path(temp) / 'reviews.tsv'
        pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(attestedGivenNameForms=count, reopenedMachineExclusions=len(reopened),
        **{key: summary[key] for key in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ['prepare', 'extend']:
        command = commands.add_parser(name)
        for field in (['sources', 'out'] if name == 'prepare' else ['base', 'seed', 'sources', 'prepared', 'index', 'out']):
            command.add_argument('--' + field, type=Path, required=True)
    args = parser.parse_args()
    prepare(args) if args.command == 'prepare' else extend(args)
