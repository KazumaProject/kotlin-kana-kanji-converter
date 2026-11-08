"""Source-backed case/victim flags; authoring evidence is separate from distributed vocabulary."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import shutil
import csv
import urllib.error
from urllib.parse import urlencode

import dbpedia_sources as db
import dictionary_sources as download
import pantheon_sources
import vocabulary_harness as h
import vocabulary_sources as lexical

POLICY=h.REPO/'english-ime/data/catalog/sensitive-policy.json'


def ordinary_spellings(assets):
    """Positive prior lexical/entity analyses protect ambiguous victim aliases."""
    lexical_roles={'noun','verb','adjective','adverb','pronoun','determiner','preposition','conjunction','interjection','contraction','abbreviation','phrase'}
    lexical_forms=set();proper_forms=set();entities=set()
    with (assets/'grammar/memberships.tsv').open(encoding='utf-8',newline='') as stream:
        for row in csv.DictReader(stream,delimiter='\t'):
            key=(row['lexeme_id'],row['surface']);category=row['category']
            if category in lexical_roles:lexical_forms.add(key)
            if category in {'noun_proper','name_person'}:proper_forms.add(key)
            if category.startswith('identifier_') or category.startswith('name_') and category!='name_person':entities.add(row['surface'])
    return {surface for _,surface in lexical_forms-proper_forms}|entities


def address(selector,size,after=None):
    cursor='FILTER(STR(?item)>'+json.dumps(after)+')' if after else ''
    prefix='''PREFIX wd:<http://www.wikidata.org/entity/>
PREFIX wdt:<http://www.wikidata.org/prop/direct/>
PREFIX dbo:<http://dbpedia.org/ontology/>
PREFIX dbp:<http://dbpedia.org/property/>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos:<http://www.w3.org/2004/02/skos/core#>
'''
    alias='OPTIONAL { ?item skos:altLabel ?alias. FILTER(LANG(?alias)="en") }' if selector['provider']=='wikidata' else ''
    query=prefix+'''SELECT DISTINCT ?item ?label ?alias WHERE {
 { SELECT DISTINCT ?item WHERE { '''+selector['body']+' '+cursor+''' }
 ORDER BY STR(?item) LIMIT '''+str(size)+''' }
 OPTIONAL { ?item rdfs:label ?label. FILTER(LANG(?label)="en") }
 '''+alias+'''
} ORDER BY STR(?item) STR(?label) STR(?alias)'''
    return ('https://query.wikidata.org/sparql?' if selector['provider']=='wikidata' else 'https://dbpedia.org/sparql?')+urlencode(dict(query=query,format='json' if selector['provider']=='wikidata' else 'application/sparql-results+json'))


def fetch(directory,policy_path=POLICY,cache_from=None):
    directory=h.external(directory);directory.mkdir(parents=True,exist_ok=True);rule=h.replay.read_json(policy_path)
    h.require(rule['schemaVersion']==1 and rule['victimMode'] in rule['availableVictimModes'] and
        1<=rule['pageSize']<=500,'Invalid sensitive-source policy')
    with h.lock(directory):
        if (directory/'sensitive.json').exists():return verify(directory,policy_path)
        checkpoint=directory/'checkpoint.json'
        value=h.replay.read_json(checkpoint) if checkpoint.exists() else dict(schemaVersion=1,complete=False,
            policy=rule,policySha256=h.replay.sha(policy_path),pages=[],attempts=[])
        h.require(value['policy']==rule,'Changed interrupted sensitive-source policy')
        cache={}
        if cache_from:
            cache_from=h.external(cache_from);old=h.replay.read_json(cache_from/'sensitive.json')
            for page in old['pages']:
                path=cache_from/page['file']
                h.require(page['file']=='sensitive-'+hashlib.sha256(page['url'].encode()).hexdigest()+'.json' and
                    not path.is_symlink() and h.replay.sha(path)==page['sha256'],'Changed sensitive-source cache')
                if page['headers']:db.complete_headers(page['headers'])
                cache[page['url']]=(path,page['headers'])
            value['cacheSourceManifestSha256']=h.replay.sha(cache_from/'sensitive.json')
        for selector in rule['selectors']:
            previous=[p for p in value['pages'] if p['selector']==selector['id']]
            if previous and previous[-1]['entities']<rule['pageSize']:continue
            after=previous[-1]['last'] if previous else None
            while True:
                url=address(selector,rule['pageSize'],after);name='sensitive-'+hashlib.sha256(url.encode()).hexdigest()+'.json'
                for attempt in range(3):
                    value['attempts'].append(dict(url=url,status='inflight'));h.dump(checkpoint,value)
                    try:
                        if url in cache:
                            source,headers=cache[url];shutil.copyfile(source,directory/name)
                        elif selector['provider']=='dbpedia':headers=db.download(url,directory/name)
                        else:download.download(url,directory/name,24*1024*1024);headers={}
                        payload=h.replay.read_json(directory/name);h.require('error' not in payload,'Sensitive source returned an error')
                        rows=payload['results']['bindings'];ids={r['item']['value'] for r in rows}
                        h.require(len(ids)<=rule['pageSize'],'Oversized sensitive-source page')
                        last=max(ids) if ids else after
                        value['pages'].append(dict(selector=selector['id'],file=name,url=url,sha256=h.replay.sha(directory/name),
                            headers=headers,after=after,last=last,entities=len(ids),rows=len(rows)))
                        value['attempts'][-1]['status']='success';h.dump(checkpoint,value)
                        print(json.dumps(dict(source=selector['id'],entities=len(ids),pages=len(value['pages']))),flush=True)
                        break
                    except (OSError,ValueError,KeyError) as error:
                        value['attempts'][-1].update(status='failed',error=type(error).__name__);h.dump(checkpoint,value)
                        (directory/name).unlink(missing_ok=True)
                        if attempt==2 or isinstance(error,urllib.error.HTTPError) and error.code==429:raise
                        time.sleep(65)
                if url not in cache:time.sleep(3)
                if len(ids)<rule['pageSize']:break
                after=last
        value['complete']=True;h.dump(directory/'sensitive.json',value)
        return verify(directory,policy_path)


def verify(directory,policy_path=POLICY):
    directory=h.external(directory);v=h.replay.read_json(directory/'sensitive.json');rule=h.replay.read_json(policy_path)
    h.require(rule['victimMode'] in rule['availableVictimModes'] and v['schemaVersion']==1 and v['complete'] and
              all(v['policy'][k]==rule[k] for k in ['schemaVersion','pageSize','selectors']),
              'Changed/incomplete sensitive-source capture')
    for selector in rule['selectors']:
        pages=[p for p in v['pages'] if p['selector']==selector['id']];h.require(pages,'Missing sensitive source')
        after=None
        for index,page in enumerate(pages):
            if selector['provider']=='dbpedia':db.complete_headers(page['headers'])
            h.require(page['after']==after and page['url']==address(selector,rule['pageSize'],after) and
                page['file']=='sensitive-'+hashlib.sha256(page['url'].encode()).hexdigest()+'.json' and
                not (directory/page['file']).is_symlink() and h.replay.sha(directory/page['file'])==page['sha256'],
                'Changed sensitive query/payload')
            rows=h.replay.read_json(directory/page['file'])['results']['bindings'];ids={r['item']['value'] for r in rows}
            h.require(len(rows)==page['rows'] and len(ids)==page['entities'] and
                (len(ids)==rule['pageSize'])==(index<len(pages)-1) and all(after is None or i>after for i in ids),
                'Incomplete/non-advancing sensitive pagination')
            prefix='http://www.wikidata.org/entity/Q' if selector['provider']=='wikidata' else 'http://dbpedia.org/resource/'
            for row in rows:
                h.require(row['item']['value'].startswith(prefix) and all(row[field].get('xml:lang')=='en'
                    for field in ['label','alias'] if field in row),'Invalid sensitive identity/language')
            after=max(ids) if ids else after;h.require(after==page['last'],'Changed sensitive cursor')
    return v


def collect(directory,pantheon_dir,policy_path=POLICY,public_people=(),public_people_snapshot=None,ordinary_assets=None):
    directory=h.external(directory);v=verify(directory,policy_path);rule=h.replay.read_json(policy_path);scopes={s['id']:s for s in rule['selectors']}
    people,_,_,_=pantheon_sources.collect(pantheon_dir)
    known={r['entity'].split(':',1)[1]:r for r in people};protected=set()
    if rule['victimMode']=='case_context_only':
        for person in people:
            if person['proofs'][0]['occupation'] not in rule['independentPublicRolesExclude']:
                protected.add(person['entity'].split(':',1)[1])
    protected_spellings={lexical.key(p['surface']) for q,p in known.items() if q in protected}
    ordinary={lexical.key(s) for s in ordinary_spellings(ordinary_assets)} if ordinary_assets else set()
    if rule['victimMode']=='case_context_only':
        protected_spellings.update(lexical.key(p['surface']) for p in public_people if p['kind']=='person' and
            any(t in {'people.actors','people.singers'} or t.startswith(('people.sports','names.')) for t in p['topics']))
    restrictions={};retained={}
    for page in v['pages']:
        selector=scopes[page['selector']]
        for row in h.replay.read_json(directory/page['file'])['results']['bindings']:
            entity=row['item']['value'];qid=entity.rsplit('/',1)[-1] if selector['provider']=='wikidata' else None
            spellings={row[f]['value'] for f in ['label','alias'] if f in row}
            if qid in known:spellings.add(known[qid]['surface'])
            if qid in protected:protected_spellings.update(lexical.key(s) for s in spellings)
            for surface in spellings:
                item=dict(surface=surface,reason=selector['reason'],evidence=(
                    'https://www.wikidata.org/wiki/'+qid if qid else entity.replace('http://','https://',1)),
                    license='CC0-1.0' if qid else 'CC-BY-SA-3.0')
                target=retained if lexical.key(surface) in ordinary or lexical.key(surface) in protected_spellings or (
                    item['reason']=='victim-person' and (qid in protected or surface.islower() and ' ' not in surface)) else restrictions
                target[surface,item['reason'],item['evidence']]=item
    public=dict(schemaVersion=1,complete=True,policy=rule,capturePolicySha256=v['policySha256'],
        decisionPolicySha256=h.replay.sha(policy_path),
        independentNameSources=public_people_snapshot,
        ordinaryVocabularyAssetsSha256=hashlib.sha256(json.dumps(h.asset_hashes(ordinary_assets),sort_keys=True).encode()).hexdigest() if ordinary_assets else None,
        sourceSnapshotSha256=h.replay.sha(directory/'sensitive.json'),
        files={p['file']:dict(url=p['url'],sha256=p['sha256']) for p in v['pages']})
    return (sorted(restrictions.values(),key=lambda r:(r['surface'],r['reason'],r['evidence'])),public,
        sorted(retained.values(),key=lambda r:(r['surface'],r['reason'],r['evidence'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-dir',type=Path,required=True)
    parser.add_argument('--policy',type=Path,default=POLICY);parser.add_argument('--cache-from',type=Path)
    args=parser.parse_args();print(fetch(args.source_dir,args.policy,args.cache_from)['complete'])
