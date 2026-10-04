"""Compact schema-4 snapshots. Full pages and model responses remain in the ledger."""
import gzip,json,os,pathlib,sqlite3,time,unicodedata

MAX_BYTES=512*1024*1024

def bound_pair(y,s):
    y=unicodedata.normalize('NFKC',y)
    return ''.join(chr(ord(c)-96) if 'ァ'<=c<='ヶ' else c for c in y),unicodedata.normalize('NFKC',s)

def compact_meaning(raw):
    """Keep factual bindings, not cached article bodies or official-page prose."""
    import hashlib
    b=json.loads(raw)
    for field in ('lead','excerpt'):
        if field in b:
            b[field+'Sha256']=hashlib.sha256(b.pop(field).encode()).hexdigest()
    return b

def precision(db,info,confidence_lower,canonical,active=None):
    unfinished=[dict(r) for r in db.execute("SELECT state,COUNT(*) n FROM candidates WHERE state NOT IN ('reviewed','adopted','excluded_confirmed','not_distributed') GROUP BY state")]
    if unfinished: raise ValueError('Unfinished/failed research: '+canonical(unfinished))
    gold=info(db,'goldFrozen')
    if not gold: raise ValueError('Independent gold validation not frozen')
    stats={'ai':{'correct':0,'n':0},'direct':{'correct':0,'n':0}};eligible=adoptable=0
    by_candidate={}
    for case in gold['cases']:
        if case['split']=='validation': by_candidate.setdefault(case['candidateId'],[]).append(case)
    for cid,cases in by_candidate.items():
        row=db.execute('SELECT * FROM candidates WHERE id=?',(cid,)).fetchone()
        if row is None or not row['decision']: raise ValueError('Gold candidate not reviewed')
        decision=json.loads(row['decision']);predicted=decision.get('roles',[]) if row['state'] in ('reviewed','adopted') else []
        if active is not None: predicted=[v for v in predicted if v['category'] in active]
        expected={(cat,c['target']) for c in cases if c['eligible'] for cat in c['categories']}
        if any(c['eligible'] for c in cases):
            eligible+=1;adoptable+=bool(expected & {(v['category'],v['target']) for v in predicted})
        for role in predicted:
            route=role.get('method',decision['classificationRoute']);s=stats[route];s['n']+=1
            s['correct']+=(role['category'],role['target']) in expected
    ai=stats['ai'];ai['lower95']=confidence_lower(ai['correct'],ai['n'])
    if not ai['n'] or ai['correct']/ai['n']<.995 or ai['lower95']<.99: raise ValueError('AI precision/one-sided confidence gate failed: '+canonical(ai))
    if not eligible or adoptable/eligible<.95: raise ValueError('Verified eligible adoption rate below 95%')
    return {'precision':stats,'eligible':eligible,'adoptable':adoptable,'goldSha256':gold['sha256']}

def active_categories(db,taxonomy):
    counts={c['id']:0 for c in taxonomy['categories']}
    for r in db.execute("SELECT decision FROM candidates WHERE state IN ('reviewed','adopted')"):
        for category in {v['category'] for v in json.loads(r[0])['roles']}: counts[category]+=1
    active=[]
    for c in taxonomy['categories']:
        if c['core'] and counts[c['id']]<max(1,c['minimum']): raise ValueError('Core category below publication floor: '+c['id'])
        if counts[c['id']]>=max(1,c['minimum']): active.append(c['id'])
    return active,counts

