"""Prepare and join English names from a pinned YAGO 4.6 bulk snapshot.

This module makes no network requests. It does not split personal names, infer
missing aliases, treat generic instances as people, or copy entity facts other
than attested names, type paths and source identities into the dictionary.
"""
import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time
import zipfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
from wiktionary_index import Index

VERSION = '4.6'
URL = 'https://yago-knowledge.org/data/yago4.6/yago-4.6-facts.zip'
PINS = {'yago-4.6-facts.zip': 'f9b57f355f0b1f8bf5b968ac20f33778fce2b521c675c5a7d28f0afd4f1c14b1',
    'yago-4.6-taxonomy.zip': '6cc9f409ee96208dbba79d571e0471b69efc73d0f2384c3250e8b27942a95278',
    'yago-4.6-schema.zip': '01a4f4fd80a04ce38375163993644e8370da3b6761b3e8cc703be97cc5a3d07a'}
ROOTS = {'schema:Person': {'name_person'}, 'schema:Place': {'name_place'},
    'schema:Organization': {'name_organization'},
    # CreativeWork also contains functions, hypotheses and other concepts.
    # Require a specific documented kind; never promote that broad root.
    'schema:Book': {'name_work'}, 'schema:TVSeries': {'name_work'},
    'schema:MusicComposition': {'name_work'}, 'yago:Magazine': {'name_work'},
    'yago:Media_franchise': {'name_work'}, 'yago:Video_Game_Series': {'name_work'},
    'yago:Software_system': {'name_product','domain_technology'},
    'yago:Operating_System_Distribution': {'name_product','domain_technology'},
    'yago:Plug-in_computing': {'name_product','domain_technology'},
    'yago:Product_Model': {'name_product'}, 'yago:Trademark': {'name_brand'},
    'yago:File_Format_Family': {'identifier_data_format','domain_technology'}}
NAME_FIELDS = {'schema:givenName', 'schema:familyName'}
LITERAL = re.compile(r'"((?:[^"\\]|\\.)*)"(?:@([A-Za-z0-9-]+))?')
ESCAPES = {'t':'\t', 'b':'\b', 'n':'\n', 'r':'\r', 'f':'\f', '"':'"', "'":"'", '\\':'\\'}


def literal(value):
    match = LITERAL.fullmatch(value)
    if not match:
        return None
    def unescape(token):
        value = token[1]
        if value in ESCAPES:
            return ESCAPES[value]
        if re.fullmatch(r'u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8}', value):
            number = int(value[1:], 16)
            if number > 0x10ffff or 0xd800 <= number <= 0xdfff:
                raise ValueError('Invalid Unicode scalar in Turtle name')
            return chr(number)
        raise ValueError('Unsupported Turtle name escape')
    text = re.sub(r'\\(u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8}|.)', unescape, match[1])
    if any(character in text for character in '\t\r\n'):
        return None  # Not a TSV-safe dictionary name; never silently rewrite it.
    return text, match[2].lower() if match[2] else None


def english(language):
    return language == 'en' or bool(language and language.startswith('en-'))


def name_language(language):
    # Wikidata's shared international proper names use `mul`. They are usable
    # only with the separately verified English-Wikipedia/named-instance scope.
    # This never imports arbitrary foreign-language lexical senses.
    return english(language) or language == 'mul'


def triple(raw):
    fields = raw.decode('utf-8').rstrip('\r\n').split('\t')
    if len(fields) != 4 or fields[-1] != '.':
        raise ValueError('Unexpected YAGO Turtle triple layout')
    return fields[:3]


def path_to_root(start, parents, roots=ROOTS):
    queue = deque([(start, [])]); seen = set(); paths = {}
    while queue:
        node, path = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        if node in roots:
            paths[node] = path
        for parent, line in sorted(parents.get(node, [])):
            queue.append((parent, path + [{'child':node, 'parent':parent, 'line':line}]))
    return paths


