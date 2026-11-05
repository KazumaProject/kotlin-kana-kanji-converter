import contextlib,io,json,tempfile,unittest
from pathlib import Path
import lexicon_pipeline as p,extend_lexicon as e,named_components as n
import test_lexicon_pipeline as f
from test_named_components import entity


class StandaloneAdmissionTests(unittest.TestCase):
    def test_contextual_fact_stays_nonadmitting_after_materialization_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);m=p.Lexicon(f.SEED);row={'id':'tsv:1','reading':'phnom','surface':'phnom','cost':1000}
            n.attach(m,[row],[entity()]);inventory=root/'inventory.jsonl';p.jsonl(inventory,[row])
            sources={'inventorySha256':p.digest(inventory),'seed':{name:p.digest(f.SEED/(name+'.tsv')) for name in ['categories','forms','memberships','relations']}}
            with contextlib.redirect_stdout(io.StringIO()):summary=p.publish(m,[row],inventory,root/'base',sources,{},[],allow_input_spellings=True)
            self.assertEqual(1,summary['pendingRows']);self.assertEqual(0,summary['includedRows'])
            loaded,*_=e.load_base(root/'base',f.SEED)
            self.assertFalse(loaded.approved.get('phnom'));self.assertTrue(any(k[1]=='phnom' for k in loaded.forms))
            self.assertTrue(all(proof['standaloneCandidateApproved'] is False for key,proofs in loaded.evidence.items() if key[1]=='phnom' for proof in proofs))
            # Independent standalone evidence admits a candidate without losing
            # the separate contextual record or claiming that it proved a name.
            loaded.add('fixture-independent','phnom','phnom',{'noun'},{'source':'curated_seed','url':'https://example.org/independent'},approved=True)
            with contextlib.redirect_stdout(io.StringIO()):second=p.publish(loaded,[row],inventory,root/'second',sources,{},[],allow_input_spellings=True)
            self.assertEqual(1,second['includedRows']);self.assertEqual(0,second['pendingRows'])


if __name__=='__main__':unittest.main()
