"""Collect attested English food/drink names from the complete raw Wiktextract stream."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import tarfile
from urllib.parse import quote

import bulk_names
import vocabulary_harness as h

POLICY=h.REPO/'english-ime/data/catalog/food-policy.json'


def topics(row,rule):
    if row.get('lang_code')!='en' or row.get('pos') not in {'noun','name'}:return []
    categories=set(row.get('categories',[]))
    for sense in row.get('senses',[]):categories.update(sense.get('categories',[]))
    found={topic for topic,patterns in rule['categoryPatterns'].items()
           if any(re.search(pattern,category) for pattern in patterns for category in categories)}
    return sorted(found|{'daily.food'}) if found else []


def capture(archive,directory,policy_path=POLICY):
    archive=h.external(archive);directory=h.external(directory);directory.mkdir(parents=True,exist_ok=True)
    rule=h.replay.read_json(policy_path)
    with h.lock(directory):
        if (directory/'food.json').exists():return verify(directory,policy_path)
        counts=Counter();expanded=0;temporary=directory/'selected.jsonl.partial'
        with gzip.open(archive,'rb') as stream,temporary.open('wb') as output:
            for line in stream:
                expanded+=len(line);h.require(expanded<40*1024**3 and len(line)<64*1024**2,'Oversized raw food source')
                row=json.loads(line);counts['allRecords']+=1
                if row.get('lang_code')=='en':counts['englishRecords']+=1
                selected=topics(row,rule)
                if selected:
                    output.write(line);counts['selectedRecords']+=1
                    counts.update(selected)
                if counts['allRecords']%1000000==0:print(json.dumps(dict(counts)),flush=True)
        h.require(counts['selectedRecords']>0,'No attested English food records')
        temporary.replace(directory/'selected.jsonl')
        notice=directory/'FOOD-SOURCES.txt'
        notice.write_text('Wiktionary contributors, CC BY-SA 4.0 / GFDL. Raw Wiktextract by Tatu Ylonen and contributors.\n'
            +bulk_names.URL+'\nhttps://en.wiktionary.org/wiki/Wiktionary:Copyrights\n'
            'Changes: scan the complete raw source to EOF; retain exact English noun/proper-name records whose '
            'source categories match the published food/drink policy. Preserve source-attested lemma/form links; '
            'no generated dishes, invented spellings, translated names or derived inflections. '
            'Category membership is not a claim that every sense is culinary.\n'
            'Preserve the full CC BY-SA 4.0 / GFDL notices supplied with this dictionary.\n')
        value=dict(schemaVersion=1,complete=True,policy=rule,policySha256=h.replay.sha(policy_path),
            url=bulk_names.URL,rawArchiveSha256=h.replay.sha(archive),expandedBytes=expanded,counts=dict(counts),
            selectedSha256=h.replay.sha(directory/'selected.jsonl'),noticeSha256=h.replay.sha(notice))
        h.dump(directory/'food.json',value);return verify(directory,policy_path)


def verify(directory,policy_path=POLICY):
    directory=h.external(directory);v=h.replay.read_json(directory/'food.json');rule=h.replay.read_json(policy_path)
    h.require(v['schemaVersion']==1 and v['complete'] and v['policy']==rule and v['policySha256']==h.replay.sha(policy_path)
        and h.replay.sha(directory/'selected.jsonl')==v['selectedSha256'] and
        h.replay.sha(directory/'FOOD-SOURCES.txt')==v['noticeSha256'],'Changed/incomplete food capture')
    count=0
    for row in h.json_lines(directory/'selected.jsonl'):
        h.require(topics(row,rule),'Food record outside declared source scope');count+=1
    h.require(count==v['counts']['selectedRecords'],'Incomplete food source rows')
    return v


def collect(directory,policy_path=POLICY):
    directory=h.external(directory);v=verify(directory,policy_path);records={}
    with (directory/'selected.jsonl').open('rb') as stream:
        for line in stream:
            row=json.loads(line);surface=row['word'];selected=topics(row,v['policy'])
            senses=row.get('senses',[]);lemmas={f['word'] for sense in senses for f in sense.get('form_of',[])}
            inflected=bool(senses) and all(s.get('form_of') for s in senses) and len(lemmas)==1
            lemma=next(iter(lemmas)) if inflected else surface
            categories={'noun'}|({'noun_proper'} if row['pos']=='name' else set())|({'phrase'} if ' ' in surface else set())
            if inflected and any('plural' in s.get('tags',[]) for s in senses):categories.add('noun_count_plural')
            item=records.setdefault((surface,lemma),dict(surface=surface,kind='lexical',entity='wiktionary-food:'+surface+'#'+lemma,
                topics=[],proofs=[],attestedSourceEntry=dict(lemma=lemma,categories=sorted(categories),source_ref='wiktextract-food:'+v['rawArchiveSha256']),
                formKind='inflection' if inflected else 'head'))
            item['topics']=sorted(set(item['topics'])|set(selected))
            item['proofs'].append(dict(source='wiktextract_raw_food',url='https://en.wiktionary.org/wiki/'+quote(surface,safe='')+'#English',
                license='CC-BY-SA-4.0',sha256=hashlib.sha256(line).hexdigest(),archiveSha256=v['rawArchiveSha256'],pos=row['pos']))
    notice=directory/'FOOD-SOURCES.txt'
    return sorted(records.values(),key=lambda r:(r['surface'],r['attestedSourceEntry']['lemma'])),v,[
        dict(name=notice.name,path=str(notice),sha256=h.replay.sha(notice))]


def wordnet_records(archive,expected_sha):
    """Read the complete pinned noun graph, including uncategorized Wiktionary dishes."""
    h.require(h.replay.sha(archive)==expected_sha,'Changed WordNet food source')
    with tarfile.open(archive) as source:
        names=source.getnames()
        lexnames=source.extractfile(next(n for n in names if n.endswith('/lexnames'))).read()
        food_id=next(int(line.split()[0]) for line in lexnames.splitlines() if line.split()[1:2]==[b'noun.food'])
        raw=source.extractfile(next(n for n in names if n.endswith('/data.noun'))).read()
    graph={};children={};total=0
    for line in raw.decode('utf-8').splitlines():
        if not line or not line[0].isdigit():continue
        fields=line.split('|',1)[0].split();offset=fields[0];count=int(fields[3],16)
        words=[fields[4+2*i].replace('_',' ') for i in range(count)]
        position=4+count*2;pointers=int(fields[position]);position+=1
        for i in range(pointers):
            symbol,target,pos,_=fields[position+4*i:position+4*i+4]
            if symbol in {'@','@i'} and pos=='n':children.setdefault(target,set()).add(offset)
        graph[offset]=dict(food=int(fields[1])==food_id,words=words);total+=1
    required={'daily.dishes':{'dish','baked goods','confectionery','sauce','condiment'},'daily.beverages':{'beverage'}}
    descendants={}
    for topic,terms in required.items():
        roots={offset for offset,row in graph.items() if row['food'] and set(row['words'])&terms}
        h.require(terms<={w for offset in roots for w in graph[offset]['words']},'Missing WordNet culinary root')
        seen=set(roots);pending=list(roots)
        while pending:
            for child in children.get(pending.pop(),[]):
                if child not in seen:seen.add(child);pending.append(child)
        descendants[topic]=seen
    records=[]
    for offset,row in sorted(graph.items()):
        if not row['food']:continue
        topics=['daily.food']+[topic for topic,ids in descendants.items() if offset in ids]
        for surface in row['words']:
            records.append(dict(surface=surface,kind='lexical',entity='wordnet-food:'+offset+':'+surface,topics=sorted(topics),
                formKind='head',attestedSourceEntry=dict(lemma=surface,categories=['noun']+(['phrase'] if ' ' in surface else []),
                    source_ref='wordnet-3.0:'+offset),proofs=[dict(source='wordnet_food',url='https://wordnet.princeton.edu/',
                        license='WordNet-3.0',sha256=expected_sha,synset=offset,lexicographerFile='noun.food')]))
    return records,dict(complete=True,archiveSha256=expected_sha,nounMemberSha256=hashlib.sha256(raw).hexdigest(),
        nounSynsetsScanned=total,foodSynsets=sum(r['food'] for r in graph.values()),scope=required_to_json(required),
        note='All noun.food headwords; prepared-food and beverage descendants. Source lexical forms, not generated morphology.')


def required_to_json(required):return {k:sorted(v) for k,v in sorted(required.items())}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--source-dir',type=Path,required=True);parser.add_argument('--policy',type=Path,default=POLICY)
    args=parser.parse_args();print(json.dumps(capture(args.archive,args.source_dir,args.policy),ensure_ascii=False))
