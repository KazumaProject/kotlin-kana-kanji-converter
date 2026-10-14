import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import finish_luna_reclassification as finish


class CompletionTests(unittest.TestCase):
    def test_incomplete_run_does_not_apply_or_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(finish.reclassification, 'load_results', side_effect=ValueError('Incomplete results')), \
                    patch.object(finish.reclassification, 'apply') as apply, \
                    patch.object(finish.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'Incomplete results'):
                    finish.finish(root)
                apply.assert_not_called()
                run.assert_not_called()
            report = json.loads((root / 'build/luna-classification/completion.json').read_text())
            self.assertEqual(report['state'], 'failed')
            self.assertEqual(report['stages'], [])

    def test_failed_build_never_reports_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(finish.reclassification, 'load_results', return_value=({}, [{}], {}, {'id': {}})), \
                    patch.object(finish.reclassification, 'apply') as apply, \
                    patch.object(finish.subprocess, 'run', side_effect=RuntimeError('build failed')):
                with self.assertRaisesRegex(RuntimeError, 'build failed'):
                    finish.finish(root)
                apply.assert_called_once()
            report = json.loads((root / 'build/luna-classification/completion.json').read_text())
            self.assertEqual(report['state'], 'failed')
            self.assertNotIn('archive_sha256', report)


if __name__ == '__main__':
    unittest.main()
