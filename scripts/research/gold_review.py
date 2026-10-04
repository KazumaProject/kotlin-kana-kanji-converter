"""Assemble independently authored annotations into source-bound gold partials.

Availability strata never supply labels. Documents and the production ledger are
read-only; unresolved reading facts remain reported for separate registration.
"""
import argparse,csv,gzip,hashlib,html,io,json,pathlib,re,sqlite3,zipfile,xml.etree.ElementTree as ET
import worker as w

def literal_entry_root(raw):
    # Entity codes affect lexical annotations, not reading/surface text. Preserve
    # the original unexpanded XML as the actual quotation.
    expanded=re.sub(r'&([A-Za-z][\w-]*);',lambda m:m[0] if m[1] in ('amp','lt','gt','quot','apos') else m[1],raw)
    root=ET.fromstring(expanded)
    if root.tag!='entry': raise ValueError('Expected literal reference entry')
    return root

def xml_binding(case,record,require_attested=False):
    """Independently check pair and sense restrictions from the literal XML."""
    raw=record['literalOriginalEntry'];root=literal_entry_root(raw)
    seq=root.findtext('ent_seq');b=record['rawRecord']
    if str(b.get('entryId'))!=seq: raise ValueError('Reference entry identity mismatch')
    y,s=w.pair(case['reading'],case['surface']);spellings=[k.findtext('keb') for k in root.findall('k_ele')]
    choices=[]
    for r in root.findall('r_ele'):
        reb=r.findtext('reb')
        if not reb or w.reading(reb)!=y: continue
        restrictions=[c.text for c in r.findall('re_restr')]
        if not set(restrictions)<=set(spellings): raise ValueError('Unknown reading restriction')
        possible=[reb]
        if r.find('re_nokanji') is None: possible += [k for k in spellings if not restrictions or k in restrictions]
        search_reading=any(c.text=='sk' for c in r.findall('re_inf'))
        search_spellings={k.findtext('keb') for k in root.findall('k_ele') if any(c.text=='sK' for c in k.findall('ke_inf'))}
        choices += [(reb,k,not search_reading and k not in search_spellings) for k in possible if w.pair(reb,k)==(y,s)]
    if not choices: raise ValueError('Candidate reading/spelling is not bound by raw reference')
    if record['source']=='JMdict':
        expected='JMdict:'+seq+':sense:'+str(b.get('sense'))
        if record['target']!=expected or type(b.get('sense')) is not int: raise ValueError('Sense target mismatch')
        senses=root.findall('sense');index=b['sense']-1
        if not 0<=index<len(senses): raise ValueError('Missing reference sense')
        sense=senses[index];ks=[c.text for c in sense.findall('stagk')];rs=[c.text for c in sense.findall('stagr')]
        choices=[(r,k,attested) for r,k,attested in choices if (not ks or k in ks) and (not rs or r in rs)]
        if not choices: raise ValueError('Candidate outside selected sense restrictions')
        if not sense.findall('gloss'): raise ValueError('Selected sense has no meaning')
        # The selected target must preserve the original individual sense gloss.
        if b.get('glosses') != [''.join(c.itertext()) for c in sense.findall('gloss')]: raise ValueError('Parsed sense differs from original source')
    elif record['source']=='JMnedict':
        index=b.get('sense');trans=root.findall('trans')
        if type(index) is not int or not 0<=index<len(trans) or record['target']!='JMnedict:'+seq+':'+str(index): raise ValueError('Name translation target mismatch')
        translated=[[''.join(c.itertext()) for c in t.findall('trans_det')] for t in trans]
        if b.get('translations')!=translated: raise ValueError('Parsed name translation differs from original source')
    else: raise ValueError('Not an XML lexical reference')
    if require_attested and not any(attested for r,k,attested in choices): raise ValueError('Search-only kana/spelling is not attested')
    return raw

def wikidata_entity(text,target):
    value=json.loads(text)
    if 'entities' in value: value=value['entities'].get(target,{})
    if value.get('id')!=target: raise ValueError('Wikidata source target mismatch')
    return value

def normalized_name(value): return w.pair('',value)[1]
def is_kana(value): return bool(value) and all('ぁ'<=c<='ゖ' or 'ァ'<=c<='ヶ' or c=='ー' for c in value)

