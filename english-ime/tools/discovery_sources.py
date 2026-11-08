"""Enumerate source categories independently of the fixed regression targets."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
from urllib.parse import urlencode, unquote, urlparse
import urllib.error

import dictionary_sources as download
import vocabulary_harness as h


def query(selector, offset, size):
    h.require(len(selector['classes']) == 1, 'Use a separate paginated selector for each source class')
    cls = 'wd:' + selector['classes'][0]
    typed = (f'?item wdt:P31 wd:Q5; wdt:P106 {cls}.' if selector['kind'] == 'person' else f'?item wdt:P31 {cls}.')
    return f'''PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?item ?links ?article ?label WHERE {{
 {{ SELECT DISTINCT ?item ?links ?article WHERE {{ {typed}
 ?item wikibase:sitelinks ?links. FILTER(?links >= {selector['minimumSitelinks']})
 ?article schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>.
 }} ORDER BY DESC(?links) ?item LIMIT {size} OFFSET {offset} }}
 OPTIONAL {{ ?item rdfs:label ?en. FILTER(LANG(?en)="en") }}
 OPTIONAL {{ ?item rdfs:label ?mul. FILTER(LANG(?mul)="mul") }}
 BIND(COALESCE(?en,?mul) AS ?label)
}} ORDER BY DESC(?links) ?item'''


def request_url(selector, offset, size, continuation=None):
    if selector['provider'] == 'wikidata':
        return 'https://query.wikidata.org/sparql?' + urlencode(dict(query=query(selector, offset, size), format='json'))
    args = dict(action='query', list='categorymembers', cmtitle=selector['category'], cmnamespace=0,
                cmlimit=500, cmprop='ids|title', format='json')
    if continuation:
        args.update(continuation)
    return 'https://en.wiktionary.org/w/api.php?' + urlencode(args)


def policy(path):
    data = h.replay.read_json(path)
    h.require(data['schemaVersion'] == 1 and len({r['id'] for r in data['selectors']}) == len(data['selectors']), 'Invalid discovery policy')
    h.require(isinstance(data['pageSize'], int) and 1 <= data['pageSize'] <= 500, 'Invalid discovery page size')
    for s in data['selectors']:
        h.require(s['provider'] in {'wikidata', 'wiktionary'} and s['kind'] in
                  {'lexical', 'person', 'product', 'brand', 'organization', 'service'}, 'Invalid discovery selector')
        if s['provider'] == 'wikidata':
            h.require(s['minimumSitelinks'] >= 10 and len(s['classes']) == 1 and
                      all(re.fullmatch(r'Q[1-9][0-9]*', q) for q in s['classes']), 'Invalid Wikidata filter')
        else:
            h.require(s['kind'] == 'lexical' and s['category'].startswith('Category:en:'), 'Not an English category')
    return data


def fetch(directory, policy_path, max_requests=120, resume_from=None, max_new_pages_per_selector=0):
    h.require(1 <= max_requests <= 10000, 'Invalid source request budget')
    h.require(max_new_pages_per_selector >= 0, 'Invalid per-selector request budget')
    directory = h.external(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rule = policy(policy_path)
    manifest_path = directory / 'discovery.json'
    if manifest_path.exists():
        return verify(directory, policy_path)
    if resume_from:
        previous = h.external(resume_from)
        old = verify(previous, policy_path)
        for name in old['files']:
            if name.startswith('page-') and not (directory / name).exists():
                shutil.copyfile(previous / name, directory / name)
    selectors = list(rule['selectors'])
    if resume_from:
        # Give untouched fields their first page before extending already large fields.
        selectors.sort(key=lambda s: (old['counts'][s['id']] > 0, old['states'][s['id']]['complete'], s['id']))
    files, pages, counts, states = {}, [], {}, {}
    requests = 0
    paused = set()
    for selector in selectors:
        offset, continuation, total = 0, None, 0
        fresh_pages = 0
        while True:
            url = request_url(selector, offset, rule['pageSize'], continuation)
            name = 'page-' + hashlib.sha256(url.encode()).hexdigest() + '.json'
            path = directory / name
            fresh = not path.exists()
            try:
                if fresh:
                    h.require(selector['provider'] not in paused, 'Provider rate-limited; resume in a later snapshot')
                    h.require(requests < max_requests, 'Source request budget reached; resume in a new snapshot')
                    h.require(not max_new_pages_per_selector or fresh_pages < max_new_pages_per_selector,
                              'Per-selector source request budget reached; resume in a new snapshot')
                    requests += 1
                    fresh_pages += 1
                    download.download(url, path, 16 * 1024 * 1024)
                    time.sleep(2)
                payload = h.replay.read_json(path)
                if 'error' in payload:
                    raise ValueError('Source error: ' + str(payload['error']))
                rows = (payload['results']['bindings'] if selector['provider'] == 'wikidata'
                        else payload['query']['categorymembers'])
            except (OSError, ValueError, KeyError) as error:
                if isinstance(error, urllib.error.HTTPError) and error.code == 429:
                    paused.add(selector['provider'])
                if path.exists():
                    path.unlink()  # A failed API reply is not source evidence.
                states[selector['id']] = dict(complete=False, nextOffset=offset,
                    continuation=continuation, pendingReason=str(error))
                print(json.dumps(dict(selector=selector['id'], rows=total, pending=str(error))), flush=True)
                break
            files[name] = dict(url=url, sha256=h.replay.sha(path))
            pages.append(dict(selector=selector['id'], file=name, offset=offset,
                              continuation=continuation, rows=len(rows)))
            total += len(rows)
            print(json.dumps(dict(selector=selector['id'], rows=total, cached=not fresh)), flush=True)
            if selector['provider'] == 'wikidata':
                if len(rows) < rule['pageSize']:
                    states[selector['id']] = dict(complete=True)
                    break
                offset += rule['pageSize']
            else:
                continuation = payload.get('continue')
                if not continuation:
                    states[selector['id']] = dict(complete=True)
                    break
                offset += len(rows)
        counts[selector['id']] = total
    notice = directory / 'DISCOVERY-SOURCES.txt'
    notice.write_text('Category-based English vocabulary discovery.\n'
        'Wikidata contributors: typed query results, labels and English sitelinks, CC0 1.0.\n'
        'https://www.wikidata.org/wiki/Wikidata:Licensing\n'
        'Wiktionary contributors: English topical category members, CC BY-SA 4.0.\n'
        'https://en.wiktionary.org/wiki/Wiktionary:Copyrights\n'
        'Changes: select direct source category/class members; merge exact spellings and entity IDs; '
        'attach source-backed topical memberships. No definitions, articles, generated morphology or aliases.\n'
        'Sitelinks are a cross-language encyclopedia-breadth proxy, not measured IME frequency. '
        'All discovered targets are extended-tier; fixed core regression targets stay independent.\n', encoding='utf-8')
    files[notice.name] = dict(sha256=h.replay.sha(notice))
    manifest = dict(schemaVersion=1, policy=rule, policySha256=h.replay.sha(policy_path), files=files, pages=pages,
        counts=counts, states=states, sealed=True, complete=all(s['complete'] for s in states.values()),
        sourceRequests=requests, capturedAt=h.dt.datetime.now(h.dt.timezone.utc).isoformat())
    h.dump(manifest_path, manifest)
    return verify(directory, policy_path)


def verify(directory, policy_path):
    manifest = h.replay.read_json(directory / 'discovery.json')
    rule = policy(policy_path)
    h.require(manifest['schemaVersion'] == 1 and manifest['sealed'] is True and manifest['policy'] == rule
              and manifest['policySha256'] == h.replay.sha(policy_path), 'Changed/incomplete discovery snapshot')
    expected = {'DISCOVERY-SOURCES.txt'}
    indexed = {s['id']: s for s in rule['selectors']}
    h.require(set(manifest['counts']) == set(indexed), 'Incomplete discovery selector set')
    h.require(set(manifest['states']) == set(indexed) and manifest['complete'] ==
              all(s['complete'] for s in manifest['states'].values()), 'Invalid discovery completion status')
    for identifier, selector in indexed.items():
        selected = [p for p in manifest['pages'] if p['selector'] == identifier]
        state = manifest['states'][identifier]
        h.require((selected and selected[0]['offset'] == 0) or not selected and not state['complete'], 'Missing first discovery page')
        offset, continuation = 0, None
        for i, page in enumerate(selected):
            h.require(page['offset'] == offset and page['continuation'] == continuation, 'Broken discovery continuation')
            payload = h.replay.read_json(directory / page['file'])
            rows = payload['results']['bindings'] if selector['provider'] == 'wikidata' else payload['query']['categorymembers']
            h.require(len(rows) == page['rows'], 'Changed discovery count')
            if selector['provider'] == 'wikidata':
                more = len(rows) == rule['pageSize']
                offset += rule['pageSize'] if more else len(rows)
            else:
                continuation = payload.get('continue')
                more = bool(continuation)
                offset += len(rows)
            h.require(more == (i < len(selected) - 1 or not state['complete']), 'Discovery stopped before source exhaustion')
        h.require(sum(p['rows'] for p in selected) == manifest['counts'][identifier], 'Discovery total differs')
        if not state['complete']:
            h.require(state['nextOffset'] == offset and state['continuation'] == continuation and
                      state['pendingReason'], 'Invalid discovery checkpoint')
    for page in manifest['pages']:
        url = request_url(indexed[page['selector']], page['offset'], rule['pageSize'], page['continuation'])
        name = 'page-' + hashlib.sha256(url.encode()).hexdigest() + '.json'
        h.require(page['file'] == name and manifest['files'][name]['url'] == url, 'Changed discovery query')
        expected.add(name)
    h.require(set(manifest['files']) == expected, 'Missing discovery payloads')
    for name, record in manifest['files'].items():
        path = directory / name
        h.require(path.is_file() and not path.is_symlink() and Path(name).name == name
                  and h.replay.sha(path) == record['sha256'], 'Changed discovery payload: ' + name)
    return manifest


def collect(directory, policy_path):
    directory = h.external(directory)
    manifest = verify(directory, policy_path)
    selectors = {s['id']: s for s in manifest['policy']['selectors']}
    targets = {}
    for page in manifest['pages']:
        selector = selectors[page['selector']]
        payload = h.replay.read_json(directory / page['file'])
        rows = payload['results']['bindings'] if selector['provider'] == 'wikidata' else payload['query']['categorymembers']
        h.require(len(rows) == page['rows'], 'Changed discovery row count')
        for row in rows:
            if selector['provider'] == 'wikidata':
                qid = row['item']['value'].rsplit('/', 1)[-1]
                article = row['article']['value']
                h.require(re.fullmatch(r'Q[1-9][0-9]*', qid) and article.startswith('https://en.wikipedia.org/wiki/')
                          and int(row['links']['value']) >= selector['minimumSitelinks'], 'Invalid discovered entity')
                title = unquote(urlparse(article).path.rsplit('/', 1)[-1]).replace('_', ' ')
                prefer_title = selector['kind'] == 'person' and not any(c in title for c in '():')
                surface = title if prefer_title else row.get('label', {}).get('value') or title
                entity = 'wikidata:' + qid
                evidence = 'https://www.wikidata.org/wiki/' + qid
                license_id = 'CC0-1.0'
                extra = dict(entity=qid, sitelinks=int(row['links']['value']), englishArticle=article,
                             nameField='englishArticleTitle' if prefer_title or not row.get('label') else 'label')
            else:
                h.require(row['ns'] == 0 and isinstance(row['pageid'], int), 'Not a dictionary headword')
                surface, entity = row['title'], 'wiktionary:' + str(row['pageid'])
                evidence = 'https://en.wiktionary.org/w/index.php?' + urlencode(dict(curid=row['pageid']))
                license_id = 'CC-BY-SA-4.0'
                extra = dict(pageId=row['pageid'], englishCategory=selector['category'])
            key = surface, selector['kind'], entity
            item = targets.setdefault(key, dict(surface=surface, kind=selector['kind'], entity=entity, topics=[], proofs=[]))
            item['topics'] = sorted(set(item['topics']) | {selector['topic']})
            proof = dict(source='category_discovery', provider=selector['provider'], url=evidence, license=license_id,
                         sha256=manifest['files'][page['file']]['sha256'], selector=selector['id'], **extra)
            if proof not in item['proofs']:
                item['proofs'].append(proof)
    notices = [dict(name='DISCOVERY-SOURCES.txt', path=str(directory / 'DISCOVERY-SOURCES.txt'),
                    sha256=manifest['files']['DISCOVERY-SOURCES.txt']['sha256'])]
    return sorted(targets.values(), key=lambda r: (r['surface'], r['kind'], r['entity'] or '')), manifest, notices
