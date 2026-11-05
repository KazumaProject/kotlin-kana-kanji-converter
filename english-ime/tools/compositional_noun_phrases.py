"""Analyze existing manual noun labels using independently verified constituents.

A productive noun phrase is separate from a source-attested fixed expression.
The rule does not invent terms, classify names from capitalization, interpret
commands as prose, or infer countability, lexicalized meaning or inflections.
"""
import argparse,hashlib,json,re
from collections import Counter,defaultdict
from pathlib import Path
import extend_lexicon as extension
import lexicon_pipeline as pipeline
import manual_aliases
import tldr_commands as tldr
import resolve_wiktionary as resolver
from wiktionary_index import Index, SNAPSHOT_SHA256

GRAMMAR='https://learnenglish.britishcouncil.org/free-resources/grammar/english-grammar-reference/noun-phrases'
SOURCES={'curated_seed','wiktionary','esdb','ngsl_list'}


def constituents(model):
    words=defaultdict(list);numbers=set()
    for key,form in model.forms.items():
        surface=form['surface'];members=model.members[key]
        if 'numeral' in members:numbers.add(surface)
        if not re.fullmatch('[a-z]+(?:-[a-z]+)*',surface) or key[0] not in model.approved[surface]:continue
        if members&{'noun_proper','abbreviation','contraction'} or any(v.startswith(('name_','identifier_','orthography_')) for v in members):continue
        roles=members&{'noun','adjective'}
        if 'adjective_predicative' in members and 'adjective_attributive' not in members:roles.discard('adjective')
        source=next((e for e in model.evidence[key] if e['source'] in SOURCES and e.get('approved',True)),None)
        if roles and source:words[surface].append({'lexemeId':key[0],'lemma':form['lemma'],'roles':sorted(roles),'evidence':source})
    return words,numbers


def attach(model,rows,pending_ids,command_roots,literals,reviews=()):
    extension.ensure_categories(model,{'phrase_noun_compositional'})
    words,numbers=constituents(model);counts=Counter();reviewed={}
    originals={row['id']:row for row in rows}
    for review in reviews:
        row=originals[review['id']];tokens=review['analysis']
        if (row['id'] in reviewed or not row['id'].startswith('manual:') or
                review['reviewer']!='implementation_agent' or not review['rationale'].strip() or
                any(row[k]!=review[k] for k in ['id','surface','reading','cost']) or
                not isinstance(tokens,list) or len(tokens)<2 or len(tokens)>5 or
                not all(re.fullmatch('[a-z]+(?:-[a-z]+)*',word) for word in tokens) or
                ' '.join(tokens).replace('-',' ')!=row['surface'].lower()):
            raise ValueError('Compositional review must retain original literal words and explicit boundaries')
        reviewed[row['id']]=review
    for row in rows:
        surface=row['surface']
        if row['id'] not in pending_ids or not row['id'].startswith('manual:') or not re.fullmatch(r'[A-Z]?[a-z]+(?: [A-Z]?[a-z]+){1,5}',surface):continue
        review=reviewed.get(row['id']);tokens=review['analysis'] if review else surface.lower().split(' ')
        # Capitalized labels can be products made from ordinary English words.
        # Their unrelated lower-case senses cannot automatically establish the
        # label's intended constituent analysis (Material You, for example).
        if surface!=surface.lower() and not review:continue
        if (not review and tokens[0] in command_roots) or any(token in numbers for token in tokens[:-1]):continue
        literal=(row['reading'],surface,row['cost'])
        if literal not in literals:continue
        evidence=[words[word] for word in tokens]
        if not all(evidence) or not any('noun' in e['roles'] for e in evidence[-1]):
            if review:raise ValueError('Explicit phrase analysis lacks independently approved constituents or noun head')
            continue
        # Every non-head has an independently supported noun/adjective use;
        # the head is a noun, with no invented whole-phrase lexical attestation.
        canonical=' '.join(tokens);key='manual-noun-phrase-'+hashlib.sha256(canonical.encode()).hexdigest()[:24]
        url='https://github.com/KazumaProject/kotlin-kana-kanji-converter/blob/'+manual_aliases.REVISION+'/english-ime/src/main/kotlin/Manual.kt#L'+str(literals[literal])
        proof={'source':'compositional_manual_noun_phrase','url':url,'legacySourceId':row['id'],'manualSourceSha256':manual_aliases.MANUAL_SHA256,
            'grammarReference':GRAMMAR,'constituents':evidence,'nounHead':tokens[-1],'approved':True,
            'originalSurface':surface,'analysis':tokens,'explicitReview':review,'humanReviewClaimed':False,
            'wholePhraseAttestedInExternalLexiconClaimed':False,'lexicalizedMeaningClaimed':False,
            'scope':'existing literal lowercase or sentence/title-case manual label analyzed as noun/adjective premodifiers plus an independently verified noun head; original spaces preserved, compound-hyphen boundaries and command-root ambiguity require separate explicit reviews; numeric modifiers excluded; productive phrase, not an asserted fixed expression, vendor name, technical standard, countability or inflection'}
        model.add(key,canonical,canonical,{'noun','phrase_noun_compositional'},dict(proof,relation='canonical_compositional_analysis'),approved=True)
        model.add(key,canonical,surface,{'noun','phrase_noun_compositional'},proof,approved=True);counts['existingCompositionalPhrases']+=1
    return counts


