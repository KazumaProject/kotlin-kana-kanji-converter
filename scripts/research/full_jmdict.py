"""Supplemental full-XML JMdict evidence for existing candidate pairs only.

This importer records constrained readings and individual meanings. Broad POS or
field tags never classify an entry as general, technical, or food automatically.
"""
import gzip,html,json,pathlib,re,time,xml.etree.ElementTree as ET
import worker as w

PARSER_VERSION=2
IMPORT_KEY='import:JMdict-full-pairs'
XML_LANG='{http://www.w3.org/XML/1998/namespace}lang'

def source_stream(path):
    path=pathlib.Path(path)
    with path.open('rb') as f: compressed=f.read(2)==b'\x1f\x8b'
    return gzip.open(path,'rb') if compressed else path.open('rb')

def entity_codes(path):
    with source_stream(path) as f: prefix=f.read(1024*1024+1)
    root=re.search(br'<JMdict(?:\s|>)',prefix)
    if root is None: raise ValueError('Missing/oversized JMdict XML header')
    header=prefix[:root.start()]
    if re.search(br'<!DOCTYPE\s+JMdict\s+(?:SYSTEM|PUBLIC)\b',header) or re.search(br'<!ENTITY\s+%',header) or re.search(br'<!ENTITY\s+[^>]+\b(?:SYSTEM|PUBLIC)\b',header):
        raise ValueError('External XML DTD/entities prohibited')
    declarations=re.findall(br'<!ENTITY\s+([\w-]+)\s+(["\'])(.*?)\2\s*>',header,re.S)
    return {html.unescape(value.decode('utf-8')):name.decode('ascii') for name,quote,value in declarations}

def scan(path,wanted):
    """Yield one bound pair/sense; never yields a headword absent from wanted."""
    wanted={w.pair(y,s) for y,s in wanted};codes=entity_codes(path)
    def tags(node,field): return sorted({codes.get(child.text,child.text) for child in node.findall(field) if child.text})
    with source_stream(path) as stream:
        root=None
        for event,node in ET.iterparse(stream,events=('start','end')):
            if root is None and event=='start':
                root=node
                if root.tag!='JMdict': raise ValueError('Expected JMdict XML root')
            if event!='end' or node.tag!='entry': continue
            seq=node.findtext('ent_seq')
            if not seq: raise ValueError('JMdict entry lacks ent_seq')
            spelling_nodes=node.findall('k_ele');spellings={k.findtext('keb'):tags(k,'ke_inf') for k in spelling_nodes}
            if None in spellings or '' in spellings: raise ValueError('JMdict spelling missing')
            reading_nodes=node.findall('r_ele');raw_readings={r.findtext('reb') for r in reading_nodes}
            if None in raw_readings or '' in raw_readings: raise ValueError('JMdict reading missing')
            matched=[]
            for rr in reading_nodes:
                reb=rr.findtext('reb');restrict=[r.text for r in rr.findall('re_restr')]
                if not set(restrict)<=set(spellings): raise ValueError('Invalid JMdict reading restriction')
                no_kanji=rr.find('re_nokanji') is not None
                eligible=[] if no_kanji else [s for s in spellings if not restrict or s in restrict]
                # Kana forms remain subject to sense spelling restrictions below.
                for surface in dict.fromkeys(eligible+[reb]):
                    y,s=w.pair(reb,surface)
                    if (y,s) in wanted:
                        matched.append((y,s,reb,surface,restrict,no_kanji,tags(rr,'re_inf'),spellings.get(surface,[])))
            inherited_pos=[]
            for index,sense in enumerate(node.findall('sense'),1):
                explicit_pos=tags(sense,'pos')
                if explicit_pos: inherited_pos=explicit_pos
                stagk=[c.text for c in sense.findall('stagk')];stagr=[c.text for c in sense.findall('stagr')]
                if not set(stagk)<=set(spellings) or not set(stagr)<=raw_readings:
                    raise ValueError('Invalid JMdict sense restriction')
                misc=tags(sense,'misc');fields=tags(sense,'field')
                # These are precise name attributes only; lexical/field decisions
                # remain inspectable source-review work regardless of POS.
                categories=w.name_categories(misc)
                glosses=[{'text':''.join(g.itertext()),'language':g.get(XML_LANG,'eng'),
                          'attributes':{k:v for k,v in g.attrib.items() if k!=XML_LANG}} for g in sense.findall('gloss')]
                for y,s,reb,surface,restrict,no_kanji,re_info,ke_info in matched:
                    if (stagk and surface not in stagk) or (stagr and reb not in stagr): continue
                    body={'source':'JMdict','fullParserVersion':PARSER_VERSION,'entryId':seq,'sense':index,
                          'reading':y,'surface':s,'rawReading':reb,'rawSurface':surface,
                          're_restr':restrict,'re_nokanji':no_kanji,'stagk':stagk,'stagr':stagr,
                          'pos':inherited_pos[:],'posExplicit':explicit_pos,'misc':misc,'fields':fields,
                          'readingInfo':re_info,'spellingInfo':ke_info,'glosses':[g['text'] for g in glosses],
                          'glossDetails':glosses,'senseInfo':[s.text for s in sense.findall('s_inf')],
                          'xref':[s.text for s in sense.findall('xref')],'ant':[s.text for s in sense.findall('ant')],
                          'dialect':tags(sense,'dial'),'evidence':'https://www.edrdg.org/jmdict/edict_doc.html#entry-'+seq+'-sense-'+str(index)}
                    yield {'reading':y,'surface':s,'target':'JMdict:'+seq+':sense:'+str(index),
                           'categories':categories,'body':body}
            node.clear();root.clear()

