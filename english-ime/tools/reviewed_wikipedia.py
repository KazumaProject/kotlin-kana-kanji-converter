"""Apply explicit local reviews of pinned English Wikipedia article evidence.

Article titles and search matches are leads, not automatic proper-name or POS
proof. Each review identifies its interpretation, literal spelling, supporting
passage and rationale. Output retains factual identifiers and passage hashes,
never article prose. This module performs no network requests.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import tempfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
import yago_name_variants

REVISION = 'b04c8d1ceb2f5cd4588862100d08de323dccfbaa'
SNAPSHOT = 'a15bc222bef47345c3d0c9feb494f9ac5b6a4285a69b9b9fbef1d0d74188950b'
LICENSE_SHA = '3f941b3b89cf7b8370ceb83cc76d2120d471b58735d8ca60238a751a48d7f72f'
DOMAINS = {'domain_technology','domain_business','domain_science','domain_sports','domain_entertainment',
    'domain_education','domain_medical','domain_food','domain_travel'}
KINDS = {
    'include_lexical_noun': ({'noun'}, {'noun','register_formal','register_informal'} | DOMAINS),
    'include_name': ({'noun','noun_proper'}, {'noun','noun_proper','name_person','name_place','name_organization',
        'name_product','name_brand','name_work','name_fictional','abbreviation'} | DOMAINS),
    'include_abbreviation': ({'abbreviation'}, {'abbreviation'} | DOMAINS),
    'include_phrase': ({'phrase'}, {'phrase','register_informal'} | DOMAINS),
    'include_symbol': ({'symbol'}, {'symbol'} | DOMAINS),
    'include_data_format': ({'identifier_data_format','domain_technology'}, {'identifier_data_format','domain_technology'}),
    'include_command': ({'identifier_command_line','domain_technology'}, {'identifier_command_line','domain_technology'}),
    'include_roman_numeral': ({'numeral','numeral_roman'}, {'numeral','numeral_roman'}),
    'include_taxonomic_name': ({'identifier_taxonomic_name','domain_science'}, {'identifier_taxonomic_name','domain_science'})}
QUALIFIED_TITLE = re.compile(r'(.+) \((disambiguation|surname|given name|name|[\w -]*(?:film|album|song|band|company|software|novel|magazine|newspaper|TV series|video game|character))\)$')


def reviewed_title_context(review, article):
    context=review['contextKind'];title=article['title']
    if context in {'qualified_article_title','qualified_disambiguation_item'}:
        match=QUALIFIED_TITLE.fullmatch(title)
        if not match or review.get('titleQualifier')!=match[2]:
            raise ValueError('Qualified title needs an explicit supported descriptor review')
        title=match[1]
        context='full_article_title' if context=='qualified_article_title' else 'disambiguation_item'
    return title,context


def load_articles(prepared, license_file):
    meta = json.loads((prepared / 'manifest.json').read_text())
    if (meta['schemaVersion'] != 1 or meta['repository'] != 'wikimedia/wikipedia' or meta['revision'] != REVISION or
            meta['config'] != '20231101.en' or meta['sourceSnapshotSha256'] != SNAPSHOT or
            meta['sourceWholeFileSha256IndependentlyVerified'] is not False or
            pipeline.digest(prepared / 'articles.jsonl') != meta['files']['articles.jsonl'] or
            pipeline.digest(license_file) != LICENSE_SHA):
        raise ValueError('Changed Wikipedia preparation, source identity or license')
    articles = {}
    for row in map(json.loads, (prepared / 'articles.jsonl').open()):
        if (row['id'] in articles or not row['url'].startswith('https://en.wikipedia.org/wiki/') or
                hashlib.sha256(row['text'].encode()).hexdigest() != row['textSha256'] or
                row['sourceWholeFileSha256IndependentlyVerified'] is not False or
                not re.fullmatch('[0-9a-f]{64}', row['declaredSourceLfsSha256'])):
            raise ValueError('Changed Wikipedia article evidence')
        articles[row['id']] = row
    if len(articles) != meta['articles']:
        raise ValueError('Incomplete Wikipedia article preparation')
    return articles, meta


def matches_title(target,title):
    # Retain a complete spelling actually present in the passage. Only case,
    # punctuation and decomposable Latin diacritics may distinguish it from
    # the complete article heading; never edit letters or take a title part.
    left=yago_name_variants.ascii_name(target);right=yago_name_variants.ascii_name(title)
    left_reading=pipeline.keyboard_reading(left) if left else None
    right_reading=pipeline.keyboard_reading(right) if right else None
    return target.casefold()==title.casefold() or bool(left_reading and right_reading and left_reading==right_reading)


SUBJECT_PREDICATES=('is','are','was','were','refers','means','became','announced','launched','introduced','joined',
    'won','plays','played','signed','performed','made','released','wrote','designed','developed','produced',
    'supports','offers','provides','had','has','have','began','did','received','moved','would')


def approved_finite_predicates(model):
    """Return independently approved English past/third-person finite forms."""
    result=defaultdict(set)
    for key,form in model.forms.items():
        members=model.members[key];surface=form['surface']
        if (not re.fullmatch('[a-z]+',surface) or not members&{'verb_past','verb_present_3sg'} or
                'noun_proper' in members or any(c.startswith(('name_','identifier_','orthography_')) for c in members) or
                key[0] not in model.approved.get(surface,())):continue
        if any(e['source'] in {'curated_seed','wiktionary','esdb','ngsl_list'} and e.get('approved',True)
                for e in model.evidence[key]):result[surface].add(key[0])
    return result


def validate_review(review, article, predicates=None):
    if (review['reviewer'] != 'implementation_agent' or not review['rationale'].strip() or
            not review['interpretation'].strip() or review['decision'] not in KINDS):
        raise ValueError('Missing explicit Wikipedia interpretation review')
    target = review['target'];members = set(review['categories']);required,allowed = KINDS[review['decision']]
    if not required <= members or not members <= allowed:
        raise ValueError('Wikipedia review cannot infer unrelated POS or inflections')
    if review['decision']=='include_lexical_noun' and review.get('englishLexicalRoleConfirmed') is not True:
        raise ValueError('An ordinary English noun requires an explicit English-usage review')
    witness = review['witness'];start,end = witness['start'],witness['end']
    if not isinstance(start,int) or not isinstance(end,int) or not 0 <= start < end <= len(article['text']):
        raise ValueError('Invalid reviewed Wikipedia passage bounds')
    passage = article['text'][start:end]
    if hashlib.sha256(passage.encode()).hexdigest() != witness['sha256']:
        raise ValueError('Changed reviewed Wikipedia passage')
    if not re.search(r'(?<!\w)' + re.escape(target) + r'(?!\w)', passage):
        raise ValueError('Reviewed passage lacks the literal whole spelling')
    title,context=reviewed_title_context(review,article)
    token=re.escape(target)+r"(?![\w'’/-]|\.[\w])"
    if context=='standalone_sentence_subject':
        before=article['text'][:start]
        match=re.match(r'(?:(?:The|the|A|a|An|an) |(?:The|the) name )?["“]?'+token+r'["”]?\s+([a-z]+)\b',passage)
        if (start and not re.search(r'[.!?]\s+$|\n\s*$',before) or
                re.search(r'\b(?:[A-Za-z]|subsp|ssp|var|sp|St|Dr|Mr|Mrs|Ms|Prof|Rev|Sr|Jr|Mt)\.\s*$',before) or
                not match):
            raise ValueError('A standalone subject needs its real sentence boundary and complete literal label')
        if match[1] not in SUBJECT_PREDICATES:
            proof=review.get('predicateProof') or {}
            if (not isinstance(proof,dict) or predicates is None or proof.get('surface')!=match[1] or
                    proof.get('lexemeId') not in predicates.get(match[1],())):
                raise ValueError('A new finite predicate requires independently approved English lexical evidence')
    elif context=='explicit_complete_alias':
        if (start and article['text'][start-1].isalnum() or
                not re.match(r'(?:known(?: simply)? as|called|named)\s+["“]?'+token+r'["”]?(?:[.,;:)]|\s+(?:is|are|was|were)\b)',passage)):
            raise ValueError('An explicit alias needs a complete lower-case prose cue, not a compound or longer work title')
    elif context == 'full_article_title':
        if not matches_title(target,title):
            raise ValueError('A title component does not establish a standalone name')
    elif context == 'disambiguation_item':
        if not matches_title(target,title) or not re.match(r'["“]?' + re.escape(target) + r'["”]?(?:\s*\(|\s*,|\s*[–—])', passage):
            raise ValueError('Disambiguation evidence is only part of a longer name')
    else:
        raise ValueError('Unsupported Wikipedia passage context')
    return members


def attach(model, rows, articles, reviews, corrections):
    predicates=approved_finite_predicates(model) if any(r.get('predicateProof') for r in reviews) else None
    by_form = defaultdict(list)
    for row in rows:
        by_form[row['surface'].casefold()].append(row)
    seen = set();counts = Counter()
    for review in reviews:
        article = articles[review['articleId']]
        members = validate_review(review, article,predicates)
        token = review['articleId'],review['target'],review['interpretation']
        if token in seen:
            raise ValueError('Duplicate Wikipedia interpretation review')
        seen.add(token)
        target = review['target'];alias = yago_name_variants.ascii_name(target)
        title,_=reviewed_title_context(review,article)
        selected = list(by_form[target.casefold()])
        if target.casefold()!=title.casefold() and matches_title(target,title):
            selected += by_form[title.casefold()]
        if alias and alias != target:
            selected += by_form[alias.casefold()]
        if ' ' in target:
            selected += [row for row in by_form[target.replace(' ','').casefold()] if row['id'].startswith('manual:')]
        if not selected:
            continue
        extension.ensure_categories(model, members)
        key = 'wikipedia-reviewed-' + hashlib.sha256(json.dumps([review['articleId'],review['interpretation']]).encode()).hexdigest()[:24]
        proof = dict(source='reviewed_wikipedia', url=article['url'], approved=True, reviewer='implementation_agent',
            humanReviewClaimed=False, sourceRevision=REVISION, sourceConfig='20231101.en', articleId=article['id'],
            articleTitle=article['title'], articleTextSha256=article['textSha256'], sourceShard=article['shard'],
            rowGroup=article['rowGroup'], rowIndexInGroup=article['rowIndexInGroup'],
            declaredSourceLfsSha256=article['declaredSourceLfsSha256'], sourceWholeFileSha256IndependentlyVerified=False,
            reviewedPassage=review['witness'], contextKind=review['contextKind'], interpretation=review['interpretation'],
            predicateProof=review.get('predicateProof'),
            reviewedTitleQualifier=review.get('titleQualifier'),
            rationale=review['rationale'], preferredCaseClaimed=False,
            englishLexicalRoleConfirmed=review.get('englishLexicalRoleConfirmed',False),
            scope='explicitly reviewed English-context name, ordinary English noun, abbreviation, symbol, phrase, numeral or taxonomic identifier; no title-only POS inference, inherited morphology, source endorsement, corpus intent or current availability claim; article prose is not redistributed')
        lemma=review.get('lemma',target)
        model.add(key,lemma,target,members,proof,approved=True)
        for row in selected:
            surface = row['surface'];effective = target
            if alias and alias!=target and surface.isascii() and pipeline.keyboard_reading(alias)==row['reading']:
                effective = alias
                model.add(key,lemma,alias,members,dict(proof,relation='derived_existing_latin_diacritic_input_alias',
                    preferredAsciiSpellingClaimed=False),approved=True)
            if surface == effective and not any(c['id']==row['id'] for c in corrections):
                continue
            if row['id'].startswith('manual:') and review['decision']=='include_name':
                model.add(key,lemma,surface,members,dict(proof,relation='existing_manual_case_or_space_free_alias',
                    legacySourceId=row['id'],originalSurface=surface),approved=True)
                continue
            if row['id'].startswith('manual:') and surface!=surface.lower():
                # Programming, notation and other identifiers can be case
                # sensitive. An unrelated manual casing is not attestation.
                continue
            if surface != surface.lower() or pipeline.keyboard_reading(effective) != row['reading']:
                raise ValueError('Wikipedia review cannot invent an input mapping: '+repr((row['id'],surface,row['reading'],effective)))
            existing = {r['target']:dict(r) for r in corrections if r['id'] == row['id']}
            existing.setdefault(effective,dict(id=row['id'],source=surface,target=effective,evidence=proof['url']))
            if model.approved.get(surface):
                original = [e['url'] for k in model.approved[surface] for e in model.evidence[k,surface]
                    if e.get('approved',True) and not e.get('requiresFullNamedContext',False)]
                if original:
                    existing.setdefault(surface,dict(id=row['id'],source=surface,target=surface,evidence=min(original)))
            corrections[:] = [r for r in corrections if r['id'] != row['id']]
            spelling = any(value.casefold() != surface.casefold() for value in existing)
            relation = ('input_spelling_correction' if len(existing)==1 else 'input_spelling_candidates') if spelling else ('case_correction' if len(existing)==1 else 'case_candidates')
            corrections += [dict(value,relation=relation) for _,value in sorted(existing.items())]
        counts[review['decision']] += 1
    return counts


def extend(args):
    articles,meta = load_articles(args.prepared,args.license)
    reviews = list(map(json.loads,args.reviews.open()))
    model,rows,sources,notices,pending = extension.load_base(args.base,args.seed)
    if pipeline.digest(args.base/'inventory.jsonl') != meta['inventorySha256']:
        raise ValueError('Wikipedia preparation belongs to another source inventory')
    prior = args.base/'surface-corrections.tsv';corrections = pipeline.read_table(prior,'corrections') if prior.is_file() else []
    counts = attach(model,rows,articles,reviews,corrections)
    prior = args.base/'reviewed-overrides.tsv';decisions = pipeline.read_table(prior,'decisions') if prior.is_file() else []
    decisions,reopened = resolve_pending.revalidate_machine_reviews(model,decisions,pending,corrections)
    prior_batch=sources.get('reviewedEnglishWikipedia')
    batch = dict(revision=REVISION,config='20231101.en',sourceSnapshotSha256=SNAPSHOT,
        preparedManifestSha256=pipeline.digest(args.prepared/'manifest.json'),reviewsSha256=pipeline.digest(args.reviews),
        researchArticles=meta['articles'],explicitInterpretationReviews=len(reviews),
        humanReviewClaimed=False,sourceWholeFileSha256IndependentlyVerified=False,
        policy='individual exact-passage reviews only; complete-title matches never automatically assign name/POS, interpretation boundaries remain separate, no source prose exported')
    batches=list(prior_batch.get('batches',[prior_batch])) if prior_batch else []
    if batch not in batches:batches.append(batch)
    sources['reviewedEnglishWikipedia']=dict(batch,batches=batches)
    notices['ENGLISH-WIKIPEDIA-REVIEWED-NOTICE.txt'] = (
        'English Wikipedia contributors, dump 2023-11-01; wikimedia/wikipedia on Hugging Face, revision '+REVISION+'.\n'
        'https://huggingface.co/datasets/wikimedia/wikipedia ; individual source page URLs and article IDs are retained with facts.\n'
        'CC BY-SA 3.0, full license retained separately. Dataset card and original article research text retained in the source preparation.\n'
        'Changes: select literal name/token facts for existing input rows; explicitly reviewed classifications and source/passage hashes; no article prose, artwork or other biographical facts redistributed. Implementation-agent reviews, not human review or source endorsement.\n').encode()
    notices['CC-BY-SA-3.0.txt'] = args.license.read_bytes()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.wikipedia-reviews-',dir=args.out.parent) as temp:
        reviewed=Path(temp)/'reviews.tsv';pipeline.table(reviewed,'decisions',decisions)
        summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,
            reviewed_decisions=reviewed,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,reopenedMachineExclusions=len(reopened),**{key:summary[key] for key in ['includedRows','excludedRows','pendingRows']})))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['base','seed','prepared','reviews','license','out']:
        parser.add_argument('--'+key,type=Path,required=True)
    extend(parser.parse_args())
