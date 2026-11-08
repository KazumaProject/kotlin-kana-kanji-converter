"""Versioned dictionary targets, topic coverage and source-only adoption.

Coverage includes existing, deferred and unsupported targets. No IME ranking,
typo generation, model API, or recurring execution is part of this workflow.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
import subprocess
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlparse
import urllib.error

import dictionary_sources as legacy
import vocabulary_harness as h
import vocabulary_sources as lexical
from extend_lexicon import categories_for, roles_for
from prepare_esdb import URL as ESDB_URL
import world_sources
import discovery_sources
import gemini_acquisition
import coverage_sources
import distribution_policy
import role_sources
import dbpedia_sources
import bulk_names
import pantheon_sources
import bulk_food
import people_enrichment
import sensitive_sources

PROFILE = 'dictionary-target-catalog-v2'
CATALOG = h.REPO / 'english-ime/data/catalog'
TOPIC_DOMAINS = lexical.DOMAINS | {'science', 'medical', 'education', 'sports', 'entertainment', 'food'}
DOCUMENTS = {
    'python': ('python-glossary.rst', 'https://raw.githubusercontent.com/python/cpython/3.14/Doc/glossary.rst',
        'PYTHON-LICENSE.txt', 'https://raw.githubusercontent.com/python/cpython/3.14/LICENSE', 'PSF-2.0', 'Python Software Foundation and contributors'),
    'postgres': ('postgres-glossary.sgml', 'https://raw.githubusercontent.com/postgres/postgres/REL_18_STABLE/doc/src/sgml/glossary.sgml',
        'POSTGRES-LICENSE.txt', 'https://raw.githubusercontent.com/postgres/postgres/REL_18_STABLE/COPYRIGHT', 'PostgreSQL', 'PostgreSQL Global Development Group; University of California'),
    'ml': ('ml-glossary.md', 'https://raw.githubusercontent.com/dotnet/docs/main/docs/machine-learning/resources/glossary.md',
        'DOTNET-LICENSE.txt', 'https://raw.githubusercontent.com/dotnet/docs/main/LICENSE', 'CC-BY-4.0', 'Microsoft and .NET documentation contributors'),
    'transformers': ('transformers-glossary.md', 'https://raw.githubusercontent.com/huggingface/transformers/main/docs/source/en/glossary.md',
        'TRANSFORMERS-LICENSE.txt', 'https://raw.githubusercontent.com/huggingface/transformers/main/LICENSE', 'Apache-2.0', 'Hugging Face and Transformers contributors'),
    'kubernetes': ('kubernetes-glossary.html', 'https://kubernetes.io/docs/reference/glossary/',
        'KUBERNETES-LICENSE.txt', 'https://raw.githubusercontent.com/kubernetes/website/main/LICENSE', 'CC-BY-4.0', 'Kubernetes documentation contributors'),
    'linguist': ('languages.yml', 'https://raw.githubusercontent.com/github-linguist/linguist/main/lib/linguist/languages.yml',
        'LINGUIST-LICENSE.txt', 'https://raw.githubusercontent.com/github-linguist/linguist/main/LICENSE', 'MIT', 'GitHub and Linguist contributors'),
}


def identity(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]


def canonical_proofs(records):
    indexed = {}
    for record in records:
        body = {k: v for k, v in record.items() if k != 'id'}
        identifier = identity(body)
        h.require(identifier not in indexed or indexed[identifier] == dict(body, id=identifier), 'Source proof identity collision')
        indexed[identifier] = dict(body, id=identifier)
    return [indexed[k] for k in sorted(indexed)]


def table(path, fields, records):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.ignored = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.ignored += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.ignored = max(0, self.ignored - 1)

    def handle_data(self, text):
        if not self.ignored:
            self.parts.append(text)


def plain(text):
    if '<' in text:
        parser = Text()
        parser.feed(text)
        text = ' '.join(parser.parts)
    return ' '.join(text.split())


def attested(term, text, lowercase_scope=False):
    return bool(re.search(r'(?<![A-Za-z0-9])' + re.escape(term) + r'(?![A-Za-z0-9])', text,
        re.IGNORECASE if lowercase_scope else 0))


def fetch(args):
    directory = h.external(args.source_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'catalog-sources.json'
    if path.exists():
        return verify_documents(directory)
    records = {}
    for name, (filename, url, notice, notice_url, license_id, author) in DOCUMENTS.items():
        legacy.download(url, directory / filename, 6 * 1024 * 1024)
        legacy.download(notice_url, directory / notice, 1024 * 1024)
        records[name] = dict(file=filename, url=url, sha256=h.replay.sha(directory / filename),
            notice=notice, noticeUrl=notice_url, noticeSha256=h.replay.sha(directory / notice),
            license=license_id, attribution=author, recordedAt=h.dt.datetime.now(h.dt.timezone.utc).isoformat())
    h.dump(path, dict(schemaVersion=2, sources=records))
    return records


def verify_documents(directory):
    manifest = h.replay.read_json(directory / 'catalog-sources.json')
    h.require(manifest['schemaVersion'] == 2 and set(manifest['sources']) == set(DOCUMENTS), 'Unknown source collection')
    for name, record in manifest['sources'].items():
        filename, url, notice, notice_url, license_id, author = DOCUMENTS[name]
        h.require([record[k] for k in ['file', 'url', 'notice', 'noticeUrl', 'license', 'attribution']] ==
            [filename, url, notice, notice_url, license_id, author], 'Changed source identity or license')
        for filename, digest in [(filename, record['sha256']), (notice, record['noticeSha256'])]:
            p = directory / filename
            h.require(p.is_file() and not p.is_symlink() and h.replay.sha(p) == digest, 'Changed source or notice: ' + filename)
    return manifest['sources']


def fetch_references(args):
    """Resolve missing spelling evidence, without changing the declared target set."""
    run = h.external(args.work_dir)
    destination = h.external(args.source_dir)
    config = h.replay.read_json(run / 'run.json')
    lexical_dir = Path(config['sourcePaths']['lexical_source_dir'])
    p = legacy.Glossary()
    p.feed((lexical_dir / 'mdn-glossary.html').read_text())
    index = [(label, url) for label, url, _ in p.labels]
    needed = {r['id'] for r in h.json_lines(run / 'before.jsonl') if r['status'] == 'blocked_evidence' and not r['registered']}
    urls = set()
    special = {'large language model': 'LLM', 'input method editor': 'Input_method_editor',
        'inter-process communication': 'IPC', 'content security policy': 'CSP',
        'public key': 'Public-key_cryptography', 'private key': 'Public-key_cryptography',
        'WebSocket': 'WebSockets', 'cross-site request forgery': 'CSRF'}
    for target in h.json_lines(run / 'targets.jsonl'):
        if target['id'] not in needed or 'mdn' not in target['providers']:
            continue
        term = target['surface']
        matches = [url for label, url in index if lexical.key(label) == lexical.key(term) or
            lexical.key(url.rsplit('/', 1)[-1].replace('_', ' ')) == lexical.key(term) or
            (term.isupper() and attested(term, label))]
        urls.update(matches or ['https://developer.mozilla.org/en-US/docs/Glossary/' + quote(special.get(term, term.replace(' ', '_')), safe='_')])
    destination.mkdir(parents=True, exist_ok=True)
    def one(url):
        filename = 'mdn-' + identity(url) + '.html'
        try:
            legacy.download(url, destination / filename, 4 * 1024 * 1024)
            return dict(file=filename, url=url, sha256=h.replay.sha(destination / filename), license='CC-BY-SA-2.5-or-later')
        except (OSError, urllib.error.HTTPError) as error:
            return dict(url=url, error=str(error))
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(one, sorted(urls)))
    manifest = dict(schemaVersion=2, pages=[r for r in records if 'file' in r], failures=[r for r in records if 'error' in r])
    path = destination / 'mdn-pages.json'
    h.require(not path.exists(), 'Reference snapshot already exists')
    h.dump(path, manifest)
    return dict(downloaded=len(manifest['pages']), failed=len(manifest['failures']))


def registry(taxonomy, scopes):
    topics = h.replay.read_json(taxonomy)
    config = h.replay.read_json(scopes)
    h.require(topics['schemaVersion'] == config['schemaVersion'] == 2, 'Unknown target schema')
    by_id = {r['id']: r for r in topics['topics']}
    h.require(len(by_id) == len(topics['topics']) and len({r['category'] for r in by_id.values()}) == len(by_id), 'Duplicate topic')
    for topic in by_id.values():
        h.require(re.fullmatch(r'topic_[a-z0-9_]+', topic['category']) and
            topic['domain'] in TOPIC_DOMAINS and all(isinstance(topic[k], str) and topic[k].strip()
                and not any(c in topic[k] for c in '\t\r\n') for k in ['id', 'label', 'definition', 'examples']), 'Invalid topic')
    for scope in config['scopes']:
        h.require(scope['topic'] in by_id and scope['kind'] in world_sources.KINDS and
            scope['tier'] in {'core', 'extended'} and set(scope['sources']) <= {'esdb', 'wordnet', 'mdn', 'homebrew', *DOCUMENTS, *world_sources.PROVIDERS} and
            all(isinstance(s, str) and s.strip() for s in scope['terms']), 'Invalid scope')
    return by_id, config


def load_sources(args, extra_words=()):
    directory, lexical_dir, esdb = (h.external(getattr(args, k)) for k in ['source_dir', 'lexical_source_dir', 'esdb_dir'])
    documents = verify_documents(directory)
    old = legacy.verify(lexical_dir)
    pins = lexical.source_files(lexical_dir, esdb)
    texts = {name: plain((directory / record['file']).read_text(encoding='utf-8-sig')) for name, record in documents.items()}
    texts['mdn'] = plain((lexical_dir / 'mdn-glossary.html').read_text())
    language_names = set()
    for line in (directory / documents['linguist']['file']).read_text(encoding='utf-8').splitlines():
        if line and not line[0].isspace() and not line.startswith('#') and line.endswith(':'):
            label = line[:-1]
            language_names.add(json.loads(label) if label.startswith('"') else label.strip("'").replace("''", "'"))
    pages = []
    if (directory / 'mdn-pages.json').exists():
        for record in h.replay.read_json(directory / 'mdn-pages.json')['pages']:
            h.require(re.fullmatch(r'mdn-[0-9a-f]{24}\.html', record['file']) and
                record['url'].startswith('https://developer.mozilla.org/en-US/docs/Glossary/') and
                record['license'] == 'CC-BY-SA-2.5-or-later' and
                h.replay.sha(directory / record['file']) == record['sha256'], 'Changed MDN reference')
            pages.append((record, plain((directory / record['file']).read_text(encoding='utf-8'))))
    mdn_parser = legacy.Glossary()
    mdn_parser.feed((lexical_dir / 'mdn-glossary.html').read_text())
    mdn_labels = {s: url for s, url, _ in mdn_parser.labels}
    connection = sqlite3.connect((esdb / 'esdb.db').as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        _, scope = registry(args.taxonomy, args.scopes)
        wanted = {term for group in scope['scopes'] for term in group['terms']}
        wanted.update(extra_words)
        if scope['basicLists']:
            for name in legacy.BASIC:
                with (lexical_dir / name).open(encoding='utf-8-sig', newline='') as stream:
                    basic = list(csv.reader(stream))
                wanted.update(r[0] for r in (basic if 'supplementary' in name else basic[1:]))
            wanted.update({'true', 'false'})
        connection.execute('create temp table requested(word text primary key)')
        connection.executemany('insert into requested values(?)', [(s,) for s in sorted(wanted)])
        # Source size affects prioritization, not whether a required spelling exists.
        rows = [dict(r) for r in connection.execute("""select e.*,min(s.size) size from entries e
            join requested r on r.word=e.word join scowl_ s using(word_id)
            where s.variant_level<=2 and s.group_rank not in ('@','~') and s.entry_rank not in ('@','~')
              and s.usage_note='' and s.tag not in ('[ukfreq]','[stale]','[ukacd]','[plurals]','[-]')
            group by e.word_id order by size,e.word_id""")]
    finally:
        connection.close()
    by_word, paradigms = defaultdict(list), defaultdict(set)
    for row in rows:
        by_word[row['word']].append(row)
        paradigms[row['lemma_id']].add(row['pos'])
    wn = lexical.wordnet(lexical_dir / 'wordnet.tar.gz')
    return dict(documents=documents, legacy=old, pins=pins, texts=texts, mdnLabels=mdn_labels,
                words=by_word, paradigms=paradigms, wordnet=wn, pages=pages, languages=language_names)


def compile_targets(args):
    topics, config = registry(args.taxonomy, args.scopes)
    discovered, discovery_manifest, discovery_notices = (discovery_sources.collect(args.discovery_dir, args.discovery_policy)
        if getattr(args, 'discovery_dir', None) else ([], None, []))
    leads, lead_manifest, lead_notices = (gemini_acquisition.collect(args.gemini_dir, getattr(args, 'gemini_named_review_dir', None))
        if getattr(args, 'gemini_dir', None) else ([], None, []))
    expansion, expansion_manifest, expansion_notices = (coverage_sources.collect(args.coverage_dir, args.coverage_policy)
        if getattr(args, 'coverage_dir', None) else ([], None, []))
    roles,role_manifest=(role_sources.collect(args.role_dir) if getattr(args,'role_dir',None) else ([],None))
    dbpedia,dbpedia_manifest,_=(dbpedia_sources.collect(args.dbpedia_dir,args.dbpedia_policy) if getattr(args,'dbpedia_dir',None) else ([],None,[]))
    bulk,bulk_manifest=(bulk_names.collect(args.bulk_dir) if getattr(args,'bulk_dir',None) else ([],None))
    pantheon,pantheon_manifest,pantheon_notices,_=(pantheon_sources.collect(args.pantheon_dir) if getattr(args,'pantheon_dir',None) else ([],None,[],[]))
    food,food_manifest,food_notices=(bulk_food.collect(args.food_dir) if getattr(args,'food_dir',None) else ([],None,[]))
    enrichment,enrichment_manifest=(people_enrichment.collect(args.enrichment_dir,args.pantheon_dir) if getattr(args,'enrichment_dir',None) else ([],None))
    _,sensitive_manifest,_=(sensitive_sources.collect(args.sensitive_dir,args.pantheon_dir,public_people=dbpedia+bulk+roles,
        public_people_snapshot=dict(dbpedia=dbpedia_manifest['sourceSnapshotSha256'] if dbpedia_manifest else None,
            bulkNames=h.replay.sha(args.bulk_dir/'bulk.json') if bulk_manifest else None,
            middleNames=role_manifest['sourceSnapshotSha256'] if role_manifest else None),
        ordinary_assets=getattr(args,'ordinary_assets',None) or args.assets)
        if getattr(args,'sensitive_dir',None) else ([],None,[]))
    sources = load_sources(args, [r['surface'] for r in discovered + leads + expansion + roles + dbpedia + bulk + pantheon + food + enrichment])
    wordnet_food_manifest=None
    if food_manifest:
        wordnet_food,wordnet_food_manifest=bulk_food.wordnet_records(args.lexical_source_dir/'wordnet.tar.gz',sources['pins']['wordnet.tar.gz']['sha256'])
        food+=wordnet_food
    if lead_manifest:
        h.require(lead_manifest['lexicalSources'] == sources['pins'], 'Gemini acquisition lexical sources changed')
        h.require(lead_manifest['plan']['taxonomySha256'] == h.replay.sha(args.taxonomy), 'Gemini acquisition taxonomy changed')
    world_index, world_manifest = world_sources.indices(args.source_dir, args.scopes) if config.get('worldSources') else ({}, None)
    targets = {}

    def add(surface, topic, kind, tier, providers, entity=None, form_kind='head'):
        # Casefold is a search aid, never the target or entity identity.
        key = identity([surface, kind, entity])
        item = targets.setdefault(key, dict(id=key, surface=surface, kind=kind, tier=tier,
            entity=entity, formKind=form_kind, topics=[], providers=[], proofs=[], sourceEntry=None))
        item['topics'] = sorted(set(item['topics']) | {topic})
        item['providers'] = sorted(set(item['providers']) | set(providers))
        if tier == 'core':
            item['tier'] = tier
        return item

    if config['basicLists']:
        for name, (_, _, _) in legacy.BASIC.items():
            with (args.lexical_source_dir / name).open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.reader(stream))
            for row in rows if 'supplementary' in name else rows[1:]:
                surface = row[0]
                # Spreadsheet boolean capitalization is not spelling evidence.
                if surface in {'TRUE', 'FALSE'} and surface.lower() in sources['words']:
                    surface = surface.lower()
                item = add(surface, 'daily.general', 'lexical', 'core', ['esdb', 'wordnet'])
                item.setdefault('selectors', []).append(dict(source=name, sha256=legacy.BASIC[name][1]))
    for scope in config['scopes']:
        for term in scope['terms']:
            add(term, scope['topic'], scope['kind'], scope['tier'], scope['sources'])
    for record in discovered + roles + dbpedia + bulk + pantheon + food + enrichment:
        h.require(set(record['topics']) <= topics.keys(), 'Unknown discovered topic')
        for topic in record['topics']:
            item = add(record['surface'], topic, record['kind'], 'extended',
                       ['esdb', 'wordnet'] if record['kind'] == 'lexical' else [],
                       entity='name-component:'+record['surface'] if all(t.startswith('names.') for t in record['topics']) else record['entity'])
        item['proofs'].extend(dict(p) for p in record['proofs'])
        if record.get('attestedSourceEntry'):
            item['attestedSourceEntry']=record['attestedSourceEntry'];item['formKind']=record['formKind']
    for record in expansion:
        h.require(set(record['topics']) <= topics.keys(), 'Unknown source-coverage topic')
        for topic in record['topics']:
            item = add(record['surface'], topic, record['kind'], 'extended', ['esdb','wordnet'],
                       entity='name-component:'+record['surface'] if all(t.startswith('names.') for t in record['topics']) else record['entity'])
        item['proofs'].extend(dict(p) for p in record['proofs'])
        if record.get('sourceScopeDeferred'):item['sourceScopeDeferred']=True
    for record in leads:
        h.require(set(record['topics']) <= topics.keys(), 'Unknown Gemini-proposed topic')
        for topic in record['topics']:
            item = add(record['surface'], topic, record['kind'], 'extended',
                       ['esdb', 'wordnet'] if record['kind'] == 'lexical' else [], entity=record['entity'])
        item['requireIndependentProof'] = True
        if record.get('deferredByNameReview'): item['deferredByNameReview'] = True
        item['proofs'].extend(dict(p) for p in record['proofs'])
    casks = json.loads((args.lexical_source_dir / 'cask.json').read_text())
    ranks = {r['cask']: int(r['number']) for r in json.loads((args.lexical_source_dir / 'cask-analytics.json').read_text())['items']}
    for record in sorted(casks, key=lambda r: (ranks.get(r['token'], 1000000), r['token'])):
        if record.get('disabled') or record.get('deprecated'):
            continue
        for index, label in enumerate(record['name']):
            selections=[]
            if ranks.get(record['token'],1000000)<=config['productRankLimit']:
                selections.append(('names.product','core' if index==0 else 'extended'))
            if getattr(args,'all_software',False):selections.append(('products.software','extended'))
            for topic,tier in selections:
                item = add(label, topic, 'product', tier, ['homebrew'],
                    entity='homebrew:' + record['token'], form_kind='head' if index == 0 else 'alias')
                item['proofs'].append(dict(source='homebrew', url='https://formulae.brew.sh/cask/' + record['token'],
                    sha256=sources['legacy']['files']['cask.json']['sha256'], record=record['token'], field='name', license='BSD-2-Clause'))

    for item in targets.values():
        surface, kind = item['surface'], item['kind']
        lower_scope = kind == 'lexical' and surface.islower()
        for provider in item['providers']:
            if provider == 'esdb':
                eligible = [r for r in sources['words'].get(surface, []) if
                    (r['pos_class'] in {'person', 'surname'} and r['pos'] == 'n0' if kind == 'person' else
                     r['pos_class'] in {'', 'upper', 'name', 'name?'})]
                if eligible:
                    row = next((r for r in eligible if r['word'] == r['lemma'] and roles_for(r['base_pos'], r['pos'])),
                        next((r for r in eligible if roles_for(r['base_pos'], r['pos'])), eligible[0]))
                    roles = roles_for(row['base_pos'], row['pos'])
                    role = next(iter(sorted(roles)), None)
                    if role:
                        item['sourceEntry'] = dict(lemma=row['lemma'], categories=sorted(categories_for(row, role, sources['paradigms'][row['lemma_id']])),
                            source_ref=f"esdb:{row['word_id']}:{row['lemma_id']}:{row['pos']}")
                        if row['word'] != row['lemma']:
                            item['formKind'] = 'inflection'
                    item['proofs'].append(dict(source='esdb', url=ESDB_URL, sha256=sources['pins']['esdb']['databaseSha256'],
                        wordId=row['word_id'], lemmaId=row['lemma_id'], pos=row['pos'], license='LicenseRef-ESDB'))
            elif provider == 'wordnet':
                records = [r for r in sources['wordnet'].get(lexical.key(surface), []) if r[0] == surface]
                if records:
                    _, role, offset = records[0]
                    item['sourceEntry'] = item['sourceEntry'] or dict(lemma=surface, categories=[role] + (['phrase'] if ' ' in surface else []),
                        source_ref='wordnet-3.0:' + offset)
                    item['proofs'].append(dict(source='wordnet', url='https://wordnet.princeton.edu/', sha256=sources['pins']['wordnet.tar.gz']['sha256'],
                        synset=offset, license='WordNet-3.0'))
            elif provider == 'mdn':
                # The index label is not automatically promoted to preferred case.
                labels = [(label, url) for label, url in sources['mdnLabels'].items()
                    if label == surface or lower_scope and lexical.key(label) == surface]
                for label, url in labels:
                    item['proofs'].append(dict(source='mdn', url=url, attestedLabel=label,
                        casePolicy='scope-declared-lowercase' if lower_scope else 'exact',
                        sha256=sources['legacy']['files']['mdn-glossary.html']['sha256'], license='CC-BY-SA-2.5-or-later'))
                for record, text in sources['pages']:
                    if attested(surface, text, lower_scope):
                        item['proofs'].append(dict(source='mdn-page', url=record['url'], sha256=record['sha256'], license=record['license'],
                            casePolicy='scope-declared-lowercase' if lower_scope else 'exact'))
            elif provider in DOCUMENTS and (surface in sources['languages'] if provider == 'linguist' else attested(surface, sources['texts'][provider], lower_scope)):
                record = sources['documents'][provider]
                item['proofs'].append(dict(source=provider, url=record['url'], sha256=record['sha256'], license=record['license'],
                    casePolicy='scope-declared-lowercase' if lower_scope and provider != 'linguist' else 'exact'))
        item['proofs'].extend(world_sources.matching(world_index, surface, kind, item['providers']))
        noun_head = next((p for p in item['proofs'] if p.get('source') == 'wiktionary' and p.get('headRole') == 'noun'), None)
        if noun_head and (not item['sourceEntry'] or item['sourceEntry']['lemma'] != surface):
            item['sourceEntry'] = dict(lemma=surface, categories=['noun'], source_ref='wiktionary:' + str(noun_head['revision']))
            item['formKind'] = 'head'
        if item.get('attestedSourceEntry'):item['sourceEntry']=item['attestedSourceEntry']
        item['proofs'] = canonical_proofs(item['proofs'])
    records = sorted(targets.values(), key=lambda r: (r['tier'] != 'core', r['surface'], r['kind'], r['id']))
    blocked=distribution_policy.keys()
    for record in records:
        if distribution_policy.excluded(record['surface'],(record['sourceEntry'] or {}).get('lemma',record['surface']),blocked):
            record['distributionRestricted']=True
    public = dict(profile=PROFILE, taxonomySha256=h.replay.sha(args.taxonomy), scopesSha256=h.replay.sha(args.scopes),
        documents=sources['documents'], lexicalSources=sources['pins'],
        mdnPages=[r for r, _ in sources['pages']],
        legacyManifest=sources['legacy'],
        legacyManifestSha256=h.replay.sha(args.lexical_source_dir / 'dictionary-sources.json'),
        topicClassification='Project-curated scope declarations; source attestation is spelling evidence, not sense disambiguation.')
    notices = [dict(name='CATALOG-' + r['notice'], path=str(args.source_dir.resolve() / r['notice']), sha256=r['noticeSha256'])
               for r in sources['documents'].values()]
    notice = args.source_dir.resolve() / 'CATALOG-SOURCE-ATTRIBUTION.txt'
    text = ['Dictionary topic catalog: source labels/terms selected by project-authored scopes.',
        'Changes: match exact declared spellings in pinned sources, normalize document whitespace, attach topical memberships; '
        'lowercase ordinary terms are explicitly declared by project scopes and may match heading case variants; '
        'names, languages and acronyms retain exact case. No suffix or plural derivation. '
        'No definitions, code examples or articles redistributed; no claim of disambiguated senses or preferred title case.']
    for name, r in sorted(sources['documents'].items()):
        text += [name + ': ' + r['attribution'], r['url'], r['license'] + ' — ' + r['noticeUrl']]
    text += ['MDN Web Docs contributors; exact term matches in referenced glossary pages. CC BY-SA 2.5 or later.',
        'https://developer.mozilla.org/en-US/docs/MDN/Writing_guidelines/Attrib_copyright_license']
    # Only fetch writes the raw collection; this deterministic derived notice is external.
    expected_notice = '\n'.join(text) + '\n'
    if notice.exists():
        h.require(notice.read_text() == expected_notice, 'Attribution changed; use a new source snapshot')
    else:
        notice.write_text(expected_notice, encoding='utf-8')
    notices.append(dict(name=notice.name, path=str(notice), sha256=h.replay.sha(notice)))
    if world_manifest:
        public['worldSources'] = world_manifest
        notices.extend(dict(name=name, path=str(args.source_dir.resolve() / name), sha256=record['sha256'])
            for name, record in world_manifest['files'].items() if name.startswith('WORLD-'))
    if discovery_manifest:
        public['discovery'] = discovery_manifest
        notices.extend(discovery_notices)
    if lead_manifest:
        public['geminiAcquisition'] = lead_manifest
        notices.extend(lead_notices)
    if expansion_manifest:
        public['sourceCoverage'] = coverage_sources.provenance(args.coverage_dir, expansion_manifest)
        notices.extend(expansion_notices)
    if role_manifest:public['nameRoles']=role_manifest
    if bulk_manifest:
        public['bulkNames']=bulk_manifest
        path=args.bulk_dir/'BULK-NAMES-SOURCES.txt'
        notices.append(dict(name=path.name,path=str(path.resolve()),sha256=h.replay.sha(path)))
    if dbpedia_manifest:
        dbpedia_sources.check_notices(args.dbpedia_dir)
        public['dbpedia']=dbpedia_manifest
        for path in sorted(args.dbpedia_dir.glob('DBPEDIA-*')):
            notices.append(dict(name=path.name,path=str(path.resolve()),sha256=h.replay.sha(path)))
    if food_manifest:
        public['food']=food_manifest
        public['wordnetFood']=wordnet_food_manifest
        notices.extend(food_notices)
    if enrichment_manifest:public['peopleEnrichment']=enrichment_manifest
    if sensitive_manifest:public['sensitive']=sensitive_manifest
    if pantheon_manifest:
        public['pantheon']=pantheon_manifest
        notices.extend(pantheon_notices)
    if distribution_policy.DEFAULT.exists():public['distributionPolicySha256']=h.replay.sha(distribution_policy.DEFAULT)
    if getattr(args,'all_software',False):public['allActiveSoftware']=dict(source='cask.json',sha256=sources['legacy']['files']['cask.json']['sha256'],
        scope='Every source-provided name of every active, non-deprecated cask; installation rank does not cap extended acquisition.')
    return records, topics, dict(catalogV2=public, references=dict(notices=notices))


def inventory(assets, cli, output):
    h.cli_run(cli, 'export-candidates', '--assets', assets, '--out', output)
    pairs = {(r['reading'], r['surface']) for r in h.json_lines(output)}
    forms = {}
    by_surface = defaultdict(list)
    with (assets / 'grammar/forms.tsv').open(encoding='utf-8') as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            row['memberships'] = set()
            forms[row['lexeme_id'], row['surface']] = row
            by_surface[row['surface']].append(row)
    with (assets / 'grammar/memberships.tsv').open(encoding='utf-8') as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            forms[row['lexeme_id'], row['surface']]['memberships'].add(row['category'])
    return pairs, by_surface


def audit(targets, topics, pairs, analyses, excluded):
    surfaces = {s for _, s in pairs}
    keys = {lexical.key(s) for s in surfaces}
    inventory_hash = hashlib.sha256(json.dumps(sorted(pairs)).encode()).hexdigest()
    results, operations = [], []
    for target in targets:
        word = target['surface']
        required = {topics[t]['category'] for t in target['topics']} | {'domain_' + topics[t]['domain'] for t in target['topics']}
        # A real dictionary candidate must exist. Input/ranking behavior belongs to the IME.
        registered = word in surfaces
        proofs = list(target['proofs'])
        preferred = {'person': {'name_person'}, 'product': {'name_product', 'name_work'}, 'organization': {'name_organization'},
                     'language': {'identifier_computer_language'}}.get(target['kind'], set())
        eligible = sorted(analyses.get(word, []), key=lambda f: (
            bool(preferred) and not bool(f['memberships'] & preferred),
            'domain_technology' not in f['memberships'] if any(t.startswith('technology.') for t in target['topics']) else False,
            f['lemma'] != word, f['lexeme_id']))
        if not proofs and registered and not target.get('requireIndependentProof'):
            # Existing reviewed analyses can support topic-only enrichment, never a new spelling.
            if target['kind'] == 'person':
                eligible = [f for f in eligible if 'name_person' in f['memberships']]
            elif target['kind'] == 'language':
                eligible = [f for f in eligible if 'identifier_computer_language' in f['memberships']]
            if eligible:
                proof = dict(source='reviewed_existing', url=eligible[0]['evidence'], inventorySha256=inventory_hash,
                    lexemeId=eligible[0]['lexeme_id'], license='retained-parent-notices')
                proofs.append(dict(proof, id=identity(proof)))
        members = set().union(*(f['memberships'] for f in analyses.get(word, [])))
        missing = sorted(required - members)
        result = dict(id=target['id'], registered=registered, missingCategories=missing, status='present')
        category = 'domain_' + topics[target['topics'][0]]['domain']
        if target.get('distributionRestricted'):
            result['status']='restricted_distribution'
        elif target.get('sourceScopeDeferred'):
            result['status'] = 'blocked_source_scope'
        elif target.get('deferredByNameReview'):
            result['status'] = 'blocked_named_review'
        elif not proofs:
            result['status'] = 'blocked_evidence'
        elif not registered and (not lexical.valid_surface(word) or
              target['sourceEntry'] and not lexical.valid_surface(target['sourceEntry']['lemma'])):
            result['status'] = 'blocked_format'
        elif not registered and (lexical.key(word) in excluded or word in surfaces):
            result['status'] = 'blocked_base_or_reading'
        elif not registered:
            result['status'] = ('new_form' if target['formKind'] == 'inflection' else
                'case_variant' if lexical.key(word) in keys else 'new_spelling')
            source = target['sourceEntry'] or dict(lemma=word, categories=[], source_ref='catalog-v2:' + target['id'])
            categories = required | set(source['categories'])
            if target['kind'] in {'person', 'product'}:
                categories |= {'noun', 'noun_proper', 'name_' + target['kind']}
            elif target['kind'] == 'organization':
                categories |= {'noun', 'noun_proper', 'name_organization'}
            elif target['kind'] in {'brand', 'service'}:
                categories |= {'noun', 'noun_proper'}
            entry = dict(zip(lexical.FIELDS, ['catalog-' + target['id'], source['lemma'], word,
                ','.join(sorted(categories)), category.removeprefix('domain_'), proofs[0]['url'], source['source_ref']]))
            # Unspecified lexical roles cannot support a different lemma.
            if source['lemma'] != word and not set(source['categories']) & {'noun', 'verb', 'adjective', 'adverb', 'pronoun', 'determiner', 'conjunction', 'preposition', 'interjection', 'contraction', 'abbreviation'}:
                result['status'] = 'blocked_lemma_role'
            else:
                operations.append(dict(id=target['id'], surface=word, entries=[entry], metadata=[], proofs=proofs,
                    change=result['status'], topics=target['topics']))
        elif missing:
            if not eligible:
                result['status'] = 'blocked_metadata_binding'
            else:
                result['status'] = 'metadata_only'
                form = eligible[0]
                entry = dict(zip(lexical.FIELDS, [form['lexeme_id'], form['lemma'], word,
                    ','.join(sorted(set(missing) | {category})), category.removeprefix('domain_'),
                    proofs[0]['url'], 'catalog-v2:' + target['id']]))
                operations.append(dict(id=target['id'], surface=word, entries=[], metadata=[entry], proofs=proofs,
                    change='metadata_only', topics=target['topics']))
        results.append(result)
    return results, operations


def excluded_inputs(directory):
    with (directory / 'base-inputs/decisions.tsv').open(encoding='utf-8') as stream:
        return {lexical.key(r['surface']) for r in csv.DictReader(stream, delimiter='\t') if r['decision'] == 'exclude'}


def prepare(args):
    directory = h.external(args.work_dir)
    h.require(not getattr(args, 'gemini_named_review_dir', None) or getattr(args, 'gemini_dir', None),
              'A named review requires its Gemini acquisition directory')
    if getattr(args, 'gemini_dir', None):
        h.require(gemini_acquisition.verify(args.gemini_dir)['plan']['assets'] == h.asset_hashes(args.assets.resolve()),
                  'Gemini acquisition baseline differs from this catalog run')
    with h.lock(directory):
        h.require(set(p.name for p in directory.iterdir()) <= {'.lock'}, 'Use a new work directory')
        targets, topics, source_manifest = compile_targets(args)
        hashes = h.verify_assets(args.assets.resolve(), args.supplement.resolve())
        h.replay.unpack(h.replay.DEFAULT_MANIFEST, directory / 'base-inputs', h.replay.DEFAULT_SOURCE)
        pairs, analyses = inventory(args.assets.resolve(), args.cli.resolve(), directory / 'baseline.jsonl')
        results, operations = audit(targets, topics, pairs, analyses, excluded_inputs(directory))
        h.write_lines(directory / 'targets.jsonl', targets)
        h.write_lines(directory / 'before.jsonl', results)
        h.write_lines(directory / 'candidates.jsonl', operations)
        with sqlite3.connect(directory / 'state.sqlite3') as connection:
            connection.executescript('''create table candidates(id text primary key,position integer,payload text,proposal text,decision text,result text);
                create table attempts(id integer primary key,started text,model text,ids text,status text,request_sha256 text,response_sha256 text,usage text);''')
            connection.executemany('insert into candidates values(?,?,?,null,null,null)',
                [(r['id'], i, json.dumps(r, sort_keys=True)) for i, r in enumerate(operations)])
        config = dict(schemaVersion=1, sourceProfile=PROFILE, sources=source_manifest, assets=str(args.assets.resolve()),
            assetHashes=hashes, supplement=str(args.supplement.resolve()), supplementManifestSha256=h.replay.sha(args.supplement / 'manifest.json'),
            baselineSha256=h.replay.sha(directory / 'baseline.jsonl'), candidatesSha256=h.replay.sha(directory / 'candidates.jsonl'),
            targetsSha256=h.replay.sha(directory / 'targets.jsonl'), selectedCandidates=len(operations), availableCandidates=len(operations),
            topics=topics, sourcePaths={k: str(getattr(args, k).resolve()) for k in ['source_dir', 'lexical_source_dir', 'esdb_dir', 'taxonomy', 'scopes']},
            additionalCategories=[dict(category=r['category'], definition=r['definition'], examples=r['examples']) for r in topics.values()],
            codeHashes={name: h.replay.sha(Path(__file__).with_name(name)) for name in ['catalog_harness.py', 'vocabulary_harness.py', 'dictionary_sources.py', 'world_sources.py', 'distribution_policy.py', 'vocabulary_sources.py']},
            baseRevision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=h.REPO, text=True).strip())
        config['catalogOptions']=dict(all_software=getattr(args,'all_software',False))
        if getattr(args,'sensitive_dir',None):config['sourcePaths']['ordinary_assets']=str((getattr(args,'ordinary_assets',None) or args.assets).resolve())
        if getattr(args, 'discovery_dir', None):
            config['sourcePaths'].update({k: str(getattr(args, k).resolve()) for k in ['discovery_dir', 'discovery_policy']})
            config['codeHashes']['discovery_sources.py'] = h.replay.sha(Path(__file__).with_name('discovery_sources.py'))
        if getattr(args, 'gemini_dir', None):
            config['sourcePaths']['gemini_dir'] = str(args.gemini_dir.resolve())
            config['codeHashes']['gemini_acquisition.py'] = h.replay.sha(Path(__file__).with_name('gemini_acquisition.py'))
            if getattr(args, 'gemini_named_review_dir', None):
                config['sourcePaths']['gemini_named_review_dir'] = str(args.gemini_named_review_dir.resolve())
        if getattr(args, 'coverage_dir', None):
            config['sourcePaths'].update({k:str(getattr(args,k).resolve()) for k in ['coverage_dir','coverage_policy']})
            config['codeHashes']['coverage_sources.py'] = h.replay.sha(Path(__file__).with_name('coverage_sources.py'))
        if getattr(args,'role_dir',None):
            config['sourcePaths']['role_dir']=str(args.role_dir.resolve())
            config['codeHashes']['role_sources.py']=h.replay.sha(Path(__file__).with_name('role_sources.py'))
        if getattr(args,'dbpedia_dir',None):
            config['sourcePaths'].update({k:str(getattr(args,k).resolve()) for k in ['dbpedia_dir','dbpedia_policy']})
            config['codeHashes']['dbpedia_sources.py']=h.replay.sha(Path(__file__).with_name('dbpedia_sources.py'))
        for provider,path_name in [('bulk_food','food_dir'),('people_enrichment','enrichment_dir'),('sensitive_sources','sensitive_dir')]:
            if getattr(args,path_name,None):
                config['sourcePaths'][path_name]=str(getattr(args,path_name).resolve())
                config['codeHashes'][provider+'.py']=h.replay.sha(Path(__file__).with_name(provider+'.py'))
        if getattr(args,'pantheon_dir',None):
            config['sourcePaths']['pantheon_dir']=str(args.pantheon_dir.resolve())
            config['codeHashes']['pantheon_sources.py']=h.replay.sha(Path(__file__).with_name('pantheon_sources.py'))
        if getattr(args,'bulk_dir',None):
            config['sourcePaths']['bulk_dir']=str(args.bulk_dir.resolve())
            config['codeHashes']['bulk_names.py']=h.replay.sha(Path(__file__).with_name('bulk_names.py'))
        h.dump(directory / 'run.json', config)
        return dict(targets=len(targets), plannedOperations=len(operations), changes=dict(Counter(r['status'] for r in results)))


def checked_state(directory):
    config, connection = h.state(directory)
    h.require(config.get('sourceProfile') == PROFILE and h.replay.sha(directory / 'targets.jsonl') == config['targetsSha256'], 'Changed target snapshot')
    return config, connection


def adopt(args):
    directory = h.external(args.work_dir)
    with h.lock(directory):
        config, connection = checked_state(directory)
        try:
            h.require(h.asset_hashes(Path(config['assets'])) == config['assetHashes'], 'Baseline assets changed')
            options = argparse.Namespace(**{k: Path(v) for k, v in config['sourcePaths'].items()},**config.get('catalogOptions',{}))
            targets, topics, sources = compile_targets(options)
            h.require(targets == h.json_lines(directory / 'targets.jsonl') and sources == config['sources'], 'Source or target declarations changed')
            # Recompute operations as well; editing SQLite cannot authorize new metadata.
            import tempfile
            with tempfile.TemporaryDirectory(dir=directory) as temp:
                pairs, analyses = inventory(Path(config['assets']), args.cli.resolve(), Path(temp) / 'inventory.jsonl')
            _, operations = audit(targets, topics, pairs, analyses, excluded_inputs(directory))
            h.require(operations == h.json_lines(directory / 'candidates.jsonl'), 'Acquisition operations changed')
            rows = connection.execute('select * from candidates where decision is null order by position').fetchall()
            accepted = []
            for start in range(0, len(rows), args.batch_size):
                batch = rows[start:start + args.batch_size]
                items = []
                for row in batch:
                    operation = json.loads(row['payload'])
                    proposal = json.loads(row['proposal']) if row['proposal'] else None
                    item = dict(id=row['id'], decision='include' if not proposal or proposal['decision'] == 'include' else 'defer',
                        reason=PROFILE + ': re-extracted frozen evidence and dictionary binding; source automation, not human review.',
                        proofIds=[p['id'] for p in operation['proofs']])
                    h.validate_decisions([item], [operation])
                    items.append(item)
                path = directory / ('catalog-decisions-' + str(batch[0]['position']).zfill(6) + '.jsonl')
                h.require(not path.exists() or h.json_lines(path) == items, 'Changed adoption journal')
                if not path.exists():
                    h.write_lines(path, items)
                with connection:
                    for item in items:
                        connection.execute('update candidates set decision=?,result=? where id=?',
                            (item['decision'], json.dumps(item, sort_keys=True), item['id']))
                accepted.extend(items)
            return dict(decisions=dict(Counter(r['decision'] for r in accepted)), apiCalls=0)
        finally:
            connection.close()


def report(args):
    directory = h.external(args.work_dir)
    with h.lock(directory):
        config, connection = checked_state(directory)
        connection.close()
        targets = h.json_lines(directory / 'targets.jsonl')
        assets = args.assets.resolve() if args.assets else Path(config['assets'])
        import tempfile
        with tempfile.TemporaryDirectory(dir=directory) as temp:
            pairs, analyses = inventory(assets, args.cli.resolve(), Path(temp) / 'inventory.jsonl')
        after, _ = audit(targets, config['topics'], pairs, analyses, excluded_inputs(directory))
        before = {r['id']: r for r in h.json_lines(directory / 'before.jsonl')}
        indexed = {r['id']: r for r in targets}
        fields = ['targets', 'registeredBefore', 'registeredAfter', 'topicCompleteBefore', 'topicCompleteAfter',
                  'blockedEvidence', 'blockedFormat', 'unresolved']
        counts = {name: Counter({field: 0 for field in fields}) for name in
                  ['all', 'tier:core', 'tier:extended', *config['topics']]}
        for row in after:
            target = indexed[row['id']]
            for topic in ['all', 'tier:' + target['tier'], *target['topics']]:
                c = counts[topic]
                c['targets'] += 1
                c['registeredBefore'] += before[row['id']]['registered']
                c['registeredAfter'] += row['registered']
                c['topicCompleteBefore'] += before[row['id']]['status'] == 'present'
                c['topicCompleteAfter'] += row['status'] == 'present'
                c['blockedEvidence'] += row['status'] == 'blocked_evidence'
                c['blockedFormat'] += row['status'] == 'blocked_format'
                c['unresolved'] += row['status'] != 'present'
        groups = {name: dict(values, spellingCoverage=values['registeredAfter'] / values['targets'] if values['targets'] else None,
            topicCoverage=values['topicCompleteAfter'] / values['targets'] if values['targets'] else None)
            for name, values in sorted(counts.items())}
        result = dict(schemaVersion=2, targetsSha256=config['targetsSha256'], assetHashes=h.asset_hashes(assets),
            taxonomySha256=config['sources']['catalogV2']['taxonomySha256'],
            catalogCodeHashesAtPrepare=config.get('codeHashes', {}),
            reportCodeHashes={name: h.replay.sha(Path(__file__).with_name(name)) for name in
                ['catalog_harness.py', 'vocabulary_harness.py', 'replay_source.py']},
            scope='Fixed core regression requirements plus frozen extended discovery; not all English. Topic counts overlap.',
            groups=groups,
            plannedChanges=dict(Counter(r['status'] for r in before.values())),
            newRegisteredSpellings=len({indexed[r['id']]['surface'] for r in after if r['registered'] and not before[r['id']]['registered']}),
            unresolved=[indexed[r['id']] | dict(audit=r) for r in after if r['status'] != 'present'])
        output = h.external(args.out)
        h.require(not output.is_relative_to(assets), 'Report output must be outside dictionary assets')
        h.require(not output.exists(), 'Report already exists; preserve previous report')
        output.mkdir(parents=True)
        h.dump(output / 'report.json', result)
        table(output / 'coverage.tsv', ['topic', *next(iter(result['groups'].values())).keys()],
            [dict(topic=k, **v) for k, v in result['groups'].items()])
        h.write_lines(output / 'unresolved.jsonl', result.pop('unresolved'))
        return dict(report=str(output / 'report.json'), totals=result['groups']['all'], newRegisteredSpellings=result['newRegisteredSpellings'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    fetcher = commands.add_parser('fetch')
    fetcher.add_argument('--source-dir', type=Path, required=True)
    world = commands.add_parser('fetch-world')
    world.add_argument('--source-dir', type=Path, required=True)
    world.add_argument('--scopes', type=Path, default=CATALOG / 'core-targets.json')
    discover = commands.add_parser('discover')
    discover.add_argument('--source-dir', type=Path, required=True)
    discover.add_argument('--policy', type=Path, default=CATALOG / 'discovery-policy.json')
    discover.add_argument('--max-requests', type=int, default=120)
    discover.add_argument('--resume-from', type=Path)
    discover.add_argument('--max-new-pages-per-selector', type=int, default=0)
    resolver = commands.add_parser('fetch-references')
    resolver.add_argument('--source-dir', type=Path, required=True)
    resolver.add_argument('--work-dir', type=Path, required=True)
    default_cli = h.REPO / 'english-ime/build/install/english-ime/bin/english-ime'
    for name in ['prepare', 'adopt', 'build', 'report']:
        p = commands.add_parser(name)
        p.add_argument('--work-dir', type=Path, required=True)
        p.add_argument('--cli', type=Path, default=default_cli)
        if name == 'adopt':
            p.add_argument('--batch-size', type=int, choices=range(1, 10001), default=1000)
        if name == 'prepare':
            p.add_argument('--all-software',action='store_true')
            p.add_argument('--pantheon-dir',type=Path)
            p.add_argument('--food-dir',type=Path)
            p.add_argument('--enrichment-dir',type=Path)
            p.add_argument('--sensitive-dir',type=Path)
            p.add_argument('--bulk-dir',type=Path)
            p.add_argument('--dbpedia-dir',type=Path)
            p.add_argument('--dbpedia-policy',type=Path,default=CATALOG/'dbpedia-policy.json')
            p.add_argument('--role-dir',type=Path)
            p.add_argument('--gemini-dir', type=Path)
            p.add_argument('--gemini-named-review-dir', type=Path)
            p.add_argument('--coverage-dir', type=Path)
            p.add_argument('--coverage-policy', type=Path, default=CATALOG/'coverage-policy.json')
            p.add_argument('--discovery-dir', type=Path)
            p.add_argument('--discovery-policy', type=Path, default=CATALOG / 'discovery-policy.json')
            for option in ['source-dir', 'lexical-source-dir', 'esdb-dir', 'assets']:
                p.add_argument('--' + option, type=Path, required=True)
            p.add_argument('--supplement', type=Path, default=lexical.SUPPLEMENT)
            p.add_argument('--taxonomy', type=Path, default=CATALOG / 'taxonomy.json')
            p.add_argument('--scopes', type=Path, default=CATALOG / 'core-targets.json')
        if name in {'build', 'report'}:
            p.add_argument('--out', type=Path, required=True)
        if name == 'report':
            p.add_argument('--assets', type=Path)
    args = parser.parse_args()
    if args.command == 'discover':
        result = discovery_sources.fetch(args.source_dir, args.policy, args.max_requests, args.resume_from,
                                         args.max_new_pages_per_selector)
        result = dict(complete=result['complete'], counts=result['counts'], modelApiCalls=0)
    elif args.command == 'fetch-world':
        result = world_sources.fetch(args.source_dir, args.scopes)
        result = dict(files=len(result['files']), batches=len(result['batches']), modelApiCalls=0)
    else:
        result = h.build(args) if args.command == 'build' else globals()[args.command.replace('-', '_')](args)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
