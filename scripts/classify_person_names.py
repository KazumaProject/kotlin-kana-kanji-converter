#!/usr/bin/env python3
"""Classify exact, explicitly generic JMnedict names; never infer person histories.

This is a subagent's source-backed proposal generator, not an approval step.
An independent reviewer must independently reparse the pinned source. All unknown,
particular-person, mixed-name and unmatched records remain on hold. No production
assets are changed. Without --workspace, proposals remain unbound drafts (null IDs).
"""
import argparse
from collections import Counter
from datetime import date
import gzip
import io
from itertools import chain
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import person_subclassification as person

SOURCE_URL = 'https://www.edrdg.org/pub/Nihongo/JMnedict.xml.gz'
DOCUMENTATION_URL = 'https://www.edrdg.org/enamdict/enamdict_doc.html'
LICENSE_URL = 'https://www.edrdg.org/edrdg/licence.html'
GENERIC = {'surname': 'surname', 'given': 'given_name', 'fem': 'given_name',
           'masc': 'given_name', 'unclass': 'personal_name'}
EXPANDED = {'family or surname': 'surname', 'given name or forename, gender not specified': 'given',
            'female given name or forename': 'fem', 'male given name or forename': 'masc',
            'unclassified name': 'unclass', 'full name of a particular person': 'person'}
ENTITY = re.compile(r'&([A-Za-z][A-Za-z0-9_]*);')
DECLARATION = re.compile(r'<!ENTITY\s+([A-Za-z][A-Za-z0-9_]*)\s+"([^"<&]*)"\s*>')


def entries(path):
    """Stream source safely: discard DTD and preserve only literal entity codes.

    Never pass a DTD to the XML parser, load external entities, or recursively
    expand references. Known inline name-type entities become harmless text.
    """
    parser = ET.XMLPullParser(events=('start', 'end'))
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        header = ''
        while ']>' not in header:
            line = stream.readline()
            person.require(bool(line), 'missing internal JMnedict DTD')
            header += line
            person.require(len(header) <= 131072, 'oversized JMnedict DTD')
        head, body = header.split(']>', 1)
        clean = re.sub(r'<!--.*?-->', '', head, flags=re.S)
        person.require('<!DOCTYPE JMnedict [' in clean, 'unexpected JMnedict doctype')
        person.require(not re.search(r'\b(SYSTEM|PUBLIC)\b', clean) and not re.search(r'<!ENTITY\s+%', clean),
                       'external/parameter entities forbidden')
        definitions = dict(DECLARATION.findall(clean))
        person.require(bool(definitions), 'missing inline name type declarations')
        without = DECLARATION.sub('', clean)
        person.require('<!ENTITY' not in without, 'unsupported entity declaration')
        for code, meaning in definitions.items():
            if code in GENERIC or code == 'person':
                person.require(EXPANDED.get(meaning) == code, 'unexpected generic/person entity meaning')

        def replace(match):
            code = match.group(1)
            if code in ('amp', 'lt', 'gt', 'apos', 'quot'):
                return match.group(0)
            person.require(code in definitions, 'undeclared entity')
            return code

        root = None
        for line in chain((body,), stream):
            person.require(len(line) <= 1048576, 'oversized XML line')
            person.require('<!DOCTYPE' not in line and '<!ENTITY' not in line, 'nested DTD forbidden')
            parser.feed(ENTITY.sub(replace, line))
            for event, element in parser.read_events():
                if root is None and event == 'start':
                    root = element
                    person.require(root.tag == 'JMnedict', 'unexpected XML root')
                if event == 'end' and element.tag == 'entry':
                    seq = element.findtext('ent_seq')
                    person.require(isinstance(seq, str) and seq.isdigit(), 'invalid entry sequence')
                    surfaces = [e.text for e in element.findall('k_ele/keb')]
                    types = sorted({EXPANDED.get(e.text, e.text) for e in element.findall('trans/name_type') if e.text})
                    if not types:
                        types = ['MISSING_TYPE']
                    readings = []
                    for reading in element.findall('r_ele'):
                        reb = reading.findtext('reb')
                        restrictions = [e.text for e in reading.findall('re_restr')]
                        person.require(person.string(reb), 'invalid source reading')
                        person.require(set(restrictions) <= set(surfaces), 'invalid reading restriction')
                        applicable = restrictions or surfaces or [reb]
                        readings.extend((reb, surface) for surface in applicable)
                    yield seq, types, readings
                    root.clear()
        parser.close()


def match_source(source, pairs):
    matches = {}
    for seq, types, readings in entries(Path(source)):
        for reading, surface in readings:
            pair = reading, surface
            if pair in pairs:
                match = {'ent_seq': seq, 'types': types, 'reading': reading, 'surface': surface}
                matches.setdefault(pair, []).append(match)
    for records in matches.values():
        records.sort(key=lambda x: (int(x['ent_seq']), x['types']))
    return matches


def category_for(matches):
    types = {kind for match in matches for kind in match['types']}
    if not matches:
        return None, 'no_exact_JMnedict_entry; identity and appearance unresearched'
    if 'person' in types:
        return None, 'particular_person_source_type; individual appearance investigation required'
    if 'MISSING_TYPE' in types:
        return None, 'source_type_missing; generic name role unverified'
    categories = {GENERIC[kind] for kind in types if kind in GENERIC}
    if not categories:
        return None, 'no_explicit_generic_name_type; no occupational or appearance inference'
    specific = categories - {'personal_name'}
    if len(specific) > 1:
        return None, 'multiple_generic_name_roles; primary role unresolved'
    return next(iter(specific or categories)), 'exact_JMnedict_generic_name_type'


