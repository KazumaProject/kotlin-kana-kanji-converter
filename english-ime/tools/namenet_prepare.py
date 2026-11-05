"""Prepare and independently verify the pinned NameNet snapshot offline.

Keep the unmodified entry references and prove any duplicated-prefix repair
through exact reverse Synset membership. Two independent streaming parsers
provide replayable evidence without loading the full resource into memory.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
import xml.parsers.expat


def extract_entries(args):
    source = args.snapshot
    out = args.out / 'prepared'
    assert not out.exists();out.mkdir()
    base=args.base;states=[json.loads(x) for x in (base/'status.jsonl').read_text().splitlines()];wanted={r['surface'].casefold() for r in states if r['decision']=='pending'}
    expected='5ecc450882f4e1b9136a86d17e05b062fd90621afd6ff94eea45cbd2b9b0939e'
    with source.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected
    entries=[];synsets={};targets=set();stack=[];total=0;scount=0;start=time.monotonic();lexicons=[]
    with gzip.open(source,'rb') as f:
     for event,e in ET.iterparse(f,events=('start','end')):
      if event=='start':
       stack.append(e)
       if e.tag=='Lexicon':lexicons.append(dict(e.attrib))
       continue
      if e.tag=='LexicalEntry':
       total+=1;lemma=e.find('Lemma')
       if lemma is not None and lemma.get('writtenForm','').casefold() in wanted:
        value={'attributes':dict(e.attrib),'lemma':dict(lemma.attrib),'forms':[dict(x.attrib) for x in e.findall('Form')],
          'senses':[dict(x.attrib) for x in e.findall('Sense')],'xml':ET.tostring(e,encoding='unicode')}
        entries.append(value);targets.update(x['synset'] for x in value['senses'])
       stack[-2].remove(e);e.clear()
       if total%250000==0:print(json.dumps({'entries':total,'matches':len(entries),'targetSynsets':len(targets),'seconds':round(time.monotonic()-start,1)}),flush=True)
      elif e.tag=='Synset':
       scount+=1
       if e.get('id') in targets:synsets[e.get('id')]={'attributes':dict(e.attrib),'xml':ET.tostring(e,encoding='unicode')}
       stack[-2].remove(e);e.clear()
       if scount%500000==0:print(json.dumps({'synsets':scount,'matchedSynsets':len(synsets),'seconds':round(time.monotonic()-start,1)}),flush=True)
      stack.pop()
    (out/'entries.json').write_text(json.dumps(entries,indent=2,ensure_ascii=False)+'\n');(out/'synsets.json').write_text(json.dumps(synsets,indent=2,ensure_ascii=False)+'\n')
    manifest={'snapshotSha256':expected,'revision':'55bc7f4001388a5a41a1fd379f23652a4f8c02fe','lexicons':lexicons,'baseManifestSha256':hashlib.sha256((base/'manifest.json').read_bytes()).hexdigest(),'scannedEntries':total,'scannedSynsets':scount,'matchedEntries':len(entries),'matchedSynsets':len(synsets),'unmatchedTargetSynsets':sorted(targets-set(synsets)),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest),flush=True)


def verify_references(args):
    folder = args.out
    base = folder / 'prepared'
    out = folder / 'prepared-reference-check'
    out.mkdir()
    entries=json.loads((base/'entries.json').read_text());wanted=set()
    for e in entries:
     for s in e['senses']:
      target=s['synset'];wanted.add(target)
      if re.fullmatch(r'oenn-oenn-Q[1-9][0-9]*-n',target):wanted.add(target[len('oenn-'):])
    parser=xml.parsers.expat.ParserCreate();records={};current=None;depth=0;textkey=None;total=0;started=time.monotonic();examples=[]
    def start(name,attrs):
     nonlocal current,depth,textkey,total
     if name=='Synset':
      total+=1
      if len(examples)<3 and attrs['id'].startswith('oenn-Q'):examples.append(dict(attrs))
      if attrs['id'] in wanted:current={'attributes':dict(attrs),'relations':[],'definitions':[]};depth=1
      if total%1000000==0:print(json.dumps({'synsets':total,'matched':len(records),'seconds':round(time.monotonic()-started,1)}),flush=True)
     elif current is not None:
      depth+=1
      if name=='SynsetRelation':current['relations'].append(dict(attrs))
      elif name in {'Definition','ILIDefinition'}:textkey=[]
    def chars(text):
     if textkey is not None:textkey.append(text)
    def end(name):
     nonlocal current,depth,textkey
     if current is None:return
     if name in {'Definition','ILIDefinition'} and textkey is not None:current['definitions'].append(''.join(textkey));textkey=None
     depth-=1
     if depth==0:
      identifier=current['attributes']['id'];assert identifier not in records;records[identifier]=current;current=None
    parser.StartElementHandler=start;parser.EndElementHandler=end;parser.CharacterDataHandler=chars
    with gzip.open(args.snapshot,'rb') as f:
     while chunk:=f.read(4*1024*1024):parser.Parse(chunk,False)
    parser.Parse(b'',True)
    (out/'synsets.json').write_text(json.dumps(records,indent=2,ensure_ascii=False)+'\n')
    audit=[]
    for e in entries:
     for s in e['senses']:
      original=s['synset'];candidate=original[len('oenn-'):] if re.fullmatch(r'oenn-oenn-Q[1-9][0-9]*-n',original) else original
      synset=records.get(candidate);members=synset['attributes'].get('members','').split() if synset else []
      audit.append({'entryId':e['attributes']['id'],'writtenForm':e['lemma']['writtenForm'],'senseId':s['id'],'originalTarget':original,'candidateTarget':candidate,'targetExists':synset is not None,'exactReverseMembership':e['attributes']['id'] in members,'prefixChanged':candidate!=original})
    (out/'audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n')
    meta={'originalPreparedManifestSha256':hashlib.sha256((base/'manifest.json').read_bytes()).hexdigest(),'scannedSynsets':total,'matchedSynsets':len(records),'verifiedLinks':sum(r['targetExists'] and r['exactReverseMembership'] for r in audit),'verifiedPrefixRepairs':sum(r['targetExists'] and r['exactReverseMembership'] and r['prefixChanged'] for r in audit),'synsetExamples':examples,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()}}
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'snapshot', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Output already exists')
    before = args.snapshot.stat()
    args.out.mkdir(parents=True)
    extract_entries(args)
    verify_references(args)
    after = args.snapshot.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Snapshot changed while preparing')
