#!/usr/bin/env python3
"""Record losses of previously published entries, separately from new rescues."""
import argparse,csv,gzip,json,hashlib,collections
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--before',required=True);p.add_argument('--after',required=True);p.add_argument('--output',required=True);a=p.parse_args()
def rows(path):
 with gzip.open(path,'rt',encoding='utf-8') as f:yield from csv.DictReader(f,delimiter='\t')
def key(r):return tuple(r[k] for k in ('reading','surface','left_id','right_id'))
def adopted(r):return r['phase']=='classification' and r['quality_status']=='accepted' and r['categories']!='unclassified'
old={key(r):r for r in rows(a.before) if adopted(r)};total=len(old);current={};retained=0
for r in rows(a.after):
 k=key(r)
 if k in old:
  if adopted(r):retained+=1;del old[k];current.pop(k,None)
  elif r['phase']=='classification' or r['quality_status']=='excluded':current[k]=r
out=Path(a.output);out.mkdir(parents=True,exist_ok=True);reasons=collections.Counter()
with gzip.open(out/'previously-published-losses.tsv.gz','wt',encoding='utf-8') as f:
 w=csv.writer(f,delimiter='\t',lineterminator='\n');w.writerow(['reading','surface','left_id','right_id','before_categories','after_status','verification_issue','semantic_issue','reading_evidence'])
 for k,r in sorted(old.items()):
  now=current.get(k,{});status=now.get('quality_status','missing');issue=now.get('verification_issue','');reasons[(status,issue)]+=1
  w.writerow([*k,r['categories'],status,issue,now.get('semantic_issue',''),now.get('reading_evidence','')])
result={'previouslyPublished':total,'retained':retained,'returnedToReview':len(old),'reasons':{'/'.join(k):v for k,v in sorted(reasons.items())},'beforeAuditSha256':hashlib.file_digest(open(a.before,'rb'),'sha256').hexdigest(),'afterAuditSha256':hashlib.file_digest(open(a.after,'rb'),'sha256').hexdigest(),'lossesSha256':hashlib.file_digest(open(out/'previously-published-losses.tsv.gz','rb'),'sha256').hexdigest()}
(out/'retention.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
assert all(k[0]!='missing' for k in reasons),'Previously published entries missing from audit'