def export(db,args,configuration,info,confidence_lower,canonical,digest,sha,emit):
    cfg=configuration(args);active,counts=active_categories(db,cfg[1]);gate=precision(db,info,confidence_lower,canonical,active)
    final=info(db,'finalized')
    if not final and not args.candidate: raise ValueError('Release export requires finalized independent reviews; use --candidate only for local validation')
    dest=pathlib.Path(args.output or 'build/research/export/snapshot.sqlite')
    dest.parent.mkdir(parents=True,exist_ok=True);tmp=dest.with_suffix('.tmp.sqlite')
    if tmp.exists(): tmp.unlink()
    out=sqlite3.connect(tmp)
    out.executescript('''
    CREATE TABLE info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE lookup(surface TEXT PRIMARY KEY,ids TEXT,direct_ids TEXT);
    CREATE TABLE entities(id TEXT PRIMARY KEY,body TEXT);
    CREATE TABLE lexical(reading TEXT,surface TEXT,categories TEXT,evidence TEXT,PRIMARY KEY(reading,surface,categories));
    CREATE TABLE pending(surface TEXT PRIMARY KEY);
    CREATE TABLE resolutions(id TEXT PRIMARY KEY,reading TEXT,surface TEXT,left_id INTEGER,right_id INTEGER,cost INTEGER,status TEXT,categories TEXT,reading_ids TEXT,roles TEXT,reason TEXT,normalization_ids TEXT,exclusion_ids TEXT);
    CREATE TABLE source_map(source TEXT,line INTEGER,candidate_id TEXT,PRIMARY KEY(source,line,candidate_id));
    CREATE INDEX resolution_pair ON resolutions(surface,reading);
    CREATE TABLE reading_facts(id TEXT PRIMARY KEY,reading TEXT,surface TEXT,url TEXT,revision TEXT,sha256 TEXT,target TEXT,body TEXT);
    CREATE TABLE semantic_facts(id TEXT PRIMARY KEY,target TEXT,kind TEXT,url TEXT,revision TEXT,sha256 TEXT,body BLOB);
    CREATE TABLE quality_facts(id TEXT PRIMARY KEY,reading TEXT,surface TEXT,target TEXT,kind TEXT,url TEXT,revision TEXT,sha256 TEXT,body BLOB);
    ''')
    h=__import__('hashlib').sha256();accepted=excluded=non=0;needed=set();semantic_needed=set();quality_needed=set();published_ids=set();omitted_links=0
    try:
        for r in db.execute('SELECT * FROM candidates ORDER BY id'):
            dec=json.loads(r['decision']);roles=[v for v in dec.get('roles',[]) if v['category'] in active];cats=sorted({v['category'] for v in roles})
            state=r['state'];reason=r['reason']
            if state in ('reviewed','adopted'):
                state='adopted' if cats else 'not_distributed';reason='verified-reading-semantics-eligibility' if cats else 'category-publication-criteria-not-met'
            if state=='adopted':
                accepted+=1;published_ids.add(r['id']);needed.update(dec['readingEvidence']);semantic_needed.update(i for v in roles for i in v['evidenceIds'])
            elif state=='excluded_confirmed': excluded+=1
            else: non+=1
            norm=[f[0] for f in db.execute("SELECT id FROM facts WHERE reading=? AND surface=? AND target=? AND kind='normalization' AND active=1 ORDER BY id",(r['reading'],r['surface'],r['id']))] if state=='adopted' else []
            exclusion=dec.get('exclusionEvidence',[]) if state=='excluded_confirmed' else []
            quality_needed.update(norm+exclusion)
            value=(r['id'],r['reading'],r['surface'],r['left_id'],r['right_id'],r['cost'],state,','.join(cats) if state=='adopted' else '',canonical(dec['readingEvidence']) if state=='adopted' else '[]',canonical(roles) if state=='adopted' else '[]',reason,canonical(norm),canonical(exclusion))
            h.update(canonical(value).encode());h.update(b'\n');out.execute('INSERT INTO resolutions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',value)
        proven={}
        for target,raw in db.execute("SELECT target,body FROM facts WHERE active=1 AND kind='normalization'"):
            if target in published_ids:
                b=json.loads(raw)
                if 'originalReading' in b and 'originalSurface' in b: proven.setdefault(target,set()).add(bound_pair(b['originalReading'],b['originalSurface']))
        for r in db.execute('SELECT o.source,o.line,m.candidate_id,o.reading,o.surface,c.reading,c.surface FROM origin_candidates m JOIN origins o ON o.id=m.origin_id JOIN candidates c ON c.id=m.candidate_id ORDER BY o.source,o.line,m.candidate_id'):
            original=bound_pair(r[3],r[4]);output=bound_pair(r[5],r[6])
            if r[2] in published_ids and original!=output and original not in proven.get(r[2],set()):
                # The full original remains in its own resolution. A verified
                # reuse of this output elsewhere cannot validate THIS mapping.
                omitted_links+=1;continue
            out.execute('INSERT INTO source_map VALUES(?,?,?)',tuple(r[:3]))
        for fid in sorted(needed):
            r=db.execute('SELECT f.*,d.url,d.revision,d.sha256 FROM facts f JOIN documents d ON d.id=f.document_id WHERE f.id=?',(fid,)).fetchone()
            if r is None or r['kind']!='reading': raise ValueError('Missing independent reading fact')
            b=json.loads(r['body']);body={k:b[k] for k in ('source','entryId','re_restr','stagk','stagr','nameTypes','sense','row','quotation','line','nameColumns','readingColumns') if k in b}
            out.execute('INSERT INTO reading_facts VALUES(?,?,?,?,?,?,?,?)',(fid,r['reading'],r['surface'],r['url'],r['revision'],r['sha256'],r['target'],canonical(body)))
        for fid in sorted(semantic_needed):
            r=db.execute('SELECT f.*,d.url,d.revision,d.sha256 FROM facts f JOIN documents d ON d.id=f.document_id WHERE f.id=?',(fid,)).fetchone()
            if r is None: raise ValueError('Missing category evidence')
            body=gzip.compress(canonical(compact_meaning(r['body'])).encode(),mtime=0)
            out.execute('INSERT INTO semantic_facts VALUES(?,?,?,?,?,?,?)',(fid,r['target'],r['kind'],r['url'],r['revision'],r['sha256'],body))
        for fid in sorted(quality_needed):
            r=db.execute('SELECT f.*,d.url,d.revision,d.sha256 FROM facts f JOIN documents d ON d.id=f.document_id WHERE f.id=?',(fid,)).fetchone()
            if r is None or r['kind'] not in ('normalization','invalid'): raise ValueError('Missing transformation/exclusion evidence')
            out.execute('INSERT INTO quality_facts VALUES(?,?,?,?,?,?,?,?,?)',(fid,r['reading'],r['surface'],r['target'],r['kind'],r['url'],r['revision'],r['sha256'],gzip.compress(r['body'].encode(),mtime=0)))
        manifest={'schemaVersion':4,'postalParserVersion':7,'sources':info(db,'inputs')['sources'],
            'research':{'releaseReady':bool(final),'sourceRows':db.execute('SELECT COUNT(*) FROM origins').fetchone()[0],
                'candidates':accepted+excluded+non,'adopted':accepted,'excludedConfirmed':excluded,'notDistributed':non,'unprocessed':0,'errors':0,'unprovenDerivedLinksOmitted':omitted_links,
                'resolutionSha256':h.hexdigest(),'configurationSha256':digest(canonical(cfg[-1])),'validation':gate,'acceptance':info(db,'acceptance')},
            'taxonomy':cfg[1],'activeCategories':active,'categoryCounts':counts,'models':cfg[0],
            'baseIdDefSha256':info(db,'baseIdDefSha256')}
        out.execute('INSERT INTO info VALUES(?,?)',('manifest',canonical(manifest)));out.commit();out.execute('VACUUM');out.close()
        if tmp.stat().st_size>MAX_BYTES: raise ValueError('Expanded schema-4 snapshot exceeds 512 MiB')
        os.replace(tmp,dest)
        archive=dest.with_suffix('.sqlite.gz')
        with open(archive,'wb') as stream,gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as f,open(dest,'rb') as source:
            import shutil;shutil.copyfileobj(source,f)
        ah=sha(archive);lock={'schemaVersion':4,'databaseSha256':sha(dest),'archiveSha256':ah,'url':'https://github.com/KazumaProject/kotlin-kana-kanji-converter/releases/download/dictionary-metadata-'+ah[:16]+'/snapshot.sqlite.gz','sources':manifest['sources']}
        dest.with_name('snapshot.lock.json').write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n')
        # Review data preserves non-distribution reasons/semantic roles; normal builds never load full ledger.
        with open(dest.with_name('review.jsonl.gz'),'wb') as stream,gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as z:
            for r in db.execute('SELECT id,old_status,old_categories,state,reason,decision FROM candidates ORDER BY id'):
                z.write((canonical(dict(r))+'\n').encode())
        emit({'snapshot':str(dest),'manifest':manifest,'databaseSha256':lock['databaseSha256'],'archiveSha256':ah})
    finally:
        try: out.close()
        except Exception: pass
        if tmp.exists(): tmp.unlink()

