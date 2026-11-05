"""Review literal legacy name presentations against complete approved names.

Only individually reviewed original manual rows are eligible. Letter identity,
complete name scope and the pinned literal mapping remain required; no API or
command case folding, name fragments, invented segmentation or preferred-case
claim is made.
"""
import argparse,json,re
from collections import Counter
from pathlib import Path
import extend_lexicon as extension
import lexicon_pipeline as pipeline
import manual_aliases


def attach(model,rows,reviews,literals):
    originals={row['id']:row for row in rows};seen=set();counts=Counter()
    for review in reviews:
        row=originals[review['id']];literal=row['reading'],row['surface'],row['cost'];canonical=review['canonical']
        relation=review['separatorRelation']
        if (row['id'] in seen or review.get('reviewer')!='implementation_agent' or not review.get('rationale','').strip() or
                not row['id'].startswith('manual:') or literal not in literals or
                any(review.get(k)!=row[k] for k in ['id','reading','surface','cost']) or
                canonical==row['surface'] or relation not in {'case_space','reviewed_space_hyphen'} or
                not re.fullmatch(r'[A-Za-z0-9]+(?:[ -][A-Za-z0-9]+)*',canonical) or
                not re.fullmatch(r'[A-Za-z0-9]+(?:[ -][A-Za-z0-9]+)*',row['surface'])):
            raise ValueError('Named alias requires an explicit unchanged original literal review')
        normalize=(lambda s:s.replace(' ','').casefold()) if relation=='case_space' else (lambda s:s.replace('-',' ').casefold())
        if normalize(canonical)!=normalize(row['surface']):raise ValueError('Named alias cannot edit letters, clip names or invent word boundaries')
        seen.add(row['id']);accepted=[]
        for identity in sorted(model.approved.get(canonical,())):
            key=identity,canonical;values=model.members[key]
            if ('noun_proper' not in values or not any(v.startswith('name_') for v in values) or
                    any(v.startswith(('identifier_','orthography_')) for v in values)):continue
            evidence=[e for e in model.evidence[key] if e.get('approved',True) and not e.get('requiresFullNamedContext',False)]
            if evidence:accepted.append((key,values,evidence))
        if not accepted:raise ValueError('Named alias needs an independently approved complete name, not a noun, command or API identifier')
        url=('https://github.com/KazumaProject/kotlin-kana-kanji-converter/blob/'+manual_aliases.REVISION+
             '/english-ime/src/main/kotlin/Manual.kt#L'+str(literals[literal]))
        for key,values,evidence in accepted:
            proof=dict(source='verified_manual_name_case',url=url,approved=True,reviewer='implementation_agent',
                humanReviewClaimed=False,legacySourceId=row['id'],manualSourceSha256=manual_aliases.MANUAL_SHA256,
                originalReading=row['reading'],originalSurface=row['surface'],originalCost=row['cost'],
                canonicalSurface=canonical,underlyingLexemeId=key[0],underlyingEvidence=evidence,
                separatorRelation=relation,rationale=review['rationale'],externallyAttestedAliasSpellingClaimed=False,
                preferredCaseClaimed=False,
                scope='explicit original manual case/space or separately reviewed space/hyphen presentation of a complete independently approved name; literal input, output and cost retained; no invented spelling, name component, ordinary POS, executable/API identity or current availability claim')
            model.add(key[0],model.forms[key]['lemma'],row['surface'],values,proof,approved=True)
            counts['reviewedManualNameSenses']+=1
        if row['reading']!=row['surface'] and (row['reading'],row['surface']) not in {(r['source'],r['target']) for r in model.relations if r['relation']=='input_alias'}:
            model.relations.append(dict(relation='input_alias',source=row['reading'],target=row['surface'],evidence=url))
    counts['reviewedManualNameRows']=len(seen)
    return counts


def extend(args):
    literals=manual_aliases.literal_mappings(args.manual_source);reviews=list(map(json.loads,args.reviews.open()))
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    counts=attach(model,rows,reviews,literals)
    sources['reviewedLiteralManualNames']=dict(manualSourceSha256=manual_aliases.MANUAL_SHA256,
        reviewsSha256=pipeline.digest(args.reviews),humanReviewClaimed=False,
        policy='individually reviewed literal manual case/space or explicit space/hyphen presentations of complete approved names only; original mappings/costs and independent name identities retained; no API/command case folding, noun-to-brand inference, name fragments or preferred-case claim')
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    prior=args.base/'reviewed-overrides.tsv'
    summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,
        reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,**{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']})))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','manual-source','reviews','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
