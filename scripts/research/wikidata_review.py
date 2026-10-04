"""Read-only, source_review-only proposals from pinned literal Wikidata classes.

No old decisions/categories are consumed. Every proposal has a current
name-bound pronunciation, an asserted P31/P279 path, and raw class definitions.
A proposal is not a review/import decision; class documents and fresh evidence
fingerprints must be materialized by the production owner before adoption.
"""
import argparse
import collections
import contextlib
import functools
import json
import pathlib
import re
import sqlite3
import time

import batch_research as b
import worker as w

VERSION = 1
# IDs are semantic anchors only when their current literal English label agrees.
# Missing/changed definitions cannot inherit the historical interpretation.
ROOTS = {}
def roots(category, values, routes=('P31', 'P279')):
    for qid, label in values.items():
        ROOTS[qid] = {'category': category, 'label': label, 'routes': routes}
roots('person', {'Q5':'human','Q101352':'family name','Q202444':'given name','Q12308941':'male given name'}, ('P31',))
roots('place', {'Q655311':'onsen','Q177380':'hot spring','Q2221906':'geographic location','Q486972':'human settlement','Q56061':'administrative territorial entity','Q8502':'mountain','Q4022':'river','Q23442':'island','Q515':'city','Q3957':'town','Q15324':'body of water','Q15284':'municipality','Q1054813':'municipality of Japan'}, ('P31',))
roots('facility', {'Q92026':'Japanese castle','Q41176':'building','Q811979':'built structure','Q11486677':'building','Q13226383':'facility','Q16917':'hospital','Q1248784':'airport','Q5393308':'Buddhist temple','Q845945':'Shinto shrine','Q1254933':'astronomical observatory','Q33506':'museum','Q11315':'shopping center','Q12280':'bridge','Q44377':'tunnel','Q483110':'stadium'})
roots('station', {'Q55488':'railway station','Q12819564':'station','Q548662':'public transport stop','Q2175765':'tram stop','Q953806':'bus stop'})
roots('organization', {'Q43229':'organization','Q3914':'school','Q3918':'university','Q4830453':'business','Q6881511':'enterprise','Q12973014':'sports team'})
roots('organization', {'Q11691':'stock exchange'})
roots('product', {'Q2424752':'product','Q431289':'brand','Q7397':'software','Q9135':'operating system','Q40056':'computer program'}, ('P31',))
roots('work', {'Q43099500':'performing arts production','Q11424':'film','Q5398426':'television series','Q8274':'manga','Q63952888':'anime television series','Q1555508':'radio program','Q7889':'video game','Q571':'book','Q8261':'novel','Q7366':'song','Q482994':'album','Q1344':'opera','Q7725634':'literary work','Q105543609':'musical work/composition','Q134556':'single','Q25379':'play','Q2743':'musical play','Q41298':'magazine','Q1002697':'periodical','Q11032':'newspaper','Q196600':'media franchise','Q47461344':'written work','Q2431196':'audiovisual work','Q179461':'religious text'}, ('P31',))
roots('character', {'Q95074':'character','Q15632617':'fictional human','Q15711870':'animated character','Q178885':'deity','Q60994492':'amatsukami'}, ('P31',))
roots('event', {'Q178561':'battle','Q198':'war','Q13418847':'historical event','Q1656682':'planned event','Q132241':'festival','Q13406554':'sports competition','Q618779':'award','Q1079023':'championship'}, ('P31',))
roots('food', {'Q2095':'food','Q746549':'dish','Q40050':'drink','Q25403900':'food ingredient'})
roots('technical', {'Q11344':'chemical element','Q11173':'chemical compound','Q12136':'disease','Q12140':'medication','Q246672':'mathematical object','Q9143':'programming language','Q235557':'file format','Q8366':'algorithm','Q65943':'theorem','Q37756':'alloy'})
roots('organism', {'Q16521':'taxon','Q7239':'organism','Q4886':'cultivar','Q23038290':'fossil taxon'})
roots('sports', {'Q349':'sport'})
roots('religion', {'Q11499334':'religious doctrine','Q9174':'religion'})
roots('astronomy', {'Q6999':'astronomical object','Q523':'star','Q318':'galaxy','Q3863':'asteroid','Q634':'planet','Q60186':'meteorite'})
roots('transport', {'Q42889':'vehicle','Q11436':'aircraft','Q11446':'ship','Q35872':'boat','Q870':'train','Q11442':'bicycle','Q852190':'shipwreck'})
# Ordinary-word semantics require an independent lexical definition. Broad
# entity/concept/object/activity roots deliberately cannot suggest general.
TAXONOMY = {'person','place','facility','station','organization','product','work','character','event','food','technical','general','organism','sports','religion','astronomy','transport'}
ANATOMY_LABELS = {'anatomical structure','anatomical entity','organ','tissue','bone','human body','organ system','body system'}
SOFTWARE_CONCEPT_LABELS = {'compiler','interpreter','operating system','database management system','character encoding','computer protocol','computer file format'}
MODEL_LABELS = {'automobile model','aircraft model','vehicle model','car model','motorcycle model','bicycle model'}
NOT_SUBJECTS = {'Q4167410','Q4167836','Q13406463'}


def claims(entity, prop):
    for stmt in entity.get('claims', {}).get(prop, []):
        snak = stmt.get('mainsnak', {})
        if stmt.get('rank') == 'deprecated' or snak.get('snaktype', 'value') != 'value':
            continue
        val = snak.get('datavalue', {}).get('value')
        qid = val.get('id') if isinstance(val, dict) else None
        if isinstance(qid, str) and re.fullmatch(r'Q[0-9]+', qid):
            yield qid, stmt


