"""Repair malformed lexical references using retained explicit English links.

Commentary is not another lemma. Keep the original reference fields and links
in the audit; ambiguous targets, restrictions and missing evidence are not
silently removed. Repaired spellings do not borrow target inflection flags.
"""
import argparse,copy,json,re
from collections import Counter,defaultdict
from pathlib import Path
import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_wiktionary as resolver,resolve_pending,restricted_references
from wiktionary_index import Index,SNAPSHOT_SHA256

NOTES=('representing ','used as ','variant of ','shortening of ','mimicking ','to indicate ','particularly')


def english_links(sense):
    return [(display,target[:-8]) for display,target in sense.get('links',[]) if isinstance(target,str) and target.endswith('#English')]


def declared_roles(row):
    result=set()
    templates={'en-noun':'noun','en-adj':'adjective','en-adv':'adverb','en-prop':'noun_proper','en-proper noun':'noun_proper'}
    labels={'noun':'noun','n':'noun','adj':'adjective','adjective':'adjective','adv':'adverb','adverb':'adverb','phr':'phrase','phrase':'phrase','symbol':'symbol','proper noun':'noun_proper'}
    for head in row.get('head_templates',[]):
        name=head.get('name');args=head.get('args',{})
        if name in templates:result.add(templates[name])
        elif name=='en-head' and args.get('1') in labels:result.add(labels[args['1']])
        elif name=='head' and args.get('1')=='en' and args.get('2') in labels:result.add(labels[args['2']])
    return result


def normalized(records):
    result=copy.deepcopy(records);count=0
    for number,row in result:
        for sense in row.get('senses',[]):
            if not resolver.eligible(row,sense):continue
            links=english_links(sense);linked={target for _,target in links}
            for kind in ['alt_of','form_of']:
                refs=sense.get(kind,[])
                if not refs:continue
                first=refs[0].get('word','');target=first;reason=None
                if len(refs)>1 and first in linked:
                    notes=[r.get('word','') for r in refs[1:]]
                    if all(n.startswith(NOTES) or any(display==n and destination==first for display,destination in links) for n in notes):reason='English target anchor separates lemma from trailing usage commentary'
                elif len(refs)==1 and first not in linked:
                    candidates=[t for t in linked if t.startswith(first) and refs[0].get('extra','').startswith(t[len(first):]) and t!=first and any('of '+t+' ' in g for g in sense.get('glosses',[]))]
                    if len(candidates)==1:target=candidates[0];reason='explicit English link and literal gloss restore a target split into the extra field'
                if reason:
                    sense['_referenceRepair']={'relation':kind,'originalReferences':copy.deepcopy(refs),'validatedEnglishLinks':links,'target':target,'rule':reason,'targetMorphologyInherited':False}
                    sense[kind]=[{'word':target}];count+=1
    return result,count


