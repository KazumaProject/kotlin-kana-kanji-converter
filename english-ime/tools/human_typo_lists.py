"""Read only explicit unannotated typo pairs from pinned Wikipedia lists.

Unlinked entries and annotated acceptable variants/false positives are leads,
not exclusions. Independent modern readings and extraction errors still block
exclusion, and all machine decisions can be reopened by later positive proof.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

import explicit_misspellings as typos
import extend_lexicon as extension
import lexicon_pipeline as pipeline
from wiktionary_index import Index

PINS={'ABCDEF.json':'bb0ab0ba098933e5e8bbc799503e28cadccb5895bd4dc076cf89bc8c2125a0f6',
    'GHIJKL.json':'8db2a88a09d1dacf3c7a1fc0feb8f51f08ad2698e88e55fda4eec2a60c3056ae',
    'MNOPQR.json':'f4d1a74907cbcf37205234a94b79ff3990a5374535cea910113572d0250ec1ed',
    'STUVWX.json':'7d32f3794b0e4b7043a6459ce8f829265040a249eb5896468d916d12de4418c8',
    'YZ.json':'aacb45a82ec330c546a5e83fc20f6362de8fafc44f607f383908d838a23b2a34'}


def plain(text):
    return re.sub(r'\[\[(?:[^\]|]+\|)?([^\]]+)\]\]',r'\1',text).strip().strip('"')


def pairs_in(text):
    for number,line in enumerate(text.splitlines(),1):
        match=re.fullmatch(r'\*\s*\{\{search link\|([^{}]+)\}\}\s*\(([^()]+)\)\s*',line)
        if not match:continue
        args=match[1].split('|');word=plain(args[1] if len(args)>1 and args[1] else args[0])
        corrected=[plain(value) for value in match[2].split(',')]
        if (not re.fullmatch(r"[A-Za-z][A-Za-z'\-]*",word) or
                any(not re.fullmatch(r"[A-Za-z][A-Za-z' \-]*",value) for value in corrected)):continue
        yield word,corrected,number,hashlib.sha256(line.encode()).hexdigest()


def load(directory):
    pairs=defaultdict(set);proof={};pages=[]
    for name,expected in sorted(PINS.items()):
        if pipeline.digest(directory/name)!=expected:raise ValueError('Changed Wikipedia typo page snapshot')
        data=json.loads((directory/name).read_text())
        for page in data['query']['pages'].values():
            if 'missing' in page:raise ValueError('Missing typo list page')
            revision=page['revisions'][0];pages.append({'title':page['title'],'revision':revision['revid']})
            for word,corrected,line,line_hash in pairs_in(revision['slots']['main']['*']):
                pairs[word].update(corrected)
                proof[word]={'source':'wikipedia_misspelling_list',
                    'url':'https://en.wikipedia.org/w/index.php?title='+quote(page['title'].replace(' ','_'),safe='')+'&oldid='+str(revision['revid']),
                    'revision':revision['revid'],'snapshotSha256':expected,'sourcePage':page['title'],
                    'line':line,'sourceLineSha256':line_hash,'unannotatedSearchEntry':True,
                    'correctionVerification':'independently approved whole correction or every whitespace-separated correction word; no invented correction'}
    if len(pages)!=26:raise ValueError('Incomplete A-Z typo list')
    return pairs,proof,pages


def extend(args):
    pairs,proof,pages=load(args.sources)
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    states=[json.loads(x) for x in (args.base/'status.jsonl').read_text().splitlines()]
    selected=[row for row,state in zip(rows,states) if state['decision']=='pending']
    exact=defaultdict(list);index=Index(args.index)
    try:
        for _,record in index.lookup({row['surface'] for row in selected if row['surface'] in pairs}):exact[record['word']].append(record)
    finally:index.close()
    additions=typos.exclusions(model,selected,pairs,exact,pending,provenance=proof,allow_word_sequences=True)
    prior=args.base/'reviewed-overrides.tsv';reviews=pipeline.read_table(prior,'decisions') if prior.is_file() else []
    existing={row['id'] for row in reviews};reviews += [row for row in additions if row['id'] not in existing]
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    sources['wikipediaHumanTypoLists']={'files':PINS,'pages':sorted(pages,key=lambda x:x['title']),
        'policy':'explicit unannotated search-link typo pairs only; skip unlinked false positives and annotated variants; exact modern readings and approved case alternatives block exclusions; independently verified corrections; source absence alone never excludes'}
    notices['WIKIPEDIA-AZ-TYPO-NOTICE.txt']=('Wikipedia contributors, Lists of common misspellings/A-Z, revisions pinned in manifest.json.\nhttps://en.wikipedia.org/wiki/Wikipedia:Lists_of_common_misspellings\n'
        'CC BY-SA 4.0; full license retained in CC-BY-SA-4.0.txt.\nChanges: selected only explicit, unannotated typo/correction search entries; verified correction words locally; excluded neither unlinked/annotated variants nor independently approved names or unresolved modern English readings. Original input rows preserved.\n').encode()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.human-typo-review-',dir=args.out.parent) as temporary:
        reviewed=Path(temporary)/'reviews.tsv';pipeline.table(reviewed,'decisions',reviews)
        summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,
            reviewed_decisions=reviewed,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(newExplicitTypoExclusions=len(additions),**{key:summary[key] for key in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','index','sources','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