def import_full(db,args,e=None):
    path=pathlib.Path(args.jmdict);version=w.sha(path);saved=w.info(db,IMPORT_KEY)
    candidate_count=db.execute('SELECT COUNT(*) FROM candidates').fetchone()[0]
    active=db.execute("SELECT COUNT(*) FROM facts f JOIN documents d ON d.id=f.document_id WHERE f.active=1 AND d.sha256=? AND json_extract(f.body,'$.source')='JMdict' AND json_extract(f.body,'$.fullParserVersion')=?",(version,PARSER_VERSION)).fetchone()[0]
    if saved and saved.get('sha256')==version and saved.get('parser')==PARSER_VERSION and saved.get('activeFacts')==active and saved.get('candidateCount')==candidate_count:
        w.emit({'phase':'JMdict-full-pairs','cached':True,**saved});return saved
    wanted={(r[0],r[1]) for r in db.execute('SELECT reading,surface FROM candidates')}
    e=e or w.Evidence(db,args)
    # Same URL/revision/content identity reuses the pinned document already saved
    # by the baseline importer. No baseline provider facts are retired here.
    doc=e.save('https://www.edrdg.org/pub/Nihongo/JMdict_e.gz',version,path.read_bytes(),'EDRDG / CC-BY-SA-4.0')
    pairs=set();senses=0;started=time.monotonic()
    for record in scan(path,wanted):
        y,s=record['reading'],record['surface'];body={**record['body'],'version':version}
        if 'sk' not in body['readingInfo'] and 'sK' not in body['spellingInfo']:
            e.fact(y,s,'reading',[],record['target'],doc,body)
        e.fact(y,s,'meaning',record['categories'],record['target'],doc,body)
        pairs.add((y,s));senses+=1
        if senses%1000==0:
            db.commit();w.emit({'phase':'JMdict-full-pairs','pairSenses':senses,'matchedPairs':len(pairs),'seconds':round(time.monotonic()-started,2)})
    active=db.execute("SELECT COUNT(*) FROM facts WHERE active=1 AND document_id=? AND json_extract(body,'$.source')='JMdict' AND json_extract(body,'$.fullParserVersion')=?",(doc,PARSER_VERSION)).fetchone()[0]
    result={'sha256':version,'parser':PARSER_VERSION,'pairSenses':senses,'matchedPairs':len(pairs),'activeFacts':active,'candidateCount':candidate_count,'seconds':round(time.monotonic()-started,2)}
    w.info(db,IMPORT_KEY,result);db.commit();w.emit({'phase':'JMdict-full-pairs',**result});return result

def analyze(db,path):
    """Read-only coverage estimate; matching evidence is not final adoption."""
    pending={};wanted=set()
    for row in db.execute('SELECT reading,surface,state FROM candidates'):
        pair=w.pair(row[0],row[1]);wanted.add(pair)
        if row[2] not in ('reviewed',*w.TERMINAL): pending[pair]=pending.get(pair,0)+1
    found=set();pending_senses=0;senses=0;started=time.monotonic()
    for record in scan(path,wanted):
        pair=(record['reading'],record['surface']);found.add(pair);senses+=1
        pending_senses+=pair in pending
    return {'matchedPairs':len(found),'matchedPendingPairs':len(found&pending.keys()),
            'matchedPendingCandidates':sum(pending[p] for p in found if p in pending),
            'pairSenses':senses,'pendingPairSenses':pending_senses,'seconds':round(time.monotonic()-started,2),
            'sha256':w.sha(path),'notAnAdoptionEstimate':True}
