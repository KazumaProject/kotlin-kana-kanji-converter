"""Acquire explicit middle-name usage; never infer it from name position."""
import argparse
import hashlib
from pathlib import Path
import re
import time
from urllib.parse import urlencode

import dictionary_sources as download
import vocabulary_harness as h


def url(offset):
    query='''PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?person ?name ?label WHERE {
 { SELECT DISTINCT ?person ?name WHERE {
   ?person p:P735 ?statement.
   ?statement ps:P735 ?name; pq:P3831 wd:Q245025.
  } ORDER BY ?person ?name LIMIT 5000 OFFSET '''+str(offset)+''' }
 OPTIONAL { ?name rdfs:label ?label. FILTER(LANG(?label)="en") }
} ORDER BY ?person ?name'''
    return 'https://query.wikidata.org/sparql?'+urlencode(dict(query=query,format='json'))


def fetch(directory):
    directory=h.external(directory);directory.mkdir(parents=True,exist_ok=True)
    with h.lock(directory):
        if (directory/'roles.json').exists():return verify(directory)
        pages=[];offset=0
        while True:
            address=url(offset);name='roles-'+hashlib.sha256(address.encode()).hexdigest()+'.json';path=directory/name
            download.download(address,path,16*1024*1024)
            data=h.replay.read_json(path);h.require('error' not in data,'Middle-name source error')
            rows=data['results']['bindings'];pages.append(dict(file=name,url=address,sha256=h.replay.sha(path),offset=offset,rows=len(rows)))
            if len(rows)<5000:break
            offset+=5000;time.sleep(65)
        value=dict(schemaVersion=1,pages=pages,complete=True,role='Q245025',predicate='P735/P3831',license='CC0-1.0')
        h.dump(directory/'roles.json',value);return verify(directory)


def verify(directory):
    directory=h.external(directory);v=h.replay.read_json(directory/'roles.json')
    h.require(v['schemaVersion']==1 and v['role']=='Q245025' and v['predicate']=='P735/P3831' and v['complete'],'Invalid middle-name capture')
    for i,p in enumerate(v['pages']):
        h.require(p['offset']==i*5000 and p['url']==url(p['offset']) and
                  p['file']=='roles-'+hashlib.sha256(p['url'].encode()).hexdigest()+'.json' and
                  h.replay.sha(directory/p['file'])==p['sha256'],'Changed middle-name evidence')
        rows=h.replay.read_json(directory/p['file'])['results']['bindings']
        h.require(len(rows)==p['rows'] and (len(rows)==5000)==(i<len(v['pages'])-1),'Incomplete middle-name pagination')
        for r in rows:
            h.require(re.fullmatch(r'http://www.wikidata.org/entity/Q[1-9][0-9]*',r['person']['value']) and
                      (re.fullmatch(r'http://www.wikidata.org/entity/Q[1-9][0-9]*',r['name']['value']) or
                       'label' not in r and r['name']['value'].startswith('http://www.wikidata.org/.well-known/genid/')) and
                      ('label' not in r or r['label'].get('xml:lang')=='en'),'Invalid middle-name identity/language')
    return v


def collect(directory):
    directory=h.external(directory);v=verify(directory);records={}
    for page in v['pages']:
        for row in h.replay.read_json(directory/page['file'])['results']['bindings']:
            if 'label' not in row:continue
            qid=row['name']['value'].rsplit('/',1)[-1];surface=row['label']['value'];person=row['person']['value'].rsplit('/',1)[-1]
            item=records.setdefault((surface,qid),dict(surface=surface,kind='person',entity='wikidata:'+qid,topics=['names.middle'],proofs=[]))
            proof=dict(source='wikidata_middle_name',url='https://www.wikidata.org/wiki/'+qid,usageUrl='https://www.wikidata.org/wiki/'+person+'#P735',
                entity=qid,person=person,role='Q245025',license='CC0-1.0',sha256=page['sha256'])
            if proof not in item['proofs']:item['proofs'].append(proof)
    return sorted(records.values(),key=lambda r:(r['surface'],r['entity'])),dict(v,sourceSnapshotSha256=h.replay.sha(directory/'roles.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-dir',type=Path,required=True)
    args=p.parse_args();value=fetch(args.source_dir);print(value)
