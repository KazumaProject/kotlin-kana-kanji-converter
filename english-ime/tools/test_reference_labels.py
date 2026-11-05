import contextlib
import io
from pathlib import Path
import tempfile
import unittest

import lexicon_pipeline as pipeline
import reference_labels as reference
import test_lexicon_pipeline as fixtures


class ReferenceLabelsTests(unittest.TestCase):
    def pokemon(self):
        return reference.pokemon_records('id,iso639,identifier,official\n9,en,en,1\n1,ja,ja-hrkt,1\n',
            'id,identifier\n98,untrusted-slug\n',
            'pokemon_species_id,local_language_id,name,genus\n98,1,NonEnglish,ignored\n98,9,Krabby,ignored\n')

    def test_english_name_comes_from_explicit_locale_and_resource_not_slug_or_foreign_name(self):
        records=self.pokemon();self.assertEqual(['Krabby'],[r['label'] for r in records])
        self.assertEqual('98',records[0]['speciesId']);self.assertEqual('en',records[0]['language'])
        for names in ['98,9,Krabby,x\n98,9,Other,x\n','99,9,Krabby,x\n','98,1,Krabby,x\n']:
            with self.assertRaises(ValueError):reference.pokemon_records('id,iso639,identifier,official\n9,en,en,1\n',
                'id\n98\n','pokemon_species_id,local_language_id,name,genus\n'+names)

    def test_stream_objects_require_explicit_namespace_and_object_not_type_or_function(self):
        text=('\\rSec2[iostream.syn]\\begin{codeblock}namespace std {\n'+
            '\n'.join('extern '+kind+' '+name+';' for name,kind in reference.STREAM_OBJECTS.items())+
            '\n}\\end{codeblock}\\rSec2[iostream.objects.overview]')
        records=reference.stream_records(text)
        self.assertEqual('std::cout',next(r for r in records if r['label']=='cout')['qualifiedIdentifier'])
        for bad in [text.replace('namespace std','namespace other'),text.replace('ostream cout;','ostream cout();'),
                    text.replace('extern ostream cout;','using cout = ostream;')]:
            with self.assertRaises(ValueError):reference.stream_records(bad)
        model=pipeline.Lexicon(fixtures.SEED)
        reference.attach(model,[dict(id='tsv:1',surface='cout',reading='cout'),dict(id='manual:2',surface='Cout',reading='cout')],records,[])
        key=next(iter(model.approved['cout']))
        self.assertEqual({'symbol','domain_technology'},model.members[key,'cout'])
        self.assertFalse(model.approved.get('Cout'));self.assertFalse(model.approved.get('couts'))

    def test_fictional_name_preserves_existing_interpretations_and_never_inherits_morphology(self):
        model=pipeline.Lexicon(fixtures.SEED);corrections=[]
        model.add('existing','krabby','krabby',{'adjective'},{'source':'curated_seed','url':'https://example.org/existing'},approved=True)
        reference.attach(model,[dict(id='tsv:1',surface='krabby',reading='krabby',cost=700)],self.pokemon(),corrections)
        self.assertEqual({'krabby','Krabby'},{r['target'] for r in corrections})
        key=next(iter(model.approved['Krabby']))
        self.assertEqual({'noun','noun_proper','name_fictional','domain_entertainment'},model.members[key,'Krabby'])
        proof=model.evidence[key,'Krabby'][0]
        self.assertNotIn('genus',proof['labelEvidence']);self.assertNotIn('text',proof)
        model.validate()

    def test_admission_survives_reload_with_original_rows_and_costs(self):
        model=pipeline.Lexicon(fixtures.SEED);rows=[dict(id='tsv:1',surface='krabby',reading='krabby',cost=700)]
        corrections=[];reference.attach(model,rows,self.pokemon(),corrections)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);inventory=root/'inventory.jsonl';pipeline.jsonl(inventory,rows)
            sources=dict(inventorySha256=pipeline.digest(inventory),seed={n:pipeline.digest(fixtures.SEED/(n+'.tsv')) for n in ['categories','forms','memberships','relations']})
            with contextlib.redirect_stdout(io.StringIO()):
                result=pipeline.publish(model,rows,inventory,root/'base',sources,{},[],allow_input_spellings=True,corrections=corrections)
                loaded,*_=reference.extension.load_base(root/'base',fixtures.SEED)
            self.assertEqual(1,result['includedRows']);self.assertTrue(loaded.approved['Krabby'])
            self.assertEqual(('Krabby',),pipeline.correction_targets(corrections,rows,loaded)['tsv:1'])

    def test_existing_explicit_spelling_alternative_keeps_relation_and_citation(self):
        model=pipeline.Lexicon(fixtures.SEED)
        model.add('prior','Krabb y','Krabb y',{'noun'},{'source':'curated_seed','url':'https://example.org/prior'},approved=True)
        corrections=[dict(id='tsv:1',source='krabby',target='Krabb y',relation='input_spelling_correction',evidence='https://example.org/prior')]
        reference.attach(model,[dict(id='tsv:1',surface='krabby',reading='krabby',cost=700)],self.pokemon(),corrections)
        self.assertEqual({'Krabb y','Krabby'},{r['target'] for r in corrections})
        self.assertTrue(all(r['relation']=='input_spelling_candidates' for r in corrections))
        self.assertEqual('https://example.org/prior',next(r['evidence'] for r in corrections if r['target']=='Krabb y'))


if __name__=='__main__':unittest.main()
