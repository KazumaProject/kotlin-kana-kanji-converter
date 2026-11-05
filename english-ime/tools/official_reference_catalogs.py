"""Read complete labels from pinned public product, program and SDK indexes.

This offline importer keeps literal identifiers and source selectors, never
website prose, code, logos, inferred English inflections or executable claims.
Commands retain exact case; only existing manual name presentations may differ
in case or spaces. A bound prefix with the same spelling cannot erase a name.
"""
import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
from urllib.parse import urljoin

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending

PINS={
    'azure-products.html':'e968143a2c3d94edb26711f4d5ef0befeb196ea38b078064fcbf9a5225144626',
    'android-tools.html':'a1a4a53c0f85bb2ff72168b4cd91fbd6265aa3bbc6def6f56d51bd3745caf5a3',
    'jmi-programs.html':'23c84c0f76cd9455281be5fa1ede657b290a2d5c61bff320cd0b8824324dcdf6',
}
URLS={'azure-products.html':'https://azure.microsoft.com/en-us/products/',
      'android-tools.html':'https://developer.android.com/tools',
      'jmi-programs.html':'https://jmi.net/programs'}


class Catalog(HTMLParser):
    def __init__(self,kind):
        super().__init__();self.kind=kind;self.stack=[];self.active=None;self.records=[];self.link=None

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        # Only the article body supplies SDK command names. Global navigation
        # labels are separately typed as technology names, never commands.
        if tag=='div':self.stack.append(set(attrs.get('class','').split()))
        if tag=='a':self.link=attrs
        select=(self.kind=='azure' and tag=='h3' and 'h5' in attrs.get('class','').split() and
                    any('card-body' in frame for frame in self.stack) and any('card' in frame for frame in self.stack) or
                self.kind=='jmi' and tag=='h3' and 'title' in attrs.get('class','').split() and self.link and
                    'box-lnk' in self.link.get('class','').split() and self.link.get('href','').startswith('/programs/'))
        if select:self.active=(tag,attrs,[])
        if self.kind=='android' and tag=='a':self.active=(tag,dict(attrs,inArticle=any('devsite-article-body' in frame for frame in self.stack)),[])

    def handle_data(self,data):
        if self.active:self.active[2].append(data)

    def handle_endtag(self,tag):
        if self.active and tag==self.active[0]:
            _,attrs,parts=self.active;self.active=None;label=' '.join(''.join(parts).split())
            if label:
                if self.kind=='azure':self.records.append(dict(label=label,kind='technology_name',selector='div.card / div.card-body / h3.h5 complete Azure product-card heading'))
                elif self.kind=='jmi':self.records.append(dict(label=label,kind='program_name',selector='a.box-lnk[href=/programs/...] / h3.title complete JMI program-card heading',programLink=self.link['href']))
                else:
                    href=attrs.get('href','')
                    if attrs['inArticle'] and href in {'/studio/command-line/'+label,'/tools/'+label} and label.isascii() and label.islower() and label.replace('-','').isalnum():
                        self.records.append(dict(label=label,kind='command_name',selector='article body complete SDK tool link',url=urljoin(URLS['android-tools.html'],href)))
                    if (href,label) in {('/kotlin/multiplatform','Kotlin Multiplatform'),('/google/play/integrity','Play Integrity')}:
                        self.records.append(dict(label=label,kind='technology_name',selector='complete Android documentation navigation label and matching namespace',url=urljoin(URLS['android-tools.html'],href)))
        if tag=='div' and self.stack:self.stack.pop()
        if tag=='a':self.link=None


def records(texts):
    result=[]
    for file,kind in [('azure-products.html','azure'),('android-tools.html','android'),('jmi-programs.html','jmi')]:
        parser=Catalog(kind);parser.feed(texts[file])
        if not parser.records:raise ValueError('Missing complete reference catalog: '+file)
        for item in parser.records:
            result.append(dict(item,sourceFile=file,snapshotSha256=PINS[file],url=item.get('url',URLS[file])))
    return result


