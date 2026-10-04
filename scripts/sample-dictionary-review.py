import csv,gzip,json,hashlib,collections,argparse
from pathlib import Path
a=argparse.ArgumentParser();a.add_argument('--before',required=True);a.add_argument('--after',default='build/reports/dictionary-quality/audit.tsv.gz');a.add_argument('--output',default='build/reports/dictionary-quality/review-samples');args=a.parse_args()
base=Path(args.before);new=Path(args.after)
def rows(p):
 with gzip.open(p,'rt') as f:
  for r in csv.DictReader(f,delimiter='\t'):
   if r['phase']=='classification':yield r
def key(r):return tuple(r[k] for k in ['reading','surface','left_id','right_id'])
def accepted(r):return r['quality_status']=='accepted' and r['categories']!='unclassified'
old={key(r) for r in rows(base) if accepted(r)}
cats=collections.defaultdict(list);held=collections.defaultdict(list)
for r in rows(new):
 if accepted(r) and key(r) not in old:
  for c in r['categories'].split(','):cats[c].append(r)
 elif not accepted(r):held[(r['quality_status'],r.get('verification_issue',''),r['sources'])].append(r)
def rank(r):return hashlib.sha256('\t'.join(key(r)).encode()).hexdigest()
out=Path(args.output);out.mkdir(exist_ok=True)
for c,rs in cats.items():
 rs=sorted(rs,key=rank)[:100]
 (out/(c+'.json')).write_text(json.dumps(rs,ensure_ascii=False,indent=2)+'\n')
 print(c,len(rs))
rs=[]
for group,items in sorted(held.items()):
 rs+=sorted(items,key=rank)[:max(1,round(500*len(items)/sum(len(x) for x in held.values())))]
rs=sorted(rs,key=rank)[:500]
if len(rs)<500:
 seen={key(r) for r in rs};extra=sorted([r for v in held.values() for r in v if key(r) not in seen],key=rank);rs+=extra[:500-len(rs)]
(out/'held.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2)+'\n')
(out/'manifest.json').write_text(json.dumps({'selection':'SHA-ranked new adopted entries per category; held stratified by source/status/missing fact','adopted':{c:min(100,len(rs)) for c,rs in cats.items()},'held':len(rs),'baselineAuditSha256':hashlib.file_digest(base.open('rb'),'sha256').hexdigest(),'currentAuditSha256':hashlib.file_digest(new.open('rb'),'sha256').hexdigest()},indent=2)+'\n')
