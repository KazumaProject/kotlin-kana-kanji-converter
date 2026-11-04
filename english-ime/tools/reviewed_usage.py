"""Apply explicit implementation-agent reviews of pinned English usage leads.

Capitalization, a name component, or a search hit never approves a candidate
automatically. External review records identify the exact quotation, spelling,
interpretation and rationale; quoted prose stays outside generated evidence.
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
from wiktionary_index import SNAPSHOT_SHA256

USAGE_SHA = '5af885ef27fdea1f0d1d56b49420aa6295e6c21d44c9c04d6cd996a6665a5f3b'
USAGE_SNAPSHOTS = {USAGE_SHA, '2417f721ba74f10ad0b75572e81e6374047afa65b9b601c99c689fb8d855c9b0'}
NAME_CATEGORIES = {'noun', 'noun_proper', 'name_person', 'name_place', 'name_organization',
    'name_product', 'name_work', 'name_fictional', 'domain_technology', 'domain_entertainment'}


def identity(row):
    # The same token can occur twice in a quotation, once independently and
    # once inside a longer name or identifier. Never collapse those witnesses.
    occurrence = hashlib.sha256(json.dumps([row['contextBefore'], row['observed'], row['contextAfter']], ensure_ascii=False).encode()).hexdigest()
    return row['form'], row['entryId'], row['senseIndex'], row['exampleIndex'], row['quoteSha256'], occurrence


def load_reviews(usage, reviews):
    observed_sha = pipeline.digest(usage)
    if observed_sha not in USAGE_SNAPSHOTS:
        raise ValueError('Changed English usage extraction')
    witnesses = {identity(row): row for row in map(json.loads, usage.open())}
    values = list(map(json.loads, reviews.open()))
    seen = set()
    for row in values:
        if row['form'] in seen or row['reviewer'] != 'implementation_agent' or not row['rationale'].strip():
            raise ValueError('Duplicate or missing explicit usage review')
        seen.add(row['form'])
        row['usageSha256'] = observed_sha
        row['witnesses'] = [witnesses[tuple(item)] for item in row['witnessIds']]
        if not row['witnesses'] or any(w['form'] != row['form'] or w['exampleType'] != 'quotation' or not w['reference'] for w in row['witnesses']):
            raise ValueError('Review requires identified quotations, not automatic examples')
    return values


def bare_observation(witness):
    observed = witness['observed']
    if witness['possessive'] and observed.endswith(("'s", '’s')):
        return observed[:-2]
    if witness['possessive'] and observed.endswith(("'", '’')):
        return observed[:-1]
    return observed


def evidence(review):
    # Retain factual identifiers and quotation hashes, not third-party prose.
    return dict(source='reviewed_english_usage', approved=True, snapshotSha256=SNAPSHOT_SHA256,
        usageExtractionSha256=review.get('usageSha256', USAGE_SHA), reviewKind='explicit_implementation_agent_review',
        humanReviewClaimed=False, rationale=review['rationale'],
        url='https://en.wiktionary.org/wiki/' + quote(review['witnesses'][0]['headword'].replace(' ', '_'), safe='') + '#English',
        witnesses=[{key: row[key] for key in ['entryId', 'headword', 'senseIndex', 'exampleIndex', 'observed', 'possessive', 'quoteSha256', 'reference']} for row in review['witnesses']],
        scope='reviewed independent English usage of this literal name or positive malformed-fragment evidence; no automatic POS from the containing entry, corpus intent, preferred spelling or inherited morphology')


def attach(model, rows, reviews, corrections, exclusions, audit):
    by_form = defaultdict(list)
    for row in rows:
        by_form[row['surface'].casefold()].append(row)
    counts = Counter()
    for review in reviews:
        selected = by_form[review['form'].casefold()]
        if not selected:
            continue
        proof = evidence(review)
        if review['decision'] == 'include_name':
            target = review['target']
            members = set(review['categories'])
            if not {'noun', 'noun_proper'} <= members or not members <= NAME_CATEGORIES:
                raise ValueError('Usage name review cannot infer lexical inflections or ordinary POS')
            if target.casefold() != review['form'].casefold() or not any(bare_observation(w) == target and not w['inKnownFullName'] and not w['embeddedInIdentifier'] for w in review['witnesses']):
                raise ValueError('Name review lacks the exact independent spelling witness')
            extension.ensure_categories(model, members)
            key = 'usage-name-' + hashlib.sha256(json.dumps([target, sorted(members)]).encode()).hexdigest()[:24]
            model.add(key, target, target, members, proof, approved=True)
            for row in selected:
                surface = row['surface']
                if surface == target:
                    continue
                if row['id'].startswith('manual:'):
                    model.add(key, target, surface, members, dict(proof, relation='existing_manual_name_case',
                        originalSurface=surface, legacySourceId=row['id'], preferredCaseClaimed=False), approved=True)
                elif surface == surface.lower() and pipeline.keyboard_reading(target) == row['reading']:
                    # This explicit review establishes a valid named reading;
                    # it does not resolve every other sense or corpus intent.
                    existing = {c['target']:dict(c) for c in corrections if c['id'] == row['id']}
                    existing.setdefault(target, dict(id=row['id'], source=surface, target=target, evidence=proof['url']))
                    corrections[:] = [c for c in corrections if c['id'] != row['id']]
                    spelling = any(value.casefold()!=surface.casefold() for value in existing)
                    relation = ('input_spelling_correction' if len(existing)==1 else 'input_spelling_candidates') if spelling else ('case_correction' if len(existing)==1 else 'case_candidates')
                    for value, item in sorted(existing.items()):
                        corrections.append(dict(item, relation=relation))
                else:
                    raise ValueError('Usage review cannot change input spelling or reading')
            counts['reviewedNameSurfaces'] += 1
        elif review['decision'] == 'exclude_fragment':
            if any(model.approved.get(surface) for surface in model.approved if surface.casefold() == review['form'].casefold()):
                raise ValueError('Fragment exclusion conflicts with an independently approved reading')
            kind = review['fragmentKind']
            witnesses = review['witnesses']
            if len({w['quoteSha256'] for w in witnesses}) < 2:
                raise ValueError('Fragment exclusion needs two independent quotation witnesses')
            if kind == 'negative_contraction_prefix':
                valid = all(w['contextAfter'].startswith(('′t', "[']t")) and not w['possessive'] for w in witnesses)
            elif kind == 'censored_word_suffix':
                valid = all(w['contextBefore'].lower().endswith('f*') and w['observed'].casefold() == 'cking' for w in witnesses)
            else:
                raise ValueError('Unknown positive fragment evidence rule')
            if not valid:
                raise ValueError('Quotation does not demonstrate the claimed word fragment')
            for row in selected:
                if row['surface'] != row['surface'].lower():
                    raise ValueError('Fragment review cannot remove a separately cased name')
                exclusions.append(dict(row, decision='exclude', lexeme_ids='-', reason='malformed', evidence=proof['url']))
                audit.append(dict(sourceId=row['id'], surface=row['surface'], reason='reviewed_positive_word_fragment',
                    evidence=proof, originalRowPreserved=True, absenceOnlyExclusion=False))
                counts['excludedFragmentRows'] += 1
        else:
            raise ValueError('Unknown explicit usage review decision')
    return counts


def extend(args):
    reviews = load_reviews(args.usage, args.reviews)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    states = list(map(json.loads, (args.base / 'status.jsonl').open()))
    selected = [row for row, state in zip(rows, states) if state['decision'] != 'exclude']
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    prior = args.base / 'reviewed-overrides.tsv'
    decisions = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    counts = attach(model, selected, reviews, corrections, decisions, pending)
    sources['reviewedEnglishUsage'] = dict(snapshotSha256=SNAPSHOT_SHA256, usageSha256=pipeline.digest(args.usage),
        reviewsSha256=pipeline.digest(args.reviews), reviewer='implementation_agent', humanReviewClaimed=False,
        policy='explicit individually reviewed standalone usages; complete-name embeddings and identifiers rejected; positive fragment evidence plus conflict checks for exclusions; original input rows and unresolved alternative-sense evidence preserved; no quotation prose redistributed')
    notices['REVIEWED-ENGLISH-USAGE-NOTICE.txt'] = (
        'English Wiktionary contributors; Wiktextract snapshot ' + SNAPSHOT_SHA256 + '.\n'
        'Existing Wiktionary/Wiktextract attribution and license notices apply. Only name facts, source references and quotation hashes are retained; quoted source prose is not redistributed.\n'
        'Changes: individual implementation-agent review of standalone named uses and positive word-fragment evidence. This is not a claim of human review, source endorsement, universal preferred casing, or exhaustive corpus-sense disambiguation.\n').encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.usage-review-', dir=args.out.parent) as temp:
        path = Path(temp) / 'reviews.tsv'
        pipeline.table(path, 'decisions', decisions)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=path, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, **{key: summary[key] for key in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ['base', 'seed', 'usage', 'reviews', 'out']:
        parser.add_argument('--' + field, type=Path, required=True)
    extend(parser.parse_args())
