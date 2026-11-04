"""Import names and explicit aliases from pinned CC0 brand metadata.

No logos, artwork, colors or trademark permissions are imported. Brand status
does not establish company/product type or lexical inflections. Existing manual
names may retain their original casing/space-free spelling, with separate proof.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.parse import quote

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
from wiktionary_index import Index

REVISION = 'aac2d0877b8a8afee1792c342fac0664ed294488'
PINS = {'simple-icons.json': '7342117ab8d9cfcbcfa133b4291142d31338a697f18049df3dd86c6b0fc0bdb3',
    'LICENSE.md': '9046848b63a5c92bff14e4accca80bd987e0623b74adf9226ce5198d312b79d5',
    'DISCLAIMER.md': '5757a1f28eff735a8b5e7425478f367812d71e974530f5bedd01219480965f4a'}
URL = 'https://github.com/simple-icons/simple-icons/blob/' + REVISION + '/data/simple-icons.json'


def load(directory):
    for name, expected in PINS.items():
        if pipeline.digest(directory / name) != expected:
            raise ValueError('Changed brand metadata or notice: ' + name)
    records = json.loads((directory / 'simple-icons.json').read_text())
    # The catalog intentionally has multiple icon variants for some brands.
    # Their separate evidence survives; forms use a title/source identity.
    if len(records) != 3468 or any(not isinstance(record['title'], str) or not record['title'] or not record['source'].startswith('https://') for record in records):
        raise ValueError('Unexpected brand catalog')
    return records


def attach(model, rows, records):
    extension.ensure_categories(model, {'name_brand'})
    aliases = defaultdict(list)
    counts = Counter()
    for record in records:
        title = record['title']
        key = 'brand-' + hashlib.sha256(json.dumps([title, record['source']]).encode()).hexdigest()[:24]
        for label in [title] + record.get('aliases', {}).get('aka', []):
            proof = {'source': 'brand_metadata', 'url': URL, 'revision': REVISION, 'catalogTitle': title,
                'documentedLabel': label, 'labelKind': 'title' if label == title else 'explicit_aka',
                'brandSourceUrl': record['source'], 'approved': True,
                'scope': 'brand name or explicit aka in CC0 metadata; no artwork, company/product type, current operational status, corpus sense or inflection claim'}
            model.add(key, title, label, {'noun', 'noun_proper', 'name_brand'}, proof, approved=True)
            aliases[label.replace(' ', '').casefold()].append((key, label, proof))
            counts['documentedLabels'] += 1
    # These variants already exist in the user's manual source. The canonical
    # spaced label is attested, rather than derived by guessing word boundaries.
    # Do not apply this expansion to arbitrary source-corpus strings.
    for row in rows:
        if not row['id'].startswith('manual:'):
            continue
        original = row['surface']
        for key, label, proof in aliases[original.replace(' ', '').casefold()]:
            if original == label:
                continue
            if (' ' in original) != (' ' in label) and ' ' in original:
                continue  # Do not invent new word boundaries in a manual phrase.
            evidence = dict(proof, legacySourceId=row['id'], originalSurface=original,
                relation='existing_manual_name_case_or_space_free_alias',
                preferredCaseClaimed=False,
                scope='existing manual spelling of a documented named label; case changes or removal of literal source spaces only; no inferred ordinary POS, preferred spelling or intended corpus sense')
            lemma = model.forms[key, label]['lemma']
            model.add(key, lemma, original, {'noun', 'noun_proper', 'name_brand'}, evidence, approved=True)
            counts['existingManualAliasSenses'] += 1
    return counts


def extend(args):
    records = load(args.sources)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    counts = attach(model, rows, records)
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    states = [json.loads(x) for x in (args.base / 'status.jsonl').read_text().splitlines()]
    selected = [row for row, state in zip(rows, states) if state['decision'] == 'pending' or row['id'] in reopened]
    index = Index(args.index)
    try:
        exact = list(index.lookup({row['surface'] for row in selected}))
    finally:
        index.close()
    additions = resolve_pending.cases(model, selected, {entry['word'] for _, entry in exact},
        resolve_pending.ineligible_exact_words(exact))
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    existing = {row['id'] for row in corrections}
    corrections += [row for row in additions if row['id'] not in existing]
    sources['brandMetadata'] = {'revision': REVISION, 'files': PINS, 'url': URL,
        'policy': 'CC0 catalog titles/explicit aka only; named brand category without assumed company/product type; all local sense alternatives preserved; existing manual case/space-free aliases separately derived; no artwork imported'}
    notices['SIMPLE-ICONS-CC0.md'] = (args.sources / 'LICENSE.md').read_bytes()
    notices['SIMPLE-ICONS-DISCLAIMER.md'] = (args.sources / 'DISCLAIMER.md').read_bytes()
    notices['SIMPLE-ICONS-NAMES-NOTICE.txt'] = ('Simple Icons contributors, revision ' + REVISION + '.\n' + URL +
        '\nCC0 metadata; preserve the project disclaimer and full CC0 text.\nChanges: extracted brand titles and explicit aka labels only, mapped to separate named-brand dictionaries, and related existing manual case/space-free input aliases. No logos, SVGs, colors or other artwork imported; this classification grants no trademark or artwork rights.\n').encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.brand-name-review-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'
        pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, reopenedMachineExclusions=len(reopened), **{k: summary[k] for k in ['includedRows','excludedRows','pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'sources', 'index', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
