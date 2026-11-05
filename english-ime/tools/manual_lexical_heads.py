"""Review original manual spellings against independently indexed English heads.

Canonical space-free aliases are explicit input reviews, never guessed word
segmentation, products or API names inferred from capitalization. Every alias
retains its literal original reading/output/cost and the canonical lexical
identity, with a separate derived-spelling category.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import extend_lexicon as extension
import initial_capitals
import lexicon_pipeline as pipeline
import manual_aliases
import resolve_wiktionary as resolver
from wiktionary_index import Index, SNAPSHOT_SHA256

SOURCES={'curated_seed','wiktionary','esdb','ngsl_list'}


def attach(model,rows,reviews,literals):
    originals={row['id']:row for row in rows};seen=set();counts=Counter()
    extension.ensure_categories(model,{'orthography_existing_manual_alias'})
    for review in reviews:
        if review['id'] in seen or review['reviewer']!='implementation_agent' or not review['rationale'].strip():
            raise ValueError('Missing or duplicate explicit manual lexical review')
        seen.add(review['id']);row=originals[review['id']];canonical=review['canonical']
        literal=row['reading'],row['surface'],row['cost']
        relation=review.get('separatorRelation','case_space')
        normalize=lambda value:value.replace(' ','').casefold() if relation=='case_space' else value.replace('-',' ').casefold()
        if (relation not in {'case_space','reviewed_space_hyphen'} or
                not row['id'].startswith('manual:') or any(review[key]!=row[key] for key in ['id','reading','surface','cost']) or
                literal not in literals or canonical==row['surface'] or
                normalize(canonical)!=normalize(row['surface'])):
            raise ValueError('A lexical alias must retain its exact original literal mapping and letters')
        approved=[]
        for identifier in sorted(model.approved.get(canonical,[])):
            key=identifier,canonical;values=model.members[key]
            if 'noun_proper' in values or any(v.startswith(('name_','identifier_','orthography_')) for v in values):continue
            if not values&{'noun','verb','adjective','adverb'}:continue
            evidence=[e for e in model.evidence[key] if e['source'] in SOURCES and e.get('approved',True)]
            if evidence:approved.append((key,evidence))
        if not approved:raise ValueError('An explicit alias needs an independently approved ordinary English head')
        for key,evidence in approved:
            values=(model.members[key]-initial_capitals.BASE_FLAGS)|{'orthography_existing_manual_alias'}
            url='https://github.com/KazumaProject/kotlin-kana-kanji-converter/blob/'+manual_aliases.REVISION+'/english-ime/src/main/kotlin/Manual.kt#L'+str(literals[literal])
            proof=dict(source='reviewed_manual_lexical_alias',url=url,approved=True,reviewer='implementation_agent',humanReviewClaimed=False,
                legacySourceId=row['id'],originalReading=row['reading'],originalSurface=row['surface'],originalCost=row['cost'],
                manualSourceSha256=manual_aliases.MANUAL_SHA256,canonicalSurface=canonical,underlyingLexemeId=key[0],
                separatorRelation=relation,
                underlyingEvidence=evidence,rationale=review['rationale'],externallyAttestedAliasSpellingClaimed=False,
                scope='explicit reviewed original literal case/space or separately reviewed space/hyphen alias of an independently approved ordinary English head; canonical identity retained, no invented segmentation, name/API interpretation, preferred case, corpus intent or inherited base-form flags')
            model.add(key[0],model.forms[key]['lemma'],row['surface'],values,proof,approved=True)
            counts['reviewedManualLexicalAliases']+=1
    return counts


def extend(args):
    literals=manual_aliases.literal_mappings(args.manual_source)
    reviews=list(map(json.loads,args.reviews.open()))
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    states=list(map(json.loads,(args.base/'status.jsonl').open()));ids={r['id'] for r in states if r['decision']=='pending'}
    wanted={r['surface'].lower() for r in rows if r['id'] in ids and r['id'].startswith('manual:')}|{r['canonical'] for r in reviews}
    index=Index(args.index)
    try:
        first=list(index.lookup(wanted,folded=True));canonical={r['word'] for _,r in first}
        records=resolver.load_closure(index,canonical|wanted)
    finally:index.close()
    counts=resolver.import_records(model,records,canonical,pending,bootstrap_approved=True)
    counts.update(attach(model,rows,reviews,literals));counts.update(initial_capitals.attach(model,rows,ids))
    sources['reviewedManualLexicalHeads']=dict(snapshotSha256=SNAPSHOT_SHA256,manualSourceSha256=manual_aliases.MANUAL_SHA256,
        reviewsSha256=pipeline.digest(args.reviews),humanReviewClaimed=False,
        policy='complete indexed English manual heads and explicit literal case/space or separately reviewed space/hyphen aliases only; raw mapping/cost and canonical identity retained, no inferred word segmentation, product/API classification or preferred case')
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    prior=args.base/'reviewed-overrides.tsv'
    summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,
        reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,**{key:summary[key] for key in ['includedRows','excludedRows','pendingRows']})))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','index','manual-source','reviews','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