class RawCatalog:
    def __init__(self, path, sha256):
        self.path = pathlib.Path(path).resolve()
        if w.sha(self.path) != sha256:
            raise ValueError('Pinned Wikidata catalog checksum mismatch')
        self.sha256 = sha256
        self.db = sqlite3.connect('file:' + self.path.as_posix() + '?mode=ro', uri=True)
        self.record = functools.lru_cache(maxsize=40000)(self._record)
        self.ancestors = functools.lru_cache(maxsize=30000)(self._ancestors)

    def _record(self, qid):
        row = self.db.execute('SELECT body FROM entities WHERE id=?', (qid,)).fetchone()
        if row is None:
            return None
        raw = row[0]; entity = b.validate_entity(qid, raw)
        if 'missing' in entity:
            return None
        return {'id': entity['id'], 'catalogEntityKey': qid, 'entity': entity, 'raw': raw,
                'sha256': w.digest(raw.encode()), 'label': entity.get('labels', {}).get('en', {}).get('value')}

    def _ancestors(self, qid, max_depth, max_nodes):
        queue = collections.deque([(qid, ())]); visited = set(); paths = {}; limits = []
        while queue:
            node, path = queue.popleft()
            if node in visited:
                continue
            if len(visited) >= max_nodes:
                limits.append('ancestry-node-bound-reached'); break
            visited.add(node); record = self.record(node)
            if record is None:
                limits.append('missing-class-definition:' + node); continue
            paths[node] = path
            links = list(claims(record['entity'], 'P279'))
            if len(path) >= max_depth:
                if any(parent not in visited for parent, _ in links):
                    limits.append('ancestry-depth-bound-reached:' + node)
                continue
            for parent, stmt in sorted(links, key=lambda item: (item[0], w.canonical(item[1]))):
                if parent not in visited:
                    edge = {'from': record['id'], 'property': 'P279', 'to': parent,
                            'sourceKey': node, 'sourceSha256': record['sha256'],
                            'quotation': w.canonical(stmt), 'statementId': stmt.get('id')}
                    queue.append((parent, path + (edge,)))
        return paths, tuple(sorted(set(limits)))

    def close(self):
        self.db.close()


def classify(catalog, subject, *, max_depth=6, max_nodes=512):
    """Return bounded literal paths; unresolved limits cannot manufacture roles."""
    proposals = []; issues = []; visited_labels = set(); asserted = []; raw = subject['entity']
    for prop in ('P31', 'P279'):
        for start, statement in claims(raw, prop):
            initial = {'from': subject['id'], 'property': prop, 'to': start,
                       'sourceKey': subject['catalogEntityKey'], 'sourceSha256': subject['sha256'],
                       'quotation': w.canonical(statement), 'statementId': statement.get('id')}
            paths, limits = catalog.ancestors(start, max_depth, max_nodes)
            issues.extend(limits)
            labels = {catalog.record(node)['label'] for node in paths if catalog.record(node)}
            visited_labels.update(labels)
            start_record = catalog.record(start)
            asserted.append({'property':prop,'id':start,'label':start_record['label'] if start_record else None,
                             'sourceSha256':start_record['sha256'] if start_record else None})
            if start in NOT_SUBJECTS:
                issues.append('not-an-encyclopedic-subject'); continue
            for node, chain in paths.items():
                anchor = ROOTS.get(node); record = catalog.record(node)
                if anchor is None or prop not in anchor['routes']:
                    continue
                if record['label'] != anchor['label']:
                    issues.append('class-definition-missing-or-changed:' + node); continue
                # Product and planned-event ontology roots have nonsemantic
                # descendants (murals, itineraries, voice types, markets).
                # Their presence alone is insufficient: require a literal
                # source class head, never a candidate-name suffix.
                if node=='Q2424752' and start!='Q2424752' and not labels & MODEL_LABELS:
                    issues.append('broad-product-root-without-product-model-class-head'); continue
                if node=='Q1656682' and start!='Q1656682' and not any(v and re.search(r'(?:^| )(?:event|award|festival|ceremony|competition|championship|tournament)$',v) for v in [start_record['label'] if start_record else None]):
                    issues.append('broad-event-root-without-explicit-event-class-head'); continue
                proposals.append({'category':anchor['category'],'method':'source_review','target':subject['id'],
                                  'root':node,'rootDefinition':{'labels':record['entity'].get('labels',{}),'descriptions':record['entity'].get('descriptions',{})},
                                  'initialClass':start,'relation':prop,'path':[initial,*chain],
                                  'definitionSourceKey':node,'definitionSourceSha256':record['sha256']})
            # A generic software class is a technical term only with a precise
            # literal class head. Named programs use their P31 product route.
            direct = catalog.record(start)
            if prop == 'P279' and direct and direct['label'] in SOFTWARE_CONCEPT_LABELS:
                proposals.append({'category':'technical','method':'source_review','target':subject['id'],
                                  'root':start,'rootDefinition':{'labels':direct['entity'].get('labels',{}),'descriptions':direct['entity'].get('descriptions',{})},
                                  'initialClass':start,'relation':prop,'path':[initial],
                                  'definitionSourceKey':start,'definitionSourceSha256':direct['sha256']})
    categories = {p['category'] for p in proposals}; suppressed = []
    def same_assertion(p, q):
        return p['relation']==q['relation'] and p['path'][0]['quotation']==q['path'][0]['quotation']
    def suppress(category, reason):
        nonlocal proposals
        removed = [p for p in proposals if p['category'] == category]
        if removed:
            suppressed.extend({'category':category,'reason':reason,'path':p['path']} for p in removed)
            proposals = [p for p in proposals if p['category'] != category]
    if 'person' in categories and 'character' in categories and any(not same_assertion(p,q) for p in proposals if p['category']=='person' for q in proposals if q['category']=='character'):
        issues.append('contradictory-real-human-and-fictional-or-deity-classes')
        return [], sorted(set(issues)), suppressed, asserted
    if 'character' in categories:
        suppress('person', 'fictional-human-class-is-not-a-real-person')
        suppress('organism', 'fictional-or-mythic-target-is-not-real-organism')
    if 'person' in categories:
        suppress('organism', 'human-name-or-person-scope')
    if visited_labels & ANATOMY_LABELS:
        suppress('organism', 'anatomical-type-is-not-an-organism')
    if visited_labels & MODEL_LABELS:
        suppress('transport', 'explicit-product-model-scope')
    # A more specific class on the same literal asserted path determines the
    # semantic scope. A town can be a built structure in an ontology without
    # becoming a dictionary facility; an opera can be a planned event without
    # introducing a separate event sense. Separate source assertions survive.
    original = list(proposals)
    for p in list(proposals):
        earlier = {edge['to'] for edge in p['path'][:-1]}
        if any(same_assertion(p,q) and q['root'] in earlier and q['category']!=p['category'] for q in original):
            suppressed.append({'category':p['category'],'reason':'more-specific-semantic-anchor-on-same-literal-path','path':p['path']}); proposals.remove(p)
    broad = {'Q2424752','Q43229','Q811979','Q13226383','Q1656682','Q2221906'}
    original = list(proposals)
    for p in list(proposals):
        others = [q for q in original if same_assertion(p,q) and q['category']!=p['category']]
        if p['root'] in broad and others and any(q['root'] not in broad for q in others):
            suppressed.append({'category':p['category'],'reason':'generic-superclass-does-not-create-additional-sense','path':p['path']}); proposals.remove(p)
        elif p['category']=='sports' and any(q['category']=='event' for q in others):
            suppressed.append({'category':p['category'],'reason':'competition-event-is-not-an-additional-sport-sense','path':p['path']}); proposals.remove(p)
    if 'station' in {p['category'] for p in proposals}:
        suppress('place', 'explicit-stop-or-station-scope'); suppress('facility', 'explicit-stop-or-station-scope')
    if {'school','university'} & visited_labels:
        suppress('facility', 'educational-institution-scope-needs-distinct-building-evidence')
    if any(p['root']=='Q9143' for p in proposals):
        suppress('product', 'programming-language-is-a-technical-name')
    for p in list(proposals):
        if p['category']=='work' and p['root'] in {'Q47461344','Q2431196'} and any(q['category']=='product' and q['root'] in {'Q7397','Q9135','Q40056'} and same_assertion(q,p) for q in proposals):
            suppressed.append({'category':'work','reason':'software-product-is-not-an-additional-written-work-sense','path':p['path']}); proposals.remove(p)
    if visited_labels & MODEL_LABELS:
        suppress('transport', 'explicit-product-model-scope')
    else:
        # Commodity is a superclass of foods/books/vehicles. Such ancestry does
        # not introduce an additional merchandise/model sense by itself.
        for p in list(proposals):
            if p['category']=='product' and p['root']=='Q2424752' and any(same_assertion(p,q) and q['category']!='product' for q in proposals):
                suppressed.append({'category':'product','reason':'more-specific-type-on-same-asserted-class-path','path':p['path']}); proposals.remove(p)
    # A node-cap is not complete enough to rule out contradictory/overlapping
    # classes. Depth is a documented bounded strategy, never a negative proof.
    if 'ancestry-node-bound-reached' in issues or 'not-an-encyclopedic-subject' in issues:
        return [], sorted(set(issues)), suppressed, asserted
    result = {}
    for p in proposals:
        category = p['category']
        if category not in result or (len(p['path']),p['root'],w.canonical(p['path'])) < (len(result[category]['path']),result[category]['root'],w.canonical(result[category]['path'])):
            result[category] = p
    return [result[k] for k in sorted(result)], sorted(set(issues)), suppressed, asserted


