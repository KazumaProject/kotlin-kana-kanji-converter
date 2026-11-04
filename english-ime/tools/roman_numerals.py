"""Verify existing Roman-numeral spellings by the pinned W3C additive rules.

English words/acronyms sharing these letters keep separate lexical identities.
Noncanonical forms are not declared invalid words by this numeric rule.
"""
import argparse
import json
from pathlib import Path
import re

import extend_lexicon as extension
import lexicon_pipeline as pipeline

SPEC_SHA='7d697581c3eb238c3e8d18bcf0c03aa889380041fa208c8bf06c51dd07be9807'
LICENSE_SHA='cf00bcb7330c1d63b1d3138b0cbd50f2a53f8b71400ecea4e1493a9d50ac0da2'
URL='https://www.w3.org/TR/2021/CR-css-counter-styles-3-20210727/#lower-roman'
SYMBOLS=[(1000,'m'),(900,'cm'),(500,'d'),(400,'cd'),(100,'c'),(90,'xc'),(50,'l'),(40,'xl'),(10,'x'),(9,'ix'),(5,'v'),(4,'iv'),(1,'i')]


def render(number):
    if not 1<=number<=3999:raise ValueError('Outside the specified Roman counter range')
    result=[]
    for value,symbol in SYMBOLS:
        count,number=divmod(number,value);result.append(symbol*count)
    return ''.join(result)


VALUES={render(number):number for number in range(1,4000)}


def attach(model,rows):
    extension.ensure_categories(model,{'numeral_roman'})
    found=set()
    for row in rows:
        surface=row['surface']
        if surface not in {surface.lower(),surface.upper()}:continue
        value=VALUES.get(surface.lower())
        if value is None:continue
        lemma=render(value).upper();key='roman-standard-'+str(value)
        proof={'source':'standard_roman_numeral','url':URL,'specificationSha256':SPEC_SHA,
            'numericValue':value,'standardLowercase':render(value),'range':[1,3999],'approved':True,
            'scope':'existing input surface exactly rendered by the normative lower/upper ASCII Roman-numeral style; separate numeric identity, no English word sense, inflection or source-frequency interpretation'}
        model.add(key,lemma,lemma,{'numeral','numeral_roman'},dict(proof,relation='canonical_uppercase_numeral'),approved=True)
        model.add(key,lemma,surface,{'numeral','numeral_roman'},proof,approved=True);found.add(row['id'])
    return found


def extend(args):
    if pipeline.digest(args.sources/'specification.html')!=SPEC_SHA or pipeline.digest(args.sources/'license.html')!=LICENSE_SHA:raise ValueError('Changed W3C specification or notice')
    text=(args.sources/'specification.html').read_text();rule=re.search(r'@counter-style lower-roman\s*\{([^}]+)\}',text)
    if not rule or not re.search(r'range:\s*1\s+3999\s*;',rule[1]):raise ValueError('Roman numeral rule changed')
    parsed=[(int(value),symbol) for value,symbol in re.findall(r'(\d+)\s+[\"\']?([mdclxvi]+)[\"\']?',rule[1])]
    if parsed!=SYMBOLS:raise ValueError('Unexpected Roman numeral additive symbols')
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    found=attach(model,rows)
    sources['standardRomanNumerals']={'url':URL,'specificationSha256':SPEC_SHA,'licenseSha256':LICENSE_SHA,
        'policy':'existing input surfaces only; canonical additive renderings for 1..3999 in all-lower/all-upper ASCII; separate numeric identities preserve English homographs; other spellings are neither guessed nor excluded'}
    notices['W3C-COUNTER-STYLES-LICENSE.html']=(args.sources/'license.html').read_bytes()
    notices['W3C-ROMAN-NUMERALS-NOTICE.txt']=('W3C CSS Counter Styles Level 3, Candidate Recommendation Snapshot, 27 July 2021; editor Tab Atkins Jr.\n'+URL+
        '\nW3C permissive document license retained separately.\nChanges: verified existing inventory strings against the normative 1..3999 lower/upper Roman numeral additive rules and attached separate numeric dictionary identities. No other words, inflections, rendering code or document prose copied.\n').encode()
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    prior=args.base/'reviewed-overrides.tsv'
    summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,
        reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(existingNumericRows=len(found),**{key:summary[key] for key in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','sources','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
