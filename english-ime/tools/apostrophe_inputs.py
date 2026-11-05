"""Map existing apostrophe-free keys to independently recorded English forms.

No possessive/contraction is invented: the complete punctuated form and its POS
must actually exist in the pinned ESDB source and pass ordinary admission. Raw
rows/costs remain intact; the omitted-apostrophe input is not claimed attested.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sqlite3
import tempfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
from wiktionary_index import Index


def input_key(surface):
    if not re.fullmatch(r"[A-Za-z]+(?:'[A-Za-z]+)+", surface):
        return None
    return surface.replace("'", '').casefold()


def source_candidates(directory, rows):
    wanted = {r['surface'] for r in rows if re.fullmatch('[a-z]+', r['surface'])}
    connection = sqlite3.connect((directory / 'esdb.db').resolve().as_uri() + '?mode=ro', uri=True)
    try:
        words = {r[0] for r in connection.execute("""select distinct e.word from entries e join scowl_ s using(word_id)
            where instr(e.word, ?) > 0 and s.size<=60 and s.variant_level<=6
              and s.group_rank not in ('@','~') and s.entry_rank not in ('@','~') and s.usage_note=''""", ("'",))}
    finally:
        connection.close()
    return {word for word in words if input_key(word) in wanted}


def attach(model, rows, candidates, corrections, audit, restricted=()):
    by_key = defaultdict(set); counts = Counter()
    for surface in candidates:
        key = input_key(surface)
        if key and surface not in restricted and model.approved.get(surface):
            by_key[key].add(surface)
    for row in rows:
        raw = row['surface']
        if not re.fullmatch('[a-z]+', raw):
            continue
        targets = sorted(target for target in by_key[raw] if pipeline.keyboard_reading(target) == row['reading'])
        if not targets:
            continue
        existing = {r['target']: dict(r) for r in corrections if r['id'] == row['id']}
        for target in targets:
            urls = [p['url'] for k in model.approved[target] for p in model.evidence[k, target]
                    if p.get('approved', True) and not p.get('requiresFullNamedContext', False)]
            if not urls:
                raise ValueError('Punctuated form lacks independent lexical evidence')
            existing.setdefault(target, dict(id=row['id'], source=raw, target=target, evidence=min(urls)))
        if model.approved.get(raw):
            urls = [p['url'] for k in model.approved[raw] for p in model.evidence[k, raw]
                    if p.get('approved', True) and not p.get('requiresFullNamedContext', False)]
            if urls:
                existing.setdefault(raw, dict(id=row['id'], source=raw, target=raw, evidence=min(urls)))
        corrections[:] = [r for r in corrections if r['id'] != row['id']]
        relation = 'input_spelling_correction' if len(existing) == 1 else 'input_spelling_candidates'
        corrections += [dict(value, relation=relation) for _, value in sorted(existing.items())]
        audit.append(dict(sourceId=row['id'], surface=raw, reason='verified_apostrophe_input',
            candidateSurfaces=targets, rawSpellingAttestationClaimed=False, corpusSenseClaimed=False,
            arbitraryLetterEditApplied=False, originalRowPreserved=True))
        counts['reviewedInputRows'] += 1
    return counts


def extend(args):
    states = list(map(json.loads, (args.base / 'status.jsonl').open()))
    selected_ids = {s['id'] for s in states if s['decision'] == 'pending'}
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    selected = [r for r in rows if r['id'] in selected_ids]
    candidates = source_candidates(args.esdb, selected)
    # This verifies the source revision/database/notices and applies the normal
    # vetted-source/POS/morphology policy; a string match alone never approves.
    manifest, imported = extension.import_esdb(model, candidates, args.esdb, pending)
    index = Index(args.index)
    try:
        entries = list(index.lookup(candidates))
    finally:
        index.close()
    restricted = resolve_pending.ineligible_exact_words(entries)
    path = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(path, 'corrections') if path.is_file() else []
    counts = attach(model, selected, candidates, corrections, pending, restricted)
    path = args.base / 'reviewed-overrides.tsv'
    decisions = pipeline.read_table(path, 'decisions') if path.is_file() else []
    decisions, reopened = resolve_pending.revalidate_machine_reviews(model, decisions, pending, corrections)
    sources['verifiedApostropheInputs'] = dict(revision=manifest['revision'], databaseSha256=manifest['databaseSha256'],
        candidates=len(candidates), policy='existing lowercase keys only; complete explicitly recorded and independently approved punctuated English forms, exact letter sequence, no generated possessive, contraction or case guess; original raw spelling and cost preserved without claiming raw-spelling attestation')
    for name in manifest['notices']:
        notices[name] = (args.esdb / name).read_bytes()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.apostrophe-inputs-', dir=args.out.parent) as temp:
        reviewed = Path(temp) / 'reviews.tsv'; pipeline.table(reviewed, 'decisions', decisions)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, sourceRecordsImported=imported, reopenedMachineExclusions=len(reopened),
        **{k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']})))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'esdb', 'index', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