def record_acceptance(db,args,info,sha,canonical,emit,source_text):
    report=json.loads(pathlib.Path(args.acceptance).read_text());required={'reviews','nonDistributionReviews','evaluation','localManifest','linuxManifest','package'}
    if set(report)!=required: raise ValueError('Acceptance file needs review/evaluation/manifest/package artifact paths')
    review=json.loads(pathlib.Path(report['reviews']).read_text());held=json.loads(pathlib.Path(report['nonDistributionReviews']).read_text())
    for kind,cases in [('adopted',review['cases']),('not_distributed',held['cases'])]:
        for case in cases:
            if not case.get('sourceVerified') or not case.get('categoryCorrect') or not case.get('documentId') or not case.get('quotation'): raise ValueError('Review requires independent source inspection and recorded findings')
            doc=db.execute('SELECT * FROM documents WHERE id=?',(case['documentId'],)).fetchone()
            if doc is None or sha(doc['path'])!=doc['sha256'] or case['quotation'] not in source_text(doc['path']): raise ValueError('Review source/quotation invalid')
            row=db.execute('SELECT * FROM candidates WHERE id=?',(case['candidateId'],)).fetchone()
            if row is None or (kind=='not_distributed' and row['state']!='not_distributed'): raise ValueError('Review does not match candidate decision')
            if kind=='adopted' and row['state'] not in ('reviewed','adopted'): raise ValueError('Positive review is not an eligible candidate')
    if len({x['candidateId'] for x in held['cases']})<500: raise ValueError('Need 500 independently checked non-distributed candidates')
    reviewed_ids={x['candidateId'] for x in held['cases']};sample_sources=set();sample_reasons=set()
    for cid in reviewed_ids:
        row=db.execute('SELECT reason FROM candidates WHERE id=?',(cid,)).fetchone();sample_reasons.update(row['reason'].split(';'))
        sample_sources.update(r[0] for r in db.execute('SELECT o.source FROM origins o JOIN origin_candidates m ON m.origin_id=o.id WHERE m.candidate_id=?',(cid,)))
    population_sources={r[0] for r in db.execute("SELECT DISTINCT o.source FROM origins o JOIN origin_candidates m ON m.origin_id=o.id JOIN candidates c ON c.id=m.candidate_id WHERE c.state='not_distributed'")}
    population_reasons={reason for r in db.execute("SELECT DISTINCT reason FROM candidates WHERE state='not_distributed'") for reason in r[0].split(';')}
    if not population_sources<=sample_sources or not population_reasons<=sample_reasons: raise ValueError('Non-distribution review must cover every source and reason group')
    counts={}
    for case in review['cases']:
        row=db.execute('SELECT * FROM candidates WHERE id=?',(case['candidateId'],)).fetchone()
        category=case['category']
        if category not in {v['category'] for v in json.loads(row['decision'])['roles']}: raise ValueError('Review category not assigned to candidate')
        group='old' if row['old_status']=='accepted' and row['old_categories']!='unclassified' else 'new'
        counts.setdefault((category,group),set()).add(row['id'])
    for category in report.get('categories',[]) or json.loads(pathlib.Path(report['localManifest']).read_text())['categories']:
        for group in ('old','new'):
            eligible=0
            for row in db.execute("SELECT old_status,old_categories,decision FROM candidates WHERE state IN ('reviewed','adopted')"):
                old=row['old_status']=='accepted' and row['old_categories']!='unclassified'
                if old==(group=='old') and category in {v['category'] for v in json.loads(row['decision'])['roles']}: eligible+=1
            if len(counts.get((category,group),set()))<min(100,eligible): raise ValueError('Insufficient old/new reviews: '+category+'/'+group)
    ev=json.loads(pathlib.Path(report['evaluation']).read_text())
    ev=ev.get('summary',ev)
    if not ev.get('passed') or ev.get('wordRegressions')!=0 or ev.get('sentenceBestRegressions')!=0 or ev.get('sentenceTop10Regressions')!=0 or ev.get('wordCases',0)<600 or ev.get('sentenceCases',0)<400 or ev.get('extraSentenceCases')!=200: raise ValueError('Regression/natural-context evaluation incomplete')
    local=json.loads(pathlib.Path(report['localManifest']).read_text());linux=json.loads(pathlib.Path(report['linuxManifest']).read_text())
    if local['artifacts']!=linux['artifacts'] or local.get('resolutionSha256')!=linux.get('resolutionSha256'): raise ValueError('Linux binary parity failed')
    import zipfile
    expected={'pos_table.dat'}|{cat+'/'+f for cat in local['categories'] for f in ('yomi.dat','tango.dat','token.dat')}
    if set(local['artifacts'])!=expected: raise ValueError('Incomplete category manifest')
    with zipfile.ZipFile(report['package']) as z:
        packed=json.loads(z.read('manifest.json'))
        notices={'NOTICES.md','LICENSE-JMDICT.html','LICENSE-CC-BY-SA-4.0.txt'}
        if len(z.namelist())!=len(set(z.namelist())) or set(z.namelist())!=expected|notices|{'manifest.json'}: raise ValueError('Unexpected ZIP contents')
        if packed['artifacts']!=local['artifacts']: raise ValueError('ZIP belongs to a different build')
        for name,h in local['artifacts'].items():
            import hashlib
            if hashlib.sha256(z.read(name)).hexdigest()!=h: raise ValueError('ZIP checksum mismatch')
        if set(packed['packageNotices'])!=notices or any(not z.read(name) or hashlib.sha256(z.read(name)).hexdigest()!=packed['packageNotices'][name] for name in notices): raise ValueError('Missing/changed source and license notices')
    record={'categoryReviews':True,'nonDistributedReview':True,'conversionRegression':True,'linuxBinaryParity':True,'zipVerified':True,
            'artifacts':{k:sha(v) for k,v in report.items()},'binaryArtifacts':local['artifacts'],'evaluation':ev,'resolutionSha256':local['resolutionSha256']}
    info(db,'acceptance',record);db.commit();emit(record)
