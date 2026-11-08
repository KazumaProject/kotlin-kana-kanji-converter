import argparse
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import collection_campaign as c


class CampaignTest(unittest.TestCase):
    def test_batch_and_large_word_count_do_not_end_an_unfinished_source_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=argparse.Namespace(work_dir=Path(tmp)/'campaign',resume_from=None,provider='coverage',
                policy=Path(tmp)/'policy',batch_requests=300,max_source_failures=3,retry_delay=65)
            states=[dict(complete=False,remainingCategories=2,missingCategories=0,errors=[],termRows=100000),
                    dict(complete=True,remainingCategories=0,missingCategories=0,errors=[],termRows=100001)]
            with patch.object(c.coverage_sources,'fetch') as fetch,patch.object(c.coverage_sources,'verify',side_effect=states):
                result=c.run(args)
            self.assertTrue(result['complete']);self.assertEqual(2,fetch.call_count)
            self.assertEqual((Path(tmp)/'campaign/batch-0000').resolve(),fetch.call_args_list[1].args[0].resume_from)

    def test_source_failure_is_preserved_as_incomplete_instead_of_publishing_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=argparse.Namespace(work_dir=Path(tmp)/'campaign',resume_from=None,provider='coverage',
                policy=Path(tmp)/'policy',batch_requests=300,max_source_failures=2,retry_delay=65)
            state=dict(complete=False,remainingCategories=1,missingCategories=0,errors=[{'reason':'HTTPError'}])
            with patch.object(c.coverage_sources,'fetch'),patch.object(c.coverage_sources,'verify',return_value=state),patch.object(c.time,'sleep'):
                with self.assertRaisesRegex(ValueError,'unresolved sources'):c.run(args)
            self.assertFalse(c.h.replay.read_json(args.work_dir/'campaign.json')['complete'])
