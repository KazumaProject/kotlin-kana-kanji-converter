import contextlib
import io
import tempfile
from pathlib import Path
import unittest

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import manual_lexical_heads as heads
import test_lexicon_pipeline as fixtures


class ManualLexicalHeadTests(unittest.TestCase):
    def fixture(self):
        model=pipeline.Lexicon(fixtures.SEED)
        model.add('fixture-ice','dry ice','dry ice',{'noun','noun_uncountable'},
            dict(source='wiktionary',url='https://example.org/ice'),approved=True)
        row=dict(id='manual:1',reading='dryice',surface='DryIce',cost=9000)
        review=dict(row,canonical='dry ice',reviewer='implementation_agent',rationale='Verified ordinary English head and exact original compact manual display alias.')
        return model,row,review,{('dryice','DryIce',9000):42}

    def test_explicit_alias_retains_canonical_ordinary_identity_and_original_mapping(self):
        model,row,review,literals=self.fixture();heads.attach(model,[row],[review],literals)
        self.assertEqual('dry ice',model.forms['fixture-ice','DryIce']['lemma'])
        self.assertEqual({'noun','noun_uncountable','orthography_existing_manual_alias'},model.members['fixture-ice','DryIce'])
        self.assertEqual(('dryice','DryIce',9000),(row['reading'],row['surface'],row['cost']))
        self.assertFalse(model.evidence['fixture-ice','DryIce'][0]['externallyAttestedAliasSpellingClaimed'])
        model.validate()

    def test_alias_rejects_changed_raw_cost_letters_missing_literal_and_names_only_heads(self):
        for kind in ['cost','letters','literal','name']:
            model,row,review,literals=self.fixture()
            if kind=='cost':review['cost']=8999
            elif kind=='letters':review['canonical']='different words'
            elif kind=='literal':literals={}
            else:model.members['fixture-ice','dry ice'].add('noun_proper')
            with self.assertRaises(ValueError):heads.attach(model,[row],[review],literals)

    def test_alias_remains_admitting_after_full_materialization_and_verified_reload(self):
        model,row,review,literals=self.fixture();heads.attach(model,[row],[review],literals)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);inventory=root/'inventory.jsonl';pipeline.jsonl(inventory,[row])
            sources=dict(inventorySha256=pipeline.digest(inventory),seed={name:pipeline.digest(fixtures.SEED/(name+'.tsv')) for name in ['categories','forms','memberships','relations']})
            with contextlib.redirect_stdout(io.StringIO()):
                result=pipeline.publish(model,[row],inventory,root/'base',sources,{},[],allow_input_spellings=True)
                loaded,*_=extension.load_base(root/'base',fixtures.SEED)
            self.assertEqual(1,result['includedRows']);self.assertTrue(loaded.approved['DryIce'])
            self.assertEqual('dry ice',loaded.forms['fixture-ice','DryIce']['lemma'])


if __name__=='__main__':unittest.main()
