import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import manual_aliases as aliases
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class LiteralInputAliasTests(unittest.TestCase):
    def test_multiline_original_alias_requires_allowlisted_exact_cost_and_verified_target(self):
        model=pipeline.Lexicon(fixtures.SEED)
        model.add('suite','Example 365','Example 365',{'noun','noun_proper','name_product'},
            {'source':'official_product_label','url':'https://example.org/suite'},approved=True)
        row=dict(id='manual:1',reading='example three sixty five',surface='Example 365',cost=9000)
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'Manual.kt'
            source.write_text('Dictionary(\n reading = "example three sixty five",\n cost = 9000.toShort(),\n word = "Example 365",\n withUpperCase = true\n)')
            with patch.object(aliases,'MANUAL_SHA256',hashlib.sha256(source.read_bytes()).hexdigest()),patch.object(aliases,'EXPECTED',{'manual:1':('example three sixty five','Example 365',9000)}):
                audit=[];aliases.attach(model,[row],source,audit)
                self.assertIn(('example three sixty five','Example 365'),{(r['source'],r['target']) for r in model.relations if r['relation']=='input_alias'})
                self.assertEqual(9000,row['cost'])
                changed=dict(row,cost=8999)
                with self.assertRaises(ValueError):aliases.attach(model,[changed],source,[])

    def test_literal_unusual_input_is_preserved_without_claiming_standard_spelling(self):
        model=pipeline.Lexicon(fixtures.SEED)
        model.add('brand','FixtureWorkers','FixtureWorkers',{'noun','noun_proper'},
            {'source':'brand_metadata','url':'https://example.org/brand'},approved=True)
        row={'id':'manual:1','reading':'fixturworkers','surface':'FixtureWorkers','cost':12000}
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'Manual.kt';source.write_text('Dictionary(reading = "fixturworkers", cost = 12000.toShort(), word = "FixtureWorkers", withUpperCase = true)\n')
            audit=[]
            with patch.object(aliases,'MANUAL_SHA256',hashlib.sha256(source.read_bytes()).hexdigest()),patch.object(aliases,'EXPECTED',{'manual:1':('fixturworkers','FixtureWorkers',12000)}):
                aliases.attach(model,[row],source,audit)
            self.assertEqual('fixturworkers',row['reading']);self.assertEqual(12000,row['cost'])
            self.assertIn(('input_alias','fixturworkers','FixtureWorkers'),{(r['relation'],r['source'],r['target']) for r in model.relations})
            self.assertEqual('fixtureworkers',audit[0]['standardKeyboardKey'])

    def test_source_hash_and_independent_target_remain_required(self):
        model=pipeline.Lexicon(fixtures.SEED)
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'Manual.kt';source.write_text('Dictionary(reading = "unknown", cost = 42.toShort(), word = "Unknown", withUpperCase = true)\n')
            with self.assertRaisesRegex(ValueError,'source changed'):aliases.attach(model,[],source,[])
            with patch.object(aliases,'MANUAL_SHA256',hashlib.sha256(source.read_bytes()).hexdigest()),patch.object(aliases,'EXPECTED',{'manual:1':('unknown','Unknown',42)}):
                with self.assertRaisesRegex(ValueError,'independently approved'):aliases.attach(model,[{'id':'manual:1','reading':'unknown','surface':'Unknown','cost':42}],source,[])


if __name__=='__main__':unittest.main()
