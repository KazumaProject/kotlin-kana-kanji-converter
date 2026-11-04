"""Join attested names across the pinned YAGO facts and taxonomy snapshots.

Latin diacritics may establish an explicitly derived existing input alias, never
an attested preferred ASCII spelling. Class labels are not entity instances;
only separately described fictional characters use the limited class path.
"""
import argparse
from collections import Counter,defaultdict
import hashlib,json,re,tempfile,unicodedata,time,zipfile
from pathlib import Path
import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending,yago_names as yago
from wiktionary_index import Index

ROOTS=dict(yago.ROOTS,**{'yago:Video_Game_Character':{'name_fictional'},'yago:Fictional_Character':{'name_fictional'}})


def ascii_name(text):
    result=[]
    for character in text:
        if ord(character)<128:result.append(character);continue
        if not unicodedata.name(character,'').startswith('LATIN '):return None
        plain=''.join(c for c in unicodedata.normalize('NFD',character) if unicodedata.category(c)!='Mn')
        if not plain.isascii():return None
        result.append(plain)
    return ''.join(result)


def prepare(args,components=False):
    base=args.base;out=args.out
    if out.exists():raise ValueError('Output exists')
    rows=pipeline.inventory(base/'inventory.jsonl');states={r['id']:r for r in map(json.loads,(base/'status.jsonl').open())}
    selected=[r for r in rows if states[r['id']]['decision']!='include' or not components and r['id'].startswith('manual:')]
    wanted={r['surface'].casefold() for r in selected};compact={r['surface'].replace(' ','').casefold() for r in selected if r['id'].startswith('manual:')}
    parents=defaultdict(list);entities={};start=time.monotonic();sources=args.sources
    for filename,expected in yago.PINS.items():
        if pipeline.digest(sources/filename)!=expected:raise ValueError('Changed YAGO source: '+filename)
    for kind,filename,member in [('facts','yago-4.6-facts.zip','yago-facts.ttl'),('taxonomy','yago-4.6-taxonomy.zip','yago-taxonomy.ttl')]:
     with zipfile.ZipFile(sources/filename) as z:
      for n,raw in enumerate(z.open(member),1):
       if n%5000000==0:print(json.dumps({'phase':'scan','archive':kind,'line':n,'seconds':round(time.monotonic()-start,1)}),flush=True)
       if kind=='taxonomy' and b'\trdfs:subClassOf\t' in raw:
        s,_,obj=yago.triple(raw);parents[s].append((obj,n))
       fields=raw.split(b'\t',2)
       if len(fields)<3 or fields[1] not in {b'rdfs:label',b'schema:alternateName'}:continue
       s,pred,obj=yago.triple(raw);v=yago.literal(obj)
       if not v or not yago.name_language(v[1]):continue
       label=v[0];ascii_label=ascii_name(label);mode=None
       if label.casefold() in wanted:mode='exact_casefold'
       elif ' ' in label and label.replace(' ','').casefold() in compact:mode='manual_space_free'
       elif ascii_label and ascii_label!=label and ascii_label.casefold() in wanted:mode='existing_ascii_diacritic_input'
       matches=[]
       if components:
        tokens=label.split(' ')
        if len(tokens)>1:
         for position,token in enumerate(tokens):
          if re.fullmatch(r"[^\W\d_]+(?:[-'][^\W\d_]+)*",token) and any(c.isupper() for c in token):
           plain=ascii_name(token)
           if token.casefold() in wanted or plain and plain.casefold() in wanted:
            matches.append({'matchingMode':'whole_whitespace_delimited_named_component','component':token,'componentPosition':position,'asciiAlias':plain if plain!=token else None})
       elif mode:matches=[{'matchingMode':mode,'asciiAlias':ascii_label if mode=='existing_ascii_diacritic_input' else None}]
       if matches:
        entity=entities.setdefault(s,{'id':s,'matches':[],'labels':[],'types':[],'classParents':[],'wikidataIds':[],'englishWikipediaUrls':[],'descriptions':[]})
        entity['matches'] += [dict(match,label=label,predicate=pred,language=v[1],archive=filename,line=n,tripleSha256=hashlib.sha256(raw).hexdigest()) for match in matches]
       if n%10000000==0:print(json.dumps({'phase':'match','archive':kind,'line':n,'entities':len(entities),'seconds':round(time.monotonic()-start,1)}),flush=True)
     print(json.dumps({'phase':'matched','archive':kind,'lines':n,'entities':len(entities),'seconds':round(time.monotonic()-start,1)}),flush=True)
    for kind,filename,member in [('facts','yago-4.6-facts.zip','yago-facts.ttl'),('taxonomy','yago-4.6-taxonomy.zip','yago-taxonomy.ttl')]:
     with zipfile.ZipFile(sources/filename) as z:
      for n,raw in enumerate(z.open(member),1):
       s=raw.split(b'\t',1)[0].decode()
       if s not in entities:continue
       s,pred,obj=yago.triple(raw);e=entities[s];proof={'archive':filename,'line':n,'tripleSha256':hashlib.sha256(raw).hexdigest()}
       if pred=='rdf:type':e['types'].append(dict(proof,type=obj))
       elif pred=='rdfs:subClassOf':e['classParents'].append(dict(proof,type=obj))
       elif pred in {'rdfs:label','rdfs:comment'}:
        v=yago.literal(obj)
        if v and yago.name_language(v[1]):e['labels' if pred=='rdfs:label' else 'descriptions'].append(dict(proof,label=v[0],language=v[1]))
       elif pred=='owl:sameAs' and re.fullmatch(r'wd:Q[1-9][0-9]*',obj):e['wikidataIds'].append(obj)
       elif pred=='schema:url':
        v=re.fullmatch(r'"(https://en\.wikipedia\.org/wiki/[^"\\]+)"\^\^xsd:anyURI',obj)
        if v:e['englishWikipediaUrls'].append(v[1])
     print(json.dumps({'phase':'metadata','archive':kind,'lines':n,'seconds':round(time.monotonic()-start,1)}),flush=True)
    roots=dict(yago.ROOTS);roots.update({'yago:Video_Game_Character':{'name_fictional'},'yago:Fictional_Character':{'name_fictional'}})
    cache={}
    for e in entities.values():
     for r in e['types']+e['classParents']:
      if r['type'] not in cache:cache[r['type']]=yago.path_to_root(r['type'],parents,roots)
     e['paths']={r['type']:cache[r['type']] for r in e['types'] if cache[r['type']]}
     e['classPaths']={r['type']:cache[r['type']] for r in e['classParents'] if cache[r['type']]}
    out.mkdir();pipeline.jsonl(out/'names.jsonl',sorted(entities.values(),key=lambda x:x['id']))
    manifest={'schemaVersion':1,'snapshots':yago.PINS,'files':{'names.jsonl':pipeline.digest(out/'names.jsonl')},'inventorySha256':pipeline.digest(base/'inventory.jsonl'),'baseManifestSha256':pipeline.digest(base/'manifest.json'),'roots':{k:sorted(v) for k,v in roots.items()},'entities':len(entities),'componentMode':components,'scope':'selected existing rows; attested English or international names only, exact/manual-space-free or Latin-diacritic input alias; no resource-title reconstruction, no arbitrary substring or transliteration'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');print(json.dumps(manifest),flush=True)


def categories(entity,roots_matrix=ROOTS):
    roots=set().union(*(set(value) for value in entity['paths'].values())) & roots_matrix.keys()
    # YAGO also models individual fictional species/characters as classes.
    # A class edge alone would otherwise turn generic class labels into names.
    fictional=any(re.search(r'^(?:Pokémon species|fictional character\b|character (?:in|from)\b)',d['label'],re.I)
        for d in entity['descriptions'] if yago.english(d['language']))
    if fictional:
        roots |= set().union(*(set(v) for v in entity.get('classPaths',{}).values())) & {'yago:Video_Game_Character','yago:Fictional_Character'}
    result=set().union(*(roots_matrix[root] for root in roots))
    if any(value.startswith('name_') for value in result):result|={'noun','noun_proper'}
    return result


def attach(model,rows,entities,roots_matrix=ROOTS):
    extension.ensure_categories(model,set().union(*roots_matrix.values()))
    inputs=defaultdict(list)
    for row in rows:inputs[row['surface'].casefold()].append(row)
    counts=Counter()
    for entity in entities:
        if entity['id'].endswith('_generic_instance') or not entity['wikidataIds'] or not entity['englishWikipediaUrls']:continue
        members=categories(entity,roots_matrix)
        labels=sorted(entity['labels'],key=lambda v:(v['language']!='en',v['language'],v['label']))
        if not members or not labels:continue
        lemma=labels[0]['label'];key='yago-variant-'+hashlib.sha256(entity['id'].encode()).hexdigest()[:24]
        for match in entity['matches']:
            label=match['label'];proof={'source':'yago_name_variant','url':yago.URL,'snapshots':yago.PINS,'entityId':entity['id'],
                'wikidataIds':entity['wikidataIds'],'englishWikipediaUrls':entity['englishWikipediaUrls'],'nameEvidence':match,
                'types':entity['types'],'verifiedInstancePaths':entity['paths'],'classPaths':entity.get('classPaths',{}),
                'descriptionEvidence':entity['descriptions'],'canonicalLabelEvidence':labels[0],'approved':True,
                'scope':'attested full English/shared international name, or explicitly derived existing Latin-diacritic input alias; no reconstructed resource title, arbitrary substring, transliteration, lexical inflection or corpus-intent claim'}
            model.add(key,lemma,lemma,members,proof,approved=True)
            model.add(key,lemma,label,members,proof,approved=True)
            counts['attestedNameSenses']+=1
            if match['matchingMode']=='existing_ascii_diacritic_input':
                plain=ascii_name(label)
                if plain is None or plain!=match['asciiAlias'] or plain==label:raise ValueError('Changed diacritic derivation')
                for row in inputs[plain.casefold()]:
                    model.add(key,lemma,row['surface'],members,dict(proof,legacySourceId=row['id'],originalSurface=row['surface'],
                        relation='derived_existing_latin_diacritic_input_alias',preferredAsciiSpellingClaimed=False),approved=True)
                    counts['existingAsciiInputSenses']+=1
            elif match['matchingMode']=='manual_space_free':
                for row in inputs[label.replace(' ','').casefold()]:
                    if row['id'].startswith('manual:'):
                        model.add(key,lemma,row['surface'],members,dict(proof,legacySourceId=row['id'],relation='existing_manual_space_free_alias'),approved=True)
                        counts['existingManualAliasSenses']+=1
    return counts


def extend(args,roots_matrix=ROOTS,source_key='yagoNameVariants'):
    metadata=json.loads((args.prepared/'manifest.json').read_text())
    if metadata['snapshots']!=yago.PINS or metadata['roots']!={k:sorted(v) for k,v in roots_matrix.items()} or pipeline.digest(args.prepared/'names.jsonl')!=metadata['files']['names.jsonl']:raise ValueError('Changed name extraction')
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    if pipeline.digest(args.base/'inventory.jsonl')!=metadata['inventorySha256']:raise ValueError('Wrong inventory')
    entities=[json.loads(line) for line in (args.prepared/'names.jsonl').open()];counts=attach(model,rows,entities,roots_matrix)
    prior=args.base/'reviewed-overrides.tsv';reviews=pipeline.read_table(prior,'decisions') if prior.is_file() else []
    reviews,reopened=resolve_pending.revalidate_machine_reviews(model,reviews,pending)
    states=[json.loads(line) for line in (args.base/'status.jsonl').open()]
    selected=[row for row,state in zip(rows,states) if state['decision']=='pending' or row['id'] in reopened]
    index=Index(args.index)
    try:exact=list(index.lookup({r['surface'] for r in selected}))
    finally:index.close()
    additions=resolve_pending.cases(model,selected,{e['word'] for _,e in exact},resolve_pending.ineligible_exact_words(exact))
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    present={r['id'] for r in corrections};corrections += [r for r in additions if r['id'] not in present]
    sources[source_key]={'preparedManifestSha256':pipeline.digest(args.prepared/'manifest.json'),'snapshots':yago.PINS,
        'policy':'attested English/shared international labels from both facts/taxonomy with Wikidata and English-Wikipedia identity; separate instance-type proof or explicitly described fictional-character class proof; existing Latin-diacritic keyboard aliases only, not preferred ASCII spellings'}
    notices['YAGO-NAME-VARIANTS-NOTICE.txt']=('YAGO 4.6, Télécom Paris YAGO team and Wikidata contributors.\nhttps://yago-knowledge.org/downloads/yago-4-6\nCC BY 4.0, full license retained separately.\nChanges: extracted matching attested labels and type/description proofs from facts and taxonomy; explicitly derived existing ASCII input aliases by removing decomposable Latin diacritics. No arbitrary transliteration, resource-title reconstruction, artwork or inferred inflections.\n').encode()
    with tempfile.TemporaryDirectory(prefix='.name-variant-review-',dir=args.out.parent) as temp:
        reviewed=Path(temp)/'reviews.tsv';pipeline.table(reviewed,'decisions',reviews)
        summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,reviewed_decisions=reviewed,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,reopenedMachineExclusions=len(reopened),**{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    for name in ['prepare','extend']:
        command=commands.add_parser(name)
        for arg in (['base','sources','out'] if name=='prepare' else ['base','seed','prepared','index','out']):command.add_argument('--'+arg,type=Path,required=True)
    args=parser.parse_args();prepare(args) if args.command=='prepare' else extend(args)
