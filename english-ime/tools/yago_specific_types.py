"""Verify additional specific named software/work/character types locally.

The graph alone can mis-type abstract concepts as products. Additional software
and device roots require a matching explicit description; generic classes and
broad CreativeWork/Product roots are not promoted into proper names.
"""
import argparse,json,re,zipfile
from collections import defaultdict
from pathlib import Path
import lexicon_pipeline as pipeline
import yago_names as yago
import yago_name_variants as variants

ROOTS={
 'yago:Computing_platform':{'name_product','domain_technology'},
 'yago:Proprietary_software':{'name_product','domain_technology'},
 'yago:Server_software':{'name_product','domain_technology'},
 'yago:Software_as_a_service':{'name_product','domain_technology'},
 'yago:Service_On_Internet':{'name_product','domain_technology'},
 'yago:Electronic_Product':{'name_product'},
 'yago:Character_arts':{'name_fictional'},
 'schema:Movie':{'name_work'},'schema:MusicAlbum':{'name_work'},
 'schema:MusicRecording':{'name_work'},'schema:TVEpisode':{'name_work'},
 'schema:TVSeason':{'name_work'},'schema:VideoGame':{'name_work'},
 'yago:Book_series':{'name_work'}}
SOFTWARE=set(ROOTS)-{'yago:Electronic_Product','yago:Character_arts'}-{k for k,v in ROOTS.items() if v=={'name_work'}}


def supported(root,descriptions):
    if root.startswith('schema:') or root=='yago:Book_series':return True
    for record in descriptions:
        if not yago.english(record['language']):continue
        text=record['label'].casefold()
        head=re.split(r'\b(?:by|for|from|with|which|that|in|on)\b',text,maxsplit=1)[0]
        if root=='yago:Character_arts' and re.search(r'\b(?:fictional character|character|superhero|supervillain)\b',head):return True
        if root in SOFTWARE and re.search(r'\b(?:software|application|app|platform|framework|engine|runtime|service|website|web browser|chatbot|tool|network|repository host|content delivery network)\b',head):return True
        if root=='yago:Electronic_Product' and re.search(r'\b(?:device|receiver|computer|console|chipset|speakers?|smartphones?|laptops?|tablets?|smartwatch|figurines|peripheral|accessory)\b',head):return True
    return False


def prepare(args):
    meta=json.loads((args.prepared/'manifest.json').read_text())
    if meta['snapshots']!=yago.PINS or pipeline.digest(args.prepared/'names.jsonl')!=meta['files']['names.jsonl']:raise ValueError('Changed extraction')
    if pipeline.digest(args.sources/'yago-4.6-taxonomy.zip')!=yago.PINS['yago-4.6-taxonomy.zip']:raise ValueError('Changed taxonomy')
    if args.out.exists():raise ValueError('Output exists')
    parents=defaultdict(list)
    with zipfile.ZipFile(args.sources/'yago-4.6-taxonomy.zip') as archive:
        for number,raw in enumerate(archive.open('yago-taxonomy.ttl'),1):
            if b'\trdfs:subClassOf\t' in raw:
                child,_,parent=yago.triple(raw);parents[child].append((parent,number))
    entities=[];cache={}
    for entity in map(json.loads,(args.prepared/'names.jsonl').open()):
        entity['paths']={};entity['classPaths']={}
        for record in entity['types']:
            kind=record['type']
            if kind not in cache:cache[kind]=yago.path_to_root(kind,parents,ROOTS)
            paths={root:path for root,path in cache[kind].items() if supported(root,entity['descriptions'])}
            if paths:entity['paths'][kind]=paths
        if entity['paths']:entities.append(entity)
    args.out.mkdir(parents=True);pipeline.jsonl(args.out/'names.jsonl',entities)
    meta.update(files={'names.jsonl':pipeline.digest(args.out/'names.jsonl')},roots={k:sorted(v) for k,v in ROOTS.items()},
        parentExtractionSha256=pipeline.digest(args.prepared/'manifest.json'),entities=len(entities),
        scope='additional specific instance types, excluding generic classes; software/service/device and character roots also require explicit supporting English description; no broad Product/CreativeWork promotion')
    (args.out/'manifest.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n');print(json.dumps({'preparedEntities':len(entities)}))


def extend(args):
    # Reuse identical inventory, exclusion, case and provenance handling while
    # requiring this extraction's independent root matrix on load and attach.
    meta=json.loads((args.prepared/'manifest.json').read_text())
    if meta['roots']!={k:sorted(v) for k,v in ROOTS.items()}:raise ValueError('Wrong specific roots')
    variants.extend(args,ROOTS,'yagoSpecificNamedTypes')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    for name in ['prepare','extend']:
        command=commands.add_parser(name)
        for arg in (['prepared','sources','out'] if name=='prepare' else ['base','seed','prepared','index','out']):command.add_argument('--'+arg,type=Path,required=True)
    args=parser.parse_args();prepare(args) if args.command=='prepare' else extend(args)
