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
TECHNOLOGY_PINS={'google-cloud-products.html':'9e302c885832947d7fdc1daba5941a6ce6997c59a8df04afb4889888dc47c050',
 'apple-technologies.json':'17f68e7ff58bfadf3d60134502950199a7c62f9881f0b7c3cd22a0b2560d761c'}
FIREBASE_PRODUCT_PINS={'firebase-products.html':'629f43ccb7f67ea910fd6de96f0688244434c10e812721e81ec38fe6e52f073c',
 'firebase-products-run.html':'d27a5253bbe0f51809753e5f5867e7f123428aedd9471a7eeeae686fab7fcf57'}
MANUFACTURER_PINS={'dassault-products.html':'742fdb58141ac717d9647ec5259dbcdfd63214a1d4a06b8c3ee7342e2d1d13b6',
 'asus-phones.html':'7da37bc8c206a82c54219012d7bf7fc5a6b4933a6967ebe9d72d1f2f005f538c'}
APPLE={'Mac','MacBook Neo','MacBook Air','MacBook Pro','iMac','Mac mini','Mac Studio','Studio Display','Studio Display XDR',
 'Apple Creator Studio','Final Cut Pro','Pixelmator Pro','Logic Pro','Apple Books','Apple News','Apple Remote Desktop','Safari','QuickTime','Apple Podcasts','macOS','Apple Arcade','Find My',
 'iPad Pro','iPad Air','iPad','iPad mini','Apple Pencil','HomeKit','iPadOS','iCloud','Apple Pay','Apple Health','iOS','MagSafe','Apple Card','Apple CarPlay',
 'watchOS','Apple Music','Apple Fitness+','Apple One','AppleCare','Apple Vision Pro','visionOS','AirPods','AirPods 5','AirPods Pro 3','AirPods Max 2',
 'Apple HomeView','Apple TV 4K','Apple TV app','Apple TV','HomePod (2nd generation)','HomePod mini 2','Home app','AirPlay','Apple News+','App Store','Apple Cash','iTunes'}
MICROSOFT={'Windows','Windows 365','Microsoft 365','Copilot for Microsoft 365','Microsoft Forms','Word','Excel','PowerPoint','Outlook','Access','Exchange','OneDrive for Business','Project','SharePoint','Microsoft Teams','Visio','Microsoft Designer','Copilot','Outlook.com','OneDrive','OneNote','Bing','Azure Maps','MSN','Linkedin','Microsoft Edge','Microsoft Surface','Surface Pro','Surface Laptop','XBOX','XBOX Series X','XBOX Series S','XBOX Game Pass','PC Game Pass','XBOX Cloud Gaming','Minecraft','Microsoft Dynamics 365','Power Platform','Microsoft Fabric','Microsoft Power BI','System Center','Microsoft SQL Server'}


class Labels(HTMLParser):
    def __init__(self,kind):super().__init__();self.kind=kind;self.active=None;self.content=[];self.records=[];self.stopped=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if self.kind=='google' and tag=='p' and 'product-filter__card-description' in attrs.get('class','').split():self.active=tag;self.content=[]
        if self.kind=='jetbrains' and tag=='h3' and not self.stopped:self.active=tag;self.content=[]
        if self.kind=='google_cloud' and tag=='div' and 'owa4Ee' in attrs.get('class','').split():self.active=tag;self.content=[]
        if self.kind=='firebase' and tag=='div' and 'content__title' in attrs.get('class','').split():self.active=tag;self.content=[]
        if self.kind=='asus' and tag=='h2' and 'seriesName' in attrs.get('class','').split():self.active=tag;self.content=[]
    def handle_data(self,data):
        if self.active:self.content.append(data)
    def handle_endtag(self,tag):
        if tag!=self.active:return
        label=' '.join(''.join(self.content).split())
        if self.kind=='jetbrains' and label=='Filters':self.stopped=True
        elif label:self.records.append({'label':label,'selector':{'google':'p.product-filter__card-description','google_cloud':'div.owa4Ee','firebase':'div.content__title','jetbrains':'h3 before Filters','asus':'h2.seriesName'}[self.kind]})
        self.active=None


