"""Resumable breadth-first traversal of declared English dictionary source trees.

Request budgets bound work, never vocabulary completeness. No model invents words.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
from urllib.parse import urlencode, urlparse, parse_qs
import urllib.error

import dictionary_sources as download
import vocabulary_harness as h

POLICY = h.REPO / 'english-ime/data/catalog/coverage-policy.json'


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]


def policy(path):
    rule = h.replay.read_json(path)
    h.require(rule['schemaVersion'] == 1 and rule['provider'] == 'wiktionary' and rule['language'] == 'en' and
              rule['pageSize'] == 500 and rule['roots'], 'Invalid source-coverage policy')
    h.require(len({(r['topic'], r['category']) for r in rule['roots']}) == len(rule['roots']) and
              all(english_category(r['category'],rule) for r in rule['roots']), 'Invalid/duplicate source roots')
    h.require(set(rule.get('categoryPrefixes',['Category:en:'])) <= {'Category:en:','Category:English '},
              'Unsupported English category prefix')
    for pattern in rule['excludeCategoryPatterns']: re.compile(pattern)
    return rule


def english_category(category, rule):
    return any(category.startswith(prefix) for prefix in rule.get('categoryPrefixes',['Category:en:']))


def request_url(category, phase, continuation):
    args = dict(action='query', list='categorymembers', cmtitle=category,
        cmnamespace=14 if phase == 'children' else 0, cmtype='subcat' if phase == 'children' else 'page',
        cmlimit=500, cmprop='ids|title|type', prop='categoryinfo', titles=category, format='json')
    if continuation: args.update(continuation)
    return 'https://en.wiktionary.org/w/api.php?' + urlencode(sorted(args.items()))


def source_rows(payload, phase):
    h.require('error' not in payload and isinstance(payload.get('query', {}).get('categorymembers'), list), 'Invalid source reply')
    rows = payload['query']['categorymembers']
    namespace = 14 if phase == 'children' else 0
    h.require(len(rows)<=500 and all(r.get('ns') == namespace and isinstance(r.get('pageid'), int) and
              r['pageid']>0 and isinstance(r.get('title'),str) and r['title'] for r in rows), 'Invalid source rows/namespace')
    continuation=payload.get('continue')
    h.require(not continuation or isinstance(continuation,dict) and set(continuation)=={'continue','cmcontinue'} and
              all(isinstance(v,str) and v for v in continuation.values()),'Invalid source pagination')
    return rows


def category_missing(payload, node):
    info_pages=payload['query'].get('pages')
    # MediaWiki's generic continuation marks categoryinfo exhausted after page 1.
    # Subsequent categorymembers pages omit it; the first page still establishes identity.
    if info_pages is None:
        h.require(node['continuation'] is not None and node['pages']>0,
                  'Missing first-page source category identity')
        return node['missing']
    info=next(iter(info_pages.values()),{})
    h.require(len(info_pages)==1 and info.get('ns')==14 and info.get('title')==node['category'],
              'Mismatching source category identity')
    return 'missing' in info


def replay(rule, pages, directory):
    """Reconstruct the complete queue from immutable pages, not mutable state."""
    nodes, excluded, cursors = {}, [], set()
    def add(topic, category, path):
        key = identity([topic, category])
        if key not in nodes:
            nodes[key] = dict(id=key, topic=topic, category=category, path=path, depth=len(path)-1,
                phase='children', continuation=None, pages=0, termRows=0, missing=False)
        return key
    for root in rule['roots']: add(root['topic'], root['category'], [root['category']])
    for page in pages:
        node = nodes[page['node']]
        cursor=(page['node'],page['phase'],json.dumps(page['continuation'],sort_keys=True))
        h.require(cursor not in cursors,'Repeated source pagination cursor')
        cursors.add(cursor)
        h.require(node['phase'] == page['phase'] and node['continuation'] == page['continuation'], 'Broken source-tree checkpoint')
        payload = h.replay.read_json(directory / page['file'])
        rows = source_rows(payload, page['phase'])
        h.require(len(rows) == page['rows'], 'Changed source-page count')
        h.require(not payload.get('continue') or payload['continue']!=page['continuation'],'Stalled source pagination')
        node['missing'] = category_missing(payload,node)
        node['pages'] += 1
        if page['phase'] == 'children':
            for row in rows:
                category = row['title']
                if not english_category(category,rule):
                    excluded.append(dict(topic=node['topic'], category=category, reason='not-English-category'))
                elif any(re.search(p, category) for p in rule['excludeCategoryPatterns']):
                    excluded.append(dict(topic=node['topic'], category=category, reason='declared-scope-exclusion'))
                else: add(node['topic'], category, node['path'] + [category])
        else: node['termRows'] += len(rows)
        node['continuation'] = payload.get('continue')
        if node['missing']: node['phase'], node['continuation'] = 'missing', None
        elif not node['continuation']:
            node['phase'] = 'terms' if page['phase'] == 'children' else 'done'
    return nodes, excluded


def fetch(args):
    directory = h.external(args.source_dir); rule = policy(args.policy)
    h.require(args.max_requests > 0, 'Source request budget must be positive')
    directory.mkdir(parents=True, exist_ok=True)
    with h.lock(directory):
        if (directory / 'coverage.json').exists(): return verify(directory, args.policy)
        pages, files = [], {}
        if args.resume_from:
            previous = h.external(args.resume_from); old = verify(previous, args.policy)
            for name in old['files']:
                if name.startswith('coverage-page-'): shutil.copyfile(previous / name, directory / name)
            pages = list(old['pages']); files = {k: dict(v) for k,v in old['files'].items() if k.startswith('coverage-page-')}
        advisor = read_advice(args.advice, args.resume_from) if args.advice else None
        ranks = {r['node']: {'high': 0, 'normal': 1, 'low': 2}[r['priority']] for r in advisor['decisions']} if advisor else {}
        requests, errors, paused, budget_stopped = 0, [], False, False
        request_log = []
        checkpoint=directory/'checkpoint.json'
        if checkpoint.exists():
            saved=h.replay.read_json(checkpoint)
            h.require(saved['policySha256']==h.replay.sha(args.policy) and saved['advisor']==advisor,
                      'Changed interrupted source-walk configuration')
            pages,files,requests,request_log=saved['pages'],saved['files'],saved['requests'],saved['requestLog']
            for name,record in files.items():h.require(h.replay.sha(directory/name)==record['sha256'],'Changed interrupted source payload')
        def save_checkpoint():
            h.dump(checkpoint,dict(policySha256=h.replay.sha(args.policy),advisor=advisor,pages=pages,files=files,
                requests=requests,requestLog=request_log))
        while True:
            nodes, excluded = replay(rule, pages, directory)
            eligible = [n for n in nodes.values() if n['phase'] in {'children', 'terms'} and
                        (not args.metadata_only or n['depth'] == 0 and n['phase'] == 'children')]
            if not eligible or requests >= args.max_requests or paused: break
            node = min(eligible, key=lambda n: (n['depth'], ranks.get(n['id'], 1), n['pages'], n['id']))
            url = request_url(node['category'], node['phase'], node['continuation'])
            name = 'coverage-page-' + hashlib.sha256(url.encode()).hexdigest() + '.json'; path = directory / name
            try:
                if not path.exists():
                    for attempt in range(3):
                        if requests >= args.max_requests:
                            budget_stopped = paused = True
                            break
                        requests += 1
                        request_log.append(dict(file=name,status='inflight',url=url))
                        save_checkpoint()
                        try:
                            download.download(url, path, 16 * 1024 * 1024)
                            request_log[-1].update(status='success')
                            save_checkpoint()
                            break
                        except urllib.error.HTTPError as error:
                            request_log[-1].update(status='http_error',code=error.code)
                            save_checkpoint()
                            retry = error.headers.get('Retry-After', '')
                            delay = int(retry) if retry.isdigit() else 5 * (attempt + 1)
                            if error.code not in {429, 503} or attempt == 2 or delay > 60: raise
                            time.sleep(max(5, delay))
                    if budget_stopped: continue
                    time.sleep(2)
                payload = h.replay.read_json(path); rows = source_rows(payload, node['phase'])
                category_missing(payload,node)
                following=payload.get('continue')
                h.require(not following or following!=node['continuation'] and not any(
                    p['node']==node['id'] and p['phase']==node['phase'] and p['continuation']==following for p in pages),
                    'Stalled/cyclic source pagination')
            except (OSError, ValueError, KeyError) as error:
                if request_log and request_log[-1]['file']==name and request_log[-1]['status']=='inflight':
                    request_log[-1].update(status='transport_error',errorType=type(error).__name__)
                if path.exists(): path.unlink()
                failure = dict(node=node['id'], phase=node['phase'], reason=type(error).__name__)
                if isinstance(error, urllib.error.HTTPError): failure['httpStatus'] = error.code
                errors.append(failure); paused = True
                save_checkpoint()
                print(json.dumps(dict(pending=failure)), flush=True); continue
            files[name] = dict(url=url, sha256=h.replay.sha(path))
            pages.append(dict(node=node['id'], phase=node['phase'], continuation=node['continuation'], file=name, rows=len(rows)))
            if request_log and request_log[-1]['file']==name and request_log[-1]['status']=='inflight':
                request_log[-1].update(status='recovered_from_cache')
            save_checkpoint()
            print(json.dumps(dict(topic=node['topic'], category=node['category'], phase=node['phase'], rows=len(rows), requests=requests)), flush=True)
        nodes, excluded = replay(rule, pages, directory)
        notice = directory / 'COVERAGE-SOURCES.txt'
        notice.write_text('English dictionary source-tree acquisition. Wiktionary contributors, CC BY-SA 4.0.\n'
            'https://en.wiktionary.org/wiki/Wiktionary:Copyrights\n'
            'Changes: select exact English headwords from declared English topical categories and descendants; '
            'retain source paths and hashes; merge exact spellings. No definitions, invented words or derived inflections.\n'
            'Traversal completeness describes only the declared source scope, not all English, input frequency or sense disambiguation.\n'
            'Preserve the full CC BY-SA notice shipped with the existing dictionary.\n', encoding='utf-8')
        files[notice.name] = dict(sha256=h.replay.sha(notice))
        remaining = sum(n['phase'] in {'children', 'terms'} for n in nodes.values())
        missing = sum(n['missing'] for n in nodes.values())
        reason = ('request_budget' if budget_stopped else 'source_error' if errors else 'metadata_bootstrap' if args.metadata_only
                  else 'request_budget' if remaining else 'source_missing' if missing else 'declared_source_walk_finished')
        manifest = dict(schemaVersion=1, kind='english-source-tree-coverage', policy=rule, policySha256=h.replay.sha(args.policy),
            pages=pages, files=files, nodes=nodes, exclusions=excluded, errors=errors, sourceRequests=requests,
            stopReason=reason, complete=not remaining and not missing, remainingCategories=remaining, missingCategories=missing,
            requestLog=request_log, advisor=advisor, capturedAt=h.dt.datetime.now(h.dt.timezone.utc).isoformat())
        h.dump(directory / 'coverage.json', manifest)
        verify(directory, args.policy)
        return dict(complete=manifest['complete'], stopReason=reason, categories=len(nodes), remainingCategories=remaining,
                    missingCategories=missing, termRows=sum(n['termRows'] for n in nodes.values()), sourceRequests=requests)


def verify(directory, policy_path=POLICY):
    directory = h.external(directory); manifest = h.replay.read_json(directory / 'coverage.json'); rule = policy(policy_path)
    h.require(manifest['schemaVersion'] == 1 and manifest['kind'] == 'english-source-tree-coverage' and
              manifest['policy'] == rule and manifest['policySha256'] == h.replay.sha(policy_path), 'Changed source-coverage policy')
    expected = {'COVERAGE-SOURCES.txt'}
    for page in manifest['pages']:
        node = manifest['nodes'][page['node']]; expected_url = urlparse(request_url(node['category'], page['phase'], page['continuation']))
        actual_url = urlparse(manifest['files'][page['file']]['url'])
        name = 'coverage-page-' + hashlib.sha256(actual_url.geturl().encode()).hexdigest() + '.json'
        h.require(page['file'] == name and (actual_url.scheme,actual_url.netloc,actual_url.path,actual_url.fragment) ==
            (expected_url.scheme,expected_url.netloc,expected_url.path,'') and
            parse_qs(actual_url.query) == parse_qs(expected_url.query), 'Changed source-tree query')
        expected.add(name)
    h.require(set(manifest['files']) == expected, 'Missing/extra source-tree files')
    for name, record in manifest['files'].items():
        path = directory / name
        h.require(Path(name).name == name and path.is_file() and not path.is_symlink() and h.replay.sha(path) == record['sha256'],
                  'Changed source-tree payload: ' + name)
    nodes, excluded = replay(rule, manifest['pages'], directory)
    remaining = sum(n['phase'] in {'children', 'terms'} for n in nodes.values()); missing = sum(n['missing'] for n in nodes.values())
    h.require(nodes == manifest['nodes'] and excluded == manifest['exclusions'] and remaining == manifest['remainingCategories'] and
              missing == manifest['missingCategories'] and manifest['complete'] == (not remaining and not missing),
              'Source-tree queue/completion differs from captured pages')
    if 'requestLog' in manifest:
        h.require(len(manifest['requestLog'])==manifest['sourceRequests'],'Source request accounting differs')
    return manifest


def collect(directory, policy_path=POLICY):
    directory = h.external(directory); manifest = verify(directory, policy_path); records = {}
    for page in manifest['pages']:
        if page['phase'] != 'terms': continue
        node = manifest['nodes'][page['node']]
        for row in source_rows(h.replay.read_json(directory / page['file']), 'terms'):
            key = row['title'], row['pageid']
            item = records.setdefault(key, dict(surface=row['title'], kind='lexical', entity='wiktionary-tree:' + str(row['pageid']), topics=[], proofs=[]))
            if not any(ch.isalpha() for ch in row['title']):item['sourceScopeDeferred']=True
            item['topics'] = sorted(set(item['topics']) | {node['topic']})
            proof = dict(source='wiktionary_source_tree', provider='wiktionary', pageId=row['pageid'],
                url='https://en.wiktionary.org/w/index.php?curid=' + str(row['pageid']), license='CC-BY-SA-4.0',
                sha256=manifest['files'][page['file']]['sha256'], englishCategory=node['category'], categoryPath=node['path'])
            if proof not in item['proofs']: item['proofs'].append(proof)
    return sorted(records.values(), key=lambda r: (r['surface'], r['entity'])), manifest, [
        dict(name='COVERAGE-SOURCES.txt', path=str(directory / 'COVERAGE-SOURCES.txt'), sha256=manifest['files']['COVERAGE-SOURCES.txt']['sha256'])]


def provenance(directory, manifest):
    """Publish source/license pins, keeping queue state and model replies external."""
    advisor = manifest.get('advisor')
    return dict(schemaVersion=1, provider='wiktionary',
        sourceSnapshotSha256=h.replay.sha(h.external(directory) / 'coverage.json'),
        policySha256=manifest['policySha256'], scope=manifest['policy'], files=manifest['files'],
        advisor={k: advisor[k] for k in ['model', 'promptSha256', 'files']} if advisor else None)


def read_advice(path, source):
    path = h.external(path); value = h.replay.read_json(path / 'advice.json')
    h.require(value['sourceSha256'] == h.replay.sha(h.external(source) / 'coverage.json'), 'Advice belongs to another source snapshot')
    for name, digest in value['files'].items():
        h.require(Path(name).name == name and h.replay.sha(path / name) == digest, 'Changed source-priority advice')
    import coverage_harness as controller
    captured=h.replay.read_json(h.external(source)/'coverage.json');nodes=captured['nodes'];rebuilt=[]
    for attempt in h.replay.read_json(path/'attempts.json'):
        if attempt['status']!='completed':continue
        name=attempt['requestFile'];request=h.replay.read_json(path/name)
        h.require(request['systemInstruction']=={'parts':[{'text':controller.PROMPT}]} and
                  request['generationConfig']['responseSchema']==controller.SCHEMA,'Changed advice prompt/schema')
        batch=json.loads(request['contents'][0]['parts'][0]['text'])
        for row in batch:
            node=nodes[row['id']]
            h.require((row['topic'],row['category'],row['path'],row['phase'])==
                (node['topic'],node['category'],node['path'],node['phase']) and
                row['dictionarySpellings']==value['dictionaryCounts'][row['topic']],'Advice input differs from source frontier')
        reply=name.replace('request-','response-')
        decisions,_=controller.response((path/reply).read_bytes(),batch);rebuilt.extend(decisions)
    h.require(rebuilt==value['decisions'] and len({r['node'] for r in rebuilt})==len(rebuilt) and
        value['remainingReviewNodes']==sum(n['phase'] in {'children','terms'} for n in nodes.values())-len(rebuilt),
        'Changed advice decisions/completion')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--policy', type=Path, default=POLICY); parser.add_argument('--max-requests', type=int, default=300)
    parser.add_argument('--resume-from', type=Path); parser.add_argument('--advice', type=Path)
    parser.add_argument('--metadata-only', action='store_true')
    print(json.dumps(fetch(parser.parse_args()), ensure_ascii=False, sort_keys=True))


if __name__ == '__main__': main()
