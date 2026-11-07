"""Join pinned English NameNet entries locally, checking reverse sense membership.

The released XML doubles a namespace prefix on generated Sense.synset links.
A repair is eligible only when the actual Synset explicitly lists the exact
LexicalEntry ID among its members. No labels, spellings or entity IDs are guessed.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
from wiktionary_index import Index

REVISION = '55bc7f4001388a5a41a1fd379f23652a4f8c02fe'
SNAPSHOT = '5ecc450882f4e1b9136a86d17e05b062fd90621afd6ff94eea45cbd2b9b0939e'
SOURCE_URL = 'https://huggingface.co/datasets/jmccrae/english-namenet/resolve/' + REVISION + '/english-namenet-2025.xml.gz'
PERSON_TYPES = {'noun.human', 'noun.person', 'noun.actor'}
PLACE_TYPES = {'noun.location', 'noun.region', 'noun.municipality', 'noun.river', 'noun.street',
    'noun.island', 'noun.mountain', 'noun.city', 'noun.administrative_unit', 'noun.hill', 'noun.town',
    'noun.stream', 'noun.geographical_area', 'noun.lake', 'noun.country', 'noun.peninsula',
    'noun.archipelago', 'noun.cape', 'noun.national_park', 'noun.bay', 'noun.canal', 'noun.volcano',
    'noun.county', 'noun.range', 'noun.french_region', 'noun.italian_region', 'noun.american_state',
    'noun.canadian_province', 'noun.malaysian_state', 'noun.waterfall', 'noun.district', 'noun.desert'}
ORGANIZATION_TYPES = {'noun.organization', 'noun.university', 'noun.terrorist_organization'}
PRODUCT_TYPES = {'noun.software', 'noun.browser'}
PREPARED_PINS = {'prepared/manifest.json': '177124b3f75dd5799beb68acfd32b4b0b0565987142d35fb4e1bf830eb2e7ce2', 'prepared/entries.json': '490126440a078d36bf7931b890f8a96c1443767130bbadcfc6362e7169434aa6', 'prepared-reference-check/manifest.json': 'ab332312911c4c20a1bb906762f9b43f71e2d3a60a4f268b34f4980ce5236540', 'prepared-reference-check/synsets.json': 'ebaaab431b96fb28b66c7c386da7719c1603743b4dde98c5f9c3ee794df0ef7a', 'prepared-reference-check/audit.json': '9f964f7dcbd4ab946b75c132e5e2ecd1db45de64d9d4c44edcb9e711e2717f54'}


def attach(model, entries, synsets, audits):
    by_sense = {(r['entryId'], r['senseId']): r for r in audits}
    if len(by_sense) != len(audits):
        raise ValueError('Duplicate NameNet audit identity')
    counts = Counter()
    for entry in entries:
        lemma = entry['lemma']; surface = lemma['writtenForm']; eid = entry['attributes']['id']
        if lemma['partOfSpeech'] != 'n':
            counts['nonNounLeads'] += 1
            continue
        for sense in entry['senses']:
            audit = by_sense[eid, sense['id']]
            target = sense['synset']
            canonical = target[len('oenn-'):] if re.fullmatch(r'oenn-oenn-Q[1-9][0-9]*-n', target) else target
            if (audit['originalTarget'] != target or audit['candidateTarget'] != canonical or
                    not audit['targetExists'] or not audit['exactReverseMembership']):
                counts['unverifiedReferences'] += 1
                continue
            synset = synsets[canonical]
            if (synset['attributes']['id'] != canonical or
                    synset['attributes'].get('partOfSpeech') != 'n' or
                    eid not in synset['attributes'].get('members', '').split()):
                raise ValueError('NameNet reverse membership changed')
            # Generated Wikidata entities have a verified Q identity. Existing
            # OEWN concepts in this file are leads, not new usage-policy proof.
            if not re.fullmatch(r'oenn-Q[1-9][0-9]*-n', canonical):
                counts['existingWordnetLeads'] += 1
                continue
            values = {'noun'}
            instance = any(r.get('relType') == 'instance_hypernym' for r in synset['relations'])
            lexical_file = synset['attributes'].get('lexfile', '').rsplit('/', 1)[-1]
            # Ontological instances include chemicals and substances, which do
            # not thereby become English proper nouns. Require an explicit
            # named-person/place/organization/software class for that category.
            if instance and lexical_file in PERSON_TYPES | PLACE_TYPES | ORGANIZATION_TYPES | PRODUCT_TYPES:
                values.add('noun_proper')
                if lexical_file in PERSON_TYPES:
                    values.add('name_person')
                elif lexical_file in PLACE_TYPES:
                    values.add('name_place')
                elif lexical_file in ORGANIZATION_TYPES:
                    values.add('name_organization')
                elif lexical_file in PRODUCT_TYPES:
                    values.add('name_product')
            if lexical_file in PRODUCT_TYPES:
                values.add('domain_technology')
            if lexical_file in {'noun.chemical', 'noun.chemical_element', 'noun.mineral', 'noun.taxon', 'noun.star', 'noun.constellation'}:
                values.add('domain_science')
            if lexical_file in {'noun.disease', 'noun.medicine', 'noun.phobia'}:
                values.add('domain_medical')
            proof = {'source': 'english_namenet', 'url': SOURCE_URL + '#' + quote(eid, safe=''),
                'revision': REVISION, 'snapshotSha256': SNAPSHOT, 'entryId': eid, 'senseId': sense['id'],
                'originalSynset': target, 'verifiedSynset': canonical, 'exactReverseMembership': True,
                'namespacePrefixRepair': target != canonical, 'lexfile': lexical_file,
                'relations': synset['relations'], 'approved': True,
                'scope': 'exact English lexical label and verified entity identity; no corpus sense or inflection claim'}
            key = 'namenet-' + hashlib.sha256(json.dumps([eid, sense['id'], canonical]).encode()).hexdigest()[:24]
            model.add(key, surface, surface, values, proof, approved=True)
            counts['verifiedEntitySenses'] += 1
            counts['namespaceRepairs'] += target != canonical
            counts['explicitInstances'] += instance
    return counts


def load(directory):
    if not PREPARED_PINS:
        raise ValueError('NameNet extraction pins have not been reviewed')
    for name, expected in PREPARED_PINS.items():
        if pipeline.digest(directory / name) != expected:
            raise ValueError('Changed NameNet extraction: ' + name)
    manifest = json.loads((directory / 'prepared/manifest.json').read_text())
    reference = json.loads((directory / 'prepared-reference-check/manifest.json').read_text())
    if (manifest['snapshotSha256'] != SNAPSHOT or manifest['revision'] != REVISION or
            reference['originalPreparedManifestSha256'] != pipeline.digest(directory / 'prepared/manifest.json') or
            manifest['lexicons'][0]['language'] != 'en' or
            manifest['lexicons'][0]['license'] != 'https://creativecommons.org/licenses/by/4.0'):
        raise ValueError('Unexpected NameNet source or license')
    return (json.loads((directory / 'prepared/entries.json').read_text()),
            json.loads((directory / 'prepared-reference-check/synsets.json').read_text()),
            json.loads((directory / 'prepared-reference-check/audit.json').read_text()))


def extend(args):
    entries, synsets, audits = load(args.sources)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    counts = attach(model, entries, synsets, audits)
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    states = [json.loads(x) for x in (args.base / 'status.jsonl').read_text().splitlines()]
    unresolved = [r for r, s in zip(rows, states) if s['decision'] == 'pending' or r['id'] in reopened]
    index = Index(args.index)
    try:
        records = list(index.lookup({r['surface'] for r in unresolved}))
    finally:
        index.close()
    additions = resolve_pending.cases(model, unresolved, {r['word'] for _, r in records},
                                      resolve_pending.ineligible_exact_words(records))
    prior_ids = {r['id'] for r in corrections}
    corrections += [r for r in additions if r['id'] not in prior_ids]
    sources['englishNameNet'] = {'revision': REVISION, 'snapshotSha256': SNAPSHOT, 'preparedPins': PREPARED_PINS,
        'policy': 'exact English noun labels; each entity sense requires an existing Synset and exact reverse LexicalEntry membership; noun_proper additionally requires explicit instance_hypernym and a named-person/place/organization/software class; no inferred inflection or corpus sense',
        'license': 'XML declares CC BY 4.0; retain that attribution/license despite dataset-card CC0 metadata; original WordNet notice retained'}
    notices['NAMENET-NOTICE.txt'] = ('Open English NameNet 2025, John P. McCrae and contributors.\n' + SOURCE_URL +
        '\nXML Lexicon declares CC BY 4.0: https://creativecommons.org/licenses/by/4.0/\n'
        'Dataset-card metadata states CC0; this derivative conservatively preserves the XML CC BY 4.0 terms and the existing WordNet notices.\n'
        'Changes: select exact English labels for existing inventory rows; preserve separate sense IDs; repair duplicated namespace prefixes only when the referenced Synset explicitly lists the exact LexicalEntry ID; map explicit lexical roles/instance relations without invented morphology.\n').encode()
    if pipeline.digest(args.base / 'notices/CC-BY-4.0.txt') != '9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411':
        raise ValueError('Missing full CC BY 4.0 license')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.namenet-review-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'; pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, reopenedMachineExclusions=len(reopened),
        **{k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'sources', 'index', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
