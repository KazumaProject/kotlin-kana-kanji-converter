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

LEGACY_ROOTS={
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
DESCRIPTION_ROOTS={
 'yago:Digital_audio_workstation':({'name_product','domain_technology'},r'\bdigital audio workstations?\b'),
 'yago:Computer_Network_Protocol':({'noun','noun_proper','domain_technology'},r'\b(?:computer network protocol|protocol suite)\b'),
 'yago:Python_Package':({'noun','noun_proper','domain_technology'},r'\bpython (?:library|package|compiler)\b'),
 'yago:Music_festival':({'noun','noun_proper','domain_entertainment'},r'\bmusic festival\b'),
 'yago:Convention_meeting':({'noun','noun_proper'},r'\b(?:convention|conference)\b'),
 'yago:Trade_show':({'noun','noun_proper'},r'\b(?:trade fair|trade show)\b'),
 'yago:Sports_league':({'noun','noun_proper','domain_sports'},r'\b(?:sports league|ice hockey league|basketball competition)\b'),
 'yago:Motorcycle_Racing_Series':({'noun','noun_proper','domain_sports'},r'\bmotorcycling world championship\b'),
 'yago:Typeface_Family':({'noun','noun_proper'},r'\btypeface family\b'),
 'yago:Film':({'name_work'},r'^\d{4}\b.*\bfilm\b')}
PREVIOUS_ROOTS=dict(LEGACY_ROOTS,**{root:values for root,(values,_) in DESCRIPTION_ROOTS.items()})
# Some genre classes have no path to YAGO's Film root. Require both the
# specific recorded type and a dated English film description, never genre
# membership alone. The same description guard applies to the other kinds.
for kind in ['Comedy_film','Film_Based_On_A_Novel','Film_Based_On_Literature','Parody_film','Romantic_comedy']:
    DESCRIPTION_ROOTS['yago:'+kind]=({'name_work'},r'^\d{4}\b.*\bfilm\b')
for kind in ['Tabletop_role-playing_game','Board_game']:
    DESCRIPTION_ROOTS['yago:'+kind]=({'name_work','domain_entertainment'},r'\b(?:role-playing game|board game)\b')
for kind in ['Ship_of_the_line','Schooner','Dugout_canoe','Preserved_Watercraft']:
    DESCRIPTION_ROOTS['yago:'+kind]=({'noun','noun_proper'},r'\b(?:ship|schooner|canoe)\b')
for kind in ['Employment_website','News_Aggregation_Website','Online_encyclopedia','Video_Streaming_Service']:
    DESCRIPTION_ROOTS['yago:'+kind]=({'name_product','domain_technology'},r'\b(?:website|aggregator|wiki|streaming service)\b')
DESCRIPTION_ROOTS.update({
 'yago:Film_festival':({'noun','noun_proper','domain_entertainment'},r'\bfilm festival\b'),
 'yago:Automobile_Racing_Series':({'noun','noun_proper','domain_sports'},r'\b(?:racing championship|racing series)\b'),
 'yago:Association_Football_League':({'noun','noun_proper','domain_sports'},r'\bfootball league\b'),
 'yago:Fair':({'noun','noun_proper'},r'^fair in\b'),
 'yago:Fictional_Humanoid':({'name_fictional'},r'^fictional (?:extraterrestrial )?species\b'),
 'yago:Fictional_Humanoid_Extraterrestrial':({'name_fictional'},r'^fictional (?:extraterrestrial )?species\b'),
 'yago:Fictional_Bird':({'name_fictional'},r'^fictional bird species\b'),
 'yago:Pokémon_Region':({'name_fictional'},r'^Pokémon region$'),
 'yago:Pokémon_Evolutionary_Line':({'name_fictional'},r'^evolution of a Pokémon species$'),
 'yago:Pokémon_Item':({'name_fictional'},r'^fictional device from the Pokémon universe\b'),
 'yago:Fictional_Metal':({'name_fictional'},r'^fictional metal$')})
ROOTS=dict(LEGACY_ROOTS,**{root:values for root,(values,_) in DESCRIPTION_ROOTS.items()})
SOFTWARE=set(LEGACY_ROOTS)-{'yago:Electronic_Product','yago:Character_arts'}-{k for k,v in LEGACY_ROOTS.items() if v=={'name_work'}}


def supported(root,descriptions):
    if root.startswith('schema:') or root=='yago:Book_series':return True
    for record in descriptions:
        if not yago.english(record['language']):continue
        text=record['label'].casefold()
        head=re.split(r'\b(?:by|for|from|with|which|that|in|on)\b',text,maxsplit=1)[0]
        if root in DESCRIPTION_ROOTS and re.search(DESCRIPTION_ROOTS[root][1],text,re.I):return True
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
        # Only specifically described fictional kinds may use class edges.
        # A type such as Person/Place/Product on a class never names an instance.
        for record in entity.get('classParents',[]):
            kind=record['type']
            if kind not in cache:cache[kind]=yago.path_to_root(kind,parents,ROOTS)
            paths={root:path for root,path in cache[kind].items()
                if ROOTS[root]=={'name_fictional'} and supported(root,entity['descriptions'])}
            if paths:entity['classPaths'][kind]=paths
        if entity['paths'] or entity['classPaths']:entities.append(entity)
    args.out.mkdir(parents=True);pipeline.jsonl(args.out/'names.jsonl',entities)
    meta.update(files={'names.jsonl':pipeline.digest(args.out/'names.jsonl')},roots={k:sorted(v) for k,v in ROOTS.items()},
        parentExtractionSha256=pipeline.digest(args.prepared/'manifest.json'),entities=len(entities),
        scope='additional specific instance types, excluding generic classes; software/service/device and character roots also require explicit supporting English description; no broad Product/CreativeWork promotion')
    (args.out/'manifest.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n');print(json.dumps({'preparedEntities':len(entities)}))


def extend(args):
    # Reuse identical inventory, exclusion, case and provenance handling while
    # requiring this extraction's independent root matrix on load and attach.
    meta=json.loads((args.prepared/'manifest.json').read_text())
    profiles=[roots for roots in [LEGACY_ROOTS,PREVIOUS_ROOTS,ROOTS] if meta['roots']=={k:sorted(v) for k,v in roots.items()}]
    if len(profiles)!=1:raise ValueError('Wrong specific roots')
    variants.extend(args,profiles[0],'yagoSpecificNamedTypes')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    for name in ['prepare','extend']:
        command=commands.add_parser(name)
        for arg in (['prepared','sources','out'] if name=='prepare' else ['base','seed','prepared','index','out']):command.add_argument('--'+arg,type=Path,required=True)
        if name=='extend':command.add_argument('--source-case-candidates',action='store_true')
    args=parser.parse_args();prepare(args) if args.command=='prepare' else extend(args)
