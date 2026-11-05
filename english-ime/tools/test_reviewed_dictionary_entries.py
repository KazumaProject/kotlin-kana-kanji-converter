import contextlib
import copy
import io
from pathlib import Path
import tempfile
import unittest

import lexicon_pipeline as pipeline
import reviewed_dictionary_entries as dictionary
import test_lexicon_pipeline as fixtures


def book(body):
    return '*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\n\n'+body+'\n\n*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\n'


def entry(text,identity='pg29765:3'):
    return dictionary.webster_entries(book(text),{identity})[identity]


def review(record,target='fixture',categories=None):
    return dict(entryId=record['id'],entrySha256=record['entrySha256'],target=target,
        categories=categories or ['noun'],reviewer='implementation_agent',headingCaseNormalized=True,
        rationale='Individually checked complete English heading, printed entry POS, usage labels and this interpretation.')


class ReviewedDictionaryTests(unittest.TestCase):
    def test_complete_shared_heads_use_printed_entry_pos_not_gloss_or_etymology(self):
        record=entry('FIXTURE; FIXTURED\nFixture, Fixtured, a. Etym: [L. n.]\n\nDefn: A sample with a noun in its explanation.')
        self.assertEqual(['fixture','fixtured'],record['heads']);self.assertEqual('a.',record['printedPos'])
        dictionary.validate_review(review(record,'fixture',['adjective']),record)
        for target,categories in [('fixt',['adjective']),('fixture',['noun']),('fixture',['adjective','adjective_comparative'])]:
            with self.assertRaises(ValueError):dictionary.validate_review(review(record,target,categories),record)
        prefix=entry('FIXTURE\nFixture.\n\nDefn: A prefix with n. only in this definition.')
        self.assertIsNone(prefix['printedPos'])
        with self.assertRaises(ValueError):dictionary.validate_review(review(prefix),prefix)

    def test_historical_source_cannot_override_obsolete_or_current_restriction(self):
        record=entry('FIXTURE\nFixture, n.\n\nDefn: A support. [Obs.]')
        with self.assertRaises(ValueError):dictionary.validate_review(review(record),record)
        record=entry('FIXTURE\nFixture, n.\n\nDefn: A support.')
        with self.assertRaises(ValueError):dictionary.validate_review(review(record),record,{'fixture'})
        with self.assertRaises(ValueError):dictionary.validate_review(dict(review(record),headingCaseNormalized=False),record)
        with self.assertRaises(ValueError):dictionary.validate_review(dict(review(record),entrySha256='0'*64),record)
        with self.assertRaises(ValueError):dictionary.validate_review(dict(review(record),decision='exclude'),record)
        with self.assertRaises(ValueError):dictionary.validate_review(review(record),record,{'Fixture'})

    def test_ordinary_heading_does_not_supply_names_count_or_verb_inflections(self):
        record=entry('FIXTURE\nFixture, n.\n\nDefn: A support.')
        for members in [['noun','noun_proper'],['noun','noun_count_singular'],['noun','verb_base']]:
            with self.assertRaises(ValueError):dictionary.validate_review(review(record,categories=members),record)

    def wordnet(self):
        return '''<LexicalResource><Lexicon id="oewn" language="en" version="2025+" license="https://creativecommons.org/licenses/by/4.0">
<LexicalEntry id="fixture-brand"><Lemma writtenForm="Fixture" partOfSpeech="n"/><Sense id="sense1" synset="synset1"><SenseRelation relType="exemplifies" target="oewn-trademark__1.10.00.."/></Sense></LexicalEntry>
<Synset id="synset1" lexfile="noun.artifact"><Definition>Not exported</Definition><SynsetRelation relType="hypernym" target="oewn-03834005-n"/></Synset>
</Lexicon></LexicalResource>'''

    def test_named_wordnet_entry_requires_language_sense_and_typed_identity(self):
        record=dictionary.wordnet_entries(io.StringIO(self.wordnet()),{'fixture-brand'})['fixture-brand']
        r=review(record,'Fixture',['noun','noun_proper','name_brand','domain_medical'])
        dictionary.validate_review(r,record)
        with self.assertRaises(ValueError):dictionary.validate_review(review(record,'fixture',r['categories']),record)
        changed=copy.deepcopy(record);changed['senses'][0]['relations']=[]
        with self.assertRaises(ValueError):dictionary.validate_review(r,changed)
        changed=copy.deepcopy(record);changed['synsets'][0]['relations']=[]
        with self.assertRaises(ValueError):dictionary.validate_review(r,changed)
        with self.assertRaises(ValueError):dictionary.wordnet_entries(io.StringIO(self.wordnet().replace('language="en"','language="fr"')),{'fixture-brand'})

    def test_named_entry_preserves_existing_reading_and_does_not_export_definitions(self):
        record=dictionary.wordnet_entries(io.StringIO(self.wordnet()),{'fixture-brand'})['fixture-brand']
        model=pipeline.Lexicon(fixtures.SEED);corrections=[]
        model.add('ordinary','fixture','fixture',{'noun'},{'source':'curated_seed','url':'https://example.org/ordinary'},approved=True)
        dictionary.attach(model,[dict(id='tsv:1',surface='fixture',reading='fixture',cost=700)],{'fixture-brand':record},
            [review(record,'Fixture',['noun','noun_proper','name_brand','domain_medical'])],corrections)
        self.assertEqual({'fixture','Fixture'},{r['target'] for r in corrections})
        proof=model.evidence[next(iter(model.approved['Fixture'])),'Fixture'][0]
        self.assertFalse(proof['humanReviewClaimed']);self.assertNotIn('Definition',str(proof));model.validate()

    def test_reviewed_entry_admission_survives_verified_reload(self):
        record=entry('FIXTURE\nFixture, n.\n\nDefn: A support.');model=pipeline.Lexicon(fixtures.SEED)
        rows=[dict(id='tsv:1',surface='fixture',reading='fixture',cost=700)]
        dictionary.attach(model,rows,{record['id']:record},[review(record)],[])
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);inventory=root/'inventory.jsonl';pipeline.jsonl(inventory,rows)
            sources=dict(inventorySha256=pipeline.digest(inventory),seed={n:pipeline.digest(fixtures.SEED/(n+'.tsv')) for n in ['categories','forms','memberships','relations']})
            with contextlib.redirect_stdout(io.StringIO()):
                result=pipeline.publish(model,rows,inventory,root/'base',sources,{},[],allow_input_spellings=True)
                loaded,*_=dictionary.extension.load_base(root/'base',fixtures.SEED)
            self.assertEqual(1,result['includedRows']);self.assertTrue(loaded.approved['fixture'])


if __name__=='__main__':unittest.main()
