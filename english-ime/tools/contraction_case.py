"""Retain initial-capital manual contractions with their attested identities.

Only an independently approved contraction reading can be copied. Ordinary
nouns/verbs sharing the spelling, brand casing and invented base roles cannot.
"""
import argparse
import json
from pathlib import Path
import tempfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
import resolve_wiktionary as resolver
from wiktionary_index import Index

BASE_FLAGS = {'verb_base','aux_be_base','aux_have_base','aux_do_base','adjective_base'}


def attach(model, rows):
    adopted = set()
    relations = {(row['relation'], row['source'], row['target']) for row in model.relations}
    for row in rows:
        original = row['surface']
        if (not row['id'].startswith('manual:') or not original or not original[0].isupper() or
                original[1:] != original[1:].lower() or "'" not in original):
            continue
        lower = original.lower()
        for key in sorted(model.approved.get(lower, ())):
            values = model.members[key, lower]
            if 'contraction' not in values or values & BASE_FLAGS:
                continue
            parent = model.forms[key, lower]
            url = min(proof['url'] for proof in model.evidence[key, lower] if proof.get('approved', True))
            proof = {'source': 'verified_contraction_case', 'url': url, 'approved': True,
                'legacySourceId': row['id'], 'canonicalSurface': lower, 'canonicalLexemeId': key,
                'scope': 'initial-capital form already present in manual source, of an independently attested contraction; same lexeme and lemma, no other spelling senses or infinitive inference'}
            model.add(key, parent['lemma'], original, values, proof, approved=True)
            relation = 'capitalization', original, lower
            if relation not in relations:
                model.relations.append(dict(zip(['relation','source','target','evidence'], [*relation, url])))
                relations.add(relation)
            adopted.add(row['id'])
    return adopted


def extend(args):
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    states = [json.loads(x) for x in (args.base / 'status.jsonl').read_text().splitlines()]
    selected = [row for row, state in zip(rows, states) if state['decision'] == 'pending']
    index = Index(args.index)
    try:
        words = {row['surface'] for row in selected}
        words.update(word.lower() for word in list(words) if "'" in word)
        records = resolver.load_closure(index, words)
        counts = resolver.import_records(model, records, words, pending)
        sources['contractionLexicalIndex'] = index.manifest
    finally:
        index.close()
    adopted = attach(model, selected)
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    sources['contractionCasePolicy'] = 'existing manual initial-capital spelling of independently approved contraction senses only; preserve lexical identity, lemma and raw input; no copying of unrelated noun/verb readings or base roles; eligible source-labeled auxiliary contractions need not invent infinitives'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.contraction-case-review-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'; pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, addedCapitalizedContractionRows=len(adopted), reopenedMachineExclusions=len(reopened),
        **{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','index','out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
