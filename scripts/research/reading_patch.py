"""Source-only corrective reading extraction from verified retained articles.

The optional label-free cohort limits inspection, never supplies categories.
Completed research rounds and final decisions are deliberately not modified.
"""
import argparse,collections,gzip,json,pathlib,re,sqlite3,time
import worker as w
import wiki_dump as dump
import source_rounds as search

VERSION=2

LEGAL_NAME = re.compile(r'^(?:株式会社|有限会社|合同会社)|(?:株式会社|有限会社|合同会社)$')

def company_base(name):
    return LEGAL_NAME.sub('',name)

def quoted_phonetic_text(text):
    value=dump.name_key(w.reading(visible_source(text)))
    # Printed syllable separators do not supply a phoneme. Keep prolonged
    # sound marks, alternatives and all non-kana boundaries intact.
    return re.sub(r'(?<=[ぁ-ゖー])[-・](?=[ぁ-ゖー])','',value)

def materialize_reviewed(db,args,stage,identity,meta,ident,e,identity_doc):
    package=json.loads(pathlib.Path(args.reviewed).read_text())
    cases=package.get('cases',[])
    if not package.get('inspector') or not 1<=len(cases)<=100:raise ValueError('Named direct inspector and 1..100 reading reviews required')
    prepared=[]
    for item in cases:
        row=db.execute('SELECT id,reading,surface FROM candidates WHERE id=?',(item['candidateId'],)).fetchone()
        if row is None or row['reading']!=item['reading'] or row['surface']!=item['surface']:raise ValueError('Reviewed pair must be an unchanged existing input')
        page=stage.execute('SELECT * FROM pages WHERE page_id=?',(item['pageId'],)).fetchone()
        qid=identity.execute('SELECT qid,quotation FROM page_identity WHERE page_id=?',(item['pageId'],)).fetchone()
        if page is None or qid is None or qid[0]!=item['target'] or w.digest(page['content'])!=item['pageContentSha256'] or str(page['revision'])!=str(item['revision']):raise ValueError('Reviewed source/referent identity changed')
        quote=item['quotation'];visible=quoted_phonetic_text(quote);bound_surface=dump.name_key(w.reading(item['surface']))
        if not quote or quote not in page['content'] or item['reading'] not in visible or bound_surface not in visible:raise ValueError('Full spelling and literal kana reading must both be quoted from the original')
        if item.get('sameReferentVerified') is not True or not item.get('bindingRationale'):raise ValueError('Explicit same-referent inspection required')
        dump.verified_page_text(page['content'],page['text_sha1']);prepared.append((dict(row),page,qid,item))
    # Preserve the exact independently authored review input as immutable
    # evidence as well as preserving its primary source quotations.
    review_bytes=pathlib.Path(args.reviewed).read_bytes();review_sha=w.digest(review_bytes)
    review_doc=e.save(args.url+'#direct-inspection-record-'+review_sha,review_sha,review_bytes,'Independent direct inspection record')
    # Validate the complete review batch before registering any fact.
    for row,page,qid,item in prepared:
        payload={'sourceProjection':'Literal verified Wikipedia XML fields; directly inspected reading','source':meta,
            'query':{'pages':{str(page['page_id']):{'pageid':page['page_id'],'title':page['title'],'revisions':[{'revid':int(page['revision']),'timestamp':page['timestamp'],'sha1':page['text_sha1'],'slots':{'main':{'*':page['content']}}}]}}}}
        did=e.save(args.url+'#direct-reading-review-page-'+str(page['page_id']),meta['sha256'],gzip.compress(w.canonical(payload).encode(),mtime=0),'Wikipedia CC-BY-SA; literal XML source projection')
        identity_fact=e.fact('',row['surface'],'context',[],qid[0],identity_doc,{'source':'Wikipedia-page-identity','pageId':page['page_id'],'title':page['title'],'qid':qid[0],'quotation':qid[1],'sourceSha256':ident['sha256']})
        inspection_fact=e.fact(row['reading'],row['surface'],'context',[],qid[0],review_doc,{'source':'Direct reading inspection record','inspector':package['inspector'],'reviewInputSha256':review_sha,'bindingRationale':item['bindingRationale'],'primaryDocumentId':did})
        e.fact(row['reading'],row['surface'],'context',[],qid[0],did,{'source':'Wikipedia','title':page['title'],'revision':int(page['revision']),'lead':w.wiki_lead(page['content']),'primaryNameVerified':True,'inspector':package['inspector'],'componentFacts':[identity_fact,inspection_fact],'acquisition':{'sourceDumpSha256':meta['sha256'],'sourcePageId':page['page_id'],'reviewInputSha256':review_sha}})
        e.fact(row['reading'],row['surface'],'reading',[],qid[0],did,{'source':'explicit-name-reading','name':row['surface'],'reading':row['reading'],'quotation':item['quotation'],'binding':'independently-inspected-explicit-referent','bindingRationale':item['bindingRationale'],'inspector':package['inspector'],'componentFacts':[identity_fact,inspection_fact],'revision':int(page['revision']),'acquisition':{'sourceDumpSha256':meta['sha256'],'sourcePageId':page['page_id'],'reviewInputSha256':review_sha}})
    db.commit()
    return {'directReadingReviewsImported':len(prepared),'qualityDecisionsMade':0,'researchRoundsChanged':0,'modelsCalled':0,'networkRequests':0}

