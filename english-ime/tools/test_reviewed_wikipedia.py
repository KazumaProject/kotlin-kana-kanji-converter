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
