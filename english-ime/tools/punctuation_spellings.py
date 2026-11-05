"""Resolve exact attested punctuation variants of existing ASCII input keys.

No edit distance, extra letters, accent stripping or inferred word boundaries.
Every corrected output is an independently approved English lexical entry.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import tempfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
import resolve_wiktionary as resolver
from wiktionary_index import Index


def corrections_for(model, rows, exact_words):
    targets = defaultdict(set)
    for surface, ids in model.approved.items():
        key = pipeline.keyboard_reading(surface)
        if ids and key:
            targets[key].add(surface)
    result = []
    for row in rows:
        word = row['surface']
        if (word != word.lower() or word in exact_words or model.approved.get(word) or
                pipeline.keyboard_reading(word) != row['reading']):
            continue
        candidates = sorted(targets[row['reading']] - {word})
        if not candidates:
            continue
        relation = 'input_spelling_correction' if len(candidates) == 1 else 'input_spelling_candidates'
        for target in candidates:
            url = min(e['url'] for key in model.approved[target] for e in model.evidence[key, target] if e.get('approved', True))
            result.append({'id': row['id'], 'source': word, 'target': target, 'relation': relation, 'evidence': url})
    return result


def extend(args):
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    states = [json.loads(x) for x in (args.base / 'status.jsonl').read_text().splitlines()]
    unresolved = [r for r, s in zip(rows, states) if s['decision'] == 'pending']
    wanted = {r['reading'] for r in unresolved if pipeline.keyboard_reading(r['surface']) == r['reading']}
    index = Index(args.index)
    try:
        spellings = {word for word, in index.connection.execute('select distinct word from entries')
                     if pipeline.keyboard_reading(word) in wanted}
        exact = {e['word'] for _, e in index.lookup({r['surface'] for r in unresolved})}
        records = resolver.load_closure(index, spellings)
        imported = resolver.import_records(model, records, spellings, pending)
        snapshot = index.manifest['snapshotSha256']
    finally:
        index.close()
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    additions = corrections_for(model, unresolved, exact)
    existing = {r['id'] for r in corrections}
    corrections += [r for r in additions if r['id'] not in existing]
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    sources['verifiedPunctuationSpellings'] = {'snapshotSha256': snapshot,
        'policy': 'no exact English entry or independently approved original; only case/apostrophe/hyphen/dot/slash normalization with the same ordered ASCII letters and digits; every candidate independently approved; all ambiguity retained; no corpus-sense claim, new raw rows, accent stripping or inferred spaces'}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.punctuation-review-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'; pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(newCorrectedRows=len({r['id'] for r in additions}), reopenedMachineExclusions=len(reopened),
        **{k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'index', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