def visible_source(text):
    text=re.sub(r'<!--.*?-->','',text,flags=re.S)
    text=re.sub(r'<ref\b[^>]*?(?:/>|>.*?</ref>)','',text,flags=re.S|re.I)
    return re.sub(r'\{\{(?:[Ss]fn|[Hh]arv(?:nb|txt)?|[Ss]fnp)\|[^{}]*\}\}','',text)

def adjacent_aliases(title,text):
    # The explicit aliases must belong to the primary name's own immediate
    # parenthetical. A later mention or another person's name cannot bind it.
    first=re.search(r"'''([^'\n]+)'''\s*[（(]",text)
    if not first or not w.same_name(first[1],title):return set()
    start=first.end();depth=1;end=start
    for end in range(start,len(text)):
        if text[end] in '（(':depth+=1
        elif text[end] in '）)':
            depth-=1
            if not depth:break
        if text[end]=='\n':return set()
    if depth:return set()
    return {dump.name_key(m[1]) for m in re.finditer(r"(?:通称|略称|別名|芸名|名義)[\s、,：:]*'''([^'\n]+)'''",text[start:end])}

def corrected_bindings(title,text,index):
    visible=visible_source(text);aliases=adjacent_aliases(title,visible);found={}
    for name,y,quote in search.full_body_reading_bindings(visible):
        names=[name]
        base=company_base(name)
        # The source itself omits the legal designation from its printed
        # pronunciation. Strip only that exact written-name boundary and
        # only when it is the article's primary company, never a mention.
        legal_primary=(base!=name and (w.same_name(base,title) or w.same_name(name,title)))
        if legal_primary:names.append(base)
        rows={r['id']:r for n in names for r in index.get(dump.name_key(n),())}
        for row in rows.values():
            if w.reading(y)!=w.reading(row['reading']):continue
            target,binding=search.binding_target(title,visible,row['surface'])
            if dump.name_key(row['surface']) in aliases:target,binding=title,'declared-adjacent-primary-alias'
            if legal_primary and dump.name_key(row['surface']) in {dump.name_key(name),dump.name_key(base)}:
                target,binding=title,'literal-primary-company-legal-name-boundary'
            if target!=title:continue
            literal=dump.literal_quote(text,quote)
            if not literal:continue
            body={'source':'explicit-name-reading','name':name,'reading':y,'quotation':literal,'binding':binding,'correctiveReadingParser':VERSION}
            found[(row['id'],w.digest(w.canonical(body)))]=(row,body)
    return list(found.values())

