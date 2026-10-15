import contextlib
import gzip
import io
import json
import unittest

import classified_distribution as d
import classification_reviews as reviews
from test_classified_distribution import DistributionTest


class ReviewTest(unittest.TestCase):
    def setUp(self):
        DistributionTest.setUp(self)
        with contextlib.redirect_stdout(io.StringIO()):
            d.freeze(self.root, self.accepted, self.dispositions, self.database, self.manual, self.taxonomy)

    def test_exclusion_addition_survive_freeze_and_repeated_apply(self):
        directory = self.root / reviews.DIRECTORY
        with gzip.open(directory / 'distribution-decisions.tsv.gz', 'rt') as stream:
            baseline = next(line.rstrip('\n').split('\t') for line in stream)
        ledger = directory / 'reviews/001.jsonl'
        ledger.parent.mkdir()
        entries = [dict(action='exclude', reading=baseline[0], surface=baseline[1],
                        candidate_key=d.key(*baseline[:2]), baseline=baseline, reason='user correction'),
                   dict(action='add', reading='か', surface='加', candidate_key=d.key('か', '加'),
                        baseline=None, reason='user correction', categories=['person'],
                        added_record=dict(left_id=1, right_id=1, cost=8400),
                        evidence=dict(kind='user_confirmation', reading='か', surface='加',
                                      categories=['person'], reference='user confirmation'))]
        ledger.write_text(''.join(json.dumps(e) + '\n' for e in entries))
        with contextlib.redirect_stdout(io.StringIO()):
            reviews.apply_saved(self.root, commit=True)
            frozen = (directory / 'distribution-candidates.tsv.gz').read_bytes()
            reviews.apply_saved(self.root, commit=True)
            self.assertEqual(frozen, (directory / 'distribution-candidates.tsv.gz').read_bytes())
            d.freeze(self.root, self.accepted, self.dispositions, self.database, self.manual, self.taxonomy)
            d.verify(self.root)
        with gzip.open(directory / 'distribution-candidates.tsv.gz', 'rt') as stream:
            rows = [line.rstrip('\n').split('\t') for line in stream]
        self.assertFalse(any(row[1] == baseline[0] and row[5] == baseline[1] for row in rows))
        self.assertIn(['person', 'か', '1', '1', '8400', '加'], rows)
