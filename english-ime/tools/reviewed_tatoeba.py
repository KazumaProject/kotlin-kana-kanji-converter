"""Apply individual reviews of exact English laughter utterances.

Corpus language labels and token matches are research leads, not automatic POS
proof. Every adopted spelling is printed in a pinned English sentence and has
a separate interpretation review plus an independently approved English anchor.
No sentence text, generated repetition variants or inflection flags are exported.
"""
import argparse
import bz2
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import re
import tempfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending

PINS={'eng_sentences_detailed.tsv.bz2':'7d8a98a1322c63eb62199b0e928efc5b9afbf8f4bb9bc4b60ebde1ea99a30cda',
      'eng_sentences_CC0.tsv.bz2':'c2e2edd063a31cbbc8e416a4858225e934bbb0afff485031821e59f230ccf1ca',
      'CC-BY-2.0-FR.html':'597d4c64f6606c64da65ba6c079e5cc87e4cce2b5187eda908c939b538e7ab9b',
      'CC0-1.0.html':'b43732f4c1463b087cf10d4daf8d8766514b2bf8f21bc5ef50905f95be227726'}
ANCHORS={'haha':r'a?(?:ha){2,}','lol':r'l(?:ol){2,}'}
ROOT_SOURCES={'curated_seed','wiktionary','esdb','ngsl_list'}


def load(directory,reviews_file):
    for name,pin in PINS.items():
        if pipeline.digest(directory/name)!=pin:raise ValueError('Changed English corpus or license: '+name)
    manifest=json.loads((directory/'pending-contexts-v32.manifest.json').read_text())
    contexts=directory/'pending-contexts-v32.jsonl'
    if (pipeline.digest(contexts)!=manifest['sha256'] or manifest['sourceSha256']!=PINS['eng_sentences_detailed.tsv.bz2'] or
            manifest['cc0SourceSha256']!=PINS['eng_sentences_CC0.tsv.bz2']):raise ValueError('Changed corpus context preparation')
    with reviews_file.open() as stream:reviews=list(map(json.loads,stream))
    wanted={str(r['sentenceId']) for r in reviews}
    with contexts.open() as stream:leads={(r['sentenceId'],r['word']):r for r in map(json.loads,stream) if r['sentenceId'] in wanted}
    actual={}
    with bz2.open(directory/'eng_sentences_detailed.tsv.bz2','rb') as stream:
        for line in stream:
            values=line.decode('utf-8').rstrip('\r\n').split('\t')
            if len(values)!=6 or values[1]!='eng':raise ValueError('Invalid English corpus row')
            if values[0] in wanted:actual[values[0]]=(values,hashlib.sha256(line).hexdigest())
    cc0=set()
    with bz2.open(directory/'eng_sentences_CC0.tsv.bz2','rt',encoding='utf-8') as stream:
        for line in stream:
            values=line.rstrip('\r\n').split('\t')
            if len(values)!=4 or values[1]!='eng':raise ValueError('Invalid CC0 corpus row')
            if values[0] in wanted:cc0.add((values[0],values[2]))
    selected=[]
    for review in reviews:
        key=str(review['sentenceId']),review['form'].casefold()
        if key not in leads or key[0] not in actual:raise ValueError('Review lacks its complete source sentence')
        context=dict(leads[key]);values,row_sha=actual[key[0]]
        if values!=[context['sentenceId'],context['language'],context['text'],context['owner'],context['added'],context['lastModified']]:
            raise ValueError('Context is not the exact complete source row')
        license='CC0-1.0' if (values[0],values[2]) in cc0 else 'CC-BY-2.0-FR'
        if context['license']!=license or context['sourceSha256']!=PINS['eng_sentences_detailed.tsv.bz2']:
            raise ValueError('Changed sentence license or snapshot')
        context['sourceRowSha256']=row_sha;selected.append((review,context))
    return selected,manifest


def validate(review,context):
    target=review['target'];anchor=review['anchorSurface'];w=context['witness'];text=context['text']
    if (review.get('reviewer')!='implementation_agent' or review.get('englishLaughterUseConfirmed') is not True or
            not review.get('rationale','').strip() or anchor not in ANCHORS or context['language']!='eng' or
            context['sourceSha256']!=PINS['eng_sentences_detailed.tsv.bz2'] or
            hashlib.sha256(text.encode()).hexdigest()!=context['textSha256'] or
            not re.fullmatch(ANCHORS[anchor],target.casefold()) or review['form'].casefold()!=target.casefold() or
            text[w['start']:w['end']]!=target or context['literal']!=target):
        raise ValueError('Laughter review needs an exact English spelling, role confirmation and separate lexical anchor')
    before=text[:w['start']].rstrip();after=text[w['end']:]
    if (before and before[-1] not in '!?.:"“\'' or not after.startswith('!') or
            w['start'] and text[w['start']-1].isalnum() or
            w['end']<len(text) and text[w['end']].isalnum()):
        raise ValueError('The whole spelling must be an independently reviewed exclamation, not a name component')


