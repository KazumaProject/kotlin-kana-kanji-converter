"""Classify existing manual name casing from independently approved name senses.

No ordinary verb/adjective interpretation is copied to a brand-like spelling.
Only letter case changes; no punctuation, words, accents or input rows are added.
The legacy surface remains intact and no preferred casing is asserted.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import extend_lexicon as extension
import lexicon_pipeline as pipeline

BASE_FLAGS = {'verb_base', 'aux_be_base', 'aux_have_base', 'aux_do_base', 'adjective_base'}


def named(values):
    return 'noun_proper' in values or any(x.startswith('name_') for x in values) or 'identifier_computer_language' in values


def attach(model, rows):
    candidates = defaultdict(list)
    for surface, ids in list(model.approved.items()):
        for key in sorted(ids):
            values = model.members[key, surface]
            if named(values) and not values & BASE_FLAGS:
                candidates[surface.lower()].append((key, surface))
    added = set()
    relations = {(r['relation'], r['source'], r['target']) for r in model.relations}
    for row in rows:
        surface = row['surface']
        if not row['id'].startswith('manual:') or surface == surface.lower() or model.approved.get(surface):
            continue
        for key, target in candidates[surface.lower()]:
            if target == surface:
                continue
            parent = model.forms[key, target]
            urls = sorted(e['url'] for e in model.evidence[key, target] if e.get('approved', True))
            proof = {'source': 'verified_manual_name_case', 'url': urls[0], 'approved': True,
                'canonicalSurface': target, 'canonicalLexemeId': key, 'legacySourceId': row['id'],
                'originalSurface': surface, 'relation': 'capitalization',
                'scope': 'existing literal manual name casing of a verified named interpretation; no ordinary lexical POS, preferred case or corpus-sense inference'}
            model.add(key, parent['lemma'], surface, set(model.members[key, target]), proof, approved=True)
            relation = 'capitalization', surface, target
            if relation not in relations:
                model.relations.append(dict(zip(['relation', 'source', 'target', 'evidence'], [*relation, urls[0]])))
                relations.add(relation)
            added.add(row['id'])
    return added


def extend(args):
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    states = [json.loads(x) for x in (args.base / 'status.jsonl').read_text().splitlines()]
    selected = [row for row, state in zip(rows, states) if state['decision'] == 'pending']
    added = attach(model, selected)
    sources['verifiedManualNameCase'] = {'policy': 'existing manual surfaces, exact letter-case equivalence to independently approved named senses only; preserve raw spelling/cost; no word boundaries, ordinary POS or preferred-case inference', 'inventorySha256': sources['inventorySha256'] if 'inventorySha256' in sources else pipeline.digest(args.base / 'inventory.jsonl')}
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    prior = args.base / 'reviewed-overrides.tsv'
    summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
        reviewed_decisions=prior if prior.is_file() else None, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(addedManualNameRows=len(added), **{k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
