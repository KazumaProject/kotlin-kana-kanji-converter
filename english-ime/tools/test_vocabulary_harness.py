import argparse
import datetime as dt
import io
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import vocabulary_harness as harness
import vocabulary_sources as sources


def candidate(identifier='one'):
    return dict(id=identifier, surface='fixture gap', priority=[1, 1, 0, 'fixture gap'],
        entries=[dict(zip(sources.FIELDS, ['fixture', 'fixture gap', 'fixture gap', 'domain_daily,noun',
            'daily', 'https://example.org/source', 'fixture:1']))], proofs=[dict(id='proof', source='fixture')])


def decision(identifier='one', action='include'):
    return dict(id=identifier, decision=action, reason='Attested form in the supplied lexical source', proofIds=['proof'])


def response(items, finish='STOP'):
    return json.dumps({'candidates': [{'finishReason': finish,
        'content': {'parts': [{'text': json.dumps({'items': items})}]}}],
        'usageMetadata': {'promptTokenCount': 12, 'candidatesTokenCount': 8}}).encode()


class VocabularyHarnessTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        harness.write_lines(self.root / 'candidates.jsonl', [candidate()])
        harness.dump(self.root / 'run.json', dict(schemaVersion=1, candidatesSha256=harness.replay.sha(self.root / 'candidates.jsonl'),
            selectedCandidates=1, availableCandidates=1, model=harness.MODEL,
            promptSha256=hashlib.sha256((harness.PROMPT + json.dumps(harness.DECISION_SCHEMA, sort_keys=True)).encode()).hexdigest()))
        with sqlite3.connect(self.root / 'state.sqlite3') as connection:
            connection.executescript('''create table candidates(id text primary key,position integer,payload text,
                proposal text,decision text,result text);
                create table attempts(id integer primary key,started text,model text,ids text,status text,
                request_sha256 text,response_sha256 text,usage text);''')
            connection.execute('insert into candidates(id,position,payload) values(?,?,?)', ('one', 0, json.dumps(candidate())))
        self.proof = dict(project_id='test-project', model=harness.MODEL, free_tier=True, billing_enabled=False,
            api_project_verified=True, api_quota_verified=True, rpm=15, rpd=500, tpm=250000,
            verified_at=dt.datetime.now(dt.timezone.utc).isoformat())
        harness.dump(self.root / 'free.json', self.proof)
        (self.root / 'key').write_text('test-secret')
        self.args = argparse.Namespace(work_dir=self.root, decisions=None, free_proof=self.root / 'free.json',
            api_key_file=self.root / 'key', quota_dir=self.root / 'quota', max_requests=1, daily_requests=20,
            batch_size=20, wait=False)

    def tearDown(self):
        self.temporary.cleanup()

    def test_proposal_does_not_authorize_export_and_resume_does_not_resend(self):
        calls = []
        def provider(payload, key):
            calls.append(payload)
            self.assertEqual('test-secret', key)
            return response([decision()])
        self.assertEqual(0, harness.review(self.args, provider)['remaining'])
        self.assertEqual(0, harness.review(self.args, provider)['requests'])
        self.assertEqual(1, len(calls))
        _, connection = harness.state(self.root)
        self.assertEqual([], harness.approved_entries(connection)[0])
        connection.close()
        harness.write_lines(self.root / 'review.jsonl', [decision()])
        self.args.decisions = self.root / 'review.jsonl'
        harness.review(self.args)
        self.assertEqual(1, harness.status(self.args)['addedSurfaces'])
        harness.review(self.args)  # Same final decision is idempotent.
        self.assertEqual(1, harness.status(self.args)['addedSurfaces'])

    def test_quota_errors_stop_without_adopting_or_losing_candidates(self):
        def provider(*unused):
            raise urllib.error.HTTPError('https://example.org', 429, 'quota', {}, io.BytesIO())
        result = harness.review(self.args, provider)
        self.assertEqual('http_429', result['paused'])
        self.assertEqual({'pending': 1}, harness.status(self.args)['finalDecisions'])
        # A restart in the same minute does not resend the failed request.
        result = harness.review(self.args, lambda *unused: self.fail('rate limit was ignored'))
        self.assertEqual('minute_limit', result['paused'])

    def test_timeout_is_counted_but_not_finalized(self):
        def provider(*unused):
            raise TimeoutError('transport timed out')
        self.assertEqual('TimeoutError', harness.review(self.args, provider)['paused'])
        self.assertEqual({'TimeoutError': 1}, harness.status(self.args)['attempts'])

    def test_invalid_response_is_not_partial_progress(self):
        self.assertEqual('JSONDecodeError', harness.review(self.args, lambda *unused: b'{invalid')['paused'])
        _, connection = harness.state(self.root)
        self.assertIsNone(connection.execute('select proposal from candidates').fetchone()[0])
        connection.close()

    def test_review_cannot_invent_ids_or_sources_or_omit_rows(self):
        mutations = [[decision('unknown')], [decision(), decision()], [],
            [dict(decision(), proofIds=['invented'])], [dict(decision(), reason='')],
            [dict(decision(), surface='replacement')], [dict(decision(), proofIds=[])]]
        for items in mutations:
            with self.subTest(items=items), self.assertRaises(ValueError):
                harness.validate_decisions(items, [candidate()])
        for finish in ['MAX_TOKENS', 'SAFETY']:
            with self.assertRaises(ValueError):
                harness.parse_response(json.loads(response([decision()], finish)), [candidate()])
        for envelope in [[], None, {'candidates': []},
                         {'candidates': [{'finishReason': 'STOP', 'content': 'invalid'}]}]:
            with self.subTest(envelope=envelope), self.assertRaises(ValueError):
                harness.parse_response(envelope, [candidate()])

    def test_candidate_file_and_database_tampering_are_detected(self):
        with sqlite3.connect(self.root / 'state.sqlite3') as connection:
            connection.execute("update candidates set payload='{}'")
        with self.assertRaisesRegex(ValueError, 'Database candidates'):
            harness.state(self.root)
        (self.root / 'candidates.jsonl').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            harness.state(self.root)

    def test_final_review_is_immutable(self):
        harness.write_lines(self.root / 'first.jsonl', [decision()])
        self.args.decisions = self.root / 'first.jsonl'
        harness.review(self.args)
        harness.write_lines(self.root / 'second.jsonl', [decision(action='exclude')])
        self.args.decisions = self.root / 'second.jsonl'
        with self.assertRaisesRegex(ValueError, 'already exists'):
            harness.review(self.args)

    def test_refuses_stale_paid_wrong_model_and_unverified_free_proofs(self):
        for changes in [dict(billing_enabled=True), dict(free_tier=False), dict(api_project_verified=False),
                        dict(model='paid-model'), dict(rpd=0),
                        dict(verified_at=(dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)).isoformat()),
                        dict(verified_at='2026-01-01T00:00:00')]:
            harness.dump(self.root / 'invalid.json', self.proof | changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                harness.free_project(self.root / 'invalid.json')

    def test_prompt_change_requires_a_new_review_run(self):
        with patch.object(harness, 'PROMPT', 'changed instructions'), self.assertRaisesRegex(ValueError, 'changed'):
            harness.review(self.args, lambda *unused: self.fail('changed prompt was sent'))

    def test_shared_daily_budget_counts_attempts_across_runs_and_resets_in_pacific_time(self):
        ledger = self.root / 'quota.sqlite3'
        now = dt.datetime(2026, 11, 7, 12, tzinfo=dt.timezone.utc)
        self.assertIsNone(harness.reserve_request(ledger, self.proof, 1, 1000, now))
        self.assertEqual('daily_limit', harness.reserve_request(ledger, self.proof, 1, 1000, now + dt.timedelta(hours=2)))
        self.assertIsNone(harness.reserve_request(ledger, self.proof, 1, 1000, now + dt.timedelta(days=1)))
        with self.assertRaises(ValueError):
            harness.reserve_request(ledger, self.proof, 1, 999999, now)

    def test_keeps_work_and_symlink_targets_outside_repo(self):
        with self.assertRaises(ValueError):
            harness.external(harness.REPO / 'build/harness')
        (self.root / 'repo').symlink_to(harness.REPO, target_is_directory=True)
        with self.assertRaises(ValueError):
            harness.external(self.root / 'repo/cache')
        other = self.root / 'other-checkout'
        (other / '.git').mkdir(parents=True)
        with self.assertRaises(ValueError):
            harness.external(other / 'ignored-build/work')

    def test_lock_rejects_concurrent_process_work(self):
        with harness.lock(self.root):
            with self.assertRaises(ValueError):
                with harness.lock(self.root):
                    self.fail('concurrent lock acquired')

    def test_evaluation_does_not_count_literal_echo_as_success(self):
        assets = self.root / 'assets'
        assets.mkdir()
        config = harness.replay.read_json(self.root / 'run.json')
        config.update(assets=str(assets), assetHashes={})
        harness.dump(self.root / 'run.json', config)
        harness.write_lines(self.root / 'cases.jsonl', [dict(id='oov', input='fixture gap', expected='fixture gap',
            mode='exact', domain='daily', source='https://example.org/heldout')])
        def run(cli, command, *arguments, **unused):
            if command == 'export-candidates':
                Path(arguments[-1]).write_text('')
            else:
                return argparse.Namespace(stdout=json.dumps({'candidates': [dict(rank=1, text='fixture gap',
                    segments=[dict(kind='literal')])]}))
        args = argparse.Namespace(work_dir=self.root, cli=Path('/unused'), assets=assets,
                                  cases=self.root / 'cases.jsonl', sample_size=200)
        with patch.object(harness, 'cli_run', run):
            result = harness.evaluate(args)
        self.assertEqual(0, result['results']['after']['all']['covered'])
        self.assertEqual(0, result['results']['after']['all']['top10'])

    def test_reading_contract_preserves_compact_and_spaced_forms(self):
        self.assertEqual({'two-factor authentication', 'twofactor authentication', 'twofactorauthentication'},
                         harness.readings('two-factor authentication'))
        self.assertEqual({"y'all", 'yall'}, harness.readings('y’all'))

    def test_ranking_sample_is_stable_balanced_and_does_not_drop_uncovered_cases(self):
        rows = [dict(id=domain + str(index), domain=domain, expected='unknown')
                for domain in sorted(sources.DOMAINS) for index in range(10)]
        sample = harness.sample_cases(rows, 8)
        self.assertEqual(sample, harness.sample_cases(list(reversed(rows)), 8))
        self.assertEqual({domain: 2 for domain in sources.DOMAINS},
                         dict(harness.Counter(row['domain'] for row in sample)))

    def test_matching_one_node_does_not_turn_a_partial_literal_echo_into_a_word_hit(self):
        response = {'candidates': [dict(rank=1, text='bookxyz', segments=[
            dict(kind='exact', surface='book'), dict(kind='literal', surface='xyz')])]}
        self.assertIsNone(harness.retrieved_rank(response, 'bookxyz'))
        response = {'candidates': [dict(rank=2, text='credit card', segments=[
            dict(kind='exact', surface='credit'), dict(kind='literal', surface=' '),
            dict(kind='exact', surface='card')])]}
        self.assertEqual(2, harness.retrieved_rank(response, 'credit card'))


class VocabularySourcesTest(unittest.TestCase):
    def test_download_checks_byte_limit_and_checksum_before_publishing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'manifest.json').write_text(json.dumps({'sources': {'words.txt': dict(
                url='https://example.org/pinned', bytes=3, sha256=hashlib.sha256(b'abc').hexdigest())}}))
            esdb = root / 'esdb'
            esdb.mkdir()
            for name, payload in [('oversized', b'abcd'), ('changed', b'xyz')]:
                with self.subTest(name=name), patch.object(sources, 'SUPPLEMENT', root), \
                        patch.object(sources.urllib.request, 'urlopen', return_value=io.BytesIO(payload)):
                    with self.assertRaises(ValueError):
                        sources.fetch_sources(root / name, esdb)
                    self.assertFalse((root / name / 'words.txt').exists())

    def test_missing_headword_precedes_a_common_lemmas_possessive_and_existing_words_are_omitted(self):
        from collections import defaultdict
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ['ngsl.csv', 'bsl.csv']:
                (root / name).write_text('bank\n')
            (root / 'cmudict.dict').write_text('fixturehead F IH K S\n')
            for corpus in ['ewt', 'gum']:
                (root / (corpus + '-train.conllu')).write_text('')
            with sqlite3.connect(root / 'esdb.db') as connection:
                connection.executescript('''
                    create table entries(word_id integer,word text,lemma text,lemma_id integer,group_id integer,
                                         pos text,base_pos text,pos_class text,usage_note text);
                    create table scowl_(word_id integer,size integer,variant_level integer,group_rank text,
                                        entry_rank text,usage_note text,tag text);
                ''')
                connection.executemany('insert into entries values(?,?,?,?,?,?,?,?,?)', [
                    (1, "bank's", 'bank', 1, 1, 'np', 'n', '', ''),
                    (2, 'fixturehead', 'fixturehead', 2, 2, 'n0', 'n', '', ''),
                    (3, 'already', 'already', 3, 3, 'n0', 'n', '', '')])
                connection.executemany('insert into scowl_ values(?,?,?,?,?,?,?)',
                    [(1, 35, 1, '', '', '', ''), (2, 50, 1, '', '', '', ''), (3, 35, 1, '', '', '', '')])
            wn = defaultdict(list, {word: [(word, 'noun', '00000001')] for word in ['bank', 'fixturehead', 'already']})
            pins = {'esdb': {'databaseSha256': '0' * 64}, 'wordnet.tar.gz': {'sha256': '1' * 64}}
            with patch.object(sources, 'source_files', return_value=pins), patch.object(sources, 'wordnet', return_value=wn):
                result, _ = sources.collect(root, root, {'noun', 'noun_possessive_singular', 'domain_daily', 'domain_business'}, {'already'}, set())
            self.assertEqual(['fixturehead', "bank's"], [row['surface'] for row in result])
            (root / 'document.txt').write_text('fixturehead')
            (root / 'notice.txt').write_text('Synthetic fixture notice')
            entry = candidate()['entries'][0] | {'surface': 'fixture', 'lemma': 'fixture'}
            harness.dump(root / 'references.json', {'documents': [dict(file='document.txt', url=entry['evidence'],
                sha256=harness.replay.sha(root / 'document.txt'), entries=[entry], notices=[dict(file='notice.txt',
                name='TEST.txt', sha256=harness.replay.sha(root / 'notice.txt'))])]})
            with patch.object(sources, 'source_files', return_value=pins), patch.object(sources, 'wordnet', return_value=wn):
                with self.assertRaisesRegex(ValueError, 'literal attestation'):
                    sources.collect(root, root, {'noun', 'domain_daily'}, set(), set(), root / 'references.json')

    def test_training_extraction_uses_observed_forms_and_rejects_typos_and_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'train.conllu'
            path.write_text('# sent_id = email-fixture\n1\tbooked\tbook\tVERB\t_\t_\t0\troot\t_\t_\n'
                '2\tLondon\tLondon\tPROPN\t_\t_\t1\tobj\t_\t_\n'
                '3\tbokked\tbook\tVERB\t_\tTypo=Yes\t1\tobj\t_\t_\n')
            self.assertEqual({'business': {'booked': 1}}, dict(sources.corpus_words(path, 'ewt')))

    def test_source_hash_changes_are_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'ngsl.csv').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'source changed'):
                sources.source_files(root, root)

    def test_only_supported_complete_spellings_are_accepted(self):
        for spelling in ['eSIM', 'carry-on', "y'all", 'two-factor authentication']:
            self.assertTrue(sources.valid_surface(spelling))
        for spelling in [' incomplete', 'two  spaces', 'a@b', '<command>', 'a' * 65]:
            self.assertFalse(sources.valid_surface(spelling))


if __name__ == '__main__':
    unittest.main()
