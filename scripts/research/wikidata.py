"""Pinned raw Wikidata facts, with name-scoped readings and no alias cross product."""
import json,re,urllib.parse

def values(entity,prop):
    result=[]
    for statement in entity.get('claims',{}).get(prop,[]):
        if statement.get('rank')=='deprecated': continue
        v=statement.get('mainsnak',{}).get('datavalue',{}).get('value')
        if v is not None: result.append((v,statement))
    return result

def fetch(db,args,e,row,round,pair,reading,extract_readings):
    ids=[]
    for f in db.execute("SELECT target,body FROM facts WHERE surface=? AND kind='context' AND active=1 ORDER BY id",(row['surface'],)):
        if re.fullmatch('Q[0-9]+',f['target']):
            b=json.loads(f['body']);kinds=b.get('nameKinds',{}).get(row['surface'],[])
            priority=0 if b.get('directTitle') or b.get('label')==row['surface'] or b.get('title')==row['surface'] or any(k in ('label:ja','title:jawiki') for k in kinds) else 1
            ids.append((priority,f['target']))
    ids=list(dict.fromkeys(qid for _,qid in sorted(ids)))
    if not ids:
        url='https://www.wikidata.org/w/api.php?'+urllib.parse.urlencode({'action':'wbsearchentities','format':'json','language':'ja','search':row['surface'],'limit':3})
        did,data=e.fetch(url,row['id'],round,license='Wikidata CC0')
        result=json.loads(data)
        if 'error' in result or 'search' not in result: raise ValueError('Wikidata search API failure')
        ids=[v['id'] for v in result['search'] if re.fullmatch('Q[0-9]+',v['id'])]
        if not ids: db.execute('INSERT INTO attempts(candidate_id,round,url,result,document_id) VALUES(?,?,?,?,?)',(row['id'],round,url,'empty',did))
    official=[]
    for qid in list(dict.fromkeys(ids))[:3]:
        url='https://www.wikidata.org/w/api.php?'+urllib.parse.urlencode({'action':'wbgetentities','format':'json','ids':qid,'props':'info|labels|aliases|claims|sitelinks'})
        did,data=e.fetch(url,row['id'],round,license='Wikidata CC0')
        result=json.loads(data);entity=result.get('entities',{}).get(qid)
        if not entity: raise ValueError('Wikidata entity response missing requested subject')
        if 'missing' in entity:
            db.execute('INSERT INTO attempts(candidate_id,round,url,result,document_id) VALUES(?,?,?,?,?)',(row['id'],round,url,'empty',did));continue
        revision=str(entity['lastrevid']);db.execute('UPDATE documents SET revision=? WHERE id=?',(revision,did))
        label=entity.get('labels',{}).get('ja',{}).get('value');title=entity.get('sitelinks',{}).get('jawiki',{}).get('title')
        primary={n for n in (label,title) if n};bound={}
        # An unqualified statement describes the subject's primary name. A
        # different article title/alias does not acquire that pronunciation.
        unqualified_names={label} if label else ({title} if title else set())
        unqualified=[]
        for y,statement in values(entity,'P1814'):
            if not isinstance(y,str): continue
            qualifiers=statement.get('qualifiers',{}).get('P5168',[]);names=[]
            for q in qualifiers:
                value=q.get('datavalue',{}).get('value',{})
                if isinstance(value,dict) and value.get('language')=='ja': names.append(value['text'])
            if not qualifiers: unqualified.append(y)
            for name in names or (unqualified_names if not qualifiers else []): bound.setdefault(name,[]).append(y)
        body={'source':'Wikidata','id':qid,'revision':revision,'label':label,'title':title,
              'aliases':[n['value'] for n in entity.get('aliases',{}).get('ja',[])],
              'types':[v['id'] for v,_ in values(entity,'P31') if isinstance(v,dict)],
              'parents':[v['id'] for v,_ in values(entity,'P279') if isinstance(v,dict)],
              'nameBoundReadings':bound,'primaryReadings':unqualified}
        e.fact('',row['surface'],'context',[],qid,did,body)
        for name,ys in bound.items():
            if pair('',name)[1]!=pair('',row['surface'])[1]: continue
            for y in ys:
                if reading(y.replace(' ', '').replace('　',''))==reading(row['reading']):
                    e.fact(row['reading'],row['surface'],'reading',[],qid,did,{'source':'Wikidata','revision':revision,'property':'P1814','name':name,'reading':y,'binding':'qualified-name' if name not in primary else 'primary-name'})
        if row['surface'] in primary and row['surface'] and all('ぁ'<=c<='ゖ' or 'ァ'<=c<='ヶ' or c=='ー' for c in row['surface']) and reading(row['surface'])==reading(row['reading']):
            e.fact(row['reading'],row['surface'],'reading',[],qid,did,{'source':'attested-canonical-kana','name':row['surface'],'binding':'Wikidata primary Japanese name','revision':revision})
        named_subject=row['surface'] in primary or row['surface'] in bound or row['surface'] in body['aliases']
        if named_subject:
            for website,_ in values(entity,'P856'):
                if isinstance(website,str) and website.startswith(('https://','http://')): official.append(website)
    return official
