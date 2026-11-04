"""Separate contextual-name classification from standalone candidate admission.

A token in an attested name is not automatically an independently usable name
or English word. Keep contextual evidence, then require separate lexical/name
proof or a verified orthographic relation before admitting a candidate.
"""
import argparse,json
from collections import Counter
from pathlib import Path
import extend_lexicon as extension
import lexicon_pipeline as pipeline
import expressive_orthography,informal_ing,initial_capitals
import resolve_pending,resolve_wiktionary,restricted_references
from wiktionary_index import Index



def extend(args):
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    states=list(map(json.loads,(args.base/'status.jsonl').open()))
    # Index contextual surfaces once; do not scan the entire lexicon per row.
    context_surfaces={key[1] for key,proofs in model.evidence.items() if any(e.get('requiresFullNamedContext') for e in proofs)}
    provisional=set()
    for row,state in zip(rows,states):
        surfaces=state.get('effective_surfaces',[state.get('effective_surface',row['surface'])])
        if state['decision']=='include' and not all(model.approved.get(s) for s in surfaces) and context_surfaces.intersection(surfaces):provisional.add(row['id'])
    selected=provisional|{r['id'] for r in states if r['decision']=='pending'}
    counts=Counter()
    counts.update(expressive_orthography.attach(model,rows,selected))
    counts.update(initial_capitals.attach(model,rows,selected))
    counts.update(informal_ing.attach(model,rows,selected))
    for proofs in model.evidence.values():
        for proof in proofs:
            if proof.get('requiresFullNamedContext'):proof['standaloneCandidateApproved']=False
    unresolved=[r for r in rows if r['id'] in selected and not model.approved.get(r['surface'])]
    index=Index(args.index)
    try:records=resolve_wiktionary.load_closure(index,{r['surface'] for r in unresolved})
    finally:index.close()
    disqualified,_=restricted_references.disqualified_roles(records)
    additions=resolve_pending.cases(model,unresolved,{r['word'] for _,r in records},disqualified)
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    existing={r['id'] for r in corrections};corrections += [r for r in additions if r['id'] not in existing]
    for row in rows:
        if row['id'] in provisional:pending.append({'sourceId':row['id'],'surface':row['surface'],'reason':'context_component_not_standalone_admission_proof',
            'previousProvisionalIncludeWithdrawn':True,'scope':'preserve full-name component evidence but re-evaluate candidate admission using independent lexical/name or verified orthographic evidence; source strings/costs unchanged; no nonword exclusion inferred from source absence'})
    sources['standaloneCandidateAdmissionAudit']={'previousContextOnlyIncludeRows':len(provisional),
        'policy':'contextual-name facts are not standalone adoption evidence, including after reload; original facts and complete source rows retained; independently verified English morphology/case/name alternatives may admit the row, otherwise continue investigation; no source-absence exclusion or automatic standalone name/POS inference'}
    prior=args.base/'reviewed-overrides.tsv'
    summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,contextOnlyProvisionalRowsReevaluated=len(provisional),**{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','index','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
