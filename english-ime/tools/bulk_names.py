"""Stream the complete raw Wiktextract dump; extract attested English name roles."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote

import vocabulary_harness as h

URL='https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz'


def topics(row):
    if row.get('lang_code')!='en' or row.get('pos')!='name':return []
    categories=set(row.get('categories',[]))
    for sense in row.get('senses',[]):categories.update(sense.get('categories',[]))
    found=set()
    for category in categories:
        if re.search(r'^English .*given names(?: |$)',category):found.add('names.given')
        if re.search(r'^English (?:.* )?surnames(?: |$)',category):found.add('names.surname')
        if category=='English middle names':found.add('names.middle')
    return sorted(found)


def capture(archive,directory,index,review_terms=None):
    archive=h.external(archive);directory=h.external(directory);directory.mkdir(parents=True,exist_ok=True)
    with h.lock(directory):
        if (directory/'bulk.json').exists():
            value=verify(directory)
            expected=set(h.replay.read_json(h.external(review_terms))) if review_terms else set()
            h.require(value['rawArchiveSha256']==h.replay.sha(archive) and
                      value['catalogueSha256']==h.replay.sha(h.external(index)) and
                      set(h.replay.read_json(directory/'review-terms.json'))==expected,
                      'Bulk capture already exists for different inputs')
            return value
        h.require(archive.name.endswith('.gz') and archive.stat().st_size<4*1024**3,'Invalid/oversized raw archive')
        terms=set(h.replay.read_json(h.external(review_terms))) if review_terms else set()
        temporary=directory/'selected.jsonl.partial';counts=Counter();expanded=0
        review_path=directory/'sense-review.jsonl.partial'
        with gzip.open(archive,'rb') as stream,temporary.open('wb') as selected,review_path.open('wb') as review:
            for line in stream:
                expanded+=len(line);h.require(expanded<40*1024**3 and len(line)<64*1024**2,'Oversized expanded record/dump')
                row=json.loads(line);counts['allRecords']+=1
                if row.get('lang_code')=='en':
                    counts['englishRecords']+=1
                    if row.get('word') in terms:
                        review.write(line);counts['senseReviewRecords']+=1
                if topics(row):
                    selected.write(line);counts['selectedRecords']+=1
                if counts['allRecords']%500000==0:print(json.dumps(dict(counts)),flush=True)
        # Reading gzip to EOF validates the compressed stream/CRC, rather than
        # considering a prefix or a chosen number of selected names complete.
        h.require(counts['englishRecords'] and counts['selectedRecords'],'Empty English/name corpus')
        temporary.replace(directory/'selected.jsonl')
        review_path.replace(directory/'sense-review.jsonl')
        (directory/'review-terms.json').write_text(json.dumps(sorted(terms),ensure_ascii=False)+'\n')
        (directory/'catalogue.html').write_bytes(h.external(index).read_bytes())
        notice=directory/'BULK-NAMES-SOURCES.txt'
        notice.write_text('Wiktionary contributors: English proper-name records, CC BY-SA 4.0 / GFDL.\n'
            'Raw Wiktextract extraction by Tatu Ylonen and contributors, downloaded from '+URL+'\n'
            'Catalogue: https://kaikki.org/dictionary/rawdata.html\n'
            'Changes: scan complete gzip to EOF, retain explicit English name categories and exact attested spellings; '
            'retain selected English entries for homonym/medical distribution review. No name splitting or generated combinations.\n'
            'The source archive and selected raw rows are retained outside Git; checksums identify the exact capture.\n'
            'https://en.wiktionary.org/wiki/Wiktionary:Copyrights\n'
            'Preserve the full CC BY-SA 4.0 / GFDL notices supplied with this dictionary.\n',encoding='utf-8')
        value=dict(schemaVersion=1,url=URL,catalogueUrl='https://kaikki.org/dictionary/rawdata.html',
            catalogueSha256=h.replay.sha(h.external(index)),rawArchiveSha256=h.replay.sha(archive),rawArchiveBytes=archive.stat().st_size,
            expandedBytes=expanded,counts=dict(counts),selectedSha256=h.replay.sha(directory/'selected.jsonl'),senseReviewSha256=h.replay.sha(directory/'sense-review.jsonl'),
            reviewTermsSha256=h.replay.sha(directory/'review-terms.json'),noticeSha256=h.replay.sha(notice),
            complete=True,language='en',license='CC-BY-SA-4.0',selection='Explicit English given-name/surname category membership on proper-name records; no name splitting or synthetic combinations.')
        h.dump(directory/'bulk.json',value);return verify(directory)


def verify(directory):
    directory=h.external(directory);v=h.replay.read_json(directory/'bulk.json')
    h.require(v['schemaVersion']==1 and v['url']==URL and v['language']=='en' and v['complete'] and
              h.replay.sha(directory/'selected.jsonl')==v['selectedSha256'],'Changed/incomplete bulk-name evidence')
    for name,field in [('sense-review.jsonl','senseReviewSha256'),('review-terms.json','reviewTermsSha256'),('catalogue.html','catalogueSha256'),('BULK-NAMES-SOURCES.txt','noticeSha256')]:
        h.require(h.replay.sha(directory/name)==v[field],'Changed bulk source review/notice: '+name)
    count=0
    with (directory/'selected.jsonl').open('rb') as stream:
        for line in stream:
            h.require(topics(json.loads(line)),'Selected bulk record no longer matches its declared name roles');count+=1
    h.require(count==v['counts']['selectedRecords'],'Changed bulk-name record count')
    return v


def collect(directory):
    directory=h.external(directory);v=verify(directory);records={}
    with (directory/'selected.jsonl').open('rb') as stream:
        for line in stream:
            row=json.loads(line);surface=row['word']
            item=records.setdefault(surface,dict(surface=surface,kind='person',entity='name-component:'+surface,topics=[],proofs=[]))
            item['topics']=sorted(set(item['topics'])|set(topics(row)))
            proof=dict(source='wiktextract_raw_name',url='https://en.wiktionary.org/wiki/'+quote(surface,safe='')+'#English',
                license='CC-BY-SA-4.0',sha256=hashlib.sha256(line).hexdigest(),archiveSha256=v['rawArchiveSha256'],
                headRole='proper-name',scope='Explicit English name categories; source sense frequency/modernity not inferred.')
            if proof not in item['proofs']:item['proofs'].append(proof)
    return sorted(records.values(),key=lambda r:r['surface']),v


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--index',type=Path,required=True)
    p.add_argument('--review-terms',type=Path)
    args=p.parse_args();print(json.dumps(capture(args.archive,args.source_dir,args.index,args.review_terms),ensure_ascii=False))
