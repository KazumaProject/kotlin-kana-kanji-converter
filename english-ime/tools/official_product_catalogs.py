"""Join factual product labels from pinned public vendor catalog snapshots.

Only label facts are imported. Cached HTML/web excerpts, marketing prose, logos
and artwork are not redistributed. Display labels do not claim universal vendor
canonical spelling or current product availability. HTTP-403 pages use the
separately recorded public web extraction, not a fabricated HTML snapshot.
"""
import argparse,hashlib,json,re,tempfile
from collections import Counter,defaultdict
from html.parser import HTMLParser
from pathlib import Path
import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
from wiktionary_index import Index

PINS={'google.html':'76a04ca2c7acc4abba30c78cde9364af50a5a1c5616fff942ea731bb075f2ce8',
 'jetbrains.html':'f87df6507af89a8ec9cfa762802ee29eaaf4c1e9c5ffffa3aa89dca75777b86f',
 'web-excerpts.txt':'d888e386356ba1d0876859402dbb2a7a1f80dc435c0c49ed1ded2e79c4900b84'}
APPLE={'Mac','MacBook Neo','MacBook Air','MacBook Pro','iMac','Mac mini','Mac Studio','Studio Display','Studio Display XDR',
 'Apple Creator Studio','Final Cut Pro','Pixelmator Pro','Logic Pro','Apple Books','Apple News','Apple Remote Desktop','Safari','QuickTime','Apple Podcasts','macOS','Apple Arcade','Find My',
 'iPad Pro','iPad Air','iPad','iPad mini','Apple Pencil','HomeKit','iPadOS','iCloud','Apple Pay','Apple Health','iOS','MagSafe','Apple Card','Apple CarPlay',
 'watchOS','Apple Music','Apple Fitness+','Apple One','Apple Vision Pro','visionOS','AirPods','AirPods 5','AirPods Pro 3','AirPods Max 2',
 'Apple HomeView','Apple TV 4K','Apple TV app','Apple TV','HomePod (2nd generation)','HomePod mini 2','Home app','AirPlay','Apple News+','App Store','Apple Cash','iTunes'}
MICROSOFT={'Windows','Windows 365','Microsoft 365','Copilot for Microsoft 365','Microsoft Forms','Word','Excel','PowerPoint','Outlook','Access','Exchange','OneDrive for Business','Project','SharePoint','Microsoft Teams','Visio','Microsoft Designer','Copilot','Outlook.com','OneDrive','OneNote','Bing','Azure Maps','MSN','Linkedin','Microsoft Edge','Microsoft Surface','Surface Pro','Surface Laptop','XBOX','XBOX Series X','XBOX Series S','XBOX Game Pass','PC Game Pass','XBOX Cloud Gaming','Minecraft','Microsoft Dynamics 365','Power Platform','Microsoft Fabric','Microsoft Power BI','System Center','Microsoft SQL Server'}


class Labels(HTMLParser):
    def __init__(self,kind):super().__init__();self.kind=kind;self.active=None;self.content=[];self.records=[];self.stopped=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if self.kind=='google' and tag=='p' and 'product-filter__card-description' in attrs.get('class','').split():self.active=tag;self.content=[]
        if self.kind=='jetbrains' and tag=='h3' and not self.stopped:self.active=tag;self.content=[]
    def handle_data(self,data):
        if self.active:self.content.append(data)
    def handle_endtag(self,tag):
        if tag!=self.active:return
        label=' '.join(''.join(self.content).split())
        if self.kind=='jetbrains' and label=='Filters':self.stopped=True
        elif label:self.records.append({'label':label,'selector':'p.product-filter__card-description' if self.kind=='google' else 'h3 before Filters'})
        self.active=None


