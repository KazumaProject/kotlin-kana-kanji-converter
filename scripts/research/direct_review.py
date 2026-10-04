"""Source-bound resolutions and inspectable exception batches; never calls a model."""
import gzip, json, pathlib, re, sqlite3, time, urllib.error
import worker as w

RULE_VERSION = 7
MAX_ATTEMPTS = 3
_verified = {}
_texts = {}


def invalidate_configuration(db, old, new):
    """Version semantic stages explicitly; packaging/logging edits are not input changes."""
    db.execute('CREATE TEMP TABLE IF NOT EXISTS changed_candidates(id TEXT PRIMARY KEY)')
    db.execute('DELETE FROM changed_candidates')
    old_stages = old.get('stages', {})
    stages = new['stages']
    if old_stages.get('onlineReadingParser', old.get('researchParserVersion')) != stages['onlineReadingParser']:
        sources = "(json_extract(f.body,'$.source')='explicit-name-reading' OR (json_extract(f.body,'$.source')='attested-canonical-kana' AND COALESCE(json_extract(f.body,'$.binding'),'')!='Wikidata primary Japanese name'))"
        db.execute('CREATE TEMP TABLE IF NOT EXISTS retired_facts(id TEXT PRIMARY KEY)')
        db.execute('DELETE FROM retired_facts')
        db.execute('INSERT INTO retired_facts SELECT f.id FROM facts f WHERE f.active=1 AND ' + sources)
        expand_retired_dependencies(db)
        db.execute("INSERT OR IGNORE INTO changed_candidates SELECT c.id FROM retired_facts r JOIN facts f ON f.id=r.id JOIN candidates c ON c.surface=f.surface AND (f.reading='' OR f.reading=c.reading)")
        db.execute('UPDATE facts SET active=0 WHERE id IN (SELECT id FROM retired_facts)')
        w.info(db, 'onlineReadingsNeedReparse', True)
    if old_stages.get('directRules') != stages['directRules']:
        if old_stages.get('directRules') in (1, 2, 3) and stages['directRules'] == 4:
            # This ruleset adds only exact Wikidata human/character types. Revisit
            # pairs with a name-bound type and same-item reading proof; preserve all
            # unrelated direct and manually reviewed decisions.
            db.execute("""INSERT OR IGNORE INTO changed_candidates
                SELECT DISTINCT c.id FROM candidates c
                JOIN facts f ON f.surface=c.surface AND (f.reading=c.reading OR f.reading='')
                WHERE f.active=1 AND f.kind='context'
                  AND json_extract(f.body,'$.source')='Wikidata'
                  AND json_extract(f.body,'$.id')=f.target
                  AND (EXISTS (SELECT 1 FROM json_each(f.body,'$.types') t WHERE t.value IN ('Q5','Q95074')))
                  AND (json_extract(f.body,'$.label')=c.surface OR json_extract(f.body,'$.title')=c.surface
                       OR EXISTS (SELECT 1 FROM json_each(f.body,'$.nameBoundReadings') n WHERE n.key=c.surface))
                  AND COALESCE(json_extract(c.decision,'$.classificationRoute'),'')!='source_review'
                  AND EXISTS (SELECT 1 FROM facts r WHERE r.active=1 AND r.kind='reading'
                       AND r.surface=c.surface AND r.reading=c.reading AND r.target=f.target)""")
        elif old_stages.get('directRules') == 4 and stages['directRules'] == 5:
            # JMdict's importer stores categories only after checking the raw
            # reading/sense restrictions. Revisit only those exact lexical pairs;
            # broad POS/field tags and source-reviewed decisions remain untouched.
            db.execute("""INSERT OR IGNORE INTO changed_candidates
                SELECT DISTINCT c.id FROM candidates c
                JOIN facts f ON f.surface=c.surface AND f.reading=c.reading
                JOIN json_each(f.categories) cat
                WHERE f.active=1 AND f.kind='meaning'
                  AND json_extract(f.body,'$.source')='JMdict'
                  AND json_extract(f.body,'$.classificationPolicy')=4
                  AND cat.value IN ('general','food','technical')
                  AND EXISTS (SELECT 1 FROM json_each(f.body,'$.categories') stored WHERE stored.value=cat.value)
                  AND f.target=replace(replace(json_extract(f.body,'$.evidence'),
                                'https://www.edrdg.org/jmdict/edict_doc.html#entry-','JMdict:'),
                                '-sense-',':sense:')
                  AND EXISTS (SELECT 1 FROM facts r WHERE r.active=1 AND r.kind='reading'
                       AND r.surface=c.surface AND r.reading=c.reading
                       AND json_extract(r.body,'$.source')='JMdict'
                       AND r.target=json_extract(f.body,'$.entryId'))
                  AND COALESCE(json_extract(c.decision,'$.classificationRoute'),'')!='source_review'
                  AND c.state NOT IN ('blocked','error','excluded_confirmed')""")
        elif old_stages.get('directRules') == 5 and stages['directRules'] == 6:
            # Tight JMnedict sense rules: exact original translation type plus
            # same-entry, same-document constrained reading. This affects only
            # the precise Japanese pair; manually reviewed decisions survive.
            db.execute("""INSERT OR IGNORE INTO changed_candidates
                SELECT DISTINCT c.id FROM facts f INDEXED BY fact_status
                JOIN candidates c ON c.surface=f.surface AND c.reading=f.reading
                JOIN json_each(f.body,'$.nameTypes') nt
                JOIN json_each(f.body,'$.translations') tr
                JOIN json_each(tr.value) td
                WHERE f.active=1 AND f.kind='meaning'
                  AND json_extract(f.body,'$.source')='JMnedict'
                  AND json_array_length(f.body,'$.nameTypes')=1
                  AND ((nt.value='place' AND c.normalization='unchanged'
                        AND (td.value LIKE '% (river)' OR td.value LIKE '% (island)' OR
                             td.value LIKE '% (mountain)' OR td.value LIKE '% (mountain range)' OR
                             td.value LIKE '% (lake)' OR td.value LIKE '% (peninsula)' OR
                             td.value LIKE '% (bay)' OR td.value LIKE '% (city)'))
                    OR (nt.value='myth' AND c.normalization='unchanged'
                        AND (lower(td.value) LIKE '% (mother goddess of chinese mythology)' OR
                             lower(td.value) LIKE '% (spiritual dragon in chinese mythology)' OR
                             lower(td.value) LIKE '% (dragon-god in chinese mythology)')))
                  AND tr.key=json_extract(f.body,'$.sense')
                  AND f.target='JMnedict:'||json_extract(f.body,'$.entryId')||':'||json_extract(f.body,'$.sense')
                  AND EXISTS (SELECT 1 FROM facts r INDEXED BY fact_pair
                       WHERE r.active=1 AND r.kind='reading' AND r.surface=f.surface AND r.reading=f.reading
                         AND r.document_id=f.document_id
                         AND r.target='JMnedict:'||json_extract(f.body,'$.entryId')
                         AND json_extract(r.body,'$.source')='JMnedict'
                         AND json_extract(r.body,'$.entryId')=json_extract(f.body,'$.entryId')
                         AND (json_array_length(r.body,'$.re_restr')=0 OR
                              EXISTS (SELECT 1 FROM json_each(r.body,'$.re_restr') restriction WHERE restriction.value=f.surface)))
                  AND COALESCE(json_extract(c.decision,'$.classificationRoute'),'')!='source_review'
                  AND c.state NOT IN ('blocked','error','excluded_confirmed')""")
        elif old_stages.get('directRules') == 6 and stages['directRules'] == 7:
            retire_legacy_jmdict_categories(db)
        else:
            db.execute("INSERT OR IGNORE INTO changed_candidates SELECT id FROM candidates WHERE decision IS NOT NULL AND (json_extract(decision,'$.classificationRoute')='direct' OR EXISTS (SELECT 1 FROM json_each(candidates.decision,'$.roles') r WHERE json_extract(r.value,'$.method')='direct'))")
    if old.get('models') != new.get('models') or old.get('prompts') != new.get('prompts'):
        db.execute("INSERT OR IGNORE INTO changed_candidates SELECT id FROM candidates WHERE state='ready_review' OR (decision IS NOT NULL AND json_extract(decision,'$.classificationRoute')='ai')")
    if old.get('taxonomy') != new.get('taxonomy'):
        before = {c['id']: c for c in old.get('taxonomy', {}).get('categories', [])}
        after = {c['id']: c for c in new['taxonomy']['categories']}
        def semantics(category):
            return {k: v for k, v in category.items() if k not in ('core', 'minimum')} if category else None
        changed = [k for k in before.keys() | after.keys() if semantics(before.get(k)) != semantics(after.get(k))]
        for category in changed:
            db.execute("INSERT OR IGNORE INTO changed_candidates SELECT c.id FROM candidates c,json_each(c.decision,'$.roles') role WHERE json_extract(role.value,'$.category')=?", (category,))
            db.execute("INSERT OR IGNORE INTO changed_candidates SELECT c.id FROM facts f,json_each(f.categories) cat JOIN candidates c ON c.surface=f.surface AND (f.reading='' OR f.reading=c.reading) WHERE f.active=1 AND cat.value=?", (category,))
        if changed:
            frozen = w.info(db, 'goldFrozen')
            if frozen:
                w.archive_frozen_gold(db, frozen)
            db.execute("DELETE FROM info WHERE key='goldFrozen'")
    db.execute("INSERT INTO decision_history(candidate_id,state,reason,decision,change,created) SELECT id,state,reason,decision,'stage-configuration-changed',? FROM candidates WHERE id IN (SELECT id FROM changed_candidates)", (time.time(),))
    # Affected pair decisions are reconsidered; completed research and unrelated errors survive.
    db.execute("UPDATE candidates SET state=CASE WHEN error IS NOT NULL AND state IN ('blocked','error') THEN state ELSE 'queued' END,decision=NULL,reason='stage-configuration-changed' WHERE id IN (SELECT id FROM changed_candidates)")
    count = db.execute('SELECT COUNT(*) FROM changed_candidates').fetchone()[0]
    if count or old_stages.get('publication') != stages['publication'] or old.get('taxonomy') != new.get('taxonomy'):
        db.execute("DELETE FROM info WHERE key IN ('finalized','acceptance')")
    w.info(db, 'lastInvalidation', {'candidates': count, 'wholeLedgerReset': False})


