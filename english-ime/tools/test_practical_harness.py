import argparse
from collections import Counter
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import practical_harness as harness
import practical_sources as sources
import vocabulary_harness as shared
from replay_source import sha


def response(text, surface=None, kind='exact', trailing_literal=False):
    surface = text if surface is None else surface
    segments = [dict(surface=surface, kind=kind)]
    if trailing_literal:
        segments.append(dict(surface='x', kind='literal'))
    return dict(schemaVersion=1, input=text, candidates=[dict(rank=1, text=surface, segments=segments)])


class PracticalHarnessTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source_dir = self.root / 'sources'
        self.source_dir.mkdir()
        fixtures = {
            'ngsl-stats.csv': 'Lemma,Rank\nhello,1\nworld,2\nform,3\nfrom,4\nI,5\nmay,6\n',
            'ngsl-spoken-stats.csv': 'Lemma,Rank\nhello,1\nmarch,2\n',
            'ngsl-supplementary.csv': 'Monday,Mondays\nMay,Mays\nMarch,Marches\n',
            'codespell.txt': 'helo->hello\nwrold->world\nform->from\nwrld->world, disabled\nwrld->world, hello,\n',
            'codespell-README.rst': 'fixture source license evidence',
        }
        self.pins = json.loads(json.dumps(sources.PINS))
        for name, text in fixtures.items():
            path = self.source_dir / name
            path.write_text(text, encoding='utf-8')
            self.pins[name].update(sha256=sha(path), bytes=path.stat().st_size)
            if 'rows' in self.pins[name]:
                self.pins[name]['rows'] = len(text.splitlines()) - (0 if 'supplementary' in name else 1)
        self.pinning = patch.object(sources, 'PINS', self.pins)
        self.pinning.start()
        self.suite = self.root / 'suite'
        self.prepare_args = argparse.Namespace(source_dir=self.source_dir, out=self.suite, fetch_sources=False)
        harness.prepare(self.prepare_args)
        self.manifest, self.cases = harness.load_suite(self.suite)
        self.assets = self.root / 'assets'
        self.assets.mkdir()
        (self.assets / 'token.dat').write_bytes(b'fixture binary')
        self.cli = self.root / 'install/bin/english-ime'
        self.cli.parent.mkdir(parents=True)
        self.cli.write_text('fixture launcher')
        lib = self.cli.parent.parent / 'lib'
        lib.mkdir()
        (lib / 'english-ime.jar').write_bytes(b'fixture engine')
        self.args = argparse.Namespace(suite=self.suite, baseline_assets=self.assets,
            candidate_assets=None, cli=self.cli, baseline_cli=None, out=self.root / 'evaluation',
            split='all', rank_limit=24, jobs=1)
        self.calls = []
        self.pairs = [(sources.key(word), word) for word in sources.headwords(self.source_dir)]

    def tearDown(self):
        self.pinning.stop()
        self.temporary.cleanup()

    def fake_cli(self, cli, command, *arguments, capture=False):
        options = dict(zip(arguments[::2], arguments[1::2]))
        self.calls.append((command, options))
        if command == 'export-candidates':
            shared.write_lines(options['--out'], [dict(reading=r, surface=s, cost=1) for r, s in self.pairs])
            return subprocess.CompletedProcess([], 0)
        text = options['--text']
        candidates = [(reading, word) for reading, word in self.pairs if reading == sources.key(text)]
        result = response(text, candidates[0][1]) if candidates else response(text, kind='literal')
        return subprocess.CompletedProcess([], 0, stdout=json.dumps(result))

    def test_sources_keep_capitalization_and_provenance_without_assuming_inflections(self):
        words = sources.headwords(self.source_dir)
        self.assertEqual({'May', 'may', 'March', 'march', 'Monday', 'I', 'hello', 'world', 'form', 'from'}, set(words))
        self.assertEqual(2, len(words['hello']))
        self.assertNotIn('Mondays', words)
        self.assertEqual(1, words['Monday'][0]['line'])
        exact = [case for case in self.cases if case['scenario'] == 'basic-exact' and case['expected'] == ['I']][0]
        self.assertEqual('i', exact['input'])

    def test_listed_typos_require_single_unannotated_corroborated_correction(self):
        listed = [case for case in self.cases if case['scenario'] == 'typo-listed']
        self.assertEqual({'helo', 'wrold'}, {case['input'] for case in listed})
        self.assertTrue(all(case['synthetic'] is False for case in listed))
        self.assertTrue(all(case['proofs'][0]['sourceCorrection'] == case['expected'][0] for case in listed))

    def test_all_keyboard_letters_and_edit_kinds_are_supported(self):
        self.assertEqual(set('abcdefghijklmnopqrstuvwxyz'), set(sources.NEIGHBOR))
        edits = list(sources.edits('minimum', {'minimum'}))
        self.assertEqual({'deletion', 'insertion', 'substitution', 'transposition'}, {kind for kind, _, _ in edits})
        for operation, changed, position in edits:
            if operation == 'deletion':
                self.assertEqual('minimum'[:position] + 'minimum'[position + 1:], changed)
            elif operation == 'insertion':
                self.assertEqual(len('minimum') + 1, len(changed))
            elif operation == 'substitution':
                self.assertEqual(1, sum(a != b for a, b in zip('minimum', changed)))
            else:
                self.assertEqual(Counter('minimum'), Counter(changed))
        self.assertEqual([], list(sources.edits('I', {'i'})))

    def test_synthetic_edits_skip_basic_real_word_collisions(self):
        known = {sources.key(word) for word in sources.headwords(self.source_dir)}
        self.assertTrue(all(case['input'] not in known for case in self.cases if case['scenario'] == 'typo-synthetic'))

    def test_sampling_is_reproducible_and_splits_do_not_leak_the_same_target(self):
        first = harness.select_cases(self.cases, 'all', 16)
        self.assertEqual(first, harness.select_cases(list(reversed(self.cases)), 'all', 16))
        splits = {}
        for case in self.cases:
            target = sources.key(case['expected'][0])
            splits.setdefault(target, set()).add(case['split'])
        self.assertTrue(all(len(values) == 1 for values in splits.values()))
        self.assertTrue(all(case['split'] == 'dev' for case in harness.select_cases(self.cases, 'dev', 100)))

    def test_literal_echo_partial_copy_and_wrong_case_are_not_dictionary_success(self):
        case = dict(input='i', expected=['I'])
        self.assertEqual(None, harness.score(case, response('i', 'I', 'literal'))['rank'])
        self.assertEqual(None, harness.score(case, response('i', 'I', trailing_literal=True))['rank'])
        self.assertEqual(None, harness.score(case, response('i', 'i'))['rank'])
        self.assertEqual(1, harness.score(case, response('i', 'I'))['rank'])

    def test_literal_preservation_uses_separate_metric(self):
        case = dict(id='id', input='abc123xyz', expected=['abc123xyz'], scenario='preserve', operation='', proofs=[])
        detail = harness.score(case, response(case['input'], kind='literal'))
        metrics = harness.metrics([case], {'id': detail}, set())['scenario:preserve']
        self.assertEqual(1, metrics['preservedTop1'])
        self.assertEqual(0, metrics['dictionaryTop1'])

    def test_coverage_denominator_includes_unsampled_missing_targets(self):
        cases = [case for case in self.cases if case['scenario'] == 'basic-exact']
        metrics = harness.metrics(cases, {}, {('i', 'I')})['scenario:basic-exact']
        self.assertEqual(10, metrics['cases'])
        self.assertEqual(1, metrics['targetCovered'])
        self.assertNotIn('rankCases', metrics)

    def test_prepare_and_report_retain_source_licenses_and_changes(self):
        attribution = json.loads((self.suite / 'attribution.json').read_text())
        self.assertEqual('CC-BY-SA-4.0', attribution['collectionLicense'])
        self.assertIn('CC-BY-SA-3.0', (self.suite / 'ATTRIBUTION.txt').read_text())
        self.assertTrue(attribution['changes'])
        with patch.object(shared, 'cli_run', self.fake_cli):
            result = harness.evaluate(self.args)
        report = json.loads(Path(result['report']).read_text())
        self.assertEqual(attribution, report['attribution'])
        self.assertFalse(report['acceptanceThresholdsAgreed'])
        self.assertTrue(report['cliOnly'])
        self.assertEqual(report['results']['before'], report['results']['after'])
        self.assertEqual((self.suite / 'ATTRIBUTION.txt').read_bytes(), (self.args.out / 'ATTRIBUTION.txt').read_bytes())

    def test_missing_license_and_modified_source_are_rejected(self):
        (self.suite / 'attribution.json').unlink()
        with self.assertRaises(OSError):
            harness.load_suite(self.suite)
        (self.source_dir / 'codespell.txt').write_text('unverified source')
        with self.assertRaisesRegex(ValueError, 'changed pinned source'):
            sources.verify(self.source_dir)

    def test_existing_suite_cannot_be_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'already exists'):
            harness.prepare(self.prepare_args)

    def test_interrupted_evaluation_resumes_successful_queries(self):
        conversion_calls = 0
        def interrupted(cli, command, *arguments, **kwargs):
            nonlocal conversion_calls
            if command == 'convert':
                conversion_calls += 1
                if conversion_calls == 4:
                    raise subprocess.TimeoutExpired('fixture-cli', 1)
            return self.fake_cli(cli, command, *arguments, **kwargs)
        with patch.object(shared, 'cli_run', interrupted), self.assertRaises(subprocess.TimeoutExpired):
            harness.evaluate(self.args)
        self.assertEqual(3, len(shared.json_lines(self.args.out / 'before-ranks.jsonl')))
        self.calls.clear()
        with patch.object(shared, 'cli_run', self.fake_cli):
            result = harness.evaluate(self.args)
        self.assertEqual(self.args.rank_limit - 3, len([call for call in self.calls if call[0] == 'convert']))
        self.assertTrue(result['noMeasuredRegression'])
        self.calls.clear()
        with patch.object(shared, 'cli_run', self.fake_cli):
            harness.evaluate(self.args)
        self.assertEqual([], self.calls)

    def test_changed_engine_cannot_resume_old_run(self):
        with patch.object(shared, 'cli_run', self.fake_cli):
            harness.evaluate(self.args)
        (self.cli.parent.parent / 'lib/english-ime.jar').write_bytes(b'new engine')
        with self.assertRaisesRegex(ValueError, 'Resume requires identical'):
            harness.evaluate(self.args)

    def test_parallel_queries_keep_the_same_results_and_checkpoint_order(self):
        with patch.object(shared, 'cli_run', self.fake_cli):
            first = harness.evaluate(self.args)
            original_cache = shared.json_lines(self.args.out / 'before-ranks.jsonl')
            self.args.jobs = 4
            self.args.out = self.root / 'parallel-evaluation'
            parallel = harness.evaluate(self.args)
        self.assertEqual(first['results'], parallel['results'])
        self.assertEqual(original_cache, shared.json_lines(self.args.out / 'before-ranks.jsonl'))

    def test_evaluation_cannot_write_into_its_inputs(self):
        self.args.out = self.assets
        with self.assertRaisesRegex(ValueError, 'must be separate'):
            harness.evaluate(self.args)
        self.assertEqual(['token.dat'], [path.name for path in self.assets.iterdir()])

    def test_modified_copied_attribution_is_rejected_on_resume(self):
        with patch.object(shared, 'cli_run', self.fake_cli):
            harness.evaluate(self.args)
        (self.args.out / 'ATTRIBUTION.txt').write_text('missing source attribution')
        with self.assertRaisesRegex(ValueError, 'Changed copied suite or attribution'):
            harness.evaluate(self.args)

    def test_regressions_include_preservation_top5_and_exact_top1(self):
        cases = [dict(id='exact', scenario='basic-exact', input='hello', expected=['hello']),
            dict(id='typo', scenario='typo-listed', input='helo', expected=['hello']),
            dict(id='control', scenario='preserve', input='Kazuma', expected=['Kazuma'])]
        before = {case['id']: dict(rank=1, displayRank=1) for case in cases}
        after = {'exact': dict(rank=2, displayRank=2), 'typo': dict(rank=6, displayRank=6),
                 'control': dict(rank=None, displayRank=None)}
        self.assertEqual(3, len(harness.regressions(cases, before, after)))

    def test_unsampled_coverage_regression_is_detected(self):
        self.args.rank_limit = 1
        self.args.candidate_assets = self.root / 'after'
        self.args.candidate_assets.mkdir()
        (self.args.candidate_assets / 'token.dat').write_bytes(b'changed dictionary')
        original = self.fake_cli
        def changed(cli, command, *arguments, **kwargs):
            options = dict(zip(arguments[::2], arguments[1::2]))
            old = self.pairs
            if options['--assets'] == self.args.candidate_assets.resolve():
                self.pairs = [(r, s) for r, s in old if s != 'world']
            try:
                return original(cli, command, *arguments, **kwargs)
            finally:
                self.pairs = old
        with patch.object(shared, 'cli_run', changed):
            result = harness.evaluate(self.args)
        self.assertGreater(result['coverageRegressions'], 0)
        self.assertFalse(result['noMeasuredRegression'])

    def test_download_with_wrong_hash_does_not_leave_a_source_file(self):
        destination = self.root / 'download'
        with patch.object(sources.urllib.request, 'urlopen', return_value=io.BytesIO(b'wrong')):
            with self.assertRaisesRegex(ValueError, 'differs from pin'):
                sources.fetch(destination)
        self.assertEqual([], list(destination.iterdir()))

    def test_work_outputs_inside_a_git_checkout_are_rejected(self):
        checkout = self.root / 'checkout'
        checkout.mkdir()
        (checkout / '.git').write_text('gitdir: fixture')
        self.prepare_args.out = checkout / 'suite'
        with self.assertRaisesRegex(ValueError, 'outside the repository'):
            harness.prepare(self.prepare_args)


if __name__ == '__main__':
    unittest.main()
