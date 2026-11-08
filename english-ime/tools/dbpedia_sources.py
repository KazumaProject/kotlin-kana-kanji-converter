"""Paged, header-checked DBpedia name acquisition with no adoption-count cap."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
from urllib.parse import urlencode
import urllib.request
import urllib.error

import vocabulary_harness as h
import dictionary_sources

POLICY=h.REPO/'english-ime/data/catalog/dbpedia-policy.json'
LICENSE='CC-BY-SA-3.0'
NOTICES={
    'DBPEDIA-CC-BY-SA-3.0.html':('https://creativecommons.org/licenses/by-sa/3.0/legalcode.en','c33d7ebdbcc5c8db073e69a794b2ac44805f5d7d9edcfb8b5181a71869a9b7d5'),
    'DBPEDIA-GFDL-1.3.txt':('https://www.gnu.org/licenses/fdl-1.3.txt','110535522396708cea37c72a802c5e7e81391139f5f7985631c93ef242b206a4')}


def ensure_notices(directory):
    for name,(url,digest) in NOTICES.items():
        path=directory/name
        if not path.exists():dictionary_sources.download(url,path,1024*1024)
        h.require(h.replay.sha(path)==digest,'Changed DBpedia license text')
    (directory/'DBPEDIA-SOURCES.txt').write_text(
        'DBpedia and Wikipedia contributors. DBpedia data: CC BY-SA 3.0 / GFDL.\n'
        'https://www.dbpedia.org/about/\nhttps://www.dbpedia.org/resources/ontology/\n'
        'https://www.dbpedia.org/resources/sparql/\n'
        'Changes: select exact English source labels by the published type/category/occupation policies; '
        'join sports classifications by exact Wikidata identity; distinguish companies from product models; '
        'derive distribution exclusion keys from explicit source flags. No generated person names, '
        'model spellings or English article URLs. Preserve the query URLs and SHA-256 source pins '
        'in the authoring manifest and the full licenses alongside this notice. '
        'Source categories/types are classification evidence, not a guarantee of completeness, '
        'current popularity or career accuracy.\n',encoding='utf-8')


def check_notices(directory):
    h.require((directory/'DBPEDIA-SOURCES.txt').is_file(),'Missing DBpedia attribution')
    for name,(_,digest) in NOTICES.items():
        h.require((directory/name).is_file() and h.replay.sha(directory/name)==digest,'Missing/changed DBpedia license')


def policy(path):
    rule=h.replay.read_json(path)
    h.require(rule['schemaVersion']==1 and rule['pageSize']==5000,'Invalid DBpedia policy')
    h.require(len({s['id'] for s in rule['selectors']})==len(rule['selectors']),'Duplicate DBpedia selector')
    for s in rule['selectors']:
        h.require(s['kind'] in {'person','product','brand','organization','service'} and
                  bool(s.get('class'))!=bool(s.get('categories')),'Invalid DBpedia scope')
        h.require(all(re.fullmatch(r'[A-Za-z0-9_()-]+',x) for x in s.get('categories',[])) and
                  (not s.get('class') or re.fullmatch(r'[A-Za-z]+',s['class'])),'Invalid DBpedia scope URI')
        h.require(s.get('queryVersion',1) in {1,4} and 1<=s.get('pageSize',rule['pageSize'])<=5000 and
                  1<=s.get('categoryDepth',2)<=4,'Invalid DBpedia query version/page/category depth')
        h.require(not s.get('occupationValues') or s['kind']=='person' and
                  all(isinstance(x,str) and 1<=len(x)<=64 for x in s['occupationValues']),'Invalid source occupation values')
        h.require(not s.get('timeoutMs') or 1<=s['timeoutMs']<=120000,'Source timeout exceeds public fair-use limit')
    return rule


def selectors(rule):
    return rule['selectors']


def query(selector,offset,size,after=None):
    if selector.get('queryVersion')==4:return person_query_v4(selector,size,after)
    body=('?item a dbo:'+selector['class']+'.' if selector.get('class') else
          'VALUES ?root { '+' '.join('dbc:'+c for c in selector['categories'])+' } ?category '+
          '/'.join(['skos:broader?']*selector.get('categoryDepth',2))+' ?root. ?item dct:subject ?category.')
    if selector['kind']=='person':body+=' ?item a dbo:Person.'
    if selector['kind']=='organization':body+=' ?item a dbo:Company.'
    if selector['kind']=='service':body+=' FILTER(EXISTS { ?item a dbo:Website } || EXISTS { ?item a dbo:Company } || EXISTS { ?item a dbo:Magazine })'
    if selector.get('requireManufacturer'):
        if selector.get('includeRawManufacturer'):
            body+=' ?item (dbo:manufacturer|<http://dbpedia.org/property/manufacturer>) ?manufacturer. FILTER(STRLEN(STR(?manufacturer))>0 && !REGEX(STR(?manufacturer),"^(various|unknown|multiple)( |$)","i"))'
        else:body+=' ?item dbo:manufacturer ?manufacturer.'
    cursor=('FILTER(STR(?item)>'+json.dumps(after[0])+' || (STR(?item)='+json.dumps(after[0])+
            ' && STR(?label)>'+json.dumps(after[1])+'))') if after else ''
    return '''PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX dbc: <http://dbpedia.org/resource/Category:>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT DISTINCT ?item ?label ?article ?adult ?company WHERE {
 '''+body+'''
 ?item rdfs:label ?label; foaf:isPrimaryTopicOf ?article.
 FILTER(LANG(?label)="en")
 '''+cursor+'''
 FILTER(STRSTARTS(STR(?article),"http://en.wikipedia.org/wiki/") || STRSTARTS(STR(?article),"https://en.wikipedia.org/wiki/"))
 BIND(EXISTS { ?item a dbo:AdultActor } AS ?adult)
 BIND(EXISTS { ?item a dbo:Company } AS ?company)
} ORDER BY ?item ?label LIMIT '''+str(size)


def person_query_v4(selector,size,after):
    body='?item a dbo:'+selector['class']+'.'
    if selector.get('occupationValues'):
        values=' '.join(json.dumps(value)+'@en' for value in selector['occupationValues'])
        body='{ '+body+' } UNION { VALUES ?occupation { '+values+' } ?item dbp:occupation ?occupation. }'
    if selector.get('occupationPattern'):
        body='{ '+body+' } UNION { ?item dbp:occupation ?occupation. FILTER(REGEX(STR(?occupation),'+json.dumps(selector['occupationPattern'])+',"i")) }'
    if selector.get('requirePerson'):body='{ '+body+' } ?item a dbo:Person.'
    cursor='FILTER(STR(?item)>'+json.dumps(after[0])+')' if after else ''
    return '''PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX dbp: <http://dbpedia.org/property/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
SELECT ?item ?label ?adult ?company WHERE {
 { SELECT DISTINCT ?item WHERE {
  { '''+body+''' }
  '''+cursor+'''
 } ORDER BY STR(?item) LIMIT '''+str(size)+''' }
 OPTIONAL { ?item rdfs:label ?label. FILTER(LANG(?label)="en") }
 BIND('''+('true' if selector.get('restricted') else 'false')+''' AS ?adult)
 BIND(false AS ?company)
} ORDER BY STR(?item) STR(?label)'''



def page_count(selector,rows):
    return len({r['item']['value'] for r in rows}) if selector.get('queryVersion')==4 else len(rows)


def last_key(row):return [row['item']['value'],row.get('label',{}).get('value','')]


def url(selector,offset,size,after=None):
    parameters=dict(query=query(selector,offset,size,after),format='application/sparql-results+json')
    if selector.get('timeoutMs'):parameters['timeout']=selector['timeoutMs']
    return 'https://dbpedia.org/sparql?'+urlencode(parameters)


def complete_headers(headers):
    lower={k.lower():v for k,v in headers.items()}
    h.require('x-sparql-maxrows' not in lower and lower.get('x-sql-state','00000')=='00000' and
              'x-sql-message' not in lower,'DBpedia returned partial/capped results')


def download(address,path):
    request=urllib.request.Request(address,headers={'User-Agent':'EnglishDictionaryHarness/1.0 (KazumaProject/kotlin-kana-kanji-converter)',
        'Accept':'application/sparql-results+json'})
    with urllib.request.urlopen(request,timeout=150) as reply:
        headers=dict(reply.headers);complete_headers(headers)
        raw=reply.read(24*1024*1024+1);h.require(len(raw)<=24*1024*1024,'Oversized DBpedia page')
    payload=json.loads(raw);h.require('error' not in payload,'DBpedia source error')
    path.write_bytes(raw);return headers


def fetch(directory,policy_path=POLICY,cache_from=None):
    directory=h.external(directory);directory.mkdir(parents=True,exist_ok=True);rule=policy(policy_path)
    with h.lock(directory):
        if (directory/'dbpedia.json').exists():return verify(directory,policy_path)
        checkpoint=directory/'checkpoint.json'
        value=h.replay.read_json(checkpoint) if checkpoint.exists() else dict(schemaVersion=1,policy=rule,
            policySha256=h.replay.sha(policy_path),pages=[],files={},attempts=[],complete=False)
        h.require(value['policy']==rule,'Changed interrupted DBpedia policy')
        cache={}
        if cache_from:
            cache_from=h.external(cache_from)
            source=cache_from/('dbpedia.json' if (cache_from/'dbpedia.json').exists() else 'checkpoint.json')
            old=h.replay.read_json(source)
            for page in old['pages']:
                complete_headers(page['headers']);record=old['files'][page['file']];path=cache_from/page['file']
                h.require(path.name==page['file'] and not path.is_symlink() and h.replay.sha(path)==record['sha256'],'Changed DBpedia cache')
                cache[record['url']]=(path,page['headers'])
            value['cacheSourceManifestSha256']=h.replay.sha(source)
        for selector in selectors(rule):
            size=selector.get('pageSize',rule['pageSize'])
            previous=[p for p in value['pages'] if p['selector']==selector['id']]
            if previous and previous[-1].get('entities',previous[-1]['rows'])<size:continue
            offset=len(previous)*size
            after=previous[-1]['last'] if previous else None
            consecutive_failures=0
            while True:
                address=url(selector,offset,size,after);name='dbpedia-'+hashlib.sha256(address.encode()).hexdigest()+'.json';path=directory/name
                value['attempts'].append(dict(url=address,status='inflight'));h.dump(checkpoint,value)
                try:
                    if address in cache:
                        cached,headers=cache[address];shutil.copyfile(cached,path)
                    else:headers=download(address,path)
                    rows=h.replay.read_json(path)['results']['bindings']
                    count=page_count(selector,rows)
                    h.require(count<=size and len(rows)<=size*10,'Oversized source result set')
                    value['files'][name]=dict(url=address,sha256=h.replay.sha(path))
                    last=last_key(rows[-1]) if rows else after
                    value['pages'].append(dict(selector=selector['id'],offset=offset,file=name,rows=len(rows),entities=count,headers=headers,after=after,last=last))
                    value['attempts'][-1]['status']='cached' if address in cache else 'success';h.dump(checkpoint,value);consecutive_failures=0
                    print(json.dumps(dict(source=selector['id'],rows=offset+len(rows))),flush=True)
                except (OSError,ValueError,KeyError) as error:
                    path.unlink(missing_ok=True);value['attempts'][-1].update(status='failed',error=type(error).__name__);h.dump(checkpoint,value)
                    consecutive_failures+=1
                    print(json.dumps(dict(source=selector['id'],status='retry_pending',error=type(error).__name__,attempt=consecutive_failures)),flush=True)
                    if consecutive_failures>=3 or isinstance(error,urllib.error.HTTPError) and error.code==429:raise
                    time.sleep(65);continue
                if address not in cache:time.sleep(2)
                if count<size:break
                offset+=size;after=last
        value['complete']=True;h.dump(directory/'dbpedia.json',value);return verify(directory,policy_path)


def verify(directory,policy_path=POLICY):
    directory=h.external(directory);v=h.replay.read_json(directory/'dbpedia.json');rule=policy(policy_path)
    h.require(v['schemaVersion']==1 and v['policy']==rule and v['policySha256']==h.replay.sha(policy_path) and v['complete'],
              'Changed/incomplete DBpedia capture')
    h.require(set(v['files'])=={p['file'] for p in v['pages']},'Missing/extra DBpedia pages')
    for selector in selectors(rule):
        size=selector.get('pageSize',rule['pageSize'])
        pages=[p for p in v['pages'] if p['selector']==selector['id']];h.require(pages,'Missing DBpedia selector')
        previous=set()
        after=None
        for i,page in enumerate(pages):
            complete_headers(page['headers']);address=url(selector,i*size,size,after)
            h.require(page['offset']==i*size and v['files'][page['file']]['url']==address and
                      page['after']==after and
                      page['file']=='dbpedia-'+hashlib.sha256(address.encode()).hexdigest()+'.json' and
                      not (directory/page['file']).is_symlink() and h.replay.sha(directory/page['file'])==v['files'][page['file']]['sha256'],
                      'Changed DBpedia query/payload')
            rows=h.replay.read_json(directory/page['file'])['results']['bindings']
            h.require(len(rows)==page['rows'] and page_count(selector,rows)==page.get('entities',len(rows)) and
                      (page_count(selector,rows)==size)==(i<len(pages)-1),'Incomplete DBpedia pagination')
            keys={tuple(last_key(r)) for r in rows}
            h.require(len({json.dumps(r,sort_keys=True) for r in rows})==len(rows) and not keys&previous,
                      'Repeated DBpedia pagination');previous|=keys
            h.require([tuple(last_key(r)) for r in rows]==sorted(tuple(last_key(r)) for r in rows),'Unordered DBpedia keyset')
            h.require(all(after is None or k>tuple(after) for k in keys),'Non-advancing DBpedia keyset')
            after=last_key(rows[-1]) if rows else after
            h.require(page['last']==after,'Changed DBpedia keyset checkpoint')
            for r in rows:
                article_valid=(True if selector.get('queryVersion')==4 else
                               r.get('article',{}).get('value','').startswith(('http://en.wikipedia.org/wiki/','https://en.wikipedia.org/wiki/')))
                h.require(r['item']['value'].startswith('http://dbpedia.org/resource/') and ('label' not in r and selector.get('queryVersion')==4 or r.get('label',{}).get('xml:lang')=='en') and article_valid and
                          r['adult']['value'] in {'0','1','true','false'},'Invalid DBpedia identity/language')
    return v


def collect(directory,policy_path=POLICY):
    directory=h.external(directory);v=verify(directory,policy_path);scopes={s['id']:s for s in selectors(v['policy'])};records={};restricted=[]
    for page in v['pages']:
        selector=scopes[page['selector']]
        for row in h.replay.read_json(directory/page['file'])['results']['bindings']:
            if 'label' not in row:continue
            surface=row['label']['value'];entity=row['item']['value'];kind=selector['kind']
            if kind in {'brand','product','service'} and row['company']['value'] in {'1','true'}:kind='organization'
            item=records.setdefault((surface,kind,entity),dict(surface=surface,kind=kind,entity='dbpedia:'+entity,topics=[],proofs=[]))
            topic=(('organizations.technology' if selector['id'] in {'computing','imaging'} else 'organizations.consumer')
                   if selector['kind']!='organization' and kind=='organization' else selector['topic'])
            item['topics']=sorted(set(item['topics'])|{topic}|set(selector.get('extraTopics',[])))
            proof=dict(source='dbpedia',url=entity.replace('http://','https://',1),license=LICENSE,
                sha256=v['files'][page['file']]['sha256'],selector=selector['id'])
            if 'article' in row:proof['englishArticle']=row['article']['value']
            else:proof['typedEnglishLabel']=True
            if proof not in item['proofs']:item['proofs'].append(proof)
            if row['adult']['value'] in {'1','true'} or selector.get('restricted'):
                restricted.append(dict(surface=surface,reason='adult-industry-person' if kind=='person' else 'adult-industry-product-service',
                    evidence=proof['url'],license=LICENSE))
    public=dict(schemaVersion=1,policySha256=v['policySha256'],sourceSnapshotSha256=h.replay.sha(directory/'dbpedia.json'),scope=v['policy'],files=v['files'])
    return sorted(records.values(),key=lambda r:(r['surface'],r['kind'],r['entity'])),public,restricted


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--policy',type=Path,default=POLICY)
    p.add_argument('--cache-from',type=Path)
    args=p.parse_args();v=fetch(args.source_dir,args.policy,args.cache_from);print(json.dumps(dict(complete=v['complete'],pages=len(v['pages']))))
