"""Scan a checksum-verified Wikipedia dump instead of per-candidate API calls.

The staging scan can follow an in-progress download. It never writes evidence
to the research ledger until the complete compressed source checksum matches.
Only literal existing-input names and readings are retained as evidence.
"""
import argparse,bz2,collections,gzip,hashlib,html,io,json,pathlib,re,sqlite3,time
import xml.etree.ElementTree as ET
import worker as w
import source_rounds

PARSER_VERSION=2

def name_key(value):
    import unicodedata
    value=unicodedata.normalize('NFKC',value)
    return re.sub(r'(?<=[\u3040-\u30ff\u3400-\u9fff々]) +(?=[\u3040-\u30ff\u3400-\u9fff々])','',value)

def subjects(title,text):
    result={title}
    first=re.search(r"'''([^'\n]+)'''",w.wiki_lead(text))
    if first: result.add(first[1])
    return result

def bindings_for_page(title,text,index,redirect=False):
    primary={name_key(n) for n in subjects(title,text)}
    result={}
    for name,y,quote in source_rounds.full_body_reading_bindings(text):
        for row in index.get(name_key(name),()):
            if w.reading(y)==w.reading(row['reading']):
                target,binding=source_rounds.binding_target(title,text,row['surface']) if not redirect else (title+'#mentioned-name:'+row['surface'],'redirect-literal-mentioned-name')
                proof={'source':'explicit-name-reading','name':name,'reading':y,'quotation':quote}
                proof['binding']=binding
                result[(row['id'],target,w.digest(w.canonical(proof)))]=(row,target,proof)
    for name in subjects(title,text):
        if redirect: continue
        if not name or not all('ぁ'<=c<='ゖ' or 'ァ'<=c<='ヶ' or c=='ー' for c in name): continue
        for row in index.get(name_key(name),()):
            if w.reading(name)==w.reading(row['reading']):
                proof={'source':'attested-canonical-kana','name':name}
                result[(row['id'],title,w.digest(w.canonical(proof)))]=(row,title,proof)
    return list(result.values())

def verified_page_text(text,sha1,declared_bytes=None):
    if not sha1: return text
    expected=format(int(sha1,36),'040x')
    if hashlib.sha1(text.encode()).hexdigest()==expected: return text
    # Older MediaWiki exports sometimes append an LF absent from the stored
    # revision. Its declared byte count can include that LF too. Restore only
    # when the complete published revision SHA1 proves the exact stored text.
    if text.endswith('\n'):
        restored=text[:-1]
        if hashlib.sha1(restored.encode()).hexdigest()==expected: return restored
    raise ValueError('Wikipedia page content checksum mismatch')

class GrowingSource(io.RawIOBase):
    """Forward-only compressed input with finite waiting and streaming hashes."""
    def __init__(self,path,expected_bytes,wait_seconds=0):
        self.file=open(path,'rb');self.expected_bytes=expected_bytes;self.wait_seconds=wait_seconds
        self.bytes=0;self.sha1=hashlib.sha1();self.sha256=hashlib.sha256()
    def readable(self): return True
    def read(self,size=-1):
        if size<0: size=1024*1024
        started=time.monotonic()
        while True:
            data=self.file.read(size)
            if data:
                self.bytes+=len(data);self.sha1.update(data);self.sha256.update(data)
                if self.bytes>self.expected_bytes: raise ValueError('Dump exceeds official size')
                return data
            if self.bytes==self.expected_bytes: return b''
            if time.monotonic()-started>=self.wait_seconds: raise ValueError('Incomplete dump download; staging preserved')
            time.sleep(.5)
    def close(self):
        self.file.close();super().close()

