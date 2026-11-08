"""Frozen public world-vocabulary evidence. Never creates targets or model calls."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.error
from urllib.parse import urlencode

import dictionary_sources as download
import vocabulary_harness as h

PROVIDERS = {'wikidata', 'wiktionary', 'qudt', 'chebi'}
KINDS = {'lexical', 'person', 'product', 'organization', 'brand', 'service', 'language'}
STATIC = {
    'qudt': ('qudt.ttl', 'https://raw.githubusercontent.com/qudt/qudt-public-repo/main/src/main/rdf/vocab/quantitykinds/VOCAB_QUDT-QUANTITY-KINDS-ALL.ttl',
             'WORLD-QUDT-LICENSE.txt', 'https://raw.githubusercontent.com/qudt/qudt-public-repo/main/LICENSE', 'CC-BY-4.0'),
    'chebi': ('chebi.obo', 'https://ftp.ebi.ac.uk/pub/databases/chebi/ontology/chebi_lite.obo',
              'WORLD-CC-BY-4.0.txt', 'https://creativecommons.org/licenses/by/4.0/legalcode.txt', 'CC-BY-4.0'),
}
NOTICES = {
    'WORLD-CC0-1.0.txt': 'https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt',
    'WORLD-CC-BY-SA-4.0.txt': 'https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt',
}


def specifications(scopes_path):
    config = h.replay.read_json(scopes_path)
    h.require(config.get('worldSources') == 1, 'World sources are not enabled')
    filename = config['entityTargets']
    h.require(Path(filename).name == filename, 'Invalid entity target path')
    entities_path = scopes_path.parent / filename
    entities = h.replay.read_json(entities_path)
    h.require(entities['schemaVersion'] == 1, 'Unknown entity scope')
    required = {(term, scope['kind']) for scope in config['scopes'] if 'wikidata' in scope['sources'] for term in scope['terms']}
    ids = set()
    for entry in entities['entities']:
        key = entry['surface'], entry['kind']
        h.require(key not in ids and entry['kind'] in KINDS and isinstance(entry['title'], str)
            and entry['title'].strip() and entry['reason'].strip(), 'Invalid/duplicate entity target')
        ids.add(key)
    h.require(required == ids, 'Entity scope and declared targets differ')
    words = sorted({term for scope in config['scopes'] if 'wiktionary' in scope['sources'] for term in scope['terms']})
    return entities['entities'], words, dict(scopesSha256=h.replay.sha(scopes_path), entitiesSha256=h.replay.sha(entities_path))


def batch_url(provider, titles):
    if provider == 'wikidata':
        return 'https://www.wikidata.org/w/api.php?' + urlencode(dict(action='wbgetentities', sites='enwiki',
            titles='|'.join(titles), props='info|labels|aliases|claims|sitelinks/urls', languages='en|mul', format='json'))
    return 'https://en.wiktionary.org/w/api.php?' + urlencode(dict(action='query', titles='|'.join(titles),
        prop='revisions', rvprop='ids|timestamp|content', rvslots='main', format='json'))


def fetch(directory, scopes_path):
    directory = h.external(directory)
    entities, words, pins = specifications(scopes_path)
    manifest_path = directory / 'world-sources.json'
    if manifest_path.exists():
        return verify(directory, scopes_path)
    directory.mkdir(parents=True, exist_ok=True)
    files, batches = {}, []

    def save(name, url, limit=16 * 1024 * 1024):
        path = directory / name
        if not path.exists():
            for attempt in range(6):
                try:
                    download.download(url, path, limit)
                    break
                except urllib.error.HTTPError as error:
                    if error.code not in {429, 503} or attempt == 5:
                        raise
                    delay = error.headers.get('Retry-After', '')
                    if delay.isdigit() and int(delay) > 60:
                        raise ValueError('Source requested a longer pause; rerun after ' + delay + ' seconds') from error
                    time.sleep(min(60, max(5, int(delay) if delay.isdigit() else 5 * 2 ** attempt)))
            time.sleep(2)
        files[name] = dict(url=url, sha256=h.replay.sha(directory / name))

    for provider, titles in [('wikidata', sorted({r['title'] for r in entities})), ('wiktionary', words)]:
        for start in range(0, len(titles), 25):
            chunk = titles[start:start + 25]
            url = batch_url(provider, chunk)
            name = provider + '-' + hashlib.sha256(url.encode()).hexdigest()[:24] + '.json'
            save(name, url)
            payload = h.replay.read_json(directory / name)
            if 'error' in payload:
                (directory / name).unlink()  # Error responses are not source snapshots.
            h.require('error' not in payload, 'Source API error: ' + str(payload.get('error')))
            batches.append(dict(provider=provider, file=name, titles=chunk))
    for _, (name, url, notice, notice_url, _) in STATIC.items():
        save(name, url, 96 * 1024 * 1024)
        save(notice, notice_url, 1024 * 1024)
    for name, url in NOTICES.items():
        save(name, url, 1024 * 1024)
    attribution = directory / 'WORLD-SOURCE-ATTRIBUTION.txt'
    attribution.write_text(
        'World vocabulary: project-curated required words and named entities, not frequency-ranked recommendations.\n'
        'Wikidata contributors: structured labels, aliases, English sitelink titles and entity identifiers, CC0 1.0.\n'
        'https://www.wikidata.org/wiki/Wikidata:Licensing\n'
        'Wiktionary contributors: English headword/section attestation, CC BY-SA 4.0.\n'
        'https://en.wiktionary.org/wiki/Wiktionary:Copyrights\n'
        'QUDT.org contributors: English quantity-kind labels, CC BY 4.0. https://qudt.org/\n'
        'ChEBI / EMBL-EBI contributors: curated non-obsolete names and exact synonyms, CC BY 4.0.\n'
        'https://www.ebi.ac.uk/chebi/about/\n'
        'Changes: select explicitly declared spellings; match ordinary lowercase targets to source heading case; '
        'attach project-declared topical memberships. Names retain exact source case.\n'
        'No article prose, definitions, quotations, images, identifiers as invented words, or generated inflections are included.\n', encoding='utf-8')
    files[attribution.name] = dict(sha256=h.replay.sha(attribution))
    manifest = dict(schemaVersion=1, pins=pins, files=files, batches=batches,
        recordedAt=h.dt.datetime.now(h.dt.timezone.utc).isoformat())
    h.dump(manifest_path, manifest)
    return verify(directory, scopes_path)


def verify(directory, scopes_path):
    entities, words, pins = specifications(scopes_path)
    manifest = h.replay.read_json(directory / 'world-sources.json')
    h.require(manifest['schemaVersion'] == 1 and manifest['pins'] == pins, 'World scope changed; use a new snapshot')
    expected_titles = {'wikidata': sorted({e['title'] for e in entities}), 'wiktionary': words}
    for provider, titles in expected_titles.items():
        actual = [title for batch in manifest['batches'] if batch['provider'] == provider for title in batch['titles']]
        h.require(sorted(actual) == titles, 'Incomplete/duplicate source request set: ' + provider)
    expected = {r[0] for r in STATIC.values()} | {r[2] for r in STATIC.values()} | set(NOTICES) | {'WORLD-SOURCE-ATTRIBUTION.txt'}
    for batch in manifest['batches']:
        h.require(batch['provider'] in {'wikidata', 'wiktionary'} and
            re.fullmatch(batch['provider'] + r'-[0-9a-f]{24}\.json', batch['file']) and
            manifest['files'][batch['file']]['url'] == batch_url(batch['provider'], batch['titles']), 'Changed source request')
        expected.add(batch['file'])
    h.require(set(manifest['files']) == expected, 'Missing/extra world source files')
    for name, record in manifest['files'].items():
        path = directory / name
        h.require(Path(name).name == name and path.is_file() and not path.is_symlink() and
            h.replay.sha(path) == record['sha256'], 'Changed world source/notice: ' + name)
    for name, url, notice, notice_url, _ in STATIC.values():
        h.require(manifest['files'][name]['url'] == url and manifest['files'][notice]['url'] == notice_url, 'Changed world source identity')
    h.require(all(manifest['files'][name]['url'] == url for name, url in NOTICES.items()), 'Changed notice identity')
    return manifest


def english_section(text):
    parts = re.split(r'^==\s*([^=\n]+?)\s*==\s*$', text, flags=re.M)
    return next((parts[i + 1] for i in range(1, len(parts), 2) if parts[i].strip() == 'English'), None)


def wikidata_values(entity):
    # mul is Wikidata's documented default label/alias language, not transliteration.
    values = []
    for language in ['en', 'mul']:
        label = entity.get('labels', {}).get(language)
        if label:
            values.append((label['value'], 'label:' + language))
        values.extend((a['value'], 'alias:' + language) for a in entity.get('aliases', {}).get(language, []))
    return values


def wikidata_attestation(spec, entity):
    claims = entity.get('claims', {}).get('P31', [])
    types = {r['mainsnak'].get('datavalue', {}).get('value', {}).get('id') for r in claims if r.get('rank') != 'deprecated'}
    if not re.fullmatch(r'Q[1-9][0-9]*', entity.get('id', '')) or 'Q4167410' in types:
        return []
    if (spec['kind'] == 'person') != ('Q5' in types):
        return []
    site = entity.get('sitelinks', {}).get('enwiki', {})
    if site.get('title', '').replace('_', ' ').casefold() != spec['title'].replace('_', ' ').casefold():
        return []
    lower = spec['kind'] == 'lexical' and spec['surface'].islower()
    matches = [(label, field) for label, field in wikidata_values(entity)
        if label == spec['surface'] or lower and label.casefold() == spec['surface']]
    if matches:
        return matches
    label = site['title']
    return [(label, 'sitelink:enwiki')] if label == spec['surface'] or lower and label.casefold() == spec['surface'] else []


def obo_terms(path):
    """Read OBO records and exact synonyms; no inference from chemical IDs/formulae."""
    term = None
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            line = line.rstrip('\n')
            if line.startswith('['):
                if term:
                    yield term
                term = defaultdict(list) if line == '[Term]' else None
            elif term is not None and ': ' in line:
                key, value = line.split(': ', 1)
                term[key].append(value)
    if term:
        yield term


def indices(directory, scopes_path):
    manifest = verify(directory, scopes_path)
    specs, _, _ = specifications(scopes_path)
    by_title = defaultdict(list)
    words = {}
    for batch in manifest['batches']:
        payload = h.replay.read_json(directory / batch['file'])
        if batch['provider'] == 'wikidata':
            for entity in payload.get('entities', {}).values():
                title = entity.get('sitelinks', {}).get('enwiki', {}).get('title', '')
                by_title[title.replace('_', ' ').casefold()].append((entity, batch['file']))
        else:
            for page in payload.get('query', {}).get('pages', {}).values():
                if page.get('ns') != 0 or 'missing' in page or not page.get('revisions'):
                    continue
                revision = page['revisions'][0]
                section = english_section(revision['slots']['main']['*'])
                if section is not None:
                    words[page['title']] = (revision['revid'], batch['file'],
                        'noun' if re.search(r'\{\{en-noun(?:[|}])', section) else None)
    config = h.replay.read_json(scopes_path)
    wanted = {term for scope in config['scopes'] for term in scope['terms']}
    lower_wanted = {term for scope in config['scopes'] if scope['kind'] == 'lexical'
                    for term in scope['terms'] if term.islower()}
    records = defaultdict(list)

    def proof(surface, provider, file, url, license_id, **extra):
        for key in ({surface} & wanted) | ({surface.casefold()} & lower_wanted):
            record = dict(source=provider, sha256=manifest['files'][file]['sha256'],
                url=url, license=license_id, **extra)
            record.setdefault('attestedLabel', surface)
            records[key].append(record)

    for spec in specs:
        for entity, file in by_title[spec['title'].replace('_', ' ').casefold()]:
            for label, field in wikidata_attestation(spec, entity):
                proof(spec['surface'], 'wikidata', file, 'https://www.wikidata.org/w/index.php?' +
                    urlencode(dict(title=entity['id'], oldid=entity['lastrevid'])), 'CC0-1.0',
                    entity=entity['id'], revision=entity['lastrevid'], field=field, attestedLabel=label,
                    kind=spec['kind'], selectionReason=spec['reason'])
    for surface, (revision, file, head_role) in words.items():
        proof(surface, 'wiktionary', file, 'https://en.wiktionary.org/w/index.php?' + urlencode(dict(title=surface, oldid=revision)),
            'CC-BY-SA-4.0', revision=revision, section='English', headRole=head_role)
    from rdflib import Graph
    from rdflib.namespace import RDFS
    graph = Graph().parse(directory / 'qudt.ttl', format='turtle')
    for subject, label in graph.subject_objects(RDFS.label):
        if (label.language or '').lower() in {'en', 'en-us'} and str(subject).replace('https:', 'http:', 1).startswith('http://qudt.org/vocab/quantitykind/'):
            proof(str(label), 'qudt', 'qudt.ttl', str(subject).replace('http:', 'https:', 1), 'CC-BY-4.0')
    for term in obo_terms(directory / 'chebi.obo'):
        curated = set(term.get('subset', [])) & {'3:STAR', '3_STAR'}
        if term.get('is_obsolete') == ['true'] or not curated:
            continue
        labels = list(term.get('name', []))
        for synonym in term.get('synonym', []):
            match = re.match(r'"((?:[^"\\]|\\.)*)" EXACT ', synonym)
            if match:
                labels.append(re.sub(r'\\([\\"])', r'\1', match[1]))
        for label in labels:
            proof(label, 'chebi', 'chebi.obo', 'https://www.ebi.ac.uk/chebi/searchId.do?chebiId=' + term['id'][0], 'CC-BY-4.0',
                entity=term['id'][0], curation=sorted(curated)[0])
    return records, manifest


def matching(index, surface, kind, providers):
    lower = kind == 'lexical' and surface.islower()
    candidates = list(index.get(surface, []))
    if lower:
        candidates += index.get(surface.casefold(), [])
    seen, result = set(), []
    for record in candidates:
        if record['source'] not in providers or record.get('kind', kind) != kind:
            continue
        value = json.dumps(record, sort_keys=True)
        if value not in seen:
            seen.add(value)
            result.append(dict(record))
    return result
