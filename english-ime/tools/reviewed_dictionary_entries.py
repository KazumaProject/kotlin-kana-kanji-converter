"""Verify individually reviewed lexical entries from pinned whole dictionaries.

Historical evidence does not prove current frequency or override explicit
restricted usage. Definitions stay in the research source; output stores only
lexical facts, entry identities, hashes and explicit implementation-agent reviews.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
from wiktionary_index import Index

WEBSTER_SHA = '86fb9c28c32008ea288ca4bcf34f4f0d3d11ccf9e0898294d98b73671497f1d3'
WORDNET_SHA = '31f4af16c54b532fd5484d4cc33aee588a31bb5b70683ae8197842fde5b586bc'
LICENSE_PINS = {'LICENSE.md': '672cc8b5663e8dc74c4b07a9dcf477193853575b119908fd3dc0aeeb60a9dbbb',
                'WNDB_License.txt': 'df30ec18fbabcdaf031b79ea026d3e6b959010cffe6dd7be9ac137822175b904'}
DOMAINS = {'domain_science', 'domain_medical', 'domain_entertainment', 'domain_business', 'domain_education'}
WEBSTER_ROLES = {'n.': 'noun', 'a.': 'adjective', 'prep.': 'preposition'}
RESTRICTED_LABEL = re.compile(r'\[(?:Obs\.?|Obsol\.?|Obsolete|Archaic\.?|Vulgar\.?)\]', re.I)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def webster_entries(text, selected):
    lines = text.replace('\r\n', '\n').splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith('*** START OF THE PROJECT GUTENBERG'))
    end = next(i for i, line in enumerate(lines) if line.startswith('*** END OF THE PROJECT GUTENBERG'))
    heads = [i for i in range(start + 1, end - 1) if lines[i] and
             re.fullmatch(r"[A-Z][A-Z0-9 ,;'&()/-]*", lines[i]) and
             not lines[i - 1].strip() and lines[i + 1].strip()]
    records = {}
    for ordinal, first in enumerate(heads):
        identity = 'pg29765:' + str(first + 1)
        if identity not in selected:
            continue
        last = heads[ordinal + 1] if ordinal + 1 < len(heads) else end
        passage = '\n'.join(lines[first:last]); header = passage.split('\n\n', 1)[0]
        # Etymology/gloss words cannot provide the entry's lexical role.
        annotation = re.search(r',\s*(n\.|a\.|prep\.)\s', header.split('Etym:', 1)[0] + ' ')
        records[identity] = dict(sourceKind='webster', id=identity, entrySha256=sha(passage),
            heads=[h.strip().casefold() for h in lines[first].split(';')], sourceHeading=lines[first],
            sourceStartLine=first + 1, sourceEndLineExclusive=last + 1,
            printedPos=annotation[1] if annotation else None,
            restricted=bool(RESTRICTED_LABEL.search(passage)),
            domainLabels=re.findall(r'\((Bot\.|Mus\.|Metal\.|Her\.)\)', header),
            url='https://www.gutenberg.org/ebooks/29765', snapshotSha256=WEBSTER_SHA)
    return records


def wordnet_entries(stream, selected):
    records = {}; synsets = {}; metadata = None
    for event, entry in ET.iterparse(stream, events=('start', 'end')):
        if event == 'start':
            if entry.tag == 'Lexicon':
                metadata = entry.attrib
            continue
        if entry.tag == 'LexicalEntry':
            if entry.attrib['id'] in selected:
                lemma = entry.find('Lemma'); senses = list(entry.findall('Sense'))
                if lemma is None or lemma.attrib.get('partOfSpeech') != 'n' or not senses:
                    raise ValueError('Reviewed named Wordnet entry needs its explicit noun and sense identity')
                records[entry.attrib['id']] = dict(sourceKind='wordnet', id=entry.attrib['id'],
                    heads=[lemma.attrib['writtenForm']], printedPos='n', entrySha256=sha(ET.tostring(entry, encoding='unicode')),
                    senses=[dict(s.attrib, relations=[r.attrib for r in s.findall('SenseRelation')]) for s in senses],
                    url='https://en-word.net/', snapshotSha256=WORDNET_SHA)
            entry.clear()
        elif entry.tag == 'Synset':
            wanted = {s['synset'] for r in records.values() for s in r['senses']}
            if entry.attrib['id'] in wanted:
                synsets[entry.attrib['id']] = dict(entry.attrib,
                    synsetSha256=sha(ET.tostring(entry, encoding='unicode')),
                    relations=[r.attrib for r in entry.findall('SynsetRelation')])
            entry.clear()
    if not metadata or any(metadata.get(k) != v for k, v in
            {'id': 'oewn', 'language': 'en', 'version': '2025+', 'license': 'https://creativecommons.org/licenses/by/4.0'}.items()):
        raise ValueError('Changed Wordnet language/version/license identity')
    for record in records.values():
        record['synsets'] = [synsets[s['synset']] for s in record['senses']]
    return records


def validate_review(review, record, restricted_current=()):
    if (review.get('reviewer') != 'implementation_agent' or not review.get('rationale', '').strip() or
            review.get('decision','include')!='include' or
            review.get('entrySha256') != record['entrySha256'] or review['target'] not in record['heads']):
        raise ValueError('Changed or missing explicit lexical-entry review')
    target = review['target']; members = set(review['categories'])
    if record['sourceKind'] == 'webster':
        role = WEBSTER_ROLES.get(record['printedPos'])
        if (not role or role not in members or not members <= {role} | DOMAINS or record['restricted'] or
                target.casefold() in {value.casefold() for value in restricted_current} or review.get('headingCaseNormalized') is not True):
            raise ValueError('Historical evidence cannot invent POS/morphology or override restricted usage')
    else:
        if not {'noun', 'noun_proper'} <= members:
            raise ValueError('A reviewed named Wordnet interpretation requires explicit proper-name review')
        if members == {'noun', 'noun_proper', 'name_brand', 'domain_medical'}:
            if not any(r.get('relType') == 'exemplifies' and r.get('target') == 'oewn-trademark__1.10.00..'
                    for s in record['senses'] for r in s['relations']):
                raise ValueError('A brand requires an explicit trademark relation')
            if not all(s.get('lexfile') == 'noun.artifact' and
                       any(r.get('relType') == 'hypernym' and r.get('target') == 'oewn-03834005-n'
                           for r in s['relations']) for s in record['synsets']):
                raise ValueError('Unexpected named-brand interpretation')
        elif members == {'noun', 'noun_proper', 'name_place'}:
            if not all(s.get('lexfile') == 'noun.location' and
                       any(r.get('relType') == 'instance_hypernym' for r in s['relations']) for s in record['synsets']):
                raise ValueError('A place name requires its reviewed location-instance identity')
        else:
            raise ValueError('Unsupported reviewed Wordnet interpretation')
    return members


def attach(model, rows, records, reviews, corrections, restricted_current=()):
    by_form = defaultdict(list); counts = Counter(); seen = set()
    for row in rows:
        by_form[row['surface'].casefold()].append(row)
    for review in reviews:
        identity = review['entryId'], review['target']
        if identity in seen:
            raise ValueError('Duplicate reviewed lexical entry')
        seen.add(identity); record = records[review['entryId']]
        members = validate_review(review, record, restricted_current); target = review['target']
        selected = by_form[target.casefold()]
        if not selected:
            continue
        extension.ensure_categories(model, members)
        key = 'reviewed-dictionary-' + sha(json.dumps(identity))[:24]
        proof = dict(source='reviewed_lexical_entry', url=record['url'], approved=True,
            lexicalEntry=record, reviewer='implementation_agent', humanReviewClaimed=False,
            rationale=review['rationale'], headingCaseNormalized=review.get('headingCaseNormalized', False),
            preferredCaseClaimed=False, currentFrequencyClaimed=False,
            scope='individually reviewed English lexical heading and printed POS, or explicit named Wordnet sense; no definition prose, pronunciation-derived spelling, source-only capitalization inference, inherited inflections or unrestricted historical-to-current usage inference')
        model.add(key, target, target, members, proof, approved=True)
        for row in selected:
            surface = row['surface']
            if surface == target:
                continue
            if row['id'].startswith('manual:') and 'noun_proper' in members:
                model.add(key, target, surface, members, dict(proof, relation='existing_manual_case', legacySourceId=row['id']), approved=True)
                continue
            if surface != surface.lower() or pipeline.keyboard_reading(target) != row['reading']:
                raise ValueError('Lexical review cannot invent a source mapping')
            existing = {r['target']: dict(r) for r in corrections if r['id'] == row['id']}
            existing.setdefault(target, dict(id=row['id'], source=surface, target=target, evidence=record['url']))
            if model.approved.get(surface):
                urls = [p['url'] for k in model.approved[surface] for p in model.evidence[k, surface]
                        if p.get('approved', True) and not p.get('requiresFullNamedContext', False)]
                if urls:
                    existing.setdefault(surface, dict(id=row['id'], source=surface, target=surface, evidence=min(urls)))
            corrections[:] = [r for r in corrections if r['id'] != row['id']]
            spelling = any(value.casefold() != surface.casefold() for value in existing)
            relation = ('input_spelling_correction' if len(existing) == 1 else 'input_spelling_candidates') if spelling else ('case_correction' if len(existing) == 1 else 'case_candidates')
            corrections += [dict(value, relation=relation) for _, value in sorted(existing.items())]
        counts[record['sourceKind']] += 1
    return counts


def extend(args):
    if pipeline.digest(args.webster) != WEBSTER_SHA or pipeline.digest(args.wordnet / 'english-wordnet-2025-plus.xml.gz') != WORDNET_SHA:
        raise ValueError('Changed whole dictionary source')
    for name, expected in LICENSE_PINS.items():
        if pipeline.digest(args.wordnet / name) != expected:
            raise ValueError('Changed dictionary license')
    reviews = list(map(json.loads, args.reviews.open())); selected = {r['entryId'] for r in reviews}
    text = args.webster.read_text(); records = webster_entries(text, selected)
    with gzip.open(args.wordnet / 'english-wordnet-2025-plus.xml.gz', 'rb') as stream:
        records.update(wordnet_entries(stream, selected))
    if selected != set(records):
        raise ValueError('Missing reviewed dictionary entry')
    index = Index(args.index)
    try:
        entries = list(index.lookup({r['target'] for r in reviews},folded=True))
    finally:
        index.close()
    restricted = resolve_pending.ineligible_exact_words(entries)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    path = args.base / 'surface-corrections.tsv'; corrections = pipeline.read_table(path, 'corrections') if path.is_file() else []
    counts = attach(model, rows, records, reviews, corrections, restricted)
    path = args.base / 'reviewed-overrides.tsv'; decisions = pipeline.read_table(path, 'decisions') if path.is_file() else []
    decisions, reopened = resolve_pending.revalidate_machine_reviews(model, decisions, pending, corrections)
    sources['reviewedEnglishDictionaryEntries'] = dict(websterSha256=WEBSTER_SHA, wordnetSha256=WORDNET_SHA,
        reviewsSha256=pipeline.digest(args.reviews), policy='explicit entry/POS/sense review only; preserve restrictive labels and independent named readings; no definition prose, inferred inflections or preferred-case claim')
    notices['REVIEWED-LEXICAL-ENTRIES-ATTRIBUTION.txt'] = (
        "Webster's Unabridged Dictionary, Project Gutenberg eBook 29765, credited to Graham Lawrence. "
        'https://www.gutenberg.org/ebooks/29765 . Catalog states public domain in the USA; full source usage notice retained separately. No particular print edition or worldwide copyright status is asserted.\n'
        'Open English Wordnet team, version 2025+, https://en-word.net/ ; derived from Princeton WordNet. CC BY 4.0 and underlying WordNet notices retained.\n'
        'Changes: selected individually reviewed entry, headword, POS, domain and named-entity facts and source hashes. No definitions, pronunciation text or other source prose is redistributed. Implementation-agent reviews, not human reviews.\n').encode()
    end = text.index('*** END OF THE PROJECT GUTENBERG')
    notices['GUTENBERG-WEBSTER-USAGE-NOTICE.txt'] = text[end:].encode()
    for name in LICENSE_PINS:
        notices['OEWN-' + name] = (args.wordnet / name).read_bytes()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.reviewed-dictionary-', dir=args.out.parent) as temp:
        reviewed = Path(temp) / 'reviews.tsv'; pipeline.table(reviewed, 'decisions', decisions)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, reopenedMachineExclusions=len(reopened), **{k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']})))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'webster', 'wordnet', 'reviews', 'index', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