def retire_legacy_jmdict_categories(db):
    """Withdraw legacy POS/field taxonomy, preserving separately proved roles."""
    rows=db.execute("""SELECT c.* FROM candidates c WHERE c.decision IS NOT NULL
        AND EXISTS (SELECT 1 FROM json_each(c.decision,'$.roles') role
          JOIN json_each(role.value,'$.evidenceIds') ref
          JOIN facts f ON f.id=ref.value
          WHERE COALESCE(json_extract(role.value,'$.method'),json_extract(c.decision,'$.classificationRoute'))='direct'
            AND json_extract(role.value,'$.category') IN ('general','technical','food')
            AND json_extract(f.body,'$.source')='JMdict'
            AND json_extract(f.body,'$.classificationPolicy')=4)""").fetchall()
    removed=0
    for raw in rows:
        row=dict(raw);decision=json.loads(row['decision']);roles=[]
        for role in decision.get('roles',[]):
            legacy=role.get('method',decision.get('classificationRoute'))=='direct' and role['category'] in ('general','technical','food')
            if legacy:
                legacy=any((lambda b:b.get('source')=='JMdict' and b.get('classificationPolicy')==4)(json.loads(f[0]))
                    for fid in role['evidenceIds'] for f in db.execute('SELECT body FROM facts WHERE id=?',(fid,)))
            if legacy:removed+=1
            else:roles.append(role)
        decision['roles']=roles
        decision['classificationRoute']=('source_review' if any(r.get('method')=='source_review' for r in roles) else 'direct') if roles else None
        selected=set(decision.get('readingEvidence',[])+decision.get('normalizationEvidence',[])+decision.get('exclusionEvidence',[]))
        selected.update(fid for role in roles for fid in role['evidenceIds'])
        decision['citations']=[c for c in decision.get('citations',[]) if c['evidenceId'] in selected]
        write_decision(db,row,row['state'] if roles else 'needs_review',
            row['reason'] if roles else 'Legacy POS/field category withdrawn; literal meaning review required',decision)
    w.info(db,'legacyJmdictTaxonomyWithdrawn',{'candidates':len(rows),'roles':removed,'unrelatedRolesPreserved':True})