def named_reading(subject, row):
    return bool(b.strict_matches(subject['entity'], [row]))


def reading_quotation(subject, row):
    matches = b.strict_matches(subject['entity'], [row])
    if not matches:
        raise ValueError('No literal source reading match')
    _, name, _, statement, _ = matches[0]
    if statement is not None:
        return w.canonical(statement)
    entity = subject['entity']; label = entity.get('labels',{}).get('ja',{})
    if label.get('value') == name:
        return w.canonical(label)
    return w.canonical(entity.get('sitelinks',{}).get('jawiki',{}))


def source_package(record, catalog):
    entity = record['entity']
    return {'catalogSha256':catalog.sha256,'catalogEntityKey':record['catalogEntityKey'],
            'entityId':record['id'],'entityRecordSha256':record['sha256'],
            'revision':str(entity['lastrevid']) if entity.get('lastrevid') is not None else 'sha256:'+record['sha256'],
            'revisionKnown':entity.get('lastrevid') is not None,'entityModified':entity.get('modified'),
            'sourceProjection':'Literal selected-field Wikidata dump transcription; not full API JSON',
            'originalUrl':'https://www.wikidata.org/wiki/Special:EntityData/'+record['id']+'.json',
            'raw':record['raw']}


def supplement_class_sources(path,qids):
    """Pin missing anchor definitions from the official API, preserving old sources."""
    import urllib.request
    package=json.loads(pathlib.Path(path).read_text());new_sources={}
    for qid in sorted(set(qids)):
        if qid not in ROOTS:raise ValueError('Class source has no inspected semantic anchor: '+qid)
        anchor=ROOTS[qid]
        if qid in package['sources']:continue
        url='https://www.wikidata.org/wiki/Special:EntityData/'+qid+'.json'
        request=urllib.request.Request(url,headers={'User-Agent':'DictionaryQualitySourceReview/1.0'})
        with urllib.request.urlopen(request,timeout=20) as response:response_bytes=response.read()
        value=json.loads(response_bytes);raw=w.canonical(value['entities'][qid]);entity=b.validate_entity(qid,raw)
        if entity.get('labels',{}).get('en',{}).get('value')!=anchor['label']:
            raise ValueError('New class source label does not match inspected rule: '+qid)
        revision=entity.get('lastrevid')
        if not isinstance(revision,int):raise ValueError('New class source has no revision: '+qid)
        new_sources[qid]={'catalogSha256':None,'catalogEntityKey':qid,'entityId':qid,
            'entityRecordSha256':w.digest(raw),'revision':str(revision),'revisionKnown':True,
            'sourceProjection':'Literal complete entity object from official API response',
            'originalUrl':url,'responseSha256':w.digest(response_bytes),'sourceSnapshot':'official-api',
            'raw':raw}
    package['sources'].update(new_sources);package['rulesSha256']=w.digest(w.canonical(ROOTS))
    pathlib.Path(path).write_text(w.canonical(package)+'\n')
    return {'addedClassDefinitions':sorted(new_sources),'sourcePackageSha256':w.sha(path),'rulesSha256':package['rulesSha256']}