def attach(model,rows,selected,corrections):
    seen=set();counts=Counter()
    for review,context in selected:
        validate(review,context);target=review['target'];anchor=review['anchorSurface']
        if review['form'] in seen:raise ValueError('Duplicate interpretation review')
        seen.add(review['form']);anchors=[]
        for identity in sorted(model.approved.get(anchor,())):
            key=identity,anchor;members=model.members[key]
            if ('interjection' not in members or 'noun_proper' in members or
                    any(c.startswith(('name_','identifier_','orthography_')) for c in members)):continue
            evidence=[e for e in model.evidence[key] if e['source'] in ROOT_SOURCES and e.get('approved',True)]
            if evidence:anchors.append(dict(lexemeId=identity,surface=anchor,urls=sorted({e['url'] for e in evidence})))
        if not anchors:raise ValueError('Laughter interpretation needs an independently approved English interjection anchor')
        matches=[r for r in rows if r['surface'].casefold()==review['form'].casefold()]
        if not matches:raise ValueError('Review cannot create a new input row')
        key='tatoeba-review-'+hashlib.sha256(json.dumps([context['sentenceId'],target]).encode()).hexdigest()[:24]
        proof=dict(source='reviewed_tatoeba_interjection',approved=True,url=context['url'],sentenceId=context['sentenceId'],
            snapshotSha256=PINS['eng_sentences_detailed.tsv.bz2'],sourceRowSha256=context['sourceRowSha256'],
            sentenceTextSha256=context['textSha256'],languageLabel='eng',owner=context['owner'],license=context['license'],
            lastModified=context['lastModified'],witness=dict(context['witness']),observedSurface=target,
            semanticAnchors=anchors,reviewer='implementation_agent',humanReviewClaimed=False,rationale=review['rationale'],
            preferredCaseClaimed=False,corpusIntentClaimed=False,
            scope='individually reviewed literal English laughter exclamation in a complete pinned public corpus row; separate approved English interjection anchor confirms interpretation, not generated variants or shared lexical identity; no sentence prose, ordinary verb/noun role, morphology, native-speaker review or source endorsement claimed')
        model.add(key,target,target,{'interjection','register_informal'},proof,approved=True)
        for row in matches:
            if row['surface']==target:continue
            if (not row['id'].startswith('tsv:') or row['surface']!=row['surface'].lower() or
                    pipeline.keyboard_reading(target)!=row['reading']):raise ValueError('Cannot invent or normalize a manual/case input')
            prior={r['target']:dict(r) for r in corrections if r['id']==row['id']}
            prior.setdefault(target,dict(id=row['id'],source=row['surface'],target=target,evidence=context['url']))
            if model.approved.get(row['surface']):
                urls=[e['url'] for i in model.approved[row['surface']] for e in model.evidence[i,row['surface']] if e.get('approved',True) and not e.get('requiresFullNamedContext',False)]
                if urls:prior.setdefault(row['surface'],dict(id=row['id'],source=row['surface'],target=row['surface'],evidence=min(urls)))
            corrections[:]=[r for r in corrections if r['id']!=row['id']]
            spelling=any(value.casefold()!=row['surface'].casefold() for value in prior)
            relation=('input_spelling_correction' if len(prior)==1 else 'input_spelling_candidates') if spelling else ('case_correction' if len(prior)==1 else 'case_candidates')
            corrections.extend(dict(r,relation=relation) for _,r in sorted(prior.items()))
        counts['reviewedInterjections']+=1
    return counts


def extend(args):
    selected,meta=load(args.sources,args.reviews)
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    corrections=pipeline.read_table(args.base/'surface-corrections.tsv','corrections')
    counts=attach(model,rows,selected,corrections)
    decisions=pipeline.read_table(args.base/'reviewed-overrides.tsv','decisions');decisions,reopened=resolve_pending.revalidate_machine_reviews(model,decisions,pending,corrections)
    sources['reviewedTatoebaInterjections']=dict(files=PINS,contextsSha256=meta['sha256'],reviewsSha256=pipeline.digest(args.reviews),
        reviewedInterpretations=len(selected),humanReviewClaimed=False,policy='exact complete corpus rows independently matched; explicit English laughter interpretation, independent approved interjection anchor and whole exclamation required; no automatic POS, copied prose, generated repetition variants or inherited inflections')
    for name in ['CC-BY-2.0-FR.html','CC0-1.0.html']:notices['TATOEBA-'+name]=(args.sources/name).read_bytes()
    notices['TATOEBA-REVIEWED-ATTRIBUTION.txt']=('Tatoeba contributors, English weekly export 2026-10-31. https://tatoeba.org/en/downloads\nhttps://downloads.tatoeba.org/exports/per_language/eng/eng_sentences_detailed.tsv.bz2\nCC BY 2.0 FR; separately verified CC0 subset. Per-sentence IDs, owners, licenses, dates and source hashes accompany facts. Changes: individual implementation-agent reviews of exact pre-existing input spellings as English laughter exclamations, not human/native-speaker review. No sentence text, audio or generalized generated variants redistributed. Full license resources retained.\n').encode()
    with tempfile.TemporaryDirectory(prefix='.tatoeba-review-',dir=args.out.parent) as temp:
        p=Path(temp)/'decisions.tsv';pipeline.table(p,'decisions',decisions)
        result=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,reviewed_decisions=p,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,reopenedMachineExclusions=len(reopened),**{k:result[k] for k in ['includedRows','excludedRows','pendingRows']})))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','sources','reviews','out']:p.add_argument('--'+name,type=Path,required=True)
    extend(p.parse_args())