def reparse_saved_readings(db, args):
    """A reading-parser change reuses already acquired raw articles, with no HTTP calls."""
    if not w.info(db, 'onlineReadingsNeedReparse'):
        return
    import re
    e = w.Evidence(db, args); processed = 0
    rows = db.execute("SELECT DISTINCT c.*,f.document_id,f.target,f.body AS context_body FROM candidates c JOIN facts f ON f.surface=c.surface AND (f.reading='' OR f.reading=c.reading) WHERE f.active=1 AND f.kind='context' AND json_extract(f.body,'$.source') IN ('Wikipedia','official-link')").fetchall()
    for raw in rows:
        row = dict(raw)
        try:
            doc = verify_document(db, raw['document_id'])
            data = pathlib.Path(doc['path']).read_bytes()
            if data.startswith(b'\x1f\x8b'):
                data = gzip.decompress(data)
            body = json.loads(raw['context_body'])
            if body['source'] == 'Wikipedia':
                value = json.loads(data)
                for page in value.get('query', {}).get('pages', {}).values():
                    if 'missing' in page or not page.get('revisions'):
                        continue
                    title = page['title']; content = page['revisions'][0]['slots']['main']['*']
                    primary = title == row['surface'] or w.article_primary_name(content, row['surface'])
                    alias = any(w.same_name(m[2].strip(), row['surface']) for m in re.finditer(r'\|\s*(別名|芸名|名義|通称|名前)\s*=\s*([^\n|}]+)', content))
                    target = page.get('pageprops', {}).get('wikibase_item', title) if primary or alias else title + '#mentioned-name:' + row['surface']
                    if value.get('sourceProjection')=='Literal XML page fields from official Wikipedia dump':
                        import source_rounds
                        target,binding=source_rounds.binding_target(title,content,row['surface'])
                        for name,y,quote in source_rounds.full_body_reading_bindings(content):
                            if w.same_name(name,row['surface']) and w.reading(y)==w.reading(row['reading']):
                                e.fact(row['reading'],row['surface'],'reading',[],target,doc['id'],
                                       {'source':'explicit-name-reading','name':name,'reading':y,'quotation':quote,'binding':binding,'revision':page['revisions'][0]['revid']})
                    w.extract_readings(db, e, row, doc['id'], content, target, canonical_name=row['surface'] if primary else title)
            else:
                w.extract_readings(db, e, row, doc['id'], w.decode_official_page(data), raw['target'])
            processed += 1
        except Exception as ex:
            mark_error(db, row['id'], ex)
    w.info(db, 'onlineReadingsNeedReparse', False)
    w.info(db, 'savedReadingReparse', {'documentsForCandidates': processed, 'modelsCalled': 0, 'networkRequests': 0})
    db.commit()


def reading_discoveries(db, baseline):
    rows = baseline.get('cases', baseline.get('readings'))
    if not isinstance(rows, list):
        return None
    ids = {r['id'] for r in rows}
    frozen = {r[0] for r in db.execute('SELECT candidate_id FROM pilot')}
    if ids != frozen:
        return None
    # Avoid fact_rows() per candidate here: it joins every matching document
    # and returns potentially large evidence bodies just to count readings.
    # Stage the immutable pilot IDs and normalize candidate pairs once, then
    # use the fact_pair index for the existence check.
    missing_ids = [item['id'] for item in rows if not item['readingEvidenceIds']]
    db.execute('CREATE TEMP TABLE IF NOT EXISTS reading_discovery_ids(id TEXT PRIMARY KEY)')
    db.execute('DELETE FROM reading_discovery_ids')
    db.executemany('INSERT INTO reading_discovery_ids VALUES(?)', ((cid,) for cid in missing_ids))
    db.execute('CREATE TEMP TABLE IF NOT EXISTS reading_discovery_pairs(surface TEXT,reading TEXT,PRIMARY KEY(surface,reading))')
    db.execute('DELETE FROM reading_discovery_pairs')
    candidates = db.execute('SELECT c.reading,c.surface FROM candidates c JOIN reading_discovery_ids i ON i.id=c.id').fetchall()
    pairs = {w.pair(row['reading'], row['surface']) for row in candidates}
    db.executemany('INSERT OR IGNORE INTO reading_discovery_pairs VALUES(?,?)', ((surface, reading) for reading, surface in pairs))
    return db.execute("""SELECT COUNT(*) FROM reading_discovery_pairs p
        WHERE EXISTS (SELECT 1 FROM facts f INDEXED BY fact_pair
          WHERE f.surface=p.surface AND (f.reading=p.reading OR f.reading='')
            AND f.active=1 AND f.kind='reading')""").fetchone()[0]


def verify_document(db, document_id):
    doc = db.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
    if doc is None:
        raise ValueError('Missing source document: ' + document_id)
    path = pathlib.Path(doc['path'])
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns, doc['sha256'])
    if key not in _verified:
        if w.sha(path) != doc['sha256']:
            raise ValueError('Source document checksum mismatch: ' + document_id)
        _verified[key] = True
    return doc


_checked_quotes=set()
_wiki_headers={}


def checked_quote(doc,quote):
    if not isinstance(quote,str) or not quote:return False
    key=(doc['path'],doc['sha256']);proof=(*key,w.digest(quote))
    if proof in _checked_quotes:return True
    if key not in _texts:_texts[key]=w.source_text(doc['path'])
    if quote not in _texts[key]:return False
    _checked_quotes.add(proof);return True


def fact_citation(db, fact, previous=()):
    """Use a literal entry/claim quotation, with shared verified document text."""
    doc=verify_document(db,fact['document_id']);body=json.loads(fact['body'])
    quote=next((c['quotation'] for c in previous if c['evidenceId']==fact['id']),body.get('quotation'))
    key=(doc['path'],doc['sha256'])
    if key not in _texts:_texts[key]=w.source_text(doc['path'])
    text=_texts[key]
    if body.get('quotation') and checked_quote(doc,body['quotation']):quote=body['quotation']
    if body.get('source')=='attested-canonical-kana' and w.pair(fact['reading'],fact['surface'])==w.pair(body.get('name',''),body.get('name','')):
        if key not in _wiki_headers:
            try:
                pages=json.loads(text.partition('\n')[0]).get('query',{}).get('pages',{})
                _wiki_headers[key]={p.get('pageid'):(p.get('title'),str(p.get('revisions',[{}])[0].get('revid'))) for p in pages.values() if p.get('revisions')}
            except (ValueError,AttributeError,TypeError):_wiki_headers[key]={}
        page_id=body.get('acquisition',{}).get('sourcePageId',body.get('pageId'))
        header=_wiki_headers[key].get(page_id)
        if header and w.same_name(header[0],body['name']) and header[1]==str(body.get('revision')):
            for fragment in ('"title":'+w.canonical(header[0]),'"title": '+w.canonical(header[0])):
                if checked_quote(doc,fragment):quote=fragment;break
    if not quote:
        entry=str(body.get('entryId','')).split(':')[0]
        at=text.find('<ent_seq>'+entry+'</ent_seq>') if entry else -1
        begin=text.rfind('<entry>',0,at) if at>=0 else -1
        end=text.find('</entry>',at) if begin>=0 else -1
        if end>=0:quote=text[begin:end+8]
        elif body.get('source') in ('JMdict','JMnedict'):
            raise ValueError('Literal dictionary entry quotation missing: '+fact['id'])
        else:quote=text.split('\n',1)[0]
    if not checked_quote(doc,quote):raise ValueError('Fact quotation absent from document: '+fact['id'])
    return {'evidenceId':fact['id'],'documentId':doc['id'],'sha256':doc['sha256'],'quotation':quote}