def recommendations(db, catalog, *, max_cases=None, max_depth=6, max_nodes=512):
    """Consume only matching current raw reading/context facts, without writes."""
    query = '''SELECT c.id,c.reading,c.surface,c.normalization,c.state,c.error,
        f.id readingEvidenceId,f.target,f.body readingBody,f.document_id readingDocumentId,
        d.sha256 readingDocumentSha256
        FROM facts f CROSS JOIN candidates c
        JOIN documents d ON d.id=f.document_id
        WHERE f.active=1 AND f.kind='reading' AND f.target GLOB 'Q[0-9]*'
        AND c.surface=f.surface AND c.reading=f.reading
        AND json_extract(f.body,'$.acquisition.catalogSha256')=?
        AND c.state IN ('queued','ready_review','needs_review') AND c.error IS NULL
        '''
    counts = collections.Counter(); grouped = collections.defaultdict(list); inspected = set()
    for fact in db.execute(query, (catalog.sha256,)):
        value = dict(fact); body = json.loads(value.pop('readingBody'))
        acquisition = body.get('acquisition',{})
        if acquisition.get('catalogSha256') != catalog.sha256:
            counts['otherReadingSourcesSkipped'] += 1; continue
        if max_cases is not None and value['id'] not in inspected and len(inspected) >= max_cases:
            continue
        inspected.add(value['id']); value['readingProof']=body; grouped[value['target']].append(value)
    counts['candidateReadingBindingsInspected'] = len(inspected)
    definitions = {}; selected = []; suggestions = collections.defaultdict(set); failures = []
    for target, rows in sorted(grouped.items()):
        subject = catalog.record(target); counts['targetsInspected'] += 1
        if subject is None or subject['id'] != target:
            counts['subjectMissingOrNoncanonical'] += len(rows); continue
        proposals, issues, suppressed, asserted = classify(catalog, subject,max_depth=max_depth,max_nodes=max_nodes)
        counts['subjectWithProposals'] += bool(proposals)
        for row in rows:
            proof = row['readingProof']; acq = proof['acquisition']
            if (acq.get('entityRecordSha256') != subject['sha256'] or row['readingDocumentSha256'] != subject['sha256'] or not named_reading(subject,row)):
                counts['readingRawBindingMismatch'] += 1; failures.append({'candidateId':row['id'],'target':target,'reason':'reading-raw-binding-mismatch'}); continue
            contexts = []
            for context in db.execute("SELECT f.id,f.document_id,f.body,d.sha256 FROM facts f JOIN documents d ON d.id=f.document_id WHERE f.active=1 AND f.surface=? AND (f.reading='' OR f.reading=?) AND f.target=? AND f.kind='context'",(row['surface'],row['reading'],target)):
                body = json.loads(context['body'])
                if (body.get('source')=='Wikidata' and body.get('acquisition',{}).get('catalogSha256')==catalog.sha256 and body.get('acquisition',{}).get('entityRecordSha256')==subject['sha256'] and context['sha256']==subject['sha256']):
                    contexts.append({'evidenceId':context['id'],'documentId':context['document_id'],'sha256':context['sha256']})
            if not contexts:
                counts['matchingRawContextMissing'] += 1; continue
            roles = []
            for proposal in proposals:
                p = dict(proposal); p['sense'] = 'Explicit '+proposal['relation']+' '+proposal['rootDefinition']['labels']['en']['value']+' class path'
                p['evidenceIds'] = sorted(c['evidenceId'] for c in contexts)
                keys = {proposal['definitionSourceKey']} | {edge['sourceKey'] for edge in proposal['path']}
                p['requiredClassSources'] = sorted(key for key in keys if key != subject['catalogEntityKey'])
                for key in keys - {subject['catalogEntityKey']}:
                    definitions[key] = source_package(catalog.record(key),catalog)
                roles.append(p); suggestions[p['category']].add(row['id'])
            case = {'candidateId':row['id'],'reading':row['reading'],'surface':row['surface'],'normalization':row['normalization'],
                    'target':target,'readingEvidence':[row['readingEvidenceId']],
                    'sourceSubjectDefinition':{'labels':subject['entity'].get('labels',{}),'descriptions':subject['entity'].get('descriptions',{})},
                    'readingCitation':{'evidenceId':row['readingEvidenceId'],'documentId':row['readingDocumentId'],'sha256':row['readingDocumentSha256'],
                                       'quotation':reading_quotation(subject,row)},
                    'subjectContextEvidence':contexts,'roles':roles,'issues':issues,'suppressed':suppressed,
                    'assertedSourceClasses':asserted,'sourceSubjectSha256':subject['sha256'],
                    'productionApplied':False,'importReady':False,
                    'remainingRequirements':['Materialize every required raw class source as target-scoped evidence','Recompute current complete evidence fingerprint','Independent source_review inspection and frozen precision gate']}
            selected.append(case)
    # Multiple pronunciations/reading facts for one entity may overlap; keep one
    # literal source reading proof per candidate-target, without mixing targets.
    unique = {(v['candidateId'],v['target']):v for v in selected}
    counts['recommendationCandidateTargets'] = sum(bool(v['roles']) for v in unique.values())
    counts['recommendationCandidates'] = len({v['candidateId'] for v in unique.values() if v['roles']})
    counts['rawDefinitionRecordsRequired'] = len(definitions)
    return list(unique.values()),definitions,dict(counts),{k:len(v) for k,v in sorted(suggestions.items())},failures


def inspection_cases(cases, limit=100):
    chosen = []; seen = set()
    for category in sorted(TAXONOMY):
        n = 0
        for case in cases:
            key = (case['candidateId'],case['target'])
            if key not in seen and any(r['category']==category for r in case['roles']):
                chosen.append(case); seen.add(key); n += 1
            if n >= 5 or len(chosen)>=limit:
                break
        if len(chosen)>=limit:
            break
    for case in sorted(cases,key=lambda v:(not bool(v['issues']),not bool(v['suppressed']),v['candidateId'],v['target'])):
        if len(chosen)>=limit:
            break
        key = (case['candidateId'],case['target'])
        if key not in seen:
            chosen.append(case); seen.add(key)
    return chosen


