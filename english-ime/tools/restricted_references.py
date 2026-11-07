"""Resolve explicitly disqualified form/spelling chains without using absence.

An unlabelled form inherits a restriction only if every same-role reading of
its explicit target is disqualified. Missing entries, unknown roles, extraction
errors, cycles and independently valid readings never establish an exclusion.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import tempfile
from urllib.parse import quote

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
import resolve_wiktionary as resolver
from wiktionary_index import Index

ERRORS = {'no-gloss', 'error-unknown-tag', 'error-unrecognized-form'}


def disqualified_roles(records):
    groups = defaultdict(list)
    for number, entry in records:
        groups[entry['word'], entry['pos']].append((number, entry))
    established = {}
    for _ in range(24):
        additions = {}
        for key, entries in groups.items():
            if key in established or any(not row.get('senses') for _, row in entries):
                continue
            reasons = []
            for number, row in entries:
                for ordinal, sense in enumerate(row['senses'], 1):
                    tags = set(row.get('tags', [])) | set(sense.get('tags', []))
                    proof = {'entryId': number, 'sense': ordinal, 'tags': sorted(tags)}
                    if tags & ERRORS:
                        reasons.append(None)
                    elif tags & (pipeline.RESTRICTED | {'misspelling'}):
                        reasons.append(dict(proof, basis='explicit_label'))
                    else:
                        references = [r['word'] for relation in ['alt_of', 'form_of'] for r in sense.get(relation, []) if 'word' in r]
                        target = (references[0], row['pos']) if len(set(references)) == 1 else None
                        reasons.append(dict(proof, basis='same_role_reference', target=list(target)) if target in established else None)
            if reasons and all(r is not None for r in reasons):
                additions[key] = reasons
        if not additions:
            break
        established.update(additions)
    roles_by_word = defaultdict(set)
    for word, pos in groups:
        roles_by_word[word].add((word, pos))
    words = {word for word, roles in roles_by_word.items() if roles <= established.keys()}
    return words, established


def extend(args):
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    states = [json.loads(x) for x in (args.base / 'status.jsonl').read_text().splitlines()]
    unresolved = [row for row, state in zip(rows, states) if state['decision'] == 'pending']
    index = Index(args.index)
    try:
        records = resolver.load_closure(index, {r['surface'] for r in unresolved})
        snapshot = index.manifest['snapshotSha256']
    finally:
        index.close()
    words, proof = disqualified_roles(records)
    previous = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(previous, 'corrections') if previous.is_file() else []
    additions = resolve_pending.cases(model, unresolved, {r['word'] for _, r in records}, words)
    prior_ids = {r['id'] for r in corrections}
    corrections += [r for r in additions if r['id'] not in prior_ids]
    mapped = {r['id'] for r in corrections}
    previous = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(previous, 'decisions') if previous.is_file() else []
    count = 0
    for row in unresolved:
        if row['surface'] not in words or row['id'] in mapped or model.approved.get(row['surface']):
            continue
        url = 'https://en.wiktionary.org/wiki/' + quote(row['surface'].replace(' ', '_'), safe='') + '#English'
        reviews.append(dict(row, decision='exclude', lexeme_ids='-', reason='ineligible_reference', evidence=url))
        pending.append({'sourceId': row['id'], 'surface': row['surface'], 'reason': 'source_label_exclusion',
            'decisionReason': 'ineligible_reference', 'evidence': {'source': 'wiktionary', 'url': url,
            'snapshotSha256': snapshot, 'policy': 'every exact sense explicitly disqualified or linked solely to disqualified same-role readings; absence never a reason'}})
        count += 1
    # Keep the complete dependency proof, including terminal source IDs/tags.
    pending.append({'reason': 'reference_restriction_proof', 'snapshotSha256': snapshot,
                    'roles': [{'word': key[0], 'pos': key[1], 'senses': value} for key, value in sorted(proof.items())]})
    sources['restrictedReferencePolicy'] = 'all exact senses explicitly restricted/misspelled or all explicit same-role reference targets recursively so; cycles/errors/missing entries never excluded; independently verified exact/canonical interpretations preserved'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.restricted-reference-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'; pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(newCaseRows=len({r['id'] for r in additions}), newExclusions=count,
        **{k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'index', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