def verify_fact(db, fact, seen=None):
    seen = set() if seen is None else seen
    if fact['id'] in seen:
        raise ValueError('Cyclic proof dependency: ' + fact['id'])
    ancestors = seen | {fact['id']}
    verify_document(db, fact['document_id'])
    body = json.loads(fact['body'])
    dependencies = body.get('componentFacts', []) + [body[k] for k in
                    ('fullAddressEvidence','outputEvidence','prefixEvidence','addressFact','sourceEvidence') if k in body]
    for fid in dependencies:
        dependency = db.execute('SELECT * FROM facts WHERE id=? AND active=1', (fid,)).fetchone()
        if dependency is None:
            raise ValueError('Missing/inactive proof dependency: ' + fid)
        verify_fact(db, dependency, ancestors)


def expand_retired_dependencies(db):
    # A boundary/exclusion proof loses validity with its underlying source facts,
    # including the full address, independently read component, and optional prefix.
    while True:
        count = db.execute("INSERT OR IGNORE INTO retired_facts SELECT f.id FROM facts f CROSS JOIN json_each(f.body) j CROSS JOIN retired_facts r ON r.id=j.value WHERE f.active=1 AND j.key IN ('fullAddressEvidence','outputEvidence','prefixEvidence','addressFact','sourceEvidence')").rowcount
        count += db.execute("INSERT OR IGNORE INTO retired_facts SELECT f.id FROM facts f CROSS JOIN json_each(f.body,'$.componentFacts') j CROSS JOIN retired_facts r ON r.id=j.value WHERE f.active=1").rowcount
        if not count:
            return


def retire_provider(db, source, filename=None):
    """Replaced reference rows cannot leave decisions pointing at retired facts."""
    where = "f.active=1 AND json_extract(f.body,'$.source')=?"
    params = [source]
    if filename is not None:
        where += ' AND d.url LIKE ?'
        params.append('%/' + filename)
    db.execute('CREATE TEMP TABLE IF NOT EXISTS retired_facts(id TEXT PRIMARY KEY)')
    db.execute('DELETE FROM retired_facts')
    db.execute('INSERT INTO retired_facts SELECT f.id FROM facts f JOIN documents d ON d.id=f.document_id WHERE ' + where, params)
    expand_retired_dependencies(db)
    apply_fact_retirement(db, 'reference-provider-replaced')


def apply_fact_retirement(db, change):
    db.execute('CREATE TEMP TABLE IF NOT EXISTS retired_pairs(candidate_id TEXT PRIMARY KEY)')
    db.execute('DELETE FROM retired_pairs')
    db.execute("INSERT OR IGNORE INTO retired_pairs SELECT c.id FROM retired_facts r JOIN facts f ON f.id=r.id JOIN candidates c ON c.surface=f.surface AND (f.reading='' OR f.reading=c.reading)")
    db.execute("INSERT INTO decision_history(candidate_id,state,reason,decision,change,created) SELECT id,state,reason,decision,?,? FROM candidates WHERE id IN (SELECT candidate_id FROM retired_pairs) AND decision IS NOT NULL", (change, time.time()))
    db.execute("UPDATE candidates SET state=CASE WHEN error IS NOT NULL AND state IN ('blocked','error') THEN state ELSE 'queued' END,decision=NULL,reason=? WHERE id IN (SELECT candidate_id FROM retired_pairs)", (change,))
    db.execute('UPDATE facts SET active=0 WHERE id IN (SELECT id FROM retired_facts)')
    db.execute("DELETE FROM info WHERE key IN ('finalized','acceptance')")


def repair_derived_proofs(db, args):
    """Upgrade legacy boundaries without resetting unrelated rows or fetching pages."""
    db.execute('CREATE TEMP TABLE IF NOT EXISTS retired_facts(id TEXT PRIMARY KEY)')
    db.execute('DELETE FROM retired_facts')
    db.execute("INSERT OR IGNORE INTO retired_facts SELECT f.id FROM facts f CROSS JOIN json_tree(f.body) j LEFT JOIN facts r ON r.id=j.value WHERE f.active=1 AND f.kind IN ('normalization','invalid') AND (j.key IN ('fullAddressEvidence','outputEvidence','prefixEvidence','addressFact','sourceEvidence') OR (j.path='$.componentFacts' AND j.type='text')) AND (r.id IS NULL OR r.active=0)")
    if not db.execute('SELECT COUNT(*) FROM retired_facts').fetchone()[0]:
        return
    expand_retired_dependencies(db)
    count = db.execute('SELECT COUNT(*) FROM retired_facts').fetchone()[0]
    apply_fact_retirement(db, 'legacy-proof-dependency-retired')
    import bulk, rescue
    e = w.Evidence(db, args)
    rescue.apply(db, args, e, w.insert_candidate, w.info, w.emit)
    bulk.normalization(db, e, w.fact_rows, w.canonical, w.info, w.emit)
    w.info(db, 'derivedProofRepair', {'retiredFacts': count, 'modelsCalled': 0, 'networkRequests': 0})
    db.commit()


def fingerprint(db, row, facts=None):
    facts = w.fact_rows(db, row) if facts is None else facts
    origins = [list(r) for r in db.execute('SELECT o.source,o.line,o.reading,o.surface FROM origins o JOIN origin_candidates m ON m.origin_id=o.id WHERE m.candidate_id=? ORDER BY o.source,o.line', (row['id'],))]
    return w.digest(w.canonical({'candidate': [row[k] for k in ('id', 'reading', 'surface', 'normalization')],
                                  'origins': origins, 'facts': facts}))


def normalization_ids(row, facts):
    return [f['id'] for f in facts if f['kind'] == 'normalization' and f['target'] == row['id']]