def stage(path,staging,index,expected_bytes,expected_sha1,wait_seconds=0):
    """Build a source index, but mark complete only after whole-source validation."""
    db=sqlite3.connect(staging);db.execute('PRAGMA journal_mode=WAL')
    db.executescript('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);'
                     'CREATE TABLE IF NOT EXISTS titles(page_id INTEGER PRIMARY KEY,title TEXT,redirect TEXT);'
                     'CREATE TABLE IF NOT EXISTS pages(page_id INTEGER PRIMARY KEY,title TEXT,revision TEXT,timestamp TEXT,text_sha1 TEXT,content TEXT,proofs TEXT,contexts TEXT);')
    cohort_rows=sorted((r for rows in index.values() for r in rows),key=lambda r:r['id'])
    cohort=source_rounds.cohort_hash(cohort_rows) if cohort_rows else None
    tracker=source_rounds.CorpusRoundTracker(cohort[0],cohort[1],'0'*64) if cohort else None
    input_meta={'file':pathlib.Path(path).name,'expectedBytes':expected_bytes,'expectedSha1':expected_sha1,
                'parserVersion':PARSER_VERSION,'candidateSelectionSha256':w.digest(w.canonical(sorted(r['id'] for rows in index.values() for r in rows)))}
    old=db.execute("SELECT value FROM meta WHERE key='source'").fetchone()
    if old:
        saved=json.loads(old[0])
        if any(saved.get(k)!=v for k,v in input_meta.items()): raise ValueError('Staging source/cohort mismatch')
        if saved.get('complete'): db.close();return saved
    db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('source',w.canonical({**input_meta,'complete':False})));db.commit()
    counts=collections.Counter();started=time.monotonic();source=GrowingSource(path,expected_bytes,wait_seconds)
    try:
        with bz2.BZ2File(source,'rb') as stream:
            root=None
            for event,page in ET.iterparse(stream,events=('start','end')):
                if root is None and event=='start':
                    root=page
                    if page.tag.split('}')[-1]!='mediawiki': raise ValueError('Expected MediaWiki XML root')
                if event!='end' or page.tag.split('}')[-1]!='page': continue
                ns=page.tag[:-4]
                field=lambda key:page.findtext(ns+key)
                counts['pagesScanned']+=1
                if field('ns')!='0': page.clear();root.clear();continue
                title=field('title');pid=field('id');rev=page.find(ns+'revision')
                if not title or not pid or rev is None: raise ValueError('Malformed article page')
                redirect=page.find(ns+'redirect');redirect=redirect.get('title') if redirect is not None else None
                text_node=rev.find(ns+'text');content=(text_node.text or '') if text_node is not None else '';sha1=rev.findtext(ns+'sha1');export_content=content
                try: content=verified_page_text(content,sha1,text_node.get('bytes') if text_node is not None else None)
                except ValueError as ex: raise ValueError(str(ex)+': '+title) from ex
                counts['exportTerminalLfRecovered']+=content!=export_content
                db.execute('INSERT OR REPLACE INTO titles VALUES(?,?,?)',(int(pid),title,redirect))
                counts['mainPagesScanned']+=1
                proofs=bindings_for_page(title,content,index,redirect=bool(redirect))
                primary={name_key(n) for n in subjects(title,content)} if not redirect else set()
                contexts={row['id']:row for name in primary for row in index.get(name,())}
                contexts.update({row['id']:row for row,target,proof in proofs if target==title})
                if tracker:
                    tracker.observe('subject',title,rev.findtext(ns+'id'),content,matches=sum(target==title for row,target,proof in proofs))
                    tracker.observe('named-binding',title,rev.findtext(ns+'id'),content,matches=len(proofs))
                if proofs or contexts:
                    db.execute('INSERT OR REPLACE INTO pages VALUES(?,?,?,?,?,?,?,?)',
                        (int(pid),title,rev.findtext(ns+'id'),rev.findtext(ns+'timestamp'),sha1,content,
                         w.canonical([{'candidate':row,'target':target,'body':proof} for row,target,proof in proofs]),w.canonical(list(contexts.values()))))
                    counts['retainedPages']+=1;counts['readingBindings']+=len(proofs);counts['contextPairs']+=len(contexts)
                if counts['pagesScanned']%10000==0:
                    db.commit();w.emit({'phase':'wiki-dump-stage','counts':dict(counts),'compressedBytes':source.bytes,'seconds':round(time.monotonic()-started,2)})
                page.clear();root.clear()
        if source.bytes!=expected_bytes or source.sha1.hexdigest()!=expected_sha1:
            raise ValueError('Official Wikipedia dump checksum mismatch')
        result={**input_meta,'complete':True,'sha256':source.sha256.hexdigest(),'counts':dict(counts),'seconds':round(time.monotonic()-started,2)}
        if tracker:
            tracker.corpus=result['sha256']
            result['completedSearchProof']=tracker.finish(eof=True,source_checksum_verified=True,main_articles_scanned=counts['mainPagesScanned'])
        db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('source',w.canonical(result)));db.commit();return result
    finally:
        source.close();db.close()

def literal_quote(text,quote):
    if quote in text:return quote
    render=lambda value:html.unescape(re.sub(r'<[^>]+>','',value)).replace("'''",'').replace("''",'')
    expected=render(quote).strip()
    lines=text.splitlines(keepends=True);window=max(1,quote.count('\n')+1)
    for n in range(len(lines)):
        raw=''.join(lines[n:n+window])
        rendered=render(raw)
        if expected in rendered:return raw.rstrip('\r\n')
    return None