class BrandCards(HTMLParser):
    """Use a complete brand-card identity corroborated by its printed logo alt."""
    def __init__(self):super().__init__();self.depth=0;self.card=None;self.records=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='div':
            self.depth+=1
            if 'ds-brand-card' in attrs.get('class','').split():
                if self.card is not None:raise ValueError('Nested product brand cards')
                label=attrs.get('id','');path=attrs.get('data-href','')
                if (not label or any(c in label for c in '\t\r\n') or
                        not re.fullmatch(r'/products/[a-z0-9-]+|https://[a-z0-9.-]+(?:/[a-zA-Z0-9._/-]*)?',path)):
                    raise ValueError('Incomplete brand card identity')
                self.card=dict(depth=self.depth,label=label,productPath=path,confirmed=False)
        if tag=='img' and self.card and 'ds-list-of-brands-brand-logo' in attrs.get('class','').split():
            if attrs.get('alt')==self.card['label']+' Logo':self.card['confirmed']=True
    def handle_endtag(self,tag):
        if tag!='div':return
        if self.card and self.card['depth']==self.depth:
            if self.card['confirmed']:self.records.append(dict(label=self.card['label'],productPath=self.card['productPath'],
                logoAlt=self.card['label']+' Logo',selector='div.ds-brand-card[id] corroborated by img.ds-list-of-brands-brand-logo[alt]',
                catalogKind='vendor_product_brand_label'))
            self.card=None
        self.depth-=1


def manufacturer_records(dassault_html,asus_html):
    parser=BrandCards();parser.feed(dassault_html)
    records=[dict(r,sourceFile='dassault-products.html',url='https://www.3ds.com/products') for r in parser.records]
    if not records:raise ValueError('Missing corroborated manufacturer brand cards')
    parser=Labels('asus');parser.feed(asus_html)
    records += [dict(r,sourceFile='asus-phones.html',url='https://www.asus.com/mobile-handhelds/phones/all-series/',
        catalogKind='vendor_product_family_title') for r in parser.records]
    if not parser.records:raise ValueError('Missing complete manufacturer product labels')
    return [dict(r,snapshotSha256=MANUFACTURER_PINS[r['sourceFile']],snapshotKind='raw_html') for r in records]


def load_manufacturers(directory):
    for name,expected in MANUFACTURER_PINS.items():
        if pipeline.digest(directory/name)!=expected:raise ValueError('Changed manufacturer catalog: '+name)
    return manufacturer_records((directory/'dassault-products.html').read_text(),(directory/'asus-phones.html').read_text())


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


def technology_records(cloud_html,apple):
    parser=Labels('google_cloud');parser.feed(cloud_html)
    records=[dict(r,sourceFile='google-cloud-products.html',url='https://cloud.google.com/products',
        snapshotKind='raw_html',catalogKind='vendor_product_display_label') for r in parser.records]
    if (apple.get('kind')!='technologies' or apple.get('metadata',{}).get('title')!='Technologies' or
            apple.get('identifier',{}).get('url')!='doc://com.apple.welcome-experience-documentation/documentation/technologies'):
        raise ValueError('Unexpected Apple technologies index')
    for identifier,value in sorted(apple['references'].items()):
        if value.get('kind')!='symbol' or value.get('role')!='collection' or value.get('type')!='topic':continue
        path=value['url'];label=value['title']
        if (identifier!=value['identifier'] or not re.fullmatch(r'/documentation/[A-Za-z0-9_-]+',path) or
                not identifier.startswith('doc://com.apple.documentation/documentation/') or
                identifier.rsplit('/',1)[-1].casefold()!=path.rsplit('/',1)[-1].casefold() or
                not label or any(c in label for c in '\t\r\n')):
            raise ValueError('Inconsistent complete Apple technology identity')
        records.append(dict(label=label,sourceFile='apple-technologies.json',url='https://developer.apple.com'+path,
            selector='references: symbol / collection / topic',snapshotKind='official_json',
            catalogKind='documented_technology_collection',documentationIdentifier=identifier))
    return [dict(r,snapshotSha256=TECHNOLOGY_PINS[r['sourceFile']]) for r in records]


def load_technologies(directory):
    for name,expected in TECHNOLOGY_PINS.items():
        if pipeline.digest(directory/name)!=expected:raise ValueError('Changed official technology index: '+name)
    return technology_records((directory/'google-cloud-products.html').read_text(),json.loads((directory/'apple-technologies.json').read_text()))


def load_firebase_products(directory):
    records=[]
    for name,expected in FIREBASE_PRODUCT_PINS.items():
        if pipeline.digest(directory/name)!=expected:raise ValueError('Changed Firebase product catalog: '+name)
        parser=Labels('firebase');parser.feed((directory/name).read_text())
        if not parser.records:raise ValueError('Missing Firebase product card titles')
        url='https://firebase.google.com/products-build' if name=='firebase-products.html' else 'https://firebase.google.com/products-run'
        records += [dict(r,sourceFile=name,snapshotSha256=expected,url=url,snapshotKind='raw_html',catalogKind='vendor_product_card_title') for r in parser.records]
    return records


