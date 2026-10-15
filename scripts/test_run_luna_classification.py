import json
from pathlib import Path
import tempfile
import sys
import io
import contextlib
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import run_luna_classification as c

ROWS = [{'candidate_key': 'key', 'reading': 'ねこ', 'surface': '猫'}]
TAXONOMY = {'categories': [{'id': 'term', 'definition': '一般語'}]}
REPLY = {'results': [{'id': 0, 'action': 'adopt', 'categories': ['term'], 'reason': '一般語として成立する'}]}

def fixture_evidence(evidence):
    evidence.mkdir(parents=True, exist_ok=True)
    c.ledger.write_jsonl(evidence / 'request.jsonl', ROWS)
    c.save(evidence / 'schema.json', c.schema({'term'}, 1))
    (evidence / 'prompt.txt').write_text(c.prompt(ROWS, TAXONOMY))
    c.save(evidence / 'invocation.json', {'model': c.MODEL, 'reasoning_effort': c.EFFORT})

class ControllerTests(unittest.TestCase):
    def setUp(self): c.STOP.clear()
    def test_finish_runs_after_completed_classification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            request = root / 'build/luna-classification/requests/000000.jsonl'
            c.ledger.write_jsonl(request, ROWS)
            c.save(request.with_suffix('.meta.json'), {'target_sha256': 'hash',
                'candidate_keys': ['key'], 'model': c.MODEL, 'reasoning_effort': c.EFFORT})
            c.save(root / 'src/main/classification/categories.json', TAXONOMY)
            completed = {'key': {'response': {'action': 'adopt'}}}
            with patch.object(sys, 'argv', ['controller', '--root', str(root), '--workers', '9', '--finish']), \
                    patch.object(c, 'load_completed', return_value=({'files': {'targets.jsonl.gz': 'hash'}}, ROWS, {}, completed)), \
                    patch.object(c.subprocess, 'run', return_value=SimpleNamespace(stdout='test-cli')), \
                    patch.object(c.signal, 'signal'), \
                    patch('finish_luna_reclassification.finish', return_value={'state': 'complete'}) as finish, \
                    patch.object(c, 'run_batch') as classify:
                c.main()
                classify.assert_not_called()
                finish.assert_called_once_with(root)
    def test_validate_exact_mapping(self):
        rows = c.validate(json.dumps(REPLY), ROWS, {'term'})
        self.assertEqual(rows[0]['surface'], '猫')
        self.assertEqual(rows[0]['model'], 'gpt-5.6-luna')
        self.assertEqual(rows[0]['reasoning_effort'], 'max')
        self.assertEqual(rows[0]['policy_version'], c.POLICY_VERSION)
    def test_reject_missing_duplicate_invalid(self):
        cases = [{'results': []}, {'results': REPLY['results'] * 2},
                 {'results': [dict(REPLY['results'][0], id=True)]},
                 {'results': [dict(REPLY['results'][0], categories=['unknown'])]},
                 {'results': [dict(REPLY['results'][0], action='hold')]},
                 {'results': [dict(REPLY['results'][0], reason='unknown')]}]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.validate(json.dumps(value), ROWS, {'term'})
    def test_mock_process_and_evidence(self):
        class Process:
            returncode = 0
            def __init__(self, cmd, **kw):
                self.cmd = cmd
                Path(cmd[cmd.index('-o') + 1]).write_text(json.dumps(REPLY))
            def communicate(self, text, timeout):
                self.text = text
            def terminate(self): pass
        with tempfile.TemporaryDirectory() as tmp, patch.object(c.subprocess, 'Popen', Process):
            root = Path(tmp).resolve()
            name, state, result = c.run_batch(('batch', ROWS), root, TAXONOMY, 'hash', 'test-cli', 5)
            self.assertEqual(state, 'completed')
            output, evidence = result
            invocation = json.loads((evidence / 'invocation.json').read_text())
            self.assertIn('gpt-5.6-luna', invocation['command'])
            self.assertIn('model_reasoning_effort="max"', invocation['command'])
            c.commit(root / 'build/luna-classification', name, output, evidence, 'hash', 'test-cli')
            self.assertTrue((root / 'build/luna-classification/results/batch.jsonl').exists())
            self.assertEqual(json.loads((root / 'build/luna-classification/results/batch.meta.json').read_text())['candidate_keys'], ['key'])
    def test_model_access_failure_stops_without_fallback(self):
        class Process:
            returncode = 1
            def __init__(self, cmd, **kw): kw['stderr'].write('Model not available: gpt-5.6-luna'); kw['stderr'].flush()
            def communicate(self, *args, **kw): pass
            def terminate(self): pass
        with tempfile.TemporaryDirectory() as tmp, patch.object(c.subprocess, 'Popen', Process):
            _, state, result = c.run_batch(('batch', ROWS), Path(tmp), TAXONOMY, 'hash', 'version', 5)
            self.assertEqual(state, 'failed')
            self.assertIsNone(result)
            self.assertTrue(c.STOP.is_set())
    def test_completed_pilot_is_skipped_and_remaining_saved(self):
        rows = [dict(ROWS[0], candidate_key='pilot'), dict(ROWS[0], candidate_key='pending')]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            request = root / 'build/luna-classification/requests/000000.jsonl'
            c.ledger.write_jsonl(request, rows)
            c.save(request.with_suffix('.meta.json'), {'target_sha256': 'hash',
                'candidate_keys': ['pilot', 'pending'], 'model': c.MODEL, 'reasoning_effort': c.EFFORT})
            c.save(root / 'src/main/classification/categories.json', TAXONOMY)
            def classify(job, *args):
                name, remaining = job
                self.assertEqual([r['candidate_key'] for r in remaining], ['pending'])
                evidence = root / 'build/luna-classification/attempts/test'
                fixture_evidence(evidence)
                (evidence / 'reply.json').write_text(json.dumps(REPLY))
                return name, 'completed', (c.validate(json.dumps(REPLY), remaining, {'term'}), evidence)
            completed = {'pilot': {'response': {'action': 'reject'}}}
            with patch.object(sys, 'argv', ['controller', '--root', str(root), '--workers', '1']), \
                 patch.object(c.ledger, 'load_results', return_value=({'files': {'targets.jsonl.gz': 'hash'}}, rows, {}, completed)), \
                 patch.object(c.subprocess, 'run', return_value=SimpleNamespace(stdout='test-cli')), \
                 patch.object(c, 'run_batch', side_effect=classify), patch.object(c.signal, 'signal'):
                c.main()
            results = list((root / 'build/luna-classification/results').glob('*.jsonl'))
            self.assertEqual(len(results), 1)
            self.assertEqual(c.ledger.jsonl(results[0])[0]['candidate_key'], 'pending')

    def test_usage_limit_global_stop_preserves_evidence(self):
        class Process:
            returncode = 1
            def __init__(self, cmd, **kw):
                kw['stderr'].write("You've hit your usage limit. Try again after reset."); kw['stderr'].flush()
            def communicate(self, *args, **kw): pass
            def terminate(self): pass
        with tempfile.TemporaryDirectory() as tmp, patch.object(c.subprocess, 'Popen', Process) as launch:
            root = Path(tmp).resolve()
            _, state, result = c.run_batch(('quota', ROWS), root, TAXONOMY, 'hash', 'cli', 5)
            self.assertEqual(state, 'failed')
            self.assertIsNone(result)
            self.assertTrue(c.STOP.is_set())
            evidence = root / 'build/luna-classification/attempts/quota/1'
            self.assertIn('usage limit', (evidence / 'stderr.txt').read_text())
            self.assertTrue((evidence / 'outcome.json').exists())
            self.assertFalse((root / 'build/luna-classification/results').exists())
            c.STOP.clear()
            _, resumed_state, _ = c.run_batch(('quota', ROWS), root, TAXONOMY, 'hash', 'cli', 5)
            self.assertEqual(resumed_state, 'failed')
            self.assertEqual(len(list(evidence.parent.iterdir())), 2)

    def test_status_does_not_create_paths_and_reads_failed_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); directory = root / 'build/luna-classification'
            loaded = ({}, ROWS, {}, {})
            with patch.object(c.ledger, 'load_results', return_value=loaded), contextlib.redirect_stdout(io.StringIO()) as out:
                c.report_status(root, directory)
            self.assertEqual(json.loads(out.getvalue())['pending'], 1)
            self.assertFalse(directory.exists())
            directory.mkdir(parents=True)
            db = sqlite3.connect(directory / 'progress.sqlite3')
            db.execute('CREATE TABLE jobs (name TEXT PRIMARY KEY, state TEXT, candidate_keys TEXT, policy_version TEXT)')
            db.execute('INSERT INTO jobs VALUES (?,?,?,?)', ('failed', 'failed', json.dumps(['key']), c.POLICY_VERSION))
            db.commit(); db.close()
            before = (directory / 'progress.sqlite3').read_bytes()
            with patch.object(c.ledger, 'load_results', return_value=loaded), contextlib.redirect_stdout(io.StringIO()) as out:
                c.report_status(root, directory)
            self.assertEqual(json.loads(out.getvalue())['failed'], 1)
            self.assertEqual((directory / 'progress.sqlite3').read_bytes(), before)
            self.assertFalse((directory / 'results.lock').exists())

    def test_interrupted_commit_accepts_no_partial_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve(); evidence = directory / 'attempts/test'; fixture_evidence(evidence)
            (evidence / 'reply.json').write_text(json.dumps(REPLY))
            output = c.validate(json.dumps(REPLY), ROWS, {'term'})
            c.STOP.set()
            self.assertFalse(c.commit(directory, 'batch', output, evidence, 'hash', 'cli'))
            self.assertFalse((directory / 'results').exists())
            c.STOP.clear()
            # Interrupted publication has metadata but no visible JSONL; retry publishes the complete pair.
            original_replace = c.os.replace
            def interrupt(source, destination):
                if str(destination).endswith('.jsonl'): raise OSError('simulated interrupted publication')
                return original_replace(source, destination)
            with patch.object(c.os, 'replace', side_effect=interrupt), self.assertRaises(OSError):
                c.commit(directory, 'batch', output, evidence, 'hash', 'cli')
            self.assertTrue((directory / 'results/batch.meta.json').exists())
            self.assertEqual(list((directory / 'results').glob('*.jsonl')), [])
            self.assertTrue(c.commit(directory, 'batch', output, evidence, 'hash', 'cli'))
            self.assertEqual(c.ledger.jsonl(directory / 'results/batch.jsonl'), output)

    def test_invalid_model_reply_retries_without_synthetic_reject(self):
        class Process:
            returncode = 0
            def __init__(self, cmd, **kw):
                Path(cmd[cmd.index('-o') + 1]).write_text('{"results": []}')
            def communicate(self, *args, **kw): pass
            def terminate(self): pass
        with tempfile.TemporaryDirectory() as tmp, patch.object(c.subprocess, 'Popen', Process), patch.object(c.STOP, 'wait', return_value=False):
            root = Path(tmp).resolve()
            _, state, result = c.run_batch(('invalid', ROWS), root, TAXONOMY, 'hash', 'cli', 5)
            self.assertEqual(state, 'failed')
            self.assertIsNone(result)
            self.assertEqual(len(list((root / 'build/luna-classification/attempts/invalid').iterdir())), 3)
            self.assertFalse((root / 'build/luna-classification/results').exists())

    def test_old_hold_policy_never_counts_as_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); directory = root / 'build/luna-classification'
            path = directory / 'results/old.jsonl'
            c.ledger.write_jsonl(path, [dict(ROWS[0], action='hold')])
            c.save(path.with_suffix('.meta.json'), {'model': c.MODEL})
            with self.assertRaisesRegex(ValueError, 'Old or unknown classification policy'):
                c.load_completed(root, directory)
            c.save(path.with_suffix('.meta.json'), {'policy_version': c.POLICY_VERSION})
            with self.assertRaisesRegex(ValueError, 'Old or unknown row classification policy'):
                c.load_completed(root, directory)

    def test_reject_is_valid_judgment_and_hold_is_not(self):
        rejected = {'results': [dict(REPLY['results'][0], action='reject', categories=[], reason='表記と読みの対応が不適切') ]}
        output = c.validate(json.dumps(rejected), ROWS, {'term'})
        self.assertEqual(output[0]['action'], 'reject')
        self.assertEqual(output[0]['policy_version'], c.POLICY_VERSION)
        rejected['results'][0]['action'] = 'hold'
        with self.assertRaises(ValueError): c.validate(json.dumps(rejected), ROWS, {'term'})

    def test_successful_lexical_error_words_are_not_account_errors(self):
        reply = {'results': [dict(REPLY['results'][0], reason='AuthenticationとUnauthorizedは認証用語。usage limitは制限の一般表現') ]}
        class Process:
            returncode = 0
            def __init__(self, cmd, **kw):
                Path(cmd[cmd.index('-o') + 1]).write_text(json.dumps(reply))
                kw['stdout'].write(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(reply)}}) + '\n')
                kw['stdout'].flush()
                kw['stderr'].write('Authentication Unauthorized usage limit in successful diagnostic context')
                kw['stderr'].flush()
            def communicate(self, *args, **kw): pass
            def terminate(self): pass
        with tempfile.TemporaryDirectory() as tmp, patch.object(c.subprocess, 'Popen', Process):
            root = Path(tmp).resolve()
            _, state, result = c.run_batch(('lexical', ROWS), root, TAXONOMY, 'hash', 'cli', 5)
            self.assertEqual(state, 'completed')
            self.assertFalse(c.STOP.is_set())
            output, evidence = result
            c.commit(root / 'build/luna-classification', 'lexical', output, evidence, 'hash', 'cli')
            meta = json.loads((root / 'build/luna-classification/results/lexical.meta.json').read_text())
            for label, filename in [('request', 'request.jsonl'), ('prompt', 'prompt.txt'), ('schema', 'schema.json'), ('invocation', 'invocation.json')]:
                self.assertEqual(meta[label + '_sha256'], c.digest(evidence / filename))

    def test_actual_quota_error_events_trigger_fatal_detection(self):
        for event in [{'type': 'error', 'message': 'insufficient_quota'},
                      {'type': 'turn.failed', 'error': {'message': 'Usage limit reached'}}]:
            diagnostics = c.error_diagnostics(0, '', json.dumps(event))
            self.assertTrue(c.permanent_error(diagnostics))
        self.assertEqual(c.error_diagnostics(0, 'Unauthorized', json.dumps({'type': 'item.completed', 'item': {'text': 'Authentication'}})), '')

    def test_prompt_exact_reading_policy(self):
        p = c.prompt(ROWS, TAXONOMY)
        self.assertIn('接頭部分だけの一致は採用不可', p)
        self.assertIn('未検証', p)
    def test_permanent_error_detection(self):
        for message in ['Unsupported reasoning effort max', 'model does not exist', 'Authentication failed']:
            self.assertTrue(c.permanent_error(message))
        self.assertFalse(c.permanent_error('429 retry later'))

if __name__ == '__main__': unittest.main()
