import copy
from pathlib import Path
import unittest
from unittest.mock import patch
import vocabulary_auto as auto


class AutomaticAdoptionTest(unittest.TestCase):
    def candidate(self):
        return dict(id='one', surface='fixture', proofs=[dict(id='p', source='esdb', wordnetOffsets=['1'], size=50, cmudict=True)], entries=[])

    def decide(self, candidate, proposal=None, actual=None):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root/'grammar').mkdir(); (root/'grammar/categories.tsv').write_text('category\nnoun\n')
            config = dict(assets=str(root), sources={'pin':'same'})
            with patch.object(auto.s, 'collect', return_value=([actual or candidate], {'pin':'same'})):
                return auto.decisions(config, [(candidate, proposal)], root, root)[0]

    def test_adopts_corroborated_source_record_without_human_or_api(self):
        self.assertEqual('include', self.decide(self.candidate())['decision'])

    def test_model_veto_insufficient_evidence_and_single_letters_are_deferred(self):
        c = self.candidate()
        self.assertEqual('defer', self.decide(c, {'decision':'defer'})['decision'])
        c['proofs'][0]['wordnetOffsets'] = []
        self.assertEqual('defer', self.decide(c)['decision'])
        c = self.candidate(); c['surface'] = 'x'
        self.assertEqual('defer', self.decide(c)['decision'])

    def test_edited_candidate_is_not_its_own_proof(self):
        c = self.candidate(); actual = copy.deepcopy(c); actual['surface'] = 'different'
        with self.assertRaises(ValueError):self.decide(c, actual=actual)

    def test_failed_previous_day_resumes_before_new_day(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = root / '2026-11-07'; old.mkdir(); (old/'run.json').write_text('{}')
            self.assertEqual('2026-11-07', auto.pending_day(root, '2026-11-08'))
            (root/'2026-11-07.json').write_text('{}')
            self.assertEqual('2026-11-08', auto.pending_day(root, '2026-11-08'))

    def test_json_snapshot_and_source_tuple_priority_match(self):
        c = self.candidate(); c['priority'] = [1, 35]
        actual = copy.deepcopy(c); actual['priority'] = (1, 35)
        self.assertEqual('include', self.decide(c, actual=actual)['decision'])

    def test_daily_checkpoint_prevents_duplicate_adoption(self):
        import argparse, tempfile, datetime
        from unittest.mock import MagicMock
        from zoneinfo import ZoneInfo
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            day = datetime.datetime.now(ZoneInfo('America/Toronto')).date().isoformat()
            run = root/day; run.mkdir(); (run/'run.json').write_text('{}')
            args = argparse.Namespace(work_dir=root, timezone='America/Toronto')
            connection = MagicMock(); connection.execute.return_value.fetchone.return_value = (0,)
            with patch.object(auto, 'adopt', return_value={'adopted':0}) as adoption, \
                    patch.object(auto.h, 'state', return_value=({}, connection)), \
                    patch.object(auto.h, 'prepare') as prepare:
                first = auto.daily(args); second = auto.daily(args)
                self.assertEqual(first, second)
                self.assertEqual(0, first['apiCallsThisCommand'])
                self.assertEqual(0, first['recordedApiAttempts'])
                self.assertEqual(1, adoption.call_count)
                prepare.assert_not_called()
