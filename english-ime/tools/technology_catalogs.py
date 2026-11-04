"""Join pinned public software identifiers and AWS service labels, entirely offline.

Devicon identifiers are catalog slugs, not preferred English brand spellings.
Botocore is read as a ZIP of static metadata; it is never imported or executed.
No AWS clients, credentials, installations, or service requests are involved.
"""
import argparse,gzip,hashlib,json,tempfile,zipfile
from collections import Counter,defaultdict
from pathlib import Path
import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
from wiktionary_index import Index

DEVICON_REVISION='32fe1d3b3f36ad11f90ab94f7db59738139c2bf6'
DEVICON_PINS={'devicon.json':'c23c643f14bf5031c994c0d225d51f4562c76a0a957d9d650e06449779ee1d33','LICENSE':'121194741d4a915b9f5890fdd6dd95121f9b1f816517c792358d72d7c838d664'}
WHEEL='botocore-1.43.123-py3-none-any.whl'
WHEEL_SHA='e30580f9c1282c321529238ff8ff75066096a2adbd0a293c8ae592c21d1733a3'
DEVICON_URL='https://github.com/devicons/devicon/blob/'+DEVICON_REVISION+'/devicon.json'
BOTOCORE_URL='https://pypi.org/project/botocore/1.43.123/'
HOMEBREW_PINS={
 'formula.json':'5a9c3d3d942627a3bddcebcff43a383089080322aff34b0b0b1663d0db5664a9',
 'cask.json':'22be06451040c225cce6c5bebfcf058c683c196471e32e54abbcfd46e37d72c4',
 'CORE-LICENSE.txt':'f80329e58613ad669c0e73cb132d8060b9b2c55e339c73848068e4d1567f4627',
 'CASK-LICENSE.txt':'abd8be86c5738400f30c426bc88d90495b2dcfca9fe20b8d9b925599a55528b0'}


def homebrew_records(formulas,casks):
    records=[]
    for filename,entries in [('formula.json',formulas),('cask.json',casks)]:
        for entry in entries:
            formula=filename=='formula.json'
            identity=entry['full_name' if formula else 'full_token']
            labels=([entry['name']]+entry.get('aliases',[])+entry.get('oldnames',[])) if formula else [entry['token']]+entry.get('old_tokens',[])
            fields=[('catalog_identifier',labels),('executable',entry.get('executables') or [])]
            if not formula:fields.append(('display_name',entry.get('name',[])))
            for kind,values in fields:
                for label in values:
                    if not isinstance(label,str) or not label or any(c in label for c in '\t\r\n'):
                        raise ValueError('Invalid literal Homebrew metadata label')
                    records.append(dict(sourceFile=filename,identity=identity,kind=kind,label=label,
                        sourceRevision=entry.get('tap_git_head'),sourcePath=entry.get('ruby_source_path'),
                        homepage=entry.get('homepage'),disabled=entry.get('disabled'),deprecated=entry.get('deprecated')))
    return records


def load_homebrew(directory):
    for name,expected in HOMEBREW_PINS.items():
        if pipeline.digest(directory/name)!=expected:raise ValueError('Changed Homebrew source or license: '+name)
    formulas=json.loads((directory/'formula.json').read_text());casks=json.loads((directory/'cask.json').read_text())
    if len(formulas)!=8703 or len(casks)!=7807:raise ValueError('Incomplete Homebrew catalog')
    return homebrew_records(formulas,casks)


def attach_homebrew(model,rows,records):
    extension.ensure_categories(model,{'identifier_software_catalog','identifier_command_line'})
    by_fold=defaultdict(list);counts=Counter()
    for row in rows:by_fold[row['surface'].casefold()].append(row)
    for record in records:
        label=record['label'];selected=list(by_fold[label.casefold()])
        if record['kind']=='display_name' and ' ' in label:
            selected += [row for row in by_fold[label.replace(' ','').casefold()] if row['id'].startswith('manual:')]
        if not selected:continue
        members=({'noun','noun_proper','name_product','domain_technology'} if record['kind']=='display_name' else
            {'identifier_command_line' if record['kind']=='executable' else 'identifier_software_catalog','domain_technology'})
        key='homebrew-fact-'+hashlib.sha256(json.dumps([record['identity'],record['kind'],label]).encode()).hexdigest()[:24]
        proof=dict(source='public_technology_catalog',url='https://formulae.brew.sh/api/'+record['sourceFile'],
            sourceSha256=HOMEBREW_PINS[record['sourceFile']],metadataFact=record,approved=True,
            preferredVendorCaseClaimed=False,softwareExecuted=False,
            scope='literal catalog slug/alias, explicitly enumerated executable, or application display name; kinds remain separate; existing manual case/space-free name variants only; no inferred executable from a package slug, English POS for identifiers, corpus intent, installation, current availability, software license or artwork claim')
        model.add(key,label,label,members,proof,approved=True)
        for row in selected:
            if row['surface']!=label and not row['id'].startswith('manual:'):continue
            model.add(key,label,row['surface'],members,dict(proof,legacySourceId=row['id'],originalSurface=row['surface']),approved=True)
            counts['homebrew_'+record['kind']+'_input_senses']+=1
    return counts


