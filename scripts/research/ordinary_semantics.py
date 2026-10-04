"""Source-only ordinary sense review. Exact inspected definition propagation only.

No candidate decisions, old category assignments, or independent evaluation labels
are inputs. An inspection record explicitly records the source groups actually
shown to the reviewing producer; untouched groups remain unresolved.
"""
import argparse, collections, hashlib, json, pathlib, time

BASE = pathlib.Path('build/research/ordinary-source-review')
CATEGORIES={'general','technical','food','product','work','person','character','organization','facility','station','place','event','organism','sports','religion','astronomy','transport'}

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def generate():
    groups = json.loads((BASE / 'groups.json').read_text())
    index = {g['groupId']: g for g in groups}
    annotations = []
    calibration_read=False
    proposals = []
    seen = set()
    for p in sorted((BASE / 'inspection-records').glob('batch-*.json')):
        record = json.loads(p.read_text())
        calibration_read |= record.get('calibrationLabelsPreviouslyRead',False)
        for a in record['annotations']:
            group = index[a['groupId']]
            if group['groupId'] in seen:
                raise ValueError('Duplicate direct review: ' + group['groupId'])
            seen.add(group['groupId'])
            if a['definitionSha256'] != digest([group['glosses'], group['fields'], group['pos'], group['misc']]):
                raise ValueError('Inspected definition changed')
            annotations.append(a)
            if a['category'] not in CATEGORIES:
                continue
            for c in group['cases']:
                proposals.append({
                    'candidateId': c['candidateId'], 'category': a['category'],
                    'method': 'source_review', 'reviewMethod': 'agent_direct_source_inspection',
                    'rule': 'exact-inspected-sense-definition-' + group['groupId'],
                    'matchedGloss': a['supportingDefinition'], 'reason': a['reason'],
                    'reading': c['reading'], 'surface': c['surface'],
                    'evidenceId': c['evidenceId'], 'documentId': c['documentId'],
                    'sha256': c['sha256'], 'target': c['target'],
                    'source': c['source'], 'quotation': c['quotation'],
                    'glosses': c['glosses'], 'fields': c['fields'],
                    'constraints': c['constraints'], 'inspectionRecord': str(p),
                    'definitionSha256': a['definitionSha256'],
                })
    with (BASE / 'proposals.jsonl').open('w') as f:
        for row in proposals:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    counts = collections.Counter(a['category'] for a in annotations)
    summary = {
        'schemaVersion': 1, 'route': 'source_review', 'productionApplied': False,
        'reviewer': 'Codex source-only producer; no human reviewer attestation',
        'sourceOnly': True, 'calibrationLabelsPreviouslyRead': calibration_read,
        'validationLabelsUsedForProduction': False,
        'rawVerifiedMeaningUnits': sum(len(g['cases']) for g in groups),
        'rawMeaningGroups': len(groups), 'directlyInspectedGroups': len(seen),
        'directReviewCounts': dict(counts),
        'proposedUniqueCandidates': len({p['candidateId'] for p in proposals}),
        'generalProposedUniqueCandidates': len({p['candidateId'] for p in proposals if p['category']=='general'}),
        'generalProposedMeaningUnits': sum(p['category']=='general' for p in proposals),
        'uninspectedGroups': len(groups) - len(seen),
        'coreGeneralMinimum': 10000, 'coreTechnicalMinimum': 1500,
        'qualification': 'Proposals require root independent fixed-gold precision validation. Uninspected definitions are not inferred ordinary merely because no field is present.',
        'rawVerifiedSha256': hashlib.sha256((BASE / 'raw-verified.json').read_bytes()).hexdigest(),
        'groupsSha256': hashlib.sha256((BASE / 'groups.json').read_bytes()).hexdigest(),
    }
    (BASE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False))