class SavedClassCatalog(RawCatalog):
    """Reuse the verified literal class sources, with no catalog copy/download."""
    def __init__(self, package):
        self.sha256=package['catalogSha256'];self.sources=package['sources']
        self.record=functools.lru_cache(maxsize=10000)(self._record)
        self.ancestors=functools.lru_cache(maxsize=10000)(self._ancestors)

    def _record(self,qid):
        source=self.sources.get(qid)
        if source is None:return None
        raw=source['raw'];entity=b.validate_entity(qid,raw)
        if w.digest(raw.encode())!=source['entityRecordSha256']:raise ValueError('Changed saved class source: '+qid)
        return dict(id=entity['id'],catalogEntityKey=qid,entity=entity,raw=raw,sha256=source['entityRecordSha256'],
                    label=entity.get('labels',{}).get('en',{}).get('value'))


@functools.lru_cache(maxsize=512)
def literal_wiki_pages(path,sha256):
    import gzip
    data=pathlib.Path(path).read_bytes()
    if w.digest(data)!=sha256:raise ValueError('Changed named-reading source')
    if data.startswith(b'\x1f\x8b'):data=gzip.decompress(data)
    value=json.loads(data);result={}
    for page in value.get('query',{}).get('pages',{}).values():
        for revision in page.get('revisions',[])[:1]:
            content=revision.get('slots',{}).get('main',{}).get('*','')
            result[page.get('pageid')]=(str(revision.get('revid')),page.get('title'),content)
    return result


@functools.lru_cache(maxsize=5000)
def literal_wiki_bindings(path,sha256,page_id,quotation):
    import source_rounds
    page=literal_wiki_pages(path,sha256).get(page_id)
    if page is None:return ()
    revision,title,content=page
    at=content.find(quotation) if quotation else -1
    if at<0:return ()
    # Parse the original characters around this exact printed name/reading.
    # The following text supplies actual closing delimiters and qualifiers;
    # nothing is invented and unrelated article sections cannot supply a match.
    excerpt=content[max(0,at-200):at+len(quotation)+1200]
    return tuple(source_rounds.full_body_reading_bindings(excerpt))


def wikipedia_name_reading(db,row,fact):
    """Require the whole-name reading and the page's native item identity."""
    import direct_review as d
    body=json.loads(fact['body']);acq=body.get('acquisition',{})
    canonical=(body.get('source')=='attested-canonical-kana' and re.fullmatch('[ぁ-ゖァ-ヶー]+',body.get('name',''))
        and w.pair(body['name'],body['name'])==w.pair(row['reading'],row['surface']))
    if (fact['kind']!='reading' or not (body.get('source')=='explicit-name-reading' or canonical)
            or w.pair(row['reading'],body.get('name',''))!=w.pair(row['reading'],row['surface'])
            or not acq.get('sourceDumpSha256') or not acq.get('sourcePageId')):return False
    identities=[]
    for fid in body.get('componentFacts',[]):
        identity=db.execute('SELECT * FROM facts WHERE id=? AND active=1',(fid,)).fetchone()
        if identity is None:continue
        ib=json.loads(identity['body'])
        if (ib.get('source')=='Wikipedia-page-identity' and identity['target']==fact['target']
                and ib.get('qid')==fact['target'] and ib.get('pageId')==acq['sourcePageId']):
            native_tuple=re.fullmatch(r"\((\d+),'wikibase_item','(Q\d+)',(?:NULL|\d+)\)",ib.get('quotation',''))
            if not native_tuple or (int(native_tuple[1]),native_tuple[2])!=(ib['pageId'],ib['qid']):return False
            source=d.verify_document(db,identity['document_id'])
            if source['sha256']!=ib.get('sourceSha256'):raise ValueError('Native page identity checksum mismatch')
            if not source['url'].startswith('https://dumps.wikimedia.org/jawiki/'):return False
            identities.append(ib)
    if not identities:return False
    source=d.verify_document(db,fact['document_id'])
    page=literal_wiki_pages(source['path'],source['sha256']).get(acq['sourcePageId'])
    if page is None:return False
    revision,title,_=page
    if revision!=str(body.get('revision')) or not any(v['title']==title for v in identities):return False
    if ((canonical and w.pair(title,title)==w.pair(row['reading'],row['surface'])) or
            any(w.pair(y,name)==w.pair(row['reading'],row['surface']) for name,y,_ in literal_wiki_bindings(source['path'],source['sha256'],acq['sourcePageId'],body.get('quotation','')))):
        d.verify_fact(db,fact);return True
    return False


def named_definition_override(db,row,facts,target):
    import direct_review as d,wiki_semantics as s
    definitions=[]
    for fact in facts:
        if fact['kind']!='reading' or fact['target']!=target or json.loads(fact['body']).get('source') not in ('explicit-name-reading','attested-canonical-kana'):continue
        if not wikipedia_name_reading(db,row,fact):continue
        source=d.verify_document(db,fact['document_id']);body=json.loads(fact['body'])
        page=literal_wiki_pages(source['path'],source['sha256']).get(body['acquisition']['sourcePageId'])
        if page is None or page[0]!=str(body['revision']):continue
        content=page[2][:24000]
        if not w.article_primary_name(content,row['surface']):continue
        definition=s.subject_definition(content,row['surface'])
        if not definition:continue
        interpretations=s.named_suggest(definition)
        if len({v['category'] for v in interpretations})!=1:continue
        definitions.append({**definition,'interpretations':interpretations,'readingEvidenceId':fact['id'],
            'documentId':source['id'],'sha256':source['sha256']})
    if len({v['interpretations'][0]['category'] for v in definitions})!=1:return None
    return definitions[0] if definitions else None


