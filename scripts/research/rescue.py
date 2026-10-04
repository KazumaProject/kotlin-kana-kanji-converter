"""Recover source-contained components using independently attested readings only."""
import hashlib,itertools,json,re

def targets(db):
    names=set()
    for row in db.execute("SELECT surface FROM origins WHERE source='place' AND (surface LIKE '%(%' OR surface LIKE '%（%' OR surface LIKE '%)%' OR surface LIKE '%）%')"):
        names.update(s for s in re.split('[()（）]',row[0]) if s and not annotation(s))
    return names

def annotation(s):
    return bool(re.fullmatch(r'(?:地下|地上|第)?[0-9０-９一二三四五六七八九十百]+(?:階|丁目|番地)(?:以上|以下)?',s)) or s in ('その他','丁目','番地','区','一部','階層不明','地階・階層不明') or any(t in s for t in ('除く','番地','階層','丁目'))

def apply(db,args,e,insert_candidate,info,emit):
    rescued=0;inputs=info(db,'inputs')['sources'];source_doc=None
    rows=db.execute("SELECT o.* FROM origins o JOIN normalization n ON n.source=o.source AND n.line=o.line WHERE o.source='place' GROUP BY o.id").fetchall()
    for row in rows:
        pieces=[s for s in re.split('[()（）]',row['surface']) if s]
        if not pieces or not any(c in row['surface'] for c in '()（）') or any('以下に掲載がない場合' in s or 'の次に番地がくる場合' in s for s in pieces): continue
        names=[s for s in pieces if not annotation(s)]
        if not names or names[0]!=pieces[0]: continue
        head=names[0]
        repeated=any(head[i:i+n]==head[i+n:i+2*n] for n in range(2,min(24,len(head)//2)+1) for i in range(len(head)-2*n+1))
        if repeated and re.search('(タワー|ビル|スクエア|ハイツ|ヒルズ)$',head): continue
        choices=[]
        for name in names:
            proofs=[dict(f) for f in db.execute("SELECT * FROM facts WHERE surface=? AND kind='reading' AND active=1 ORDER BY reading,id",(name,))]
            unique={f['reading']:f for f in proofs};choices.append(list(unique.values()))
        partial=False
        if any(not c for c in choices):
            prefix=[f for f in choices[0] if row['reading'].startswith(f['reading'])] if choices else []
            if len(prefix)!=1: continue
            names=names[:1];choices=[prefix];partial=True
        matches=[]
        for parts in itertools.product(*choices):
            joined=''.join(f['reading'] for f in parts)
            if joined==row['reading'] or (partial and row['reading'].startswith(joined)) or (all(annotation(s) for s in pieces[len(names):]) and row['reading'].startswith(joined)): matches.append(parts)
            if len(matches)>1: break
        if len(matches)!=1: continue
        if source_doc is None:
            import pathlib
            path=pathlib.Path(args.source_dir)/'place.txt.zip'
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=inputs['place']:
                raise ValueError('Original place input checksum changed; preserve the prepared source before boundary reinspection')
            source_doc=e.save('https://github.com/KazumaProject/kotlin-kana-kanji-converter/blob/c98c1080a665196dde5a73a73c45c1bd3aa793d8/src/main/bin/place.txt.zip',inputs['place'],data,'MozcUT supplementary input; see distribution notices')
        for name,proof in zip(names,matches[0]):
            cid=insert_candidate(db,proof['reading'],name,row['left_id'],row['right_id'],row['cost'],normalization='source-bound-parenthesis-rescue')
            db.execute('INSERT OR IGNORE INTO origin_candidates VALUES(?,?)',(row['id'],cid))
            e.fact(proof['reading'],name,'normalization',[],cid,source_doc,
                {'rule':'independent-components-unique-boundary-v1','source':'place','line':row['line'],'originalSurface':row['surface'],'originalReading':row['reading'],'componentFacts':[f['id'] for f in matches[0]],'components':names,'sourceSha256':inputs['place']})
            rescued+=1
    info(db,'componentRescue',{'mappedComponents':rescued});db.commit();emit({'phase':'componentRescue','mappedComponents':rescued})
