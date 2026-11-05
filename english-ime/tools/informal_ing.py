"""Retain verified informal English uses independently of name/code alternatives.

Research-attested abbreviations are direct evidence. Final-written-g omissions
are explicitly derived variants of approved English -ing verb forms, not claimed
individual source attestations or arbitrary string truncations.
"""
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
import extend_lexicon as extension
import lexicon_pipeline as pipeline
import expressive_orthography as references

URL='https://aclanthology.org/N13-1037/'
ABBREVIATIONS={'lol','lmao','smh','ikr','ctfu','lls','af'}
ROOT_SOURCES={'curated_seed','wiktionary','esdb'}


def attach(model,rows,pending_ids=None):
    extension.ensure_categories(model,{'orthography_informal_ing'})
    counts=Counter();wanted={row['surface'] for row in rows};roots=defaultdict(list)
    for token in sorted(wanted&ABBREVIATIONS):
        key='internet-abbreviation-'+token
        proof={'source':'research_attested_abbreviation','url':URL,'referenceSha256':references.PINS['N13-1037.pdf'],
            'page':3,'sections':['2.4 Pragmatics','2.5 Social variables'],'literalAbbreviation':token,'approved':True,
            'scope':'form explicitly identified as an English social-media abbreviation in the cited research; no invented expansion, ordinary noun/verb POS, inflection, corpus-intent or human-review claim'}
        model.add(key,token,token,{'abbreviation','register_informal'},proof,approved=True);counts['attestedAbbreviationForms']+=1
    for key,form in list(model.forms.items()):
        word=form['surface'];members=model.members[key]
        if (not word.isascii() or not word.isalpha() or not word.islower() or not word.endswith('ing') or len(word)<5
                or 'verb_ing' not in members or 'noun_proper' in members or key[0] not in model.approved[word]
                or any(c.startswith(('name_','identifier_','orthography_')) for c in members)):continue
        proof=next((e for e in model.evidence[key] if e['source'] in ROOT_SOURCES and e.get('approved',True)),None)
        if proof:roots[word[:-1]].append((key,form['lemma'],proof))
    for row in rows:
        if pending_ids is not None and row['id'] not in pending_ids:continue
        for key,lemma,root_proof in roots[row['surface']]:
            proof={'source':'derived_informal_ing','url':URL,'referenceSha256':references.PINS['N13-1037.pdf'],'page':3,'section':'2.5 Social variables',
                'underlyingLexemeId':key[0],'underlyingSurface':key[1],'underlyingEvidence':root_proof,'legacySourceId':row['id'],'approved':True,
                'individuallyAttestedVariantClaimed':False,'scope':'existing lowercase spelling omitting only the final written g of an independently approved -ing verb inflection; same lemma and participle use, explicitly derived informal orthography; no arbitrary stem truncation, proper-name/identifier transformation or corpus-intent claim'}
            model.add(key[0],lemma,row['surface'],{'verb','verb_ing','register_informal','orthography_informal_ing'},proof,approved=True);counts['derivedIngInputSenses']+=1
    return counts


def extend(args):
    for name,pin in references.PINS.items():
        if pipeline.digest(args.sources/name)!=pin:raise ValueError('Changed research reference')
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    states=list(map(json.loads,(args.base/'status.jsonl').open()));ids={r['id'] for r in states if r['decision']=='pending'}
    counts=attach(model,rows,ids)
    sources['informalEnglishIngAndAbbreviations']={'url':URL,'referenceSha256':references.PINS['N13-1037.pdf'],
        'policy':'derived -ing spellings limited to currently pending rows so established ordinary words gain no speculative participle flags; seven literal research-attested English abbreviations, no guessed expansions or lexical POS; existing final-written-g omissions only from independently approved -ing verb inflections, keeping lemma and participle flags; explicitly derived informal variants, not individually source-attested entries; alternative name/code senses retained'}
    notices['INFORMAL-ENGLISH-REFERENCE.txt']=('Jacob Eisenstein (2013), What to do about bad language on the internet. NAACL-HLT, pp. 359–369, section 2.4–2.5, page 361. '+URL+'\nNo paper prose, examples, code, tables or corpus redistributed. Seven abbreviation-label facts and the general written -ing variation phenomenon support existing input forms. Derived spellings retain independently attested English verb morphology and are marked as derived, without a claim of individual attestation or original corpus sense.\n').encode()
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    prior=args.base/'reviewed-overrides.tsv'
    summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,**{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','sources','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