def attach(model,rows,records):
    by_name=defaultdict(list);counts=Counter()
    for row in rows:by_name[row['surface'].casefold()].append(row)
    for record in records:
        label=record['label'];selected=list(by_name[label.casefold()])
        if ' ' in label:selected += [r for r in by_name[label.replace(' ','').casefold()] if r['id'].startswith('manual:')]
        if not selected:continue
        key='official-product-'+hashlib.sha256(json.dumps([record['url'],label]).encode()).hexdigest()[:24]
        proof={'source':'official_product_label','url':record['url'],'snapshotSha256':record.get('snapshotSha256') or PINS[record['sourceFile']],
            'labelEvidence':record,'approved':True,'preferredVendorCaseClaimed':False,
            'scope':'factual product display label in vendor catalog; exact labels and existing manual case/space-free variants only; no artwork, marketing prose, current availability, corpus-intent or inflection claim'}
        members={'noun','noun_proper','name_product','domain_technology'}
        if record.get('catalogKind')=='vendor_product_brand_label':members.add('name_brand')
        extension.ensure_categories(model,members)
        model.add(key,label,label,members,proof,approved=True)
        for row in selected:
            if row['surface']!=label and not row['id'].startswith('manual:'):continue
            model.add(key,label,row['surface'],members,dict(proof,legacySourceId=row['id'],originalSurface=row['surface']),approved=True);counts['existingInputProductSenses']+=1
    return counts


def extend(args):
    manufacturers=getattr(args,'manufacturers',None)
    records=load(args.sources)
    if args.technologies:records+=load_technologies(args.technologies)
    if args.firebase_products:records+=load_firebase_products(args.firebase_products)
    if manufacturers:records+=load_manufacturers(manufacturers)
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed);counts=attach(model,rows,records)
    if args.technologies:
        sources['officialTechnologyDisplayLabels']={'files':TECHNOLOGY_PINS,
            'policy':'complete Google Cloud product display labels and Apple documented technology collection titles only; source fields and identities retained, no URL-slug name inference, page prose, artwork, implementation, current availability or preferred-case claim'}
        notices['OFFICIAL-TECHNOLOGY-LABELS-ATTRIBUTION.txt']=('Factual display labels: Google Cloud, https://cloud.google.com/products ; Apple Developer Technologies, https://developer.apple.com/documentation/technologies ; JSON index https://developer.apple.com/tutorials/data/documentation/technologies.json .\n'
            'Apple source copyright: Copyright 2026 Apple Inc. All rights reserved. Terms: https://www.apple.com/legal/internet-services/terms/site.html . Google terms: https://cloud.google.com/terms .\n'
            'Only matching factual product/framework collection labels, complete documentation identifiers, source selectors and citations are extracted. No documentation prose, abstracts, marketing descriptions, code, artwork or logos redistributed. No trademark/artwork permission, installed capability, current availability, preferred spelling or inflection is implied. Existing original manual case/space variants remain separately identified.\n').encode()
    if args.firebase_products:
        sources['firebaseProductDisplayLabels']={'files':FIREBASE_PRODUCT_PINS,'policy':'complete printed product card titles only; original manual case/space-free variants retained, no label invented by prefixing the vendor name or deriving a product name from a URL slug'}
        notices['FIREBASE-PRODUCT-LABELS-ATTRIBUTION.txt']=('Google/Firebase contributors. https://firebase.google.com/products-build ; https://firebase.google.com/products-run\n'
            'Extracted factual complete printed product card titles and source citations only, retaining source hashes and original manual variants. No marketing prose, artwork, code or logos redistributed; no inferred vendor-prefixed label, current availability, preferred case or inflection. No license to redistribute marketing page content or artwork is asserted.\n').encode()
    if manufacturers:
        sources['manufacturerProductLabels']={'files':MANUFACTURER_PINS,
            'policy':'complete Dassault product-brand card identities corroborated by explicit logo alternative text; complete ASUS phone-series headings; no product inferred from URL slugs, model suffix removal or marketing descriptions'}
        notices['MANUFACTURER-PRODUCT-LABELS-ATTRIBUTION.txt']=('Factual product/brand labels: Dassault Systemes, https://www.3ds.com/products ; ASUS, https://www.asus.com/mobile-handhelds/phones/all-series/ .\n'
            'Only complete card labels corroborated by explicit logo alternative text and complete product-family headings are selected, retaining source hashes and selector identities. No page prose, descriptions, artwork, logos or code are redistributed; no content license, trademark permission, current availability, preferred case or inflection is asserted.\n').encode()
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
    parser.add_argument('--technologies',type=Path,help='Optional pinned complete official product/framework indexes')
    parser.add_argument('--firebase-products',type=Path,help='Optional pinned Firebase Build/Run product card indexes')
    parser.add_argument('--manufacturers',type=Path,help='Optional pinned Dassault/ASUS complete manufacturer catalog labels')
    extend(parser.parse_args())