def apply(args):
    import direct_review as d
    import semantic_audit as s
    import worker as w
    generate()
    exact=collections.defaultdict(list)
    with (BASE/'proposals.jsonl').open() as stream:
        for line in stream:
            v=json.loads(line);exact[(v['candidateId'],v['target'])].append(v)
    inspected=set()
    groups={g['groupId']:g for g in json.loads((BASE/'groups.json').read_text())}
    for path in sorted((BASE/'inspection-records').glob('batch-*.json')):
        for annotation in json.loads(path.read_text())['annotations']:
            inspected.update((c['candidateId'],c['target']) for c in groups[annotation['groupId']]['cases'])
    counts=collections.Counter();pending=[];started=time.monotonic()
    implementation_sha=w.sha(__file__);semantic_sha=w.sha(s.__file__)
    with w.coordinator_lock(args.ledger),w.connect(args.ledger) as db:
        if not w.info(db,'goldFrozen'):raise ValueError('Freeze independent gold before source-sense classification')
        w.pin_config(db,args)
        evidence=w.Evidence(db,args)
        def flush():
            if not pending:return
            path=pathlib.Path('build/research/current-review.json')
            path.write_text(w.canonical({'schemaVersion':1,'cases':pending})+'\n');args.input=str(path)
            d.import_reviews(db,args);db.commit();pending.clear()
            w.emit({'phase':'literal-sense-review','reviewed':counts['reviewed'],'seconds':round(time.monotonic()-started,2)})
        source_rows=[]
        for case in json.loads((BASE/'raw-verified.json').read_text()):
            fact=db.execute('SELECT * FROM facts WHERE id=? AND active=1',(case['evidenceId'],)).fetchone()
            row=db.execute('SELECT id,reading,surface FROM candidates WHERE id=?',(case['candidateId'],)).fetchone()
            if fact is None or row is None:raise ValueError('Missing current source-sense input')
            doc=d.verify_document(db,fact['document_id'])
            source_rows.append({**dict(row),'evidenceId':fact['id'],'body':json.loads(fact['body']),
                'document_id':doc['id'],'target':fact['target'],'path':doc['path'],'sha256':doc['sha256']})
        verified,failures=s.inspect_rows(source_rows)
        if failures:raise ValueError('Literal source constraints changed: '+w.canonical(failures[:10]))
        by_candidate=collections.defaultdict(list)
        for case in verified:by_candidate[case['candidateId']].append(case)
        for cid,cases in by_candidate.items():
            row=dict(db.execute('SELECT * FROM candidates WHERE id=?',(cid,)).fetchone())
            if row['state'] in ('excluded_confirmed','error','blocked') or row['error']:counts['protected']+=1;continue
            old=json.loads(row['decision']) if row['decision'] else {};roles=list(old.get('roles',[]))
            known={(r['category'],r['target']) for r in roles};facts=w.fact_rows(db,row);byid={f['id']:f for f in facts}
            reads=set(old.get('readingEvidence',[]));norms=d.normalization_ids(row,facts);added=False
            changed=row['normalization']!='unchanged' and not row['normalization'].startswith('original:')
            if changed and not norms:counts['boundaryUnresolved']+=1;continue
            for case in cases:
                fid=case['evidenceId'];fact=byid.get(fid)
                if not fact or fact['kind']!='meaning' or fact['target']!=case['target']:raise ValueError('Stale literal sense evidence: '+cid)
                doc=d.verify_document(db,case['documentId'])
                if fact['document_id']!=doc['id'] or doc['sha256']!=case['sha256']:raise ValueError('Changed literal XML source: '+cid)
                body=json.loads(fact['body']);entry=str(body.get('entryId','')).split(':')[0]
                bound=[f['id'] for f in facts if f['kind']=='reading' and f['document_id']==doc['id'] and
                    str(json.loads(f['body']).get('entryId','')).split(':')[0]==entry]
                if not bound:
                    # inspect_rows independently parsed the literal <reb>,
                    # <keb>, re_restr, re_nokanji, stagk and stagr above.
                    # Restore a separate reading proof from that exact XML;
                    # a semantic category or a different entry cannot grant it.
                    read=evidence.fact(row['reading'],row['surface'],'reading',[],case['source']+':'+entry,doc['id'],
                        dict(source=case['source'],entryId=entry,reading=row['reading'],surface=row['surface'],
                            quotation=case['quotation'],literalXmlConstraints=case['constraints'],
                            parser='literal-source-reading-repair-1'))
                    bound=[read];facts=w.fact_rows(db,row);byid={f['id']:f for f in facts};counts['restoredLiteralReadings']+=1
                    added=True
                reads.update(bound)
                key=(cid,case['target'])
                suggestions=[(v['category'],v['rule'],v['matchedGloss']) for v in exact.get(key,[])] if key in inspected else s.suggested_rules(case['glosses'],case['fields'],case['source'],case['constraints'].get('pos',()),case['constraints'].get('misc',()))
                expected={v[0] for v in suggestions}
                generated_prefixes=('exact-inspected-sense-definition-','explicit-','ordinary-','closed-','controlled-','biological-','named-target-')
                retired=[r for r in roles if r['target']==case['target'] and fid in r['evidenceIds'] and r.get('method')=='source_review'
                    and r.get('sense','').startswith(generated_prefixes) and r['category'] not in expected]
                if retired:
                    roles=[r for r in roles if r not in retired];known={(r['category'],r['target']) for r in roles};added=True
                    counts['retiredUnprovedRoles']+=len(retired)
                for category,rule,definition in suggestions:
                    if (category,case['target']) in known:continue
                    role=dict(category=category,target=case['target'],sense=rule,evidenceIds=[fid],method='source_review')
                    if not w.target_supported(role,facts):counts['targetUnresolved']+=1;continue
                    roles.append(role);known.add((category,case['target']));reads.update(bound);counts[category]+=1;added=True
            if not added and row['state']=='queued' and row['reason']=='evidence-changed':
                # A previously restored reading can have queued this exact
                # pair in an earlier run. Re-evaluate its current XML senses
                # above, rather than leaving an unfinished queue checkpoint.
                added=True
            if not added:continue
            if not roles:
                unresolved=dict(old,roles=[],readingEvidence=sorted(reads),normalizationEvidence=norms,
                    classificationRoute='source_review',reason='Literal source category remains unresolved; previous semantic shortcut withdrawn')
                d.write_decision(db,row,'needs_review',unresolved['reason'],unresolved);counts['reopenedCandidates']+=1;continue
            selected=reads|set(norms)|{fid for role in roles for fid in role['evidenceIds']}
            citations=[d.fact_citation(db,f,old.get('citations',())) for f in facts if f['id'] in selected]
            pending.append(dict(candidateId=cid,evidenceSha256=d.fingerprint(db,row,facts),state='reviewed',
                readingEvidence=sorted(reads),roles=roles,normalizationEvidence=norms,exclusionEvidence=[],
                reason='Literal XML constraints and inspected sense definitions; precision validation pending',citations=citations))
            counts['reviewed']+=1
            if len(pending)==100:flush()
        flush();result={'counts':dict(counts),'seconds':round(time.monotonic()-started,2),'modelsCalled':0,
            'rawVerifiedSha256':w.sha(BASE/'raw-verified.json'),'implementationSha256':implementation_sha,
            'semanticRulesSha256':semantic_sha}
        w.info(db,'literalSenseReview',result);db.commit();w.emit(result)
        (BASE/'applied.json').write_text(w.canonical(result)+'\n')

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true')
    p.add_argument('--ledger',default='build/research/ledger.sqlite');p.add_argument('--config');p.add_argument('--documents',default='build/research/documents')
    args=p.parse_args()
    if args.apply:
        import worker as w
        args.config=args.config or str(w.DEFAULT_CONFIG);apply(args)
    else:generate()