def import_stage(db,args,staging,url,max_pages=None,identity_index=None):
    source=sqlite3.connect('file:'+str(pathlib.Path(staging).resolve())+'?mode=ro',uri=True);source.row_factory=sqlite3.Row
    try:
        record=source.execute("SELECT value FROM meta WHERE key='source'").fetchone()
        metadata=json.loads(record[0]) if record else None
        if not metadata or not metadata.get('complete'): raise ValueError('Unverified staging dump cannot supply evidence')
        proof=metadata.get('completedSearchProof')
        if not proof: raise ValueError('Verified full-input search coverage is required before importing evidence')
        cohort,count=source_rounds.cohort_hash(db.execute('SELECT id,reading,surface FROM candidates ORDER BY id'))
        if cohort!=proof.get('cohortSha256') or count!=proof.get('candidateCount'):
            raise ValueError('Staged Wikipedia search belongs to another candidate cohort')
        key='wikiDump:'+metadata['sha256']+':'+str(PARSER_VERSION);receipt=w.info(db,key) or {};cursor=receipt.get('cursor',0)
        if receipt.get('complete'): return receipt
        e=w.Evidence(db,args);counts=collections.Counter(receipt.get('counts',{}));started=time.monotonic();pages=[];paused=False
        identity=None;identity_doc=None;identity_meta=None
        if identity_index:
            identity=sqlite3.connect('file:'+str(pathlib.Path(identity_index).resolve())+'?mode=ro',uri=True)
            identity_meta=json.loads(identity.execute("SELECT value FROM meta WHERE key='source'").fetchone()[0])
            if not identity_meta.get('complete') or w.sha(identity_meta['source'])!=identity_meta['sha256']:
                raise ValueError('Unverified page identity source')
            if pathlib.Path(identity_meta['source']).name.split('-')[1]!=metadata['file'].split('-')[1]:
                raise ValueError('Article and page identity dumps are from different snapshots')
            identity_doc=e.save(identity_meta['url'],identity_meta['sha256'],pathlib.Path(identity_meta['source']).read_bytes(),'Wikipedia CC-BY-SA; page identity SQL source')
        def flush(batch):
            prepared=[]
            for page in batch:
                item_id=identity.execute('SELECT qid,quotation FROM page_identity WHERE page_id=?',(page['page_id'],)).fetchone() if identity else None
                subject=item_id[0] if item_id else page['title']
                proofs=[];contexts=[]
                for item in json.loads(page['proofs']):
                    row=item['candidate'];target=subject if item['target']==page['title'] else item['target']
                    if db.execute("SELECT 1 FROM facts WHERE active=1 AND kind='reading' AND surface=? AND reading=? AND target=? LIMIT 1",(row['surface'],row['reading'],target)).fetchone():
                        counts['existingTargetReadingsReused']+=1
                    else:proofs.append(item)
                for row in json.loads(page['contexts']):
                    if db.execute("SELECT 1 FROM facts WHERE active=1 AND kind='context' AND surface=? AND reading=? AND target=? AND json_extract(body,'$.source')='Wikipedia' AND json_extract(body,'$.primaryNameVerified')=1 LIMIT 1",(row['surface'],row['reading'],subject)).fetchone():
                        counts['existingPrimaryContextsReused']+=1
                    else:contexts.append(row)
                if proofs or contexts:prepared.append((page,proofs,contexts))
            payload={'sourceProjection':'Literal XML page fields from official Wikipedia dump','source':metadata,'query':{'pages':{}}}
            for page,proofs,contexts in prepared:
                if page['text_sha1'] and hashlib.sha1(page['content'].encode()).hexdigest()!=format(int(page['text_sha1'],36),'040x'):
                    raise ValueError('Staged page checksum mismatch: '+page['title'])
                payload['query']['pages'][str(page['page_id'])]={'pageid':page['page_id'],'ns':0,'title':page['title'],
                    'revisions':[{'revid':int(page['revision']),'timestamp':page['timestamp'],'sha1':page['text_sha1'],
                                  'slots':{'main':{'*':page['content']}}}]}
            if prepared:
                raw=gzip.compress(w.canonical(payload).encode(),mtime=0)
                did=e.save(url+'#matched-pages-'+str(batch[0]['page_id'])+'-'+str(batch[-1]['page_id']),metadata['sha256'],raw,'Wikipedia CC-BY-SA; literal XML source projection')
            for page,proofs,contexts in prepared:
                item_id=identity.execute('SELECT qid,quotation FROM page_identity WHERE page_id=?',(page['page_id'],)).fetchone() if identity else None
                subject=item_id[0] if item_id else page['title']
                identity_proofs={}
                if item_id:
                    for row in {r['id']:r for r in contexts+[p['candidate'] for p in proofs]}.values():
                        identity_proofs[row['id']]=e.fact('',row['surface'],'context',[],subject,identity_doc,
                            {'source':'Wikipedia-page-identity','pageId':page['page_id'],'title':page['title'],'qid':subject,'quotation':item_id[1],'sourceSha256':identity_meta['sha256']})
                for item in proofs:
                    row=item['candidate'];body={**item['body'],'revision':page['revision'],'acquisition':{'sourceDumpSha256':metadata['sha256'],'sourcePageId':page['page_id'],'parserVersion':metadata['parserVersion'],'importerVersion':PARSER_VERSION}}
                    target=subject if item['target']==page['title'] else item['target']
                    if body.get('quotation'):
                        quote=literal_quote(page['content'],body['quotation'])
                        if not quote:
                            counts['nonLiteralBindingsWithheld']+=1;continue
                        if quote!=body['quotation']:
                            body['parsedBindingQuotation']=body['quotation'];body['quotation']=quote;counts['literalQuotationRecovered']+=1
                    if target==subject and row['id'] in identity_proofs:
                        body['componentFacts']=[identity_proofs[row['id']]]
                    y,s=w.pair(row['reading'],row['surface'])
                    had=db.execute("SELECT 1 FROM facts WHERE active=1 AND kind='reading' AND surface=? AND reading=? LIMIT 1",(s,y)).fetchone()
                    e.fact(y,s,'reading',[],target,did,body);counts['newReadingBindings']+=not bool(had);counts['readingBindings']+=1
                for row in contexts:
                    e.fact(row['reading'],row['surface'],'context',[],subject,did,
                           {'source':'Wikipedia','title':page['title'],'revision':int(page['revision']),'lead':w.wiki_lead(page['content']),
                            'primaryNameVerified':True,'acquisition':{'sourceDumpSha256':metadata['sha256'],'sourcePageId':page['page_id'],'parserVersion':metadata['parserVersion'],'importerVersion':PARSER_VERSION},
                            'componentFacts':[identity_proofs[row['id']]] if row['id'] in identity_proofs else []})
                    counts['contextPairs']+=1
            counts['pagesImported']+=len(batch)
            value={'source':metadata,'cursor':batch[-1]['page_id'],'complete':False,'counts':dict(counts)}
            w.info(db,key,value);db.commit();w.emit({'phase':'wiki-dump-import',**value})
        scanned=0
        for page in source.execute('SELECT * FROM pages WHERE page_id>? ORDER BY page_id',(cursor,)):
            pages.append(page);scanned+=1
            if len(pages)>=64: flush(pages);pages=[]
            if max_pages and scanned>=max_pages: paused=True;break
        if pages: flush(pages)
        receipt=w.info(db,key) or {'cursor':cursor}
        result={**receipt,'source':metadata,'identitySource':identity_meta,'complete':not paused,'counts':dict(counts),'secondsThisRun':round(time.monotonic()-started,2),'modelsCalled':0,'networkRequests':0}
        if identity:identity.close()
        w.info(db,key,result);db.commit();return result
    finally: source.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['stage','import'])
    p.add_argument('--dump');p.add_argument('--staging',required=True);p.add_argument('--expected-bytes',type=int);p.add_argument('--expected-sha1')
    p.add_argument('--wait-seconds',type=float,default=0);p.add_argument('--url');p.add_argument('--ledger',default='build/research/ledger.sqlite')
    p.add_argument('--documents',default='build/research/documents');p.add_argument('--config',default=str(w.DEFAULT_CONFIG));p.add_argument('--max-pages',type=int);p.add_argument('--identity-index')
    args=p.parse_args()
    if args.action=='stage':
        if not args.dump or not args.expected_bytes or not args.expected_sha1: p.error('stage requires dump and official size/SHA1')
        with w.connect(args.ledger,readonly=True) as db:
            index=collections.defaultdict(list)
            for row in db.execute('SELECT id,reading,surface FROM candidates'): index[name_key(row['surface'])].append(dict(row))
        w.emit(stage(args.dump,args.staging,index,args.expected_bytes,args.expected_sha1,args.wait_seconds))
    else:
        if not args.url: p.error('import requires source URL')
        with w.coordinator_lock(args.ledger),w.connect(args.ledger) as db: w.emit(import_stage(db,args,args.staging,args.url,args.max_pages,args.identity_index))

if __name__=='__main__': main()
