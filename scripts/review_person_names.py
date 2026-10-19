#!/usr/bin/env python3
"""Independently verify JMnedict exact name-component proposals; no network IO.

Classification/parser code is not imported. A positive metadata indicator only
blocks adoption; it never establishes adult appearance. Unmatched people stay hold.
"""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET

LABELS = {'family or surname':'surname','given name or forename, gender not specified':'given',
          'female given name or forename':'fem','male given name or forename':'masc',
          'unclassified name':'unclass','full name of a particular person':'person'}
LABELS.update({'character':'char','company name':'company','creature':'creat','deity':'dei','document':'doc','event':'ev','fiction':'fict','group':'group','legend':'leg','mythology':'myth','object':'obj','organization name':'organization','other':'oth','place name':'place','product name':'product','religion':'relig','service':'serv','ship name':'ship','railway station':'station','work of art, literature, music, etc. name':'work'})
GENERIC={'surname','given','fem','masc','unclass'}
ADULT_PATTERNS=(r'(?:[^の\n]+の)*(?:AV女優|AV男優|ポルノ女優|ポルノ男優|ポルノ俳優|アダルトモデル|アダルトゲーム声優)',r'(?:[^の\n]+の)*成人向けゲームの声優')
SOURCE_URL='https://www.edrdg.org/pub/Nihongo/JMnedict.xml.gz'

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def require(condition,message):
    if not condition:raise ValueError(message)
def jsonl(path):
    op=gzip.open if str(path).endswith('.gz') else open
    with op(path,'rt',encoding='utf-8') as f:
        for line in f:
            require(bool(line.strip()),'blank JSONL record')
            yield json.loads(line)

def parse_source(source,target_pairs):
    """Return exact (reading,surface) -> entry records, with independent XML parser.

    Raw DTD codes are recovered from expanded entity descriptions. Unknown types
    retain their exact label rather than being guessed into human categories.
    """
    matches=collections.defaultdict(list)
    with gzip.open(source,'rb') as f:
        header=b''
        while b'<entry>' not in header:
            chunk=f.read(65536)
            if not chunk:break
            header+=chunk
            require(len(header)<=2*1024*1024,'oversized XML header')
        require(not re.search(rb'<!DOCTYPE[^>]*(?:SYSTEM|PUBLIC)|<!ENTITY[^>]*(?:SYSTEM|PUBLIC)',header,re.I),'external XML entities/DTD forbidden')
    with gzip.open(source,'rb') as f:
        parser=ET.iterparse(f,events=('start','end'));_,root=next(parser)
        for event,e in parser:
            if event!='end' or e.tag!='entry':continue
            seq=e.findtext('ent_seq');require(seq and seq.isdigit(),'missing/invalid ent_seq')
            spellings=[v.text for v in e.findall('./k_ele/keb') if v.text]
            types=sorted({LABELS.get(v.text,v.text or 'MISSING_TYPE') for v in e.findall('./trans/name_type')})
            if not types:types=['MISSING_TYPE']
            for reading in e.findall('r_ele'):
                reb=reading.findtext('reb')
                if not reb:continue
                restrictions={v.text for v in reading.findall('re_restr')}
                surfaces=[s for s in spellings if not restrictions or s in restrictions] if spellings else [reb]
                for surface in surfaces:
                    pair=reb,surface
                    if pair in target_pairs:
                        matches[pair].append({'ent_seq':str(seq),'types':types,'reading':reb,'surface':surface})
            e.clear();root.clear()
    for pair in matches:
        matches[pair]=sorted(matches[pair],key=lambda v:(int(v['ent_seq']),v['reading'],v['surface'],v['types']))
    return dict(matches)

def assess_match(matches):
    types={t for m in matches for t in m['types']}
    cats=set()
    if 'surname' in types:cats.add('surname')
    if types & {'given','fem','masc'}:cats.add('given_name')
    if not cats and 'unclass' in types:cats.add('personal_name')
    if not matches:reason='source_exact_pair_missing'
    elif 'person' in types:reason='specific_person_shared_form'
    elif 'MISSING_TYPE' in types:reason='source_type_missing'
    elif len(cats)>1:reason='surname_given_ambiguous'
    elif not cats:reason='generic_name_type_missing'
    else:reason='independent_generic_name_exact_match'
    eligible=reason=='independent_generic_name_exact_match'
    return {'categories':sorted(cats) if eligible else [],'primary_category':next(iter(cats)) if eligible else None,'eligible':eligible,'reason':reason}