def load(devicon,botocore):
    for name,pin in DEVICON_PINS.items():
        if pipeline.digest(devicon/name)!=pin:raise ValueError('Changed Devicon source/notice')
    entries=json.loads((devicon/'devicon.json').read_text())
    if len(entries)!=657 or len({r['name'] for r in entries})!=len(entries):raise ValueError('Incomplete Devicon catalog')
    if pipeline.digest(botocore/WHEEL)!=WHEEL_SHA:raise ValueError('Changed botocore package')
    services=[];notices={}
    with zipfile.ZipFile(botocore/WHEEL) as archive:
        for name in archive.namelist():
            if name.endswith('/service-2.json.gz'):
                raw=archive.read(name);data=json.loads(gzip.decompress(raw))
                services.append({'archiveMember':name,'memberSha256':hashlib.sha256(raw).hexdigest(),'metadata':{k:v for k,v in data['metadata'].items() if k in {'serviceId','serviceFullName','serviceAbbreviation'}}})
        for name in ['LICENSE.txt','NOTICE']:notices['BOTOCORE-'+name]=archive.read('botocore-1.43.123.dist-info/'+name)
    if len(services)!=468:raise ValueError('Incomplete service model metadata')
    return entries,services,notices


def attach(model,rows,entries,services):
    extension.ensure_categories(model,{'identifier_software_catalog'})
    by_fold=defaultdict(list);counts=Counter()
    for row in rows:by_fold[row['surface'].casefold()].append(row)
    for record in entries:
        key='devicon-catalog-'+record['name']
        for label in [record['name']]+record.get('altnames',[]):
            matches=by_fold[label.casefold()]
            if not matches:continue
            proof={'source':'public_technology_catalog','url':DEVICON_URL,'revision':DEVICON_REVISION,'catalogName':record['name'],
                'literalCatalogIdentifier':label,'identifierKind':'name' if label==record['name'] else 'explicit_altname','approved':True,
                'scope':'published Devicon catalog identifier, no artwork, preferred vendor casing, lexical POS, inflection or current installation claim'}
            model.add(key,record['name'],record['name'],{'identifier_software_catalog','domain_technology'},proof,approved=True)
            model.add(key,record['name'],label,{'identifier_software_catalog','domain_technology'},proof,approved=True)
            for row in matches:
                if row['surface']!=label and not row['id'].startswith('manual:'):continue
                model.add(key,record['name'],row['surface'],{'identifier_software_catalog','domain_technology'},
                    dict(proof,legacySourceId=row['id'],relation='existing_manual_case_variant' if row['surface']!=label else 'exact_catalog_identifier'),approved=True)
                counts['existingCatalogInputSenses']+=1
    for record in services:
        metadata=record['metadata'];lemma=metadata['serviceFullName'];key='aws-service-'+hashlib.sha256(metadata['serviceId'].encode()).hexdigest()[:24]
        # API-version metadata can occasionally rename a service. Keep each
        # full-name identity independent rather than changing an existing lemma.
        key+='-'+hashlib.sha256(lemma.encode()).hexdigest()[:12]
        for field in ['serviceFullName','serviceAbbreviation']:
            label=metadata.get(field)
            if not label:continue
            selected=list(by_fold[label.casefold()])
            if ' ' in label:selected += [r for r in by_fold[label.replace(' ','').casefold()] if r['id'].startswith('manual:')]
            if not selected:continue
            proof={'source':'public_technology_catalog','url':BOTOCORE_URL,'packageSha256':WHEEL_SHA,'archiveMember':record['archiveMember'],
                'memberSha256':record['memberSha256'],'serviceId':metadata['serviceId'],'labelField':field,'attestedLabel':label,'approved':True,
                'scope':'published AWS static service name/abbreviation; exact labels and existing manual case/space-free variants only, no service requests, account/credential access, current availability or corpus-intent claim'}
            members={'noun','noun_proper','name_product','domain_technology'}
            model.add(key,lemma,lemma,members,proof,approved=True);model.add(key,lemma,label,members,proof,approved=True)
            for row in selected:
                if row['surface']!=label and not row['id'].startswith('manual:'):continue
                model.add(key,lemma,row['surface'],members,dict(proof,legacySourceId=row['id'],originalSurface=row['surface'],preferredCaseClaimed=False),approved=True)
                counts['existingServiceInputSenses']+=1
    return counts