def apply(db,args):
    stage=sqlite3.connect('file:'+str(pathlib.Path(args.staging).resolve())+'?mode=ro',uri=True);stage.row_factory=sqlite3.Row
    identity=sqlite3.connect('file:'+str(pathlib.Path(args.identity_index).resolve())+'?mode=ro',uri=True)
    try:
        meta=json.loads(stage.execute("SELECT value FROM meta WHERE key='source'").fetchone()[0]);ident=json.loads(identity.execute("SELECT value FROM meta WHERE key='source'").fetchone()[0])
        if not meta.get('complete') or not ident.get('complete') or w.sha(ident['source'])!=ident['sha256']:raise ValueError('Verified original source and page identity required')
        if pathlib.Path(ident['source']).name.split('-')[1]!=meta['file'].split('-')[1]:raise ValueError('Source snapshot mismatch')
        e=w.Evidence(db,args);identity_doc=e.save(ident['url'],ident['sha256'],pathlib.Path(ident['source']).read_bytes(),'Wikipedia CC-BY-SA; literal page identity SQL')
        if getattr(args,'reviewed',None):return materialize_reviewed(db,args,stage,identity,meta,ident,e,identity_doc)
        selected=None
        if args.selection:selected={r['candidateId'] for r in json.loads(pathlib.Path(args.selection).read_text())['cases']}
        index=collections.defaultdict(list)
        for row in db.execute('SELECT id,reading,surface FROM candidates'):
            if selected is None or row['id'] in selected:index[dump.name_key(row['surface'])].append(dict(row))
        page_qids={pid:qid for pid,qid in identity.execute('SELECT page_id,qid FROM page_identity')}
        counts=collections.Counter();started=time.monotonic()
        for page in stage.execute('SELECT * FROM pages ORDER BY page_id'):
            # Only pages with a selected primary name or a stored selected
            # mentioned-name binding need corrective inspection of full text.
            if selected is not None and not any(r['id'] in selected for r in json.loads(page['contexts'])+ [p['candidate'] for p in json.loads(page['proofs'])]):continue
            counts['pagesInspected']+=1
            bound=corrected_bindings(page['title'],page['content'],index)
            if not bound:continue
            qid=page_qids.get(page['page_id']);target=qid or page['title'];new=[]
            for row,body in bound:
                if not db.execute("SELECT 1 FROM facts WHERE active=1 AND kind='reading' AND surface=? AND reading=? AND target=? LIMIT 1",(row['surface'],row['reading'],target)).fetchone():new.append((row,body))
            if not new:continue
            content=dump.verified_page_text(page['content'],page['text_sha1'])
            payload={'sourceProjection':'Literal verified Wikipedia XML fields; corrective reading inspection','source':meta,
                     'query':{'pages':{str(page['page_id']):{'pageid':page['page_id'],'title':page['title'],'revisions':[{'revid':int(page['revision']),'timestamp':page['timestamp'],'sha1':page['text_sha1'],'slots':{'main':{'*':content}}}]}}}}
            did=e.save(args.url+'#corrective-readings-page-'+str(page['page_id']),meta['sha256'],gzip.compress(w.canonical(payload).encode(),mtime=0),'Wikipedia CC-BY-SA; literal XML source projection')
            quote=identity.execute('SELECT quotation FROM page_identity WHERE page_id=?',(page['page_id'],)).fetchone() if qid else None
            for row,body in new:
                dependencies=[]
                if quote:dependencies=[e.fact('',row['surface'],'context',[],qid,identity_doc,{'source':'Wikipedia-page-identity','pageId':page['page_id'],'title':page['title'],'qid':qid,'quotation':quote[0],'sourceSha256':ident['sha256']})]
                e.fact(row['reading'],row['surface'],'reading',[],target,did,{**body,'revision':int(page['revision']),'componentFacts':dependencies,'acquisition':{'sourceDumpSha256':meta['sha256'],'sourcePageId':page['page_id'],'correctiveParserVersion':VERSION}});counts['newExactTargetReadings']+=1
            db.commit()
        result={'counts':dict(counts),'sourceSha256':meta['sha256'],'correctiveParserVersion':VERSION,'cohortRestricted':bool(selected),'seconds':round(time.monotonic()-started,2),'qualityDecisionsMade':0,'researchRoundsChanged':0,'modelsCalled':0,'networkRequests':0}
        w.info(db,'correctiveReadingInspection',result);db.commit();return result
    finally:stage.close();identity.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ledger',default='build/research/ledger.sqlite');p.add_argument('--documents',default='build/research/documents');p.add_argument('--config',default=str(w.DEFAULT_CONFIG));p.add_argument('--staging',required=True);p.add_argument('--identity-index',required=True);p.add_argument('--selection');p.add_argument('--reviewed');p.add_argument('--url',required=True);a=p.parse_args()
    with w.coordinator_lock(a.ledger),w.connect(a.ledger) as db:w.emit(apply(db,a))

if __name__=='__main__':main()