def metadata_blockers(db):
    if db is None:return set(),None
    c=sqlite3.connect('file:'+str(Path(db).resolve())+'?mode=ro',uri=True)
    try:return _metadata_blockers_connection(c)
    finally:c.close()

def _metadata_blockers_connection(c):
    c.execute('BEGIN')
    blocked=set();audit=[]
    for bid,titles_json in c.execute('SELECT batch_id,titles FROM batches WHERE status="complete" ORDER BY batch_id').fetchall():
        edges={};adult_titles=set();hashes=[]
        parts=c.execute('SELECT part,http_status,sha256,payload_gzip FROM responses WHERE batch_id=? ORDER BY part',(bid,)).fetchall()
        require(parts or all('|' in t for t in json.loads(titles_json)),'completed metadata batch has no response')
        for i,(part,status,h,z) in enumerate(parts):
            raw=gzip.decompress(z);require(hashlib.sha256(raw).hexdigest()==h and status==200 and part==i,'metadata source integrity error');obj=json.loads(raw)
            require('error' not in obj and bool(obj.get('continue'))==(i<len(parts)-1),'metadata incomplete/error response')
            q=obj.get('query',{});hashes.append(h)
            for key in ('normalized','redirects'):
                for r in q.get(key,[]):edges[r['from']]=r['to']
            for p in q.get('pages',{}).values():
                cats=[v['title'].removeprefix('Category:') for v in p.get('categories',[])]
                if any(re.fullmatch(pattern,cat) for cat in cats for pattern in ADULT_PATTERNS):adult_titles.add(p['title'])
        for title in json.loads(titles_json):
            resolved=title;seen=set()
            while resolved in edges:
                require(resolved not in seen,'metadata redirect cycle');seen.add(resolved);resolved=edges[resolved]
            if resolved in adult_titles:blocked.add(title)
        if adult_titles:audit.append({'batch_id':bid,'source_hashes':hashes,'positive_indicator_titles':sorted(adult_titles)})
    return blocked,digest(audit)

def normalize_records(records):
    return sorted([{'ent_seq':str(v['ent_seq']),'types':sorted(v['types']),'reading':v['reading'],'surface':v['surface']} for v in records],key=lambda v:(int(v['ent_seq']),v['reading'],v['surface'],v['types']))

