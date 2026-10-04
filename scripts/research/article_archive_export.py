"""Export requested raw article pages, with verified same-snapshot QID identity.

No readings or categories are interpreted, and no production ledger is opened.
"""
import argparse,gzip,hashlib,json,pathlib,sqlite3
from article_archive import canonical

def connect(path):
 db=sqlite3.connect('file:'+str(pathlib.Path(path).resolve())+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;return db

def export(archive,identity,requests,output,*,provisional=False):
 db=connect(archive);ids=connect(identity)
 try:
  source=json.loads(db.execute("SELECT value FROM meta WHERE key='source'").fetchone()[0]);mapping=json.loads(ids.execute("SELECT value FROM meta WHERE key='source'").fetchone()[0])
  verified=bool(source.get('complete')and source.get('eof')and source.get('sourceChecksumVerified'))
  if not verified and not provisional:raise ValueError('Complete checksum-verified article archive required')
  if not mapping.get('complete'):raise ValueError('Complete identity index required')
  if source['file'].split('-')[1]!=pathlib.Path(mapping['source']).name.split('-')[1]:raise ValueError('Different article/QID dump snapshots')
  raw_identity=pathlib.Path(mapping['source']).read_bytes()
  if hashlib.sha256(raw_identity).hexdigest()!=mapping['sha256']:raise ValueError('Identity original source checksum changed')
  literal_identity=gzip.decompress(raw_identity);pages={};missing=[]
  for request in requests:
   pid=request.get('page_id',request.get('pageId'));qid=request['qid'];bound=ids.execute('SELECT * FROM page_identity WHERE page_id=?',(pid,)).fetchone()
   if bound is None or bound['qid']!=qid:raise ValueError('Requested page/QID identity mismatch: '+str(pid))
   if request.get('quotation')and request['quotation']!=bound['quotation']:raise ValueError('Requested identity literal quotation mismatch')
   # The SQL text is a literal tuple in the official gzip projection source.
   if bound['quotation'].encode()not in literal_identity:raise ValueError('Identity quote absent from original SQL')
   page=db.execute('SELECT * FROM pages WHERE page_id=?',(pid,)).fetchone()
   if page is None:missing.append({'pageId':pid,'qid':qid});continue
   expected=format(int(page['text_sha1'],36),'040x')
   if hashlib.sha1(page['content'].encode()).hexdigest()!=expected:raise ValueError('Archived revision checksum changed: '+str(pid))
   pages[str(pid)]={'pageid':pid,'ns':0,'title':page['title'],'redirect':page['redirect'],'sourceIdentity':{'qid':qid,'quotation':bound['quotation'],'sourceSha256':mapping['sha256']},'revisions':[{'revid':int(page['revision']),'timestamp':page['timestamp'],'sha1':page['text_sha1'],'slots':{'main':{'*':page['content']}}}],'sourceXmlMetadata':{'declaredBytes':page['declared_bytes'],'exportTerminalLfRecovered':bool(page['export_terminal_lf_recovered'])}}
  payload={'schemaVersion':1,'archiveComplete':verified,'usableForEvidence':verified,'evaluationDraftOnly':not verified,'sourceProjection':'Literal main-namespace page XML fields and literal page identity SQL tuples','source':source,'identitySource':mapping,'requests':requests,'missingPages':missing,'query':{'pages':pages},'modelsCalled':0,'networkRequests':0,'ledgerWritten':False}
  path=pathlib.Path(output);path.parent.mkdir(parents=True,exist_ok=True);data=gzip.compress(canonical(payload).encode(),mtime=0);path.write_bytes(data)
  report={'archiveComplete':verified,'usableForEvidence':verified,'evaluationDraftOnly':not verified,'file':str(path.resolve()),'sha256':hashlib.sha256(data).hexdigest(),'requestedEntries':len(requests),'exportedPages':len(pages),'missingPages':missing,'sourceDumpSha256':source.get('sha256'),'expectedSourceDumpSha256':source.get('expectedSha256'),'identitySourceSha256':mapping['sha256'],'ledgerWritten':False}
  path.with_suffix('.report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report
 finally:db.close();ids.close()

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',default='build/research/wiki-dump/all-articles.sqlite');p.add_argument('--identity',default='build/research/wiki-dump/page-identity.sqlite');p.add_argument('--requests',required=True);p.add_argument('--output',required=True);p.add_argument('--provisional',action='store_true');args=p.parse_args(argv);print(canonical(export(args.archive,args.identity,json.loads(pathlib.Path(args.requests).read_text()),args.output,provisional=args.provisional)))
if __name__=='__main__':main()
