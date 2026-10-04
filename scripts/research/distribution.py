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

CLASSIFICATION_METHODS=('direct','source_review','ai')
INFERRED_METHODS=('source_review','ai')
DEPENDENCY_FIELDS=('fullAddressEvidence','outputEvidence','prefixEvidence','addressFact','sourceEvidence')

def proof_dependencies(body):
    refs=body.get('componentFacts',[])
    if not isinstance(refs,list): raise ValueError('Invalid proof dependency array')
    refs=refs+[body[key] for key in DEPENDENCY_FIELDS if key in body]
    if any(not isinstance(fid,str) or not fid for fid in refs): raise ValueError('Invalid proof dependency ID')
    return refs

def expand_export_dependencies(db,reading,semantic,quality):
    pending=list(reading|semantic|quality);seen=set()
    while pending:
        fid=pending.pop()
        if fid in seen:continue
        seen.add(fid)
        row=db.execute('SELECT kind,body FROM facts WHERE id=? AND active=1',(fid,)).fetchone()
        if row is None:raise ValueError('Missing export proof dependency: '+fid)
        destinations={'reading':reading,'meaning':semantic,'context':semantic,'normalization':quality,'invalid':quality}
        if row['kind'] not in destinations:raise ValueError('Unsupported export proof kind')
        destinations[row['kind']].add(fid)
        pending.extend(proof_dependencies(json.loads(row['body'])))

def verify_snapshot_dependencies(db):
    ids=set();graph={}
    for table in ('reading_facts','semantic_facts','quality_facts'):
        for fid,raw in db.execute('SELECT id,body FROM '+table):
            if fid in ids:raise ValueError('Duplicate exported proof identity')
            ids.add(fid)
            if isinstance(raw,bytes):raw=gzip.decompress(raw).decode('utf-8')
            refs=proof_dependencies(json.loads(raw))
            if refs:graph[fid]=refs
    if any(ref not in ids for refs in graph.values() for ref in refs):raise ValueError('Missing exported proof dependency')
    checked=set()
    for root in graph:
        path=set();stack=[(root,False)]
        while stack:
            fid,leaving=stack.pop()
            if leaving:path.remove(fid);checked.add(fid);continue
            if fid in path:raise ValueError('Cyclic exported proof dependency')
            if fid in checked:continue
            path.add(fid);stack.append((fid,True));stack.extend((child,False) for child in graph.get(fid,[]))

def classification_method(role,decision):
    # Older decisions put the method on the decision; explicit per-role methods
    # must never be silently relabeled by that fallback.
    route=role['method'] if 'method' in role else decision.get('classificationRoute')
    if route not in CLASSIFICATION_METHODS:
        raise ValueError('Invalid classification method: '+repr(route))
    return route

def require_active_selected_facts(db,candidate_id,decision):
    selected=set(decision.get('readingEvidence',[])+decision.get('normalizationEvidence',[])+decision.get('exclusionEvidence',[]))
    selected.update(fid for role in decision.get('roles',[]) for fid in role.get('evidenceIds',[]))
    checked=set();visiting=set()
    def check(fid):
        if not isinstance(fid,str) or not fid: raise ValueError('Invalid selected evidence dependency: '+candidate_id)
        if fid in visiting: raise ValueError('Cyclic selected evidence dependency: '+candidate_id)
        if fid in checked: return
        fact=db.execute('SELECT kind,body FROM facts WHERE id=? AND active=1',(fid,)).fetchone()
        if fact is None: raise ValueError('Missing/inactive selected evidence: '+candidate_id)
        visiting.add(fid)
        body=json.loads(fact['body']);dependencies=body.get('componentFacts',[])
        if not isinstance(dependencies,list): raise ValueError('Invalid selected evidence dependencies: '+candidate_id)
        dependencies=dependencies+[body[key] for key in ('fullAddressEvidence','outputEvidence','prefixEvidence','addressFact','sourceEvidence') if key in body]
        for dependency in dependencies: check(dependency)
        visiting.remove(fid);checked.add(fid)
    for fid in selected: check(fid)

def bound_role_target(db,role):
    for fid in role.get('evidenceIds',[]):
        fact=db.execute('SELECT target,kind FROM facts WHERE id=? AND active=1',(fid,)).fetchone()
        if fact is not None and fact['target']==role['target'] and fact['kind'] in ('meaning','context'):return True
    return False