def load(directory):
    for name,sha in PINS.items():
        if pipeline.digest(directory/name)!=sha:raise ValueError('Changed product snapshot: '+name)
    records=[]
    for kind,url in [('google','https://about.google/products/'),('jetbrains','https://www.jetbrains.com/products/')]:
        parser=Labels(kind);parser.feed((directory/(kind+'.html')).read_text())
        if not parser.records:raise ValueError('Empty product selector')
        records += [dict(r,sourceFile=kind+'.html',url=url,snapshotKind='raw_html') for r in parser.records]
    sections=(directory/'web-excerpts.txt').read_text().split('Microsoft.com Site Map',1)
    if len(sections)!=2:raise ValueError('Missing independent vendor excerpt blocks')
    for text,allowed,url in [(sections[0],APPLE,'https://www.apple.com/sitemap/'),(sections[1],MICROSOFT,'https://www.microsoft.com/en-us/sitemap')]:
        found=set()
        for line in text.splitlines():
            number=re.match(r'L(\d+):',line)
            if not number:continue
            labels=re.findall(r'【\d+†([^†】]+)',line)
            heading=re.match(r'L\d+: ## (.+)$',line)
            if heading:labels.append(heading[1])
            for literal in labels:
                label=' '.join(literal.split())
                if label in allowed and label not in found:
                    records.append({'label':label,'sourceLabel':literal,'sourceLine':int(number[1]),'sourceFile':'web-excerpts.txt',
                        'url':url,'snapshotKind':'public_web_extraction_not_raw_html','selector':'audited product-name label/heading in complete public sitemap excerpt'});found.add(label)
    return records


def attach(model,rows,records):
    by_name=defaultdict(list);counts=Counter()
    for row in rows:by_name[row['surface'].casefold()].append(row)
    for record in records:
        label=record['label'];selected=list(by_name[label.casefold()])
        if ' ' in label:selected += [r for r in by_name[label.replace(' ','').casefold()] if r['id'].startswith('manual:')]
        if not selected:continue
        key='official-product-'+hashlib.sha256(json.dumps([record['url'],label]).encode()).hexdigest()[:24]
        proof={'source':'official_product_label','url':record['url'],'snapshotSha256':PINS[record['sourceFile']],
            'labelEvidence':record,'approved':True,'preferredVendorCaseClaimed':False,
            'scope':'factual product display label in vendor catalog; exact labels and existing manual case/space-free variants only; no artwork, marketing prose, current availability, corpus-intent or inflection claim'}
        members={'noun','noun_proper','name_product','domain_technology'}
        model.add(key,label,label,members,proof,approved=True)
        for row in selected:
            if row['surface']!=label and not row['id'].startswith('manual:'):continue
            model.add(key,label,row['surface'],members,dict(proof,legacySourceId=row['id'],originalSurface=row['surface']),approved=True);counts['existingInputProductSenses']+=1
    return counts


def extend(args):
    records=load(args.sources);model,rows,sources,notices,pending=extension.load_base(args.base,args.seed);counts=attach(model,rows,records)
    prior=args.base/'reviewed-overrides.tsv';reviews=pipeline.read_table(prior,'decisions') if prior.is_file() else []
    reviews,reopened=resolve_pending.revalidate_machine_reviews(model,reviews,pending)
    states=list(map(json.loads,(args.base/'status.jsonl').open()));selected=[r for r,s in zip(rows,states) if s['decision']=='pending' or r['id'] in reopened]
    index=Index(args.index)
    try:exact=list(index.lookup({r['surface'] for r in selected}))
    finally:index.close()
    additions=resolve_pending.cases(model,selected,{e['word'] for _,e in exact},resolve_pending.ineligible_exact_words(exact))
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    present={r['id'] for r in corrections};corrections += [r for r in additions if r['id'] not in present]
    sources['officialProductCatalogLabels']={'files':PINS,'policy':'factual labels only from pinned complete vendor indexes; raw HTML for Google/JetBrains, explicitly recorded public web excerpts for Apple/Microsoft HTTP-403 downloads; audited product selectors, no marketing prose/logos/source pages redistributed; display labels are not universal preferred spelling or current availability claims'}
    notices['OFFICIAL-PRODUCT-LABELS-ATTRIBUTION.txt']=('Sources: Apple https://www.apple.com/sitemap/ ; Microsoft https://www.microsoft.com/en-us/sitemap ; Google https://about.google/products/ ; JetBrains https://www.jetbrains.com/products/ .\nOnly factual product labels matching existing input rows and their source citations are used. No vendor page content, logos, artwork, marketing copy or executable code is redistributed; no trademark or artwork permission is implied. Display labels and existing manual input variants are recorded separately without inferring lexical inflections or current product availability.\n').encode()
    with tempfile.TemporaryDirectory(prefix='.official-label-review-',dir=args.out.parent) as temp:
        reviewed=Path(temp)/'reviews.tsv';pipeline.table(reviewed,'decisions',reviews)
        summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,reviewed_decisions=reviewed,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,reopenedMachineExclusions=len(reopened),**{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','sources','index','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
