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
from wiktionary_index import Index, SNAPSHOT_SHA256 as WIKTIONARY_SNAPSHOT

REVISION = 'b04c8d1ceb2f5cd4588862100d08de323dccfbaa'
SNAPSHOT = 'a15bc222bef47345c3d0c9feb494f9ac5b6a4285a69b9b9fbef1d0d74188950b'
LICENSE_SHA = '3f941b3b89cf7b8370ceb83cc76d2120d471b58735d8ca60238a751a48d7f72f'
DOMAINS = {'domain_technology','domain_business','domain_science','domain_sports','domain_entertainment',
    'domain_education','domain_medical','domain_food','domain_travel'}
KINDS = {
    'include_lexical_noun': ({'noun'}, {'noun','register_formal','register_informal'} | DOMAINS),
    'include_lexical_adjective': ({'adjective'}, {'adjective','register_formal','register_informal'} | DOMAINS),
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
    # A terminal bang can have semantic force in a pseudonym. Its keyboard
    # transcription needs an explicit reviewed input mapping, not title repair.
    if target.casefold()!=title.casefold() and ('!' in target or '!' in title):return False
    left=yago_name_variants.ascii_name(target);right=yago_name_variants.ascii_name(title)
    left_reading=pipeline.keyboard_reading(left) if left else None
    right_reading=pipeline.keyboard_reading(right) if right else None
    return target.casefold()==title.casefold() or bool(left_reading and right_reading and left_reading==right_reading)


SUBJECT_PREDICATES=('is','are','was','were','refers','means','became','announced','launched','introduced','joined',
    'won','plays','played','signed','performed','made','released','wrote','designed','developed','produced',
    'supports','offers','provides','had','has','have','began','did','received','moved','would','will')


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


def approved_nominal_modifiers(model):
    """Independently verified English adjective/participle modifiers only."""
    result=defaultdict(set)
    for key,form in model.forms.items():
        members=model.members[key];surface=form['surface']
        if (not re.fullmatch('[a-z]+',surface) or not members&{'adjective','verb_past_participle'} or
                'noun_proper' in members or any(c.startswith(('name_','identifier_','orthography_')) for c in members) or
                key[0] not in model.approved.get(surface,())):continue
        if any(e['source'] in {'curated_seed','wiktionary','esdb','ngsl_list'} and e.get('approved',True)
                for e in model.evidence[key]):result[surface].add(key[0])
    return result


def approved_noun_heads(model):
    """Independent ordinary English noun evidence for reviewed modifiers."""
    result=defaultdict(set)
    for key,form in model.forms.items():
        members=model.members[key];surface=form['surface']
        if (not re.fullmatch('[a-z]+',surface) or 'noun' not in members or
                'noun_proper' in members or any(c.startswith(('name_','identifier_','orthography_')) for c in members) or
                key[0] not in model.approved.get(surface,())):continue
        if any(e['source'] in {'curated_seed','wiktionary','esdb','ngsl_list'} and e.get('approved',True)
                for e in model.evidence[key]):result[surface].add(key[0])
    return result


def verified_person_name_roles(index, words):
    """Read actual unrestricted English given-name/surname sense categories."""
    import resolve_wiktionary
    result={}
    for number,entry in index.lookup(words):
        for ordinal,sense in enumerate(entry.get('senses',[])):
            if not resolve_wiktionary.eligible(entry,sense):continue
            for role,category in [('given','English given names'),('family','English surnames')]:
                if category in sense.get('categories',[]):
                    proof=dict(surface=entry['word'],role=role,entryId=number,senseIndex=ordinal,snapshotSha256=WIKTIONARY_SNAPSHOT)
                    result[entry['word'],role,number,ordinal]=proof
    return result


def verified_census_family_roles(directory, words):
    """Use actual pinned aggregate surname rows, never a given-name guess."""
    import census_surnames
    values,csv_sha=census_surnames.load(directory);by_name={r['name']:r for r in values};result={}
    for surface in words:
        row=by_name.get(surface.upper())
        if not row:continue
        proof=dict(surface=surface,role='family',entryId=row['rank'],senseIndex=0,
            source='census_surname',snapshotSha256=csv_sha,archiveSha256=census_surnames.ARCHIVE_SHA,
            sourceSurname=row['name'],count=row['count'],url=census_surnames.URL+'#Names_2010Census.csv',
            casingSource='literal spelling in the separately pinned English article; Census surname identity is uppercase',
            demographicsOrSpecificPersonClaimed=False)
        result[surface,'family',row['rank'],0]=proof
    return result


def validate_review(review, article, predicates=None, modifiers=None, name_roles=None, noun_heads=None):
    if (review['reviewer'] != 'implementation_agent' or not review['rationale'].strip() or
            not review['interpretation'].strip() or review['decision'] not in KINDS):
        raise ValueError('Missing explicit Wikipedia interpretation review')
    target = review['target'];members = set(review['categories']);required,allowed = KINDS[review['decision']]
    if not required <= members or not members <= allowed:
        raise ValueError('Wikipedia review cannot infer unrelated POS or inflections')
    if review['decision'].startswith('include_lexical_') and review.get('englishLexicalRoleConfirmed') is not True:
        raise ValueError('An ordinary English lexical role requires an explicit English-usage review')
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
        months='January|February|March|April|May|June|July|August|September|October|November|December'
        date=r'(?:In (?:(?:'+months+r') )?[1-9][0-9]{3},\s+)?'
        match=re.match(date+r'(?:(?:The|the|A|a|An|an) |(?:The|the) name )?["“]?'+token+r'["”]?\s+([a-z]+)\b',passage)
        if (start and not re.search(r'[.!?]\s+$|\n\s*$',before) or
                re.search(r'\b(?:[A-Za-z]|subsp|ssp|var|sp|St|Dr|Mr|Mrs|Ms|Prof|Rev|Sr|Jr|Mt)\.\s*$',before) or
                not match):
            raise ValueError('A standalone subject needs its real sentence boundary and complete literal label')
        if match[1] not in SUBJECT_PREDICATES:
            proof=review.get('predicateProof') or {}
            if (not isinstance(proof,dict) or predicates is None or proof.get('surface')!=match[1] or
                    proof.get('lexemeId') not in predicates.get(match[1],())):
                raise ValueError('A new finite predicate requires independently approved English lexical evidence')
    elif context=='quoted_sentence_subject':
        before=article['text'][:start]
        match=re.fullmatch(r'["“]'+token+r'\s+([a-z]+)\b[^"“”]*["”]',passage)
        if (review['decision']!='include_name' or review.get('englishQuotationConfirmed') is not True or
                not re.search(r'\b(?:said|wrote)(?: that)?[: ,]?\s*$',before) or
                not match or match[1] not in SUBJECT_PREDICATES):
            raise ValueError('A quoted subject needs a complete explicitly reviewed English quotation and reporting cue')
    elif context=='complete_nominal_reference':
        if (review['decision']!='include_name' or review.get('completeNominalReferenceConfirmed') is not True or
                start and article['text'][start-1].isalnum() or
                not re.match(r'(?:by|of|from|to|as|for|with|about|under|in)\s+(?:(?:the|The|just)\s+)?'+token+
                    r'(?=[,.;:)]|\s+(?:(?:in|since|until) [1-9][0-9]{3}\b|(?:is|was|are|were|has|had|have|came)\b))',passage)):
            raise ValueError('A nominal reference needs its complete prepositional name and explicit English-context review')
    elif context=='complete_name_genitive_reference':
        if (review['decision']!='include_name' or review.get('nameGenitiveConfirmed') is not True or
                start and article['text'][start-1].isalnum() or
                not re.match(r'(?:by|of|from|to|for|with|about|under|in)\s+(?:(?:the|The)\s+)?'+
                    re.escape(target)+r"['’]s\s+[a-z]+\b",passage)):
            raise ValueError('A named genitive needs its complete prepositional name and explicit independent-name review')
    elif context=='comma_prefaced_name_subject':
        before=article['text'][:start];match=re.match(token+r'\s+([a-z]+)\b',passage)
        confirmation='prefacedNameSubjectConfirmed' if review['decision']=='include_name' else 'prefacedLexicalSubjectConfirmed'
        if (review['decision'] not in {'include_name','include_lexical_noun'} or review.get(confirmation) is not True or
                not re.search(r',\s+$',before) or not match):
            raise ValueError('A prefaced name subject needs a complete finite name clause after the comma')
        if match[1] not in SUBJECT_PREDICATES:
            proof=review.get('predicateProof') or {}
            if (not isinstance(proof,dict) or predicates is None or proof.get('surface')!=match[1] or
                    proof.get('lexemeId') not in predicates.get(match[1],())):
                raise ValueError('A prefaced name predicate needs independently approved English lexical evidence')
    elif context=='complete_english_noun_phrase':
        match=re.match(r'(?:a|an|the|A|An|The) ([a-z]+) '+token+r'(?=[,.;:)])',passage)
        proof=review.get('modifierProof') or {}
        if (review['decision']!='include_lexical_noun' or start and article['text'][start-1].isalnum() or
                not match or not isinstance(proof,dict) or modifiers is None or proof.get('surface')!=match[1] or
                proof.get('lexemeId') not in modifiers.get(match[1],())):
            raise ValueError('A complete English noun phrase needs an independently verified modifier and whole noun head')
    elif context=='complete_determined_noun_head':
        if (review['decision'] not in {'include_lexical_noun','include_name'} or
                review['decision']=='include_name' and review.get('completeNominalReferenceConfirmed') is not True or
                start and article['text'][start-1].isalnum() or
                not re.match(r'(?:[Aa]n?|[Aa]nother|[Tt]he|[Tt]hese|[Tt]hose|[Hh]is|[Hh]er|[Tt]heir|[Ii]ts) '+token+
                    r'(?=[,.;:)]|["”][,.;:)]|\s+(?:who|which|that|is|was|are|were|can|could|would|will)\b)',passage)):
            raise ValueError('A determined head needs its whole noun and an explicit English lexical-role or independent-name review')
    elif context=='article_title_initialism':
        initials=''.join(word[0] for word in re.findall(r'[A-Za-z]+',article['title'])).upper()
        before=article['text'][:start]
        boundary=not start or re.search(r'[.!?]\s+$|\n\s*$|\b(?:the same|that|this) (?:day|month|year|time)\s+$',before)
        if (review['decision'] not in {'include_name','include_abbreviation'} or
                review.get('titleInitialismConfirmed') is not True or not re.fullmatch('[A-Z]{2,12}',target) or
                target!=initials or not boundary or
                not re.match(token+r'\s+(?:is|was|are|were|has|had|will|would)\b',passage)):
            raise ValueError('A title initialism needs exact title initials and a reviewed complete finite subject')
    elif context=='recorded_work_list_item':
        before=article['text'][:start]
        if (review['decision']!='include_name' or 'name_work' not in members or
                review.get('recordedWorkItemConfirmed') is not True or
                not re.search(r'\nRecordings[ \t]*\n',before) or not re.search(r';[ \t]+$',before) or
                not re.match(token+r';(?=\s)',passage)):
            raise ValueError('A recorded work needs its full independently printed semicolon-delimited list item')
    elif context=='reviewed_english_noun_modifier':
        match=re.match(token+r" ([a-z]+)(?![\w'’/-])(?=[,.;:)]|\s+(?:of|in|with|from|for|to)\b)",passage)
        proof=review.get('nounHeadProof') or {}
        if (review['decision']!='include_lexical_adjective' or start and article['text'][start-1].isalnum() or
                not match or not isinstance(proof,dict) or noun_heads is None or proof.get('surface')!=match[1] or
                proof.get('lexemeId') not in noun_heads.get(match[1],())):
            raise ValueError('An English adjective review needs its complete independently approved ordinary noun head')
    elif context=='named_classifier_phrase':
        classes={'controller':{'name_product'},'series':{'name_product','name_work','name_brand'},
                 'company':{'name_organization'},'band':{'name_organization'},'newspaper':{'name_work'},
                 'family':{'name_person','name_fictional'},'brand':{'name_brand'}}
        match=re.match(r'(?:(the|The) )?'+token+r' ([a-z]+|Series)(?=[,.;:)]|\s+(?:is|are|was|were|has|have|had)\b)',passage)
        before=article['text'][:start]
        if (review['decision']!='include_name' or review.get('namedClassifierConfirmed') is not True or
                start and article['text'][start-1].isalnum() or not match or
                not match[1] and start and not re.search(r'[.!?]\s+$|\n\s*$',before) or
                not match[1] and re.search(r'\b(?:[A-Za-z]|St|Dr|Mr|Mrs|Ms|Prof|Rev|Sr|Jr)\.\s*$',before) or
                not members&classes.get(match[2].lower(),set())):
            raise ValueError('A named classifier phrase needs a complete unqualified name and explicit entity-class review')
    elif context=='explicit_pseudonym_item':
        before=article['text'][:start]
        if (review['decision']!='include_name' or members-({'noun','noun_proper','name_person'}|DOMAINS) or
                'name_person' not in members or review.get('pseudonymConfirmed') is not True or
                start and not re.search(r'\n[ \t]*$',before) or
                not re.match(token+r', pseudonym for (?:an? |the )?(?:[A-Z][\w-]* )*(?:artist|writer|musician|actor|performer)\b',passage)):
            raise ValueError('A pseudonym needs a complete literal list item and explicit personal-name review')
    elif context=='verified_personal_name_unit':
        proof=review.get('counterpartNameProof') or {};role=review.get('personalNameUnitRole')
        if (start!=0 or review['decision']!='include_name' or 'name_person' not in members or
                review.get('personalNameStructureConfirmed') is not True or not isinstance(proof,dict) or
                role not in {'given','family'} or name_roles is None or
                not members <= {'noun','noun_proper','name_person'}|DOMAINS or
                not isinstance(proof.get('surface'),str) or not isinstance(proof.get('role'),str) or
                type(proof.get('entryId')) is not int or type(proof.get('senseIndex')) is not int):
            raise ValueError('A personal name unit needs an explicit full-name structure and independent counterpart role')
        identity=proof.get('surface'),proof.get('role'),proof.get('entryId'),proof.get('senseIndex')
        order=review.get('personalNameOrder','given_family')
        if (proof!=name_roles.get(identity) or proof.get('role')==role or
                order not in {'given_family','family_given'} or
                order=='family_given' and review.get('familyFirstNameStructureConfirmed') is not True or
                not re.fullmatch(r'[A-Z][a-zA-Z]+(?:-[a-zA-Z]+)*',target) or
                not re.fullmatch(r'[A-Z][a-zA-Z]+',proof.get('surface',''))):
            raise ValueError('A name counterpart must have the actual opposite English name role')
        # Exactly two whole name units, optionally with explicit middle initials.
        # A whole hyphenated unit is retained. Never admit one of its pieces.
        first_role='given' if order=='given_family' else 'family'
        first,last=(re.escape(target),re.escape(proof['surface'])) if role==first_role else (re.escape(proof['surface']),re.escape(target))
        middle=r'(?:[A-Z]\. )*' if order=='given_family' else ''
        if not re.match(first+' '+middle+last+r"(?![\w'’/-])(?:\s*(?=[(,])|\s+(?=(?:is|was)\b))",passage):
            raise ValueError('A reviewed personal name cannot clip a larger or hyphenated full name')
    elif context=='explicit_complete_alias':
        if (start and article['text'][start-1].isalnum() or
                not re.match(r'(?:known(?: simply)? as|called|named|nicknamed)\s+["“]?'+token+r'["”]?(?:[.,;:)]|\s+(?:is|are|was|were)\b)',passage)):
            raise ValueError('An explicit alias needs a complete lower-case prose cue, not a compound or longer work title')
    elif context=='explicit_named_object_reference':
        if (review['decision']!='include_name' or review.get('explicitNamingConfirmed') is not True or
                start and article['text'][start-1].isalnum() or
                not re.match(r'names it '+token+r'(?=[,.;:)])',passage)):
            raise ValueError('A named object needs an explicit complete English naming clause')
    elif context=='explicit_brand_name':
        if (review['decision']!='include_name' or 'name_brand' not in members or
                review.get('brandNameConfirmed') is not True or
                start and article['text'][start-1].isalnum() or
                not re.match(r'brand name '+token+r'(?=[,.;:)]| among others[,.;:)])',passage)):
            raise ValueError('A brand name needs an explicit complete brand-label cue and reviewed identity')
    elif context=='explicit_personal_nickname_list':
        match=re.match(r'known by (?:his|her|their) nicknames? ((?:["“][^"“”\n]+["”](?:, | or | and ))*["“][^"“”\n]+["”])(?=[,.;:]|\s*\()',passage)
        labels=re.findall(r'["“]([^"“”\n]+)["”]',match[1]) if match else []
        if (review['decision']!='include_name' or 'name_person' not in members or
                review.get('personalNicknameConfirmed') is not True or
                start and article['text'][start-1].isalnum() or target not in labels):
            raise ValueError('A personal nickname needs its whole quoted label and explicit personal-name cue')
    elif context=='titled_person_reference':
        before=article['text'][:start]
        if (review['decision']!='include_name' or not members&{'name_person','name_fictional'} or
                review.get('titledNameConfirmed') is not True or
                start and not re.search(r'[,;:.!?]\s+$|\n\s*$',before) or
                not re.match(r'(?:Ser|Sir|Dame|Lord|Lady) '+token+r'\s+(?:is|was|has|had)\b',passage)):
            raise ValueError('A titled person reference needs a complete label and independent finite clause')
    elif context=='quoted_personal_nickname':
        name_word=r"[A-Z][\w’'.-]*"
        pattern=(r'(?:'+name_word+r' ){1,6}["“]'+re.escape(target)+r'["”] '
                 +name_word+r'(?: '+name_word+r'){0,5}\s*(?:\(|,)')
        if (start!=0 or review['decision']!='include_name' or 'name_person' not in members or
                review.get('personalNicknameConfirmed') is not True or not re.match(pattern,passage)):
            raise ValueError('A quoted nickname needs an explicitly reviewed complete personal-name lead')
    elif context=='explicit_fictional_name_apposition':
        if (review['decision']!='include_name' or 'name_fictional' not in members or
                review.get('fictionalNameConfirmed') is not True or start and article['text'][start-1].isalnum() or
                not re.match(r'(?:the|a) (?:titular )?(?:monster|character), (?:the )?'+token+r',',passage)):
            raise ValueError('A fictional name apposition needs an explicit complete entity label and interpretation')
    elif context == 'full_article_title':
        if not matches_title(target,title):
            raise ValueError('A title component does not establish a standalone name')
    elif context == 'disambiguation_item':
        if not matches_title(target,title) or not re.match(r'["“]?' + re.escape(target) + r'["”]?(?:\s*\(|\s*,|\s*[–—])', passage):
            raise ValueError('Disambiguation evidence is only part of a longer name')
    else:
        raise ValueError('Unsupported Wikipedia passage context')
    return members


def attach(model, rows, articles, reviews, corrections, name_roles=None):
    predicates=approved_finite_predicates(model) if any(r.get('predicateProof') for r in reviews) else None
    modifiers=approved_nominal_modifiers(model) if any(r.get('contextKind')=='complete_english_noun_phrase' for r in reviews) else None
    noun_heads=approved_noun_heads(model) if any(r.get('nounHeadProof') for r in reviews) else None
    by_form = defaultdict(list)
    for row in rows:
        by_form[row['surface'].casefold()].append(row)
    seen = set();counts = Counter()
    for review in reviews:
        article = articles[review['articleId']]
        members = validate_review(review, article,predicates,modifiers,name_roles,noun_heads)
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
        if review.get('normalizedInputConfirmed') is True:
            reading=pipeline.keyboard_reading(target)
            if not reading:raise ValueError('Normalized input needs a declared punctuation transcription')
            selected += [row for row in by_form[reading] if row['surface']==reading and row['reading']==reading]
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
            personalNicknameConfirmed=review.get('personalNicknameConfirmed',False),
            brandNameConfirmed=review.get('brandNameConfirmed',False),
            explicitNamingConfirmed=review.get('explicitNamingConfirmed',False),
            titledNameConfirmed=review.get('titledNameConfirmed',False),
            fictionalNameConfirmed=review.get('fictionalNameConfirmed',False),
            englishQuotationConfirmed=review.get('englishQuotationConfirmed',False),
            completeNominalReferenceConfirmed=review.get('completeNominalReferenceConfirmed',False),
            titleInitialismConfirmed=review.get('titleInitialismConfirmed',False),
            recordedWorkItemConfirmed=review.get('recordedWorkItemConfirmed',False),
            nameGenitiveConfirmed=review.get('nameGenitiveConfirmed',False),
            prefacedNameSubjectConfirmed=review.get('prefacedNameSubjectConfirmed',False),
            prefacedLexicalSubjectConfirmed=review.get('prefacedLexicalSubjectConfirmed',False),
            modifierProof=review.get('modifierProof'),
            nounHeadProof=review.get('nounHeadProof'),
            namedClassifierConfirmed=review.get('namedClassifierConfirmed',False),
            counterpartNameProof=review.get('counterpartNameProof'),
            personalNameUnitRole=review.get('personalNameUnitRole'),
            personalNameStructureConfirmed=review.get('personalNameStructureConfirmed',False),
            personalNameOrder=review.get('personalNameOrder','given_family'),
            familyFirstNameStructureConfirmed=review.get('familyFirstNameStructureConfirmed',False),
            pseudonymConfirmed=review.get('pseudonymConfirmed',False),
            normalizedInputConfirmed=review.get('normalizedInputConfirmed',False),
            scope='explicitly reviewed English-context name, ordinary English noun/adjective, abbreviation, symbol, phrase, numeral or taxonomic identifier; no title-only POS inference, inherited morphology, source endorsement, corpus intent or current availability claim; article prose is not redistributed')
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
    name_roles=None
    if any(r.get('contextKind')=='verified_personal_name_unit' for r in reviews):
        if not getattr(args,'index',None):raise ValueError('Personal-name unit review requires the pinned local English index')
        index=Index(args.index)
        try:name_roles=verified_person_name_roles(index,{r['counterpartNameProof']['surface'] for r in reviews if r.get('contextKind')=='verified_personal_name_unit'})
        finally:index.close()
        if any(r.get('counterpartNameProof',{}).get('source')=='census_surname' for r in reviews):
            if not getattr(args,'census',None):raise ValueError('Census counterpart role requires the pinned surname source')
            extra=verified_census_family_roles(args.census,{r['counterpartNameProof']['surface'] for r in reviews if r.get('counterpartNameProof',{}).get('source')=='census_surname'})
            if set(extra)&set(name_roles):raise ValueError('Ambiguous counterpart source identity')
            name_roles.update(extra)
    model,rows,sources,notices,pending = extension.load_base(args.base,args.seed)
    if pipeline.digest(args.base/'inventory.jsonl') != meta['inventorySha256']:
        raise ValueError('Wikipedia preparation belongs to another source inventory')
    prior = args.base/'surface-corrections.tsv';corrections = pipeline.read_table(prior,'corrections') if prior.is_file() else []
    counts = attach(model,rows,articles,reviews,corrections,name_roles)
    prior = args.base/'reviewed-overrides.tsv';decisions = pipeline.read_table(prior,'decisions') if prior.is_file() else []
    decisions,reopened = resolve_pending.revalidate_machine_reviews(model,decisions,pending,corrections)
    prior_batch=sources.get('reviewedEnglishWikipedia')
    batch = dict(revision=REVISION,config='20231101.en',sourceSnapshotSha256=SNAPSHOT,
        preparedManifestSha256=pipeline.digest(args.prepared/'manifest.json'),reviewsSha256=pipeline.digest(args.reviews),
        researchArticles=meta['articles'],explicitInterpretationReviews=len(reviews),
        humanReviewClaimed=False,sourceWholeFileSha256IndependentlyVerified=False,
        policy='individual exact-passage reviews only; complete-title matches never automatically assign name/POS, interpretation boundaries remain separate, no source prose exported')
    census_proofs=[r['counterpartNameProof'] for r in reviews if r.get('counterpartNameProof',{}).get('source')=='census_surname']
    if census_proofs:
        import census_surnames
        batch['additionalCounterpartRoleSource']=dict(source='census_surname',archiveSha256=census_surnames.ARCHIVE_SHA,
            csvSha256=census_proofs[0]['snapshotSha256'],scope='aggregate surname-role identity only, original whole-name article spelling retained')
        notices['CC0-1.0.txt']=(args.census/'CC0-1.0.txt').read_bytes()
        notices['WIKIPEDIA-NAME-COUNTERPART-NOTICE.txt']=('U.S. Census Bureau, 2010 aggregate surname table, CC0-1.0. '+census_surnames.URL+'\nSelect surname spelling/rank/count to verify the opposite family-name role in explicitly reviewed complete English personal names. No demographics, individual Census identity, preferred case or gender inference.\n').encode()
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
    parser.add_argument('--index',type=Path,help='Pinned local English name-role evidence for explicit personal-name unit reviews')
    parser.add_argument('--census',type=Path,help='Optional pinned aggregate Census family-name counterpart evidence')
    extend(parser.parse_args())