def write_decision(db, row, state, reason, decision):
    if row.get('decision') and (row['decision'] != w.canonical(decision) or row['state'] != state):
        db.execute('INSERT INTO decision_history(candidate_id,state,reason,decision,change,created) VALUES(?,?,?,?,?,?)',
                   (row['id'], row['state'], row['reason'], row['decision'], 'source-decision-replaced', time.time()))
    if state == 'needs_review' and row.get('error'):
        # An unresolved retrieval/parse failure survives an inconclusive inspection.
        failure_state = row['state'] if row['state'] in ('blocked', 'error') else ('blocked' if row['error_count'] >= MAX_ATTEMPTS else 'error')
        db.execute('UPDATE candidates SET state=?,decision=?,reason=? WHERE id=?', (failure_state, w.canonical(decision), reason, row['id']))
        return
    db.execute('UPDATE candidates SET state=?,reason=?,decision=?,error=NULL,next_retry=0 WHERE id=?',
               (state, reason, w.canonical(decision), row['id']))
    db.execute("DELETE FROM info WHERE key IN ('finalized','acceptance')")


def resolve(db, row):
    facts = w.fact_rows(db, row)
    reads = [f for f in facts if f['kind'] == 'reading']
    norms = normalization_ids(row, facts)
    invalid = [f for f in facts if f['kind'] == 'invalid' and f['target'] == row['id']]
    roles = []
    for f in facts:
        body = json.loads(f['body'])
        categories = set(json.loads(f['categories']))
        if f['kind'] == 'context':
            for category in ('person', 'character'):
                if w.direct_category_fact(f, category, row['normalization']):
                    categories.add(category)
        if f['kind']=='meaning' and json.loads(f['body']).get('source')=='JMnedict':
            for category in ('place','character'):
                if w.direct_category_fact(f, category, row['normalization']):
                    categories.add(category)
        for category in categories:
            if w.direct_category_fact(f, category, row['normalization']):
                role = {'category': category, 'target': f['target'],
                        'sense': str(body.get('sense', body.get('entryId', body.get('row', '')))) + ':' + category,
                        'evidenceIds': [f['id']], 'method': 'direct'}
                if w.target_supported(role, facts):
                    roles.append(role)
    roles = list({(r['category'], r['target'], r['sense']): r for r in roles}.values())
    changed = row['normalization'] != 'unchanged' and not row['normalization'].startswith('original:')
    decision = {'readingEvidence': [f['id'] for f in reads], 'roles': roles,
                'classificationRoute': 'direct', 'normalizationVerified': not changed or bool(norms),
                'normalizationEvidence': norms, 'researchRounds': row['research_round'],
                'missing': [], 'ruleVersion': RULE_VERSION, 'evidenceSha256': fingerprint(db, row, facts)}
    if invalid:
        for f in invalid:
            verify_fact(db, f)
        decision['exclusionEvidence'] = [f['id'] for f in invalid]
        write_decision(db, row, 'excluded_confirmed', 'source-confirmed-invalid-structure', decision)
        return True
    if reads and roles and (not changed or norms):
        used = set(decision['readingEvidence'] + norms + [i for r in roles for i in r['evidenceIds']])
        for f in facts:
            if f['id'] in used:
                verify_fact(db, f)
        write_decision(db, row, 'reviewed', 'source-verified-awaiting-independent-validation', decision)
        return True
    decision['missing'] = (["reading-evidence-insufficient"] if not reads else []) + (["meaning-or-target-unresolved"] if not roles else []) + (["normalization-evidence-insufficient"] if changed and not norms else [])
    write_decision(db, row, 'needs_review', ';'.join(decision['missing']), decision)
    return False


def mark_error(db, cid, ex):
    row = db.execute('SELECT error_count FROM candidates WHERE id=?', (cid,)).fetchone()
    count = row[0] + 1
    transient = isinstance(ex, (TimeoutError, ConnectionError, OSError)) and not isinstance(ex, (FileNotFoundError, PermissionError))
    if isinstance(ex, urllib.error.HTTPError):
        transient = ex.code in (408, 429, 500, 502, 503, 504)
    if w.capacity_failure(ex):
        transient = False
    state = 'error' if transient and count < MAX_ATTEMPTS else 'blocked'
    delay = min(3600, 30 * 2 ** (count - 1)) if state == 'error' else 0
    db.execute('UPDATE candidates SET state=?,error=?,error_count=?,next_retry=? WHERE id=?',
               (state, str(ex), count, time.time() + delay if delay else 0, cid))
    return state


def source_query(pilot):
    # Starting with the tiny frozen cohort avoids scanning a million queued rows.
    return 'pilot p CROSS JOIN candidates c ON c.id=p.candidate_id' if pilot else 'candidates c'


def run(db, args, pilot=False):
    if not w.info(db, 'prepared') or not w.info(db, 'bulkComplete'):
        raise ValueError('Prepare all inputs and complete mandatory bulk source verification first')
    if pilot:
        w.select_pilot(db, args.pilot_size)
    batch = args.batch_size or 100
    online = getattr(args, 'online', False)
    total = batches = 0
    started = time.monotonic()
    # One pass per command. Retried/unchanged exceptions cannot re-enter this pass.
    cursor = ''
    while True:
        conditions = "(c.state IN ('queued','ready_review','blocked') OR (c.state='error' AND (?=0 OR c.next_retry<=?))"
        if online:
            conditions += " OR (c.state='needs_review' AND c.research_round<2)"
        conditions += ')'
        rows = [dict(r) for r in db.execute('SELECT c.* FROM ' + source_query(pilot) +
                ' WHERE c.id>? AND ' + conditions + ' ORDER BY c.id LIMIT ?', (cursor, int(online), time.time(), batch))]
        if not rows:
            break
        for row in rows:
            cursor = row['id']
            try:
                resolved = resolve(db, row)
                if not resolved and row['state'] in ('blocked','error'):
                    state = 'blocked' if row['error_count'] >= MAX_ATTEMPTS or row['state'] == 'blocked' else 'error'
                    db.execute('UPDATE candidates SET state=?,error=?,error_count=?,next_retry=? WHERE id=?',
                               (state, row['error'], row['error_count'], row['next_retry'], row['id']))
                if not resolved and online and row['state'] != 'blocked' and row['error_count'] < MAX_ATTEMPTS:
                    proposal = {'searchTerms': [row['surface'] + ' 読み']}
                    for round_no in range(row['research_round'] + 1, 3):
                        w.research(db, args, row, proposal, round_no)
                        db.execute('UPDATE candidates SET error=NULL,error_count=0,next_retry=0 WHERE id=?', (row['id'],))
                        row = dict(db.execute('SELECT * FROM candidates WHERE id=?', (row['id'],)).fetchone())
                        import bulk
                        bulk.check_normalization_row(db, w.Evidence(db, args), row, w.fact_rows)
                        if resolve(db, row):
                            break
                total += 1
            except Exception as ex:
                state = mark_error(db, row['id'], ex)
                w.emit({'phase': 'source-error', 'candidateId': row['id'], 'state': state, 'error': str(ex)})
                if w.capacity_failure(ex):
                    db.commit()
                    raise
        batches += 1
        db.commit()
        w.emit({'phase': 'direct-review', 'processedThisRun': total, 'batches': batches,
                'seconds': round(time.monotonic() - started, 2)})
        if args.max_batches and batches >= args.max_batches:
            break
    states = dict(db.execute('SELECT c.state,COUNT(*) FROM ' + source_query(pilot) + ' GROUP BY c.state'))
    pending = sum(n for state, n in states.items() if state not in ('reviewed', *w.TERMINAL))
    w.info(db, 'lastRun', {'seconds': time.monotonic() - started, 'processed': total, 'pilot': pilot,
                         'modelsCalled': 0, 'states': states, 'unfinished': pending})
    db.commit()
    return 3 if pending else 0


