"""Add sense-separated OEWN evidence leads, without approving distribution.

A WordNet entry establishes lexical-role evidence. It does not itself resolve
usage restrictions, source casing, corpus meaning or a nonidentity input alias.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import extend_lexicon as extension
import lexicon_pipeline as pipeline

PINS = {'english-wordnet-2025-plus.xml.gz': '31f4af16c54b532fd5484d4cc33aee588a31bb5b70683ae8197842fde5b586bc',
        'LICENSE.md': '672cc8b5663e8dc74c4b07a9dcf477193853575b119908fd3dc0aeeb60a9dbbb',
        'WNDB_License.txt': 'df30ec18fbabcdaf031b79ea026d3e6b959010cffe6dd7be9ac137822175b904'}
URL = 'https://en-word.net/downloads/english-wordnet-2025-plus.xml.gz'
ROLES = {'n': 'noun', 'v': 'verb', 'a': 'adjective', 's': 'adjective', 'r': 'adverb'}


def extract(stream, wanted):
    entries, synsets = [], {}
    for event, element in ET.iterparse(stream, events=['end']):
        if element.tag == 'LexicalEntry':
            lemma = element.find('Lemma')
            if lemma is not None and lemma.attrib['writtenForm'].lower() in wanted:
                entries.append({'id': element.attrib['id'], 'lemma': dict(lemma.attrib),
                                'senses': [dict(item.attrib) for item in element.findall('Sense')]})
            element.clear()
        elif element.tag == 'Synset':
            synsets[element.attrib['id']] = {'lexfile': element.get('lexfile'),
                'instanceHypernyms': [r.attrib['target'] for r in element.findall('SynsetRelation') if r.get('relType') == 'instance_hypernym']}
            element.clear()
    for entry in entries:
        for sense in entry['senses']:
            if sense['synset'] not in synsets:
                raise ValueError('Missing OEWN synset ' + sense['synset'])
    return entries, synsets


def attach(model, rows, entries, synsets, pending):
    wanted = defaultdict(list)
    for row in rows:
        wanted[row['surface'].lower()].append(row)
    counts = Counter()
    for entry in entries:
        word = entry['lemma']['writtenForm']
        role = ROLES.get(entry['lemma']['partOfSpeech'])
        if not role:
            continue
        for sense in entry['senses']:
            synset = synsets[sense['synset']]
            categories = {role}
            if role == 'noun' and synset['instanceHypernyms']:
                categories.add('noun_proper')
                if synset['lexfile'] == 'noun.person':
                    categories.add('name_person')
                elif synset['lexfile'] == 'noun.location':
                    categories.add('name_place')
            key = 'oewn-' + hashlib.sha256(sense['id'].encode()).hexdigest()[:24]
            proof = {'source': 'oewn_2025_plus', 'url': URL, 'entryId': entry['id'], 'senseId': sense['id'],
                     'synset': sense['synset'], 'lexfile': synset['lexfile'], 'instanceHypernyms': synset['instanceHypernyms'],
                     'scope': 'lexical_evidence_only_not_usage_or_mapping_approval', 'approved': False}
            model.add(key, word, word, categories, proof, approved=False)
            counts['senseLeads'] += 1
        for row in wanted[word.lower()]:
            pending.append({'sourceId': row['id'], 'surface': row['surface'], 'candidateSurface': word,
                            'reason': 'oewn_lexical_lead_requires_usage_and_mapping_review', 'entryId': entry['id'],
                            'source': 'oewn_2025_plus', 'url': URL, 'wordAccepted': False})
            counts['sourceRowCandidateLeads'] += 1
    return counts


def extend(args):
    for name, expected in PINS.items():
        if pipeline.digest(args.sources / name) != expected:
            raise ValueError('Changed OEWN source or notice: ' + name)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    states = [json.loads(line) for line in (args.base / 'status.jsonl').read_text().splitlines()]
    unresolved = [row for row, state in zip(rows, states) if state['decision'] == 'pending']
    with gzip.open(args.sources / 'english-wordnet-2025-plus.xml.gz', 'rb') as stream:
        entries, synsets = extract(stream, {row['surface'].lower() for row in unresolved})
    counts = attach(model, unresolved, entries, synsets, pending)
    sources['oewn2025Plus'] = {'files': PINS, 'url': URL, 'version': '2025+',
        'policy': 'sense-specific lexical leads only; no distribution approval, automatic case correction or inferred morphology',
        'matchedEntries': len(entries)}
    for original, name in [('LICENSE.md', 'OEWN-CC-BY-4.0.txt'), ('WNDB_License.txt', 'OEWN-PRINCETON-LICENSE.txt')]:
        notices[name] = (args.sources / original).read_bytes()
    notices['OEWN-CHANGES.txt'] = b'Open English Wordnet team and Princeton University, https://en-word.net/, 2025+ release, CC BY 4.0 with underlying Princeton attribution. Selected lexical identifiers, roles and explicit instance relationships. No glosses, quotations, examples or inferred inflections imported. These are evidence leads, not reviewed usage or mapping decisions.\n'
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    prior = args.base / 'reviewed-overrides.tsv'
    summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
        reviewed_decisions=prior if prior.is_file() else None, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, matchedEntries=len(entries),
        **{key: summary[key] for key in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'sources', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
