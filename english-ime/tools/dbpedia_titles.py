"""Use exact titles from the pinned public DBpedia14 classification dataset.

Only title/label columns are read; abstracts are neither imported nor treated
as lexical senses. Dataset labels are machine-derived. Artist includes groups,
Company can include brands: neither establishes a more specific name category.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
import resolve_wiktionary as resolver
import restricted_references
from wiktionary_index import Index

REVISION = '9abd46cf7fc8b4c64290f26993c540b92aa145ac'
FILES = {'train-00000-of-00001.parquet': '0640e4664a99cc94c47db1d7b2e01c14455d5bbecb8183ad1f93bde59f3f28ee',
         'test-00000-of-00001.parquet': '05fed41640e97f93ffd442757f6a84170348cf0c7500ecbda9e95ddcd928c631'}
LICENSE_SHA = '3f941b3b89cf7b8370ceb83cc76d2120d471b58735d8ca60238a751a48d7f72f'
CLASSES = ['Company', 'EducationalInstitution', 'Artist', 'Athlete', 'OfficeHolder', 'MeanOfTransportation',
           'Building', 'NaturalPlace', 'Village', 'Animal', 'Plant', 'Album', 'Film', 'WrittenWork']
PREPARED_PINS = {'manifest.json': 'f6ad95ab167086ff7a852ca93340b945f67f5ea2d86a7e677e402b755f2696e1', 'titles.json': '216c066db75d1aef1f3a613104f65a51ec81ad104c9bbfc59ea9887f1d64fc14'}


def prepare(args):
    # Optional preparation dependency; extend/revalidation remain stdlib-only.
    import pyarrow.parquet as pq
    pipeline.verify(args.base)
    states = [json.loads(x) for x in (args.base / 'status.jsonl').read_text().splitlines()]
    wanted = {r['surface'].casefold() for r in states if r['decision'] in {'pending', 'exclude'}}
    counts = Counter(); matches = []
    for filename, expected in FILES.items():
        path = args.sources / filename
        if pipeline.digest(path) != expected:
            raise ValueError('Changed DBpedia14 file')
        offset = 0
        for batch in pq.ParquetFile(path).iter_batches(columns=['label', 'title']):
            for row in batch.to_pylist():
                label = row['label']; title = row['title']
                if label not in range(14) or not title or any(c in title for c in '\t\r\n'):
                    raise ValueError('Invalid title/label row')
                counts[label] += 1
                if title.casefold() in wanted:
                    matches.append({'file': filename, 'row': offset, 'label': label, 'title': title})
                offset += 1
    if counts != Counter({i: 45000 for i in range(14)}) or args.out.exists():
        raise ValueError('Unexpected dataset size or existing output')
    args.out.mkdir(parents=True)
    path = args.out / 'titles.json'; path.write_text(json.dumps(matches, indent=2, ensure_ascii=False) + '\n')
    manifest = {'revision': REVISION, 'sourceFiles': FILES, 'baseManifestSha256': pipeline.digest(args.base / 'manifest.json'),
        'titlesSha256': pipeline.digest(path), 'matches': len(matches), 'classRows': dict(sorted(counts.items())),
        'scope': 'exact casefold title match to existing pending/excluded surfaces; no abstracts, title qualifier removal, aliases or preferred-case inference'}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps(manifest, sort_keys=True))


def attach(model, matches):
    for row in matches:
        title, label = row['title'], row['label']
        if row['file'] not in FILES or not isinstance(row['row'], int) or row['row'] < 0 or label not in range(14):
            raise ValueError('Invalid DBpedia title identity')
        values = {'noun'}
        if label in {0, 1, 2, 3, 4, 6, 7, 8, 11, 12, 13}:
            values.add('noun_proper')
        if label == 1:
            values.add('name_organization')
        elif label in {3, 4}:
            values.add('name_person')
        elif label in {6, 7, 8}:
            values.add('name_place')
        if label in {9, 10}:
            values.add('domain_science')
        elif label in {11, 12}:
            values.add('domain_entertainment')
        proof = {'source': 'dbpedia14_title', 'url': 'https://huggingface.co/datasets/fancyzhx/dbpedia_14/resolve/' +
            REVISION + '/dbpedia_14/' + row['file'] + '#row-' + str(row['row']), 'revision': REVISION,
            'file': row['file'], 'fileSha256': FILES[row['file']], 'row': row['row'], 'title': title,
            'datasetLabel': CLASSES[label], 'annotation': 'machine-derived dataset class; not human lexical review',
            'scope': 'exact English dataset title and coarse entity class; no corpus sense, current office/status or inflection claim', 'approved': True}
        key = 'dbpedia14-' + hashlib.sha256(json.dumps([row['file'], row['row'], label, title]).encode()).hexdigest()[:24]
        model.add(key, title, title, values, proof, approved=True)


def extend(args):
    if not PREPARED_PINS:
        raise ValueError('DBpedia title extraction has not been pinned')
    for name, expected in PREPARED_PINS.items():
        if pipeline.digest(args.prepared / name) != expected:
            raise ValueError('Changed prepared title source')
    manifest = json.loads((args.prepared / 'manifest.json').read_text())
    if manifest['revision'] != REVISION or manifest['sourceFiles'] != FILES:
        raise ValueError('Unexpected title dataset source')
    for name, expected in FILES.items():
        if pipeline.digest(args.sources / name) != expected:
            raise ValueError('Changed DBpedia14 source')
    if pipeline.digest(args.sources / 'CC-BY-SA-3.0.txt') != LICENSE_SHA:
        raise ValueError('Changed source license')
    matches = json.loads((args.prepared / 'titles.json').read_text())
    if len(matches) != manifest['matches']:
        raise ValueError('Changed title row count')
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    attach(model, matches)
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    states = [json.loads(x) for x in (args.base / 'status.jsonl').read_text().splitlines()]
    unresolved = [r for r, s in zip(rows, states) if s['decision'] == 'pending' or r['id'] in reopened]
    index = Index(args.index)
    try:
        records = resolver.load_closure(index, {r['surface'] for r in unresolved})
    finally:
        index.close()
    disqualified, _ = restricted_references.disqualified_roles(records)
    additions = resolve_pending.cases(model, unresolved, {r['word'] for _, r in records}, disqualified)
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    existing = {r['id'] for r in corrections}
    corrections += [r for r in additions if r['id'] not in existing]
    sources['dbpedia14Titles'] = {'revision': REVISION, 'files': FILES, 'preparedPins': PREPARED_PINS,
        'policy': manifest['scope'] + '; coarse machine labels only, Artist never implies an individual, Company never implies a separate organization rather than a brand; no inflections or active/current status claim'}
    notices['DBPEDIA14-NOTICE.txt'] = ('DBpedia ontology classification dataset, Xiang Zhang, Junbo Zhao and Yann LeCun (2015), from DBpedia 2014/Wikipedia.\n'
        'https://arxiv.org/abs/1509.01626 ; https://github.com/zhangxiangxiao/Crepe ; https://huggingface.co/datasets/fancyzhx/dbpedia_14/tree/' + REVISION +
        '\nCC BY-SA 3.0, dataset card. Changes: exact title selection and coarse named dictionary memberships; retain split file, row and machine class; no abstracts imported. Source machine labels do not constitute human lexical review.\n').encode()
    notices['CC-BY-SA-3.0.txt'] = (args.sources / 'CC-BY-SA-3.0.txt').read_bytes()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.dbpedia-title-review-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'; pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(sourceTitles=len(matches), reopenedMachineExclusions=len(reopened),
        **{k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ['prepare', 'extend']:
        part = sub.add_parser(command)
        for name in (['base', 'sources', 'out'] if command == 'prepare' else ['base', 'sources', 'prepared', 'seed', 'index', 'out']):
            part.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    (prepare if args.command == 'prepare' else extend)(args)
