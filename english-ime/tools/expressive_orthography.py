"""Verify narrow productive repeated-letter spellings of existing English forms.

These are derived informal orthographic variants, not claimed individually
attested dictionary entries. No frequency-selected canonical guess, general
spell correction, word invention, proper-name stretch or inflection inference.
"""
import argparse,itertools,json,re,tempfile
from collections import Counter,defaultdict
from pathlib import Path
import extend_lexicon as extension
import lexicon_pipeline as pipeline

URL='https://aclanthology.org/D11-1052/'
PINS={'D11-1052.pdf':'24649e210c52ffbef4f48249665ecb59c46179a38fc7578b8e5692ea484708dd','N13-1037.pdf':'ed2d527162465ae1182c5c2d464ccbca7dab899dfc64c7c022faa438fd9f782c'}
ROLES={'noun','verb','adjective','adverb','interjection','pronoun','determiner','preposition','conjunction','particle','negation'}
ROOT_SOURCES={'curated_seed','wiktionary','esdb','ngsl_list'}


def bases(surface):
    if not re.fullmatch('[a-z]+',surface):return []
    groups=[''.join(group) for _,group in itertools.groupby(surface)]
    # Require an unambiguous lengthening signal. Interior consonant triples
    # (e.g. a repeated m in a typo of commit) are left for lexical review.
    selected=[i for i,g in enumerate(groups) if len(g)>=3 and (g[0] in 'aeiou' or i==len(groups)-1)]
    if not selected:return []
    if any(len(g)>=3 and i not in selected for i,g in enumerate(groups)):return []
    if len(selected)>6:return []
    result=[]
    for lengths in itertools.product((1,2),repeat=len(selected)):
        replacement=dict(zip(selected,lengths));word=''.join(g[0]*replacement[i] if i in replacement else g for i,g in enumerate(groups))
        if len(word)>1:result.append(word)
    return sorted(set(result))


def attach(model,rows,pending_ids):
    extension.ensure_categories(model,{'orthography_expressive_lengthening'})
    roots=defaultdict(list);counts=Counter()
    for key,form in list(model.forms.items()):
        members=model.members[key];surface=form['surface'];roles=members&ROLES
        if (not roles or not re.fullmatch('[a-z]{2,}',surface) or key[0] not in model.approved[surface]
                or 'noun_proper' in members or any(c.startswith(('name_','identifier_')) for c in members)):continue
        if not any(e['source'] in ROOT_SOURCES and e.get('approved',True) for e in model.evidence[key]):continue
        roots[surface].append((key,form['lemma'],roles))
    for row in rows:
        if row['id'] not in pending_ids:continue
        for base in bases(row['surface']):
            for key,lemma,roles in roots[base]:
                proof={'source':'expressive_orthography','url':URL,'referenceSha256':PINS,'legacySourceId':row['id'],
                    'underlyingLexemeId':key[0],'underlyingSurface':base,'derivedSurface':row['surface'],'approved':True,
                    'individuallyAttestedVariantClaimed':False,'corpusSenseClaimed':False,
                    'scope':'existing lowercase input derived only by extending a vowel run or final-letter run to at least three; all verified one/two-letter underlying alternatives retained; independently approved ordinary English base, no proper-name/identifier stretching, arbitrary edit, preferred spelling, frequency guess or inherited inflection flags'}
                model.add(key[0],lemma,row['surface'],roles|{'register_informal','orthography_expressive_lengthening'},proof,approved=True)
                counts['derivedInputSenses']+=1
    return counts


def extend(args):
    for name,pin in PINS.items():
        if pipeline.digest(args.sources/name)!=pin:raise ValueError('Changed research reference')
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    states=list(map(json.loads,(args.base/'status.jsonl').open()));pending_ids={r['id'] for r in states if r['decision']=='pending'}
    counts=attach(model,rows,pending_ids)
    sources['expressiveOrthography']={'references':PINS,'url':URL,'policy':'narrow independently implemented productive orthographic relation, existing lowercase rows and independently approved ordinary English roots only; at least triple vowel or final-letter runs, all one/two-letter root alternatives retained; derived informal variants, not individually attested entries or inferred inflections; no paper text, tables, code or corpus imported'}
    notices['EXPRESSIVE-ORTHOGRAPHY-REFERENCES.txt']=('Linguistic references only; no paper text, tables, code or corpus redistributed.\nSamuel Brody and Nicholas Diakopoulos (2011), Cooooooooooooooollllllllllllll!!!!!!!!!!!!!! Using Word Lengthening to Detect Sentiment in Microblogs. EMNLP, pp. 562–570. '+URL+'\nJacob Eisenstein (2013), What to do about bad language on the internet. NAACL-HLT, pp. 359–369. https://aclanthology.org/N13-1037/\nThe implemented rule is narrower than general repeated-letter normalization: it only verifies existing lowercase strings with triple vowel/final-letter runs against independently approved English roots, preserving all valid alternatives without copying inflection flags or choosing a canonical spelling by corpus frequency. These forms are labeled derived informal orthographic variants, not individually source-attested entries.\n').encode()
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    prior=args.base/'reviewed-overrides.tsv'
    summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,**{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','sources','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