def extend(args):
    entries,services,new_notices=load(args.devicon,args.botocore)
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed);counts=attach(model,rows,entries,services)
    if getattr(args,'homebrew',None):
        counts.update(attach_homebrew(model,rows,load_homebrew(args.homebrew)))
        sources['homebrewCatalogFacts']={'files':HOMEBREW_PINS,'formulaRows':8703,'caskRows':7807,
            'policy':'read pinned public JSON only; slugs/explicit aliases, explicit executable lists and display names are separate facts; do not execute formulas, artifacts, installation hooks or scripts; no preferred vendor spelling, installation, current availability, application licensing or corpus-sense inference'}
        for name in ['CORE-LICENSE.txt','CASK-LICENSE.txt']:notices['HOMEBREW-'+name]=(args.homebrew/name).read_bytes()
        notices['HOMEBREW-CATALOG-NOTICE.txt']=('Homebrew contributors, homebrew-core and homebrew-cask, BSD-2-Clause; complete notices retained separately.\nhttps://formulae.brew.sh/docs/api/\nhttps://formulae.brew.sh/api/formula.json\nhttps://formulae.brew.sh/api/cask.json\nChanges: extract selected factual package identifiers, published executable names and display names, preserving source hashes and source references. No descriptions, logos, installation recipes or software are redistributed or executed. Catalog metadata does not grant application software licenses or imply availability, preferred vendor spelling, installed commands or original corpus intent.\n').encode()
    prior=args.base/'reviewed-overrides.tsv';reviews=pipeline.read_table(prior,'decisions') if prior.is_file() else []
    reviews,reopened=resolve_pending.revalidate_machine_reviews(model,reviews,pending)
    states=list(map(json.loads,(args.base/'status.jsonl').open()));selected=[r for r,s in zip(rows,states) if s['decision']=='pending' or r['id'] in reopened]
    index=Index(args.index)
    try:exact=list(index.lookup({r['surface'] for r in selected}))
    finally:index.close()
    additions=resolve_pending.cases(model,selected,{e['word'] for _,e in exact},resolve_pending.ineligible_exact_words(exact))
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    present={r['id'] for r in corrections};corrections += [r for r in additions if r['id'] not in present]
    sources['publicTechnologyCatalogs']={'deviconRevision':DEVICON_REVISION,'deviconFiles':DEVICON_PINS,'botocorePackage':WHEEL,'botocoreSha256':WHEEL_SHA,
        'policy':'Devicon names/explicit altnames are identifiers without English POS or preferred vendor casing; AWS serviceFullName/serviceAbbreviation are documented service names; existing manual case/space-free variants separately recorded; no artwork, executable software, AWS clients or API calls'}
    notices.update(new_notices);notices['DEVICON-MIT.txt']=(args.devicon/'LICENSE').read_bytes()
    notices['PUBLIC-TECHNOLOGY-CATALOGS-NOTICE.txt']=('Devicon contributors, '+DEVICON_REVISION+', MIT; '+DEVICON_URL+'\nAmazon Web Services botocore 1.43.123, Apache-2.0; '+BOTOCORE_URL+'\nFull notices retained separately. Changes: selected public catalog identifiers and AWS service names from static metadata, recording source hashes and existing manual variants. No icons, executable code, documentation prose or inferred inflections imported.\n').encode()
    with tempfile.TemporaryDirectory(prefix='.tech-catalog-review-',dir=args.out.parent) as temp:
        reviewed=Path(temp)/'reviews.tsv';pipeline.table(reviewed,'decisions',reviews)
        summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,reviewed_decisions=reviewed,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,reopenedMachineExclusions=len(reopened),**{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','devicon','botocore','index','out']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--homebrew',type=Path)
    extend(parser.parse_args())
