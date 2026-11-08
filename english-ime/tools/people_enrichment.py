"""Enrich all published notable people through bounded, exact-identity lookups."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode, unquote
from urllib.parse import urlsplit
import urllib.request
import urllib.error
import shutil

import dbpedia_sources as db
import pantheon_sources
import vocabulary_harness as h

POLICY=h.REPO/'english-ime/data/catalog/people-enrichment-policy.json'


def population(directory,all_people=False):
    records,manifest,_,_=pantheon_sources.collect(directory)
    sports=sorted((r for r in records if any(t.startswith('people.sports') for t in r['topics'])),key=lambda r:r['entity'])
    if not all_people:return sports,manifest
    known={r['entity'] for r in sports}
    return sports+sorted((r for r in records if r['entity'] not in known),key=lambda r:r['entity']),manifest


def batches(records,rule):
    # Preserve the original sports query batches so a broadened capture can
    # reuse their exact immutable responses rather than refetching them.
    boundary=next((i for i,r in enumerate(records) if not any(t.startswith('people.sports') for t in r['topics'])),len(records))
    groups=[(0,boundary)]+([(boundary,len(records))] if boundary<len(records) else [])
    return [(start,[r['entity'].split(':',1)[1] for r in records[start:min(start+rule['batchSize'],end)]])
        for begin,end in groups for start in range(begin,end,rule['batchSize'])]


def address(ids):
    # Exact QIDs, not names or model-created article titles, bind the two sources.
    values=' '.join('wd:'+i for i in ids)
    query='''PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX owl:<http://www.w3.org/2002/07/owl#>
PREFIX dct:<http://purl.org/dc/terms/>
SELECT ?entity ?item (GROUP_CONCAT(DISTINCT STR(?type);separator="|") AS ?types)
 (GROUP_CONCAT(DISTINCT STR(?category);separator="|") AS ?categories) WHERE {
 VALUES ?entity { '''+values+''' }
 ?item owl:sameAs ?entity.
 FILTER(STRSTARTS(STR(?item),"http://dbpedia.org/resource/"))
 OPTIONAL { ?item a ?type. FILTER(STRSTARTS(STR(?type),"http://dbpedia.org/ontology/")) }
 OPTIONAL { ?item dct:subject ?category. }
} GROUP BY ?entity ?item'''
    return 'https://dbpedia.org/sparql?'+urlencode(dict(query=query,format='application/sparql-results+json'))


def download(address,path):
    # POST avoids HTTP URL-size limits for a complete 1,000-identity transport
    # batch. The encoded query remains in the provenance, and partial responses
    # are checked exactly as for GET acquisitions.
    parts=urlsplit(address)
    request=urllib.request.Request('https://dbpedia.org/sparql',data=parts.query.encode(),method='POST',
        headers={'User-Agent':'EnglishDictionaryHarness/1.0 (KazumaProject/kotlin-kana-kanji-converter)',
                 'Content-Type':'application/x-www-form-urlencoded','Accept':'application/sparql-results+json'})
    with urllib.request.urlopen(request,timeout=150) as reply:
        headers=dict(reply.headers);db.complete_headers(headers);body=reply.read(24*1024*1024+1)
    h.require(len(body)<=24*1024*1024 and 'error' not in json.loads(body),'Oversized/failed enrichment result')
    path.write_bytes(body);return headers


def fetch(directory,pantheon_dir,policy_path=POLICY,cache_from=None):
    directory=h.external(directory);directory.mkdir(parents=True,exist_ok=True)
    rule=h.replay.read_json(policy_path);records,source=population(pantheon_dir,rule.get('allPeople',False));ids=[r['entity'].split(':',1)[1] for r in records]
    h.require(rule['schemaVersion']==1 and 1<=rule['batchSize']<=1000 and rule['httpMethod']=='POST','Invalid enrichment transport policy')
    with h.lock(directory):
        if (directory/'enrichment.json').exists():return verify(directory,pantheon_dir,policy_path)
        path=directory/'checkpoint.json'
        manifest=h.replay.read_json(path) if path.exists() else dict(schemaVersion=1,complete=False,policy=rule,
            policySha256=h.replay.sha(policy_path),pantheonManifestSha256=h.replay.sha(pantheon_dir/'pantheon.json'),
            targetQids=ids,pages=[],attempts=[])
        h.require(manifest['targetQids']==ids and manifest['policy']==rule and
            manifest['pantheonManifestSha256']==h.replay.sha(pantheon_dir/'pantheon.json'),'Changed enrichment source population')
        cache={}
        if cache_from:
            cache_from=h.external(cache_from);old=h.replay.read_json(cache_from/'enrichment.json')
            h.require(old['pantheonManifestSha256']==h.replay.sha(pantheon_dir/'pantheon.json'),'Changed enrichment cache population')
            for page in old['pages']:
                cached_file=cache_from/page['file'];db.complete_headers(page['headers'])
                h.require(page['method']=='POST' and page['file']=='people-'+hashlib.sha256(page['url'].encode()).hexdigest()+'.json' and
                    not cached_file.is_symlink() and h.replay.sha(cached_file)==page['sha256'],'Changed enrichment cache')
                cache[page['url']]=(cached_file,page['headers'])
            manifest['cacheSourceManifestSha256']=h.replay.sha(cache_from/'enrichment.json')
        for start,batch in batches(records,rule):
            if any(p['start']==start for p in manifest['pages']):continue
            url=address(batch);name='people-'+hashlib.sha256(url.encode()).hexdigest()+'.json'
            for attempt in range(3):
                manifest['attempts'].append(dict(start=start,status='inflight'));h.dump(path,manifest)
                try:
                    if url in cache:
                        cached_file,headers=cache[url];shutil.copyfile(cached_file,directory/name)
                    else:headers=download(url,directory/name)
                    manifest['pages'].append(dict(start=start,count=len(batch),url=url,file=name,
                        sha256=h.replay.sha(directory/name),headers=headers,method='POST'))
                    manifest['attempts'][-1]['status']='success';h.dump(path,manifest)
                    print(json.dumps(dict(processed=start+len(batch),total=len(ids))),flush=True)
                    break
                except (OSError,ValueError) as error:
                    manifest['attempts'][-1].update(status='failed',error=type(error).__name__);h.dump(path,manifest)
                    if attempt==2 or isinstance(error,urllib.error.HTTPError) and error.code==429:raise
                    time.sleep(65)
            if url not in cache:time.sleep(2)
        manifest['complete']=True;h.dump(directory/'enrichment.json',manifest)
        return verify(directory,pantheon_dir,policy_path)


def verify(directory,pantheon_dir,policy_path=POLICY):
    directory=h.external(directory);v=h.replay.read_json(directory/'enrichment.json');rule=h.replay.read_json(policy_path)
    records,_=population(pantheon_dir,rule.get('allPeople',False));ids=[r['entity'].split(':',1)[1] for r in records]
    h.require(v['schemaVersion']==1 and v['complete'] and all(v['policy'][k]==rule[k] for k in ['schemaVersion','batchSize','httpMethod']) and
        v['pantheonManifestSha256']==h.replay.sha(pantheon_dir/'pantheon.json') and v['targetQids']==ids,'Changed/incomplete enrichment')
    plan=dict(batches(records,rule))
    h.require([p['start'] for p in v['pages']]==list(plan),'Missing/repeated enrichment batches')
    for page in v['pages']:
        batch=plan[page['start']];db.complete_headers(page['headers'])
        h.require(page['count']==len(batch) and page['method']=='POST' and page['url']==address(batch) and
            page['file']=='people-'+hashlib.sha256(page['url'].encode()).hexdigest()+'.json' and
            not (directory/page['file']).is_symlink() and h.replay.sha(directory/page['file'])==page['sha256'],'Changed enrichment query/payload')
        seen=set()
        for row in h.replay.read_json(directory/page['file'])['results']['bindings']:
            qid=row['entity']['value'].rsplit('/',1)[-1];key=(qid,row['item']['value'])
            h.require(qid in batch and key not in seen and key[1].startswith('http://dbpedia.org/resource/'),
                      'Unexpected/repeated classification identity');seen.add(key)
            h.require(all(t.startswith('http://dbpedia.org/ontology/') for t in row['types']['value'].split('|') if t) and
                all(t.startswith('http://dbpedia.org/resource/Category:') for t in row['categories']['value'].split('|') if t),
                'Invalid classification class/category URI')
    return v


def classified_topics(row,rule):
    topics={rule['classTopics'][t.rsplit('/',1)[-1]] for t in row['types']['value'].split('|')
            if t.rsplit('/',1)[-1] in rule['classTopics']}
    for category in row['categories']['value'].split('|'):
        title=unquote(category.split('Category:',1)[-1])
        topics.update(r['topic'] for r in rule['categoryRules'] if re.search(r['pattern'],title,re.I))
    if any(t.startswith('people.sports.') for t in topics):topics.add('people.sports')
    return sorted(topics)


def collect(directory,pantheon_dir,policy_path=POLICY):
    directory=h.external(directory);v=verify(directory,pantheon_dir,policy_path);rule=h.replay.read_json(policy_path)
    source,_=population(pantheon_dir,rule.get('allPeople',False));known={r['entity'].split(':',1)[1]:r for r in source};records={};matched=set()
    for page in v['pages']:
        for row in h.replay.read_json(directory/page['file'])['results']['bindings']:
            qid=row['entity']['value'].rsplit('/',1)[-1];matched.add(qid);topics=classified_topics(row,rule)
            if not topics:continue
            base=known[qid]
            item=records.setdefault(qid,dict(surface=base['surface'],kind='person',entity=base['entity'],
                topics=[],proofs=list(base['proofs'])))
            item['topics']=sorted(set(item['topics'])|set(topics))
            item['proofs'].append(dict(source='dbpedia_person_classification',url=row['item']['value'].replace('http://','https://',1),
                entity=qid,license='CC-BY-SA-3.0',sha256=page['sha256'],classes=row['types']['value'].split('|'),
                categories=row['categories']['value'].split('|')))
    public=dict(schemaVersion=1,complete=True,policy=rule,capturePolicySha256=v['policySha256'],
        classificationPolicySha256=h.replay.sha(policy_path),
        sourceSnapshotSha256=h.replay.sha(directory/'enrichment.json'),pantheonManifestSha256=v['pantheonManifestSha256'],
        targets=len(v['targetQids']),matchedEntities=len(matched),missingEntityMetadata=len(set(v['targetQids'])-matched),
        files={p['file']:dict(url=p['url'],sha256=p['sha256']) for p in v['pages']})
    return sorted(records.values(),key=lambda r:r['surface']),public


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-dir',type=Path,required=True)
    parser.add_argument('--pantheon-dir',type=Path,required=True);parser.add_argument('--policy',type=Path,default=POLICY)
    parser.add_argument('--cache-from',type=Path)
    args=parser.parse_args();value=fetch(args.source_dir,args.pantheon_dir,args.policy,args.cache_from)
    print(json.dumps(dict(complete=value['complete'],targets=len(value['targetQids']))))
