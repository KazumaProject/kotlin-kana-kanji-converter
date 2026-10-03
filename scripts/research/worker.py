#!/usr/bin/env python3
"""Resumable local-only dictionary research. No third-party Python dependencies.
Operational failures remain errors. AI outputs never create reading evidence.
"""
import argparse, contextlib, csv, gzip, hashlib, html, io, json, math, os, pathlib
import re, socket, sqlite3, sys, time, unicodedata, urllib.parse, urllib.request, urllib.error, zipfile
import xml.etree.ElementTree as ET

FILES = {'person':'names.txt','place':'place.txt.zip','wiki':'only_wiki.txt.zip',
         'neologd':'only_neologd.txt.zip','common':'wiki_neologd_common.txt.zip'}
DOCUMENT_USAGE = {}
ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / 'src/main/dictionary-quality/research'
TERMINAL = ('adopted','excluded_confirmed','not_distributed')
SCHEMA = '''
CREATE TABLE info(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE origins(id TEXT PRIMARY KEY,source TEXT,line INTEGER,reading TEXT,surface TEXT,left_id INTEGER,right_id INTEGER,cost INTEGER,raw TEXT NOT NULL);
CREATE TABLE candidates(id TEXT PRIMARY KEY,reading TEXT,surface TEXT,left_id INTEGER,right_id INTEGER,cost INTEGER,old_status TEXT,old_categories TEXT,normalization TEXT,state TEXT NOT NULL DEFAULT 'queued',research_round INTEGER NOT NULL DEFAULT 0,reason TEXT,decision TEXT,cache_key TEXT,error TEXT,error_count INTEGER NOT NULL DEFAULT 0,next_retry REAL NOT NULL DEFAULT 0);
CREATE INDEX candidate_pair ON candidates(surface,reading);
CREATE INDEX candidate_state ON candidates(state,id);
CREATE TABLE origin_candidates(origin_id TEXT,candidate_id TEXT,PRIMARY KEY(origin_id,candidate_id),FOREIGN KEY(origin_id) REFERENCES origins(id),FOREIGN KEY(candidate_id) REFERENCES candidates(id));
CREATE INDEX candidate_origins ON origin_candidates(candidate_id);
CREATE TABLE normalization(source TEXT,line INTEGER,reading TEXT,surface TEXT,left_id INTEGER,right_id INTEGER,cost INTEGER,status TEXT,reason TEXT,PRIMARY KEY(source,line,reading,surface,left_id,right_id));
CREATE TABLE documents(id TEXT PRIMARY KEY,url TEXT NOT NULL,revision TEXT NOT NULL,sha256 TEXT NOT NULL,path TEXT NOT NULL,bytes INTEGER NOT NULL,license TEXT NOT NULL);
CREATE TABLE facts(id TEXT PRIMARY KEY,reading TEXT,surface TEXT,kind TEXT NOT NULL,categories TEXT NOT NULL,target TEXT NOT NULL,document_id TEXT NOT NULL,body TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,FOREIGN KEY(document_id) REFERENCES documents(id));
CREATE INDEX fact_pair ON facts(surface,reading);
CREATE INDEX fact_document ON facts(document_id);
CREATE TABLE attempts(id INTEGER PRIMARY KEY,candidate_id TEXT,round INTEGER,url TEXT,result TEXT NOT NULL,error TEXT,document_id TEXT);
CREATE TABLE inferences(id INTEGER PRIMARY KEY,candidate_id TEXT,role TEXT,cache_key TEXT,model_digest TEXT,prompt_sha256 TEXT,input_sha256 TEXT,output TEXT,seconds REAL,tokens INTEGER,error TEXT,created REAL);
CREATE INDEX inference_reuse ON inferences(candidate_id,role,cache_key);
CREATE TABLE pilot(candidate_id TEXT PRIMARY KEY,stratum TEXT NOT NULL);
CREATE TABLE evaluations(id TEXT PRIMARY KEY,body TEXT NOT NULL);
CREATE TABLE model_calls(id INTEGER PRIMARY KEY,role TEXT,model_digest TEXT,configuration_sha256 TEXT,input_sha256 TEXT,request BLOB,response BLOB,aliases TEXT,error TEXT,seconds REAL,created REAL);
CREATE TABLE configuration_history(sha256 TEXT PRIMARY KEY,body TEXT NOT NULL,created REAL NOT NULL);
'''

def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(x): return hashlib.sha256(x if isinstance(x,bytes) else x.encode()).hexdigest()
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def reading(x):
    x=unicodedata.normalize('NFKC',x)
    return ''.join(chr(ord(c)-96) if 'ァ'<=c<='ヶ' else c for c in x)
def pair(y,s): return reading(y),unicodedata.normalize('NFKC',s)
def candidate_id(y,s,l,r): return digest(canonical([y,s,l,r]))[:32]
def emit(x): print(canonical(x),flush=True)
class LedgerConnection(sqlite3.Connection):
    def __exit__(self,*args):
        try: return super().__exit__(*args)
        finally: self.close()

def connect(path):
    db=sqlite3.connect(path,timeout=30,factory=LedgerConnection);db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA journal_mode=WAL')
    columns={r[1] for r in db.execute('PRAGMA table_info(candidates)')}
    if columns:
        if 'error_count' not in columns: db.execute('ALTER TABLE candidates ADD COLUMN error_count INTEGER NOT NULL DEFAULT 0')
        if 'next_retry' not in columns: db.execute('ALTER TABLE candidates ADD COLUMN next_retry REAL NOT NULL DEFAULT 0')
        db.execute('CREATE TABLE IF NOT EXISTS model_calls(id INTEGER PRIMARY KEY,role TEXT,model_digest TEXT,configuration_sha256 TEXT,input_sha256 TEXT,request BLOB,response BLOB,aliases TEXT,error TEXT,seconds REAL,created REAL)')
        db.execute('CREATE TABLE IF NOT EXISTS configuration_history(sha256 TEXT PRIMARY KEY,body TEXT NOT NULL,created REAL NOT NULL)')
        if 'active' not in {r[1] for r in db.execute('PRAGMA table_info(facts)')}: db.execute('ALTER TABLE facts ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
        db.execute('CREATE INDEX IF NOT EXISTS fact_document ON facts(document_id)')
        db.commit()
    return db

def info(db,k,v=None):
    if v is not None: db.execute('INSERT OR REPLACE INTO info VALUES(?,?)',(k,canonical(v)))
    row=db.execute('SELECT value FROM info WHERE key=?',(k,)).fetchone()
    return json.loads(row[0]) if row else None

def local_url(url):
    u=urllib.parse.urlparse(url)
    if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1') or u.username or u.password or u.path not in ('','/') or u.query or u.fragment:
        raise ValueError('Ollama endpoint must be a bare loopback HTTP endpoint')
    return url.rstrip('/')

class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        check_public_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl): raise ValueError('Ollama redirects are forbidden')

