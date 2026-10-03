"""Deterministic, source-bound research evidence; existing candidates only."""
import csv,hashlib,io,json,pathlib,re,sqlite3,zipfile

def postal(db,args,e,pair,reading,sha,info,emit):
    path=pathlib.Path(args.postal_zip);version=sha(path)
    if info(db,'import:postal')=={'sha256':version,'parser':7}: return
    wanted={pair(r[0],r[1]) for r in db.execute('SELECT reading,surface FROM candidates')}
    wanted_names={s for _,s in wanted}
    import rescue
    wanted_surfaces=rescue.targets(db)
    did=e.save('https://www.post.japanpost.jp/zipcode/dl/utf/zip/utf_ken_all.zip',version,path.read_bytes(),'Japan Post postal data')
    db.execute('UPDATE facts SET active=0 WHERE document_id=?',(did,))
    def annotation(s): return bool(re.fullmatch(r'(?:地下|地上|第)?[0-9０-９一二三四五六七八九十百]+(?:階|丁目|番地)(?:以上|以下)?',s)) or s in ('その他','丁目','番地','区','一部','階層不明','地階・階層不明') or any(t in s for t in ('除く','番地','階層','丁目'))
    def instruction(s): return 'の次に番地がくる場合' in s or '以下に掲載がない場合' in s or s=='その他' or s.endswith('全域')
    count=0;seen=set()
    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv') and not n.startswith('__MACOSX/')]
        if len(names)!=1: raise ValueError('Postal ZIP needs one CSV')
        with z.open(names[0]) as f:
            for line,cells in enumerate(csv.reader(io.TextIOWrapper(f,encoding='utf-8-sig')),1):
                if len(cells)!=15: raise ValueError('Invalid postal CSV row')
                pr,cr,tr=map(reading,cells[3:6]);pref,city,town=[pair('',s)[1] for s in cells[6:9]]
                def add(y,s,kind='reading',categories=()):
                    nonlocal count
                    if (pair(y,s) in wanted or s in wanted_surfaces or (kind=='address-structure' and s in wanted_names)) and (kind=='address-structure' or not instruction(s)):
                        scope=cells[0][:2] if s==pref else cells[0]
                        target='JapanPost:'+hashlib.sha256(json.dumps([scope,s],ensure_ascii=False).encode()).hexdigest()[:24]
                        key=(y,s,kind,target)
                        if key in seen: return
                        seen.add(key)
                        e.fact(y,s,kind,categories,target,did,{'source':'Japan Post','row':line,'municipality':city,'town':town,'readingColumns':cells[3:6],'nameColumns':cells[6:9],'parser':7});count+=1
                for y,s in [(pr,pref),(cr,city),(pr+cr,pref+city)]:
                    add(y,s);add(y,s,'meaning',['place'])
                for y,s in [(tr,town),(cr+tr,city+town),(pr+cr+tr,pref+city+town)]:
                    add(y,s,'address-structure');add(y.replace('(','').replace(')',''),s,'address-structure')
                if instruction(town): continue
                sg=re.fullmatch(r'([^()]*)\(([^()]*)\)',town);rg=re.fullmatch(r'([^()]*)\(([^()]*)\)',tr)
                if '(' not in town and ')' not in town:
                    for y,s in [(tr,town),(cr+tr,city+town),(pr+cr+tr,pref+city+town)]:
                        add(y,s);add(y,s,'meaning',['place'])
                elif sg and rg:
                    head,alias=sg.groups();hy,ay=rg.groups()
                    for y,s in [(hy,head),(cr+hy,city+head),(pr+cr+hy,pref+city+head)]: add(y,s,'address-structure')
                    # A floor-specific town+building is not a verified canonical building name.
                    floor=bool(re.fullmatch(r'(?:(?:地下|地上|第)?[0-9０-９一二三四五六七八九十百]+階|地階|(?:地階・)?階層不明)',alias))
                    if not floor:
                        for y,s in [(hy,head),(cr+hy,city+head),(pr+cr+hy,pref+city+head)]:
                            add(y,s);add(y,s,'meaning',['place'])
                    if not annotation(alias) and not re.search('[、,～~・]',alias):
                        add(ay,alias);add(ay,alias,'meaning',['place'])
    info(db,'import:postal',{'sha256':version,'parser':7});db.commit();emit({'phase':'postal','facts':count,'sha256':version})

