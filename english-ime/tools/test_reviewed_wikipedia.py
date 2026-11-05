import copy
import contextlib
import hashlib
import io
from pathlib import Path
import tempfile
import unittest

import lexicon_pipeline as pipeline
import reviewed_wikipedia as wiki
import test_lexicon_pipeline as fixtures


def article(title='Fixture',text='Fixture is a documented software product.'):
    return dict(id='123',url='https://en.wikipedia.org/wiki/Fixture',title=title,text=text,
        textSha256=hashlib.sha256(text.encode()).hexdigest(),shard='20231101.en/train-00000-of-00041.parquet',
        rowGroup=0,rowIndexInGroup=0,declaredSourceLfsSha256='a'*64,sourceWholeFileSha256IndependentlyVerified=False)


def review(value):
    return dict(articleId=value['id'],target=value['title'],interpretation='software-product',decision='include_name',
        categories=['noun','noun_proper','name_product','domain_technology'],reviewer='implementation_agent',
        rationale='Explicit independently reviewed software identity and literal spelling.',contextKind='full_article_title',
        witness=dict(start=0,end=len(value['text']),sha256=value['textSha256']))


class WikipediaReviewTests(unittest.TestCase):
    def test_named_object_needs_whole_independent_label_and_explicit_review(self):
        value=article('Other','names it Fixture, combining it with another machine.');r=review(value)
        r.update(target='Fixture',contextKind='explicit_named_object_reference',explicitNamingConfirmed=True,categories=['noun','noun_proper','name_fictional'])
        wiki.validate_review(r,value)
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,explicitNamingConfirmed=False),value)
        for text in ['names it Fixture Junior,','names it Fixture-like,','renames it Fixture,']:
            value=article('Other',text);r['witness']=dict(start=0,end=len(text),sha256=value['textSha256'])
            with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_title_initialism_requires_printed_full_subject_and_all_title_initials(self):
        text='It closed the same month TCR was released.';value=article('The Complete Reference',text);r=review(value);start=text.index('TCR')
        r.update(target='TCR',categories=['noun','noun_proper','name_work','abbreviation'],contextKind='article_title_initialism',titleInitialismConfirmed=True,witness=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest()))
        wiki.validate_review(r,value)
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,titleInitialismConfirmed=False),value)
        for title,text in [('Another Full Title','TCR was released.'),('The Complete Reference','Long TCR was released.'),('The Complete Reference','TCR Junior was released.')]:
            value=article(title,text);start=text.index('TCR');r['witness']=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest())
            with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_recorded_work_requires_whole_list_item_not_parenthesized_title_fragment(self):
        text='Details.\n\nRecordings \nOther Work; Fixture; Last Work, Ensemble, 2002.';value=article('Fixture (subtitle)',text);start=text.index('Fixture;');r=review(value)
        r.update(target='Fixture',categories=['noun','noun_proper','name_work'],contextKind='recorded_work_list_item',recordedWorkItemConfirmed=True,witness=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest()))
        wiki.validate_review(r,value)
        for text in ['Details.\n\nRecordings\nOther Work; Fixture (subtitle); Last Work.', 'Details.\nOther Work; Fixture; Last Work.','Details.\n\nRecordings\nOther Work; Fixture Junior; Last Work.']:
            value=article('Fixture (subtitle)',text);start=text.index('Fixture');r['witness']=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest())
            with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_prefaced_lexical_noun_requires_its_own_explicit_english_role_confirmation(self):
        text='In this field, fixture refers to a technical concept.';value=article('Other',text);r=review(value);start=text.index('fixture')
        r.update(target='fixture',decision='include_lexical_noun',categories=['noun'],contextKind='comma_prefaced_name_subject',englishLexicalRoleConfirmed=True,prefacedLexicalSubjectConfirmed=True,witness=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest()))
        wiki.validate_review(r,value)
        for change in [dict(englishLexicalRoleConfirmed=False),dict(prefacedLexicalSubjectConfirmed=False,prefacedNameSubjectConfirmed=True)]:
            with self.assertRaises(ValueError):wiki.validate_review(dict(r,**change),value)

    def test_future_station_name_does_not_need_a_current_existence_claim(self):
        value=article('Other','Fixture will be an underground station.');r=review(value)
        r.update(target='Fixture',contextKind='standalone_sentence_subject',categories=['noun','noun_proper','name_place'])
        wiki.validate_review(r,value)
        value=article('Other','Long Fixture will be a station.');start=value['text'].index('Fixture');r['witness']=dict(start=start,end=len(value['text']),sha256=hashlib.sha256(value['text'][start:].encode()).hexdigest())
        with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_determined_name_needs_separate_name_review_and_keeps_complete_boundaries(self):
        value=article('Other','the Fixture, an insurance company.');r=review(value)
        r.update(target='Fixture',categories=['noun','noun_proper','name_organization'],contextKind='complete_determined_noun_head',completeNominalReferenceConfirmed=True)
        wiki.validate_review(r,value)
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,completeNominalReferenceConfirmed=False,englishLexicalRoleConfirmed=True),value)
        for text in ['the Long Fixture,','the Fixture Holdings,','the Fixture-like company,']:
            value=article('Other',text);r['witness']=dict(start=0,end=len(text),sha256=value['textSha256'])
            with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_reviewed_determined_noun_requires_explicit_english_role_and_complete_head(self):
        for text,target in [('a fixture, which is described.','fixture'),('the fixture who works.','fixture'),('his fixture, which was changed.','fixture'),('These fixtures can be used.','fixtures'),('another fixture"; the reviewer continues.','fixture'),('Another fixture”, according to the reviewer.','fixture')]:
            value=article('Other',text);r=review(value)
            r.update(target=target,decision='include_lexical_noun',categories=['noun'],contextKind='complete_determined_noun_head',englishLexicalRoleConfirmed=True)
            wiki.validate_review(r,value)
            with self.assertRaises(ValueError):wiki.validate_review(dict(r,englishLexicalRoleConfirmed=False),value)
        for text in ['a fixture Junior,','a fixture-like,','a long fixture,','another fixture Junior";','another fixture-like";','another long fixture";','another fixture" Junior,','another fixture\'s,']:
            value=article('Other',text);r['witness']=dict(start=0,end=len(text),sha256=value['textSha256'])
            with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_reviewed_adjective_requires_independent_ordinary_noun_and_explicit_english_role(self):
        model=pipeline.Lexicon(fixtures.SEED);model.add('actual','variant','variants',{'noun','noun_count_plural'},dict(source='curated_seed',url='https://example.org/variant'),approved=True)
        model.add('proper','Example','example',{'noun','noun_proper'},dict(source='curated_seed',url='https://example.org/example'),approved=True)
        value=article('Other','Regional variants in the game.');r=review(value)
        r.update(target='Regional',decision='include_lexical_adjective',categories=['adjective'],contextKind='reviewed_english_noun_modifier',englishLexicalRoleConfirmed=True,nounHeadProof=dict(surface='variants',lexemeId='actual'))
        heads=wiki.approved_noun_heads(model);wiki.validate_review(r,value,noun_heads=heads);self.assertNotIn('example',heads)
        for change in [dict(nounHeadProof=None),dict(nounHeadProof=dict(surface='variants',lexemeId='invented')),dict(englishLexicalRoleConfirmed=False)]:
            with self.assertRaises(ValueError):wiki.validate_review(dict(r,**change),value,noun_heads=heads)
        value=article('Other','Regional variants-like forms.');r['witness']=dict(start=0,end=len(value['text']),sha256=value['textSha256'])
        with self.assertRaises(ValueError):wiki.validate_review(r,value,noun_heads=heads)

    def test_explicit_brand_classifier_does_not_infer_a_product_or_person(self):
        value=article('Other','The Fixture brand was launched.');r=review(value)
        r.update(target='Fixture',categories=['noun','noun_proper','name_brand'],contextKind='named_classifier_phrase',namedClassifierConfirmed=True)
        wiki.validate_review(r,value)
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,categories=['noun','noun_proper','name_product']),value)

    def test_family_first_name_preserves_whole_hyphenated_given_unit_and_opposite_role(self):
        proof=dict(surface='Kim',role='family',entryId=123,senseIndex=0,snapshotSha256=wiki.WIKTIONARY_SNAPSHOT)
        roles={('Kim','family',123,0):proof};value=article('Other','Kim Nam-joon (born 1994) is a musician.');r=review(value)
        r.update(target='Nam-joon',categories=['noun','noun_proper','name_person'],contextKind='verified_personal_name_unit',
                 personalNameUnitRole='given',personalNameOrder='family_given',familyFirstNameStructureConfirmed=True,
                 counterpartNameProof=proof,personalNameStructureConfirmed=True)
        wiki.validate_review(r,value,name_roles=roles)
        for change in [dict(target='Nam'),dict(target='joon'),dict(personalNameOrder='given_family'),
                       dict(familyFirstNameStructureConfirmed=False),dict(counterpartNameProof=dict(proof,role='given'))]:
            with self.assertRaises(ValueError):wiki.validate_review(dict(r,**change),value,name_roles=roles)
        value=article('Other','Kim Nam-joon Extra (born 1994) is a person.');r['witness']=dict(start=0,end=len(value['text']),sha256=value['textSha256'])
        with self.assertRaises(ValueError):wiki.validate_review(r,value,name_roles=roles)

    def test_genitive_reference_does_not_clip_a_longer_name_or_inherit_grammar(self):
        value=article('Other',"according to Fixture's website, a statement.");r=review(value);start=value['text'].index('to ')
        r.update(target='Fixture',contextKind='complete_name_genitive_reference',nameGenitiveConfirmed=True,witness=dict(start=start,end=len(value['text']),sha256=hashlib.sha256(value['text'][start:].encode()).hexdigest()))
        model=pipeline.Lexicon(fixtures.SEED);rows=[dict(id='raw:1',surface='fixture',reading='fixture',cost=700)];corrections=[]
        wiki.attach(model,rows,{value['id']:value},[r],corrections)
        self.assertEqual({'noun','noun_proper','name_product','domain_technology'},next(model.members[k] for k in model.forms if k[1]=='Fixture'))
        self.assertFalse(model.approved.get("Fixture's"));model.validate()
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,nameGenitiveConfirmed=False),value)
        for text in ["to Long Fixture's website,", "to Fixture Junior's website,", "to Fixture-Smith's website,"]:
            value=article('Other',text);r['witness']=dict(start=0,end=len(text),sha256=value['textSha256'])
            with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_comma_prefaced_subject_keeps_complete_name_and_verified_predicate(self):
        text='After recovering, Fixture discovers a secret.';value=article('Other',text);r=review(value);start=text.index('Fixture')
        r.update(target='Fixture',contextKind='comma_prefaced_name_subject',prefacedNameSubjectConfirmed=True,predicateProof=dict(surface='discovers',lexemeId='actual'),witness=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest()))
        wiki.validate_review(r,value,predicates={'discovers':{'actual'}})
        for change in [dict(prefacedNameSubjectConfirmed=False),dict(predicateProof=None),dict(predicateProof=dict(surface='discovers',lexemeId='invented'))]:
            with self.assertRaises(ValueError):wiki.validate_review(dict(r,**change),value,predicates={'discovers':{'actual'}})
        for text in ['After recovering, Long Fixture discovers a secret.','After recovering, Fixture Junior discovers a secret.','After recovering, Fixture-Smith discovers a secret.']:
            value=article('Other',text);start=text.index('Fixture');r['witness']=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest())
            with self.assertRaises(ValueError):wiki.validate_review(r,value,predicates={'discovers':{'actual'}})

    def test_explicit_brand_label_cannot_clip_a_longer_product_name(self):
        for text in ['brand name Fixture among others, is a product.', 'brand name Fixture, is a product.']:
            value=article('Other',text);r=review(value)
            r.update(target='Fixture',categories=['noun','noun_proper','name_brand'],contextKind='explicit_brand_name',brandNameConfirmed=True)
            wiki.validate_review(r,value)
            with self.assertRaises(ValueError):wiki.validate_review(dict(r,brandNameConfirmed=False),value)
        for text in ['brand name Fixture XR among others,','brand name Fixture-Plus,','brand name Fixture Holdings,']:
            value=article('Other',text);r['witness']=dict(start=0,end=len(text),sha256=value['textSha256'])
            with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_personal_nickname_list_requires_a_whole_quoted_personal_alias(self):
        text='known by his nickname "First" or "Fixture" (meaning friend), used publicly.'
        value=article('Other',text);r=review(value)
        r.update(target='Fixture',categories=['noun','noun_proper','name_person'],contextKind='explicit_personal_nickname_list',personalNicknameConfirmed=True)
        wiki.validate_review(r,value)
        for change in [dict(target='Fixt'),dict(personalNicknameConfirmed=False),dict(categories=['noun','noun_proper','name_work'])]:
            with self.assertRaises(ValueError):wiki.validate_review(dict(r,**change),value)
        for text in ['known by his nickname "Fixture Junior" (meaning friend),', 'film named "Fixture" (released recently),', 'known by his nickname "Fixture" Jones (a person),']:
            value=article('Other',text);r['witness']=dict(start=0,end=len(text),sha256=value['textSha256'])
            with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_titled_name_requires_complete_person_reference_and_finite_clause(self):
        text='After the succession, Ser Fixture is retired.';value=article('Other',text);r=review(value);start=text.index('Ser')
        r.update(target='Fixture',categories=['noun','noun_proper','name_fictional'],contextKind='titled_person_reference',titledNameConfirmed=True,witness=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest()))
        wiki.validate_review(r,value)
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,titledNameConfirmed=False),value)
        for text in ['Long Ser Fixture is retired.','Ser Fixture Junior is retired.','Ser Fixture-Smith is retired.']:
            value=article('Other',text);start=text.index('Ser');r['witness']=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest())
            with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_pseudonym_preserves_terminal_punctuation_and_never_clips_larger_names(self):
        text='Other references:\n Fixture!, pseudonym for American artist Sample Person'
        value=article('Other',text);start=text.index('Fixture!');r=review(value)
        r.update(target='Fixture!',interpretation='artist-pseudonym',categories=['noun','noun_proper','name_person'],
                 contextKind='explicit_pseudonym_item',pseudonymConfirmed=True,normalizedInputConfirmed=True,
                 witness=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest()))
        model=pipeline.Lexicon(fixtures.SEED);rows=[dict(id='raw:1',surface='fixture',reading='fixture',cost=700)];corrections=[]
        wiki.attach(model,rows,{value['id']:value},[r],corrections)
        self.assertEqual(('Fixture!',),pipeline.correction_targets(corrections,rows,model)['raw:1'])
        self.assertFalse(model.approved.get('fixture'));model.validate()
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,pseudonymConfirmed=False),value)
        for text in ['Prefix Fixture!, pseudonym for American artist Sample Person',
                     'Fixture! Junior, pseudonym for American artist Sample Person']:
            value=article('Other',text);start=text.index('Fixture!');r['witness']=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest())
            with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_article_free_classifier_requires_a_real_sentence_boundary(self):
        value=article('Other','Fixture Series are published games.');r=review(value)
        r.update(target='Fixture',contextKind='named_classifier_phrase',namedClassifierConfirmed=True)
        wiki.validate_review(r,value)
        text='Long Fixture Series are published games.';value=article('Other',text);start=text.index('Fixture')
        r['witness']=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest())
        with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_person_name_unit_needs_independent_opposite_name_role_and_complete_lead(self):
        proof=dict(surface='Wilson',role='family',entryId=123,senseIndex=0,snapshotSha256=wiki.WIKTIONARY_SNAPSHOT)
        roles={('Wilson','family',123,0):proof};value=article('Frae Wilson','Frae Wilson (born 1989) is a rugby player.');r=review(value)
        r.update(target='Frae',categories=['noun','noun_proper','name_person'],contextKind='verified_personal_name_unit',
                 personalNameUnitRole='given',counterpartNameProof=proof,personalNameStructureConfirmed=True)
        wiki.validate_review(r,value,name_roles=roles)
        for change in [dict(personalNameUnitRole='family'),dict(personalNameStructureConfirmed=False),
                       dict(counterpartNameProof=dict(proof,entryId=999)),dict(counterpartNameProof=dict(proof,role='given'))]:
            with self.assertRaises(ValueError):wiki.validate_review(dict(r,**change),value,name_roles=roles)
        for text in ['Frae Wilson Smith (born 1989) is a person.','Frae-Wilson (born 1989) is a person.','Long Frae Wilson (born 1989) is a person.']:
            value=article('Other',text);r['witness']=dict(start=0,end=len(text),sha256=value['textSha256'])
            with self.assertRaises(ValueError):wiki.validate_review(r,value,name_roles=roles)

    def test_name_role_comes_from_actual_unrestricted_english_sense_not_generic_person_label(self):
        class Names:
            def lookup(self,words):
                return [(1,dict(word='Known',senses=[dict(categories=['English given names']),
                    dict(categories=['English surnames'],tags=['obsolete']),dict(categories=['English people'])]))]
        roles=wiki.verified_person_name_roles(Names(),{'Known'})
        self.assertEqual({('Known','given',1,0)},set(roles))

    def test_noun_phrase_needs_verified_english_modifier_and_complete_ordinary_head(self):
        model=pipeline.Lexicon(fixtures.SEED)
        model.add('recognized','recognize','recognized',{'verb','verb_past_participle'},
                  {'source':'curated_seed','url':'https://example.org/recognize'},approved=True)
        value=article('Other','a recognized fixture, with a separate function.');r=review(value)
        r.update(target='fixture',decision='include_lexical_noun',categories=['noun'],contextKind='complete_english_noun_phrase',
                 englishLexicalRoleConfirmed=True,modifierProof=dict(surface='recognized',lexemeId='recognized'))
        modifiers=wiki.approved_nominal_modifiers(model);wiki.validate_review(r,value,modifiers=modifiers)
        for proof in [None,dict(surface='other',lexemeId='recognized'),dict(surface='recognized',lexemeId='unverified')]:
            with self.assertRaises(ValueError):wiki.validate_review(dict(r,modifierProof=proof),value,modifiers=modifiers)
        for text in ['a recognized fixture family,','a recognized fixture-like,']:
            value=article('Other',text);r['witness']=dict(start=0,end=len(text),sha256=value['textSha256'])
            with self.assertRaises(ValueError):wiki.validate_review(r,value,modifiers=modifiers)

    def test_named_classifier_requires_complete_name_and_reviewed_entity_type(self):
        value=article('Other','the Fixture controller, which was released.');r=review(value)
        r.update(target='Fixture',contextKind='named_classifier_phrase',namedClassifierConfirmed=True)
        wiki.validate_review(r,value)
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,namedClassifierConfirmed=False),value)
        for text in ['the Long Fixture controller,','the Fixture Junior controller,','the Fixture-Plus controller,','the Fixture rose,']:
            value=article('Other',text);r['witness']=dict(start=0,end=len(text),sha256=value['textSha256'])
            with self.assertRaises(ValueError):wiki.validate_review(r,value)
        value=article('Other','the Fixture controller,');r['witness']=dict(start=0,end=len(value['text']),sha256=value['textSha256'])
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,categories=['noun','noun_proper','name_person']),value)

    def test_date_preface_keeps_the_real_subject_boundary_and_finite_evidence(self):
        for prefix in ['In 1896, ','In September 2021, ']:
            value=article('Another heading',prefix+'Fixture released a recording.');r=review(value)
            r.update(target='Fixture',contextKind='standalone_sentence_subject');wiki.validate_review(r,value)
        value=article('Another heading','In September 2021, Long Fixture released a recording.');r=review(value)
        r.update(target='Fixture',contextKind='standalone_sentence_subject')
        with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_quoted_subject_needs_complete_reported_english_clause_not_name_fragment(self):
        text='The critic said that "Fixture is a remarkable performer".';value=article('Different',text);r=review(value)
        start=text.index('"');end=text.rindex('"')+1
        r.update(target='Fixture',contextKind='quoted_sentence_subject',englishQuotationConfirmed=True,
                 witness=dict(start=start,end=end,sha256=hashlib.sha256(text[start:end].encode()).hexdigest()))
        wiki.validate_review(r,value)
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,englishQuotationConfirmed=False),value)
        for text in ['The title is "Fixture is a remarkable performer".',
                     'The critic said that "Fixture Junior is a performer".',
                     'The critic said that "Fixture" is a performer.']:
            value=article('Different',text);start=text.index('"');end=text.rindex('"')+1
            r['witness']=dict(start=start,end=end,sha256=hashlib.sha256(text[start:end].encode()).hexdigest())
            with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_nominal_reference_requires_full_left_and_right_name_boundaries(self):
        for text in ['as Fixture in 1971.','of The Fixture came later.','to just Fixture.']:
            value=article('Different',text);r=review(value)
            r.update(target='Fixture',contextKind='complete_nominal_reference',completeNominalReferenceConfirmed=True)
            wiki.validate_review(r,value)
            with self.assertRaises(ValueError):wiki.validate_review(dict(r,completeNominalReferenceConfirmed=False),value)
        for text in ['of Long Fixture.','of Fixture Junior.','of Fixture-like.','as Fixture Holdings in 1971.']:
            value=article('Different',text);r=review(value)
            r.update(target='Fixture',contextKind='complete_nominal_reference',completeNominalReferenceConfirmed=True)
            with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_ordinary_adjective_requires_confirmed_role_without_inflection_or_name_inference(self):
        value=article('Fixture (disambiguation)','Fixture relates to a historical doctrine.');r=review(value)
        r.update(target='Fixture',decision='include_lexical_adjective',categories=['adjective'],contextKind='standalone_sentence_subject',
                 predicateProof=dict(surface='relates',lexemeId='fixture-relate'))
        predicates={'relates':{'fixture-relate'}}
        with self.assertRaises(ValueError):wiki.validate_review(r,value,predicates)
        r['englishLexicalRoleConfirmed']=True;self.assertEqual({'adjective'},wiki.validate_review(r,value,predicates))
        for category in ['noun_proper','adjective_comparative','verb_present_3sg']:
            with self.assertRaises(ValueError):wiki.validate_review(dict(r,categories=['adjective',category]),value,predicates)

    def test_quoted_personal_nickname_requires_complete_quote_and_biographical_lead(self):
        value=article('Person','Chanston James "Chansey" Paech (born 1987) is an Australian politician.');r=review(value)
        r.update(target='Chansey',categories=['noun','noun_proper','name_person'],contextKind='quoted_personal_nickname',personalNicknameConfirmed=True)
        self.assertEqual(set(r['categories']),wiki.validate_review(r,value))
        for text in ['Chanston James "Chansey Paech" Smith (born 1987) is a person.',
                     'An album called "Chansey" Paech, a recording.',
                     'The story. Chanston James "Chansey" Paech (born 1987) is a person.']:
            value=article('Person',text);r['witness']=dict(start=0,end=len(text),sha256=value['textSha256'])
            with self.assertRaises(ValueError):wiki.validate_review(r,value)
        value=article('Person','Chanston James "Chansey" Paech (born 1987) is a politician.')
        r['witness']=dict(start=0,end=len(value['text']),sha256=value['textSha256'])
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,personalNicknameConfirmed=False),value)

    def test_fictional_apposition_cannot_clip_longer_names_or_assign_real_species(self):
        value=article('Another title','the titular monster, the Babadook, a fictional creature.');r=review(value)
        r.update(target='Babadook',categories=['noun','noun_proper','name_fictional'],contextKind='explicit_fictional_name_apposition',fictionalNameConfirmed=True)
        self.assertEqual(set(r['categories']),wiki.validate_review(r,value))
        for text in ['the titular monster, the Babadook Junior, a fictional creature.',
                     'the titular monster, the Babadook-like, a fictional creature.']:
            value=article('Another title',text);r['witness']=dict(start=0,end=len(text),sha256=value['textSha256'])
            with self.assertRaises(ValueError):wiki.validate_review(r,value)
        value=article('Another title','the titular monster, the Babadook, a fictional creature.')
        r['witness']=dict(start=0,end=len(value['text']),sha256=value['textSha256'])
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,fictionalNameConfirmed=False),value)
        with self.assertRaises(ValueError):wiki.validate_review(dict(r,categories=['noun','noun_proper','identifier_taxonomic_name']),value)

    def test_extra_finite_predicate_needs_verified_english_verb_evidence(self):
        model=pipeline.Lexicon(fixtures.SEED)
        model.add('fixture-said','say','say',{'verb','verb_base'},{'source':'curated_seed','url':'https://example.org/say'},approved=True)
        model.add('fixture-said','say','said',{'verb','verb_past'},{'source':'curated_seed','url':'https://example.org/say'},approved=True)
        wiki.extension.ensure_categories(model,{'identifier_programming_api'})
        model.add('fixture-api','Said','Said',{'identifier_programming_api'},{'source':'public_api_identifier','url':'https://example.org/api'},approved=True)
        value=article('Other heading','Fixture said it was ready.');r=review(value)
        r.update(target='Fixture',contextKind='standalone_sentence_subject',predicateProof=dict(surface='said',lexemeId='fixture-said'))
        with self.assertRaises(ValueError):wiki.validate_review(r,value)
        predicates=wiki.approved_finite_predicates(model);self.assertNotIn('Said',predicates)
        wiki.validate_review(r,value,predicates)
        for proof in [None,'not lexical evidence',dict(surface='said',lexemeId='fixture-api'),dict(surface='invented',lexemeId='fixture-said')]:
            with self.assertRaises(ValueError):wiki.validate_review(dict(r,predicateProof=proof),value,predicates)

    def test_independent_sentence_usage_cannot_clip_a_long_name_or_taxon_component(self):
        value=article('A different heading','The Fixture is a software product.');r=review(value)
        r.update(target='Fixture',contextKind='standalone_sentence_subject')
        self.assertEqual(set(r['categories']),wiki.validate_review(r,value))
        for text,start in [('Long Fixture is a software product.',5),('A. Fixture is a taxon.',3),('var. Fixture is a taxon.',5),('The Fixture Company is a software company.',0)]:
            value=article('A different heading',text);test=copy.deepcopy(r)
            test['witness']=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest())
            with self.assertRaises(ValueError):wiki.validate_review(test,value)

    def test_reviewed_finite_predicates_keep_sentence_and_whole_label_guards(self):
        for predicate in ['had recently won','has returned','have returned','began instruction','did lease land','received royalties','moved home','would return']:
            value=article('Another heading','Fixture '+predicate+'.');r=review(value)
            r.update(target='Fixture',contextKind='standalone_sentence_subject')
            wiki.validate_review(r,value)
            for text in ['Fixture Holdings '+predicate+'.','P. h. Fixture '+predicate+'.','St. Fixture '+predicate+'.','Mrs. Fixture '+predicate+'.']:
                value=article('Another heading',text);start=text.index('Fixture')
                r['witness']=dict(start=start,end=len(text),sha256=hashlib.sha256(text[start:].encode()).hexdigest())
                with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_explicit_alias_is_complete_prose_and_never_a_longer_creative_work_title(self):
        for text,valid in [('known simply as Fixture, a company.',True),('named Fixture, a software package.',True),('nicknamed Fixture, a person.',True),('nicknamed Fixture Junior, a person.',False),('named Fixture Tools, a company.',False),('called Fixture-based, a technique.',False),('Called Fixture, the album A Girl Called Fixture.',False)]:
            value=article('An unrelated heading',text);r=review(value);r.update(target='Fixture',contextKind='explicit_complete_alias')
            if valid:wiki.validate_review(r,value)
            else:
                with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_ordinary_noun_review_requires_explicit_english_use_and_never_invents_morphology(self):
        value=article('A different heading','The fixture is a physical support.');r=review(value)
        r.update(target='fixture',decision='include_lexical_noun',categories=['noun'],contextKind='standalone_sentence_subject')
        with self.assertRaises(ValueError):wiki.validate_review(r,value)
        r['englishLexicalRoleConfirmed']=True;self.assertEqual({'noun'},wiki.validate_review(r,value))
        r['categories'].append('noun_count_singular')
        with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_qualified_title_needs_an_explicit_descriptor_and_literal_complete_body_label(self):
        value=article('Fixture (software)','Fixture is a documented software product.');r=review(value)
        r.update(target='Fixture',contextKind='qualified_article_title',titleQualifier='software')
        model=pipeline.Lexicon(fixtures.SEED);corrections=[]
        wiki.attach(model,[dict(id='tsv:1',surface='fixture',reading='fixture',cost=700)],{'123':value},[r],corrections)
        self.assertTrue(model.approved['Fixture'])
        self.assertEqual('software',model.evidence[next(iter(model.approved['Fixture'])),'Fixture'][0]['reviewedTitleQualifier'])
        for change in ['implicit','wrong-descriptor','name-component','missing-literal','unsupported-descriptor']:
            test=copy.deepcopy(r);source=copy.deepcopy(value)
            if change=='implicit':test['contextKind']='full_article_title'
            elif change=='wrong-descriptor':test['titleQualifier']='film'
            elif change=='name-component':source['title']='Fixture Company (software)'
            elif change=='unsupported-descriptor':source['title']='Fixture (random qualifier)';test['titleQualifier']='random qualifier'
            else:
                source['text']='A documented product.';source['textSha256']=hashlib.sha256(source['text'].encode()).hexdigest()
                test['witness']=dict(start=0,end=len(source['text']),sha256=source['textSha256'])
            with self.assertRaises(ValueError):wiki.validate_review(test,source)

    def test_qualified_disambiguation_keeps_complete_item_guard_and_separate_interpretations(self):
        value=article('Fixture (disambiguation)','Fixture (album), a documented album.');r=review(value)
        r.update(target='Fixture',contextKind='qualified_disambiguation_item',titleQualifier='disambiguation',categories=['noun','noun_proper','name_work'])
        self.assertEqual({'noun','noun_proper','name_work'},wiki.validate_review(r,value))
        value['text']='Fixture Company, a company.';r['witness']=dict(start=0,end=len(value['text']),sha256=hashlib.sha256(value['text'].encode()).hexdigest())
        with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_independent_review_remains_admitting_after_verified_reload(self):
        model=pipeline.Lexicon(fixtures.SEED);value=article()
        rows=[dict(id='tsv:1',surface='fixture',reading='fixture',cost=700)]
        corrections=[];wiki.attach(model,rows,{'123':value},[review(value)],corrections)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);inventory=root/'inventory.jsonl';pipeline.jsonl(inventory,rows)
            sources=dict(inventorySha256=pipeline.digest(inventory),seed={name:pipeline.digest(fixtures.SEED/(name+'.tsv')) for name in ['categories','forms','memberships','relations']})
            with contextlib.redirect_stdout(io.StringIO()):
                result=pipeline.publish(model,rows,inventory,root/'base',sources,{},[],allow_input_spellings=True,corrections=corrections)
                loaded,*_=wiki.extension.load_base(root/'base',fixtures.SEED)
            self.assertEqual(1,result['includedRows']);self.assertTrue(loaded.approved['Fixture'])
            self.assertFalse(loaded.approved.get('fixture'))

    def test_article_titles_alone_never_adopt_and_review_does_not_export_prose_or_inherit_morphology(self):
        model=pipeline.Lexicon(fixtures.SEED);value=article();rows=[dict(id='tsv:1',surface='fixture',reading='fixture',cost=700)]
        wiki.attach(model,rows,{'123':value},[],[]);self.assertFalse(model.approved.get('Fixture'))
        corrections=[];wiki.attach(model,rows,{'123':value},[review(value)],corrections)
        key=next(iter(model.approved['Fixture']))
        self.assertEqual({'noun','noun_proper','name_product','domain_technology'},model.members[key,'Fixture'])
        proof=model.evidence[key,'Fixture'][0];self.assertNotIn('text',proof);self.assertFalse(proof['humanReviewClaimed'])
        self.assertFalse(proof['sourceWholeFileSha256IndependentlyVerified']);self.assertEqual('Fixture',corrections[0]['target'])
        model.validate()

    def test_full_name_component_or_generic_title_cannot_approve_an_unreviewed_short_name(self):
        value=article('Fixture Company','Fixture Company is a company.');r=review(value);r['target']='Fixture'
        with self.assertRaises(ValueError):wiki.validate_review(r,value)
        value=article('Fixture','Fixture Company is a company.');r=review(value);r['contextKind']='disambiguation_item'
        with self.assertRaises(ValueError):wiki.validate_review(r,value)

    def test_disambiguation_item_requires_a_complete_label_and_preserves_separate_interpretations(self):
        value=article('Fixture','Fixture (album), a documented album.');r=review(value);r['contextKind']='disambiguation_item'
        r['categories']=['noun','noun_proper','name_work']
        self.assertEqual({'noun','noun_proper','name_work'},wiki.validate_review(r,value))
        other=copy.deepcopy(r);other['interpretation']='distinct-work'
        model=pipeline.Lexicon(fixtures.SEED)
        wiki.attach(model,[dict(id='tsv:1',surface='fixture',reading='fixture',cost=700)],{'123':value},[r,other],[])
        self.assertEqual(2,len(model.approved['Fixture']))

    def test_changed_passage_unattested_case_bad_roles_and_duplicate_review_are_rejected(self):
        value=article()
        for kind in ['passage','case','morphology','ordinary-symbol-pos']:
            r=review(value)
            if kind=='passage':r['witness']['sha256']='b'*64
            elif kind=='case':r['target']='FIXTURE'
            elif kind=='morphology':r['categories'].append('verb_base')
            else:r.update(decision='include_symbol',categories=['symbol','noun'])
            with self.assertRaises(ValueError):wiki.validate_review(r,value)
        with self.assertRaises(ValueError):wiki.attach(pipeline.Lexicon(fixtures.SEED),[dict(id='tsv:1',surface='fixture',reading='fixture')],{'123':value},[review(value),review(value)],[])

    def test_existing_latin_alias_retains_source_lemma_and_derived_status(self):
        value=article('Fíxture','Fíxture is a documented software product.');model=pipeline.Lexicon(fixtures.SEED)
        corrections=[];wiki.attach(model,[dict(id='tsv:1',surface='fixture',reading='fixture',cost=700)],{'123':value},[review(value)],corrections)
        key=next(iter(model.approved['Fixture']))
        self.assertEqual('Fíxture',model.forms[key,'Fixture']['lemma'])
        self.assertFalse(model.evidence[key,'Fixture'][0]['preferredAsciiSpellingClaimed'])
        self.assertEqual('Fixture',corrections[0]['target']);model.validate()

    def test_existing_latin_input_keeps_attested_abbreviation_punctuation(self):
        value=article('Ther','Thér., the documented botanical author abbreviation.');r=review(value)
        r.update(target='Thér.',decision='include_abbreviation',categories=['abbreviation','domain_science'])
        model=pipeline.Lexicon(fixtures.SEED);rows=[dict(id='tsv:1',surface='ther',reading='ther',cost=700)]
        corrections=[];wiki.attach(model,rows,{'123':value},[r],corrections)
        self.assertEqual(('Ther.',),pipeline.correction_targets(corrections,rows,model)['tsv:1'])
        key=next(iter(model.approved['Ther.']))
        self.assertEqual('Thér.',model.forms[key,'Ther.']['lemma'])
        self.assertFalse(model.evidence[key,'Ther.'][0]['preferredAsciiSpellingClaimed'])

    def test_independent_literal_name_does_not_remove_existing_case_candidate_or_its_citation(self):
        value=article('fixture','fixture is a documented software product.');model=pipeline.Lexicon(fixtures.SEED)
        proof=dict(source='curated_seed',url='https://example.org/original-name')
        model.add('old-name','Fixture','Fixture',{'noun','noun_proper'},proof,approved=True)
        rows=[dict(id='tsv:1',surface='fixture',reading='fixture',cost=700)]
        corrections=[dict(id='tsv:1',source='fixture',target='Fixture',relation='case_correction',evidence=proof['url'])]
        wiki.attach(model,rows,{'123':value},[review(value)],corrections)
        self.assertEqual(('Fixture','fixture'),pipeline.correction_targets(corrections,rows,model)['tsv:1'])
        self.assertEqual(proof['url'],next(c['evidence'] for c in corrections if c['target']=='Fixture'))

    def test_complete_punctuation_spelling_is_retained_without_changing_letters(self):
        value=article('Fixture','Fix-ture, a documented software product.');r=review(value)
        r.update(target='Fix-ture',contextKind='disambiguation_item')
        model=pipeline.Lexicon(fixtures.SEED);rows=[dict(id='tsv:1',surface='fixture',reading='fixture',cost=700)]
        corrections=[];wiki.attach(model,rows,{'123':value},[r],corrections)
        self.assertEqual(('Fix-ture',),pipeline.correction_targets(corrections,rows,model)['tsv:1'])
        self.assertEqual('input_spelling_correction',corrections[0]['relation'])
        self.assertFalse(wiki.matches_title('Fixtured','Fixture'))
        self.assertFalse(wiki.matches_title('Fixture!','Different!'))
        self.assertFalse(wiki.matches_title('Fixture!','Fixture'))

    def test_identifiers_do_not_acquire_unattested_manual_casing(self):
        value=article('Expr','expr is a command-line utility.');r=review(value)
        r.update(target='expr',decision='include_command',categories=['identifier_command_line','domain_technology'])
        model=pipeline.Lexicon(fixtures.SEED)
        wiki.attach(model,[dict(id='manual:1',surface='Expr',reading='expr',cost=700)],{'123':value},[r],[])
        self.assertTrue(model.approved.get('expr'));self.assertFalse(model.approved.get('Expr'))


if __name__=='__main__':unittest.main()
