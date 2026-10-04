"""Archive every raw main-namespace article from a pinned official XML dump.

This module parses only XML identity/revision fields. It does not inspect names,
readings, categories, candidates, or the research ledger. An interrupted or failed
scan remains incomplete; only verified XML EOF and compressed source hashes can
publish a complete archive.
"""
import argparse,bz2,collections,hashlib,json,math,pathlib,signal,sqlite3,time
import xml.etree.ElementTree as ET
from wiki_dump import GrowingSource,verified_page_text

PARSER_VERSION=1

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def archive(dump,output,expected_bytes,expected_sha1,*,expected_sha256=None,url=None,wait_seconds=0,progress_every=10000,emit=None):
    if type(expected_bytes)is not int or expected_bytes<=0:raise ValueError('Positive official source byte count required')
    if not isinstance(expected_sha1,str)or len(expected_sha1)!=40 or any(c not in '0123456789abcdef'for c in expected_sha1):raise ValueError('Official hexadecimal SHA1 required')
    if expected_sha256 is not None and(len(expected_sha256)!=64 or any(c not in '0123456789abcdef'for c in expected_sha256)):raise ValueError('Invalid pinned SHA256')
    if not math.isfinite(wait_seconds)or not 0<=wait_seconds<=60:raise ValueError('Wait must be finite and at most 60 seconds')
    if type(progress_every)is not int or progress_every<1:raise ValueError('Positive progress interval required')
    dump=pathlib.Path(dump).resolve();output=pathlib.Path(output).resolve()
    if dump==output:raise ValueError('Archive cannot replace source dump')
    output.parent.mkdir(parents=True,exist_ok=True)
    input_meta={'source':str(dump),'file':dump.name,'url':url,'expectedBytes':expected_bytes,'expectedSha1':expected_sha1,'expectedSha256':expected_sha256,'parserVersion':PARSER_VERSION,'sourceProjection':'Literal main-namespace page identity and revision XML fields; cryptographically restored stored text when legacy export adds a terminal LF','modelsCalled':0,'networkRequests':0,'ledgerWritten':False}
    db=sqlite3.connect(output);source=None;counts=collections.Counter();started=time.monotonic();transcript=hashlib.sha256()
    try:
        db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=NORMAL')
        db.executescript('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE IF NOT EXISTS pages(page_id INTEGER PRIMARY KEY,title TEXT NOT NULL,revision TEXT NOT NULL,timestamp TEXT NOT NULL,text_sha1 TEXT NOT NULL,content TEXT NOT NULL,redirect TEXT,declared_bytes TEXT,export_terminal_lf_recovered INTEGER NOT NULL);CREATE INDEX IF NOT EXISTS article_title ON pages(title);')
        old=db.execute("SELECT value FROM meta WHERE key='source'").fetchone()
        if old:
            saved=json.loads(old[0])
            if any(saved.get(k)!=v for k,v in input_meta.items()):raise ValueError('Archive belongs to another pinned source')
            if saved.get('complete'):return saved
            # Reparse the same immutable source from its beginning. Preserve an
            # incomplete archive on failure, but never mix leftover rows into EOF.
            db.execute('DELETE FROM pages')
        db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('source',canonical({**input_meta,'complete':False})));db.commit()
        source=GrowingSource(dump,expected_bytes,wait_seconds)
        with bz2.BZ2File(source,'rb')as stream:
            root=None
            for event,page in ET.iterparse(stream,events=('start','end')):
                if root is None and event=='start':
                    root=page
                    if page.tag.split('}')[-1]!='mediawiki':raise ValueError('Expected MediaWiki XML root')
                if event!='end'or page.tag.split('}')[-1]!='page':continue
                ns=page.tag[:-4];field=lambda key:page.findtext(ns+key);counts['pagesScanned']+=1
                if field('ns')!='0':page.clear();root.clear();continue
                title=field('title');pid=field('id');rev=page.find(ns+'revision')
                if not title or not pid or rev is None:raise ValueError('Malformed main-namespace page')
                page_id=int(pid);revision=rev.findtext(ns+'id');timestamp=rev.findtext(ns+'timestamp');sha1=rev.findtext(ns+'sha1');text_node=rev.find(ns+'text')
                if page_id<=0 or not revision or int(revision)<=0 or not timestamp or not sha1 or text_node is None:raise ValueError('Missing article identity, text, or published revision SHA1: '+title)
                if not 0<=int(sha1,36)<2**160:raise ValueError('Invalid revision SHA1: '+title)
                export_content=text_node.text or'';content=verified_page_text(export_content,sha1,text_node.get('bytes'));recovered=int(content!=export_content)
                redirect_node=page.find(ns+'redirect');redirect=redirect_node.get('title')if redirect_node is not None else None
                db.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?,?,?)',(page_id,title,revision,timestamp,sha1,content,redirect,text_node.get('bytes'),recovered))
                counts['mainPagesArchived']+=1;counts['redirectsArchived']+=redirect is not None;counts['exportTerminalLfRecovered']+=recovered
                transcript.update(canonical([page_id,title,revision,timestamp,sha1,redirect,hashlib.sha256(content.encode()).hexdigest()]).encode()+b'\n')
                page.clear();root.clear()
                if counts['pagesScanned']%progress_every==0:
                    partial={**input_meta,'complete':False,'counts':dict(counts),'compressedBytes':source.bytes,'seconds':round(time.monotonic()-started,2)}
                    db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('source',canonical(partial)));db.commit()
                    if emit:emit({'phase':'article-archive',**partial})
        if source.bytes!=expected_bytes or source.sha1.hexdigest()!=expected_sha1:raise ValueError('Official compressed source size/SHA1 mismatch')
        if expected_sha256 and source.sha256.hexdigest()!=expected_sha256:raise ValueError('Pinned compressed source SHA256 mismatch')
        if db.execute('SELECT COUNT(*) FROM pages').fetchone()[0]!=counts['mainPagesArchived']:raise ValueError('Article count mismatch')
        result={**input_meta,'complete':True,'eof':True,'sourceChecksumVerified':True,'sha1':source.sha1.hexdigest(),'sha256':source.sha256.hexdigest(),'bytes':source.bytes,'counts':dict(counts),'articleTranscriptSha256':transcript.hexdigest(),'seconds':round(time.monotonic()-started,2)}
        db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('source',canonical(result)));db.commit();return result
    except BaseException as ex:
        # Do not overwrite another source's existing receipt after validation fails.
        old=db.execute("SELECT value FROM meta WHERE key='source'").fetchone()
        if old and all(json.loads(old[0]).get(k)==v for k,v in input_meta.items())and not json.loads(old[0]).get('complete'):
            failed={**input_meta,'complete':False,'counts':dict(counts),'compressedBytes':source.bytes if source else 0,'error':type(ex).__name__+': '+str(ex),'seconds':round(time.monotonic()-started,2)}
            db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)',('source',canonical(failed)));db.commit()
        raise
    finally:
        if source:source.close()
        db.close()

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dump',required=True);p.add_argument('--output',default='build/research/wiki-dump/all-articles.sqlite');p.add_argument('--expected-bytes',required=True,type=int);p.add_argument('--expected-sha1',required=True);p.add_argument('--expected-sha256');p.add_argument('--url');p.add_argument('--wait-seconds',type=float,default=0)
    args=p.parse_args(argv)
    def interrupted(signum,frame):raise InterruptedError('Archive interrupted by signal '+str(signum))
    signal.signal(signal.SIGTERM,interrupted)
    result=archive(args.dump,args.output,args.expected_bytes,args.expected_sha1,expected_sha256=args.expected_sha256,url=args.url,wait_seconds=args.wait_seconds,emit=lambda v:print(canonical(v),flush=True));print(canonical(result),flush=True)
if __name__=='__main__':main()