def review(root,source,classifier_output,workspace,output,metadata_db=None):
    # Core validates immutable workspace membership; no classifier logic imported.
    from person_subclassification import load_workspace, validate_proposal
    root,source,classifier_output,workspace,output=map(Path,(root,source,classifier_output,workspace,output))
    require(not output.exists(),'review output exists; refusing overwrite')
    snapshot,taxonomy,items=load_workspace(root,workspace)
    batch_for={k:b['batch_id'] for b in snapshot['batches'] for k in b['item_ids']}
    require(set(batch_for)=={i['item_id'] for i in items},'review requires full-corpus workspace')
    by_id={i['item_id']:i for i in items};pairs={(i['reading'],i['surface']) for i in items}
    source_sha=file_hash(source)
    manifest=json.loads((classifier_output/'manifest.json').read_text())
    require(manifest['source']['sha256']==source_sha and manifest['snapshot_id']==snapshot['snapshot_id'] and manifest['unbound_draft'] is False,'classifier manifest source/snapshot mismatch')
    for name in ('proposals.jsonl','source-matches.jsonl.gz'):
        require(manifest['files'][name]==file_hash(classifier_output/name),'classifier file integrity mismatch')
    matches=parse_source(source,pairs);blocked,blocker_digest=metadata_blockers(metadata_db)
    sidecars={}
    for v in jsonl(classifier_output/'source-matches.jsonl.gz'):
        key=v['item_id'];require(key in by_id and key not in sidecars,'duplicate/unknown source sidecar')
        i=by_id[key];pair=i['reading'],i['surface']
        require(v['reading']==pair[0] and v['surface']==pair[1] and v['source_sha256']==source_sha,'source sidecar pair/hash mismatch')
        require(normalize_records(v['matches'])==matches.get(pair,[]),'independent source entries differ')
        sidecars[key]=v
    require(all(i['item_id'] in sidecars for i in items if (i['reading'],i['surface']) in matches),'source match missing from classifier sidecar')
    proposals={}
    category_ids={v['id'] for v in taxonomy['categories']}
    for p in jsonl(classifier_output/'proposals.jsonl'):
        key=p['item_id'];require(key in by_id and key not in proposals,'duplicate/unknown proposal');validate_proposal(p,snapshot,batch_for,category_ids,by_id[key]);proposals[key]=p
    require(set(proposals)==set(by_id),'full proposals incomplete')
    require(file_hash(source)==source_sha,'source changed during independent parsing')
    for name in ('proposals.jsonl','source-matches.jsonl.gz'):
        require(manifest['files'][name]==file_hash(classifier_output/name),'classifier file changed during review')
    output.mkdir(parents=True)
    counts=collections.Counter()
    from datetime import date
    checked=date.today().isoformat()
    with (output/'reviews.jsonl').open('w',encoding='utf-8') as f:
        for item in items:
            key=item['item_id'];p=proposals[key];pair=item['reading'],item['surface'];found=matches.get(pair,[]);assessment=assess_match(found)
            if key in sidecars:require(sidecars[key]['proposal_sha256']==digest(p),'sidecar proposal hash mismatch')
            expected=assessment['eligible'];actual=p['adult_appearance_status']=='not_applicable'
            # A held classifier proposal may conservatively decline a source-supported
            # name, but it must never introduce unsupported name-component adoption.
            if actual:
                require(expected,'unsupported generic-name adoption')
                require(p['identity_status']=='name_component' and not p['entity_ids'] and not p['public_aliases'],'name component has identity links')
                require(p['categories']==assessment['categories'] and p['primary_category']==assessment['primary_category'],'independent generic category mismatch')
            decision='approve' if actual and item['surface'] not in blocked else 'hold'
            reason=assessment['reason'] if decision=='approve' else 'adult_metadata_shared_surface_requires_review' if item['surface'] in blocked else assessment['reason'] if not expected else 'classifier_conservative_hold'
            ev=[]
            for match in found:
                ev.append({'url':SOURCE_URL+'#ent_seq='+match['ent_seq'],'summary':'独立XML解析で読み・表記の完全一致を確認。ent_seq='+match['ent_seq']+'; types='+','.join(match['types'])+'; source_sha256='+source_sha+'。特定人物の非出演を確認したという意味ではない。','checked_on':checked})
            row={'schema_version':1,'snapshot_id':snapshot['snapshot_id'],'batch_id':batch_for[key],'item_id':key,'proposal_sha256':digest(p),'reviewer_id':'independent-jmnedict-reviewer-20261019','run_id':'independent-jmnedict-review-20261019','checked_on':checked,'decision':decision,'evidence':ev,'reason':reason}
            require(row['reviewer_id']!=p['classifier_id'] and row['run_id']!=p['run_id'],'self review metadata')
            f.write(canonical(row).decode()+'\n');counts[decision]+=1
    # Provenance artifact only; no count report file.
    audit={'schema_version':1,'source_url':SOURCE_URL,'source_sha256':source_sha,'reviewer_code_sha256':file_hash(__file__),'snapshot_id':snapshot['snapshot_id'],'proposal_file_sha256':file_hash(classifier_output/'proposals.jsonl'),'classifier_sidecar_sha256':file_hash(classifier_output/'source-matches.jsonl.gz'),'metadata_positive_blocker_digest':blocker_digest,'reviews_sha256':file_hash(output/'reviews.jsonl'),'checked_on':checked,'scope':'Independent exact generic-name evidence; full particular-person matches vetoed; no adult absence assertion.'}
    (output/'source-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    return dict(counts)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--classifier-output',type=Path,required=True);ap.add_argument('--workspace',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--metadata-db',type=Path);a=ap.parse_args()
    try:print(json.dumps(review(a.root,a.source,a.classifier_output,a.workspace,a.output,a.metadata_db),ensure_ascii=False))
    except (ValueError,KeyError,TypeError,OSError,ET.ParseError,sqlite3.Error) as e:ap.exit(1,'error: '+str(e)+'\n')
if __name__=='__main__':main()