def make_proposal(item, matches, snapshot_id, batch_id, classifier_id, run_id, checked_on):
    category, reason = category_for(matches)
    relevant = [m for m in matches if category and any(GENERIC.get(t) == category for t in m['types'])]
    sources = [{'url': SOURCE_URL + '#ent_seq=' + m['ent_seq'],
                'summary': 'JMnedict entry ' + m['ent_seq'] + ': exact reading=' + item['reading'] +
                           ', surface=' + item['surface'] + ', explicit name types=' + ','.join(m['types']) +
                           '; generic name evidence, not a claim about a particular person or appearance history.',
                'checked_on': checked_on} for m in relevant]
    return {
        'schema_version': 1, 'snapshot_id': snapshot_id, 'batch_id': batch_id, 'item_id': item['item_id'],
        'classifier_id': classifier_id, 'run_id': run_id, 'checked_on': checked_on,
        'identity_status': 'name_component' if category else 'unresolved', 'entity_ids': [], 'public_aliases': [],
        'categories': [category] if category else [], 'primary_category': category, 'tags': [],
        'adult_appearance_status': 'not_applicable' if category else 'not_checked',
        'identity_evidence': sources, 'occupation_evidence': sources, 'reading_evidence': sources,
        'adult_evidence': [], 'search_log': [], 'reason': reason}


def classify(root, source, output, workspace=None, classifier_id='jmnedict-classifier', run_id='jmnedict-v1'):
    root, source, output = Path(root).resolve(), Path(source).resolve(), Path(output).resolve()
    person.require(not output.exists(), 'output already exists; refusing overwrite')
    person.require(not output.is_relative_to(root / 'src') and not output.is_relative_to(root / 'docs'), 'output must be a build artifact')
    person.require(person.string(classifier_id) and person.string(run_id), 'invalid classifier/run ID')
    source_sha = person.sha(source)
    items = person.collect_items(root)
    matches = match_source(source, {(x['reading'], x['surface']) for x in items})
    snapshot_id, batch_for = None, {}
    if workspace is not None:
        snapshot, _, workspace_items = person.load_workspace(root, workspace)
        person.require(items == workspace_items and snapshot['selected_count'] == len(items), 'full-universe workspace required')
        snapshot_id = snapshot['snapshot_id']
        batch_for = {key: batch['batch_id'] for batch in snapshot['batches'] for key in batch['item_ids']}
    checked_on = date.today().isoformat()
    output.mkdir(parents=True)
    counts = Counter()
    with (output / 'proposals.jsonl').open('w', encoding='utf-8', newline='\n') as proposals:
        with (output / 'source-matches.jsonl.gz').open('wb') as raw:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as zipped:
                with io.TextIOWrapper(zipped, encoding='utf-8', newline='\n') as match_file:
                    for item in items:
                        records = matches.get((item['reading'], item['surface']), [])
                        proposal = make_proposal(item, records, snapshot_id, batch_for.get(item['item_id']), classifier_id, run_id, checked_on)
                        counts['items'] += 1
                        counts['exact_source_match_items'] += bool(records)
                        counts['generic_name_proposals'] += proposal['adult_appearance_status'] == 'not_applicable'
                        counts['individual_or_unresolved_hold'] += proposal['adult_appearance_status'] == 'not_checked'
                        if proposal['primary_category']:
                            counts[proposal['primary_category']] += 1
                        proposals.write(person.canonical(proposal).decode() + '\n')
                        if records:
                            match_file.write(person.canonical({
                                'item_id': item['item_id'], 'reading': item['reading'], 'surface': item['surface'],
                                'matches': records, 'source_sha256': source_sha,
                                'proposal_sha256': person.proposal_sha(proposal)}).decode() + '\n')
    person.require(source_sha == person.sha(source), 'source changed during classification')
    manifest = {'schema_version': 1, 'snapshot_id': snapshot_id, 'unbound_draft': snapshot_id is None,
                'classifier_id': classifier_id, 'run_id': run_id, 'checked_on': checked_on,
                'source': {'url': SOURCE_URL, 'sha256': source_sha, 'documentation_url': DOCUMENTATION_URL,
                           'license_url': LICENSE_URL, 'attribution': 'JMnedict, Electronic Dictionary Research and Development Group'},
                'implementation_sha256': person.sha(Path(__file__)), 'engine_sha256': person.sha(Path(person.__file__)),
                'sources': person.source_hashes(root), 'counts': dict(counts),
                'files': {name: person.sha(output / name) for name in ('proposals.jsonl', 'source-matches.jsonl.gz')},
                'production_release': False,
                'limitations': 'Generic-source proposals only. Individual appearance histories have not been investigated. Independent review required.'}
    person.write_json(output / 'manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--classifier-id', default='jmnedict-classifier')
    parser.add_argument('--run-id', default='jmnedict-v1')
    args = parser.parse_args()
    try:
        result = classify(args.root, args.source, args.output, args.workspace, args.classifier_id, args.run_id)
        print(json.dumps({'counts': result['counts'], 'snapshot_id': result['snapshot_id'],
                          'source_sha256': result['source']['sha256']}, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError, ET.ParseError) as error:
        parser.exit(1, f'error: {error}\n')


if __name__ == '__main__':
    main()