def request_json(url,body=None,local=False,timeout=300):
    req=urllib.request.Request(url,data=None if body is None else canonical(body).encode(),
        headers={'Content-Type':'application/json','User-Agent':'DictionaryResearch/4 (KazumaProject; source validation)'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()) if local else urllib.request.build_opener()
    with opener.open(req,timeout=timeout) as r:
        data=r.read(16*1024*1024+1)
        if len(data)>16*1024*1024: raise ValueError('Oversized JSON response')
    return json.loads(data)

def configuration(args):
    p=pathlib.Path(args.config); models=json.loads((p/'models.lock.json').read_text())
    taxonomy=json.loads((p/'categories.json').read_text())
    endpoint=local_url(models['endpoint'])
    prompts={r:(p/(r+'.txt')).read_text() for r in ('proposer','reviewer')}
    identity={'models':models,'taxonomy':taxonomy,'researchParserVersion':2,'prompts':{k:digest(v) for k,v in prompts.items()},'worker':digest(canonical({f.name:sha(f) for f in pathlib.Path(__file__).parent.glob('*.py')}))}
    return models,taxonomy,prompts,endpoint,identity

def pin_config(db,args):
    cfg=configuration(args);stored=info(db,'configuration')
    if stored is not None and stored!=cfg[-1]:
        info(db,'previousConfiguration',stored)
        if stored.get('researchParserVersion')!=cfg[-1]['researchParserVersion']:
            db.execute("UPDATE facts SET active=0 WHERE active=1 AND COALESCE(json_extract(body,'$.seedOnly'),0)!=1 AND json_extract(body,'$.source') IN ('Wikidata','Wikipedia','official-link','explicit-name-reading','attested-canonical-kana')")
        db.execute("UPDATE candidates SET state='queued',decision=NULL,reason='configuration-changed',error=NULL,research_round=0,error_count=0,next_retry=0 WHERE state!='queued' OR research_round!=0")
        db.execute("DELETE FROM info WHERE key IN ('finalized','acceptance')")
        if stored.get('taxonomy')!=cfg[-1].get('taxonomy'): db.execute("DELETE FROM info WHERE key='goldFrozen'")
    db.execute('INSERT OR IGNORE INTO configuration_history VALUES(?,?,?)',(digest(canonical(cfg[-1])),canonical(cfg[-1]),time.time()))
    info(db,'configuration',cfg[-1]);db.commit();return cfg

def validate_models(models,endpoint):
    available={m['name']:m['digest'] for m in request_json(endpoint+'/api/tags',local=True)['models']}
    for role in ('proposer','reviewer'):
        if available.get(models[role]['name'])!=models[role]['digest']: raise ValueError('Model digest mismatch: '+role)

@contextlib.contextmanager
def source_lines(path):
    if path.suffix=='.zip':
        with zipfile.ZipFile(path) as z:
            names=[n for n in z.namelist() if not n.endswith('/') and not n.startswith('__MACOSX/')]
            if names!=[path.stem]: raise ValueError('Unexpected source ZIP layout: '+str(path))
            with z.open(names[0]) as f: yield io.TextIOWrapper(f,encoding='utf-8')
    else:
        with path.open(encoding='utf-8') as f: yield f

def insert_candidate(db,y,s,l,r,c,old_status='',old_categories='',normalization='unchanged'):
    cid=candidate_id(y,s,l,r)
    db.execute('INSERT OR IGNORE INTO candidates(id,reading,surface,left_id,right_id,cost,old_status,old_categories,normalization) VALUES(?,?,?,?,?,?,?,?,?)',
               (cid,y,s,l,r,c,old_status,old_categories,normalization))
    db.execute('UPDATE candidates SET cost=MIN(cost,?) WHERE id=?',(c,cid))
    return cid

def prepare(args):
    models,taxonomy,prompts,endpoint,cfg=configuration(args)
    sources=pathlib.Path(args.source_dir);audit=pathlib.Path(args.audit);snapshot=pathlib.Path(args.snapshot)
    inputs={'sources':{s:sha(sources/f) for s,f in FILES.items()},'audit':sha(audit),'snapshot':sha(snapshot)}
    dest=pathlib.Path(args.ledger);dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        with connect(dest) as db:
            if info(db,'inputs')!=inputs or not info(db,'prepared'): raise ValueError('Existing ledger inputs differ or preparation is incomplete')
            pin_config(db,args);augment_originals(db);db.commit()
        return status(args)
    tmp=dest.with_suffix('.preparing.sqlite')
    if tmp.exists(): tmp.unlink()
    db=connect(tmp);db.executescript(SCHEMA)
    info(db,'inputs',inputs);info(db,'configuration',cfg);info(db,'schema',4)
    counts={'classification':0,'normalization':0,'origins':0,'links':0}
    try:
        with gzip.open(audit,'rt',encoding='utf-8',newline='') as f:
            for row in csv.DictReader(f,delimiter='\t'):
                l,r,c=(int(row[k]) for k in ('left_id','right_id','cost'))
                if row['phase']=='classification':
                    insert_candidate(db,row['reading'],row['surface'],l,r,c,row['quality_status'],row['categories'])
                    counts['classification']+=1
                elif row['phase']=='normalization':
                    y,s=row['output_reading'],row['output_surface']
                    db.execute('INSERT OR IGNORE INTO normalization VALUES(?,?,?,?,?,?,?,?,?)',
                        (row['sources'],int(row['line']),y,s,l,r,c,row['quality_status'],row['reason']))
                    counts['normalization']+=1
                if sum(counts.values())%10000==0: db.commit()
        db.commit();emit({'phase':'auditImported',**counts})
        for source,name in FILES.items():
            with source_lines(sources/name) as lines:
                for line,raw in enumerate(lines,1):
                    raw=raw.rstrip('\n\r')
                    fields=raw.split('\t')
                    if len(fields)!=5: raise ValueError(f'{source}:{line}: invalid input')
                    y,left,right,cost,s=fields;l,r,c=map(int,(left,right,cost))
                    if not 0<=l<=32767 or not 0<=r<=32767 or not -32768<=c<=32767: raise ValueError('Source context IDs/cost outside Kotlin Short range')
                    oid=digest(canonical([source,inputs['sources'][source],line]))[:32]
                    db.execute('INSERT INTO origins VALUES(?,?,?,?,?,?,?,?,?)',(oid,source,line,y,s,l,r,c,raw))
                    normalized=db.execute('SELECT * FROM normalization WHERE source=? AND line=?',(source,line)).fetchall()
                    outputs=[(x['reading'],x['surface'],x['reason']) for x in normalized if x['surface']]
                    if not normalized: outputs=[(y,s,'unchanged')]
                    if not outputs: outputs=[(y,s,'original:'+normalized[0]['reason'])]
                    for ny,ns,reason in outputs:
                        cid=insert_candidate(db,ny,ns,l,r,c,normalization=reason)
                        if reason!='unchanged': db.execute('UPDATE candidates SET normalization=? WHERE id=?',(reason,cid))
                        db.execute('INSERT OR IGNORE INTO origin_candidates VALUES(?,?)',(oid,cid));counts['links']+=1
                    counts['origins']+=1
                    if counts['origins']%10000==0: db.commit()
            db.commit();emit({'phase':'sourceImported','source':source,**counts})
        db.execute("UPDATE candidates SET normalization='unchanged' WHERE EXISTS (SELECT 1 FROM origin_candidates oc JOIN origins o ON o.id=oc.origin_id WHERE oc.candidate_id=candidates.id AND o.reading=candidates.reading AND o.surface=candidates.surface AND NOT EXISTS (SELECT 1 FROM normalization n WHERE n.source=o.source AND n.line=o.line))")
        if db.execute('SELECT COUNT(*) FROM candidates c WHERE NOT EXISTS (SELECT 1 FROM origin_candidates o WHERE o.candidate_id=c.id)').fetchone()[0]:
            raise ValueError('Baseline candidates not traceable to original rows')
        if db.execute('SELECT COUNT(*) FROM origins o WHERE NOT EXISTS (SELECT 1 FROM origin_candidates c WHERE c.origin_id=o.id)').fetchone()[0]: raise ValueError('Untracked original rows')
        augment_originals(db)
        info(db,'counts',counts);info(db,'snapshotPath',str(snapshot.resolve()));info(db,'prepared',True)
        db.commit();db.execute('PRAGMA wal_checkpoint(TRUNCATE)');db.close();os.replace(tmp,dest)
    except BaseException:
        db.close();raise
    status(args)

def augment_originals(db):
    # Review full originals as well as emitted components; dropped tails must not disappear.
    rows=db.execute("SELECT DISTINCT o.*,n.reason FROM origins o JOIN normalization n ON n.source=o.source AND n.line=o.line ORDER BY o.source,o.line").fetchall()
    for row in rows:
        cid=insert_candidate(db,row['reading'],row['surface'],row['left_id'],row['right_id'],row['cost'],old_status='normalization-original',normalization='original:'+row['reason'])
        db.execute('INSERT OR IGNORE INTO origin_candidates VALUES(?,?)',(row['id'],cid))

class Evidence:
    def __init__(self,db,args):
        self.db=db;self.root=pathlib.Path(args.documents);self.root.mkdir(parents=True,exist_ok=True)
        self.limit=configuration(args)[0]['documentLimitBytes']
        storage=str(self.root.resolve())
        if storage not in DOCUMENT_USAGE: DOCUMENT_USAGE[storage]=sum(f.stat().st_size for f in self.root.iterdir() if f.is_file())
        self.storage=storage
    def save(self,url,revision,data,license):
        h=digest(data);did=digest(canonical([url,revision,h]))[:32];p=self.root/h
        if not p.exists():
            total=DOCUMENT_USAGE[self.storage]
            if total+len(data)>self.limit: raise OSError('Document storage limit exceeded; no candidate decision changed')
            tmp=self.root/(h+'.tmp');tmp.write_bytes(data);os.replace(tmp,p);DOCUMENT_USAGE[self.storage]+=len(data)
        self.db.execute('INSERT OR IGNORE INTO documents VALUES(?,?,?,?,?,?,?)',(did,url,revision,h,str(p.resolve()),len(data),license))
        return did
    def fact(self,y,s,kind,categories,target,doc,body):
        y,s=pair(y,s);value=(y,s,kind,canonical(sorted(categories)),target,doc,canonical(body));fid=digest(canonical(value))[:32]
        inserted=self.db.execute('INSERT OR IGNORE INTO facts(id,reading,surface,kind,categories,target,document_id,body) VALUES(?,?,?,?,?,?,?,?)',(fid,*value)).rowcount
        inserted+=self.db.execute('UPDATE facts SET active=1 WHERE id=? AND active=0',(fid,)).rowcount
        if inserted:
            self.db.execute("UPDATE candidates SET state='queued',reason='evidence-changed',decision=NULL,error=NULL WHERE surface=? AND (reading=? OR ?='') AND decision IS NOT NULL",(s,y,y))
            self.db.execute("DELETE FROM info WHERE key IN ('finalized','acceptance')")
        return fid
    def fetch(self,url,cid,round,revision='retrieved',license='source-specific'):
        try: check_public_url(url)
        except Exception as ex:
            self.db.execute('INSERT INTO attempts(candidate_id,round,url,result,error) VALUES(?,?,?,?,?)',(cid,round,url,'error',str(ex)))
            self.db.commit();raise
        old=self.db.execute('SELECT d.* FROM attempts a JOIN documents d ON d.id=a.document_id WHERE a.url=? AND a.result=\'success\' ORDER BY a.id DESC LIMIT 1',(url,)).fetchone()
        if old:
            p=pathlib.Path(old['path'])
            if sha(p)!=old['sha256']: raise ValueError('Cached document checksum mismatch')
            self.db.execute('INSERT INTO attempts(candidate_id,round,url,result,document_id) VALUES(?,?,?,?,?)',(cid,round,url,'success',old['id']))
            return old['id'],p.read_bytes()
        try:
            host=urllib.parse.urlparse(url).hostname;last=info(self.db,'lastFetch:'+host) or 0
            blocked=info(self.db,'blockedUntil:'+host) or 0
            if blocked>time.time(): raise OSError('Source backoff active until '+str(blocked))
            delay=max(0,2-(time.time()-last))
            if delay: time.sleep(delay)
            info(self.db,'lastFetch:'+host,time.time());self.db.commit()
            opener=urllib.request.build_opener(PublicRedirect())
            with opener.open(urllib.request.Request(url,headers={'User-Agent':'KazumaProject-kana-research/4.0 (+https://github.com/KazumaProject/kotlin-kana-kanji-converter)'}),timeout=45) as f:
                check_public_url(f.url);data=f.read(2*1024*1024+1)
                if len(data)>2*1024*1024: raise ValueError('Oversized page')
            did=self.save(url,revision if revision!='retrieved' else 'sha256:'+digest(data),data,license)
            self.db.execute('INSERT INTO attempts(candidate_id,round,url,result,document_id) VALUES(?,?,?,?,?)',(cid,round,url,'success',did))
            return did,data
        except Exception as e:
            if isinstance(e,urllib.error.HTTPError) and e.code in (429,503):
                import email.utils
                retry=e.headers.get('Retry-After','60')
                try: until=time.time()+max(1,int(retry))
                except ValueError:
                    try: until=email.utils.parsedate_to_datetime(retry).timestamp()
                    except (ValueError,TypeError): until=time.time()+60
                info(self.db,'blockedUntil:'+urllib.parse.urlparse(url).hostname,until)
            self.db.execute('INSERT INTO attempts(candidate_id,round,url,result,error) VALUES(?,?,?,?,?)',(cid,round,url,'error',str(e)))
            self.db.commit();raise

def check_public_url(url):
    import ipaddress
    u=urllib.parse.urlparse(url)
    port=443 if u.scheme=='https' else 80
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.port not in (None,port): raise ValueError('Research pages must use public HTTP(S)')
    for address in socket.getaddrinfo(u.hostname,port):
        if not ipaddress.ip_address(address[4][0]).is_global: raise ValueError('Private/local research URL rejected')

def import_mozc(db,args,e):
    base=pathlib.Path(args.base_dir)
    wanted={pair(r[0],r[1]) for r in db.execute('SELECT reading,surface FROM candidates')}
    for name in ['dictionary%02d.txt'%i for i in range(10)]+['suffix.txt']:
        path=base/name;version=sha(path);key='import:'+name
        if info(db,key)==version: continue
        did=e.save('https://github.com/google/mozc/blob/'+args.mozc_commit+'/src/data/dictionary_oss/'+name,args.mozc_commit,path.read_bytes(),'Mozc BSD-3-Clause')
        with path.open() as f:
            for line,raw in enumerate(f,1):
                cells=raw.rstrip('\n').split('\t')
                if len(cells)>=5 and pair(cells[0],cells[4]) in wanted:
                    e.fact(cells[0],cells[4],'reading',[],name+':'+str(line),did,{'source':'Mozc','line':line,'reading':cells[0],'surface':cells[4]})
        info(db,key,version);db.commit()

NAME_TYPES={'surname':'person','given':'person','fem':'person','masc':'person','person':'person',
            'company':'organization','organization':'organization','group':'organization','place':'place',
            'station':'station','product':'product','work':'work','doc':'work','ev':'event','char':'character',
            'dei':'character','ship':'transport'}

def import_jmnedict(db,args,e):
    path=pathlib.Path(args.jmnedict);version=sha(path)
    if info(db,'import:JMnedict')=={'sha256':version,'parser':4}: return
    wanted={pair(r[0],r[1]) for r in db.execute('SELECT reading,surface FROM candidates')}
    import rescue
    wanted_surfaces=rescue.targets(db)
    data=path.read_bytes();did=e.save('https://www.edrdg.org/pub/Nihongo/JMnedict.xml.gz',version,data,'EDRDG / CC-BY-SA-4.0')
    db.execute('UPDATE facts SET active=0 WHERE document_id=?',(did,))
    with gzip.open(path,'rb') as f:
        header=f.read(20000)
    if b'<!ENTITY %' in header or re.search(br'<!ENTITY\s+[^>]+\b(?:SYSTEM|PUBLIC)\b',header): raise ValueError('External XML entities prohibited')
    names={html.unescape(v.decode()):k.decode() for k,v in re.findall(br'<!ENTITY\s+(\w+)\s+"([^"]+)"',header)}
    hits=0
    with gzip.open(path,'rb') as f:
        for event,node in ET.iterparse(f,events=('start','end')):
            if event=='start' and node.tag=='JMnedict': root=node
            if event!='end' or node.tag!='entry': continue
            seq=node.findtext('ent_seq');spellings=[n.text for n in node.findall('k_ele/keb')]
            for rr in node.findall('r_ele'):
                y=rr.findtext('reb');restrict=[n.text for n in rr.findall('re_restr')]
                if restrict and not set(restrict)<=set(spellings): raise ValueError('Invalid JMnedict reading restriction')
                for s in restrict or spellings or [y]:
                    if pair(y,s) not in wanted and pair('',s)[1] not in wanted_surfaces: continue
                    types=sorted({names.get(n.text,n.text) for n in node.findall('trans/name_type')})
                    evidence={'source':'JMnedict','entryId':seq,'reading':y,'surface':s,'re_restr':restrict,'nameTypes':types,
                              'translations':[[n.text for n in t.findall('trans_det')] for t in node.findall('trans')]}
                    e.fact(y,s,'reading',[], 'JMnedict:'+seq,did,evidence)
                    # Each translation keeps its own sense/name-type; no unconstrained union.
                    for i,tr in enumerate(node.findall('trans')):
                        ts=[names.get(n.text,n.text) for n in tr.findall('name_type')]
                        cats=sorted({NAME_TYPES[t] for t in ts if t in NAME_TYPES})
                        e.fact(y,s,'meaning',cats,'JMnedict:'+seq+':'+str(i),did,{**evidence,'nameTypes':ts,'sense':i})
                    hits+=1
            node.clear();root.clear()
            if hits and hits%10000==0: db.commit()
    info(db,'import:JMnedict',{'sha256':version,'parser':4});db.commit();emit({'phase':'JMnedict','matchedPairs':hits,'sha256':version})

def import_jmdict(db,args,e):
    """Consume schema3 pair-restricted senses only after checking their raw entry constraints."""
    path=pathlib.Path(args.jmdict);version=sha(path)
    if info(db,'import:JMdict')=={'sha256':version,'policy':5}: return
    snapshot=sqlite3.connect('file:'+str(pathlib.Path(args.snapshot).resolve())+'?mode=ro',uri=True)
    facts={}
    for y,s,body in snapshot.execute('SELECT reading,surface,body FROM lexical_details'):
        b=json.loads(body)
        if b.get('source')=='JMdict' and b.get('version')==version:
            facts.setdefault(b['entryId'].split(':')[0],[]).append((y,s,b))
    did=e.save('https://www.edrdg.org/pub/Nihongo/JMdict_e.gz',version,path.read_bytes(),'EDRDG / CC-BY-SA-4.0')
    checked=0
    db.execute('UPDATE facts SET active=0 WHERE document_id=?',(did,))
    with gzip.open(path,'rb') as f:
        header=f.read(20000)
    if b'<!ENTITY %' in header or re.search(br'<!ENTITY\s+[^>]+\b(?:SYSTEM|PUBLIC)\b',header): raise ValueError('External XML entities prohibited')
    codes={html.unescape(v.decode()):k.decode() for k,v in re.findall(br'<!ENTITY\s+([\w-]+)\s+"([^"]+)"',header)}
    def tags(n,k): return {codes.get(v.text,v.text) for v in n.findall(k)}
    with gzip.open(path,'rb') as f:
        for event,node in ET.iterparse(f,events=('start','end')):
            if event=='start' and node.tag=='JMdict': root=node
            if event!='end' or node.tag!='entry': continue
            seq=node.findtext('ent_seq')
            for y,s,b in facts.get(seq,[]):
                readings=[r for r in node.findall('r_ele') if pair(r.findtext('reb'),s)==pair(y,s) and
                          (pair(y,s)==pair(r.findtext('reb'),r.findtext('reb')) or not r.findall('re_restr') or s in [pair('',n.text)[1] for n in r.findall('re_restr')]) and
                          (not r.findall('re_nokanji') or pair(y,s)==pair(y,r.findtext('reb')))]
                index=int(re.search(r'sense-(\d+)',b['evidence']).group(1))-1
                sense=node.findall('sense')[index]
                if not readings or (sense.findall('stagk') and s not in [pair('',n.text)[1] for n in sense.findall('stagk')]) or (sense.findall('stagr') and reading(y) not in [reading(n.text) for n in sense.findall('stagr')]): raise ValueError('JMdict stored pair violates raw constraints: '+canonical([y,s,b['evidence']]))
                pos=misc=set()
                for prior in node.findall('sense')[:index+1]:
                    pos=tags(prior,'pos') or pos;misc=tags(prior,'misc') or misc
                fields=tags(sense,'field');cats=set()
                for name,cat in NAME_TYPES.items():
                    if name in misc: cats.add(cat)
                if 'food' in fields: cats.add('food')
                if fields & {'comp','chem','math','med','pharm','physics','biol','bot','anat','engr','elec','electr','telec','stat','logic','geol','astron','law'}: cats.add('technical')
                if not fields and pos & {'n','n-adv','n-t'} and not pos & {'n-pr','unc'} and not misc & (set(NAME_TYPES)|{'unclass','rare','fict','myth','creat'}): cats.add('general')
                evidence={**b,'pos':sorted(pos),'misc':sorted(misc),'fields':sorted(fields),'categories':sorted(cats),'classificationPolicy':4,'re_restr':[n.text for r in readings for n in r.findall('re_restr')],
                          'stagk':[n.text for n in sense.findall('stagk')],'stagr':[n.text for n in sense.findall('stagr')]}
                e.fact(y,s,'reading',[],b['entryId'],did,evidence)
                e.fact(y,s,'meaning',cats,'JMdict:'+b['entryId']+':sense:'+str(index+1),did,evidence)
                checked+=1
            node.clear();root.clear()
    snapshot.close();info(db,'import:JMdict',{'sha256':version,'policy':5});db.commit();emit({'phase':'JMdict','rawConstraintsChecked':checked})

def bulk(args):
    if not all((args.base_dir,args.jmdict,args.jmnedict,args.postal_zip)): raise ValueError('bulk requires Mozc resources, JMdict, JMnedict, and postal ZIP; partial reference fallback is forbidden')
    with connect(args.ledger) as db:
        pin_config(db,args);info(db,'bulkComplete',False);db.commit();augment_originals(db);e=Evidence(db,args)
        if args.base_dir:
            import_mozc(db,args,e);info(db,'baseIdDefSha256',sha(pathlib.Path(args.base_dir)/'id.def'))
        if args.jmdict: import_jmdict(db,args,e)
        if args.jmnedict: import_jmnedict(db,args,e)
        import bulk as reference_bulk
        if args.postal_zip: reference_bulk.postal(db,args,e,pair,reading,sha,info,emit)
        reference_bulk.snapshot_context(db,args,e,sha,info,emit)
        import rescue
        rescue.apply(db,args,e,insert_candidate,info,emit)
        reference_bulk.normalization(db,e,fact_rows,canonical,info,emit)
        info(db,'bulkComplete',{'configurationSha256':digest(canonical(configuration(args)[-1])),'completedAt':time.time()});db.commit()
    status(args)

def fact_rows(db,row):
    y,s=pair(row['reading'],row['surface'])
    return [dict(r) for r in db.execute("SELECT f.*,d.url,d.revision,d.sha256 FROM facts f JOIN documents d ON d.id=f.document_id WHERE f.active=1 AND (f.reading=? OR f.reading='') AND f.surface=? ORDER BY f.id",(y,s))]

def response_schema(ids,categories,fids):
    strings={'type':'array','items':{'type':'string'},'maxItems':8}
    refs={'type':'array','items':{'type':'string','enum':sorted(fids)} if fids else {'type':'string'},'maxItems':20 if fids else 0}
    role={'type':'object','additionalProperties':False,'properties':{
        'category':{'type':'string','enum':categories},'target':{'type':'string'},'sense':{'type':'string'},'evidenceIds':refs},
        'required':['category','target','sense','evidenceIds']}
    item={'type':'object','additionalProperties':False,'properties':{
        'id':{'type':'string','enum':ids},'quality':{'type':'string','enum':['appropriate','inappropriate','uncertain']},
        'roles':{'type':'array','items':role,'maxItems':8},'evidenceIds':refs,'missing':strings,
        'searchTerms':{'type':'array','items':{'type':'string'},'maxItems':3},
        'corrections':{'type':'array','items':{'type':'object','additionalProperties':False,
            'properties':{'surface':{'type':'string'},'reading':{'type':'string'},'evidenceIds':refs},'required':['surface','reading','evidenceIds']},'maxItems':4}},
        'required':['id','quality','roles','evidenceIds','missing','searchTerms','corrections']}
    return {'type':'object','additionalProperties':False,'properties':{'results':{'type':'array','items':item,'minItems':len(ids),'maxItems':len(ids)}},'required':['results']}

def validate_output(value,rows,evidence,categories):
    if not isinstance(value,dict) or set(value)!= {'results'} or not isinstance(value['results'],list): raise ValueError('Invalid AI result envelope')
    ids={r['id'] for r in rows};seen=set()
    for v in value['results']:
        if set(v)!= {'id','quality','roles','evidenceIds','missing','searchTerms','corrections'} or v['id'] not in ids or v['id'] in seen: raise ValueError('Wrong/duplicate AI candidate ID or fields')
        seen.add(v['id']);allowed={f['id'] for f in evidence[v['id']]}
        if v['quality'] not in ('appropriate','inappropriate','uncertain'): raise ValueError('Invalid AI quality')
        for k,limit in [('roles',8),('evidenceIds',20),('missing',8),('searchTerms',3),('corrections',4)]:
            if not isinstance(v[k],list) or len(v[k])>limit: raise ValueError('Invalid AI array: '+k)
        if not set(v['evidenceIds'])<=allowed: raise ValueError('AI invented evidence')
        targets={f['target'] for f in evidence[v['id']] if f['kind'] in ('meaning','context')}
        if any(role.get('target') not in targets for role in v['roles']): raise ValueError('AI invented target')
        for k in ('missing','searchTerms'):
            if any(not isinstance(s,str) or len(s)>512 for s in v[k]): raise ValueError('Invalid AI text')
        for role in v['roles']:
            if set(role)!= {'category','target','sense','evidenceIds'} or role['category'] not in categories or not role['target'] or not role['sense'] or not isinstance(role['evidenceIds'],list) or not set(role['evidenceIds'])<=allowed: raise ValueError('Invalid AI role or evidence')
        for correction in v['corrections']:
            if set(correction)!= {'surface','reading','evidenceIds'} or not isinstance(correction['surface'],str) or not isinstance(correction['reading'],str) or not set(correction['evidenceIds'])<=allowed: raise ValueError('Invalid AI correction')
    if seen!=ids: raise ValueError('AI omitted candidates')

def model_fact(f,row):
    body=json.loads(f['body'])
    if f['kind']=='reading': return {k:v for k,v in body.items() if k in ('source','entryId','reading','surface','re_restr','stagk','stagr','row','readingColumns','nameColumns','quotation','line')}
    if body.get('seedOnly'):
        kinds=body.get('nameKinds',{});names=[n for n in body.get('names',[]) if n==row['surface'] or any(k in ('label:ja','label:en','title:jawiki') for k in kinds.get(n,[]))]
        return {k:v for k,v in {**body,'names':names,'nameKinds':{n:kinds.get(n,[]) for n in names}}.items() if k not in ('readingPairs','readingNames')} | {'readingPairs':{n:ys for n,ys in body.get('readingPairs',{}).items() if n==row['surface']}}
    if body.get('source')=='Wikipedia': return {**body,'lead':body['lead'][:2000]}
    if body.get('source')=='official-link': return {**body,'excerpt':body['excerpt'][:2000]}
    if body.get('source')=='Wikidata':
        return {**body,'aliases':[n for n in body.get('aliases',[]) if pair('',n)[1]==pair('',row['surface'])[1]],
                'nameBoundReadings':{n:ys for n,ys in body.get('nameBoundReadings',{}).items() if pair('',n)[1] in {pair('',v)[1] for v in (row['surface'],body.get('label') or '',body.get('title') or '')}}}
    return body

def target_supported(role,facts):
    selected=[f for f in facts if f['id'] in role['evidenceIds'] and f['target']==role['target'] and f['kind'] in ('meaning','context')]
    if re.fullmatch(r'Q[0-9]+',role['target']) and not any(f['kind']=='reading' and f['target']==role['target'] for f in facts):
        # A dictionary pronunciation for a homograph is not proof of this entity.
        return False
    scoped=[json.loads(f['body']) for f in facts if f['target']==role['target'] and f['kind']=='context' and json.loads(f['body']).get('source')=='Wikidata']
    for b in scoped:
        names=b.get('nameBoundReadings',{})
        surface=next((f['surface'] for f in selected),'')
        known=names.get(surface,[])
        proof=[f for f in facts if f['kind']=='reading' and f['target']==role['target']]
        if known and not proof: return False
    for f in selected:
        b=json.loads(f['body'])
        if f['kind']=='meaning': return True
        if b.get('source')=='Wikidata':
            primary=(b.get('label'),b.get('title'))
            named=f['surface'] in primary or f['surface'] in b.get('nameBoundReadings',{})
            readings=b.get('nameBoundReadings',{}).get(f['surface'],[])
            if named and (not readings or any(reading(v) in [g['reading'] for g in facts if g['kind']=='reading'] for v in readings)): return True
        if b.get('source')=='Wikipedia' and (b.get('title')==f['surface'] or any(g['kind']=='reading' and g['target']==f['target'] and g['document_id']==f['document_id'] for g in facts)): return True
        if b.get('source')=='official-link' and any(g['kind']=='reading' and g['document_id']==f['document_id'] for g in facts): return True
        if b.get('seedOnly'):
            surface=f['surface'];kinds=b.get('nameKinds',{}).get(surface,[])
            if any(k in ('label:ja','title:jawiki') for k in kinds):
                readings=b.get('primaryReadings',[])
                pair_readings=[g['reading'] for g in facts if g['kind']=='reading']
                if not readings or any(reading(v) in pair_readings for v in readings): return True
    return False

def inference(db,args,rows,role,cfg,evidence_override=None,partition=True):
    models,taxonomy,prompts,endpoint,identity=cfg
    evidence={r['id']:(evidence_override[r['id']] if evidence_override is not None else fact_rows(db,r)) for r in rows}
    cats=[c['id'] for c in taxonomy['categories']]
    payload=[{'id':r['id'],'surface':r['surface'],'reading':r['reading'],'normalization':'original' if r['normalization']=='unchanged' or r['normalization'].startswith('original:') else 'derived',
              'facts':[{'evidenceId':f['id'],'kind':f['kind'],'categories':json.loads(f['categories']),'target':f['target'],'reading':f['reading'],'surface':f['surface'],'body':model_fact(f,r)} for f in evidence[r['id']]]} for r in rows]
    model=models[role];ph=digest(prompts[role]);keys={r['id']:digest(canonical([identity,role,item])) for r,item in zip(rows,payload)}
    previous={}
    for r in rows:
        old=db.execute('SELECT output FROM inferences WHERE candidate_id=? AND role=? AND cache_key=? AND error IS NULL ORDER BY id DESC LIMIT 1',(r['id'],role,keys[r['id']])).fetchone()
        if old: previous[r['id']]=json.loads(old[0])
    if len(previous)==len(rows): return previous
    if previous: return previous|inference(db,args,[r for r in rows if r['id'] not in previous],role,cfg,evidence_override,partition)
    cid_alias={r['id']:'c'+str(i) for i,r in enumerate(rows)}
    fid_alias={fid:'e'+str(i) for i,fid in enumerate(sorted({f['id'] for fs in evidence.values() for f in fs}))}
    request_payload=json.loads(canonical(payload))
    for item in request_payload:
        item['id']=cid_alias[item['id']]
        for fact in item['facts']: fact['evidenceId']=fid_alias[fact['evidenceId']]
    schema=response_schema(list(cid_alias.values()),cats,set(fid_alias.values()))
    semantic_targets=sorted({f['target'] for fs in evidence.values() for f in fs if f['kind'] in ('meaning','context')})
    item_schema=schema['properties']['results']['items']
    if semantic_targets: item_schema['properties']['roles']['items']['properties']['target']['enum']=semantic_targets
    else: item_schema['properties']['roles']['maxItems']=0
    shape={'results':[{'id':'candidate ID','quality':'appropriate|inappropriate|uncertain','roles':[{'category':'category ID','target':'evidence target ID','sense':'独立した語義','evidenceIds':['取得済みevidenceId']}],'evidenceIds':[],'missing':[],'searchTerms':[],'corrections':[]}]}
    message=canonical({'taxonomy':taxonomy,'candidates':request_payload,'outputShape':shape})
    # A too-large batch is retried as smaller batches, never silently truncated.
    estimated_tokens=sum(1 if ord(c)>127 else .34 for c in message+prompts[role])
    if estimated_tokens>models['options']['num_ctx']-models['options']['num_predict']-512 and len(rows)>1:
        mid=len(rows)//2;return {**inference(db,args,rows[:mid],role,cfg,evidence_override,partition),**inference(db,args,rows[mid:],role,cfg,evidence_override,partition)}
    if estimated_tokens>models['options']['num_ctx']-models['options']['num_predict']-512:
        if partition:
            row=rows[0];all_facts=evidence[row['id']];units=[f for f in all_facts if f['kind'] in ('meaning','context')]
            results=[]
            for unit in units:
                scoped=[f for f in all_facts if f['kind']=='reading' and (f['target']==unit['target'] or f['target'].rsplit(':',1)[0]==unit['target'].rsplit(':',1)[0])]
                if not scoped:
                    # Reading proofs bind the pair; target compatibility is checked
                    # against ALL facts below. One representative per provider is enough here.
                    representatives={}
                    for f in all_facts:
                        if f['kind']=='reading': representatives.setdefault(json.loads(f['body']).get('source',''),f)
                    scoped=list(representatives.values())
                related=[f for f in all_facts if f['target']==unit['target'] and f['kind']=='context' and json.loads(f['body']).get('source')=='Wikidata']
                control=[f for f in all_facts if f['target']==row['id'] and f['kind'] in ('normalization','invalid')]
                selected={f['id']:f for f in [unit]+scoped+related+control}
                results.append(inference(db,args,[row],role,cfg,{row['id']:list(selected.values())},False)[row['id']])
            if results:
                merged={'id':row['id'],'quality':'appropriate' if any(v['quality']=='appropriate' for v in results) else ('inappropriate' if all(v['quality']=='inappropriate' for v in results) else 'uncertain'),
                        'roles':list({(v['category'],v['target']):v for result in results if result['quality']=='appropriate' for v in result['roles']}.values()),
                        'evidenceIds':sorted({i for v in results for i in v['evidenceIds']}),'missing':sorted({i for v in results for i in v['missing']}),
                        'searchTerms':list(dict.fromkeys(i for v in results for i in v['searchTerms']))[:3],
                        'corrections':list({canonical(c):c for v in results for c in v['corrections']}.values())}
                # This is a host merge of independently stored source-unit calls, not
                # a fabricated model response. Each source unit was schema validated.
                db.execute('INSERT INTO inferences(candidate_id,role,cache_key,model_digest,prompt_sha256,input_sha256,output,seconds,tokens,created) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (row['id'],role,keys[row['id']],model['digest'],ph,digest(message),canonical(merged),0,0,time.time()))
                db.commit();return {row['id']:merged}
        for row in rows: retry_error(db,row['id'],ValueError('oversized-context'));db.commit()
        raise ValueError('Single candidate exceeds context budget; preserve evidence and resolve oversized context explicitly')
    start=time.monotonic();response=None
    request={'model':model['name'],'messages':[{'role':'system','content':prompts[role]}, {'role':'user','content':message}],
        'stream':False,'think':False,'format':schema,'options':models['options'],'keep_alive':'5m'}
    def record_call(error=None):
        db.execute('INSERT INTO model_calls(role,model_digest,configuration_sha256,input_sha256,request,response,aliases,error,seconds,created) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (role,model['digest'],digest(canonical(identity)),digest(message),gzip.compress(canonical(request).encode(),mtime=0),
             None if response is None else gzip.compress(canonical(response).encode(),mtime=0),canonical({'candidates':cid_alias,'facts':fid_alias}),error,time.monotonic()-start,time.time()))
        db.commit()
    try:
        validate_models(models,endpoint)
        for active in request_json(endpoint+'/api/ps',local=True).get('models',[]):
            if active['name'] in [models[r]['name'] for r in ('proposer','reviewer')] and active['name']!=model['name']:
                request_json(endpoint+'/api/generate',{'model':active['name'],'keep_alive':0},local=True)
        response=request_json(endpoint+'/api/chat',request,local=True,timeout=600)
        if response.get('done_reason')=='length': raise ValueError('Truncated model output; retry with smaller batch')
        value=json.loads(response['message']['content'])
        candidates_reverse={v:k for k,v in cid_alias.items()};facts_reverse={v:k for k,v in fid_alias.items()}
        for item in value['results']:
            item['id']=candidates_reverse[item['id']]
            for field in [item]+item['roles']+item['corrections']: field['evidenceIds']=[facts_reverse[i] for i in field['evidenceIds']]
        validate_output(value,rows,evidence,cats)
        record_call()
        result={v['id']:v for v in value['results']}
        for r in rows: db.execute('INSERT INTO inferences(candidate_id,role,cache_key,model_digest,prompt_sha256,input_sha256,output,seconds,tokens,created) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (r['id'],role,keys[r['id']],model['digest'],ph,digest(message),canonical(result[r['id']]),(time.monotonic()-start)/len(rows),response.get('eval_count',0)/len(rows),time.time()))
        db.commit();return result
    except Exception as ex:
        if capacity_failure(ex): raise
        record_call(str(ex))
        if len(rows)>1 and isinstance(ex,(ValueError,KeyError,TypeError)):
            mid=len(rows)//2;return {**inference(db,args,rows[:mid],role,cfg,evidence_override,partition),**inference(db,args,rows[mid:],role,cfg,evidence_override,partition)}
        for r in rows:
            db.execute('INSERT INTO inferences(candidate_id,role,cache_key,model_digest,prompt_sha256,input_sha256,error,seconds,created) VALUES(?,?,?,?,?,?,?,?,?)',
                (r['id'],role,keys[r['id']],model['digest'],ph,digest(message),str(ex),(time.monotonic()-start)/len(rows),time.time()))
            retry_error(db,r['id'],ex)
        db.commit();raise

def wiki_lead(content):
    depth=0;out=[];i=0
    while i<len(content):
        if content[i:i+2]=='{{': depth+=1;i+=2
        elif content[i:i+2]=='}}' and depth: depth-=1;i+=2
        else:
            if not depth: out.append(content[i])
            i+=1
    text=''.join(out);text=re.sub(r'<!--.*?-->','',text,flags=re.S)
    text=re.sub(r'\[\[([^]\n]+)\]\]',lambda m:m.group(1).split('|')[-1],text)
    return text.split('\n==')[0][:8000]

def extract_readings(db,e,row,did,text,target,canonical_name=None):
    """Only explicit name-bound readings. No text-to-reading model or alias Cartesian product."""
    s=row['surface'];plain=html.unescape(re.sub(r'<[^>]+>','',text)).replace("'''",'').replace("''",'')
    for match in re.finditer(re.escape(s)+r'\s*[（(]([ぁ-ゖァ-ヶー 　・]+)(?:[、,)）])',plain[:12000]):
        y=reading(match.group(1).replace(' ','').replace('　','').replace('・',''))
        if y==reading(row['reading']): e.fact(y,s,'reading',[],target,did,{'source':'explicit-name-reading','quotation':match.group(0),'start':match.start()})
    for name,y,quote in explicit_reading_bindings(text):
        if pair('',name)[1]==pair('',s)[1] and reading(y)==reading(row['reading']):
            e.fact(row['reading'],s,'reading',[],target,did,{'source':'explicit-name-reading','quotation':quote,'name':name,'reading':y})
    if all('ぁ'<=c<='ゖ' or 'ァ'<=c<='ヶ' or c=='ー' for c in s) and reading(s)==reading(row['reading']) and (canonical_name or target)==s:
        e.fact(row['reading'],s,'reading',[],target,did,{'source':'attested-canonical-kana','name':s})

def explicit_reading_bindings(text):
    """Literal ruby/reading fields only; never infer a pronunciation from prose."""
    kana=r'[ぁ-ゖァ-ヶー 　・]+'
    clean=lambda value:html.unescape(re.sub(r'<[^>]+>','',value)).strip()
    result=[]
    for match in re.finditer(r'\{\{\s*(?:ruby|ルビ|ふりがな)\s*\|\s*([^|{}]+)\s*\|\s*('+kana+r')\s*\}\}',text,re.I):
        result.append((clean(match[1]),match[2].replace(' ','').replace('　','').replace('・',''),match[0]))
    for match in re.finditer(r'<ruby\b[^>]*>(.*?)</ruby>',text,re.I|re.S):
        rt=re.search(r'<rt\b[^>]*>('+kana+r')</rt>',match[1],re.I|re.S)
        if rt:
            base=re.sub(r'<(?:rt|rp)\b[^>]*>.*?</(?:rt|rp)>','',match[1],flags=re.I|re.S)
            result.append((clean(base),rt[1].replace(' ','').replace('　','').replace('・',''),match[0]))
    # Restrict infobox bindings to ONE flat template with ONE name and reading.
    # Ambiguous/nested templates remain for additional investigation.
    for template in re.finditer(r'\{\{[^{}]+\}\}',text):
        names=re.findall(r'\|\s*(?:名前|名称|name)\s*=\s*([^\n|}]+)',template[0],re.I)
        ys=re.findall(r'\|\s*(?:ふりがな|よみがな|読み仮名)\s*=\s*('+kana+r')(?=[\n|}])',template[0])
        if len(names)==len(ys)==1: result.append((clean(names[0]),ys[0].replace(' ','').replace('　','').replace('・',''),template[0]))
    return result

def article_primary_name(content,surface):
    # A disambiguating page-title suffix is not part of a person's stated name.
    # Keep literal parentheses in names; only the article's explicit subject counts.
    first=re.search(r"'''([^'\n]+)'''",wiki_lead(content))
    return bool(first and pair('',first[1])[1]==pair('',surface)[1])

def decode_official_page(data):
    # Unsupported document formats/encodings are parser failures, never negative evidence.
    if data.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as source: data=source.read(2*1024*1024+1)
        if len(data)>2*1024*1024: raise ValueError('Expanded official page exceeds size limit')
    if data.startswith((b'%PDF',b'PK\x03\x04')) or b'\x00' in data[:4096]: raise ValueError('Unsupported official document format; parser work remains queued')
    match=re.search(br'charset\s*=\s*["\']?([A-Za-z0-9_-]+)',data[:8192],re.I)
    charset=match.group(1).decode('ascii') if match else 'utf-8'
    if charset.lower().replace('-','_') in ('shift_jis','sjis','x_sjis','windows_31j'): charset='cp932'
    try: return data.decode(charset,errors='strict')
    except (LookupError,UnicodeDecodeError) as ex: raise ValueError('Official page encoding could not be parsed') from ex

def research(db,args,row,proposal,round):
    e=Evidence(db,args);terms=[row['surface']] if round==1 else proposal['searchTerms'][:3] or [row['surface']+' 読み']
    import wikidata
    official=wikidata.fetch(db,args,e,row,round,pair,reading,extract_readings)
    titles=[]
    for term in terms[:3]:
        url='https://ja.wikipedia.org/w/api.php?'+urllib.parse.urlencode({'action':'query','format':'json','list':'search','srsearch':term,'srlimit':3})
        did,data=e.fetch(url,row['id'],round,license='Wikipedia search / CC-BY-SA')
        result=json.loads(data)
        if 'error' in result: raise ValueError('Wikipedia search API failure: '+canonical(result['error']))
        entries=result['query']['search']
        if not entries: db.execute('INSERT INTO attempts(candidate_id,round,url,result,document_id) VALUES(?,?,?,?,?)',(row['id'],round,url,'empty',did))
        titles.extend(t['title'] for t in entries)
        if len(set(titles))>=3: break
    for title in list(dict.fromkeys(titles))[:3]:
        url='https://ja.wikipedia.org/w/api.php?'+urllib.parse.urlencode({'action':'query','format':'json','titles':title,'prop':'revisions|extlinks|pageprops','rvprop':'ids|timestamp|content','rvslots':'main','ellimit':'max'})
        did,data=e.fetch(url,row['id'],round,license='Wikipedia / CC-BY-SA')
        value=json.loads(data)
        if 'error' in value: raise ValueError('Wikipedia article API failure')
        for page in value['query']['pages'].values():
            if 'missing' in page: continue
            rev=page['revisions'][0];content=rev['slots']['main']['*']
            db.execute('UPDATE documents SET revision=? WHERE id=?',(str(rev['revid']),did))
            e.fact(row['reading'],row['surface'],'context',[],page.get('pageprops',{}).get('wikibase_item',title),did,{'source':'Wikipedia','title':title,'revision':rev['revid'],'lead':wiki_lead(content)})
            primary=title==row['surface'] or article_primary_name(content,row['surface'])
            reading_target=page.get('pageprops',{}).get('wikibase_item',title) if primary else title+'#mentioned-name:'+row['surface']
            extract_readings(db,e,row,did,content,reading_target,canonical_name=row['surface'] if primary else title)
            # Kana aliases need an explicit name field, not a search-alias match.
            if row['surface'] and all('ぁ'<=c<='ゖ' or 'ァ'<=c<='ヶ' or c=='ー' for c in row['surface']) and reading(row['surface'])==reading(row['reading']):
                for field in re.finditer(r'\|\s*(別名|芸名|名義|通称|名前)\s*=\s*([^\n|}]+)',content):
                    name=field.group(2).strip().replace("'''",'')
                    if name==row['surface']:
                        target=page.get('pageprops',{}).get('wikibase_item',title)
                        e.fact(row['reading'],row['surface'],'reading',[],target,did,{'source':'attested-canonical-kana','name':name,'field':field.group(1),'quotation':field.group(0),'revision':rev['revid']})
            # Only article-declared official links, never URLs invented by a model.
            alias_declared=any(m[2].strip()==row['surface'] for m in re.finditer(r'\|\s*(別名|芸名|名義|通称|名前)\s*=\s*([^\n|}]+)',content))
            if primary or alias_declared:
                for candidate in re.findall(r'\{\{\s*(?:Official website|公式ウェブサイト|公式サイト)\s*\|\s*(https?://[^\s|}]+)',content,re.I):
                    if candidate in [v['*'] for v in page.get('extlinks',[])]: official.append(candidate)
                for candidate in re.findall(r'(?:公式サイト|公式ウェブサイト)\s*=\s*(https?://[^\s|}]+)',content):
                    if candidate in [v['*'] for v in page.get('extlinks',[])]: official.append(candidate)
    for url in list(dict.fromkeys(official))[:3]:
        did,data=e.fetch(url,row['id'],round)
        text=decode_official_page(data);extract_readings(db,e,row,did,text,url)
        e.fact(row['reading'],row['surface'],'context',[],url,did,{'source':'official-link','excerpt':html.unescape(re.sub('<[^>]+>','',text))[:8000]})
    db.execute('UPDATE candidates SET research_round=? WHERE id=?',(round,row['id']));db.commit()

def agreement(proposal,review):
    def roles(v): return {(r['category'],r['target'],r['sense']) for r in v['roles']}
    # Stable published target IDs are needed. Free prose descriptions cannot establish identity.
    return proposal['quality']==review['quality']=='appropriate' and {(v['category'],v['target']) for v in proposal['roles']}=={(v['category'],v['target']) for v in review['roles']} and bool(proposal['roles'])

def direct_category_fact(f,category):
    if f['kind']!='meaning': return False
    b=json.loads(f['body']);source=b.get('source')
    if source=='Japan Post': return category=='place'
    # JMnedict place-name covers buildings too; it is not a precise place category.
    if source=='JMnedict': return category!='place' and any(NAME_TYPES.get(t)==category for t in b.get('nameTypes',[]))
    if source=='JMdict': return any(NAME_TYPES.get(t)==category for t in b.get('misc',[]))
    return False

def decide(db,row,p,r):
    facts=fact_rows(db,row);reading_facts=[f for f in facts if f['kind']=='reading'];byid={f['id']:f for f in facts}
    direct={(c,f['target']) for f in facts for c in json.loads(f['categories']) if direct_category_fact(f,c)}
    ai_roles=p['roles'] if agreement(p,r) else []
    supported=[v for v in ai_roles if v['evidenceIds'] and all(i in byid for i in v['evidenceIds']) and target_supported(v,facts)]
    correction=any((v['reading'],v['surface'])!=(row['reading'],row['surface']) for v in p['corrections']+r['corrections'])
    # An uncertainty vote cannot overturn an explicit constrained lexical/postal fact.
    # Only facts rechecked against raw reference data participate; seed classifications do not.
    source_roles=[]
    for f in facts:
        cats=json.loads(f['categories']);b=json.loads(f['body'])
        if len(cats)==1 and direct_category_fact(f,cats[0]):
            source_roles.append({'category':cats[0],'target':f['target'],'sense':str(b.get('sense',b.get('entryId',b.get('row','')))),'evidenceIds':[f['id']],'method':'direct'})
    for role in supported:
        role['method']='direct' if (role['category'],role['target']) in direct else 'ai'
        role['evidenceIds']=[i for i in role['evidenceIds'] if byid[i]['target']==role['target'] and byid[i]['kind'] in ('context','meaning')]
    inferred={(v['category'],v['target']) for v in supported}
    source_roles=[v for v in source_roles if not (v['category'] in ('general','technical','product') and any(w['target']==v['target'] and w['category']!=v['category'] for w in supported))]
    merged={(v['category'],v['target']):v for v in source_roles+supported}
    supported=list(merged.values())
    # Full original-row normalization must be independently proven before adoption.
    normalized=row['normalization']!='unchanged' and not row['normalization'].startswith('original:')
    normalization_proof=any(f['kind']=='normalization' and f['target']==row['id'] for f in facts)
    eligible=bool(reading_facts and supported and not correction and (not normalized or normalization_proof))
    decision={'readingEvidence':[f['id'] for f in reading_facts],'roles':supported,
              'classificationRoute':'direct' if supported and all(v.get('method')=='direct' for v in supported) else 'ai',
              'independentReviewDisagreement':not agreement(p,r),
              'researchRounds':db.execute('SELECT research_round FROM candidates WHERE id=?',(row['id'],)).fetchone()[0],'missing':sorted(set(p['missing']+r['missing'])),
              'correctionProposals':[v for v in p['corrections']+r['corrections'] if (v['reading'],v['surface'])!=(row['reading'],row['surface'])],'normalizationVerified':not normalized or normalization_proof}
    invalid=[f for f in facts if f['kind']=='invalid' and f['target']==row['id']]
    if invalid:
        state='excluded_confirmed';reason='source-confirmed-invalid-structure';decision['exclusionEvidence']=[f['id'] for f in invalid]
    elif eligible: state='reviewed';reason='source-verified-despite-ai-uncertainty' if not agreement(p,r) else 'eligible-awaiting-independent-validation'
    else:
        state='not_distributed';reasons=[]
        if not reading_facts: reasons.append('reading-evidence-insufficient')
        if not supported: reasons.append('meaning-or-target-unresolved')
        if not agreement(p,r): reasons.append('independent-review-disagreement')
        if correction or (normalized and not normalization_proof): reasons.append('normalization-evidence-insufficient')
        reason=';'.join(reasons)
    # AI judgment alone never establishes a confirmed exclusion.
    db.execute('UPDATE candidates SET state=?,reason=?,decision=?,error=NULL WHERE id=?',(state,reason,canonical(decision),row['id']))

def select_pilot(db,n=2000):
    old=[tuple(r) for r in db.execute('SELECT candidate_id,stratum FROM pilot ORDER BY candidate_id')]
    if old and info(db,'pilotSelectorVersion')==2: return
    if old:
        if db.execute("SELECT COUNT(*) FROM candidates WHERE state!='queued' AND id IN (SELECT candidate_id FROM pilot)").fetchone()[0]: raise ValueError('Existing pilot is in progress; preserve its frozen selection')
        info(db,'previousPilot',{'selectorVersion':1,'cases':old,'frozenAt':info(db,'pilotFrozenAt')});db.execute('DELETE FROM pilot')
    db.execute("CREATE TEMP TABLE pilot_strata AS WITH ownership AS (SELECT DISTINCT m.candidate_id,o.source FROM origin_candidates m JOIN origins o ON o.id=m.origin_id ORDER BY m.candidate_id,o.source), owners AS (SELECT candidate_id,group_concat(source,',') sources FROM ownership GROUP BY candidate_id) SELECT c.id,json_array(c.old_status,c.old_categories,c.normalization,o.sources) stratum FROM candidates c JOIN owners o ON o.candidate_id=c.id")
    db.execute('CREATE INDEX temp.pilot_stratum ON pilot_strata(stratum,id)')
    groups=db.execute('SELECT stratum,COUNT(*) n FROM pilot_strata GROUP BY stratum').fetchall()
    allocations={g['stratum']:min(g['n'],max(1,n//max(1,len(groups)))) for g in groups}
    remaining=n-sum(allocations.values())
    while remaining>0:
        changed=False
        for g in sorted(groups,key=lambda g:(-g['n'],g['stratum'])):
            k=g['stratum']
            if allocations[k]<g['n'] and remaining: allocations[k]+=1;remaining-=1;changed=True
        if not changed: break
    if remaining<0: raise ValueError('Pilot has too many strata; increase pilot size')
    for g in groups:
        for row in db.execute('SELECT id FROM pilot_strata WHERE stratum=? ORDER BY id LIMIT ?',(g['stratum'],allocations[g['stratum']])):
            db.execute('INSERT INTO pilot VALUES(?,?)',(row[0],g['stratum']))
    db.execute('DROP TABLE pilot_strata')
    info(db,'pilotSelectorVersion',2);info(db,'pilotFrozenAt',time.time());db.commit()

def capacity_failure(ex):
    return (isinstance(ex,OSError) and (getattr(ex,'errno',None) in (28,122) or 'storage limit' in str(ex))) or (isinstance(ex,sqlite3.OperationalError) and any(t in str(ex).lower() for t in ('disk is full','database or disk is full')))

def retry_error(db,cid,ex):
    count=db.execute('SELECT error_count FROM candidates WHERE id=?',(cid,)).fetchone()[0]+1
    delay=min(3600,30*2**min(count,7))
    db.execute("UPDATE candidates SET state='error',error=?,error_count=?,next_retry=? WHERE id=?",(str(ex),count,time.time()+delay,cid))

@contextlib.contextmanager
def coordinator_lock(path):
    import fcntl
    p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.with_suffix('.worker.lock').open('a') as f:
        try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('Another research worker owns this ledger')
        try: yield
        finally: fcntl.flock(f,fcntl.LOCK_UN)

def _run(args,pilot=False):
    with connect(args.ledger) as db:
        cfg=pin_config(db,args);validate_models(cfg[0],cfg[3])
        if not info(db,'prepared') or not info(db,'bulkComplete'): raise ValueError('Prepare all inputs and complete mandatory bulk validation before inference')
        if pilot: select_pilot(db,args.pilot_size)
        if not pilot and info(db,'goldFrozen') is None: raise ValueError('Full research requires independently verified calibration/validation sets; use pilot first')
        filter=' AND EXISTS (SELECT 1 FROM pilot p WHERE p.candidate_id=c.id)' if pilot else ''
        total=0;batches=0;batch=args.batch_size or cfg[0]['batchSize'];start=time.monotonic();window=cfg[0].get('reviewWindow',128)
        proposing=True
        while True:
            ready_count=db.execute("SELECT COUNT(*) FROM candidates c WHERE state='ready_review'"+filter).fetchone()[0]
            queued_count=db.execute("SELECT COUNT(*) FROM candidates c WHERE (state='queued' OR (state='error' AND next_retry<=?))"+filter,(time.time(),)).fetchone()[0]
            if ready_count>=window or (ready_count and not queued_count): proposing=False
            if not ready_count: proposing=True
            if not queued_count and not ready_count:
                remaining=db.execute("SELECT COUNT(*) FROM candidates c WHERE state IN ('queued','error')"+filter).fetchone()[0]
                if not remaining: break
                emit({'waitingForRetry':remaining,'processedThisRun':total});time.sleep(10);continue
            selector="(state='queued' OR (state='error' AND next_retry<=?))" if proposing else "state='ready_review'"
            params=(time.time(),batch) if proposing else (batch,)
            rows=[dict(r) for r in db.execute("SELECT * FROM candidates c WHERE "+selector+filter+" ORDER BY id LIMIT ?",params)]
            if not rows: proposing=not proposing;continue
            batches+=1
            if proposing:
                try: p=inference(db,args,rows,'proposer',cfg)
                except Exception as ex:
                    if capacity_failure(ex): raise
                    emit({'phase':'proposal-error','error':str(ex),'retryable':True})
                    if args.max_batches and batches>=args.max_batches: break
                    continue
                ready=[]
                for row in rows:
                    try:
                        facts=fact_rows(db,row);cats={c for f in facts if f['kind']=='meaning' for c in json.loads(f['categories'])}
                        insufficient=not any(f['kind']=='reading' for f in facts) or not cats
                        proposed={v['category'] for v in p[row['id']]['roles']}
                        needs_research=insufficient or row['normalization']!='unchanged' or len(proposed)>1 or row['reason']=='additional-research-for-blind-disagreement' or (row['old_status']=='accepted' and set(row['old_categories'].split(','))!=proposed)
                        if needs_research:
                            for research_round in range(row['research_round']+1,3): research(db,args,row,p[row['id']],research_round)
                        ready.append(row)
                    except Exception as ex:
                        retry_error(db,row['id'],ex);db.commit();emit({'phase':'research-error','candidateId':row['id'],'error':str(ex),'retryable':True})
                        if capacity_failure(ex): raise
                if ready:
                    try:
                        p=inference(db,args,ready,'proposer',cfg)
                        for row in ready: db.execute("UPDATE candidates SET state='ready_review',decision=?,error=NULL WHERE id=?",(canonical({'proposal':p[row['id']]}),row['id']))
                        db.commit()
                    except Exception as ex:
                        if capacity_failure(ex): raise
                        emit({'phase':'proposal-refresh-error','error':str(ex),'retryable':True})
            else:
                try:
                    r=inference(db,args,rows,'reviewer',cfg)
                    for row in rows:
                        p=json.loads(row['decision'])['proposal']
                        current=db.execute('SELECT research_round FROM candidates WHERE id=?',(row['id'],)).fetchone()[0]
                        if not agreement(p,r[row['id']]) and current<2:
                            db.execute("UPDATE candidates SET state='queued',decision=NULL,reason='additional-research-for-blind-disagreement' WHERE id=?",(row['id'],))
                        else:
                            import bulk as reference_bulk
                            reference_bulk.check_normalization_row(db,Evidence(db,args),row,fact_rows)
                            decide(db,row,p,r[row['id']]);total+=1
                    db.commit()
                except Exception as ex:
                    if capacity_failure(ex): raise
                    emit({'phase':'review-error','error':str(ex),'retryable':True})
            emit({'phase':'proposal' if proposing else 'review','processedThisRun':total,'batches':batches,'seconds':round(time.monotonic()-start,2)})
            if args.max_batches and batches>=args.max_batches: break
        info(db,'lastRun',{'seconds':time.monotonic()-start,'processed':total,'pilot':pilot});db.commit()
    status(args)

def run(args,pilot=False):
    started=time.time()
    with connect(args.ledger) as db:
        db.execute('CREATE TABLE IF NOT EXISTS execution_runs(id INTEGER PRIMARY KEY,action TEXT,configuration_sha256 TEXT,started REAL,ended REAL,state TEXT,error TEXT)')
        db.execute("UPDATE execution_runs SET ended=?,state='interrupted' WHERE ended IS NULL",(started,))
        rid=db.execute('INSERT INTO execution_runs(action,configuration_sha256,started,state) VALUES(?,?,?,?)',('pilot' if pilot else 'run',digest(canonical(configuration(args)[-1])),started,'running')).lastrowid
        db.commit()
    error=None
    try: return _run(args,pilot)
    except BaseException as ex: error=str(ex);raise
    finally:
        with connect(args.ledger) as db:
            filt=' AND id IN (SELECT candidate_id FROM pilot)' if pilot else ''
            pending=db.execute("SELECT COUNT(*) FROM candidates WHERE state IN ('queued','error','ready_review')"+filt).fetchone()[0]
            state='failed' if error is not None else ('paused' if pending else 'review-finished')
            db.execute('UPDATE execution_runs SET ended=?,state=?,error=? WHERE id=?',(time.time(),state,error,rid));db.commit()

def status(args):
    with connect(args.ledger) as db:
        has_runs=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='execution_runs'").fetchone()
        last=db.execute('SELECT * FROM execution_runs ORDER BY id DESC LIMIT 1').fetchone() if has_runs else None
        run_info=dict(last) if last else None
        if run_info: run_info['elapsedSeconds']=round((run_info['ended'] or time.time())-run_info['started'],2)
        value={'prepared':info(db,'prepared'),'sourceRows':db.execute('SELECT COUNT(*) FROM origins').fetchone()[0],
               'candidates':db.execute('SELECT COUNT(*) FROM candidates').fetchone()[0],
               'states':dict(db.execute('SELECT state,COUNT(*) FROM candidates GROUP BY state').fetchall()),
               'facts':dict(db.execute('SELECT kind,COUNT(*) FROM facts WHERE active=1 GROUP BY kind').fetchall()),
               'archivedFacts':db.execute('SELECT COUNT(*) FROM facts WHERE active=0').fetchone()[0],
               'pilot':dict(db.execute('SELECT c.state,COUNT(*) FROM candidates c JOIN pilot p ON p.candidate_id=c.id GROUP BY c.state').fetchall()),
               'failedRequests':db.execute('SELECT COUNT(*) FROM attempts WHERE result=\'error\'').fetchone()[0],
               'lastRun':info(db,'lastRun'),'execution':run_info,
               'pilotClassificationAccuracy':'Independent gold inspection not recorded; counts are not precision'}
        emit(value);return value

def explain(args):
    with connect(args.ledger) as db:
        query='SELECT * FROM candidates WHERE '+('id=?' if args.id else 'surface=?')
        for row in db.execute(query,(args.id or args.surface,)):
            emit({'candidate':dict(row),'origins':[dict(r) for r in db.execute('SELECT o.* FROM origins o JOIN origin_candidates c ON c.origin_id=o.id WHERE c.candidate_id=?',(row['id'],))],
                  'facts':fact_rows(db,row),'attempts':[dict(r) for r in db.execute('SELECT * FROM attempts WHERE candidate_id=?',(row['id'],))],
                  'inferences':[dict(r) for r in db.execute('SELECT role,model_digest,prompt_sha256,output,error FROM inferences WHERE candidate_id=?',(row['id'],))]})

def source_text(path):
    data=pathlib.Path(path).read_bytes()
    if data.startswith(b'\x1f\x8b'): data=gzip.decompress(data)
    elif data.startswith(b'PK\x03\x04'):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names=[n for n in z.namelist() if not n.endswith('/') and not n.startswith('__MACOSX/')]
            if len(names)!=1: raise ValueError('Gold document ZIP has multiple files')
            data=z.read(names[0])
    if len(data)>512*1024*1024: raise ValueError('Oversized expanded evidence document')
    text=data.decode('utf-8',errors='strict')
    try: return canonical(json.loads(text))
    except json.JSONDecodeError: return text

def confidence_lower(correct,n,alpha=.05):
    # Exact one-sided Clopper-Pearson, binomial upper-tail inversion. No external stats library.
    if not n or not correct: return 0.0
    def tail(p):
        if p<=0: return 0.0
        if p>=1: return 1.0
        terms=[math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)+k*math.log(p)+(n-k)*math.log1p(-p) for k in range(correct,n+1)]
        largest=max(terms);return math.exp(largest)*sum(math.exp(t-largest) for t in terms)
    lo,hi=0.0,1.0
    for _ in range(60):
        mid=(lo+hi)/2
        if tail(mid)<alpha: lo=mid
        else: hi=mid
    return (lo+hi)/2

def validate_gold(db,args):
    """Ground truth must have bound quotations and document hashes; model output isn't accepted."""
    path=pathlib.Path(args.gold);value=json.loads(path.read_text());surface_seen={};target_seen={};counts={};cases_seen=set()
    for item in value['cases']:
        required={'candidateId','split','categories','target','readingEvidence','meaningEvidence','eligible'}
        if set(item)!=required or item['split'] not in ('calibration','validation'): raise ValueError('Invalid gold fields')
        if not isinstance(item['eligible'],bool) or not item['target'] or not item['categories'] or len(set(item['categories']))!=len(item['categories']) or not set(item['categories'])<=set(c['id'] for c in configuration(args)[1]['categories']): raise ValueError('Gold labels/type invalid')
        row=db.execute('SELECT * FROM candidates WHERE id=?',(item['candidateId'],)).fetchone()
        if row is None: raise ValueError('Gold candidate not in inputs')
        key=(row['surface'],item['target'],item['split'])
        if key in cases_seen: raise ValueError('Duplicate surface/target gold case')
        cases_seen.add(key)
        if (row['surface'] in surface_seen and surface_seen[row['surface']]!=item['split']) or (item['target'] in target_seen and target_seen[item['target']]!=item['split']): raise ValueError('Calibration/validation surface or entity leakage')
        surface_seen[row['surface']]=item['split'];target_seen[item['target']]=item['split']
        for field in ('readingEvidence','meaningEvidence'):
            for evidence in item[field]:
                if set(evidence)!= {'documentId','quotation','sha256'}: raise ValueError('Gold provenance fields invalid')
                doc=db.execute('SELECT * FROM documents WHERE id=?',(evidence['documentId'],)).fetchone()
                if doc is None or sha(doc['path'])!=evidence['sha256'] or doc['sha256']!=evidence['sha256']: raise ValueError('Gold source checksum mismatch')
                text=source_text(doc['path'])
                if not evidence['quotation'] or evidence['quotation'] not in text: raise ValueError('Gold quotation absent from source')
        if not item['readingEvidence'] or not item['meaningEvidence']: raise ValueError('Gold needs independently checked reading and meaning sources')
        observed=fact_rows(db,dict(row))
        for field,kinds in [('readingEvidence',('reading',) if item['eligible'] else ('reading','context')),('meaningEvidence',('meaning','context'))]:
            for ref in item[field]:
                related=[f for f in observed if f['document_id']==ref['documentId'] and f['kind'] in kinds and (field=='readingEvidence' or f['target']==item['target'])]
                if not related: raise ValueError('Gold source is not bound to this input pair/target')
        for cat in item['categories']: counts[(cat,item['split'])]=counts.get((cat,item['split']),0)+1
    for cat in configuration(args)[1]['categories']:
        minimum=100 if cat['core'] else 50
        if any(counts.get((cat['id'],split),0)<minimum for split in ('calibration','validation')): raise ValueError('Insufficient gold examples: '+cat['id'])
    return value,sha(path)

def freeze_gold(args):
    with connect(args.ledger) as db:
        pin_config(db,args);value,h=validate_gold(db,args)
        if db.execute('SELECT COUNT(*) FROM candidates WHERE state!=\'queued\' AND id NOT IN (SELECT candidate_id FROM pilot)').fetchone()[0]: raise ValueError('Gold must be frozen before full run')
        info(db,'goldFrozen',{'sha256':h,'cases':value['cases']});db.commit();emit({'goldFrozen':h,'cases':len(value['cases'])})

def finalize(args):
    import distribution
    with connect(args.ledger) as db:
        cfg=pin_config(db,args);active,counts=distribution.active_categories(db,cfg[1])
        gate=distribution.precision(db,info,confidence_lower,canonical,active)
        acceptance=info(db,'acceptance')
        if not acceptance or not all(acceptance.get(k) for k in ('categoryReviews','nonDistributedReview','conversionRegression','linuxBinaryParity','zipVerified')): raise ValueError('Required independent reviews/conversion/Linux/ZIP records missing')
        for row in db.execute("SELECT id,decision FROM candidates WHERE state='reviewed'").fetchall():
            categories={v['category'] for v in json.loads(row['decision'])['roles']} & set(active)
            db.execute('UPDATE candidates SET state=?,reason=? WHERE id=?',('adopted' if categories else 'not_distributed','verified-reading-semantics-eligibility' if categories else 'category-publication-criteria-not-met',row['id']))
        info(db,'finalized',{'validation':gate,'configuration':digest(canonical(cfg[-1])),'acceptance':acceptance,'activeCategories':active});db.commit();emit(info(db,'finalized'))

def export(args):
    import distribution
    with connect(args.ledger) as db:
        pin_config(db,args);distribution.export(db,args,configuration,info,confidence_lower,canonical,digest,sha,emit)

def accept(args):
    import distribution
    with connect(args.ledger) as db:
        pin_config(db,args);distribution.record_acceptance(db,args,info,sha,canonical,emit,source_text)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','bulk','pilot','run','status','explain','freeze-gold','accept','finalize','export'])
    p.add_argument('--ledger',default='build/research/ledger.sqlite');p.add_argument('--config',default=str(DEFAULT_CONFIG))
    p.add_argument('--source-dir',default='src/main/bin');p.add_argument('--base-dir')
    p.add_argument('--audit',default='build/research/baseline-v2/audit.tsv.gz');p.add_argument('--snapshot',default='build/dictionary-metadata/snapshot.sqlite')
    p.add_argument('--postal-zip');p.add_argument('--documents',default='build/research/documents');p.add_argument('--jmnedict');p.add_argument('--jmdict')
    p.add_argument('--mozc-commit',default='c7538e6f8ee56ff94789494106ad5d6d658cd4f6')
    p.add_argument('--acceptance');p.add_argument('--candidate',action='store_true');p.add_argument('--id');p.add_argument('--surface');p.add_argument('--gold');p.add_argument('--output')
    p.add_argument('--batch-size',type=int);p.add_argument('--pilot-size',type=int,default=2000);p.add_argument('--max-batches',type=int)
    args=p.parse_args(argv)
    if args.batch_size is not None and not 1<=args.batch_size<=16: p.error('batch-size must be 1..16')
    if args.max_batches is not None and args.max_batches<1: p.error('max-batches must be positive')
    with (contextlib.nullcontext() if args.action in ('status','explain') else coordinator_lock(args.ledger)):
        if args.action=='prepare': prepare(args)
        elif args.action=='bulk': bulk(args)
        elif args.action in ('pilot','run'): run(args,args.action=='pilot')
        elif args.action=='status': status(args)
        elif args.action=='explain':
            if not args.id and not args.surface: p.error('explain needs --id or --surface')
            explain(args)
        elif args.action=='freeze-gold': freeze_gold(args)
        elif args.action=='accept': accept(args)
        elif args.action=='finalize': finalize(args)
        elif args.action=='export': export(args)

if __name__=='__main__':
    try: main()
    except Exception as ex: print('research: '+str(ex),file=sys.stderr);sys.exit(2)