def saved_named_cases(db,package):
    import direct_review as d
    catalog=SavedClassCatalog(package);seen=set();counts=collections.Counter();started=time.monotonic()
    query="""SELECT c.id,c.reading,c.surface,c.normalization,
        json_extract(c.decision,'$.roles') roles_json,f.id reading_id,f.target item FROM candidates c
        JOIN facts f INDEXED BY fact_pair ON f.surface=c.surface AND f.reading=c.reading
        WHERE c.error IS NULL AND c.state NOT IN ('excluded_confirmed','error','blocked')
          AND f.active=1 AND f.kind='reading' AND f.target GLOB 'Q[0-9]*'
          AND json_extract(f.body,'$.source') IN ('explicit-name-reading','attested-canonical-kana')
          AND json_extract(f.body,'$.acquisition.sourcePageId') IS NOT NULL
          AND (NOT EXISTS (SELECT 1 FROM json_each(c.decision,'$.roles') role
            WHERE json_extract(role.value,'$.target')=f.target)
            OR EXISTS (SELECT 1 FROM json_each(c.decision,'$.roles') role,
              json_each(role.value,'$.evidenceIds') ref JOIN facts proof ON proof.id=ref.value
              WHERE json_extract(role.value,'$.target')=f.target AND json_extract(proof.body,'$.classPaths') IS NOT NULL
                AND json_extract(proof.body,'$.rulesSha256')!=?))"""
    for raw in db.execute(query,(package['rulesSha256'],)):
        row=dict(raw);key=(row['id'],row['item'])
        if key in seen:continue
        counts['sourceNamedPairsScanned']+=1
        if counts['sourceNamedPairsScanned']%2000==0:
            w.emit({'phase':'saved-named-source-progress','counts':dict(counts),'seconds':round(time.monotonic()-started,2)})
        facts=w.fact_rows(db,row);read=next(f for f in facts if f['id']==row['reading_id'])
        if not wikipedia_name_reading(db,row,read):counts['unboundNamedReading']+=1;continue
        seen.add(key)
        contexts=[f for f in facts if f['kind']=='context' and f['target']==row['item'] and
            json.loads(f['body']).get('source')=='Wikidata' and
            json.loads(f['body']).get('acquisition',{}).get('catalogSha256')==catalog.sha256]
        if not contexts:counts['missingPinnedSubject']+=1;continue
        context=contexts[0];doc=d.verify_document(db,context['document_id']);literal=pathlib.Path(doc['path']).read_text()
        entity=b.validate_entity(row['item'],literal);subject=dict(id=entity['id'],entity=entity,raw=literal,
            catalogEntityKey=row['item'],sha256=doc['sha256'])
        proposals,issues,suppressed,asserted=classify(catalog,subject)
        if not proposals:counts['noInspectedClassPath']+=1;continue
        interpretation=named_definition_override(db,row,facts,row['item'])
        category=interpretation['interpretations'][0]['category'] if interpretation else None
        old={'roles':json.loads(row['roles_json'] or '[]')}
        current={(v['category'],v['target']) for v in old.get('roles',[]) if v['target']==row['item'] and any(
            json.loads(f['body']).get('classPaths') for fid in v['evidenceIds'] for f in facts if f['id']==fid)}
        expected={(category or v['category'],v['target']) for v in proposals}
        if expected==current:
            counts['unchangedClassRoles']+=1;continue
        for proposal in proposals:
            proposal['sense']='Explicit '+proposal['relation']+' '+proposal['rootDefinition']['labels']['en']['value']+' class path'
        counts['proposed']+=1
        yield dict(candidateId=row['id'],target=row['item'],readingEvidence=[read['id']],
            readingCitation=d.fact_citation(db,read),readingBasis='native-Wikipedia-name-binding',
            namedDefinition=interpretation,
            subjectContextEvidence=[{'evidenceId':context['id']}],sourceSubjectSha256=doc['sha256'],roles=proposals)
    w.emit({'phase':'saved-named-source-scan','counts':dict(counts)})