def attach(model,rows,facts,corrections):
    counts=Counter()
    for fact in facts:
        label=fact['label'];kind=fact['kind'];is_name=kind!='command_name'
        if kind not in {'command_name','technology_name','program_name'}:raise ValueError('Unsupported public reference identity')
        members=({'identifier_command_prefix','domain_technology'} if not is_name else
                 {'noun','noun_proper','name_product','domain_technology'} if kind=='technology_name' else
                 {'noun','noun_proper','domain_entertainment'})
        selected=[r for r in rows if r['surface']==label or is_name and r['surface'].casefold()==label.casefold() or
                  is_name and r['id'].startswith('manual:') and r['surface'].replace(' ','').casefold()==label.replace(' ','').casefold()]
        if not selected:continue
        key='official-reference-'+hashlib.sha256(json.dumps([fact['url'],label,kind]).encode()).hexdigest()[:24]
        proof=dict(source='official_reference_label',approved=True,url=fact['url'],labelEvidence=fact,
            preferredCaseClaimed=False,completionRequired=None,
            scope='whole printed public catalog name or exact case-sensitive SDK command name; original manual name case/space presentations retained separately; no website prose/code/artwork, guessed acronym expansion, ordinary English inflections, command execution, installed capability, endorsement or current availability claim')
        extension.ensure_categories(model,members);model.add(key,label,label,members,proof,approved=True)
        for row in selected:
            if row['surface']!=label and row['id'].startswith('manual:'):
                model.add(key,label,row['surface'],members,dict(proof,relation='existing_manual_case_or_space_presentation',legacySourceId=row['id'],externallyAttestedAliasSpellingClaimed=False),approved=True)
            elif row['surface']!=label:
                if row['surface']!=row['surface'].lower() or pipeline.keyboard_reading(label)!=row['reading']:
                    raise ValueError('A reference catalog cannot invent an input spelling')
                existing={r['target']:dict(r) for r in corrections if r['id']==row['id']}
                existing.setdefault(label,dict(id=row['id'],source=row['surface'],target=label,evidence=fact['url']))
                if model.approved.get(row['surface']):
                    urls=[e['url'] for k in model.approved[row['surface']] for e in model.evidence[k,row['surface']] if e.get('approved',True) and not e.get('requiresFullNamedContext')]
                    if urls:existing.setdefault(row['surface'],dict(id=row['id'],source=row['surface'],target=row['surface'],evidence=min(urls)))
                corrections[:]=[r for r in corrections if r['id']!=row['id']]
                corrections += [dict(r,relation='case_correction' if len(existing)==1 else 'case_candidates') for _,r in sorted(existing.items())]
            counts[kind]+=1
    return counts


def extend(args):
    for file,pin in PINS.items():
        if pipeline.digest(args.sources/file)!=pin:raise ValueError('Changed public reference snapshot: '+file)
    facts=records({file:(args.sources/file).read_text() for file in PINS})
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    counts=attach(model,rows,facts,corrections)
    prior=args.base/'reviewed-overrides.tsv';reviews=pipeline.read_table(prior,'decisions') if prior.is_file() else []
    reviews,reopened=resolve_pending.revalidate_machine_reviews(model,reviews,pending,corrections)
    sources['officialReferenceCatalogs']=dict(files=PINS,urls=URLS,policy='whole printed Azure product-card, JMI music-program-card and SDK command/documentation labels only; commands case-sensitive, no program-to-product or prefix-to-nonword inference')
    notices['OFFICIAL-REFERENCE-CATALOGS-NOTICE.txt']=('Factual names: Microsoft Azure products https://azure.microsoft.com/en-us/products/ ; Android Developers SDK tools https://developer.android.com/tools ; JM International programs https://jmi.net/programs .\nOnly complete labels, exact source selectors, source hashes and citations are retained. No prose, logos, source code, descriptions, or implementation is redistributed. No general website-content/trademark license, affiliation, endorsement, executable support or current availability is claimed. Original manual case/space presentations are not externally attested alias spellings.\n').encode()
    with tempfile.TemporaryDirectory(prefix='.official-reference-review-',dir=args.out.parent) as temp:
        reviewed=Path(temp)/'reviews.tsv';pipeline.table(reviewed,'decisions',reviews)
        summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,reviewed_decisions=reviewed,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,reopenedMachineExclusions=len(reopened),**{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','sources','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
