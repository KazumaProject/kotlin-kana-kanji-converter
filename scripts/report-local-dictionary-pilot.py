#!/usr/bin/env python3
"""Read-only pilot progress. An unfinished cohort never produces a full-run ETA."""
import argparse,gzip,hashlib,json,pathlib,sqlite3,time,unicodedata

def pair(y,s):
    y=unicodedata.normalize('NFKC',y)
    return ''.join(chr(ord(c)-96) if 'ァ'<=c<='ヶ' else c for c in y),unicodedata.normalize('NFKC',s)

def capture_bulk_baseline(ledger,destination):
    """Bulk providers are immutable inputs, not discoveries from online research."""
    with sqlite3.connect('file:'+str(ledger.resolve())+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row;cases=[]
        for r in db.execute('SELECT c.* FROM candidates c JOIN pilot p ON p.candidate_id=c.id ORDER BY c.id'):
            y,s=pair(r['reading'],r['surface'])
            facts=db.execute("SELECT id,kind FROM facts WHERE active=1 AND surface=? AND reading=? AND json_extract(body,'$.source') IN ('Mozc','JMdict','JMnedict','Japan Post')",(s,y)).fetchall()
            cases.append({'id':r['id'],'readingEvidenceIds':sorted(f['id'] for f in facts if f['kind']=='reading'),'meaningEvidenceIds':sorted(f['id'] for f in facts if f['kind']=='meaning')})
        if not cases: raise ValueError('Pilot selection has not been prepared')
        receipt=db.execute("SELECT value FROM info WHERE key='bulkComplete'").fetchone()
        if not receipt or not json.loads(receipt[0]): raise ValueError('Mandatory bulk validation incomplete')
        value={'schemaVersion':1,'capturedAt':time.time(),'basis':'Mandatory offline bulk facts only; excludes additional online research. Not independent gold.',
            'bulkReceipt':json.loads(receipt[0]),'pilotIdsSha256':hashlib.sha256('\n'.join(v['id'] for v in cases).encode()).hexdigest(),'cases':cases}
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(gzip.compress(json.dumps(value,ensure_ascii=False,sort_keys=True).encode(),mtime=0))

def report(ledger,baseline):
    base=json.loads(gzip.decompress(baseline.read_bytes()))
    with sqlite3.connect('file:'+str(ledger.resolve())+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute('SELECT c.* FROM candidates c JOIN pilot p ON p.candidate_id=c.id ORDER BY c.id').fetchall()
        ids='\n'.join(r['id'] for r in rows)
        if hashlib.sha256(ids.encode()).hexdigest()!=base['pilotIdsSha256']: raise ValueError('Baseline belongs to another pilot selection')
        old={r['id']:r for r in base['cases']};states={};discovered=[];source_counts={}
        for r in rows:
            states[r['state']]=states.get(r['state'],0)+1
            y,s=pair(r['reading'],r['surface'])
            facts=db.execute("SELECT id,body FROM facts WHERE active=1 AND kind='reading' AND reading=? AND surface=?",(y,s)).fetchall()
            if facts and not old[r['id']]['readingEvidenceIds']:
                discovered.append(r['id'])
                for source in {json.loads(f['body']).get('source','unknown') for f in facts}: source_counts[source]=source_counts.get(source,0)+1
        run=db.execute("SELECT * FROM execution_runs WHERE action='pilot' ORDER BY id DESC LIMIT 1").fetchone()
        calls=[] if not run else db.execute('SELECT role,COUNT(*) calls,SUM(seconds) seconds,SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) errors FROM model_calls WHERE created>=? GROUP BY role',(run['started'],)).fetchall()
        terminal={'reviewed','adopted','excluded_confirmed','not_distributed'}
        finished=bool(rows) and not (set(states)-terminal)
        return {'schemaVersion':1,'source':'local SQLite pilot ledger','pilotCases':len(rows),'states':states,
            'initialBulkReadingConfirmed':sum(bool(v['readingEvidenceIds']) for v in old.values()),
            'additionalReadingDiscovered':len(discovered),'additionalReadingSources':source_counts,
            'elapsedSeconds':None if not run else round((run['ended'] or time.time())-run['started'],2),
            'modelCalls':[dict(r) for r in calls],'historicalRequestErrors':db.execute("SELECT COUNT(*) FROM attempts WHERE result='error'").fetchone()[0],
            'cohortProcessingFinished':finished,'independentClassificationPrecision':None,
            'precisionExplanation':'Requires independent source-verified labels; agreement and previous classifications are not ground truth.',
            'fullRunEstimatedSeconds':None,
            'estimateExplanation':'No extrapolation from an unfinished cohort. Completed cohort still requires source/reading/category strata and resource-time analysis.',
            'countsAreNotReleaseAdoptions':True}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ledger',type=pathlib.Path,default=pathlib.Path('build/research/ledger.sqlite'))
    p.add_argument('--baseline',type=pathlib.Path,default=pathlib.Path('build/research/pilot-bulk-baseline.json.gz'));p.add_argument('--output',type=pathlib.Path)
    p.add_argument('--capture-bulk-baseline',action='store_true')
    args=p.parse_args()
    if args.capture_bulk_baseline:
        if args.baseline.exists(): raise ValueError('Refusing to overwrite frozen baseline; select another path')
        capture_bulk_baseline(args.ledger,args.baseline)
    value=report(args.ledger,args.baseline);text=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if args.output: args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text)
    print(text,end='')

if __name__=='__main__': main()