def apply_inspected(db, args, cases=None):
    """Apply inspected class rules; keep inference pending the frozen precision gate."""
    import direct_review as d
    if not w.info(db, 'goldFrozen'):
        raise ValueError('Freeze independent source-bound gold before applying class rules')
    package = json.loads(pathlib.Path(args.source_package).read_text())
    if package['rulesSha256'] != w.digest(w.canonical(ROOTS)):
        raise ValueError('Source package belongs to different class rules')
    receipt = w.info(db, 'rawWikidataCatalog:' + package['catalogSha256'] + ':1')
    if not receipt or not receipt.get('complete'):
        raise ValueError('Class review needs the completed pinned source catalog receipt')
    source_sha = w.sha(args.source_package)
    evidence = w.Evidence(db, args); sources = {}; source_facts = {}; subjects = {}
    for key, record in package['sources'].items():
        raw = record['raw']; entity = b.validate_entity(key, raw)
        pinned=record['catalogSha256']==package['catalogSha256']
        supplemental=(record.get('sourceSnapshot')=='official-api' and record.get('catalogSha256') is None
            and record.get('originalUrl')=='https://www.wikidata.org/wiki/Special:EntityData/'+key+'.json'
            and str(entity.get('lastrevid'))==record.get('revision') and record.get('revisionKnown') is True
            and re.fullmatch(r'[a-f0-9]{64}',record.get('responseSha256','')))
        if not (pinned or supplemental) or w.digest(raw.encode()) != record['entityRecordSha256']:
            raise ValueError('Class source checksum mismatch: ' + key)
        sources[key] = (record, entity)
    def class_fact(key):
        if key not in source_facts:
            record, entity = sources[key]
            did = evidence.save(record['originalUrl'], record['revision'], record['raw'].encode(), 'CC0')
            source_facts[key] = evidence.fact('', '', 'context', [], entity['id'], did,
                {'source':'inspected-class-definition', 'id':entity['id'],
                 'labels':entity.get('labels', {}), 'quotation':record['raw']})
        return source_facts[key]
    pending = []; pending_pairs = set(); counts = collections.Counter(); started = time.monotonic()
    review_path = pathlib.Path(getattr(args,'review_path','build/research/current-review.json'))
    def flush():
        if not pending: return
        review_path.write_text(w.canonical({'schemaVersion':1, 'cases':pending}) + '\n')
        original_input = getattr(args, 'input', None); args.input = str(review_path)
        try: d.import_reviews(db, args)
        finally: args.input = original_input
        db.commit(); pending.clear(); pending_pairs.clear()
        w.emit({'phase':'inspected-class-review', 'reviewed':counts['reviewed'],
                'seconds':round(time.monotonic()-started, 2)})
    with contextlib.ExitStack() as stack:
        if cases is None:
            stream=stack.enter_context(pathlib.Path(args.recommendations).open())
            cases=(json.loads(line) for line in stream)
        for case in cases:
            counts['sourceBindingsScanned'] += 1
            row = dict(db.execute('SELECT * FROM candidates WHERE id=?', (case['candidateId'],)).fetchone())
            if (row['surface'],row['reading']) in pending_pairs:
                flush()
                row = dict(db.execute('SELECT * FROM candidates WHERE id=?', (case['candidateId'],)).fetchone())
            if row['state'] in ('excluded_confirmed','error','blocked') or row['error']:
                counts['protected'] += 1; continue
            old = json.loads(row['decision']) if row['decision'] else {}
            facts = w.fact_rows(db, row); by_id = {f['id']:f for f in facts}
            interpretation=named_definition_override(db,row,facts,case['target'])
            explicit_category=interpretation['interpretations'][0]['category'] if interpretation else None
            actual_categories={(explicit_category or r['category'],r['target']) for r in case['roles']}
            previous_class_roles=[r for r in old.get('roles',[]) if r['target']==case['target'] and any(
                json.loads(by_id[fid]['body']).get('classPaths') for fid in r['evidenceIds'] if fid in by_id)]
            if previous_class_roles and {(r['category'],r['target']) for r in previous_class_roles}!=actual_categories:
                old={**old,'roles':[r for r in old.get('roles',[]) if r not in previous_class_roles]}
                counts['reclassifiedTargets']+=1
            known = {(r['category'],r['target']) for r in old.get('roles', [])}
            proposed = [r for r in case['roles'] if (explicit_category or r['category'],r['target']) not in known]
            if not proposed: continue
            norms = d.normalization_ids(row, facts)
            changed = row['normalization']!='unchanged' and not row['normalization'].startswith('original:')
            if changed and not norms: counts['boundaryUnresolved'] += 1; continue
            read_ids = case['readingEvidence']
            if not all(fid in by_id and by_id[fid]['kind']=='reading' and by_id[fid]['target']==case['target'] for fid in read_ids):
                counts['staleReading'] += 1; continue
            context_ids = [x['evidenceId'] for x in case['subjectContextEvidence']]
            if not context_ids or not all(fid in by_id and by_id[fid]['kind']=='context' and by_id[fid]['target']==case['target'] for fid in context_ids):
                counts['staleContext'] += 1; continue
            context = by_id[context_ids[0]]; doc = d.verify_document(db, context['document_id'])
            if doc['sha256'] != case['sourceSubjectSha256']:
                raise ValueError('Subject checksum changed: ' + row['id'])
            if doc['id'] not in subjects:
                raw = pathlib.Path(doc['path']).read_text()
                subjects[doc['id']] = b.validate_entity(case['target'], raw)
            subject = subjects[doc['id']]
            matches = b.strict_matches(subject, [row])
            if not matches and case.get('readingBasis')=='native-Wikipedia-name-binding':
                if any(wikipedia_name_reading(db,row,by_id[fid]) for fid in read_ids):
                    matches=[(row,row['surface'],row['reading'],None,True)]
            if not matches:
                counts['readingNameMismatch'] += 1; continue
            inspected = []; dependencies = set(context_ids)
            for role in proposed:
                root = role['root']; definition = sources.get(role['definitionSourceKey'])
                if definition is None: raise ValueError('Missing literal class definition: ' + root)
                record, entity = definition; anchor = ROOTS.get(root)
                label=entity.get('labels',{}).get('en',{}).get('value')
                software_concept=(role['category']=='technical' and role['relation']=='P279'
                    and root==role['initialClass'] and len(role['path'])==1
                    and label in SOFTWARE_CONCEPT_LABELS)
                if not software_concept and (not anchor or role['relation'] not in anchor['routes'] or role['category']!=anchor['category'] or label!=anchor['label']):
                    counts['uninspectedAnchor'] += 1; continue
                if record['entityRecordSha256']!=role['definitionSourceSha256']:
                    raise ValueError('Class definition changed: ' + root)
                previous = subject['id']
                for n, edge in enumerate(role['path']):
                    src = subject if n==0 else sources[edge['sourceKey']][1]
                    prop = role['relation'] if n==0 else 'P279'
                    edge_sha = doc['sha256'] if n==0 else sources[edge['sourceKey']][0]['entityRecordSha256']
                    if (edge['from']!=previous or src['id']!=previous or edge['property']!=prop
                            or edge['sourceSha256']!=edge_sha
                            or not any(qid==edge['to'] and w.canonical(stmt)==edge['quotation'] for qid,stmt in claims(src,prop))):
                        raise ValueError('Unbound class path: ' + row['id'])
                    if n: dependencies.add(class_fact(edge['sourceKey']))
                    previous = edge['to']
                if previous!=root: raise ValueError('Class path ends at another definition')
                dependencies.add(class_fact(role['definitionSourceKey']))
                inspected.append(role)
            if not inspected: continue
            if interpretation:
                dependencies.add(interpretation['readingEvidenceId'])
            body = json.loads(context['body'])
            body['nameBoundReadings'] = {**body.get('nameBoundReadings',{}),
                                        row['surface']:sorted({m[2] for m in matches})}
            body.update({'componentFacts':sorted(dependencies), 'classPaths':inspected,
                         'inspector':'Codex direct literal class-definition inspection',
                         'sourcePackageSha256':source_sha, 'rulesSha256':package['rulesSha256']})
            if interpretation:body['namedDefinitionInterpretation']=interpretation
            fid = evidence.fact(row['reading'],row['surface'],'context',[],case['target'],doc['id'],body,append_inspection=True)
            new_roles={(explicit_category or r['category'],r['target']):dict(category=explicit_category or r['category'],target=r['target'],sense='Literal Wikipedia subject definition: '+interpretation['definition'] if interpretation else r['sense'],evidenceIds=[fid],method='source_review') for r in inspected}
            roles = list(old.get('roles', [])) + list(new_roles.values())
            reading_ids = sorted(set(old.get('readingEvidence', [])+read_ids+([interpretation['readingEvidenceId']] if interpretation else [])))
            selected = set(reading_ids+norms+[f for role in roles for f in role['evidenceIds']])
            facts = w.fact_rows(db, row); citations = []
            for fact in facts:
                if fact['id'] not in selected: continue
                source = d.verify_document(db, fact['document_id'])
                value = json.loads(fact['body'])
                if fact['id']==fid: quote=w.canonical(subject['claims'])
                elif interpretation and fact['id']==interpretation['readingEvidenceId']:quote=interpretation['quotation']
                elif fact['id']==case['readingCitation']['evidenceId']: quote=case['readingCitation']['quotation']
                else:quote=d.fact_citation(db,fact,old.get('citations',()))['quotation']
                citations.append(dict(evidenceId=fact['id'],documentId=source['id'],sha256=source['sha256'],quotation=quote))
            pending.append(dict(candidateId=row['id'],evidenceSha256=d.fingerprint(db,row,facts),state='reviewed',readingEvidence=reading_ids,
                roles=roles,normalizationEvidence=norms,exclusionEvidence=[],reason='Inspected source class paths; independent precision validation pending',citations=citations))
            pending_pairs.add((row['surface'],row['reading']))
            counts['reviewed'] += 1
            if len(pending)==100: flush()
            if args.max_cases is not None and counts['reviewed']>=args.max_cases: break
    flush()
    result={'sourcePackageSha256':source_sha, 'rulesSha256':package['rulesSha256'],
            'counts':dict(counts), 'classSources':len(source_facts), 'seconds':round(time.monotonic()-started,2), 'modelsCalled':0}
    w.info(db, 'inspectedWikidataReview', result); db.commit(); w.emit(result)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog'); parser.add_argument('--catalog-sha256')
    parser.add_argument('--ledger',required=True); parser.add_argument('--output',required=True)
    parser.add_argument('--recommendations'); parser.add_argument('--source-package')
    parser.add_argument('--apply-inspected',action='store_true')
    parser.add_argument('--apply-saved',action='store_true')
    parser.add_argument('--supplement-class-sources',action='store_true')
    parser.add_argument('--class-source',action='append',default=[])
    parser.add_argument('--config',default=str(w.DEFAULT_CONFIG)); parser.add_argument('--documents',default='build/research/documents')
    parser.add_argument('--provenance',action='append',default=[])
    parser.add_argument('--max-cases',type=int); parser.add_argument('--max-depth',type=int,default=6)
    parser.add_argument('--max-nodes',type=int,default=512)
    args=parser.parse_args()
    if args.supplement_class_sources:
        if not args.source_package or not args.class_source:parser.error('Supplementing definitions needs source-package and class-source')
        result=supplement_class_sources(args.source_package,args.class_source);pathlib.Path(args.output).write_text(w.canonical(result)+'\n');w.emit(result);return
    if args.apply_inspected or args.apply_saved:
        if not args.source_package or (not args.apply_saved and not args.recommendations): parser.error('Applying inspections needs recommendations and source-package')
        with w.coordinator_lock(args.ledger), w.connect(args.ledger) as db:
            w.pin_config(db,args)
            package=json.loads(pathlib.Path(args.source_package).read_text())
            result=apply_inspected(db,args,saved_named_cases(db,package) if args.apply_saved else None)
        pathlib.Path(args.output).write_text(w.canonical(result)+'\n')
        return
    if not args.catalog or not args.catalog_sha256: parser.error('Read-only recommendations need catalog and catalog-sha256')
    if not 1<=args.max_depth<=12 or not 1<=args.max_nodes<=10000 or (args.max_cases is not None and args.max_cases<1):
        parser.error('Positive bounded depth/nodes/cases are required')
    started=time.monotonic(); code_sha256=w.sha(__file__); catalog=RawCatalog(args.catalog,args.catalog_sha256)
    w.emit({'phase':'raw-wikidata-review-catalog-verified','catalogSha256':catalog.sha256})
    db=sqlite3.connect('file:'+pathlib.Path(args.ledger).resolve().as_posix()+'?mode=ro',uri=True); db.row_factory=sqlite3.Row
    try:
        cases,sources,counts,categories,failures=recommendations(db,catalog,max_cases=args.max_cases,max_depth=args.max_depth,max_nodes=args.max_nodes)
        provenance=[]
        for p in args.provenance:
            reported=json.loads(pathlib.Path(p).read_text())
            provenance.append({'file':pathlib.Path(p).name,'sha256':w.sha(p),'reportedSource':reported,
                               'reportedCatalogHashMatchesCurrent':reported.get('outputCatalogSha256')==catalog.sha256 if reported.get('outputCatalogSha256') else None})
        metadata={'schemaVersion':VERSION,'purpose':'Read-only source-review proposal audit; no old decisions consumed, no production decisions made',
                  'catalogSha256':catalog.sha256,'sourceProjection':True,'provenance':provenance,
                  'maxDepth':args.max_depth,'maxNodes':args.max_nodes,'boundedSample':args.max_cases,
                  'rulesSha256':w.digest(w.canonical(ROOTS)),'implementationSha256':code_sha256,'rootRules':ROOTS,'counts':counts,
                  'suggestedCandidateCounts':categories,'failures':failures,'route':'source_review',
                  'independentGoldCases':0,'productionApplied':False,'seconds':round(time.monotonic()-started,3)}
        selected=inspection_cases(cases)
        output={**metadata,'inspectionCaseCount':len(selected),'inspectionSelectionSha256':w.digest(w.canonical([(v['candidateId'],v['target'])for v in selected])),'cases':selected}
        pathlib.Path(args.output).write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
        if args.recommendations:
            with pathlib.Path(args.recommendations).open('w') as f:
                for case in cases:
                    if case['roles']: f.write(w.canonical(case)+'\n')
        if args.source_package:
            pathlib.Path(args.source_package).write_text(json.dumps({**metadata,'sources':sources},ensure_ascii=False,indent=2)+'\n')
        print(w.canonical({'counts':counts,'suggestedCandidateCounts':categories,'seconds':metadata['seconds'],'inspectionCases':len(selected),'productionApplied':False}),flush=True)
    finally:
        db.close(); catalog.close()

if __name__=='__main__':main()