def score_targets(by_candidate,observed,stats,active=None,target_bound=None):
    """Gold is keyed by candidate and exact referent/sense, not all homographs.

    Categories judge the meaning. Eligibility additionally judges whether the
    frozen source bundle proved the reading and publication boundary. A later
    reading proof cannot change the meaning label or make an unlabelled target
    part of the original classification sample.
    """
    eligible=adoptable=0;unassessed={route:0 for route in CLASSIFICATION_METHODS}
    for cid,cases in by_candidate.items():
        if cid not in observed:raise ValueError('Gold candidate not reviewed')
        resolved=observed[cid];roles=[role for role,route in resolved]
        eligible_expected={(cat,c['target']) for c in cases if c['eligible'] for cat in c['categories']}
        classified={(cat,c['target']) for c in cases for cat in c['categories']}
        targets={c['target'] for c in cases}
        if any(c['eligible'] for c in cases):
            predicted=roles if active is None else [v for v in roles if v['category'] in active]
            eligible+=1;adoptable+=bool(eligible_expected & {(v['category'],v['target']) for v in predicted})
        for role,route in resolved:
            if role['target'] not in targets:
                if target_bound is None or not target_bound(role):
                    raise ValueError('Unbound predicted target outside the gold sample: '+role['target'])
                unassessed[route]+=1;continue
            s=stats[route];s['n']+=1;s['correct']+=(role['category'],role['target']) in classified
    return eligible,adoptable,unassessed


def precision(db,info,confidence_lower,canonical,active=None):
    unfinished=[dict(r) for r in db.execute("SELECT state,COUNT(*) n FROM candidates WHERE state NOT IN ('reviewed','adopted','excluded_confirmed','not_distributed') GROUP BY state")]
    if unfinished: raise ValueError('Unfinished/failed research: '+canonical(unfinished))
    gold=info(db,'goldFrozen')
    if not gold: raise ValueError('Independent gold validation not frozen')
    stats={route:{'correct':0,'n':0,'population':0} for route in CLASSIFICATION_METHODS}
    by_candidate={};observed={}
    for case in gold['cases']:
        if case['split']=='validation': by_candidate.setdefault(case['candidateId'],[]).append(case)
    # Check the complete decision population, not only gold or published
    # categories: an unsampled inferred route cannot masquerade as zero use.
    for row in db.execute('SELECT id,state,decision FROM candidates'):
        if not row['decision']: raise ValueError('Candidate has no final decision: '+row['id'])
        decision=json.loads(row['decision']);roles=decision.get('roles',[]);resolved=[]
        if row['state'] in ('reviewed','adopted'): require_active_selected_facts(db,row['id'],decision)
        elif row['state']=='excluded_confirmed': require_active_selected_facts(db,row['id'],{'exclusionEvidence':decision.get('exclusionEvidence',[])})
        for role in roles:
            route=classification_method(role,decision);resolved.append((role,route))
            if row['state'] in ('reviewed','adopted'): stats[route]['population']+=1
        if row['id'] in by_candidate:
            observed[row['id']]=resolved if row['state'] in ('reviewed','adopted') else []
    # All sampled targets, including categories below publication floors and
    # known meanings with an originally unproved reading, remain in the score.
    eligible,adoptable,unassessed=score_targets(by_candidate,observed,stats,active,lambda role:bound_role_target(db,role))
    for route in INFERRED_METHODS:
        s=stats[route];s['lower95']=confidence_lower(s['correct'],s['n'])
        if s['population'] and (not s['n'] or s['correct']/s['n']<.995 or s['lower95']<.99):
            raise ValueError(route+' precision/one-sided confidence gate failed: '+canonical(s))
    if not eligible or adoptable/eligible<.95: raise ValueError('Verified eligible adoption rate below 95%')
    report={'precision':stats,'eligible':eligible,'adoptable':adoptable,'goldSha256':gold['sha256'],
        'sampleUnit':'candidateId+target','unassessedTargetsInSelectedCandidates':unassessed}
    verify_precision_report(report,{})
    return report