def extend(args):
    if pipeline.digest(args.manual_source)!=manual_aliases.MANUAL_SHA256:raise ValueError('Changed manual source')
    literals=manual_aliases.literal_mappings(args.manual_source)
    files=tldr.load(args.tldr);roots=set()
    for name in files:
        if name.startswith('pages/common/'):
            title=(args.tldr/name).read_text().splitlines()[0]
            if title.startswith('# '):roots.add(title[2:].split(' ')[0])
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    states=list(map(json.loads,(args.base/'status.jsonl').open()));ids={r['id'] for r in states if r['decision']=='pending'}
    reviews=list(map(json.loads,args.reviews.open())) if args.reviews else []
    if reviews and args.index:
        wanted={word for review in reviews for word in review['analysis']}
        index=Index(args.index)
        try:records=resolver.load_closure(index,wanted)
        finally:index.close()
        resolver.import_records(model,records,wanted,pending,bootstrap_approved=True)
    counts=attach(model,rows,ids,roots,literals,reviews)
    sources['compositionalManualNounPhrases']={'manualSourceSha256':manual_aliases.MANUAL_SHA256,'tldrRevision':tldr.REVISION,'grammarReference':GRAMMAR,
        'reviewsSha256':pipeline.digest(args.reviews) if args.reviews else None,
        'reviewConstituentSnapshotSha256':SNAPSHOT_SHA256 if reviews and args.index else None,
        'policy':'existing literal manual labels only, no inferred camel-case boundaries; independently approved ordinary English noun/adjective constituents and noun head; title/sentence-case labels, compound-hyphen analysis or command-root ambiguity require explicit original-row review, no numeric modifier; separate productive noun-phrase category, no claim of externally attested fixed expression, lexicalized meaning, technical standard, countability or inflection'}
    notices['COMPOSITIONAL-NOUN-PHRASE-REFERENCE.txt']=('Grammar reference: British Council LearnEnglish, Noun phrases: '+GRAMMAR+'\nOnly the general linguistic premodifier/head relation is used; no grammar-page prose, examples or exercises are copied. Existing manual labels, independently approved constituent senses and original source lines are retained as evidence. A productive composition is not represented as an externally attested fixed lexical expression or technical-standard definition.\n').encode()
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    prior=args.base/'reviewed-overrides.tsv'
    summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,**{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','tldr','manual-source','out']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--reviews',type=Path,help='Explicit original-row constituent/hyphen reviews')
    parser.add_argument('--index',type=Path,help='Pinned English index for explicitly reviewed constituent heads')
    extend(parser.parse_args())
