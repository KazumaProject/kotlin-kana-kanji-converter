import copy
import bz2
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import lexicon_pipeline as pipeline
import reviewed_tatoeba as usage
import test_lexicon_pipeline as fixtures

def context(text='Good! Hahahaha!'):
    target='Hahahaha';start=text.index(target)
    return dict(sentenceId='123',word='hahahaha',url='https://tatoeba.org/en/sentences/show/123',language='eng',text=text,
        textSha256=hashlib.sha256(text.encode()).hexdigest(),literal=target,owner='fixture',license='CC-BY-2.0-FR',
        added='2025-01-01',lastModified='2026-01-01',sourceSha256=usage.PINS['eng_sentences_detailed.tsv.bz2'],sourceRowSha256='a'*64,
        witness=dict(start=start,end=start+len(target)))

def review():
    return dict(form='hahahaha',target='Hahahaha',anchorSurface='haha',sentenceId='123',reviewer='implementation_agent',
        englishLaughterUseConfirmed=True,rationale='Independent English laughter utterance in its complete sentence.')

class TatoebaReviewTests(unittest.TestCase):
    def test_prepared_context_must_match_the_pinned_full_source_even_if_context_hash_is_updated(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);raw=b'123\teng\tGood! Hahahaha!\tfixture\t2025-01-01\t2026-01-01\n'
            (root/'eng_sentences_detailed.tsv.bz2').write_bytes(bz2.compress(raw));(root/'eng_sentences_CC0.tsv.bz2').write_bytes(bz2.compress(b''))
            for name in ['CC-BY-2.0-FR.html','CC0-1.0.html']:(root/name).write_text('fixture license')
            pins={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in usage.PINS}
            with patch.object(usage,'PINS',pins):
                c=context();p=root/'pending-contexts-v32.jsonl';reviews=root/'reviews.jsonl';reviews.write_text(json.dumps(review())+'\n')
                def write_context(value):
                    p.write_text(json.dumps(value)+'\n');(root/'pending-contexts-v32.manifest.json').write_text(json.dumps(dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),sourceSha256=pins['eng_sentences_detailed.tsv.bz2'],cc0SourceSha256=pins['eng_sentences_CC0.tsv.bz2'])))
                write_context(c);selected,_=usage.load(root,reviews);self.assertEqual(hashlib.sha256(raw).hexdigest(),selected[0][1]['sourceRowSha256'])
                write_context(dict(c,text='Bad! Hahahaha!'))
                with self.assertRaisesRegex(ValueError,'exact complete source row'):usage.load(root,reviews)
                with (root/'eng_sentences_detailed.tsv.bz2').open('ab') as stream:stream.write(b'changed')
                with self.assertRaisesRegex(ValueError,'Changed English corpus'):usage.load(root,reviews)

    def test_exact_utterance_requires_role_review_and_rejects_name_fragments_or_changed_case(self):
        r=review();c=context();usage.validate(r,c)
        for change in [dict(englishLaughterUseConfirmed=False),dict(target='HAHAHAHA'),dict(anchorSurface='he'),dict(rationale='')]:
            with self.subTest(change=change),self.assertRaises(ValueError):usage.validate(dict(r,**change),c)
        for text in ['The Hahahaha Company!','A product called Hahahaha!']:
            with self.subTest(text=text),self.assertRaises(ValueError):usage.validate(r,context(text))
        with self.assertRaises(ValueError):usage.validate(r,dict(c,language='fra'))
        with self.assertRaises(ValueError):usage.validate(r,dict(c,textSha256='b'*64))

    def test_independent_anchor_and_literal_casing_do_not_inherit_other_roles_or_export_prose(self):
        model=pipeline.Lexicon(fixtures.SEED);rows=[dict(id='tsv:1',reading='hahahaha',surface='hahahaha',cost=700)]
        with self.assertRaises(ValueError):usage.attach(model,rows,[(review(),context())],[])
        model.add('fixture-haha','haha','haha',{'interjection','verb_base'},dict(source='curated_seed',url='https://example.org/haha'),approved=True)
        corrections=[];usage.attach(model,rows,[(review(),context())],corrections)
        identity=next(iter(model.approved['Hahahaha']));self.assertEqual({'interjection','register_informal'},model.members[identity,'Hahahaha'])
        proof=model.evidence[identity,'Hahahaha'][0];self.assertFalse(proof['humanReviewClaimed']);self.assertFalse(proof['preferredCaseClaimed']);self.assertNotIn('text',proof);self.assertEqual(context()['textSha256'],proof['sentenceTextSha256'])
        self.assertEqual('Hahahaha',corrections[0]['target']);self.assertEqual(700,rows[0]['cost']);self.assertEqual('hahahaha',rows[0]['surface'])

    def test_existing_valid_reading_is_retained_and_names_cannot_supply_anchors(self):
        model=pipeline.Lexicon(fixtures.SEED);r=review();rows=[dict(id='tsv:1',reading='hahahaha',surface='hahahaha',cost=700)]
        model.add('name','haha','haha',{'interjection','noun_proper'},dict(source='curated_seed',url='https://example.org/name'),approved=True)
        with self.assertRaises(ValueError):usage.attach(model,rows,[(r,context())],[])
        model.add('base','haha','haha',{'interjection'},dict(source='wiktionary',url='https://example.org/base'),approved=True)
        model.add('prior','hahahaha','hahahaha',{'interjection'},dict(source='wiktionary',url='https://example.org/prior'),approved=True)
        corrections=[];usage.attach(model,rows,[(r,context())],corrections)
        self.assertEqual({'hahahaha','Hahahaha'},{v['target'] for v in corrections});self.assertTrue(all(v['relation']=='case_candidates' for v in corrections))
        with self.assertRaises(ValueError):usage.attach(model,rows,[(r,context()),(copy.deepcopy(r),context())],[])

    def test_existing_punctuated_spelling_candidate_keeps_its_identity_and_relation_kind(self):
        model=pipeline.Lexicon(fixtures.SEED);rows=[dict(id='tsv:1',reading='hahahaha',surface='hahahaha',cost=700)]
        model.add('base','haha','haha',{'interjection'},dict(source='wiktionary',url='https://example.org/base'),approved=True)
        model.add('prior','ha-ha-ha-ha','ha-ha-ha-ha',{'interjection'},dict(source='wiktionary',url='https://example.org/prior'),approved=True)
        corrections=[dict(id='tsv:1',source='hahahaha',target='ha-ha-ha-ha',relation='input_spelling_correction',evidence='https://example.org/prior')]
        usage.attach(model,rows,[(review(),context())],corrections)
        self.assertEqual({'Hahahaha','ha-ha-ha-ha'},{r['target'] for r in corrections})
        self.assertTrue(all(r['relation']=='input_spelling_candidates' for r in corrections))
        pipeline.correction_targets(corrections,rows,model)

if __name__=='__main__':unittest.main()
