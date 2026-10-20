"""Deterministic, stdlib-only coordinator for real Codex subagent classifications.

Run: python3 -m scripts.term_semantic --help
No command performs model inference or substitutes heuristic classifications.
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import uuid


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(value).hexdigest()


def stable_id(reading, surface):
    return digest(encoded([reading, surface]).encode())


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(value, encoding='utf-8')
    os.replace(temp, path)


def records(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    rows = []
    with opener(path, 'rt', encoding='utf-8', newline='') as stream:
        for row in csv.reader(stream, delimiter='\t', quoting=csv.QUOTE_NONE):
            if len(row) == 6:
                category, *row = row
                if category != 'term':
                    continue
            if len(row) != 5:
                raise ValueError('Expected category + 5 dictionary fields, or 5 raw fields')
            if not row[0] or not row[4]:
                raise ValueError('Empty reading or surface')
            for value in row[1:4]:
                int(value)
            rows.append(row)
    if not rows:
        raise ValueError('No term records')
    return rows


class ManagedConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

    def __del__(self):
        self.close()


def connect(run):
    db = sqlite3.connect(external_path(run) / 'state.sqlite', timeout=60, factory=ManagedConnection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    columns={r[1] for r in db.execute('PRAGMA table_info(jobs)')}
    if columns and 'lease_token' not in columns:
        db.execute('ALTER TABLE jobs ADD COLUMN lease_token TEXT')
        db.commit()
    if columns:
        db.executescript('CREATE TABLE IF NOT EXISTS result_items(pass TEXT,id TEXT,value TEXT,job_id TEXT,PRIMARY KEY(pass,id)); CREATE TABLE IF NOT EXISTS job_items(stage TEXT,id TEXT,job_id TEXT,PRIMARY KEY(stage,id)); CREATE TABLE IF NOT EXISTS validation_errors(job_id TEXT,created_at REAL,error TEXT); CREATE TABLE IF NOT EXISTS anomalies(job_id TEXT PRIMARY KEY,unknown_count INTEGER,item_count INTEGER,status TEXT);')
        for row in db.execute("SELECT * FROM jobs WHERE NOT EXISTS(SELECT 1 FROM job_items WHERE job_id=jobs.id)").fetchall():
            for i in json.loads(row['ids']): db.execute('INSERT OR IGNORE INTO job_items VALUES(?,?,?)',(row['pass'],i,row['id']))
            if row['status']=='validated':
                for item in json.loads(row['result']): db.execute('INSERT OR REPLACE INTO result_items VALUES(?,?,?,?)',(row['pass'],item['stable_id'],encoded(item),row['id']))
        db.execute('CREATE INDEX IF NOT EXISTS result_items_id ON result_items(id)')
        db.execute('CREATE INDEX IF NOT EXISTS job_items_job ON job_items(job_id)')
        missing_review=[r[0] for r in db.execute("SELECT a.id FROM job_items a LEFT JOIN job_items r ON r.stage='reviewer' AND r.id=a.id WHERE a.stage='adjudicator' AND r.id IS NULL")]
        if missing_review:
            meta=config(run)
            for offset in range(0,len(missing_review),meta['batch_size']):
                add_job(db,'reviewer',missing_review[offset:offset+meta['batch_size']],meta)
        db.commit()
    return db


def config(run):
    return json.loads((Path(run) / 'manifest.json').read_text())


def taxonomy_ids(tax):
    def ids(key):
        return {x['id'] if isinstance(x, dict) else x for x in tax[key]}
    return ids('domains' if 'domains' in tax else 'categories'), ids('tags')


def external_path(value):
    path=Path(value).resolve()
    repo=Path(__file__).resolve().parents[2]
    if path==repo or repo in path.parents:
        raise ValueError('Runtime outputs must be outside repository')
    return path


def prepare(args):
    run = external_path(args.run)
    if run.exists() and any(run.iterdir()):
        raise ValueError('Run directory must be empty; use next/status to resume')
    source = Path(args.source).resolve()
    data = records(source)
    pairs = {stable_id(r[0], r[4]): {'stable_id': stable_id(r[0], r[4]), 'reading': r[0], 'surface': r[4]} for r in data}
    ordered = sorted(pairs, key=lambda i: digest((args.seed + i).encode()))
    uniform = ordered[:min(900, args.pilot_size)]
    readings = collections.Counter(x['reading'] for x in pairs.values())
    surfaces = collections.Counter(x['surface'] for x in pairs.values())
    uniform_set=set(uniform)
    ambiguous = [i for i in ordered if i not in uniform_set and (readings[pairs[i]['reading']] > 1 or surfaces[pairs[i]['surface']] > 1)]
    chosen = uniform + ambiguous[:max(0, args.pilot_size-len(uniform))]
    chosen_set=set(chosen)
    chosen += [i for i in ordered if i not in chosen_set][:max(0,args.pilot_size-len(chosen))]
    if args.full:
        chosen = ordered
    run.mkdir(parents=True, exist_ok=True)
    atomic(run/'source-records.json', encoded(data))
    atomic(run/'pairs.json', encoded(pairs))
    tax = json.loads(Path(args.taxonomy).read_text())
    taxonomy_ids(tax)
    atomic(run/'taxonomy.json', encoded(tax))
    prompts = {}
    for name in ('A','B','reviewer','adjudicator'):
        filename = {'A':'classifier-a','B':'classifier-b'}.get(name,name)
        p = Path(args.prompts) / (filename + '.md')
        common = Path(args.prompts) / 'common.md'
        text = (common.read_text() + '\n\n' if common.exists() else '') + p.read_text()
        prompts[name] = digest(text.encode())
        atomic(run/'prompts'/(name+'.md'), text)
    meta = dict(source_sha256=digest(source.read_bytes()), snapshot_sha256=digest(encoded(data).encode()), records=len(data), pairs=len(pairs), selected=len(chosen), seed=args.seed, full=args.full, taxonomy_sha256=digest(encoded(tax).encode()), prompt_hashes=prompts, batch_size=args.batch_size, created_at=int(time.time()), uniform_ids=uniform, ambiguity_ids=chosen[len(uniform):], selected_ids=sorted(chosen), surface_ambiguity_ids=[i for i,x in pairs.items() if surfaces[x['surface']]>1], models={'A':args.classifier_model,'B':args.classifier_model,'reviewer':args.classifier_model,'adjudicator':args.adjudicator_model})
    if getattr(args,'pair_anchored',True):
        meta.update(pair_anchor_required=True,output_contract='word-pair-v1')
        schema=Path(args.taxonomy).with_name('result.schema.json')
        atomic(run/'result.schema.json',schema.read_text())
        meta['schema_sha256']=digest((run/'result.schema.json').read_bytes())
    atomic(run/'manifest.json', encoded(meta))
    db = connect(run)
    db.executescript('''CREATE TABLE jobs(id TEXT PRIMARY KEY, pass TEXT NOT NULL, ids TEXT NOT NULL, status TEXT NOT NULL, lease_until REAL, lease_token TEXT, attempt INTEGER DEFAULT 0, result TEXT, evidence TEXT, error TEXT); CREATE TABLE finals(id TEXT PRIMARY KEY, value TEXT NOT NULL, origin TEXT NOT NULL);''')
    db.executescript('CREATE TABLE result_items(pass TEXT,id TEXT,value TEXT,job_id TEXT,PRIMARY KEY(pass,id)); CREATE TABLE job_items(stage TEXT,id TEXT,job_id TEXT,PRIMARY KEY(stage,id)); CREATE TABLE validation_errors(job_id TEXT,created_at REAL,error TEXT); CREATE TABLE anomalies(job_id TEXT PRIMARY KEY,unknown_count INTEGER,item_count INTEGER,status TEXT);')
    for offset in range(0,len(chosen),args.batch_size):
        ids = sorted(chosen[offset:offset+args.batch_size])
        for stage in ('A','B'):
            add_job(db, stage, ids, meta)
    db.commit()
    print(encoded({k:v for k,v in meta.items() if not k.endswith('_ids')}))


def job_identity(meta, stage, ids):
    identity=[meta['source_sha256'],meta['taxonomy_sha256'],meta['prompt_hashes'][stage],meta['models'][stage],stage,sorted(ids)]
    if 'output_contract' in meta: identity.append(meta['output_contract'])
    return digest(encoded(identity).encode())


def add_job(db, stage, ids, meta):
    if stage=='adjudicator':
        # An independent Sol audit may discover an unknown meaning even when
        # A/B agreed. Ensure the required Reviewer judgment exists in that case.
        unreviewed=[i for i in ids if not db.execute("SELECT 1 FROM job_items WHERE stage='reviewer' AND id=?",(i,)).fetchone()]
        if unreviewed:
            add_job(db, 'reviewer', unreviewed, meta)
    job_id = job_identity(meta,stage,ids)
    db.execute('INSERT OR IGNORE INTO jobs(id,pass,ids,status) VALUES(?,?,?,?)',(job_id,stage,encoded(sorted(ids)),'pending'))
    for i in ids: db.execute('INSERT OR IGNORE INTO job_items VALUES(?,?,?)',(stage,i,job_id))


def promote(args):
    run=Path(args.run); meta=config(run)
    marker=run/'promotion-pending.json'
    if not marker.exists():
        args.complete=True
        verify(args)
    if meta['full']:
        marker.unlink(missing_ok=True)
        print(encoded({'already_full':True})); return
    pairs=json.loads((run/'pairs.json').read_text())
    db=connect(run)
    existing=set()
    for row in db.execute("SELECT ids FROM jobs WHERE pass='A'"):
        existing.update(json.loads(row['ids']))
    remaining=sorted(set(pairs)-existing,key=lambda i:digest((meta['seed']+i).encode()))
    meta.setdefault('ambiguity_ids',sorted(existing-set(meta.get('uniform_ids',[]))))
    meta.setdefault('pilot_ids',sorted(existing))
    if marker.exists():
        pending=json.loads(marker.read_text())
        if pending['source_sha256']!=meta['source_sha256']: raise ValueError('Promotion source mismatch')
        remaining=pending['remaining_ids']
        meta['batch_size']=pending.get('batch_size',meta['batch_size'])
        if getattr(args,'batch_size',None) not in (None,meta['batch_size']): raise ValueError('Interrupted promotion has a fixed batch size')
    else:
        if getattr(args,'batch_size',None): meta['batch_size']=args.batch_size
        atomic(marker,encoded({'source_sha256':meta['source_sha256'],'remaining_ids':remaining,'batch_size':meta['batch_size']}))
    for offset in range(0,len(remaining),meta['batch_size']):
        for stage in ('A','B'): add_job(db,stage,remaining[offset:offset+meta['batch_size']],meta)
    meta.update(full=True,selected=len(pairs),pilot_selected=meta['selected'],selected_ids=sorted(pairs))
    db.commit()
    atomic(run/'manifest.json',encoded(meta))
    marker.unlink()
    print(encoded({'selected':len(pairs),'reused':len(existing),'added':len(remaining)}))


def extend_pilot(args):
    run=Path(args.run); meta=config(run); target=args.pilot_size
    if meta['full']: raise ValueError('Cannot extend a full run as pilot')
    marker=run/'extension-pending.json'
    if marker.exists():
        pending=json.loads(marker.read_text())
        if pending['target_size']!=target: raise ValueError('Different pilot extension pending')
    else:
        if target<=meta['selected'] or target>meta['pairs']: raise ValueError('Pilot extension must increase selected size within source pairs')
        verify(argparse.Namespace(run=args.run,complete=True))
        pending={'target_size':target,'previous_size':meta['selected'],'source_sha256':meta['source_sha256']}
        atomic(marker,encoded(pending))
    if pending['source_sha256']!=meta['source_sha256']: raise ValueError('Extension source changed')
    pairs=json.loads((run/'pairs.json').read_text()); ordered=sorted(pairs,key=lambda i:digest((meta['seed']+i).encode()))
    uniform=ordered[:min(900,target)]; used=set(uniform)
    rc=collections.Counter(x['reading'] for x in pairs.values()); sc=collections.Counter(x['surface'] for x in pairs.values())
    extra=[i for i in ordered if i not in used and (rc[pairs[i]['reading']]>1 or sc[pairs[i]['surface']]>1)]
    selected=uniform+extra[:max(0,target-len(uniform))]; used=set(selected)
    selected+=[i for i in ordered if i not in used][:max(0,target-len(selected))]
    db=connect(run)
    existing={r['id'] for r in db.execute("SELECT id FROM job_items WHERE stage='A'")}
    if not existing<=set(selected): raise ValueError('Previous sample is not subset of extension')
    audit_path=run/'audit-selection.json'
    if audit_path.exists():
        archive=run/'audit-history'/('selected-'+str(pending['previous_size'])+'.json')
        immutable_artifact(archive,audit_path.read_text()); audit_path.unlink()
    remaining=[i for i in selected if i not in existing]
    db.execute('BEGIN IMMEDIATE')
    for offset in range(0,len(remaining),meta['batch_size']):
        for stage in ('A','B'): add_job(db,stage,remaining[offset:offset+meta['batch_size']],meta)
    db.commit()
    meta.update(selected=target,selected_ids=sorted(selected),uniform_ids=uniform,ambiguity_ids=selected[len(uniform):])
    atomic(run/'manifest.json',encoded(meta)); marker.unlink()
    print(encoded({'selected':target,'reused':len(existing),'added':len(remaining)}))


def audit(args):
    run=Path(args.run); meta=config(run); db=connect(run)
    if args.size<1: raise ValueError('Audit size must be positive')
    path=run/'audit-selection.json'
    if path.exists():
        selection=json.loads(path.read_text())
        if selection['requested_size']!=args.size: raise ValueError('Audit selection already fixed with another size')
    else:
        values={row['id']:json.loads(row['value']) for row in db.execute('SELECT id,value FROM finals')}
        if len(values)!=meta['selected']: raise ValueError('Initial classifications must be complete before audit selection')
        count=min(args.size,len(values)); ordered=sorted(values,key=lambda i:digest(('audit-v1'+meta['seed']+i).encode()))
        uniform=ordered[:count//2]; excluded=set(uniform)
        cells=collections.defaultdict(list)
        for i in ordered:
            if i not in excluded:
                item=values[i]; cells[(item['final_category'],item['usage_class'],item['agreement_status'])].append(i)
        stratified=[]; membership={}
        while len(stratified)<count-len(uniform):
            advanced=False
            for cell in sorted(cells):
                if cells[cell] and len(stratified)<count-len(uniform):
                    i=cells[cell].pop(0); stratified.append(i); membership[i]=list(cell); advanced=True
            if not advanced: break
        selection={'requested_size':args.size,'source_sha256':meta['source_sha256'],'seed':meta['seed'],'uniform_ids':uniform,'stratified_ids':stratified,'strata':membership}
        atomic(path,encoded(selection))
    ids=selection['uniform_ids']+selection['stratified_ids']
    outstanding=[i for i in ids if not db.execute("SELECT 1 FROM job_items WHERE stage='adjudicator' AND id=?",(i,)).fetchone()]
    for offset in range(0,len(outstanding),meta['batch_size']): add_job(db,'adjudicator',outstanding[offset:offset+meta['batch_size']],meta)
    db.commit()
    print(encoded({'audit_selected':len(ids),'newly_scheduled':len(outstanding),'selection':str(path)}))


def acknowledge_anomaly(args):
    note=args.note.strip()
    if len(note)<10: raise ValueError('Concrete inspection note is required (minimum 10 characters)')
    db=connect(args.run)
    row=db.execute('SELECT * FROM anomalies WHERE job_id=?',(args.job,)).fetchone()
    if not row: raise ValueError('Unknown anomaly')
    evidence=json.loads(Path(args.evidence).read_text())
    if evidence.get('model')!=config(args.run)['models']['adjudicator'] or not evidence.get('agent_id'): raise ValueError('Sol inspection evidence required')
    directory=Path(args.run)/'anomaly-inspections'; target=directory/(args.job+'.json')
    value={'job_id':args.job,'note':note,'evidence':evidence}
    if target.exists() and json.loads(target.read_text())!=value: raise ValueError('Inspection history is immutable')
    atomic(target,encoded(value))
    db.execute("UPDATE anomalies SET status='inspected_by_sol' WHERE job_id=?",(args.job,)); db.commit()
    print(encoded({'acknowledged':args.job}))


def review_all(args):
    run=Path(args.run);meta=config(run);meta.update(review_all=True,adjudicate_disagreements=True)
    atomic(run/'manifest.json',encoded(meta))
    with connect(run) as db:
        ids=[r['id'] for r in db.execute("SELECT id FROM result_items WHERE pass='A'")]
        before=db.execute("SELECT count(*) FROM job_items WHERE stage='reviewer'").fetchone()[0]
        sol_before=db.execute("SELECT count(*) FROM job_items WHERE stage='adjudicator'").fetchone()[0]
        reconcile(db,meta,ids)
        after=db.execute("SELECT count(*) FROM job_items WHERE stage='reviewer'").fetchone()[0]
        sol_after=db.execute("SELECT count(*) FROM job_items WHERE stage='adjudicator'").fetchone()[0]
    print(encoded({'review_all':True,'adjudicate_disagreements':True,'newly_scheduled_words':after-before,'newly_scheduled_adjudications':sol_after-sol_before}))


def compact_pending(db, stage, meta):
    """Batch unstarted reviews; never discard a call, lease or accepted history."""
    if stage not in ('reviewer','adjudicator'):
        return
    pending=db.execute("SELECT id,ids FROM jobs WHERE pass=? AND status='pending' AND attempt=0",(stage,)).fetchall()
    if len(pending)<2:
        return
    ids=sorted({i for row in pending for i in json.loads(row['ids'])})
    if len(pending)==(len(ids)+meta['batch_size']-1)//meta['batch_size']:
        return
    for row in pending:
        db.execute('DELETE FROM job_items WHERE job_id=?',(row['id'],))
        db.execute('DELETE FROM jobs WHERE id=?',(row['id'],))
    for offset in range(0,len(ids),meta['batch_size']):
        add_job(db,stage,ids[offset:offset+meta['batch_size']],meta)


def next_job(args):
    db = connect(args.run)
    db.execute('BEGIN IMMEDIATE')
    now = time.time()
    lease_token = uuid.uuid4().hex
    db.execute("UPDATE jobs SET status='pending' WHERE status='leased' AND lease_until < ?",(now,))
    compact_pending(db,args.stage,config(args.run))
    stage = ' AND pass=?' if args.stage else ''
    row = db.execute("SELECT * FROM jobs WHERE status='pending'"+stage+" AND (pass!='adjudicator' OR NOT EXISTS(SELECT 1 FROM job_items ji LEFT JOIN result_items ri ON ri.pass='reviewer' AND ri.id=ji.id WHERE ji.stage='adjudicator' AND ji.job_id=jobs.id AND ri.id IS NULL)) ORDER BY CASE pass WHEN 'A' THEN 0 WHEN 'B' THEN 1 WHEN 'reviewer' THEN 2 ELSE 3 END,ids LIMIT 1", (args.stage,) if args.stage else ()).fetchone()
    if not row:
        db.commit(); print(encoded({'job':None})); return
    db.execute("UPDATE jobs SET status='leased',lease_until=?,lease_token=?,attempt=attempt+1 WHERE id=?",(now+args.lease_seconds,lease_token,row['id']))
    db.commit()
    pairs=json.loads((Path(args.run)/'pairs.json').read_text())
    payload={'batch_id':row['id'],'classification_pass':row['pass'],'lease_token':lease_token,'items':[pairs[i] for i in json.loads(row['ids'])]}
    anchored=config(args.run).get('pair_anchor_required',False)
    if row['pass'] in ('reviewer','adjudicator') and not anchored:
        candidates={}
        for i in json.loads(row['ids']):
            for prior in db.execute('SELECT pass,value FROM result_items WHERE id=?',(i,)):
                item=json.loads(prior['value'])
                candidates.setdefault(i,[]).append({'pass':prior['pass'],'result':{k:item[k] for k in FIELDS-{'stable_id','reading','surface'}}})
        payload['candidate_results']=candidates
    path=Path(args.run)/'jobs'/row['id']/'attempts'/str(row['attempt']+1)/'input.json'
    atomic(path,encoded(payload))
    independent=path.with_name('independent-input.json')
    atomic(independent,encoded({k:v for k,v in payload.items() if k!='candidate_results'}))
    print(encoded({'job':row['id'],'pass':row['pass'],'model':config(args.run)['models'][row['pass']],'lease_token':lease_token,'input':str(path),'prompt':str(Path(args.run)/'prompts'/(row['pass']+'.md')),'independent_input':str(independent),'taxonomy':str(Path(args.run)/'taxonomy.json'),'schema':str(Path(args.run)/'result.schema.json') if anchored else str(Path(__file__).resolve().parents[2]/'src/main/classification/term-semantic/result.schema.json'),'draft_fields':DRAFT_FIELDS,'draft_format':'Prefer compact JSON {fields: draft_fields, rows: literal rows}; emit expands the result JSONL. Explicitly author reading/surface and every semantic field in each row. Omit derived stable_id. Do not fill semantic defaults with code.','decisions':str(path.with_name('decisions.json')),'independent_decisions':str(path.with_name('independent-decisions.json')),'independent_output':str(path.with_name('independent-output.jsonl')),'candidate_input':str(path.with_name('candidate-input.json')),'output':str(path.with_name('output.jsonl'))}))


def attempt_directory(run, job):
    return Path(run)/'jobs'/job['id']/'attempts'/str(job['attempt'])


def immutable_artifact(path, text):
    if path.exists():
        if path.read_text()!=text: raise ValueError('Cannot alter accepted artifact: '+str(path))
    else: atomic(path,text)


def parse_decisions(path):
    raw=Path(path).read_text()
    try: parsed=json.loads(raw)
    except json.JSONDecodeError: return [json.loads(line) for line in raw.splitlines() if line.strip()]
    if isinstance(parsed,dict) and set(parsed)=={'fields','rows'}:
        fields=parsed['fields']
        if not isinstance(fields,list) or len(fields)!=len(set(fields)): raise ValueError('Duplicate compact fields')
        rows=parsed['rows']
        if not isinstance(rows,list) or any(not isinstance(row,list) or len(row)!=len(fields) for row in rows): raise ValueError('Malformed compact decisions')
        return [dict(zip(fields,row)) for row in rows]
    if isinstance(parsed,list): return parsed
    if isinstance(parsed,dict) and set(parsed)=={'results'}: return parsed['results']
    return [parsed]


def check_proof(run, job, proof_path, independent=False, context=None):
    context=context or {'meta':config(run),'pairs':json.loads((Path(run)/'pairs.json').read_text()),'taxonomy':json.loads((Path(run)/'taxonomy.json').read_text())}
    meta=context['meta']; proof_path=Path(proof_path); proof=json.loads(proof_path.read_text())
    directory=attempt_directory(run,job)
    prefix='independent-' if independent else ''
    output=directory/(prefix+'output.jsonl')
    expected={'contract':meta['output_contract'],'job':job['id'],'lease_token':job['lease_token'],'input_sha256':digest((directory/'independent-input.json').read_bytes()),'output_sha256':digest(output.read_bytes())}
    if any(proof.get(k)!=v for k,v in expected.items()) or proof_path.resolve()!=(directory/(prefix+'emit-proof.json')).resolve(): raise ValueError('Invalid pair-anchor proof')
    authored=Path(proof['authored_path'])
    if digest(authored.read_bytes())!=proof['decisions_sha256']: raise ValueError('Authored decisions changed')
    items=parse_decisions(authored)
    anchored=[]
    for item in items:
        if not isinstance(item,dict) or not {'reading','surface'}<=set(item): raise ValueError('Every authored decision requires reading and surface')
        item=dict(item); computed=stable_id(item['reading'],item['surface'])
        if item.get('stable_id',computed)!=computed: raise ValueError('Authored stable_id/pair mismatch')
        item['stable_id']=computed; anchored.append(item)
    validate(anchored,json.loads(job['ids']),context['pairs'],context['taxonomy'])
    wanted=''.join(encoded(item)+'\n' for item in sorted(anchored,key=lambda x:x['stable_id']))
    if output.read_text()!=wanted: raise ValueError('Output differs from authored pair decisions')
    return proof


def emit(args):
    try:
        return _emit(args)
    except (ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        with connect(args.run) as db:
            db.execute('INSERT INTO validation_errors VALUES(?,?,?)',
                       (args.job,time.time(),encoded({'phase':'emit','independent':getattr(args,'independent',False),'error':str(exc)})))
        raise


def _emit(args):
    meta=config(args.run)
    if not meta.get('pair_anchor_required'): raise ValueError('Emit requires a pair-anchored run')
    with connect(args.run) as db:
        job=db.execute('SELECT * FROM jobs WHERE id=?',(args.job,)).fetchone()
        if not job or job['status'] not in ('leased','validated'): raise ValueError('Job must be leased')
        directory=attempt_directory(args.run,job); independent=getattr(args,'independent',False)
        if independent and job['pass'] not in ('reviewer','adjudicator'): raise ValueError('Independent emit is only for review passes')
        items=parse_decisions(args.decisions); anchored=[]
        for original in items:
            if not isinstance(original,dict) or not {'reading','surface'}<=set(original): raise ValueError('Every authored decision requires reading and surface')
            item=dict(original); computed=stable_id(item['reading'],item['surface'])
            if item.get('stable_id',computed)!=computed: raise ValueError('Authored stable_id/pair mismatch')
            item['stable_id']=computed; anchored.append(item)
        validate(anchored,json.loads(job['ids']),json.loads((Path(args.run)/'pairs.json').read_text()),json.loads((Path(args.run)/'taxonomy.json').read_text()))
        prefix='independent-' if independent else ''
        output=directory/(prefix+'output.jsonl'); proof_path=directory/(prefix+'emit-proof.json')
        text=''.join(encoded(item)+'\n' for item in sorted(anchored,key=lambda x:x['stable_id']))
        proof={'contract':meta['output_contract'],'job':job['id'],'lease_token':job['lease_token'],'input_sha256':digest((directory/'independent-input.json').read_bytes()),'authored_path':str(Path(args.decisions).resolve()),'decisions_sha256':digest(Path(args.decisions).read_bytes()),'output_sha256':digest(text.encode())}
        if job['status']=='validated' and (not output.exists() or not proof_path.exists()): raise ValueError('Cannot create artifacts for accepted history')
        immutable_artifact(output,text); immutable_artifact(proof_path,encoded(proof)+'\n')
        print(encoded({'output':str(output),'proof':str(proof_path)}))


def reveal(args):
    if not config(args.run).get('pair_anchor_required'): raise ValueError('Reveal requires a pair-anchored run')
    with connect(args.run) as db:
        job=db.execute('SELECT * FROM jobs WHERE id=?',(args.job,)).fetchone()
        if not job or job['pass'] not in ('reviewer','adjudicator') or job['status'] not in ('leased','validated'): raise ValueError('Reveal is only for leased review passes')
        directory=attempt_directory(args.run,job); proof_path=directory/'independent-emit-proof.json'
        proof=check_proof(args.run,job,proof_path,True)
        seal={'job':job['id'],'independent_proof_sha256':digest(proof_path.read_bytes()),'independent_output_sha256':proof['output_sha256']}
        immutable_artifact(directory/'independent-seal.json',encoded(seal)+'\n')
        payload=json.loads((directory/'independent-input.json').read_text()); candidates={}
        for i in json.loads(job['ids']):
            for prior in db.execute('SELECT pass,value FROM result_items WHERE id=?',(i,)):
                if prior['pass']==job['pass']: continue
                item=json.loads(prior['value'])
                candidates.setdefault(i,[]).append({'pass':prior['pass'],'result':{k:item[k] for k in FIELDS-{'stable_id','reading','surface'}}})
        payload['candidate_results']=candidates
        target=directory/'candidate-input.json'; immutable_artifact(target,encoded(payload))
        print(encoded({'candidate_input':str(target),'independent_seal':str(directory/'independent-seal.json')}))


def anchor_evidence(run,job,output=None,context=None):
    context=context or {'meta':config(run),'pairs':json.loads((Path(run)/'pairs.json').read_text()),'taxonomy':json.loads((Path(run)/'taxonomy.json').read_text())}
    directory=attempt_directory(run,job)
    proof_path=directory/'emit-proof.json'; proof=check_proof(run,job,proof_path,context=context)
    if output is not None and Path(output).resolve()!=(directory/'output.jsonl').resolve(): raise ValueError('Ingest requires assigned emitted output')
    evidence={'emit_proof':str(proof_path),'emit_proof_sha256':digest(proof_path.read_bytes()),'input_sha256':proof['input_sha256'],'output_sha256':proof['output_sha256']}
    if job['pass'] in ('reviewer','adjudicator'):
        independent=directory/'independent-emit-proof.json'; check_proof(run,job,independent,True,context=context)
        seal_path=directory/'independent-seal.json'; seal=json.loads(seal_path.read_text())
        if seal.get('job')!=job['id'] or seal.get('independent_proof_sha256')!=digest(independent.read_bytes()) or seal.get('independent_output_sha256')!=digest((directory/'independent-output.jsonl').read_bytes()): raise ValueError('Independent judgment seal changed')
        if not (directory/'candidate-input.json').exists(): raise ValueError('Review reveal missing')
        evidence.update(independent_proof_sha256=digest(independent.read_bytes()),independent_seal_sha256=digest(seal_path.read_bytes()))
    return evidence


DRAFT_FIELDS=['reading','surface','usage_class','primary_domain','alternative_domains','tags','ambiguous','needs_review','short_reason','final_category','uncertain_tags','ambiguity_types','context_required']
FIELDS=set(DRAFT_FIELDS)|{'stable_id'}
UNKNOWN={'term_unknown','term_unresolved_abbreviation'}


def validate(items, ids, pairs, tax):
    if not isinstance(items, list) or not items:
        raise ValueError('Results must be a nonempty array or JSONL objects')
    seen = set()
    errors = []
    for index, item in enumerate(items):
        try:
            if not isinstance(item, dict) or not isinstance(item.get('stable_id'), str):
                raise ValueError('Result must be an object with string stable_id')
            ident = item['stable_id']
            if ident not in ids or ident in seen:
                raise ValueError('Unknown or duplicate stable_id')
            seen.add(ident)
            _validate([item], [ident], pairs, tax)
        except (ValueError, TypeError, KeyError) as exc:
            errors.append({'index': index, 'error': str(exc),
                           'primary_domain': item.get('primary_domain') if isinstance(item, dict) else None,
                           'final_category': item.get('final_category') if isinstance(item, dict) else None})
    if seen != set(ids):
        errors.append({'error': 'Missing IDs', 'count': len(set(ids)-seen)})
    if errors:
        raise ValueError(encoded({'validation_errors': errors}))


def _validate(items, ids, pairs, tax):
    domains,tags=taxonomy_ids(tax)
    seen=set()
    for item in items:
        if not isinstance(item,dict) or FIELDS-set(item): raise ValueError('Missing required fields')
        if set(item)-FIELDS-{'model','prompt_version','classification_pass','batch_id','agreement_status','agent_id','call_id'}: raise ValueError('Unknown result fields')
        i=item['stable_id']
        if i not in ids or i in seen: raise ValueError('Unknown or duplicate stable_id')
        seen.add(i)
        if any(item[k]!=pairs[i][k] for k in ('reading','surface')): raise ValueError('Reading/surface changed')
        if item['usage_class'] not in ('general','technical','mixed','uncertain'): raise ValueError('Invalid usage')
        if item['primary_domain'] is not None and item['primary_domain'] not in domains: raise ValueError('Unknown domain')
        for key,allowed in [('alternative_domains',domains),('tags',tags),('uncertain_tags',tags)]:
            value=item.get(key,[])
            if not isinstance(value,list) or any(not isinstance(x,str) for x in value) or len(set(value))!=len(value) or not set(value)<=allowed: raise ValueError('Invalid '+key)
        if set(item.get('uncertain_tags',[])) & set(item['tags']): raise ValueError('Contradictory tags')
        if not isinstance(item['ambiguity_types'],list) or any(not isinstance(x,str) for x in item['ambiguity_types']) or len(set(item['ambiguity_types']))!=len(item['ambiguity_types']) or not set(item['ambiguity_types']) <= {'polysemy','unresolved_abbreviation','reading_surface_mismatch','unknown_meaning','domain_boundary'}: raise ValueError('Invalid ambiguity_types')
        for key in ('ambiguous','needs_review','context_required'):
            if type(item[key]) is not bool: raise ValueError('Invalid boolean')
        if not isinstance(item['short_reason'],str) or not item['short_reason'].strip() or len(item['short_reason'])>160: raise ValueError('Invalid short reason')
        if item['final_category'] not in domains|{c['id'] for c in tax.get('additional_categories',[])}: raise ValueError('Unregistered final category')
        if item['final_category'] in domains and item['primary_domain'] != item['final_category']: raise ValueError('Primary/final domain mismatch')
        if item['final_category']=='term_multidomain' and len(item['alternative_domains'])<2: raise ValueError('Multiple domains requires alternatives')
        if item['final_category'] in UNKNOWN and (item['primary_domain'] is not None or not item['needs_review']): raise ValueError('Unknown requires null primary and needs_review')
        if item['final_category']=='term_multidomain' and (item['primary_domain'] is not None or not item['ambiguous'] or not item['context_required']): raise ValueError('Multidomain requires null primary, ambiguity and context')
    if seen != set(ids): raise ValueError('Missing IDs')


def semantic(item):
    value={k:item.get(k) for k in ('usage_class','primary_domain','alternative_domains','tags','uncertain_tags','ambiguous','needs_review','final_category','context_required','ambiguity_types')}
    for k in ('alternative_domains','tags','uncertain_tags','ambiguity_types'): value[k]=sorted(value[k] or [])
    return encoded(value)


def unknown(item):
    return item.get('final_category') in UNKNOWN


def high_risk(item):
    return (unknown(item) or item['needs_review'] or item['ambiguous']
            or item['context_required'] or item['usage_class']=='uncertain'
            or bool(item['alternative_domains'] or item['uncertain_tags'] or item['ambiguity_types'])
            or 'term_tag_abbreviations' in item['tags'])


def reviewer_requires_sol(a,b,reviewed,all_disagreements=False):
    core=lambda item:(item['usage_class'],item['primary_domain'])
    return ((all_disagreements and semantic(a)!=semantic(b))
            or reviewed['needs_review'] or unknown(reviewed)
            or (core(a)==core(b) and core(reviewed)!=core(a))
            or reviewed['primary_domain'] not in (a['primary_domain'],b['primary_domain']))


def reconcile(db, meta, affected):
    surface_ambiguity=set(meta.get('surface_ambiguity_ids',[]))
    passes=collections.defaultdict(dict)
    for i in affected:
        for row in db.execute('SELECT * FROM result_items WHERE id=?',(i,)):
            passes[row['pass']][i]=(json.loads(row['value']),row['job_id'])
    pending=collections.defaultdict(list)
    for i in sorted(set(passes['A'])&set(passes['B'])):
        db.execute('DELETE FROM finals WHERE id=?',(i,))
        a,origin=passes['A'][i]; b,_=passes['B'][i]
        if i in passes['adjudicator']:
            final,origin=passes['adjudicator'][i]
        elif int(i[:8],16)%100==0 and semantic(a)==semantic(b) and not unknown(a) and not a['needs_review']:
            pending['adjudicator'].append(i); continue
        elif i in passes['reviewer']:
            final,origin=passes['reviewer'][i]
            if reviewer_requires_sol(a,b,final,meta.get('adjudicate_disagreements',False)): pending['adjudicator'].append(i); continue
        elif meta.get('review_all') or semantic(a)!=semantic(b) or high_risk(a) or high_risk(b) or i in surface_ambiguity or int(i[:8],16)%10==0:
            pending['reviewer'].append(i); continue
        else:
            final=a
        final=dict(final)
        final.setdefault('final_category',final['primary_domain'] or 'term_unknown')
        final['agreement_status']='agree' if semantic(a)==semantic(b) else 'disagree'
        db.execute('INSERT OR REPLACE INTO finals VALUES(?,?,?)',(i,encoded(final),origin))
    for stage,ids in pending.items():
        ids=[i for i in ids if not db.execute('SELECT 1 FROM job_items WHERE stage=? AND id=?',(stage,i)).fetchone()]
        for offset in range(0,len(ids),meta['batch_size']): add_job(db,stage,ids[offset:offset+meta['batch_size']],meta)


def ingest(args):
    try:
        return _ingest(args)
    except (ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        db=connect(args.run)
        db.execute('INSERT INTO validation_errors VALUES(?,?,?)',(args.job,time.time(),str(exc)))
        db.execute('UPDATE jobs SET error=? WHERE id=?',(str(exc),args.job)); db.commit()
        raise


def _ingest(args):
    with connect(args.run) as db:
        db.execute('BEGIN IMMEDIATE')
        return _ingest_transaction(db,args)


def _ingest_transaction(db,args):
    row=db.execute('SELECT * FROM jobs WHERE id=?',(args.job,)).fetchone()
    if row is None: raise ValueError('Unknown job')
    raw=Path(args.output).read_text()
    try:
        parsed=json.loads(raw)
        items=parsed if isinstance(parsed,list) else parsed.get('results',[parsed]) if isinstance(parsed,dict) else [parsed]
    except json.JSONDecodeError:
        items=[json.loads(line) for line in raw.splitlines() if line.strip()]
    pairs=json.loads((Path(args.run)/'pairs.json').read_text()); tax=json.loads((Path(args.run)/'taxonomy.json').read_text()); meta=config(args.run)
    validate(items,json.loads(row['ids']),pairs,tax)
    evidence=json.loads(Path(args.evidence).read_text())
    if meta.get('pair_anchor_required'):
        anchor=anchor_evidence(args.run,row,args.output)
        if any(evidence.get(k)!=v for k,v in anchor.items()): raise ValueError('Attestation lacks pair-anchor proof hashes')
    if row['status']!='validated' and (row['status']!='leased' or not row['lease_token'] or evidence.get('lease_token')!=row['lease_token']): raise ValueError('Stale or missing lease token')
    if evidence.get('model')!=meta['models'][row['pass']] or not evidence.get('agent_id'): raise ValueError('Actual model and agent_id evidence required')
    for item in items:
        item.update(agent_id=evidence['agent_id'],call_id=evidence.get('call_id',evidence['agent_id']),model=evidence['model'],prompt_version=meta['prompt_hashes'][row['pass']],classification_pass=row['pass'],batch_id=row['id'])
    value=encoded(sorted(items,key=lambda x:x['stable_id']))
    if row['status']=='validated' and row['result']!=value: raise ValueError('Cannot overwrite validated result')
    db.execute("UPDATE jobs SET status='validated',result=?,evidence=?,lease_until=NULL,error=NULL WHERE id=?",(value,encoded(evidence),args.job))
    for item in items: db.execute('INSERT OR REPLACE INTO result_items VALUES(?,?,?,?)',(row['pass'],item['stable_id'],encoded(item),args.job))
    unknown_count=sum(unknown(item) for item in items)
    if unknown_count/len(items)>0.2: db.execute('INSERT OR REPLACE INTO anomalies VALUES(?,?,?,?)',(args.job,unknown_count,len(items),'requires_sol_inspection'))
    reconcile(db,meta,[item['stable_id'] for item in items]); db.commit(); print(encoded({'validated':len(items)}))


def status(args):
    db=connect(args.run)
    print(encoded({'manifest':{k:v for k,v in config(args.run).items() if not k.endswith('_ids')},'jobs':[dict(x) for x in db.execute('SELECT pass,status,count(*) AS count FROM jobs GROUP BY pass,status')],'validation_errors':db.execute('SELECT count(*) FROM validation_errors').fetchone()[0],'unknown_anomalies':db.execute('SELECT count(*) FROM anomalies').fetchone()[0],'finalized':db.execute('SELECT count(*) FROM finals').fetchone()[0], 'complete':db.execute('SELECT count(*) FROM finals').fetchone()[0]==config(args.run)['selected'] and not db.execute("SELECT 1 FROM jobs WHERE status!='validated' LIMIT 1").fetchone() and not db.execute("SELECT 1 FROM anomalies WHERE status!='inspected_by_sol' LIMIT 1").fetchone()}))


def verify(args):
    with connect(args.run) as db:
        db.execute('BEGIN')
        return _verify(db,args)


def _verify(db,args):
    run=Path(args.run); meta=config(run); data=json.loads((run/'source-records.json').read_text()); pairs=json.loads((run/'pairs.json').read_text())
    if digest(encoded(data).encode())!=meta['snapshot_sha256']: raise ValueError('Source snapshot changed')
    if len(data)!=meta['records'] or len(pairs)!=meta['pairs']: raise ValueError('Source counts changed')
    actual={stable_id(r[0],r[4]):{'stable_id':stable_id(r[0],r[4]),'reading':r[0],'surface':r[4]} for r in data}
    if actual!=pairs: raise ValueError('Source pair mapping changed')
    tax=json.loads((run/'taxonomy.json').read_text())
    if digest(encoded(tax).encode())!=meta['taxonomy_sha256']: raise ValueError('Taxonomy changed')
    if meta.get('schema_sha256') and digest((run/'result.schema.json').read_bytes())!=meta['schema_sha256']: raise ValueError('Frozen schema changed')
    for name,sha in meta['prompt_hashes'].items():
        if digest((run/'prompts'/(name+'.md')).read_bytes())!=sha: raise ValueError('Prompt changed')
    selected=set(meta.get('selected_ids',[]))
    if not selected:
        selected={r['id'] for r in db.execute("SELECT id FROM job_items WHERE stage='A'")}
    ordered=sorted(pairs,key=lambda i:digest((meta['seed']+i).encode()))
    expected=ordered[:min(900,meta['selected'])]
    expected_set=set(expected)
    rc=collections.Counter(x['reading'] for x in pairs.values()); sc=collections.Counter(x['surface'] for x in pairs.values())
    surface_ambiguity={i for i,x in pairs.items() if sc[x['surface']]>1}
    if 'surface_ambiguity_ids' in meta and set(meta['surface_ambiguity_ids'])!=surface_ambiguity: raise ValueError('Surface ambiguity inventory changed')
    extras=[i for i in ordered if i not in expected_set and (rc[pairs[i]['reading']]>1 or sc[pairs[i]['surface']]>1)]
    expected+=extras[:max(0,meta['selected']-len(expected))]
    expected_set=set(expected)
    expected+=[i for i in ordered if i not in expected_set][:max(0,meta['selected']-len(expected))]
    if meta['full']: expected=ordered
    if selected!=set(expected): raise ValueError('Invalid selected IDs')
    for stage in ('A','B'):
        scheduled={r['id'] for r in db.execute('SELECT id FROM job_items WHERE stage=?',(stage,))}
        if scheduled!=selected: raise ValueError('A/B selected coverage mismatch')
    for job in db.execute('SELECT * FROM jobs'):
        ids=json.loads(job['ids'])
        wanted=job_identity(meta,job['pass'],ids)
        if wanted!=job['id'] or not set(ids)<=selected: raise ValueError('Job identity changed')
        if job['status']!='validated': continue
        items=json.loads(job['result']); validate(items,ids,pairs,tax)
        evidence=json.loads(job['evidence'])
        if meta.get('pair_anchor_required'):
            anchor=anchor_evidence(run,job,context={'meta':meta,'pairs':pairs,'taxonomy':tax})
            if any(evidence.get(k)!=v for k,v in anchor.items()): raise ValueError('Accepted anchor evidence changed')
            emitted={item['stable_id']:item for item in parse_decisions(attempt_directory(run,job)/'output.jsonl')}
            if any({key:item[key] for key in FIELDS}!={key:emitted[item['stable_id']][key] for key in FIELDS} for item in items): raise ValueError('Accepted result differs from emitted pair decision')
        if evidence.get('model')!=meta['models'][job['pass']] or not evidence.get('agent_id'): raise ValueError('Invalid execution evidence')
        for item in items:
            if item.get('model')!=evidence['model'] or item.get('classification_pass')!=job['pass'] or item.get('batch_id')!=job['id'] or item.get('prompt_version')!=meta['prompt_hashes'][job['pass']]: raise ValueError('Result provenance mismatch')
            indexed=db.execute('SELECT value,job_id FROM result_items WHERE pass=? AND id=?',(job['pass'],item['stable_id'])).fetchone()
            if not indexed or indexed['value']!=encoded(item) or indexed['job_id']!=job['id']: raise ValueError('Result index mismatch')
    finals=list(db.execute('SELECT * FROM finals'))
    for row in finals:
        validate([json.loads(row['value'])],[row['id']],pairs,tax)
        origin=db.execute('SELECT pass,status,result FROM jobs WHERE id=?',(row['origin'],)).fetchone()
        if origin is None or origin['status']!='validated': raise ValueError('Invalid final origin')
        final=json.loads(row['value'])
        original=next((item for item in json.loads(origin['result']) if item['stable_id']==row['id']),None)
        if original is None or {k:v for k,v in final.items() if k!='agreement_status'}!={k:v for k,v in original.items() if k!='agreement_status'}: raise ValueError('Final differs from origin')
        if row['id'] not in selected: raise ValueError('Unexpected final ID')
        for stage in ('A','B'):
            if not db.execute('SELECT 1 FROM result_items WHERE pass=? AND id=?',(stage,row['id'])).fetchone(): raise ValueError('Final missing A/B')
        ab=[json.loads(db.execute('SELECT value FROM result_items WHERE pass=? AND id=?',(stage,row['id'])).fetchone()['value']) for stage in ('A','B')]
        if final.get('agreement_status')!=('agree' if semantic(ab[0])==semantic(ab[1]) else 'disagree'): raise ValueError('Agreement status changed')
        prior={r['pass']:r for r in db.execute('SELECT pass,value,job_id FROM result_items WHERE id=?',(row['id'],))}
        need_review=(meta.get('review_all') or semantic(ab[0])!=semantic(ab[1]) or high_risk(ab[0]) or high_risk(ab[1]) or row['id'] in surface_ambiguity or int(row['id'][:8],16)%10==0)
        if need_review and 'reviewer' not in prior: raise ValueError('Required Reviewer judgment missing')
        need_sol=(int(row['id'][:8],16)%100==0 and semantic(ab[0])==semantic(ab[1]) and not unknown(ab[0]) and not ab[0]['needs_review'])
        if 'reviewer' in prior:
            reviewed=json.loads(prior['reviewer']['value'])
            need_sol=need_sol or reviewer_requires_sol(ab[0],ab[1],reviewed,meta.get('adjudicate_disagreements',False))
        if need_sol and 'adjudicator' not in prior: raise ValueError('Required Sol judgment missing')
        expected_origin=next(prior[stage]['job_id'] for stage in ('adjudicator','reviewer','A') if stage in prior)
        if row['origin']!=expected_origin: raise ValueError('Final bypasses the latest review')
        if unknown(final):
            if origin['pass']!='adjudicator': raise ValueError('Unknown without Sol adjudication')
            if not db.execute("SELECT 1 FROM result_items WHERE pass='reviewer' AND id=?",(row['id'],)).fetchone(): raise ValueError('Unknown without Reviewer')
    audit_path=run/'audit-selection.json'
    if audit_path.exists():
        audit_selection=json.loads(audit_path.read_text())
        if audit_selection['source_sha256']!=meta['source_sha256']: raise ValueError('Audit source mismatch')
        audit_ids=audit_selection['uniform_ids']+audit_selection['stratified_ids']
        if len(audit_ids)!=len(set(audit_ids)) or not set(audit_ids)<=selected: raise ValueError('Invalid audit IDs')
        if args.complete:
            for i in audit_ids:
                origin=db.execute('SELECT jobs.pass FROM finals JOIN jobs ON jobs.id=finals.origin WHERE finals.id=?',(i,)).fetchone()
                if not origin or origin['pass']!='adjudicator': raise ValueError('Independent Sol audit incomplete')
    if args.complete and ({r['id'] for r in finals}!=selected or db.execute("SELECT count(*) FROM jobs WHERE status!='validated'").fetchone()[0]): raise ValueError('Classification incomplete')
    if args.complete and db.execute("SELECT 1 FROM anomalies WHERE status!='inspected_by_sol' LIMIT 1").fetchone(): raise ValueError('Unknown-rate anomaly requires Sol inspection')
    complete=({r['id'] for r in finals}==selected
              and not db.execute("SELECT 1 FROM jobs WHERE status!='validated' LIMIT 1").fetchone()
              and not db.execute("SELECT 1 FROM anomalies WHERE status!='inspected_by_sol' LIMIT 1").fetchone())
    if audit_path.exists():
        complete=complete and all(db.execute("SELECT jobs.pass FROM finals JOIN jobs ON jobs.id=finals.origin WHERE finals.id=?",(i,)).fetchone()[0]=='adjudicator' for i in audit_ids)
    print(encoded({'verified':True,'selected':meta['selected'],'finalized':len(finals),'complete':bool(complete)}))


def report(args):
    with connect(args.run) as db:
        db.execute('BEGIN')
        return _report(db,args)


def _report(db,args):
    counts=collections.defaultdict(collections.Counter); passes=collections.defaultdict(dict); evidence=[]
    for row in db.execute("SELECT pass,result,evidence FROM jobs WHERE status='validated'"):
        for item in json.loads(row['result']): passes[row['pass']][item['stable_id']]=item
        evidence.append(json.loads(row['evidence']))
    domains=collections.defaultdict(collections.Counter)
    for i in set(passes['A'])&set(passes['B']):
        a,b=passes['A'][i],passes['B'][i]
        agree=semantic(a)==semantic(b)
        counts['agreement']['agree' if agree else 'disagree']+=1
        domains[a['primary_domain'] or 'null']['agree' if agree else 'disagree']+=1
        for field in ('usage_class','primary_domain','tags','ambiguous'):
            equal=sorted(a[field])==sorted(b[field]) if isinstance(a[field],list) else a[field]==b[field]
            counts['field_agreement'][field+'_agree' if equal else field+'_disagree']+=1
    for row in db.execute('SELECT value FROM finals'):
        item=json.loads(row['value'])
        for field in ('usage_class','primary_domain','final_category','agreement_status'): counts[field][str(item.get(field))]+=1
    meta=config(args.run)
    groups={'uniform':set(meta.get('uniform_ids',[])), 'ambiguity':set(meta.get('ambiguity_ids',[]))}
    if not groups['ambiguity'] and not meta['full']:
        groups['ambiguity']={r['id'] for r in db.execute("SELECT id FROM job_items WHERE stage='A'")}-groups['uniform']
    strata={name:collections.Counter() for name in groups}
    for row in db.execute('SELECT id,value FROM finals'):
        item=json.loads(row['value'])
        for name,ids in groups.items():
            if row['id'] in ids: strata[name][item['usage_class']]+=1
    output={'validation_errors_scope':'Recorded ingest and instrumented emit failures; older pre-emit failures and worker serialization failures may be absent. Consult host traces.','sample_group_usage':strata,'selected':meta['selected'],'counts':counts,'domain_agreement':domains,'model_processed':{stage:len(items) for stage,items in passes.items()},'usage_evidence':evidence,'validation_errors':[dict(r) for r in db.execute('SELECT * FROM validation_errors')],'unknown_anomalies':[dict(r) for r in db.execute('SELECT * FROM anomalies')],'agreement_fields':sorted(json.loads(semantic(next(iter(passes['A'].values()))))) if passes['A'] else [],'domain_grouping':'Classifier A primary_domain; null includes unresolved or multiple domains','accuracy':'not measured: no independent human gold labels','cost':'unavailable unless explicitly present in execution evidence'}
    overlap=len(set(passes['A'])&set(passes['B']))
    output['agreement_rates']={'compared_pairs':overlap,
        'all_fields':counts['agreement']['agree']/overlap if overlap else None,
        **{field:counts['field_agreement'][field+'_agree']/overlap if overlap else None for field in ('usage_class','primary_domain','tags','ambiguous')}}
    output['domain_disagreement_rates']={domain:values['disagree']/sum(values.values()) for domain,values in domains.items()}
    model_ids=collections.defaultdict(set);model_counts=collections.Counter()
    for stage,items in passes.items():
        model=meta['models'][stage];model_ids[model].update(items);model_counts[model]+=len(items)
    output['model_totals']={model:{'judgments':n,'unique_pairs':len(model_ids[model])} for model,n in model_counts.items()}
    output['finalized']=db.execute('SELECT count(*) FROM finals').fetchone()[0]
    output['review_judgments']=sum(len(passes[stage]) for stage in ('reviewer','adjudicator'))
    output['ai_audit_is_ground_truth']=False
    finals={r['id']:json.loads(r['value']) for r in db.execute('SELECT id,value FROM finals')}
    run=Path(args.run)
    atomic(run/'human-review.jsonl',''.join(encoded(finals[i])+'\n' for i in sorted(finals) if unknown(finals[i])))
    atomic(run/'disagreements.jsonl',''.join(encoded({'stable_id':i,'A':passes['A'][i],'B':passes['B'][i],'final':finals.get(i)})+'\n' for i in sorted(set(passes['A'])&set(passes['B'])) if semantic(passes['A'][i])!=semantic(passes['B'][i])))
    audit_path=run/'audit-selection.json'
    if audit_path.exists():
        selection=json.loads(audit_path.read_text())
        atomic(run/'audit-sample.jsonl',''.join(encoded(finals[i])+'\n' for i in selection['uniform_ids']+selection['stratified_ids'] if i in finals))
    output['human_review_count']=sum(unknown(item) for item in finals.values())
    atomic(Path(args.run)/'report.json',encoded(output)); print(encoded({k:v for k,v in output.items() if k!='usage_evidence'}))


def export(args):
    args.complete=True; verify(args)
    run=Path(args.run); db=connect(run); finals={r['id']:json.loads(r['value']) for r in db.execute('SELECT * FROM finals')}; data=json.loads((run/'source-records.json').read_text())
    selected_records=[r for r in data if stable_id(r[0],r[4]) in finals]
    out=external_path(args.output)
    if out.exists(): raise ValueError('Export destination already exists')
    out.mkdir(parents=True)
    grouped=collections.defaultdict(list)
    for row in selected_records: grouped[finals[stable_id(row[0],row[4])]['final_category']].append(row)
    recovered=[]
    for category,rows in sorted(grouped.items()):
        if not category.replace('_','').isalnum(): raise ValueError('Unsafe category filename')
        payload=''.join('\t'.join(r)+'\n' for r in sorted(rows)).encode()
        path=out/(category+'.tsv.gz')
        with path.open('wb') as raw:
            with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as stream: stream.write(payload)
        with gzip.open(path,'rt',encoding='utf-8') as stream: recovered.extend(list(csv.reader(stream,delimiter='\t',quoting=csv.QUOTE_NONE)))
    if collections.Counter(map(tuple,recovered))!=collections.Counter(map(tuple,selected_records)): raise ValueError('Export multiset mismatch')
    tag_rows=collections.defaultdict(list)
    for row in selected_records:
        for tag in finals[stable_id(row[0],row[4])]['tags']: tag_rows[tag].append(row)
    for tag,rows in sorted(tag_rows.items()):
        target=out/'tags'/(tag+'.tsv.gz'); target.parent.mkdir(exist_ok=True)
        with target.open('wb') as raw:
            with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as stream: stream.write(''.join('\t'.join(r)+'\n' for r in sorted(rows)).encode())
        with gzip.open(target,'rt',encoding='utf-8') as stream: restored=list(csv.reader(stream,delimiter='\t',quoting=csv.QUOTE_NONE))
        if collections.Counter(map(tuple,restored))!=collections.Counter(map(tuple,rows)): raise ValueError('Tag export mismatch')
    atomic(out/'assignments.jsonl' ,''.join(encoded(finals[i])+'\n' for i in sorted(finals)))
    atomic(out/'taxonomy.json',(run/'taxonomy.json').read_text())
    repo=Path(__file__).resolve().parents[2]
    notice=repo/'src/main/classification/term-semantic/NOTICE.md'
    if notice.is_file(): shutil.copyfile(notice,out/'taxonomy-NOTICE.md')
    licenses=out/'source-notices'; licenses.mkdir()
    shutil.copyfile(repo/'LICENSE-DATA.md',licenses/'LICENSE-DATA.md')
    shutil.copytree(repo/'src/main/resources/third-party',licenses/'third-party')
    atomic(out/'README.txt','Classification proposal, not an IME binary.\n'
           'Primary category files preserve each selected original reading/POS/cost/surface record once.\n'
           'Tag files overlap and must not be added to the primary multiset.\n'
           'New annotations come from the recorded LLM passes, not supplied dictionary evidence.\n'
           'Inherited taxonomy and original dictionary notices are retained separately.\n'
           'No blanket relicensing or measured semantic accuracy is asserted.\n')
    export_manifest={'schema_version':1,'status':'proposal','production_integration':False,
        'semantic_accuracy_measured':False,'source_sha256':config(run)['source_sha256'],
        'source_records_snapshot_sha256':config(run)['snapshot_sha256'],
        'original_pairs':config(run)['pairs'],'original_records':len(data),
        'exported_pairs':len(finals),'exported_records':len(recovered),
        'full_source':len(recovered)==len(data),'taxonomy_sha256':config(run)['taxonomy_sha256'],
        'models':config(run)['models'],'prompt_hashes':config(run)['prompt_hashes'],
        'files':{str(f.relative_to(out)):digest(f.read_bytes()) for f in sorted(out.rglob('*')) if f.is_file()}}
    atomic(out/'manifest.json',encoded(export_manifest)+'\n')
    print(encoded({'exported_pairs':len(finals),'exported_records':len(recovered),'full_source':len(recovered)==len(data)}))


def compare(args):
    opener=gzip.open if args.legacy.endswith('.gz') else open
    legacy={}
    with opener(args.legacy,'rt',encoding='utf-8') as stream:
        for row in csv.DictReader(stream,delimiter='\t'):
            reading=row.get('reading'); surface=row.get('surface'); category=row.get('primary_category',row.get('category',row.get('domain')))
            if reading is None or surface is None or category is None: raise ValueError('Legacy headers must identify reading,surface,category')
            legacy[stable_id(reading,surface)]=category
    db=connect(args.run); transitions=collections.Counter(); examples=[]
    for row in db.execute('SELECT id,value FROM finals ORDER BY id'):
        item=json.loads(row['value']); old=legacy.get(row['id'])
        if old is not None:
            transitions[(old,item['final_category'])]+=1
            if old!=item['final_category'] and len(examples)<200: examples.append({'old':old,'new':item})
    output={'transitions':[{'old':a,'new':b,'count':n} for (a,b),n in sorted(transitions.items())],'examples':examples,'legacy_is_gold':False}
    atomic(Path(args.run)/'comparison.json',encoded(output)); print(encoded(output))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','promote','extend-pilot','audit','review-all','acknowledge-anomaly','next','emit','reveal','ingest','status','verify','report','compare','export'):
        p=sub.add_parser(name); p.add_argument('--run',required=True)
        if name=='prepare':
            for key in ('source','taxonomy','prompts'): p.add_argument('--'+key,required=True)
            p.add_argument('--seed',default='semantic-v1'); p.add_argument('--pilot-size',type=int,default=1200); p.add_argument('--batch-size',type=int,default=100); p.add_argument('--full',action='store_true'); p.add_argument('--classifier-model',default='gpt-6-luna'); p.add_argument('--adjudicator-model',default='gpt-6.1-sol')
        if name=='extend-pilot': p.add_argument('--pilot-size',type=int,default=1200)
        if name=='promote': p.add_argument('--batch-size',type=int,choices=range(1,201))
        if name=='audit': p.add_argument('--size',type=int,default=240)
        if name=='acknowledge-anomaly':
            p.add_argument('--job',required=True); p.add_argument('--note',required=True); p.add_argument('--evidence',required=True)
        if name=='next': p.add_argument('--stage',choices=['A','B','reviewer','adjudicator']); p.add_argument('--lease-seconds',type=int,default=1800)
        if name in ('emit','reveal'): p.add_argument('--job',required=True)
        if name=='emit':
            p.add_argument('--decisions',required=True); p.add_argument('--independent',action='store_true')
        if name=='ingest':
            for key in ('job','output','evidence'): p.add_argument('--'+key,required=True)
        if name=='verify': p.add_argument('--complete',action='store_true')
        if name=='compare': p.add_argument('--legacy',required=True)
        if name=='export': p.add_argument('--output',required=True)
    args=parser.parse_args()
    if (getattr(args,'batch_size',None) is not None and args.batch_size<1) or getattr(args,'pilot_size',1)<1: parser.error('Sizes must be positive')
    try: globals()[{'next':'next_job','acknowledge-anomaly':'acknowledge_anomaly','review-all':'review_all','extend-pilot':'extend_pilot'}.get(args.command,args.command)](args)
    except (ValueError,KeyError,TypeError) as exc: parser.exit(2,str(exc)+'\n')

if __name__=='__main__': main()