def verify_precision_report(validation,published_counts):
    """Offline release check, including inferred routes present in exported rows."""
    eligible=validation.get('eligible');adoptable=validation.get('adoptable')
    if type(eligible) is not int or type(adoptable) is not int or not 0<eligible or not 0<=adoptable<=eligible or adoptable/eligible<.95:
        raise ValueError('Adoption coverage gate failed')
    gold=validation.get('goldSha256')
    if not isinstance(gold,str) or len(gold)!=64 or any(c not in '0123456789abcdef' for c in gold):
        raise ValueError('Independent frozen gold checksum missing')
    stats=validation.get('precision',{})
    if set(stats)!=set(CLASSIFICATION_METHODS) or set(published_counts)-set(CLASSIFICATION_METHODS):
        raise ValueError('Invalid classification methods in validation/export')
    for route in CLASSIFICATION_METHODS:
        s=stats[route];n=s.get('n');correct=s.get('correct');population=s.get('population')
        if any(type(v) is not int for v in (n,correct,population)) or not 0<=correct<=n<=population or population<published_counts.get(route,0):
            raise ValueError('Invalid classification population/validation: '+route)
        if route in INFERRED_METHODS and population:
            lower=s.get('lower95')
            if not n or correct/n<.995 or type(lower) not in (int,float) or not .99<=lower<=1:
                raise ValueError(route+' precision/one-sided confidence gate failed')

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
            dec=json.loads(r['decision']);roles=[dict(v,method=classification_method(v,dec)) for v in dec.get('roles',[]) if v['category'] in active];cats=sorted({v['category'] for v in roles})
            state=r['state'];reason=r['reason']
            if state in ('reviewed','adopted'):
                state='adopted' if cats else 'not_distributed';reason='verified-reading-semantics-eligibility' if cats else 'category-publication-criteria-not-met'
            if state=='adopted':
                accepted+=1;published_ids.add(r['id']);needed.update(dec['readingEvidence']);semantic_needed.update(i for v in roles for i in v['evidenceIds'])
            elif state=='excluded_confirmed': excluded+=1
            else: non+=1
            norm=[f[0] for f in db.execute("SELECT id FROM facts WHERE reading=? AND surface=? AND target=? AND kind='normalization' AND active=1 ORDER BY id",(r['reading'],r['surface'],r['id']))] if state=='adopted' else []
            exclusion=dec.get('exclusionEvidence',[]) if state=='excluded_confirmed' else []
            require_active_selected_facts(db,r['id'],{'readingEvidence':dec['readingEvidence'] if state=='adopted' else [],'roles':roles if state=='adopted' else [],'normalizationEvidence':norm,'exclusionEvidence':exclusion})
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
        expand_export_dependencies(db,needed,semantic_needed,quality_needed)
        for fid in sorted(needed):
            r=db.execute('SELECT f.*,d.url,d.revision,d.sha256 FROM facts f JOIN documents d ON d.id=f.document_id WHERE f.id=? AND f.active=1',(fid,)).fetchone()
            if r is None or r['kind']!='reading': raise ValueError('Missing independent reading fact')
            b=json.loads(r['body']);body={k:b[k] for k in ('source','entryId','re_restr','stagk','stagr','nameTypes','sense','row','quotation','line','nameColumns','readingColumns','name','binding','rawReading','rawSurface','readingInfo','spellingInfo','acquisition','componentFacts',*DEPENDENCY_FIELDS) if k in b}
            out.execute('INSERT INTO reading_facts VALUES(?,?,?,?,?,?,?,?)',(fid,r['reading'],r['surface'],r['url'],r['revision'],r['sha256'],r['target'],canonical(body)))
        for fid in sorted(semantic_needed):
            r=db.execute('SELECT f.*,d.url,d.revision,d.sha256 FROM facts f JOIN documents d ON d.id=f.document_id WHERE f.id=? AND f.active=1',(fid,)).fetchone()
            if r is None: raise ValueError('Missing category evidence')
            body=gzip.compress(canonical(compact_meaning(r['body'])).encode(),mtime=0)
            out.execute('INSERT INTO semantic_facts VALUES(?,?,?,?,?,?,?)',(fid,r['target'],r['kind'],r['url'],r['revision'],r['sha256'],body))
        for fid in sorted(quality_needed):
            r=db.execute('SELECT f.*,d.url,d.revision,d.sha256 FROM facts f JOIN documents d ON d.id=f.document_id WHERE f.id=? AND f.active=1',(fid,)).fetchone()
            if r is None or r['kind'] not in ('normalization','invalid'): raise ValueError('Missing transformation/exclusion evidence')
            out.execute('INSERT INTO quality_facts VALUES(?,?,?,?,?,?,?,?,?)',(fid,r['reading'],r['surface'],r['target'],r['kind'],r['url'],r['revision'],r['sha256'],gzip.compress(r['body'].encode(),mtime=0)))
        verify_snapshot_dependencies(out)
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