def wikidata_binding(case,entity):
    """Return literal reading quotes; aliases cannot borrow primary-name readings."""
    surface=normalized_name(case['surface']);y=w.reading(case['reading'])
    label=entity.get('labels',{}).get('ja',{});title=entity.get('sitelinks',{}).get('jawiki',{}).get('title','')
    canonical=[n for n in (label.get('value',''),title) if normalized_name(n)==surface]
    refs=[]
    if canonical and is_kana(surface) and w.reading(surface)==y:
        if normalized_name(label.get('value',''))==surface: refs.append(w.canonical(label))
        else: refs.append(w.canonical(entity['sitelinks']['jawiki']))
    import batch_research
    for name,value,statement,qualified in batch_research.reading_bindings(entity):
        if batch_research.name_key(name)==batch_research.name_key(case['surface']) and batch_research.reading_key(value)==batch_research.reading_key(case['reading']): refs.append(w.canonical(statement))
    return refs

def postal_binding(case,record,raw):
    """Bind a native postal target to its literal administrative CSV record."""
    quote=record.get('literalOriginalRow','')
    if not quote or quote not in raw.splitlines(): raise ValueError('Postal quotation is not an original complete row')
    values=list(csv.reader([quote]))
    if len(values)!=1 or len(values[0])!=15: raise ValueError('Invalid original postal row')
    cells=values[0];y,s=w.pair(case['reading'],case['surface'])
    pr,cr,tr=map(w.reading,cells[3:6]);pref,city,town=[w.pair('',v)[1] for v in cells[6:9]]
    choices=[(pr,pref),(cr,city),(pr+cr,pref+city)]
    if '(' not in town and ')' not in town and not ('以下に掲載がない場合' in town or 'の次に番地がくる場合' in town or town=='その他' or town.endswith('全域')):
        choices += [(tr,town),(cr+tr,city+town),(pr+cr+tr,pref+city+town)]
    if (y,s) not in choices: raise ValueError('Candidate not explicitly bound by native postal row')
    scope=cells[0][:2] if s==pref else cells[0]
    target='JapanPost:'+hashlib.sha256(json.dumps([scope,s],ensure_ascii=False).encode()).hexdigest()[:24]
    if record['target']!=target: raise ValueError('Postal administrative target mismatch')
    return quote

class Sources:
    def __init__(self,db): self.db=db;self.docs={};self.raw={};self.text={}
    def document(self,did):
        if did not in self.docs:
            row=self.db.execute('select * from documents where id=?',(did,)).fetchone()
            if row is None: raise ValueError('Unknown source document: '+did)
            doc=dict(row);data=pathlib.Path(doc['path']).read_bytes()
            if hashlib.sha256(data).hexdigest()!=doc['sha256']: raise ValueError('Source checksum changed: '+did)
            self.docs[did]=doc
            if data.startswith(b'\x1f\x8b'): data=gzip.decompress(data)
            elif data.startswith(b'PK\x03\x04'):
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    files=[n for n in archive.namelist() if not n.endswith('/') and not n.startswith('__MACOSX/')]
                    if len(files)!=1: raise ValueError('Gold source ZIP needs one file')
                    data=archive.read(files[0])
            self.raw[did]=data.decode('utf-8',errors='strict')
        return self.docs[did]
    def quote(self,did,quotation):
        doc=self.document(did)
        if did not in self.text: self.text[did]=w.source_text(doc['path'])
        if not quotation or quotation not in self.text[did]: raise ValueError('Quotation absent from source: '+did)
        return {'documentId':did,'quotation':quotation,'sha256':doc['sha256']}

