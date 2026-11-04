"""Verify existing initial-capital spellings of approved ordinary English forms.

This productive case relation does not infer a software/product interpretation,
preferred name casing or the original corpus's intended sense. Mixed-case code
identifiers, acronyms and proper-name-only bases are outside the rule.
"""
import argparse,json,re
from collections import Counter,defaultdict
from pathlib import Path
import extend_lexicon as extension
import lexicon_pipeline as pipeline

SOURCES={'curated_seed','wiktionary','esdb','ngsl_list'}
BASE_FLAGS={'verb_base','aux_be_base','aux_have_base','aux_do_base','adjective_base'}


def attach(model,rows,pending_ids):
    extension.ensure_categories(model,{'orthography_initial_capital'})
    counts=Counter();ordinary=defaultdict(list)
    for key,form in list(model.forms.items()):
        surface=form['surface'];members=model.members[key]
        if not re.fullmatch(r'[a-z]+(?: [a-z]+)*',surface) or key[0] not in model.approved[surface]:continue
        if 'noun_proper' in members or any(v.startswith(('name_','identifier_','orthography_')) for v in members):continue
        proof=next((p for p in model.evidence[key] if p['source'] in SOURCES and p.get('approved',True)),None)
        if proof:ordinary[surface].append((key,form,members.copy(),proof))
    for row in rows:
        if row['id'] not in pending_ids:continue
        original=row['surface']
        # Sentence-style or title-style initial capitals, never arbitrary
        # internal capitalization, ALL-CAPS or changes in letters/word spacing.
        if original==original.lower() or not re.fullmatch(r'[A-Z][a-z]*(?: [A-Za-z][a-z]*)*',original):continue
        for key,form,members,source in ordinary[original.lower()]:
            values=(members-BASE_FLAGS)|{'orthography_initial_capital'}
            proof={'source':'verified_initial_capital','url':source['url'],'legacySourceId':row['id'],
                'underlyingLexemeId':key[0],'underlyingSurface':key[1],'underlyingEvidence':source,'approved':True,
                'preferredNameCaseClaimed':False,'individuallyAttestedCaseClaimed':False,
                'scope':'existing initial-capital spelling of an independently approved ordinary English form, preserving letters/spaces and lemma; no proper-name, software, acronym, corpus-intent or preferred-case claim; base flags are not copied onto a non-lemma surface'}
            model.add(key[0],form['lemma'],original,values,proof,approved=True);counts['existingInitialCapitalSenses']+=1
    return counts


def extend(args):
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    states=list(map(json.loads,(args.base/'status.jsonl').open()));ids={r['id'] for r in states if r['decision']=='pending'}
    counts=attach(model,rows,ids)
    sources['ordinaryEnglishInitialCapitals']={'policy':'existing sentence/title-style initial capitals only, letters/spaces unchanged, independently approved ordinary English base and identity required; no names-only, acronyms, mixed-case identifiers, software-name or corpus-intent inference; derived case variants, not individually source-attested spellings; base flags never copied onto non-lemma forms'}
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    prior=args.base/'reviewed-overrides.tsv'
    summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,**{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
