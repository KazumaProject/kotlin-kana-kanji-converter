"""Recover qualified YAGO personal-name fields with an English spelling witness.

YAGO can serialize a referenced name entity's identifier as an xsd:string.
That string is not necessarily a literal spelling. Single alphabetic names
with a documented QID/surname qualifier are considered; an optional mode also
matches literal single names and decomposable Latin-diacritic input aliases.
The spelling must also occur as a complete token in the owner's English name.
Compound names, arbitrary identifier fragments and inferred name positions
are never imported. All joins are local against pinned public snapshots.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time
from zipfile import ZipFile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import named_case_variants
import resolve_pending
import yago_names as yago
import yago_name_variants as variants

ROOTS = {'schema:Person': {'name_person'}}
QUALIFIED = re.compile(r'([A-Za-z]+)_(?:Q[1-9][0-9]*|surname)')
LATIN_FIELD = re.compile(r"([^\W\d_]+)(?:_(?:Q[1-9][0-9]*|surname))?")
FORMAT_REFERENCES = {
    '03-make-facts.py':'4d5a52527fc215484b28f2f2fa8b5e4f5968086a1c155d4f1d5d11ad1f9d15b6',
    '04-make-typecheck.py':'ebf5a957b996dac3149fd168722f5392926f0b15bea2d31391155db03eb61eb1',
    '05-make-ids.py':'be85f2c583c92cc6ced15e6945d17c9f348ab1f4d5bb1d3ac761455f72995165'}
PREVIOUS_POLICY = ('explicit personal-name relation of a verified Person with Wikidata and English-Wikipedia identity; '
    'a recognized single-name QID/surname qualifier plus an independent complete-token English owner-name spelling; '
    'no compound splitting, arbitrary identifier decoding, name-position inference, preferred casing, '
    'original corpus identity, gender, nationality or morphology claim')
POLICY = ('explicit personal-name relation of a verified Person with Wikidata and English-Wikipedia identity; '
    'a recognized single-name QID/surname qualifier, or optional literal single-name field, plus an independent complete-token English owner-name spelling; '
    'optional existing decomposable Latin-diacritic keyboard aliases retain the original name and do not assert preferred ASCII spelling; '
    'no compound splitting, arbitrary identifier decoding, name-position inference, preferred casing, '
    'original corpus identity, gender, nationality or morphology claim')


def stem(value):
    match = QUALIFIED.fullmatch(value)
    return match[1] if match else None


def candidate_stem(value, ascii_input_aliases=False):
    if not ascii_input_aliases:
        return stem(value)
    match = LATIN_FIELD.fullmatch(value)
    return match[1] if match and variants.ascii_name(match[1]) is not None else None


def spelling_witnesses(value, labels, ascii_input_aliases=False):
    word = candidate_stem(value, ascii_input_aliases)
    if not word:
        return []
    pattern = re.compile(r"(?<![\w'-])" + re.escape(word) + r"(?![\w'-])", re.IGNORECASE)
    result = []
    for label in labels:
        if not yago.english(label['language']):
            continue
        for match in pattern.finditer(label['label']):
            spelling = match[0]
            if spelling.casefold() == word.casefold():
                result.append(dict(spelling=spelling, ownerNameEvidence=label))
    return result


def prepare(args):
    if args.out.exists():
        raise ValueError('Output already exists')
    pipeline.verify(args.base)
    for name, expected in yago.PINS.items():
        if pipeline.digest(args.sources / name) != expected:
            raise ValueError('Changed YAGO snapshot: ' + name)
    rows = pipeline.inventory(args.base / 'inventory.jsonl')
    states = list(map(json.loads, (args.base / 'status.jsonl').open()))
    wanted = {row['surface'].casefold() for row, state in zip(rows, states) if state['decision'] != 'include'}
    ascii_aliases = bool(getattr(args, 'ascii_input_aliases', False))
    fields = defaultdict(list)
    start = time.monotonic()
    with ZipFile(args.sources / 'yago-4.6-facts.zip') as archive:
        if archive.namelist() != ['yago-facts.ttl']:
            raise ValueError('Unexpected YAGO facts archive')
        for number, raw in enumerate(archive.open('yago-facts.ttl'), 1):
            if number % 10000000 == 0:
                print(json.dumps(dict(phase='name_fields', lines=number, owners=len(fields), seconds=round(time.monotonic()-start, 1))), flush=True)
            if b'\tschema:givenName\t' not in raw and b'\tschema:familyName\t' not in raw:
                continue
            owner, relation, obj = yago.triple(raw)
            value = yago.literal(obj)
            if value and value[1] is None:
                name = candidate_stem(value[0], ascii_aliases)
                alias = variants.ascii_name(name) if name else None
                if name and (name.casefold() in wanted or ascii_aliases and alias.casefold() in wanted):
                    fields[owner].append(dict(relation=relation, literal=value[0], line=number, tripleSha256=hashlib.sha256(raw).hexdigest()))
        entities = {owner: dict(id=owner, nameFields=names, labels=[], types=[], wikidataIds=[], englishWikipediaUrls=[])
                    for owner, names in sorted(fields.items())}
        for number, raw in enumerate(archive.open('yago-facts.ttl'), 1):
            if number % 10000000 == 0:
                print(json.dumps(dict(phase='owner_names', lines=number, seconds=round(time.monotonic()-start, 1))), flush=True)
            owner = raw.split(b'\t', 1)[0].decode()
            if owner not in entities:
                continue
            _, relation, obj = yago.triple(raw)
            entity = entities[owner]
            proof = dict(line=number, tripleSha256=hashlib.sha256(raw).hexdigest())
            if relation in {'rdfs:label', 'schema:alternateName'}:
                value = yago.literal(obj)
                if value and yago.english(value[1]):
                    entity['labels'].append(dict(proof, label=value[0], language=value[1], relation=relation))
            elif relation == 'rdf:type':
                entity['types'].append(dict(proof, type=obj))
            elif relation == 'owl:sameAs' and re.fullmatch(r'wd:Q[1-9][0-9]*', obj):
                entity['wikidataIds'].append(obj)
            elif relation == 'schema:url':
                match = re.fullmatch(r'"(https://en\.wikipedia\.org/wiki/[^"\\]+)"\^\^xsd:anyURI', obj)
                if match:
                    entity['englishWikipediaUrls'].append(match[1])
    parents = defaultdict(list)
    with ZipFile(args.sources / 'yago-4.6-taxonomy.zip') as archive:
        for number, raw in enumerate(archive.open('yago-taxonomy.ttl'), 1):
            if b'\trdfs:subClassOf\t' in raw:
                child, _, parent = yago.triple(raw)
                parents[child].append((parent, number))
    paths = {}
    for entity in entities.values():
        for kind in {record['type'] for record in entity['types']}:
            if kind not in paths:
                paths[kind] = yago.path_to_root(kind, parents, ROOTS)
        entity['paths'] = {kind: paths[kind] for kind in sorted({r['type'] for r in entity['types']}) if paths[kind]}
    args.out.mkdir(parents=True)
    pipeline.jsonl(args.out / 'names.jsonl', entities.values())
    metadata = dict(schemaVersion=1, snapshots=yago.PINS, inventorySha256=pipeline.digest(args.base / 'inventory.jsonl'),
        baseManifestSha256=pipeline.digest(args.base / 'manifest.json'), files={'names.jsonl': pipeline.digest(args.out / 'names.jsonl')},
        owners=len(entities), asciiInputAliases=ascii_aliases, scope=POLICY)
    (args.out / 'manifest.json').write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')
    print(json.dumps(metadata), flush=True)


def attach(model, entities, rows=(), ascii_input_aliases=False):
    counts = Counter()
    wanted = {row['surface'].casefold() for row in rows}
    for entity in entities:
        if (entity['id'].endswith('_generic_instance') or not entity['wikidataIds'] or not entity['englishWikipediaUrls'] or
                not any('schema:Person' in paths for kind, paths in entity['paths'].items()
                        if kind in {record['type'] for record in entity['types']})):
            counts['unverifiedPerson'] += 1
            continue
        for field in entity['nameFields']:
            if field['relation'] not in yago.NAME_FIELDS:
                counts['notPersonalNameField'] += 1
                continue
            witnesses = spelling_witnesses(field['literal'], entity['labels'], ascii_input_aliases)
            if not witnesses:
                counts['unprovedStandaloneSpelling'] += 1
            for witness in witnesses:
                surface = witness['spelling']
                key = 'yago-qualified-' + hashlib.sha256(json.dumps([field['relation'], surface]).encode()).hexdigest()[:24]
                proof = dict(source='yago_english_name', approved=True, url=yago.URL, version=yago.VERSION, snapshots=yago.PINS,
                    entityId=entity['id'], wikidataIds=entity['wikidataIds'], englishWikipediaUrls=entity['englishWikipediaUrls'],
                    nameEvidence=field, spellingWitness=witness, types=entity['types'], verifiedTypePaths=entity['paths'],
                    producerFormatReferences={name:dict(url='https://github.com/yago-naga/yago-4.6/blob/main/'+name,sha256=sha)
                        for name,sha in FORMAT_REFERENCES.items()},
                    exactHistoricalDumpProducerRevisionClaimed=False,
                    lexicalIdentityIsNameComponentNotPerson=True, relation='qualified_field_with_independent_english_spelling',
                    preferredCaseClaimed=False, scope=POLICY)
                model.add(key, surface, surface, {'noun', 'noun_proper', 'name_person'}, proof, approved=True)
                counts['verifiedNameWitnesses'] += 1
                alias = variants.ascii_name(surface)
                if ascii_input_aliases and alias != surface and alias.casefold() in wanted:
                    model.add(key, surface, alias, {'noun', 'noun_proper', 'name_person'},
                        dict(proof, relation='derived_existing_latin_diacritic_input_alias',
                            canonicalSurface=surface, preferredAsciiSpellingClaimed=False), approved=True)
                    counts['derivedExistingAsciiNameWitnesses'] += 1
    return counts


def extend(args):
    metadata = json.loads((args.prepared / 'manifest.json').read_text())
    if (metadata['schemaVersion'] != 1 or metadata['snapshots'] != yago.PINS or metadata['scope'] not in {PREVIOUS_POLICY,POLICY} or
            pipeline.digest(args.prepared / 'names.jsonl') != metadata['files']['names.jsonl']):
        raise ValueError('Changed qualified-name preparation')
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    if pipeline.digest(args.base / 'inventory.jsonl') != metadata['inventorySha256']:
        raise ValueError('Qualified-name preparation belongs to another inventory')
    counts = attach(model, list(map(json.loads, (args.prepared / 'names.jsonl').open())), rows,
        metadata.get('asciiInputAliases', False))
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    states = list(map(json.loads, (args.base / 'status.jsonl').open()))
    selected = [row for row, state in zip(rows, states) if state['decision'] == 'pending' or row['id'] in reopened]
    additions = named_case_variants.source_name_candidates(model, selected)
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    existing = {row['id'] for row in corrections}
    corrections += [row for row in additions if row['id'] not in existing]
    sources['qualifiedPersonalNameFields'] = dict(preparedManifestSha256=pipeline.digest(args.prepared / 'manifest.json'),
        snapshots=yago.PINS, asciiInputAliases=metadata.get('asciiInputAliases', False), policy=POLICY,
        asciiAliasPolicy='optional existing decomposable Latin-diacritic input aliases preserve the source name and independent English spelling witness; never arbitrary transliteration or preferred ASCII spelling')
    notices['YAGO-QUALIFIED-NAME-FIELDS-NOTICE.txt'] = ('YAGO 4.6, YAGO team of Télécom Paris; underlying Wikidata contributors.\n' +
        yago.URL + '\nCC BY 4.0; full license retained in CC-BY-4.0.txt.\nChanges: ' + POLICY + '.\n').encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.qualified-names-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'
        pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, reopenedMachineExclusions=len(reopened),
        **{key: summary[key] for key in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ['prepare', 'extend']:
        command = commands.add_parser(name)
        for key in (['base', 'sources', 'out'] if name == 'prepare' else ['base', 'seed', 'prepared', 'out']):
            command.add_argument('--' + key, type=Path, required=True)
        if name == 'prepare':
            command.add_argument('--ascii-input-aliases', action='store_true', help='Also match literal single-name fields and explicitly derived existing Latin-diacritic keyboard aliases, with the same independent English spelling requirement')
    args = parser.parse_args()
    prepare(args) if args.command == 'prepare' else extend(args)