def assemble(db,batch,annotations):
    if annotations.get('selectionCanonicalSha256')!=batch.get('selectionCanonicalSha256'): raise ValueError('Annotations belong to another fixed selection')
    if not annotations.get('inspector'): raise ValueError('Independent inspector required')
    src=Sources(db);output=[];seen=set();covered=set();issues=[]
    valid_categories={c['id'] for c in json.loads((w.DEFAULT_CONFIG/'categories.json').read_text())['categories']}
    for ann in annotations.get('annotations',[]):
        if type(ann.get('caseIndex')) is not int or type(ann.get('recordIndex')) is not int: raise ValueError('Explicit case/record index required')
        ci,ri=ann['caseIndex']-1,ann['recordIndex']
        if not 0<=ci<len(batch['cases']) or not 0<=ri<len(batch['cases'][ci]['records']): raise ValueError('Annotation index outside batch')
        case=batch['cases'][ci];record=case['records'][ri];cats=ann.get('categories')
        if not isinstance(cats,list) or (not cats and ann.get('eligible') is not False) or any(not isinstance(c,str) for c in cats) or len(cats)!=len(set(cats)) or not set(cats)<=valid_categories: raise ValueError('Explicit valid reviewed categories required')
        if type(ann.get('eligible')) is not bool: raise ValueError('Explicit reading/eligibility judgment required')
        target=record['target'];key=(case['candidateId'],target)
        if key in seen: raise ValueError('Duplicate reviewed candidate/target')
        seen.add(key);covered.add(case['candidateId'])
        row=db.execute('select reading,surface from candidates where id=?',(case['candidateId'],)).fetchone()
        if row is None or tuple(row)!=(case['reading'],case['surface']): raise ValueError('Batch candidate differs from original inputs')
        did=record['documentId'];src.document(did)
        if record['source'] in ('JMdict','JMnedict'):
            raw=xml_binding(case,record,require_attested=ann['eligible'])
            read_refs=[src.quote(did,raw)];meaning_refs=[src.quote(did,raw)]
        elif record['source']=='Japan Post':
            raw=postal_binding(case,record,src.raw[did])
            read_refs=[src.quote(did,raw)];meaning_refs=[src.quote(did,raw)]
        elif record['source']=='Wikidata':
            entity=wikidata_entity(src.raw[did],target)
            names=[v.get('value','') for v in entity.get('labels',{}).values()]
            names += [v.get('value','') for vs in entity.get('aliases',{}).values() for v in vs]
            names += [v.get('title','') for v in entity.get('sitelinks',{}).values()]
            import batch_research
            names += [n for n,y,statement,qualified in batch_research.reading_bindings(entity)]
            if normalized_name(case['surface']) not in {normalized_name(n) for n in names}: raise ValueError('Input spelling is not an explicit name of source entity')
            claims=entity.get('claims',{}).get('P31',[])
            if not claims: raise ValueError('Entity source has no class statements for meaning inspection')
            meaning_refs=[src.quote(did,w.canonical(claims))]
            for lang in ('ja','en'):
                desc=entity.get('descriptions',{}).get(lang)
                if desc: meaning_refs.append(src.quote(did,w.canonical(desc)))
            literal_readings=wikidata_binding(case,entity)
            if ann['eligible'] and not literal_readings and not ann.get('readingEvidence'): raise ValueError('Eligible entity has no literal full reading binding: '+case['candidateId'])
            # Negative/unresolved reading judgments still cite the original entity context.
            read_refs=[src.quote(did,q) for q in literal_readings] if literal_readings else [src.quote(did,w.canonical(entity.get('labels',{})))]
        else: raise ValueError('Unsupported source type; supply separately checked sources')
        for field,refs in (('readingEvidence',read_refs),('meaningEvidence',meaning_refs)):
            if field in ann:
                refs[:]=[src.quote(e['documentId'],e['quotation']) for e in ann[field]]
                if not refs: raise ValueError('Empty checked source references')
        facts=db.execute('select kind,document_id,target from facts where active=1 and surface=? and reading in (?,\'\')',(case['surface'],case['reading'])).fetchall()
        if ann['eligible'] and ann.get('readingEvidence') and not all(any(f['kind']=='reading' and f['document_id']==e['documentId'] and f['target']==target for f in facts) for e in read_refs): raise ValueError('External reading quotation needs a verified pair/target reading fact')
        for field,refs,kinds in [('readingEvidence',read_refs,('reading',) if ann['eligible'] else ('reading','context','meaning')),('meaningEvidence',meaning_refs,('meaning','context'))]:
            for ref in refs:
                if not any(f['kind'] in kinds and f['document_id']==ref['documentId'] and (field=='readingEvidence' or f['target']==target) for f in facts):issues.append({'candidateId':case['candidateId'],'target':target,'field':field,'documentId':ref['documentId'],'reason':'checked-source-needs-pair-target-registration'})
        output.append({'candidateId':case['candidateId'],'split':case['split'],'categories':cats,'target':target,'readingEvidence':read_refs,'meaningEvidence':meaning_refs,'eligible':ann['eligible']})
    missing=sorted({c['candidateId'] for c in batch['cases']}-covered)
    return {'schemaVersion':1,'cases':output},{'selectionCanonicalSha256':batch['selectionCanonicalSha256'],'inspector':annotations['inspector'],'reviewedCandidates':len(covered),'reviewedTargetCases':len(output),'unreviewedCandidateIds':missing,'registrationRequired':issues,'productionLedgerWritten':False}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ledger',default='build/research/ledger.sqlite');p.add_argument('--batch',required=True);p.add_argument('--annotations',required=True);p.add_argument('--output',required=True);args=p.parse_args(argv)
    db=sqlite3.connect('file:'+str(pathlib.Path(args.ledger).resolve())+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    batch=json.loads(pathlib.Path(args.batch).read_text());annotations=json.loads(pathlib.Path(args.annotations).read_text());result,audit=assemble(db,batch,annotations)
    out=pathlib.Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');audit['batchSha256']=w.sha(args.batch);audit['annotationsSha256']=w.sha(args.annotations);audit['partialGoldSha256']=w.sha(out);out.with_suffix('.audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');print(w.canonical(audit))

if __name__=='__main__':main()