def attach_direct(model,records,wanted,pending):
    counts=Counter();terminal=defaultdict(list)
    disqualified_words,disqualified_roles=restricted_references.disqualified_roles(records)
    for number,row in records:
        for ordinal,sense in enumerate(row.get('senses',[]),1):
            if resolver.eligible(row,sense) and not sense.get('form_of') and not sense.get('alt_of') and not set(sense.get('tags',[]))&{'form-of','alt-of'}:terminal[row['word']].append((number,row,ordinal,sense))
    for number,row in records:
        pos=resolver.ROLES.get(row.get('pos'));surface=row['word']
        if not pos:continue
        for ordinal,sense in enumerate(row.get('senses',[]),1):
            if not resolver.eligible(row,sense):continue
            proof=resolver.provenance(number,row,sense,ordinal);tags=set(proof['tags']);links={target for _,target in english_links(sense)}
            refs=[r['word'] for r in sense.get('form_of',[]) if 'word' in r];values=None;lemma=surface;rule=None
            if pos=='contraction' and {'contraction','contracted'}<=tags and any(h.get('name')=='en-head' and h.get('args',{}).get('1')=='contr' for h in row.get('head_templates',[])):
                values={'contraction'};rule='explicit English contraction head; expansion does not need to be a lexical headword'
            elif 'abbreviation' in tags and pos in declared_roles(row) and any(g.startswith(('Initialism of ','Abbreviation of ','Acronym of ')) for g in sense.get('glosses',[])):
                values=(resolver.categories(row,sense,pos)-resolver.MORPHOLOGY)|{'abbreviation'}
                rule='explicit English abbreviation head supplies its own role; expansion need not be a lexical headword and supplies no inherited POS or morphology'
            elif pos=='symbol' and pos in declared_roles(row) and 'symbol' in tags and any(g.startswith('Symbol for ') for g in sense.get('glosses',[])):
                values={'symbol'};rule='explicit English symbol head and expansion; no noun, name or inflection inference'
            elif pos=='noun' and 'agent' in tags and len(set(refs))==1 and any(t in {refs[0],refs[0]+'#English'} for _,t in sense.get('links',[])) and any(g.startswith('Agent noun of '+refs[0]) for g in sense.get('glosses',[])) and any('verb' in model.members[key,refs[0]] for key in model.approved.get(refs[0],[])):
                values={'noun'};rule='explicit agent-noun derivation, not a noun inflection or inherited verb role'
            elif len(set(refs))==1 and refs[0] in links and terminal.get(refs[0]) and pos in {'verb','noun','adjective','adverb'}:
                proposed=resolver.categories(row,sense,pos)-{'verb_base','adjective_base'}
                if proposed & resolver.MORPHOLOGY:
                    values=proposed;lemma=refs[0];rule='English form entry explicitly states morphology and linked lemma spelling; supporting lemma has no independently inferred infinitive or sense'
                    if pos=='verb' and any(g.startswith('simple past and past participle of '+lemma) for g in sense.get('glosses',[])):values|={'verb_past','verb_past_participle'}
            # This scoped phonetic-code reading must not inherit an unrelated
            # month/given-name sense of the same uppercase target.
            elif pos=='noun' and sense.get('alt_of') and any('from the NATO/ICAO Phonetic Alphabet' in g for g in sense.get('glosses',[])):
                linked=[t for t in links if any(g.startswith('Alternative letter-case form of '+t+' from the NATO/ICAO Phonetic Alphabet') for g in sense.get('glosses',[]))]
                if len(linked)==1:
                    values={'noun','identifier_phonetic_code'};rule='explicitly scoped NATO/ICAO codeword reading, not an unrelated month or personal-name sense'
            if values is not None:
                key=resolver.identifier(number,ordinal,pos,'direct_reference_fact')
                resolver.add(model,key,lemma,surface,values,dict(proof,referenceAdmissionRule=rule,unresolvedLemmaSenseNotPooled=True),pending);counts['directReferenceFacts']+=1
            # A canonical English entry's explicit alternative spelling table
            # provides its role independently of a conflicting alternate head.
            if sense.get('form_of') or sense.get('alt_of') or not model.approved.get(surface):continue
            grammatical='noun' if pos=='noun_proper' else pos
            if not any(grammatical in model.members[key,surface] for key in model.approved[surface]):continue
            for form in row.get('forms',[]):
                word=form.get('form');form_tags=set(form.get('tags',[]))
                if word not in wanted or 'alternative' not in form_tags or form_tags&resolver.BAD:continue
                if word in disqualified_words or (word,row['pos']) in disqualified_roles:
                    pending.append(dict(surface=word,reason='canonical_alternative_table_conflicts_with_explicit_restriction',
                        canonicalEntryId=number,canonicalSurface=surface,canonicalPos=row['pos'],
                        originalForm=copy.deepcopy(form),restrictions=[dict(word=k[0],pos=k[1],proof=v) for k,v in disqualified_roles.items() if k[0]==word],
                        approved=False,absenceOnlyRejection=False))
                    counts['conflictingAlternativeTableForms']+=1
                    continue
                key=resolver.identifier(number,ordinal,pos,'explicit_alternative_table',word)
                values=resolver.categories(row,sense,pos)-resolver.MORPHOLOGY
                resolver.add(model,key,surface,word,values,dict(proof,relation='explicit_alternative_spelling_table',alternativeForm=copy.deepcopy(form),canonicalEntryPos=row['pos'],targetMorphologyInherited=False),pending);counts['explicitAlternativeTableForms']+=1
    return counts


def extend(args):
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    states=list(map(json.loads,(args.base/'status.jsonl').open()));selected=[r for r,s in zip(rows,states) if s['decision']=='pending'];wanted={r['surface'] for r in selected}
    index=Index(args.index)
    try:
        first=list(index.lookup(wanted,folded=True));records=resolver.load_closure(index,{r['word'] for _,r in first}|wanted)
        repaired,repair_count=normalized(records)
        extra={t for _,row in repaired for sense in row.get('senses',[]) for _,t in english_links(sense)}
        records=resolver.load_closure(index,{r['word'] for _,r in first}|wanted|extra);repaired,repair_count=normalized(records)
    finally:index.close()
    canonical_wanted=wanted|{r['word'] for _,r in first}
    counts=resolver.import_records(model,repaired,canonical_wanted,pending,bootstrap_approved=True);counts.update(attach_direct(model,repaired,canonical_wanted,pending))
    counts.update(resolver.import_records(model,repaired,canonical_wanted,pending,bootstrap_approved=True))
    disqualified,_=restricted_references.disqualified_roles(records);additions=resolve_pending.cases(model,selected,{r['word'] for _,r in records},disqualified)
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else [];existing={r['id'] for r in corrections};corrections += [r for r in additions if r['id'] not in existing]
    sources['auditedEnglishReferenceRepairs']={'snapshotSha256':SNAPSHOT_SHA256,'repairedSenses':repair_count,
        'policy':'explicit English anchors distinguish target from usage commentary and restore literal split targets; originals/links retained; no inherited morphology on repaired spelling variants; separately declared abbreviation/symbol heads supply their own roles without requiring lexical expansion heads; canonical spellings selected by exact casefold; contraction heads, agent nouns, explicit alternative-form tables and scoped phonetic-code uses remain separate; no inferred infinitive or pooled lemma senses'}
    prior=args.base/'reviewed-overrides.tsv';summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,repairedReferenceSenses=repair_count,**{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','index','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