def complete_source_search(db, args):
    started = time.time()
    db.execute('CREATE TABLE IF NOT EXISTS execution_runs(id INTEGER PRIMARY KEY,action TEXT,configuration_sha256 TEXT,started REAL,ended REAL,state TEXT,error TEXT)')
    db.execute("UPDATE execution_runs SET ended=?,state='interrupted' WHERE ended IS NULL", (started,))
    rid = db.execute('INSERT INTO execution_runs(action,configuration_sha256,started,state) VALUES(?,?,?,?)',
                     ('complete-source-search', w.digest(w.canonical(w.configuration(args)[-1])), started, 'running')).lastrowid
    db.commit()
    error = None
    try:
        return _complete_source_search(db, args)
    except BaseException as ex:
        error = str(ex)
        raise
    finally:
        ended = time.time()
        remaining = dict(db.execute('SELECT state,COUNT(*) FROM candidates GROUP BY state'))
        pending = sum(count for state, count in remaining.items()
                      if state not in ('reviewed','adopted','excluded_confirmed','not_distributed'))
        state = 'failed' if error is not None else ('paused' if pending else 'review-finished')
        db.execute('UPDATE execution_runs SET ended=?,state=?,error=? WHERE id=?', (ended, state, error, rid))
        report = w.info(db, 'completedSourceSearchDisposition') or {}
        w.info(db, 'lastRun', {'seconds': round(ended-started, 2), 'processed': report.get('rechecked', 0),
                               'pilot': False, 'modelsCalled': 0, 'sourceSearchRounds': 2,
                               'newlyNonDistributed': report.get('newlyNonDistributed', 0),
                               'states': remaining, 'unfinished': pending})
        db.commit()


def _complete_source_search(db, args):
    """Close unresolved candidates after a checksum-verified, full-cohort search."""
    import source_rounds
    path = pathlib.Path(args.source_staging)
    source = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    source.row_factory = sqlite3.Row
    try:
        record = source.execute("SELECT value FROM meta WHERE key='source'").fetchone()
        metadata = json.loads(record['value']) if record else None
    finally:
        source.close()
    if not metadata or metadata.get('complete') is not True:
        raise ValueError('Source search staging is not complete')
    proof = metadata.get('completedSearchProof')
    if not proof or metadata.get('sha256') != proof.get('corpusSha256'):
        raise ValueError('Source search checksum/proof is missing')
    key = 'wikiDump:' + metadata['sha256'] + ':2'
    receipt = w.info(db, key)
    if not receipt or receipt.get('complete') is not True:
        raise ValueError('Full source search has not been imported into the ledger')
    imported = receipt.get('source', {})
    if (imported.get('sha256') != metadata['sha256'] or
            imported.get('completedSearchProof') != proof):
        raise ValueError('Imported source search receipt does not match staging')
    queued = db.execute("SELECT COUNT(*) FROM candidates WHERE state IN ('queued','ready_review')").fetchone()[0]
    if queued:
        raise ValueError('Run the direct resolver before completing source review')
    proof_result = source_rounds.record_completed_rounds(db, proof)
    proof_sha = w.digest(w.canonical(proof))
    changed = checked = 0
    cursor = ''
    while True:
        rows = db.execute("""SELECT * FROM candidates
            WHERE state='needs_review' AND research_round>=2 AND error IS NULL AND id>?
            ORDER BY id LIMIT 5000""", (cursor,)).fetchall()
        if not rows:
            break
        for raw in rows:
            row = dict(raw); cursor = row['id']; previous_reason = row.get('reason') or ''
            previous = json.loads(row['decision']) if row.get('decision') else {}
            if resolve(db, row):
                checked += 1
                continue
            current = dict(db.execute('SELECT * FROM candidates WHERE id=?', (row['id'],)).fetchone())
            decision = json.loads(current['decision']) if current.get('decision') else {}
            held = {key: previous[key] for key in ('roles','inspectionEvidence','citations','evidenceSha256') if previous.get(key)}
            if held:
                decision['heldReview'] = {'reason': previous_reason, **held}
            decision.update({'researchRounds': 2,
                             'nonDistributionBasis': 'No direct reading/category proof after two complete full-corpus searches; inference-only category proposals remain withheld pending their precision gate.',
                             'sourceSearchProofSha256': proof_sha})
            missing = ';'.join(decision.get('missing', [])) or 'direct-reading-or-category-proof-insufficient'
            reason = 'not-distributed-after-two-complete-source-searches:' + missing
            if previous_reason and previous_reason not in reason:
                reason += '; prior review reason: ' + previous_reason
            write_decision(db, current, 'not_distributed', reason, decision)
            changed += 1; checked += 1
        db.commit()
        if checked and checked % 50000 < len(rows):
            w.emit({'phase':'complete-source-search','checked':checked,'newlyNonDistributed':changed})
    db.execute("DELETE FROM info WHERE key IN ('finalized','acceptance')")
    remaining = dict(db.execute('SELECT state,COUNT(*) FROM candidates GROUP BY state'))
    result = {'sourceSearchProofSha256': proof_sha, 'sourceSearchRounds': 2,
              'sourceSearchCandidates': proof_result['candidates'],
              'rechecked': checked, 'newlyNonDistributed': changed, 'remainingStates': remaining,
              'modelsCalled': 0, 'networkRequests': 0}
    w.info(db, 'completedSourceSearchDisposition', result)
    db.commit()
    w.emit(result)
    return 3 if any(remaining.get(state, 0) for state in ('queued','ready_review','needs_review','blocked','error')) else 0


