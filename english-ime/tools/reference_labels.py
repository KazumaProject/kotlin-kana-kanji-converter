"""Import factual identifiers from pinned complete public reference tables.

Pokemon English species names describe fictional entities, not biological taxa.
C++ standard stream objects are symbols, not API types, keywords or English POS.
This offline tool exports identifiers and provenance, never source prose/artwork.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import tempfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending

POKEMON_REVISION = 'e5b79b2e15d7c50735a945936afd4cd1cfd94eae'
POKEMON_PINS = {
    'LICENSE.md': '1c04595dc662981c20956ae4251dfa7b62b475c345eddf98bc9b904cb2373f2c',
    'data/v2/csv/languages.csv': 'fbb60019a6a461783d5671a995d5f590db61792a273e90faa0ed630d102a19b8',
    'data/v2/csv/pokemon_species.csv': 'e66e2eeb25fd3836b0ebab6bf87bbf01960aa3c0555e2bac495fa8393c5e0c45',
    'data/v2/csv/pokemon_species_names.csv': '820cde17074cdb1c2b0595c997fb8f998e773bd5da3bb525dec85703c86c5fd9',
}
CPP_REVISION = 'd4d6f38143c1b495aa33b2e5de0e0ec2daa173ca'
CPP_PIN = '97109de6a7f8603b6443de2069d0fb514bfe8f415105963bd59897114cc8e01a'
STREAM_OBJECTS = {'cin': 'istream', 'cout': 'ostream', 'cerr': 'ostream', 'clog': 'ostream',
                  'wcin': 'wistream', 'wcout': 'wostream', 'wcerr': 'wostream', 'wclog': 'wostream'}


def pokemon_records(languages, species, names):
    languages = list(csv.DictReader(io.StringIO(languages)))
    english = [r['id'] for r in languages if r['identifier'] == 'en' and r['iso639'] == 'en' and r['official'] == '1']
    if len(english) != 1:
        raise ValueError('Missing unique official English language identity')
    species = list(csv.DictReader(io.StringIO(species)))
    identifiers = {r['id'] for r in species}
    if len(identifiers) != len(species) or any(not re.fullmatch('[1-9][0-9]*', value) for value in identifiers):
        raise ValueError('Invalid or duplicate species identity')
    records = []; seen = set()
    for row in csv.DictReader(io.StringIO(names)):
        if row['local_language_id'] != english[0]:
            continue
        identity = row['pokemon_species_id']; label = row['name']
        if identity not in identifiers or identity in seen or not label or any(c in label for c in '\t\r\n'):
            raise ValueError('Invalid or duplicate English species name')
        seen.add(identity)
        records.append(dict(identity='pokemon-species-' + identity, label=label, entityKind='fictional_species',
            speciesId=identity, languageId=english[0], language='en', sourceRevision=POKEMON_REVISION,
            sourceFile='data/v2/csv/pokemon_species_names.csv', snapshotSha256=POKEMON_PINS['data/v2/csv/pokemon_species_names.csv'],
            url='https://github.com/PokeAPI/pokeapi/blob/' + POKEMON_REVISION + '/data/v2/csv/pokemon_species_names.csv'))
    if seen != identifiers:
        raise ValueError('Incomplete English species name table')
    return records


def stream_records(text):
    start = text.index('\\rSec2[iostream.syn]'); end = text.index('\\rSec2[iostream.objects.overview]', start)
    section = text[start:end]
    blocks = re.findall(r'\\begin\{codeblock\}(.*?)\\end\{codeblock\}', section, re.S)
    if len(blocks) != 1:
        raise ValueError('Unexpected stream synopsis block')
    namespace = re.search(r'\bnamespace std\s*\{([^{}]*)\}', blocks[0], re.S)
    if not namespace:
        raise ValueError('Missing explicit standard namespace')
    declarations = re.findall(r'extern\s+(istream|ostream|wistream|wostream)\s+([a-z]+)\s*;', namespace[1])
    if len(declarations) != len(STREAM_OBJECTS) or {name: kind for kind, name in declarations} != STREAM_OBJECTS:
        raise ValueError('Changed standard stream object declarations')
    remainder = re.sub(r'extern\s+(istream|ostream|wistream|wostream)\s+([a-z]+)\s*;', '', namespace[1])
    if remainder.strip():
        raise ValueError('A function or other declaration is not a stream object')
    return [dict(identity='cpp-std-' + name, label=name, qualifiedIdentifier='std::' + name,
        namespace='std', declaredType=kind, entityKind='standard_cpp_stream_object', sourceRevision=CPP_REVISION,
        sourceFile='source/iostreams.tex', snapshotSha256=CPP_PIN,
        url='https://github.com/cplusplus/draft/blob/' + CPP_REVISION + '/source/iostreams.tex')
        for kind, name in declarations]


def load(pokemon, cpp):
    for name, expected in POKEMON_PINS.items():
        if pipeline.digest(pokemon / name) != expected:
            raise ValueError('Changed Pokemon reference table or license: ' + name)
    if pipeline.digest(cpp / 'iostreams.tex') != CPP_PIN:
        raise ValueError('Changed C++ stream synopsis')
    tables = [(pokemon / ('data/v2/csv/' + name)).read_text() for name in (
        'languages.csv', 'pokemon_species.csv', 'pokemon_species_names.csv')]
    return pokemon_records(*tables) + stream_records((cpp / 'iostreams.tex').read_text())


def attach(model, rows, records, corrections):
    by_name = defaultdict(list); counts = Counter()
    for row in rows:
        by_name[row['surface'].casefold()].append(row)
    for record in records:
        if record['entityKind'] not in {'fictional_species', 'standard_cpp_stream_object'}:
            raise ValueError('Unsupported reference entity kind')
        label = record['label']; is_name = record['entityKind'] == 'fictional_species'
        selected = list(by_name[label.casefold()])
        if is_name and ' ' in label:
            selected += [r for r in by_name[label.replace(' ', '').casefold()] if r['id'].startswith('manual:')]
        if not is_name:
            selected = [r for r in selected if r['surface'] == label]
        if not selected:
            continue
        members = ({'noun', 'noun_proper', 'name_fictional', 'domain_entertainment'} if is_name else
                   {'symbol', 'domain_technology'})
        extension.ensure_categories(model, members)
        proof = dict(source='published_reference_label', url=record['url'], approved=True, labelEvidence=record,
            scope='published complete English fictional-species name or case-sensitive standard C++ stream object identifier; no source prose, artwork, inferred ordinary English POS, inflections, current availability or corpus-intent claim')
        key = 'reference-label-' + hashlib.sha256(record['identity'].encode()).hexdigest()[:24]
        model.add(key, label, label, members, proof, approved=True)
        counts[record['entityKind']] += 1
        for row in selected:
            surface = row['surface']
            if surface == label:
                continue
            if row['id'].startswith('manual:') and is_name:
                model.add(key, label, surface, members, dict(proof, relation='existing_manual_case_or_space_free_alias',
                    legacySourceId=row['id'], originalSurface=surface), approved=True)
                continue
            if surface != surface.lower() or pipeline.keyboard_reading(label) != row['reading']:
                raise ValueError('Reference table cannot invent an input mapping')
            existing = {r['target']: dict(r) for r in corrections if r['id'] == row['id']}
            existing.setdefault(label, dict(id=row['id'], source=surface, target=label, evidence=record['url']))
            if model.approved.get(surface):
                original = [e['url'] for k in model.approved[surface] for e in model.evidence[k, surface]
                            if e.get('approved', True) and not e.get('requiresFullNamedContext', False)]
                if original:
                    existing.setdefault(surface, dict(id=row['id'], source=surface, target=surface, evidence=min(original)))
            corrections[:] = [r for r in corrections if r['id'] != row['id']]
            spelling = any(value.casefold() != surface.casefold() for value in existing)
            relation = ('input_spelling_correction' if len(existing) == 1 else 'input_spelling_candidates') if spelling else ('case_correction' if len(existing) == 1 else 'case_candidates')
            corrections += [dict(value, relation=relation) for _, value in sorted(existing.items())]
    return counts


def extend(args):
    records = load(args.pokemon, args.cpp)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    path = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(path, 'corrections') if path.is_file() else []
    counts = attach(model, rows, records, corrections)
    path = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(path, 'decisions') if path.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending, corrections)
    sources['publishedReferenceLabels'] = dict(pokemonRevision=POKEMON_REVISION, pokemonFiles=POKEMON_PINS,
        cppRevision=CPP_REVISION, cppSourceSha256=CPP_PIN, policy='complete locale-verified fictional names and explicitly declared stream object identifiers; case-sensitive objects, no name-fragment or slug inference, no English morphology')
    notices['POKEAPI-REFERENCE-LICENSE.txt'] = (args.pokemon / 'LICENSE.md').read_bytes()
    notices['PUBLISHED-REFERENCE-LABELS-NOTICE.txt'] = (
        'Pokemon names: PokeAPI contributors, https://github.com/PokeAPI/pokeapi/tree/' + POKEMON_REVISION +
        ' ; BSD-3-Clause notice retained separately. Pokemon and Pokemon character names are trademarks of Nintendo. '
        'Only complete English name facts and resource IDs are selected; no genus prose, flavor text, artwork or endorsement.\n'
        'C++ standard stream object name, namespace and declared-type facts: cplusplus/draft, https://github.com/cplusplus/draft/tree/' + CPP_REVISION +
        ' ; source/iostreams.tex [iostream.syn]. No ISO draft prose or source code is redistributed; no license grant to ISO text, published-edition status or installed implementation support is asserted.\n').encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.reference-labels-', dir=args.out.parent) as temp:
        reviewed = Path(temp) / 'reviews.tsv'; pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, reopenedMachineExclusions=len(reopened),
        **{k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'pokemon', 'cpp', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
