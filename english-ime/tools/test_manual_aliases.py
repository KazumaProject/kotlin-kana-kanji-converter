import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import manual_aliases as aliases
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class LiteralInputAliasTests(unittest.TestCase):
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