def export_reviews(db, args):
    limit = args.batch_size or 100
    if not 1 <= limit <= 100:
        raise ValueError('review-export batch-size must be 1..100')
    where = "c.state IN ('needs_review','blocked','error')"
    params = []
    if args.id:
        where = 'c.id=?'; params = [args.id]
    elif args.surface:
        where = 'c.surface=?'; params = [args.surface]
    if getattr(args, 'reason', None):
        where += ' AND c.reason=?'; params.append(args.reason)
    if getattr(args, 'after_id', None):
        where += ' AND c.id>?'; params.append(args.after_id)
    cases = []
    for raw in db.execute('SELECT c.* FROM candidates c WHERE ' + where + ' ORDER BY c.id LIMIT ?', (*params, limit)):
        row = dict(raw); facts = w.fact_rows(db, row)
        previous = json.loads(row['decision']) if row['decision'] else {}
        cases.append({'candidateId': row['id'], 'reading': row['reading'], 'surface': row['surface'],
                      'evidenceSha256': fingerprint(db, row, facts), 'state': 'needs_review',
                      'readingEvidence': previous.get('readingEvidence', []), 'roles': previous.get('roles', []),
                      'normalizationEvidence': previous.get('normalizationEvidence', normalization_ids(row, facts)),
                      'exclusionEvidence': previous.get('exclusionEvidence', []),
                      'inspectionEvidence': previous.get('inspectionEvidence', []),
                      'reason': row['reason'] or 'source-review-required', 'citations': previous.get('citations', []),
                      'sourceFacts': [],
                      'researchRounds': row['research_round'], 'error': row['error'], 'facts': facts,
                      'origins': [dict(o) for o in db.execute('SELECT o.* FROM origins o JOIN origin_candidates m ON m.origin_id=o.id WHERE m.candidate_id=?', (row['id'],))]})
    value = {'schemaVersion': 1, 'cases': cases}
    dest = pathlib.Path(args.output or 'build/research/review-batch.json')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    w.emit({'reviewBatch': str(dest), 'cases': len(cases), 'sha256': w.sha(dest),
            'nextAfterId': cases[-1]['candidateId'] if cases else None})


def import_reviews(db, args):
    path = pathlib.Path(args.input)
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or set(value) != {'schemaVersion', 'cases'} or value['schemaVersion'] != 1 or not isinstance(value['cases'], list) or not 1 <= len(value['cases']) <= 100:
        raise ValueError('Review file needs schemaVersion 1 and 1..100 cases')
    required = {'candidateId','evidenceSha256','state','readingEvidence','roles','normalizationEvidence','exclusionEvidence','reason','citations'}
    allowed = required | {'sourceFacts', 'inspectionEvidence'}
    export_fields = {'reading','surface','researchRounds','error','facts','origins'}
    seen = set(); validated = []
    cfg = w.configuration(args); categories = {c['id'] for c in cfg[1]['categories']}
    for case in value['cases']:
        if not isinstance(case, dict) or not required <= set(case) or set(case) - allowed - export_fields:
            raise ValueError('Invalid source-review fields')
        cid = case['candidateId']
        row = db.execute('SELECT * FROM candidates WHERE id=?', (cid,)).fetchone()
        if row is None or cid in seen:
            raise ValueError('Unknown/duplicate source-review candidate')
        seen.add(cid); row = dict(row); facts = w.fact_rows(db, row); byid = {f['id']: f for f in facts}
        if case['evidenceSha256'] != fingerprint(db, row, facts):
            raise ValueError('Stale source-review evidence: ' + cid)
        source_facts = validate_source_facts(db, row, case.get('sourceFacts', []))
        for f in source_facts:
            if f['id'] in byid:
                raise ValueError('Source fact already exists in the review evidence set')
            byid[f['id']] = f
        facts.extend(source_facts)
        state = case['state']
        if state not in ('reviewed','excluded_confirmed','not_distributed','needs_review') or not isinstance(case['reason'], str) or not case['reason'].strip():
            raise ValueError('Invalid source-review state/reason')
        if (row['state'] in ('error','blocked') or row['error']) and state == 'not_distributed':
            raise ValueError('Operational failure cannot become non-distribution')
        if (row['state'] in ('error','blocked') or row['error']) and state == 'needs_review':
            raise ValueError('Inconclusive review cannot clear an operational failure')
        if state == 'not_distributed' and row['research_round'] < 2:
            raise ValueError('Non-distribution needs two completed research rounds')
        references = set()
        for field, kind in [('readingEvidence','reading'),('normalizationEvidence','normalization'),('exclusionEvidence','invalid')]:
            ids = case[field]
            if not isinstance(ids, list) or len(set(ids)) != len(ids):
                raise ValueError('Invalid source-review evidence array')
            for fid in ids:
                if fid not in byid or byid[fid]['kind'] != kind or (kind != 'reading' and byid[fid]['target'] != cid):
                    raise ValueError('Source-review evidence is not bound to candidate')
                references.add(fid)
        inspection_ids = case.get('inspectionEvidence', [])
        if not isinstance(inspection_ids, list) or len(set(inspection_ids)) != len(inspection_ids):
            raise ValueError('Invalid inspected-source evidence array')
        if inspection_ids and state != 'needs_review':
            raise ValueError('Inspection-only evidence cannot complete a source review')
        for fid in inspection_ids:
            if fid not in byid or byid[fid]['kind'] not in ('reading','meaning','context'):
                raise ValueError('Inspected-source evidence is not bound to this candidate')
            references.add(fid)
        if not isinstance(case['roles'], list):
            raise ValueError('Invalid source-review roles')
        role_keys = set()
        for role in case['roles']:
            if set(role) != {'category','target','sense','evidenceIds','method'} or role['category'] not in categories or role['method'] not in ('direct','source_review') or not role['sense'] or not role['evidenceIds']:
                raise ValueError('Invalid source-review role')
            key = (role['category'],role['target'],role['sense'])
            if key in role_keys:
                raise ValueError('Duplicate source-review role')
            role_keys.add(key)
            selected_facts = [f for f in facts if f['kind'] != 'reading' or f['id'] in case['readingEvidence']]
            if not set(role['evidenceIds']) <= set(byid) or not w.target_supported(role, selected_facts):
                raise ValueError('Unbound source-review meaning/target')
            for fid in role['evidenceIds']:
                f = byid[fid]
                if f['kind'] not in ('meaning','context') or f['target'] != role['target']:
                    raise ValueError('Category citation describes another target')
            if role['method'] == 'direct' and not any(w.direct_category_fact(byid[fid], role['category'], row['normalization']) for fid in role['evidenceIds']):
                raise ValueError('Inferred classification cannot claim direct provenance')
            references.update(role['evidenceIds'])
        cited = set()
        if not isinstance(case['citations'], list):
            raise ValueError('Invalid citations')
        for cite in case['citations']:
            if set(cite) != {'evidenceId','documentId','sha256','quotation'} or cite['evidenceId'] not in references:
                raise ValueError('Invalid or unused source-review citation')
            f = byid[cite['evidenceId']]
            if f['id'] not in {v['id'] for v in source_facts}:
                verify_fact(db, f)
            doc = verify_document(db, cite['documentId'])
            if f['document_id'] != doc['id'] or cite['sha256'] != doc['sha256']:
                raise ValueError('Source-review document hash/binding mismatch')
            text_key = (doc['path'], doc['sha256'])
            if text_key not in _texts:
                _texts[text_key] = w.source_text(doc['path'])
            if not checked_quote(doc,cite['quotation']):
                raise ValueError('Source-review quotation absent from document')
            cited.add(cite['evidenceId'])
        if references - cited:
            raise ValueError('Every selected fact needs a checked source quotation')
        changed = row['normalization'] != 'unchanged' and not row['normalization'].startswith('original:')
        if state == 'reviewed' and (not case['readingEvidence'] or not case['roles'] or (changed and not case['normalizationEvidence'])):
            raise ValueError('Adoption requires independent reading, meaning and transformation proofs')
        if state == 'excluded_confirmed' and not case['exclusionEvidence']:
            raise ValueError('Confirmed exclusion needs independent invalidity proof')
        route = ('direct' if all(r['method'] == 'direct' for r in case['roles']) else 'source_review') if case['roles'] else None
        decision = {'readingEvidence': case['readingEvidence'], 'roles': case['roles'],
                    'inspectionEvidence': inspection_ids, 'classificationRoute': route,
                    'normalizationEvidence': case['normalizationEvidence'], 'normalizationVerified': not changed or bool(case['normalizationEvidence']),
                    'exclusionEvidence': case['exclusionEvidence'], 'researchRounds': row['research_round'],
                    'citations': case['citations'], 'evidenceSha256': case['evidenceSha256'], 'reviewFileSha256': w.sha(path)}
        validated.append((row, state, case['reason'], decision))
    # No partial import if one of the 100 records is stale or malformed.
    evidence = w.Evidence(db, args)
    for case in value['cases']:
        row = dict(db.execute('SELECT * FROM candidates WHERE id=?', (case['candidateId'],)).fetchone())
        for source_fact in validate_source_facts(db, row, case.get('sourceFacts', [])):
            evidence.fact(row['reading'], row['surface'], source_fact['kind'], [], source_fact['target'],
                          source_fact['document_id'], json.loads(source_fact['body']))
    for row, state, reason, decision in validated:
        decision['evidenceSha256'] = fingerprint(db, row, w.fact_rows(db, row))
        write_decision(db, row, state, reason, decision)
    w.emit({'importedReviews': len(validated),
            'sourceFacts': sum(len(case.get('sourceFacts', [])) for case in value['cases']),
            'reviewFileSha256': w.sha(path)})


