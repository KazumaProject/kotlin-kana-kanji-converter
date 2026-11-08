import argparse
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import coverage_harness as controller


class CoveragePassTest(unittest.TestCase):
    def test_newly_discovered_frontier_remains_unreviewed_after_bootstrap_advice(self):
        manifest=dict(advisor=dict(decisions=[dict(node='old')],remainingReviewNodes=0),nodes={
            'old':dict(id='old',phase='done'),'new':dict(id='new',phase='terms')})
        self.assertEqual(1,controller.review_remaining(manifest))
        manifest['nodes']['new']['phase']='done'
        self.assertEqual(0,controller.review_remaining(manifest))

    def test_offline_no_change_pass_skips_build_resumes_and_rejects_changed_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);snapshot=root/'snapshot';snapshot.mkdir()
            (snapshot/'coverage.json').write_text('{}')
            assets=root/'assets';assets.mkdir();(assets/'token.dat').write_bytes(b'baseline')
            args=argparse.Namespace(work_dir=root/'pass',snapshot=snapshot,assets=assets,policy=snapshot/'coverage.json',
                catalog_source_dir=root,lexical_source_dir=root,esdb_dir=root,cli=root/'cli',source_budget=300)
            calls=[]
            def execute(command,check):
                script=Path(command[2]).name;action=command[3];calls.append((script,action))
                def value(name):return Path(command[command.index(name)+1])
                if action=='prepare':
                    output=value('--work-dir');output.mkdir();controller.h.dump(output/'run.json',dict(selectedCandidates=0))
                elif action=='adopt':return
                elif action=='build':self.fail('No-change pass must not build')
                else:
                    output=value('--out');output.mkdir()
                    if action=='assess':controller.h.dump(output/'assessment.json',{})
                    if action=='export':(output/'adopted.tsv').write_text('')
                    if action=='publish':controller.h.dump(output/'counts.json',dict(spellings=0))
            with patch.object(controller.source,'verify',return_value={'complete':False}), \
                 patch.object(controller.subprocess,'run',side_effect=execute), \
                 patch.object(controller.h,'free_project',side_effect=AssertionError('Offline pass contacted model')):
                first=controller.run(args);second=controller.run(args)
                self.assertTrue(first['noChanges']);self.assertEqual(str(assets.resolve()),first['assets'])
                self.assertEqual(first,second)
                self.assertEqual(1,calls.count(('catalog_harness.py','prepare')))
                self.assertEqual(1,calls.count(('catalog_review.py','publish')))
                (assets/'token.dat').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'Changed pass inputs'):controller.run(args)


if __name__=='__main__':unittest.main()
