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
CODESPELL_REVISION='b53e95197f7c799674c785028a182e2dfd1df881'
CODESPELL_PINS={'dictionary.txt':'154078a5877ef228b8c8b28d5c69991b053947ea8685717599044988e172ddd7',
    'README.rst':'aeb6dbb0177013821bfb6920e0e101a68d6dc1688971189ee1ac97382d249dc2',
    'CC-BY-SA-3.0.txt':'3f941b3b89cf7b8370ceb83cc76d2120d471b58735d8ca60238a751a48d7f72f'}


def reviewed_codespell_pairs(directory,rows,reviews):
    """Select individually reviewed data facts, never import the GPL program."""
    for name,pin in CODESPELL_PINS.items():
        if pipeline.digest(directory/name)!=pin:raise ValueError('Changed spelling dictionary or license: '+name)
    lines=(directory/'dictionary.txt').read_text().splitlines();originals={r['id']:r for r in rows};seen=set();pairs={};provenance={}
    for review in reviews:
        row=originals[review['id']];line=review['line']
        if (row['id'] in seen or not row['id'].startswith('tsv:') or row['surface']!=row['surface'].lower() or
                any(review.get(k)!=row[k] for k in ['id','reading','surface','cost']) or
                review.get('decision')!='exclude_typo' or review.get('reviewer')!='implementation_agent' or
                not review.get('rationale','').strip() or type(line) is not int or not 1<=line<=len(lines)):
            raise ValueError('Missing or changed explicit spelling-label review')
        wrong,separator,correct=lines[line-1].partition('->')
        if (not separator or wrong!=row['surface'] or review.get('sourceMisspelling')!=wrong or
                review.get('sourceCorrection')!=correct or pipeline.keyboard_reading(wrong)!=row['reading']):
            raise ValueError('Review must retain the exact listed spelling, corrections and original input')
        corrections={word.strip() for word in correct.split(',') if word.strip()}
        if not corrections:raise ValueError('A spelling label needs its actual source correction')
        seen.add(row['id']);pairs[wrong]=corrections
        provenance[wrong]=dict(source='codespell_misspelling_dictionary',revision=CODESPELL_REVISION,
            snapshotSha256=CODESPELL_PINS['dictionary.txt'],url='https://github.com/codespell-project/codespell/blob/'+CODESPELL_REVISION+
                '/codespell_lib/data/dictionary.txt#L'+str(line),line=line,listedSpelling=wrong,
            reviewer='implementation_agent',humanReviewClaimed=False,rationale=review['rationale'],
            universalNonwordClaimed=False,automaticCorrectionApplied=False,license='CC-BY-SA-3.0 dictionary data')
    return pairs,provenance


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
    approved = defaultdict(set);approved_inputs=defaultdict(set)
    for surface, ids in model.approved.items():
        if ids:
            approved[surface.casefold()].add(surface)
            reading=pipeline.keyboard_reading(surface)
            if reading:approved_inputs[reading].add(surface)
    reviews = []
    for row in rows:
        surface = row['surface']
        if surface not in pairs or approved[surface.casefold()] or approved_inputs[row.get('reading')]:
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
    codespell=getattr(args,'codespell_source',None)
    if codespell and not getattr(args,'reviews',None):raise ValueError('Spelling dictionary matching requires individual input reviews')
    pairs = {} if codespell else load(args.snapshot)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    states = [json.loads(x) for x in (args.base / 'status.jsonl').read_text().splitlines()]
    selected = [row for row, state in zip(rows, states) if state['decision'] == 'pending']
    folded=bool(codespell or getattr(args,'ascii_input_casefold',False))
    if codespell:
        pairs,provenance=reviewed_codespell_pairs(codespell,selected,list(map(json.loads,args.reviews.open())))
    else:pairs,provenance=ascii_input_pairs(selected,pairs) if folded else (pairs,None)
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
    additions = exclusions(model, selected, pairs, exact, pending,provenance,allow_word_sequences=bool(codespell))
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    existing = {row['id'] for row in reviews}
    reviews += [row for row in additions if row['id'] not in existing]
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    if codespell:
        sources['reviewedCodespellLabels']=dict(revision=CODESPELL_REVISION,files=CODESPELL_PINS,reviewsSha256=pipeline.digest(args.reviews),
            policy='individual exact source-line reviews only; independently approved corrections or their complete listed word sequences required; all case-equivalent approved names and unresolved English senses block exclusion; no source-absence rejection, universal nonword claim or program/library code imported')
        notices['CODESPELL-DICTIONARY-ATTRIBUTION.txt']=('Codespell dictionary contributors and English Wikipedia contributors. https://github.com/codespell-project/codespell/tree/'+CODESPELL_REVISION+'\n'
            'Only selected individually reviewed misspelling/correction data facts from codespell_lib/data/dictionary.txt, CC BY-SA 3.0 per the pinned README. Full data license retained; no GPL codespell program/library code imported.\n'
            'Changes: cross-check literal original input IDs, spellings, readings and costs; preserve named/lexical alternatives and unresolved English senses; record source-line citations and auditable machine exclusions. The list is not exhaustive and does not establish universal nonexistence; original rows are retained and not automatically corrected.\n').encode()
        notices['CODESPELL-DATA-LICENSE-STATEMENT.txt']=('The pinned upstream README identifies dictionary.txt and dictionary_*.txt as data derived from English Wikipedia under CC BY-SA 3.0.\n'
            'https://github.com/codespell-project/codespell/blob/'+CODESPELL_REVISION+'/README.rst#license\n'
            'README SHA-256: '+CODESPELL_PINS['README.rst']+' . Full README retained in research sources, not redistributed as program documentation.\n').encode()
        notices['CC-BY-SA-3.0.txt']=(codespell/'CC-BY-SA-3.0.txt').read_bytes()
    else:
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
    for name in ['base', 'seed', 'index', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--snapshot',type=Path)
    group.add_argument('--codespell-source',type=Path)
    parser.add_argument('--reviews',type=Path,help='Required individual source-line reviews for the spelling dictionary')
    parser.add_argument('--ascii-input-casefold',action='store_true')
    extend(parser.parse_args())
