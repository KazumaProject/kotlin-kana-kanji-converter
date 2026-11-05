"""Audit explicit misspelling labels without treating source absence as proof.

The pinned community list is positive typo evidence, not an exhaustive list of
invalid words. Independent approved readings or unresolved exact lexical senses
block exclusion. Later positive source evidence can reopen these machine rules.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import tempfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_wiktionary as resolver
from wiktionary_index import Index

SNAPSHOT = 'c2a990450230ec79396f1d912198563f1cce469e41af58950a1b9ec58dad1e33'
REVISION = 1199637275
URL = 'https://en.wikipedia.org/w/index.php?title=Wikipedia:Lists_of_common_misspellings/For_machines&oldid=' + str(REVISION)


def load(path):
    if pipeline.digest(path) != SNAPSHOT:
        raise ValueError('Changed Wikipedia misspelling snapshot')
    data = json.loads(path.read_text())
    page = data['query']['pages']['1687242']
    revision = page['revisions'][0]
    if revision['revid'] != REVISION or revision['timestamp'] != '2024-01-27T15:31:36Z':
        raise ValueError('Unexpected misspelling-list revision')
    pairs = defaultdict(set)
    for line in revision['slots']['main']['*'].splitlines():
        match = re.fullmatch(r'\s*([^<>]+?)->([^<>]+?)\s*', line)
        if match:
            pairs[match[1]].update(value.strip() for value in match[2].split(','))
    return pairs


def ascii_input_pairs(rows,pairs):
    """Keep listed spelling evidence when matching original lowercase ASCII keys.

    This prepares positive labels only; independent approved names or modern
    case-equivalent English senses still block the later exclusion rule.
    """
    result={word:set(values) for word,values in pairs.items()};proof={}
    folded=defaultdict(list)
    for word in pairs:folded[word.casefold()].append(word)
    for row in rows:
        word=row['surface']
        if (word in result or not row['id'].startswith('tsv:') or not word.isascii() or
                word!=word.lower() or pipeline.keyboard_reading(word)!=row['reading']):continue
        labels=sorted(folded[word.casefold()])
        if not labels:continue
        result[word]=set().union(*(pairs[label] for label in labels))
        proof[word]=dict(listedSpelling=labels[0],listedSpellings=labels,asciiInputCasefoldMatch=True,
            matchingScope='original lowercase ASCII TSV input spelling only; retain the exact listed labels and all independent-reading guards, not a case rewrite or universal nonword claim')
    return result,proof


def exclusions(model, rows, pairs, exact_entries, pending, provenance=None, allow_word_sequences=False):
    approved = defaultdict(set)
    for surface, ids in model.approved.items():
        if ids:
            approved[surface.casefold()].add(surface)
    reviews = []
    for row in rows:
        surface = row['surface']
        if surface not in pairs or approved[surface.casefold()]:
            continue
        # An unresolved modern exact English sense must be investigated, even
        # when the same spelling is also on the typo list.
        if any(resolver.eligible(entry, sense) for entry in exact_entries.get(surface, []) for sense in entry.get('senses', [])):
            continue
        if any(not entry.get('senses') or any((set(entry.get('tags', [])) | set(sense.get('tags', []))) & {'no-gloss', 'error-unknown-tag', 'error-unrecognized-form'} for sense in entry['senses'])
               for entry in exact_entries.get(surface, [])):
            continue
        # A listed typo must name at least one independently approved correction;
        # otherwise the list alone remains a lead, not an exclusion decision.
        alternatives = sorted(pairs[surface])
        verified = sorted(value for value in alternatives if approved[value.casefold()] or
            allow_word_sequences and len(value.split()) > 1 and all(approved[word.casefold()] for word in value.split()))
        if not verified:
            continue
        proof = {'source': 'wikipedia_misspelling_list', 'url': URL, 'revision': REVISION,
            'snapshotSha256': SNAPSHOT, 'listedSpelling': surface, 'listedCorrections': alternatives,
            'independentlyVerifiedCorrections': verified, 'approvedOriginalReadings': [],
            'scope': 'explicit typo label plus independently verified correction and no approved case-equivalent reading or unresolved exact English sense; not a claim of exhaustive source coverage'}
        if provenance is not None:
            proof.update(provenance.get(surface,{}))
        reviews.append(dict(row, decision='exclude', lexeme_ids='-', reason='malformed', evidence=proof['url']))
        pending.append({'sourceId': row['id'], 'surface': surface, 'reason': 'source_label_exclusion',
            'decisionReason': 'malformed', 'evidence': proof})
    return reviews


def extend(args):
    pairs = load(args.snapshot)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    states = [json.loads(x) for x in (args.base / 'status.jsonl').read_text().splitlines()]
    selected = [row for row, state in zip(rows, states) if state['decision'] == 'pending']
    folded=getattr(args,'ascii_input_casefold',False)
    pairs,provenance=ascii_input_pairs(selected,pairs) if folded else (pairs,None)
    index = Index(args.index)
    exact = defaultdict(list)
    try:
        candidates={row['surface'] for row in selected if row['surface'] in pairs}
        by_fold=defaultdict(list)
        for word in candidates:by_fold[word.casefold()].append(word)
        for _, entry in index.lookup(candidates,folded=folded):
            for word in by_fold[entry['word'].casefold()] if folded else [entry['word']]:exact[word].append(entry)
    finally:
        index.close()
    additions = exclusions(model, selected, pairs, exact, pending,provenance)
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    existing = {row['id'] for row in reviews}
    reviews += [row for row in additions if row['id'] not in existing]
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    sources['explicitMisspellingList'] = {'revision': REVISION, 'snapshotSha256': SNAPSHOT, 'url': URL,
        'asciiInputCasefold':folded,
        'policy': 'explicit listed typo plus verified correction; approved case-equivalent readings and unresolved exact English senses block exclusion; machine decisions remain auditable and reopen on later evidence; absence alone never excludes'}
    notices['WIKIPEDIA-MISSPELLINGS-NOTICE.txt'] = ('Wikipedia contributors, Lists of common misspellings/For machines, revision ' + str(REVISION) + '.\n' + URL +
        '\nCC BY-SA 4.0; full license retained in CC-BY-SA-4.0.txt.\nChanges: selected explicit misspelling/correction pairs for existing source rows; cross-checked local English lexical evidence; recorded machine exclusions only when no approved original reading or unresolved English sense exists. The upstream list is incomplete and is not used as proof that unlisted strings are invalid.\n').encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.explicit-typo-review-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'
        pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(newExplicitTypoExclusions=len(additions), **{k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'snapshot', 'index', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--ascii-input-casefold',action='store_true')
    extend(parser.parse_args())