def validate_source_facts(db, row, source_facts):
    """Validate narrowly scoped facts added from an already saved Japanese Wikipedia page."""
    if not isinstance(source_facts, list):
        raise ValueError('Invalid source facts')
    result = []; seen = set()
    fields = {'target','documentId','sha256','source','title','pageId','revision','quotation'}
    for item in source_facts:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError('Invalid source fact fields')
        if item['source'] != 'Wikipedia' or not isinstance(item['target'], str) or not item['target']:
            raise ValueError('Unsupported source fact')
        if not isinstance(item['title'], str) or not item['title'] or type(item['pageId']) is not int or type(item['revision']) is not int:
            raise ValueError('Invalid Wikipedia source identity')
        if not isinstance(item['quotation'], str) or not item['quotation']:
            raise ValueError('Wikipedia quotation does not identify the candidate surface')
        compact = lambda text: re.sub(r'(?<=[\u3040-\u30ff\u3400-\u9fff々]) +(?=[\u3040-\u30ff\u3400-\u9fff々])', '',
                                      w.unicodedata.normalize('NFKC', text))
        if compact(row['surface']) not in compact(item['quotation']):
            raise ValueError('Wikipedia quotation does not identify the candidate surface')
        if item['target'] != item['title'] + '#mentioned-name:' + row['surface']:
            raise ValueError('Wikipedia mentioned-name target does not match the candidate')
        doc = verify_document(db, item['documentId'])
        if item['sha256'] != doc['sha256']:
            raise ValueError('Wikipedia source fact checksum mismatch')
        parsed = w.urllib.parse.urlparse(doc['url'])
        if parsed.scheme != 'https' or parsed.hostname != 'dumps.wikimedia.org' or not parsed.path.startswith('/jawiki/'):
            raise ValueError('Wikipedia source fact must use the saved Japanese source dump')
        source_summary = w.source_text(doc['path']).partition('\n')[0]
        source = json.loads(source_summary)
        if not isinstance(source, dict):
            raise ValueError('Invalid saved Wikipedia page bundle')
        pages = source.get('query', {}).get('pages', {})
        page = next((p for p in pages.values() if p.get('pageid') == item['pageId']), None)
        if page is None or page.get('title') != item['title']:
            raise ValueError('Wikipedia page identity does not match the saved source')
        revisions = page.get('revisions', [])
        revision = next((r for r in revisions if r.get('revid') == item['revision']), None)
        if revision is None:
            raise ValueError('Wikipedia revision does not match the saved source')
        content = revision.get('slots', {}).get('main', {}).get('*', '')
        if item['quotation'] not in content:
            raise ValueError('Wikipedia quotation absent from the identified page revision')
        body = {'source': 'Wikipedia', 'title': item['title'], 'pageId': item['pageId'],
                'revision': item['revision'], 'quotation': item['quotation'],
                'acquisition': {'parserVersion': 1, 'sourceDumpSha256': doc['revision'],
                                'sourcePageId': item['pageId']}}
        normalized = (w.reading(row['reading']), w.unicodedata.normalize('NFKC', row['surface']),
                      'context', '[]', item['target'], item['documentId'], w.canonical(body))
        fid = w.digest(w.canonical(normalized))[:32]
        if fid in seen:
            raise ValueError('Duplicate source fact')
        seen.add(fid)
        result.append({'id': fid, 'reading': row['reading'], 'surface': row['surface'], 'kind': 'context',
                       'categories': '[]', 'target': item['target'], 'document_id': item['documentId'],
                       'body': w.canonical(body), 'active': 1, 'sha256': doc['sha256'], 'url': doc['url'],
                       'revision': doc['revision']})
    return result
    db.commit()
    w.emit({'importedReviews': len(validated), 'sha256': w.sha(path)})
