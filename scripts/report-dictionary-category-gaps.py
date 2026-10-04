#!/usr/bin/env python3
"""Inspect reading-verified, unclassified entries; linked type counts are not adoption decisions."""
import sqlite3,csv,gzip,json,collections,argparse
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--snapshot',default='build/dictionary-metadata/snapshot.sqlite');parser.add_argument('--audit',default='build/reports/dictionary-quality/audit.tsv.gz');parser.add_argument('--output',default='build/reports/dictionary-quality/category-gaps.json');args=parser.parse_args()
c=sqlite3.connect('file:'+str(Path(args.snapshot).resolve())+'?mode=ro',uri=True);types=collections.Counter();fields=collections.Counter();pos=collections.Counter();samples=collections.defaultdict(list);field_samples=collections.defaultdict(list);total=0;links=0;lexical=0
with gzip.open(args.audit,'rt') as f:
 for r in csv.DictReader(f,delimiter='\t'):
  if r['phase']!='classification' or r['quality_status']!='accepted' or r['categories']!='unclassified':continue
  total+=1;seen=set();fs=set();ps=set()
  for result in c.execute('select body from lexical_details where reading=? and surface=?',(r['reading'],r['surface'])):
   fact=json.loads(result[0]);fs.update(fact.get('fields',[]));ps.update(fact.get('pos',[]));lexical+=1
  fields.update(fs);pos.update(ps)
  for field in fs:
   if len(field_samples[field])<10:field_samples[field].append({'reading':r['reading'],'surface':r['surface']})
  row=c.execute('select ids,direct_ids from lookup where surface=?',(r['surface'],)).fetchone()
  if row:
   for ident in json.loads(row[0]):
    for body in c.execute('select body from entities where id=?',(ident,)):
     entity=json.loads(body[0]);seen.update(entity['types'])
  types.update(seen)
  for typ in seen:
   if len(samples[typ])<10:samples[typ].append({'reading':r['reading'],'surface':r['surface']})
result={'readingVerifiedUnclassified':total,'typeCountsCandidateLinksOnly':dict(types.most_common(50)),'typeExamples':{k:samples[k] for k,_ in types.most_common(30)},'jmdictFieldCounts':dict(fields.most_common()),'jmdictPosCounts':dict(pos.most_common()),'fieldExamples':dict(field_samples),'caveat':'Entity links include unresolved same-name/search associations; counts are investigation opportunities, not adopted or category-confirmed counts. JMdict fields are pair-constrained senses.'}
Path(args.output).parent.mkdir(parents=True,exist_ok=True)
Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'readingVerifiedUnclassified':total,'typeCountsCandidateLinksOnly':dict(types.most_common(12)),'jmdictFieldCounts':dict(fields.most_common())},ensure_ascii=False))
c.close()