def matching_mode(label, wanted, manual_compact):
    if label.casefold() in wanted:
        return 'exact_casefold'
    if ' ' in label and label.replace(' ', '').casefold() in manual_compact:
        return 'existing_manual_space_free_name'
    return None


def prepare(args):
    if args.out.exists():
        raise ValueError('Output already exists')
    pipeline.verify(args.base)
    for name, expected in PINS.items():
        if not expected or pipeline.digest(args.sources / name) != expected:
            raise ValueError('Unpinned or changed YAGO snapshot: ' + name)
    rows = pipeline.inventory(args.base / 'inventory.jsonl')
    states = [json.loads(line) for line in (args.base / 'status.jsonl').read_text().splitlines()]
    selected = [row for row, state in zip(rows, states) if state['decision'] != 'include' or row['id'].startswith('manual:')]
    wanted = {row['surface'].casefold() for row in selected}
    manual_compact = {row['surface'].casefold() for row in selected if row['id'].startswith('manual:') and ' ' not in row['surface']}
    matched = defaultdict(list); start = time.monotonic(); total = 0
    relevant = {b'rdfs:label', b'schema:alternateName', b'schema:givenName', b'schema:familyName'}
    with zipfile.ZipFile(args.sources / 'yago-4.6-facts.zip') as archive:
        if archive.namelist() != ['yago-facts.ttl']:
            raise ValueError('Unexpected YAGO facts archive')
        with archive.open('yago-facts.ttl') as stream:
            for number, raw in enumerate(stream, 1):
                total = number
                fields = raw.split(b'\t', 2)
                if len(fields) > 1 and fields[1] in relevant:
                    subject, predicate, obj = triple(raw)
                    value = literal(obj)
                    if value and (name_language(value[1]) or predicate in NAME_FIELDS and value[1] is None):
                        mode = matching_mode(value[0], wanted, manual_compact)
                        if mode:
                            matched[subject].append({'predicate':predicate,'label':value[0],'language':value[1],
                                'line':number,'tripleSha256':hashlib.sha256(raw).hexdigest(),'matchingMode':mode})
                if number % 1000000 == 0:
                    print(json.dumps({'pass':1,'lines':number,'matchedEntities':len(matched),'seconds':round(time.monotonic()-start,1)}),flush=True)
        entities = {key:{'id':key,'matches':value,'labels':[],'types':[],'wikidataIds':[],'englishWikipediaUrls':[]} for key,value in sorted(matched.items())}
        with archive.open('yago-facts.ttl') as stream:
            for number, raw in enumerate(stream, 1):
                fields = raw.split(b'\t', 1)
                subject = fields[0].decode('utf-8')
                if subject in entities and len(fields) == 2:
                    subject, predicate, obj = triple(raw); entity = entities[subject]
                    if predicate == 'rdf:type':
                        entity['types'].append({'type':obj,'line':number,'tripleSha256':hashlib.sha256(raw).hexdigest()})
                    elif predicate == 'rdfs:label':
                        value = literal(obj)
                        if value and name_language(value[1]): entity['labels'].append({'label':value[0],'language':value[1],'line':number,'tripleSha256':hashlib.sha256(raw).hexdigest()})
                    elif predicate == 'owl:sameAs' and re.fullmatch(r'wd:Q[1-9][0-9]*',obj): entity['wikidataIds'].append(obj)
                    elif predicate == 'schema:url':
                        value = re.fullmatch(r'"(https://en\.wikipedia\.org/wiki/[^"\\]+)"\^\^xsd:anyURI',obj)
                        if value: entity['englishWikipediaUrls'].append(value[1])
                if number % 1000000 == 0:
                    print(json.dumps({'pass':2,'lines':number,'matchedEntities':len(entities),'seconds':round(time.monotonic()-start,1)}),flush=True)
    parents = defaultdict(list)
    with zipfile.ZipFile(args.sources / 'yago-4.6-taxonomy.zip') as archive:
        with archive.open('yago-taxonomy.ttl') as stream:
            for number, raw in enumerate(stream,1):
                if b'\trdfs:subClassOf\t' in raw:
                    child, _, parent = triple(raw);parents[child].append((parent,number))
    paths = {}
    for entity in entities.values():
        for record in entity['types']:
            kind = record['type']
            if kind not in paths: paths[kind] = path_to_root(kind, parents)
        entity['paths'] = {record['type']:paths[record['type']] for record in entity['types'] if paths[record['type']]}
    args.out.mkdir(parents=True)
    pipeline.jsonl(args.out / 'names.jsonl', entities.values())
    manifest = {'schemaVersion':1,'version':VERSION,'snapshots':PINS,'baseManifestSha256':pipeline.digest(args.base / 'manifest.json'),
        'namedTypeRoots':{key:sorted(value) for key,value in sorted(ROOTS.items())},
        'inventorySha256':pipeline.digest(args.base / 'inventory.jsonl'),'scannedFactsLinesPerPass':total,
        'matchedEntities':len(entities),'taxonomyEdges':sum(map(len,parents.values())),
        'files':{'names.jsonl':pipeline.digest(args.out / 'names.jsonl')},
        'scope':'nonincluded input rows and all existing manual rows; exact English or shared international (mul) names/aliases, later requiring an English Wikipedia named instance, or literal person-name fields; no network queries or name splitting'}
    (args.out / 'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps(manifest),flush=True)


def attach(model, rows, entities):
    extension.ensure_categories(model, set().union(*ROOTS.values()))
    counts = Counter(); manual = defaultdict(list)
    for row in rows:
        if row['id'].startswith('manual:'):manual[row['surface'].replace(' ','').casefold()].append(row)
    for entity in entities:
        if entity['id'].endswith('_generic_instance') or not entity['wikidataIds'] or not entity['englishWikipediaUrls']:
            counts['unverifiedEntityScope'] += 1;continue
        roots = set().union(*(set(value) for value in entity['paths'].values())) & ROOTS.keys()
        values = set().union(*(ROOTS[root] for root in roots))
        if any(value.startswith('name_') for value in values):
            values |= {'noun','noun_proper'}
        if not roots:
            counts['notVerifiedNamedType'] += 1;continue
        labels = sorted(entity['labels'], key=lambda record:(record['language'] != 'en',record['language'],record['label']))
        for match in entity['matches']:
            field = match['predicate'] in NAME_FIELDS
            if field and 'schema:Person' not in roots:
                counts['nameFieldWithoutPersonType'] += 1;continue
            if not field and not labels:
                counts['missingEnglishLabel'] += 1;continue
            label = match['label'];lemma = label if field else labels[0]['label']
            # A shared surname/given-name string is a lexical name component,
            # not one new full-person interpretation per witness. Keep the
            # witnesses in evidence without making thousands of lookup forms.
            identity = ['name_component',match['predicate'],label] if field else ['entity_name',entity['id']]
            key = 'yago-' + hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
            member = {'noun','noun_proper','name_person'} if field else values
            proof = {'source':'yago_english_name','url':URL,'version':VERSION,'snapshots':PINS,
                'entityId':entity['id'],'wikidataIds':entity['wikidataIds'],'englishWikipediaUrls':entity['englishWikipediaUrls'],
                'nameEvidence':match,'types':entity['types'],'verifiedTypePaths':entity['paths'],'approved':True,
                'lexicalIdentityIsNameComponentNotPerson':field,
                'scope':'attested English or shared international name/alias of a typed named entity, or an explicit personal name field in its English-Wikipedia context; no arbitrary foreign lexical senses, splitting names, inferred inflection, current status or corpus intent'}
            if not field:
                model.add(key,lemma,lemma,member,dict(proof,primaryLabelEvidence=labels[0]),approved=True)
            model.add(key,lemma,label,member,proof,approved=True)
            counts['verifiedNameFieldSenses' if field else 'verifiedEnglishNameSenses'] += 1
            for row in manual[label.replace(' ','').casefold()]:
                original=row['surface']
                if original==label or (' ' in original and ' ' not in label):continue
                model.add(key,lemma,original,member,dict(proof,legacySourceId=row['id'],originalSurface=original,
                    relation='existing_manual_name_case_or_space_free_alias',preferredCaseClaimed=False),approved=True)
                counts['existingManualAliasSenses'] += 1
    return counts


def extend(args):
    metadata=json.loads((args.prepared/'manifest.json').read_text())
    if (metadata['schemaVersion']!=1 or metadata['snapshots']!=PINS or
            metadata.get('namedTypeRoots')!={key:sorted(value) for key,value in sorted(ROOTS.items())} or
            pipeline.digest(args.prepared/'names.jsonl')!=metadata['files']['names.jsonl']):
        raise ValueError('Changed YAGO extraction')
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    if pipeline.digest(args.base/'inventory.jsonl')!=metadata['inventorySha256']:
        raise ValueError('YAGO extraction belongs to another inventory')
    entities=[json.loads(line) for line in (args.prepared/'names.jsonl').read_text().splitlines()]
    counts=attach(model,rows,entities)
    prior=args.base/'reviewed-overrides.tsv';reviews=pipeline.read_table(prior,'decisions') if prior.is_file() else []
    reviews,reopened=resolve_pending.revalidate_machine_reviews(model,reviews,pending)
    states=[json.loads(x) for x in (args.base/'status.jsonl').read_text().splitlines()]
    selected=[row for row,state in zip(rows,states) if state['decision']=='pending' or row['id'] in reopened]
    index=Index(args.index)
    try:exact=list(index.lookup({row['surface'] for row in selected}))
    finally:index.close()
    additions=resolve_pending.cases(model,selected,{entry['word'] for _,entry in exact},resolve_pending.ineligible_exact_words(exact))
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    existing={row['id'] for row in corrections};corrections += [row for row in additions if row['id'] not in existing]
    sources['yagoEnglishNames']={'version':VERSION,'snapshots':PINS,'preparedManifestSha256':pipeline.digest(args.prepared/'manifest.json'),
        'namedTypeRoots':{key:sorted(value) for key,value in sorted(ROOTS.items())},
        'policy':'exact English or shared international (mul) names/aliases with English Wikipedia URLs and Wikidata identity; explicit Person/Place/Organization, specific book/program/music/publication/franchise/software/product-model/brand types, or file-format identifiers; broad CreativeWork never implies a proper name; literal person-name fields only with Person proof; no arbitrary foreign lexical senses, generic instances, name splitting, inferred morphology or corpus-sense claim'}
    notices['YAGO-NAMES-NOTICE.txt']=('YAGO 4.6, YAGO team of Télécom Paris; underlying Wikidata contributors.\nhttps://yago-knowledge.org/downloads/yago-4-6\n'+URL+
        '\nCC BY 4.0; full license retained in CC-BY-4.0.txt.\nChanges: selected attested English/shared international names/aliases and explicit person-name fields matching existing input rows, required English-Wikipedia named-instance context, retained type paths/identities and source line hashes, and related existing manual name spellings. No other biographical facts, arbitrary foreign lexical senses, artwork, generated generic instances or inferred inflections imported.\n').encode()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.yago-name-review-',dir=args.out.parent) as temporary:
        reviewed=Path(temporary)/'reviews.tsv';pipeline.table(reviewed,'decisions',reviews)
        summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,
            reviewed_decisions=reviewed,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,reopenedMachineExclusions=len(reopened),**{key:summary[key] for key in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    for name in ['prepare','extend']:
        command=commands.add_parser(name)
        for arg in (['base','sources','out'] if name=='prepare' else ['base','seed','index','prepared','out']):
            command.add_argument('--'+arg,type=Path,required=True)
    args=parser.parse_args();prepare(args) if args.command=='prepare' else extend(args)