def snapshot_context(db,args,e,sha,info,emit):
    path=pathlib.Path(args.snapshot);version=sha(path)
    if info(db,'import:context')==version: return
    did=e.save('https://github.com/KazumaProject/kotlin-kana-kanji-converter/releases/tag/dictionary-metadata-841246a60a852ed8',version,path.read_bytes(),'Wikidata CC0; seed facts, not reverified reading evidence')
    s=sqlite3.connect('file:'+str(path.resolve())+'?mode=ro',uri=True);count=0
    # Keep direct-title vs alias lookup separate. Reference data is contextual, never quality proof.
    for surface,ids,direct in s.execute('SELECT surface,ids,direct_ids FROM lookup'):
        if not db.execute('SELECT 1 FROM candidates WHERE surface=? LIMIT 1',(surface,)).fetchone(): continue
        for qid in json.loads(ids):
            raw=s.execute('SELECT body FROM entities WHERE id=?',(qid,)).fetchone()
            if not raw: continue
            body=json.loads(raw[0]);body['directTitle']=qid in json.loads(direct);body['seedOnly']=True
            e.fact('',surface,'context',[],qid,did,body);count+=1
        if count%10000==0: db.commit()
    s.close();info(db,'import:context',version);db.commit();emit({'phase':'context','facts':count})

def normalization(db,e,fact_rows,canonical,info,emit):
    verified=excluded=0
    # Changed ORIGINAL candidates receive structural issues, not an inferred reading.
    for row in db.execute("SELECT * FROM candidates WHERE normalization LIKE 'original:%'").fetchall():
        origins=db.execute('SELECT o.* FROM origins o JOIN origin_candidates m ON o.id=m.origin_id WHERE m.candidate_id=?',(row['id'],)).fetchall()
        facts=fact_rows(db,row);postal=[f for f in facts if f['kind']=='address-structure']
        floor=bool(re.search(r'[（(](?:(?:地下|地上|第)?[0-9０-９一二三四五六七八九十百]+階|(?:地階・)?階層不明)[)）]',row['surface']))
        guide='以下に掲載がない場合' in row['surface'] or 'の次に番地がくる場合' in row['surface'] or row['surface'].endswith('全域')
        if postal and (floor or guide) and any(o['source']=='place' for o in origins):
            e.fact(row['reading'],row['surface'],'invalid',[],row['id'],postal[0]['document_id'],{'issue':'postal-annotation-not-independent-candidate','addressFact':postal[0]['id']});excluded+=1
    # Reuse the same proof checker after additional source acquisition.
    for row in db.execute("SELECT * FROM candidates WHERE normalization!='unchanged' AND normalization NOT LIKE 'original:%'").fetchall():
        verified+=check_normalization_row(db,e,row,fact_rows)
    info(db,'normalizationCheck',{'verified':verified,'excluded':excluded});db.commit();emit({'phase':'normalizationEvidence','verified':verified,'excluded':excluded})

def check_normalization_row(db,e,row,fact_rows):
    if row['normalization']=='unchanged' or row['normalization'].startswith('original:'): return 0
    facts=fact_rows(db,row);read=[f for f in facts if f['kind']=='reading']
    if not read: return 0
    origins=db.execute('SELECT o.* FROM origins o JOIN origin_candidates m ON o.id=m.origin_id WHERE m.candidate_id=?',(row['id'],)).fetchall()
    for original in origins:
        address=[f for f in fact_rows(db,original) if f['kind']=='address-structure']
        if not address:
            # Official floor readings may use numeric digits. The discarded floor
            # does not license a new reading: both retained components still need
            # exact independent proofs and an input reading boundary.
            address=[dict(f) for f in db.execute("SELECT * FROM facts WHERE active=1 AND kind='address-structure' AND surface=?",(original['surface'],))]
        if not address: continue
        s,y=original['surface'],original['reading'];out_s,out_y=row['surface'],row['reading']
        components=re.fullmatch(r'([^()]*)\(([^()]*)\)',s)
        # Whole-row postal evidence fixes the original pair. Component readings fix the boundary.
        boundary=bool(components and ((out_s==components.group(1) and y.startswith(out_y)) or (out_s==components.group(2) and y.endswith(out_y))))
        prefix_proof=None
        if not boundary:
            head=components.group(1) if components else s
            if head!=out_s and head.endswith(out_s):
                prefix=head[:-len(out_s)]
                choices=[dict(f) for f in db.execute("SELECT * FROM facts WHERE surface=? AND kind='reading' AND active=1",(prefix,)) if y.startswith(f['reading']+out_y)]
                if len({f['reading'] for f in choices})==1:
                    prefix_proof=choices[0];boundary=True
        if boundary:
            body={'originalSource':original['source'],'originalLine':original['line'],'originalSurface':s,'originalReading':y,'outputSurface':out_s,'outputReading':out_y,'fullAddressEvidence':address[0]['id'],'outputEvidence':read[0]['id']}
            if prefix_proof: body['prefixEvidence']=prefix_proof['id']
            e.fact(out_y,out_s,'normalization',[],row['id'],address[0]['document_id'],body)
            return 1
    return 0
