#!/usr/bin/env python3
"""Resumable local-only dictionary research. No third-party Python dependencies.
Operational failures remain errors. AI outputs never create reading evidence.
"""
import argparse, contextlib, csv, gzip, hashlib, html, io, json, math, os, pathlib
import re, socket, sqlite3, sys, time, unicodedata, urllib.parse, urllib.request, urllib.error, zipfile
import xml.etree.ElementTree as ET
sys.modules.setdefault("worker", sys.modules[__name__])

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
CREATE INDEX fact_status ON facts(active,kind);
CREATE INDEX fact_document ON facts(document_id);
CREATE TABLE attempts(id INTEGER PRIMARY KEY,candidate_id TEXT,round INTEGER,url TEXT,result TEXT NOT NULL,error TEXT,document_id TEXT);
CREATE TABLE inferences(id INTEGER PRIMARY KEY,candidate_id TEXT,role TEXT,cache_key TEXT,model_digest TEXT,prompt_sha256 TEXT,input_sha256 TEXT,output TEXT,seconds REAL,tokens INTEGER,error TEXT,created REAL);
CREATE INDEX inference_reuse ON inferences(candidate_id,role,cache_key);
CREATE TABLE pilot(candidate_id TEXT PRIMARY KEY,stratum TEXT NOT NULL);
CREATE TABLE evaluations(id TEXT PRIMARY KEY,body TEXT NOT NULL);
CREATE TABLE model_calls(id INTEGER PRIMARY KEY,role TEXT,model_digest TEXT,configuration_sha256 TEXT,input_sha256 TEXT,request BLOB,response BLOB,aliases TEXT,error TEXT,seconds REAL,created REAL);
CREATE TABLE configuration_history(sha256 TEXT PRIMARY KEY,body TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE decision_history(id INTEGER PRIMARY KEY,candidate_id TEXT,state TEXT,reason TEXT,decision TEXT,change TEXT,created REAL);
CREATE INDEX attempt_cache ON attempts(url,result,id);
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
def bound_reading(x):
    # Wikidata writes Japanese family/given-name readings with a display space;
    # it separates name components and does not change the pronunciation.
    return re.sub(r'\s+','',reading(x))
def pair(y,s): return reading(y),unicodedata.normalize('NFKC',s)
def candidate_id(y,s,l,r): return digest(canonical([y,s,l,r]))[:32]
def emit(x): print(canonical(x),flush=True)
class LedgerConnection(sqlite3.Connection):
    def __exit__(self,*args):
        try: return super().__exit__(*args)
        finally: self.close()

def connect(path,readonly=False):
    target="file:"+str(pathlib.Path(path).resolve())+"?mode=ro" if readonly else path
    db=sqlite3.connect(target,uri=readonly,timeout=30,factory=LedgerConnection);db.row_factory=sqlite3.Row
    if readonly: return db
    db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA journal_mode=WAL')
    columns={r[1] for r in db.execute('PRAGMA table_info(candidates)')}
    if columns:
        if 'error_count' not in columns: db.execute('ALTER TABLE candidates ADD COLUMN error_count INTEGER NOT NULL DEFAULT 0')
        if 'next_retry' not in columns: db.execute('ALTER TABLE candidates ADD COLUMN next_retry REAL NOT NULL DEFAULT 0')
        db.execute('CREATE TABLE IF NOT EXISTS model_calls(id INTEGER PRIMARY KEY,role TEXT,model_digest TEXT,configuration_sha256 TEXT,input_sha256 TEXT,request BLOB,response BLOB,aliases TEXT,error TEXT,seconds REAL,created REAL)')
        db.execute('CREATE TABLE IF NOT EXISTS configuration_history(sha256 TEXT PRIMARY KEY,body TEXT NOT NULL,created REAL NOT NULL)')
        if 'active' not in {r[1] for r in db.execute('PRAGMA table_info(facts)')}: db.execute('ALTER TABLE facts ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
        db.execute('CREATE INDEX IF NOT EXISTS fact_document ON facts(document_id)')
        db.execute('CREATE INDEX IF NOT EXISTS fact_status ON facts(active,kind)')
        db.execute('CREATE INDEX IF NOT EXISTS attempt_cache ON attempts(url,result,id)')
        db.execute('CREATE TABLE IF NOT EXISTS decision_history(id INTEGER PRIMARY KEY,candidate_id TEXT,state TEXT,reason TEXT,decision TEXT,change TEXT,created REAL)')
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
    identity={'models':models,'taxonomy':taxonomy,'researchParserVersion':4,'prompts':{k:digest(v) for k,v in prompts.items()},'stages':{'onlineReadingParser':4,'directRules':7,'publication':2}}
    return models,taxonomy,prompts,endpoint,identity

def pin_config(db,args):
    import direct_review
    cfg=configuration(args);stored=info(db,'configuration')
    if stored is not None and stored!=cfg[-1]:
        info(db,'previousConfiguration',stored)
        direct_review.invalidate_configuration(db,stored,cfg[-1])
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
        self.storage=storage
    def document_usage(self):
        if self.storage not in DOCUMENT_USAGE:
            # Load only when writing a new file; most direct-review imports add facts for saved documents.
            prefix=self.storage+os.sep
            row=self.db.execute("SELECT COALESCE(SUM(bytes),0) FROM (SELECT path,MAX(bytes) AS bytes FROM documents WHERE substr(path,1,?)=? GROUP BY path)",(len(prefix),prefix)).fetchone()
            DOCUMENT_USAGE[self.storage]=row[0]
        return DOCUMENT_USAGE[self.storage]
    def save(self,url,revision,data,license):
        h=digest(data);did=digest(canonical([url,revision,h]))[:32];p=self.root/h
        if not p.exists():
            total=self.document_usage()
            if total+len(data)>self.limit: raise OSError('Document storage limit exceeded; no candidate decision changed')
            tmp=self.root/(h+'.tmp');tmp.write_bytes(data);os.replace(tmp,p);DOCUMENT_USAGE[self.storage]+=len(data)
        self.db.execute('INSERT OR IGNORE INTO documents VALUES(?,?,?,?,?,?,?)',(did,url,revision,h,str(p.resolve()),len(data),license))
        return did
    def fact(self,y,s,kind,categories,target,doc,body,*,append_inspection=False):
        if append_inspection and (kind!='context' or body.get('source')!='Wikidata' or not body.get('classPaths') or not body.get('componentFacts')):
            raise ValueError('Append-only inspection requires a bound class-path context')
        y,s=pair(y,s);value=(y,s,kind,canonical(sorted(categories)),target,doc,canonical(body));fid=digest(canonical(value))[:32]
        inserted=self.db.execute('INSERT OR IGNORE INTO facts(id,reading,surface,kind,categories,target,document_id,body) VALUES(?,?,?,?,?,?,?,?)',(fid,*value)).rowcount
        inserted+=self.db.execute('UPDATE facts SET active=1 WHERE id=? AND active=0',(fid,)).rowcount
        if inserted and not append_inspection:
            self.db.execute("INSERT INTO decision_history(candidate_id,state,reason,decision,change,created) SELECT id,state,reason,decision,'evidence-changed',? FROM candidates WHERE surface=? AND (reading=? OR ?='') AND decision IS NOT NULL",(time.time(),s,y,y))
            self.db.execute("UPDATE candidates SET state=CASE WHEN error IS NOT NULL AND state IN ('blocked','error') THEN state ELSE 'queued' END,reason='evidence-changed',decision=NULL WHERE surface=? AND (reading=? OR ?='') AND decision IS NOT NULL",(s,y,y))
            self.db.execute("DELETE FROM info WHERE key IN ('finalized','acceptance')")
        return fid
    def fetch(self,url,cid,round,revision='retrieved',license='source-specific'):
        try: check_public_url(url)
        except Exception as ex:
            self.db.execute('INSERT INTO attempts(candidate_id,round,url,result,error) VALUES(?,?,?,?,?)',(cid,round,url,'error',str(ex)))
            self.db.commit();raise
        old=self.db.execute("SELECT d.* FROM attempts a JOIN documents d ON d.id=a.document_id WHERE a.url=? AND a.result='success' AND NOT EXISTS (SELECT 1 FROM attempts bad WHERE bad.document_id=a.document_id AND bad.result='invalid-api') ORDER BY a.id DESC LIMIT 1",(url,)).fetchone()
        if old:
            p=pathlib.Path(old['path'])
            if sha(p)!=old['sha256']: raise ValueError('Cached document checksum mismatch')
            data=p.read_bytes()
            try: validate_mediawiki_payload(url,data)
            except (ValueError,OSError) as ex:
                self.db.execute('INSERT INTO attempts(candidate_id,round,url,result,error,document_id) VALUES(?,?,?,?,?,?)',(cid,round,url,'invalid-api',str(ex),old['id']))
                self.db.commit()
            else:
                self.db.execute('INSERT INTO attempts(candidate_id,round,url,result,document_id) VALUES(?,?,?,?,?)',(cid,round,url,'success',old['id']))
                return old['id'],data
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
            validate_mediawiki_payload(url, data)
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

def validate_mediawiki_payload(url, data):
    # HTTP 200 can still carry a temporary API failure. Preserve the raw document,
    # but do not cache that response as a successfully usable research result.
    u=urllib.parse.urlparse(url)
    if u.hostname not in ('ja.wikipedia.org','www.wikidata.org') or u.path!='/w/api.php': return
    value=json.loads(data)
    if isinstance(value,dict) and 'error' in value:
        failure=value['error'];code=failure.get('code') if isinstance(failure,dict) else None
        message='MediaWiki API failure: '+canonical(failure)
        if code in ('maxlag','ratelimited','readonly','internal_api_error_DBConnectionError'): raise OSError(message)
        raise ValueError(message)

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
        import direct_review
        direct_review.retire_provider(db,'Mozc',name)
        did=e.save('https://github.com/google/mozc/blob/'+args.mozc_commit+'/src/data/dictionary_oss/'+name,args.mozc_commit,path.read_bytes(),'Mozc BSD-3-Clause')
        with path.open() as f:
            for line,raw in enumerate(f,1):
                cells=raw.rstrip('\n').split('\t')
                if len(cells)>=5 and pair(cells[0],cells[4]) in wanted:
                    e.fact(cells[0],cells[4],'reading',[],name+':'+str(line),did,{'source':'Mozc','line':line,'reading':cells[0],'surface':cells[4]})
        info(db,key,version);db.commit()

NAME_TYPES={'surname':'person','given':'person','fem':'person','masc':'person','person':'person',
            'company':'organization','organization':'organization','org':'organization','group':'organization','place':'place',
            'station':'station','product':'product','work':'work','doc':'work','ev':'event','char':'character',
            'dei':'character','ship':'transport'}

def name_categories(types):
    cats={NAME_TYPES[t] for t in types if t in NAME_TYPES}
    if 'person' in cats and set(types)&{'fict','myth','leg','dei'}:
        cats.remove('person');cats.add('character')
    return sorted(cats)

def import_jmnedict(db,args,e):
    path=pathlib.Path(args.jmnedict);version=sha(path)
    if info(db,'import:JMnedict')=={'sha256':version,'parser':5}: return
    wanted={pair(r[0],r[1]) for r in db.execute('SELECT reading,surface FROM candidates')}
    import rescue
    wanted_surfaces=rescue.targets(db)
    data=path.read_bytes();did=e.save('https://www.edrdg.org/pub/Nihongo/JMnedict.xml.gz',version,data,'EDRDG / CC-BY-SA-4.0')
    import direct_review
    direct_review.retire_provider(db,'JMnedict')
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
                        cats=name_categories(ts)
                        e.fact(y,s,'meaning',cats,'JMnedict:'+seq+':'+str(i),did,{**evidence,'nameTypes':ts,'sense':i})
                    hits+=1
            node.clear();root.clear()
            if hits and hits%10000==0: db.commit()
    info(db,'import:JMnedict',{'sha256':version,'parser':5});db.commit();emit({'phase':'JMnedict','matchedPairs':hits,'sha256':version})

def import_jmdict(db,args,e):
    """Consume schema3 pair-restricted senses only after checking their raw entry constraints."""
    path=pathlib.Path(args.jmdict);version=sha(path)
    if info(db,'import:JMdict')=={'sha256':version,'policy':6}: return
    snapshot=sqlite3.connect('file:'+str(pathlib.Path(args.snapshot).resolve())+'?mode=ro',uri=True)
    facts={}
    for y,s,body in snapshot.execute('SELECT reading,surface,body FROM lexical_details'):
        b=json.loads(body)
        if b.get('source')=='JMdict' and b.get('version')==version:
            facts.setdefault(b['entryId'].split(':')[0],[]).append((y,s,b))
    did=e.save('https://www.edrdg.org/pub/Nihongo/JMdict_e.gz',version,path.read_bytes(),'EDRDG / CC-BY-SA-4.0')
    checked=0
    import direct_review
    direct_review.retire_provider(db,'JMdict')
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
                pos=set()
                for prior in node.findall('sense')[:index+1]:
                    pos=tags(prior,'pos') or pos
                misc=tags(sense,'misc')
                fields=tags(sense,'field');cats=set()
                for name,cat in NAME_TYPES.items():
                    if name in misc: cats.add(cat)
                evidence={**b,'pos':sorted(pos),'misc':sorted(misc),'fields':sorted(fields),'categories':sorted(cats),'classificationPolicy':6,'re_restr':[n.text for r in readings for n in r.findall('re_restr')],
                          'stagk':[n.text for n in sense.findall('stagk')],'stagr':[n.text for n in sense.findall('stagr')]}
                e.fact(y,s,'reading',[],b['entryId'],did,evidence)
                e.fact(y,s,'meaning',cats,'JMdict:'+b['entryId']+':sense:'+str(index+1),did,evidence)
                checked+=1
            node.clear();root.clear()
    snapshot.close();info(db,'import:JMdict',{'sha256':version,'policy':6});db.commit();emit({'phase':'JMdict','rawConstraintsChecked':checked})

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

FACT_ROWS_SQL = "SELECT f.*,d.url,d.revision,d.sha256 FROM facts f INDEXED BY fact_pair JOIN documents d ON d.id=f.document_id WHERE f.active=1 AND (f.reading=? OR f.reading='') AND f.surface=? ORDER BY f.id"

def fact_rows(db,row):
    y,s=pair(row['reading'],row['surface'])
    return [dict(r) for r in db.execute(FACT_ROWS_SQL,(y,s))]

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
    # Wikidata type facts classify only the exact Japanese label whose reading is
    # independently bound to the same item. A homograph's dictionary reading is
    # not enough to turn an entity type into a classification.
    for fact in selected:
        body=json.loads(fact['body'])
        if body.get('source')=='Wikidata' and body.get('id')==role['target'] and (
                'Q5' in body.get('types',[]) or 'Q95074' in body.get('types',[])):
            name=fact['surface']; bound=body.get('nameBoundReadings',{}).get(name,[])
            if not bound and name in (body.get('label'),body.get('title')):
                bound=body.get('primaryReadings',[])
            if not bound or not any(g['kind']=='reading' and g['target']==role['target'] and
                       g['surface']==name and any(bound_reading(v)==bound_reading(g['reading']) for v in bound) for g in facts):
                return False
        if (body.get('source')=='JMnedict' and
                ((role.get('category')=='place' and jmnedict_geographic_fact(fact)) or
                 (role.get('category')=='character' and jmnedict_mythic_character_fact(fact))) and
                not jmnedict_entry_reading_supported(fact,facts)):
            return False
    # A pair of agreeing models cannot turn an explicit fictional-person tag
    # into a real person, or add an ordinary-word sense to a name-only entry.
    for fact in facts:
        if fact['target']!=role['target'] or fact['kind']!='meaning': continue
        body=json.loads(fact['body'])
        if body.get('source')!='JMnedict': continue
        allowed=set(name_categories(body.get('nameTypes',[])))
        if 'place' in allowed: allowed.update(('facility','station'))
        if 'product' in allowed and 'programming language' in canonical(body.get('translations',[])).lower(): allowed.add('technical')
        if role.get('category')=='general' or (allowed and role.get('category') not in allowed): return False
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
            if named and (not readings or any(bound_reading(v)==bound_reading(g['reading']) for v in readings for g in facts if g['kind']=='reading')): return True
        if b.get('source')=='Wikipedia':
            def binds_page_reading(g):
                if g['kind']!='reading' or g['target']!=f['target'] or g['surface']!=f['surface']:
                    return False
                if g['document_id']==f['document_id']:
                    return True
                rb=json.loads(g['body']); ra=rb.get('acquisition',{}); fa=b.get('acquisition',{})
                return (rb.get('source')=='explicit-name-reading'
                        and str(rb.get('revision',''))==str(b.get('revision',''))
                        and bool(ra.get('sourceDumpSha256'))
                        and ra.get('sourceDumpSha256')==fa.get('sourceDumpSha256')
                        and str(ra.get('sourcePageId',''))==str(fa.get('sourcePageId','')))
            if b.get('title')==f['surface'] or any(binds_page_reading(g) for g in facts): return True
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
    depth=0;out=[]
    # Process template delimiters as tokens rather than scanning every article
    # character in Python. Full-body reading search remains separate.
    for token in re.split(r'(\{\{|\}\})',content):
        if token=='{{': depth+=1
        elif token=='}}' and depth: depth-=1
        elif not depth: out.append(token)
    text=''.join(out);text=re.sub(r'<!--.*?-->','',text,flags=re.S)
    text=re.sub(r'\[\[([^]\n]+)\]\]',lambda m:m.group(1).split('|')[-1],text)
    return text.split('\n==')[0][:8000]

def literal_name_reading_bindings(text):
    """Return the literal whole-name readings used by online and dump parsers."""
    kana=r'([ぁ-ゖァ-ヶー 　・]+(?:[、,][ぁ-ゖァ-ヶー 　・]+)*)(?=[、,)）])'
    # Preserve the WHOLE written name. Searching for the input as a substring
    # would attach 井上太郎's pronunciation to the separate name 太郎.
    marked=r"'''([^\n]{1,256}?)'''\s*[（(]"+kana
    plain=html.unescape(re.sub(r'<[^>]+>','',re.sub(marked,' ',text))).replace("''",'')
    bindings=[(m[1],m[2],m[0]) for m in re.finditer(marked,text[:12000])]
    names=r"(?<![\w々〆])([\w々〆ー・'’=＝\- 　]{1,256})\s*[（(]"+kana
    bindings.extend((m[1].strip(),m[2],m[0]) for m in re.finditer(names,plain[:12000]))
    result=[]
    for name,readings,quote in bindings:
        for i,explicit in enumerate(re.split('[、,]',readings)):
            if i: explicit=re.sub(r'^(?:または|もしくは)','',explicit.strip())
            result.append((name,explicit.replace(' ','').replace('　','').replace('・',''),quote))
    return result+explicit_reading_bindings(text)

def extract_readings(db,e,row,did,text,target,canonical_name=None):
    """Only explicit name-bound readings. No text-to-reading model or alias Cartesian product."""
    s=row['surface']
    for name,y,quote in literal_name_reading_bindings(text):
        if same_name(name,s) and reading(y)==reading(row['reading']):
            e.fact(row['reading'],s,'reading',[],target,did,{'source':'explicit-name-reading','quotation':quote,'name':name,'reading':y})
    if all('ぁ'<=c<='ゖ' or 'ァ'<=c<='ヶ' or c=='ー' for c in s) and reading(s)==reading(row['reading']) and (canonical_name or target)==s:
        e.fact(row['reading'],s,'reading',[],target,did,{'source':'attested-canonical-kana','name':s})

def same_name(a,b):
    # Japanese family/given-name spacing is display style, not a shorter alias.
    def normalized(value):
        value=unicodedata.normalize('NFKC',value)
        return re.sub(r'(?<=[\u3040-\u30ff\u3400-\u9fff々]) +(?=[\u3040-\u30ff\u3400-\u9fff々])','',value)
    return normalized(a)==normalized(b)

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
    return bool(first and same_name(first[1],surface))

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
            alias_declared=any(m[2].strip()==row['surface'] for m in re.finditer(r'\|\s*(別名|芸名|名義|通称|名前)\s*=\s*([^\n|}]+)',content))
            reading_target=page.get('pageprops',{}).get('wikibase_item',title) if primary or alias_declared else title+'#mentioned-name:'+row['surface']
            extract_readings(db,e,row,did,content,reading_target,canonical_name=row['surface'] if primary else title)
            # Kana aliases need an explicit name field, not a search-alias match.
            if row['surface'] and all('ぁ'<=c<='ゖ' or 'ァ'<=c<='ヶ' or c=='ー' for c in row['surface']) and reading(row['surface'])==reading(row['reading']):
                for field in re.finditer(r'\|\s*(別名|芸名|名義|通称|名前)\s*=\s*([^\n|}]+)',content):
                    name=field.group(2).strip().replace("'''",'')
                    if name==row['surface']:
                        target=page.get('pageprops',{}).get('wikibase_item',title)
                        e.fact(row['reading'],row['surface'],'reading',[],target,did,{'source':'attested-canonical-kana','name':name,'field':field.group(1),'quotation':field.group(0),'revision':rev['revid']})
            # Only article-declared official links, never URLs invented by a model.
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

JM_NEDICT_GEOGRAPHICAL_TYPES={'bay','city','island','lake','mountain','mountain range','peninsula','river'}
JM_NEDICT_MYTHIC_CHARACTER_DESCRIPTIONS={
    'mother goddess of chinese mythology',
    'spiritual dragon in chinese mythology',
    'dragon-god in chinese mythology',
}

def _normalization_is_original(normalization):
    return isinstance(normalization,str) and (normalization=='unchanged' or normalization.startswith('original:'))

def _jmnedict_selected_sense(f):
    if f.get('kind')!='meaning':
        return None,None
    try:
        body=json.loads(f['body'])
        sense=body.get('sense');entry=str(body.get('entryId',''))
        translations=body.get('translations')
        if (not entry or type(sense) is not int or not isinstance(translations,list) or
                sense<0 or sense>=len(translations) or f.get('target')!=f'JMnedict:{entry}:{sense}'):
            return None,None
        selected=translations[sense]
        if not isinstance(selected,list):
            return None,None
        return body,[value.strip() for value in selected if isinstance(value,str) and value.strip()]
    except (KeyError,TypeError,ValueError):
        return None,None

def jmnedict_geographic_fact(f):
    body,translations=_jmnedict_selected_sense(f)
    if body is None or body.get('nameTypes')!=['place']:
        return False
    pattern=r'.+\((?:'+ '|'.join(re.escape(v) for v in sorted(JM_NEDICT_GEOGRAPHICAL_TYPES,key=len,reverse=True))+r')\)'
    return any(re.fullmatch(pattern,value,re.IGNORECASE) for value in translations)

def jmnedict_mythic_character_fact(f):
    body,translations=_jmnedict_selected_sense(f)
    if body is None or body.get('nameTypes')!=['myth']:
        return False
    pattern=r'.+\((?:'+ '|'.join(re.escape(v) for v in sorted(JM_NEDICT_MYTHIC_CHARACTER_DESCRIPTIONS,key=len,reverse=True))+r')\)'
    return any(re.fullmatch(pattern,value,re.IGNORECASE) for value in translations)

def jmnedict_entry_reading_supported(meaning,facts):
    body,_=_jmnedict_selected_sense(meaning)
    if body is None:
        return False
    entry=str(body['entryId']);target='JMnedict:'+entry
    for fact in facts:
        if (fact.get('kind')!='reading' or fact.get('target')!=target or
                fact.get('document_id')!=meaning.get('document_id') or
                pair(fact.get('reading',''),fact.get('surface',''))!=pair(meaning.get('reading',''),meaning.get('surface',''))):
            continue
        try:
            reading_body=json.loads(fact['body'])
        except (KeyError,TypeError,ValueError):
            continue
        if reading_body.get('source')!='JMnedict' or str(reading_body.get('entryId',''))!=entry:
            continue
        restrictions=reading_body.get('re_restr',[])
        if restrictions and not any(pair('',value)[1]==pair('',meaning['surface'])[1] for value in restrictions):
            continue
        return True
    return False

def direct_category_fact(f,category,normalization=None):
    if f['kind']=='context':
        b=json.loads(f['body'])
        if b.get('source')!='Wikidata' or b.get('id')!=f['target']:
            return False
        types=set(b.get('types',[]))
        # Prefer the explicit fictional-character type over the broader human type.
        if 'Q95074' in types:
            return category=='character'
        return 'Q5' in types and category=='person'
    if f['kind']!='meaning': return False
    b=json.loads(f['body']);source=b.get('source')
    if source=='Japan Post': return category=='place'
    # JMnedict place-name covers buildings too; it is not a precise place category.
    if source=='JMnedict':
        if category!='place' and category in name_categories(b.get('nameTypes',[])):
            return True
        if category not in ('place','character'):
            return False
        if category=='place':
            return _normalization_is_original(normalization) and jmnedict_geographic_fact(f)
        return _normalization_is_original(normalization) and jmnedict_mythic_character_fact(f)
    if source=='JMdict':
        if any(NAME_TYPES.get(t)==category for t in b.get('misc',[])):
            return True
        # XML constraints attest the pair and sense, not its taxonomy. Legacy
        # policy 4 assigned every unscoped noun to general and biological fields
        # to technical; those assignments require source review and validation.
        return False
    return False

def decide(db,row,p,r):
    facts=fact_rows(db,row);reading_facts=[f for f in facts if f['kind']=='reading'];byid={f['id']:f for f in facts}
    direct=set()
    for f in facts:
        categories=set(json.loads(f['categories']))
        if f['kind']=='context':
            for category in ('person','character'):
                if direct_category_fact(f,category,row['normalization']): categories.add(category)
        if f['kind']=='meaning' and json.loads(f['body']).get('source')=='JMnedict':
            for category in ('place','character'):
                if direct_category_fact(f,category,row['normalization']): categories.add(category)
        direct.update((category,f['target']) for category in categories if direct_category_fact(f,category,row['normalization']))
    ai_roles=p['roles'] if agreement(p,r) else []
    supported=[v for v in ai_roles if v['evidenceIds'] and all(i in byid for i in v['evidenceIds']) and target_supported(v,facts)]
    correction=any((v['reading'],v['surface'])!=(row['reading'],row['surface']) for v in p['corrections']+r['corrections'])
    # An uncertainty vote cannot overturn an explicit constrained lexical/postal fact.
    # Only facts rechecked against raw reference data participate; seed classifications do not.
    source_roles=[]
    for f in facts:
        cats=set(json.loads(f['categories']))
        if f['kind']=='context':
            for category in ('person','character'):
                if direct_category_fact(f,category,row['normalization']): cats.add(category)
        if f['kind']=='meaning' and json.loads(f['body']).get('source')=='JMnedict':
            for category in ('place','character'):
                if direct_category_fact(f,category,row['normalization']): cats.add(category)
        b=json.loads(f['body'])
        for category in cats:
            if direct_category_fact(f,category,row['normalization']):
                source_roles.append({'category':category,'target':f['target'],'sense':str(b.get('sense',b.get('entryId',b.get('row',''))))+':'+category,'evidenceIds':[f['id']],'method':'direct'})
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
    import direct_review
    return direct_review.mark_error(db,cid,ex)

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
    import direct_review
    with connect(args.ledger) as db:
        pin_config(db,args)
        direct_review.reparse_saved_readings(db,args)
        direct_review.repair_derived_proofs(db,args)
        code=direct_review.run(db,args,pilot)
    return code

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
            pending=db.execute("SELECT COUNT(*) FROM candidates WHERE state NOT IN ('reviewed','adopted','excluded_confirmed','not_distributed')"+filt).fetchone()[0]
            state='failed' if error is not None else ('paused' if pending else 'review-finished')
            db.execute('UPDATE execution_runs SET ended=?,state=?,error=? WHERE id=?',(time.time(),state,error,rid));db.commit()
        status(args)

def direct_reading_discoveries(db):
    baseline=pathlib.Path('build/research/pilot-bulk-baseline.json.gz')
    if not baseline.is_file(): return None
    try:
        value=json.loads(gzip.decompress(baseline.read_bytes()))
        # Report only immutable cohort-compatible baselines; never invent a zero.
        import direct_review
        return direct_review.reading_discoveries(db,value)
    except (KeyError,ValueError,TypeError): return None

def status(args):
    with connect(args.ledger,readonly=True) as db:
        has_runs=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='execution_runs'").fetchone()
        last=db.execute('SELECT * FROM execution_runs ORDER BY id DESC LIMIT 1').fetchone() if has_runs else None
        run_info=dict(last) if last else None
        if run_info: run_info['elapsedSeconds']=round((run_info['ended'] or time.time())-run_info['started'],2)
        states=dict(db.execute('SELECT state,COUNT(*) FROM candidates GROUP BY state').fetchall())
        value={'prepared':info(db,'prepared'),'sourceRows':db.execute('SELECT COUNT(*) FROM origins').fetchone()[0],
               'candidates':sum(states.values()),
               'states':states,
               'facts':dict(db.execute('SELECT kind,COUNT(*) FROM facts WHERE active=1 GROUP BY kind').fetchall()),
               'confirmed':sum(states.get(s,0) for s in ('adopted','excluded_confirmed','not_distributed')),
               'sourceVerified':sum(states.get(s,0) for s in ('reviewed','adopted')),
               'awaitingValidation':states.get('reviewed',0),
               'inspectionWaiting':states.get('needs_review',0),
               'waitingByReason':dict(db.execute("SELECT reason,COUNT(*) FROM candidates WHERE state='needs_review' GROUP BY reason")),
               'blocked':states.get('blocked',0),
               'additionalReadingDiscovered':direct_reading_discoveries(db),
               'archivedFacts':db.execute('SELECT COUNT(*) FROM facts WHERE active=0').fetchone()[0],
               'pilot':dict(db.execute('SELECT c.state,COUNT(*) FROM candidates c JOIN pilot p ON p.candidate_id=c.id GROUP BY c.state').fetchall()),
               'failedRequests':db.execute('SELECT COUNT(*) FROM attempts WHERE result=\'error\'').fetchone()[0],
               'lastRun':info(db,'lastRun'),'execution':run_info,
               'pilotClassificationAccuracy':'Independent gold inspection not recorded; counts are not precision'}
        emit(value);return value

def explain(args):
    with connect(args.ledger,readonly=True) as db:
        query='SELECT * FROM candidates WHERE '+('id=?' if args.id else 'surface=?')
        for row in db.execute(query,(args.id or args.surface,)):
            emit({'candidate':dict(row),'origins':[dict(r) for r in db.execute('SELECT o.* FROM origins o JOIN origin_candidates c ON c.origin_id=o.id WHERE c.candidate_id=?',(row['id'],))],
                  'facts':fact_rows(db,row),'attempts':[dict(r) for r in db.execute('SELECT * FROM attempts WHERE candidate_id=?',(row['id'],))],
                  'inferences':[dict(r) for r in db.execute('SELECT role,model_digest,prompt_sha256,output,error FROM inferences WHERE candidate_id=?',(row['id'],))]})

def source_text(path, data=None):
    if data is None:data=pathlib.Path(path).read_bytes()
    if data.startswith(b'\x1f\x8b'): data=gzip.decompress(data)
    elif data.startswith(b'PK\x03\x04'):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names=[n for n in z.namelist() if not n.endswith('/') and not n.startswith('__MACOSX/')]
            if len(names)!=1: raise ValueError('Gold document ZIP has multiple files')
            data=z.read(names[0])
    if len(data)>512*1024*1024: raise ValueError('Oversized expanded evidence document')
    # Wikimedia page_props contains binary blobs in unrelated properties.
    # Identity quotes are ASCII SQL tuples; the reversible byte representation
    # preserves those exact bytes without treating arbitrary blobs as readings.
    if b'CREATE TABLE `page_props`' in data[:65536]:
        text=data.decode('latin-1',errors='strict')
    else:
        text=data.decode('utf-8',errors='strict')
    try:
        value=json.loads(text)
        def strings(v):
            if isinstance(v,str): yield v
            elif isinstance(v,dict):
                for x in v.values(): yield from strings(x)
            elif isinstance(v,list):
                for x in v: yield from strings(x)
        return canonical(value)+'\n'+'\n'.join(strings(value))
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

def gold_selection_pairs(cases):
    return sorted({(item['candidateId'],item['split']) for item in cases})

def check_gold_selection(db,cases):
    selection=info(db,'goldSelection')
    if selection and gold_selection_pairs(cases)!=gold_selection_pairs(selection['cases']):
        raise ValueError('Gold labels do not match the frozen candidate/split selection')
    return selection

def inferred_outside_pilot(db):
    """Include history and failed model calls, so resetting a row cannot erase tuning."""
    for table in ('candidates','decision_history'):
        identifier='id' if table=='candidates' else 'candidate_id'
        query="SELECT 1 FROM "+table+" d WHERE d."+identifier+" NOT IN (SELECT candidate_id FROM pilot) AND d.decision IS NOT NULL AND ((json_extract(d.decision,'$.classificationRoute') IS NOT NULL AND json_extract(d.decision,'$.classificationRoute')!='direct') OR EXISTS (SELECT 1 FROM json_each(d.decision,'$.roles') role WHERE COALESCE(json_extract(role.value,'$.method'),json_extract(d.decision,'$.classificationRoute'),'')!='direct')) LIMIT 1"
        if db.execute(query).fetchone(): return True
    if db.execute('SELECT 1 FROM inferences WHERE candidate_id NOT IN (SELECT candidate_id FROM pilot) LIMIT 1').fetchone(): return True
    if db.execute("SELECT 1 FROM model_calls m,json_each(m.aliases,'$.candidates') c WHERE c.key NOT IN (SELECT candidate_id FROM pilot) LIMIT 1").fetchone(): return True
    return False

def gold_selection_record(cases,file_sha,mode):
    frozen=[{'candidateId':cid,'split':split} for cid,split in gold_selection_pairs(cases)]
    return {'schemaVersion':1,'cases':frozen,'selectionSha256':digest(canonical(frozen)),
            'fileSha256':file_sha,'mode':mode,'recordedAt':time.time()}

def select_gold(args):
    """Record a label-free independently drawn cohort before inferred full decisions."""
    path=pathlib.Path(args.input);value=json.loads(path.read_text())
    if not isinstance(value,dict) or set(value)!={'schemaVersion','cases'} or value['schemaVersion']!=1 or not isinstance(value['cases'],list) or not value['cases']:
        raise ValueError('Gold selection needs schemaVersion 1 and nonempty cases')
    with connect(args.ledger) as db:
        pin_config(db,args);seen=set();surfaces={};splits=set()
        for item in value['cases']:
            if not isinstance(item,dict) or set(item)!={'candidateId','split'} or not isinstance(item['candidateId'],str) or item['split'] not in ('calibration','validation'):
                raise ValueError('Gold selection must contain only candidateId/split, never labels')
            cid=item['candidateId'];split=item['split']
            row=db.execute('SELECT surface FROM candidates WHERE id=?',(cid,)).fetchone()
            if row is None or cid in seen: raise ValueError('Unknown/duplicate gold selection candidate')
            if row['surface'] in surfaces and surfaces[row['surface']]!=split: raise ValueError('Calibration/validation surface leakage in selection')
            seen.add(cid);surfaces[row['surface']]=split;splits.add(split)
        if splits!={'calibration','validation'}: raise ValueError('Gold selection requires calibration and validation splits')
        record=gold_selection_record(value['cases'],sha(path),'independent-selection')
        old=info(db,'goldSelection')
        if old:
            if old['selectionSha256']!=record['selectionSha256']: raise ValueError('Frozen gold selection is immutable')
            emit(old);return old
        if info(db,'goldFrozen') or inferred_outside_pilot(db):
            raise ValueError('Independent selection must precede gold labels and inferred full decisions/calibration tuning')
        info(db,'goldSelection',record);db.commit();emit(record);return record

def validate_gold(db,args):
    """Ground truth must have bound quotations and document hashes; model output isn't accepted."""
    path=pathlib.Path(args.gold);value=json.loads(path.read_text());surface_seen={};target_seen={};counts={};cases_seen=set();checked_documents={}
    check_gold_selection(db,value['cases'])
    for item in value['cases']:
        required={'candidateId','split','categories','target','readingEvidence','meaningEvidence','eligible'}
        if set(item)!=required or item['split'] not in ('calibration','validation'): raise ValueError('Invalid gold fields')
        if not isinstance(item['eligible'],bool) or not item['target'] or not isinstance(item['categories'],list) or (item['eligible'] and not item['categories']) or len(set(item['categories']))!=len(item['categories']) or not set(item['categories'])<=set(c['id'] for c in configuration(args)[1]['categories']): raise ValueError('Gold labels/type invalid')
        row=db.execute('SELECT * FROM candidates WHERE id=?',(item['candidateId'],)).fetchone()
        if row is None: raise ValueError('Gold candidate not in inputs')
        key=(row['surface'],row['reading'],item['target'],item['split'])
        if key in cases_seen: raise ValueError('Duplicate input pair/target gold case')
        cases_seen.add(key)
        if (row['surface'] in surface_seen and surface_seen[row['surface']]!=item['split']) or (item['target'] in target_seen and target_seen[item['target']]!=item['split']): raise ValueError('Calibration/validation surface or entity leakage')
        surface_seen[row['surface']]=item['split'];target_seen[item['target']]=item['split']
        for field in ('readingEvidence','meaningEvidence'):
            for evidence in item[field]:
                if set(evidence)!= {'documentId','quotation','sha256'}: raise ValueError('Gold provenance fields invalid')
                doc=db.execute('SELECT * FROM documents WHERE id=?',(evidence['documentId'],)).fetchone()
                if doc is None or doc['sha256']!=evidence['sha256']: raise ValueError('Gold source checksum mismatch')
                source_key=(doc['path'],doc['sha256'])
                if source_key not in checked_documents:
                    raw=pathlib.Path(doc['path']).read_bytes()
                    if digest(raw)!=evidence['sha256']:raise ValueError('Gold source checksum mismatch')
                    checked_documents[source_key]=source_text(doc['path'],raw)
                text=checked_documents[source_key]
                if not evidence['quotation'] or evidence['quotation'] not in text: raise ValueError('Gold quotation absent from source')
        if not item['readingEvidence'] or not item['meaningEvidence']: raise ValueError('Gold needs independently checked reading and meaning sources')
        observed=fact_rows(db,dict(row))
        # A negative's original reference entry can document a search-only form;
        # it must never become an affirmative reading proof.
        for field,kinds in [('readingEvidence',('reading',) if item['eligible'] else ('reading','context','meaning')),('meaningEvidence',('meaning','context'))]:
            for ref in item[field]:
                related=[f for f in observed if f['document_id']==ref['documentId'] and f['kind'] in kinds and (field=='readingEvidence' or f['target']==item['target'])]
                if not related: raise ValueError('Gold source is not bound to this input pair/target')
        for cat in item['categories']: counts[(cat,item['split'])]=counts.get((cat,item['split']),0)+1
    for cat in configuration(args)[1]['categories']:
        minimum=100 if cat['core'] else 50
        if any(counts.get((cat['id'],split),0)<minimum for split in ('calibration','validation')): raise ValueError('Insufficient gold examples: '+cat['id'])
    return value,sha(path)

def archive_frozen_gold(db,frozen):
    history=info(db,'goldFrozenHistory') or []
    identity=(frozen['sha256'],frozen.get('selectionSha256'))
    if not any((entry['sha256'],entry.get('selectionSha256'))==identity for entry in history):
        history.append({**frozen,'archivedAt':time.time()});info(db,'goldFrozenHistory',history)
    return history

def isolated_source_reviews(db, selection):
    """Permit preselected, source-only gold after disjoint individual inspections.

    This is not a waiver for model inference or classifier tuning: the selected
    names and every evidence-linked target remain quarantined, including history.
    Only citation-bearing import-review records may precede the first freeze.
    """
    if not selection or selection.get('mode') != 'independent-selection': return False
    if db.execute('SELECT 1 FROM inferences WHERE candidate_id NOT IN (SELECT candidate_id FROM pilot) LIMIT 1').fetchone(): return False
    if db.execute("SELECT 1 FROM model_calls m,json_each(m.aliases,'$.candidates') c WHERE c.key NOT IN (SELECT candidate_id FROM pilot) LIMIT 1").fetchone(): return False
    selected = {item['candidateId'] for item in selection['cases']}
    surfaces = set(); targets = set()
    for cid in selected:
        row = db.execute('SELECT surface,reading FROM candidates WHERE id=?', (cid,)).fetchone()
        if row is None: return False
        surfaces.add(row['surface'])
        targets.update(r[0] for r in db.execute("SELECT target FROM facts INDEXED BY fact_pair WHERE surface=? AND reading IN (?, '') AND active=1 AND kind IN ('reading','meaning','context')", (row['surface'], row['reading'])))
    non_direct = "(COALESCE(json_extract(decision,'$.classificationRoute'),'direct')!='direct' OR EXISTS (SELECT 1 FROM json_each(decision,'$.roles') role WHERE COALESCE(json_extract(role.value,'$.method'),json_extract(decision,'$.classificationRoute'),'')!='direct'))"
    query = "SELECT id candidate_id,decision,NULL created FROM candidates WHERE id NOT IN (SELECT candidate_id FROM pilot) AND decision IS NOT NULL AND " + non_direct
    query += " UNION ALL SELECT candidate_id,decision,created FROM decision_history WHERE candidate_id NOT IN (SELECT candidate_id FROM pilot) AND decision IS NOT NULL AND " + non_direct
    inspected = 0
    for record in db.execute(query):
        decision = json.loads(record['decision']); roles = decision.get('roles', [])
        methods = {role.get('method', decision.get('classificationRoute')) for role in roles}
        if decision.get('classificationRoute') in (None, 'direct') and methods <= {'direct'}: continue
        cid = record['candidate_id']
        row = db.execute('SELECT surface FROM candidates WHERE id=?', (cid,)).fetchone()
        if (cid in selected or row is None or row['surface'] in surfaces
                or any(role.get('target') in targets for role in roles)
                or (record['created'] is not None and record['created'] < selection['recordedAt'])): return False
        if (decision.get('classificationRoute') != 'source_review'
                or not methods <= {'direct', 'source_review'} or not roles
                or not re.fullmatch('[0-9a-f]{64}', decision.get('reviewFileSha256', ''))
                or not re.fullmatch('[0-9a-f]{64}', decision.get('evidenceSha256', ''))
                or not decision.get('citations')): return False
        inspected += 1
    return bool(inspected)

def freeze_gold(args):
    with connect(args.ledger) as db:
        pin_config(db,args)
        previous=info(db,'goldFrozen')
        if previous:
            if sha(args.gold)!=previous['sha256']: raise ValueError('Frozen gold labels are immutable; existing evaluation cannot be overwritten')
            validate_gold(db,args)
            archive_frozen_gold(db,previous);db.commit()
            emit({'goldFrozen':previous['sha256'],'cases':len(previous['cases']),'selectionSha256':previous.get('selectionSha256'),'unchanged':True})
            return
        progress=db.execute("SELECT COUNT(*) FROM candidates WHERE state!='queued' AND id NOT IN (SELECT candidate_id FROM pilot)").fetchone()[0]
        selection=info(db,'goldSelection')
        # Reject late labels before even loading them. Source-only inspection may
        # precede cohort selection, but inferred full decisions may not.
        if progress and not selection: raise ValueError('Full source inspection requires a separately recorded gold selection before labels')
        inferred = inferred_outside_pilot(db)
        isolated = inferred and isolated_source_reviews(db, selection)
        if inferred and not isolated: raise ValueError('Gold must be frozen before inferred full decisions/calibration tuning')
        value,h=validate_gold(db,args)
        if not selection:
            # Preserve the original pre-full-run path and fix its cohort at the
            # same point as the labels, before any full-population decisions.
            selection=gold_selection_record(value['cases'],h,'pre-full-gold')
            info(db,'goldSelection',selection)
        frozen={'sha256':h,'cases':value['cases'],'selectionSha256':selection['selectionSha256']}
        if isolated: frozen['priorInspectionBasis']='Citation-bearing individual source reviews disjoint from every selected name and evidence-linked target; no model inference outside pilot'
        info(db,'goldFrozen',frozen);archive_frozen_gold(db,frozen);db.commit()
        emit({'goldFrozen':h,'cases':len(value['cases']),'selectionSha256':selection['selectionSha256']})

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
    p.add_argument('action',choices=['prepare','bulk','pilot','run','status','explain','review-export','import-review','complete-source-search','select-gold','freeze-gold','accept','finalize','export'])
    p.add_argument('--ledger',default='build/research/ledger.sqlite');p.add_argument('--config',default=str(DEFAULT_CONFIG))
    p.add_argument('--source-dir',default='src/main/bin');p.add_argument('--base-dir')
    p.add_argument('--audit',default='build/research/baseline-v2/audit.tsv.gz');p.add_argument('--snapshot',default='build/dictionary-metadata/snapshot.sqlite')
    p.add_argument('--postal-zip');p.add_argument('--documents',default='build/research/documents');p.add_argument('--jmnedict');p.add_argument('--jmdict')
    p.add_argument('--mozc-commit',default='c7538e6f8ee56ff94789494106ad5d6d658cd4f6')
    p.add_argument('--input');p.add_argument('--online',action='store_true');p.add_argument('--acceptance');p.add_argument('--candidate',action='store_true');p.add_argument('--id');p.add_argument('--surface');p.add_argument('--reason');p.add_argument('--after-id');p.add_argument('--gold');p.add_argument('--output')
    p.add_argument('--source-staging')
    p.add_argument('--batch-size',type=int);p.add_argument('--pilot-size',type=int,default=100);p.add_argument('--max-batches',type=int)
    args=p.parse_args(argv)
    if args.batch_size is not None and not 1<=args.batch_size<=1000: p.error('batch-size must be 1..1000')
    if args.max_batches is not None and args.max_batches<1: p.error('max-batches must be positive')
    with (contextlib.nullcontext() if args.action in ('status','explain') else coordinator_lock(args.ledger)):
        if args.action=='prepare': prepare(args)
        elif args.action=='bulk': bulk(args)
        elif args.action in ('pilot','run'): return run(args,args.action=='pilot')
        elif args.action=='status': status(args)
        elif args.action=='explain':
            if not args.id and not args.surface: p.error('explain needs --id or --surface')
            explain(args)
        elif args.action in ('review-export','import-review','complete-source-search'):
            import direct_review
            if args.action=='import-review' and not args.input: p.error('import-review needs --input')
            if args.action=='complete-source-search' and not args.source_staging: p.error('complete-source-search needs --source-staging')
            with connect(args.ledger) as db:
                pin_config(db,args)
                if args.action=='review-export': direct_review.export_reviews(db,args)
                elif args.action=='import-review': direct_review.import_reviews(db,args)
                else: return direct_review.complete_source_search(db,args)
        elif args.action=='select-gold':
            if not args.input: p.error('select-gold needs --input')
            select_gold(args)
        elif args.action=='freeze-gold': freeze_gold(args)
        elif args.action=='accept': accept(args)
        elif args.action=='finalize': finalize(args)
        elif args.action=='export': export(args)

if __name__=='__main__':
    try: sys.exit(main() or 0)
    except Exception as ex: print('research: '+str(ex),file=sys.stderr);sys.exit(2)
