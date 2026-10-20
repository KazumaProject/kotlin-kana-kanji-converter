"""Synthetic contract tests: these do not measure LLM semantic accuracy."""
import argparse
import contextlib
import copy
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest

from term_semantic import pipeline as p
from term_semantic import runtime


class SemanticPipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='semantic-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.run = self.base / 'run'
        self.source = self.base / 'source.tsv.gz'
        self.rows = [('いぬ', '1', '2', '100', '犬'),
                     ('いぬ', '3', '4', '-20', '犬'),
                     ('さいぼうまく', '1', '1', '200', '細胞膜'),
                     ('えっくす', '1', '1', '10', 'X')]
        self.source.write_bytes(gzip.compress((''.join('term\t'+'\t'.join(r)+'\n' for r in self.rows)
                                              +'person\tたろう\t1\t1\t100\t太郎\n').encode(), mtime=0))
        repo = Path(__file__).resolve().parents[1]
        self.taxpath = repo/'src/main/classification/term-semantic/taxonomy.json'
        self.tax = json.loads(self.taxpath.read_text())
        self.invoke(p.prepare, source=str(self.source), taxonomy=str(self.taxpath),
                    prompts=str(self.taxpath.parent/'prompts'), seed='test-v1',
                    pilot_size=3, batch_size=3, full=False,
                    classifier_model='gpt-6-luna', adjudicator_model='gpt-6.1-sol')
        self.pairs = json.loads((self.run/'pairs.json').read_text())

    def invoke(self, function, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            function(argparse.Namespace(run=str(self.run), **kwargs))
        return json.loads(output.getvalue().strip().splitlines()[-1])

    def result(self, pair):
        # Explicit synthetic fixture labels, not a production classifier.
        fixture = {'犬': ('general', 'term_animals'),
                   '細胞膜': ('technical', 'term_biology'),
                   'X': ('uncertain', None)}
        usage, domain = fixture[pair['surface']]
        unknown = domain is None
        return dict(pair, usage_class=usage, primary_domain=domain,
                    alternative_domains=[], tags=[], ambiguous=unknown,
                    needs_review=unknown, short_reason='Synthetic test fixture.',
                    final_category=domain or 'term_unknown', uncertain_tags=[],
                    ambiguity_types=['unknown_meaning'] if unknown else [],
                    context_required=unknown)

    def claim(self, stage):
        return self.invoke(p.next_job, stage=stage, lease_seconds=1800)

    def ingest(self, job, results=None, evidence_change=None):
        payload = json.loads(Path(job['input']).read_text())
        if results is None:
            results = [self.result(row) for row in payload['items']]
        output = Path(job['output'])
        output.write_text('\n'.join(p.encoded(row) for row in results)+'\n')
        evidence = dict(model=job['model'], agent_id='synthetic-fixture-only',
                        lease_token=job['lease_token'], execution_kind='test-fixture')
        evidence.update(evidence_change or {})
        path = output.with_name('evidence.json')
        path.write_text(p.encoded(evidence))
        return self.invoke(p.ingest, job=job['job'], output=str(output), evidence=str(path))

    def finish(self):
        for stage in ('A', 'B', 'reviewer', 'adjudicator'):
            while True:
                job = self.claim(stage)
                if job['job'] is None:
                    break
                self.ingest(job)
        self.acknowledge_fixture_anomalies()

    def acknowledge_fixture_anomalies(self):
        evidence = self.base/'synthetic-inspection.json'
        evidence.write_text(p.encoded(dict(model='gpt-6.1-sol', agent_id='synthetic-fixture-only')))
        with p.connect(self.run) as db:
            jobs = [row['job_id'] for row in db.execute("SELECT job_id FROM anomalies WHERE status!='inspected_by_sol'")]
        for job in jobs:
            self.invoke(p.acknowledge_anomaly, job=job, evidence=str(evidence),
                        note='Synthetic mechanics fixture: one intentionally unknown term, not actual semantic review.')

    def test_source_scope_and_pos_cost_variants(self):
        self.assertEqual(p.records(self.source), [list(r) for r in self.rows])
        self.assertEqual(len(self.pairs), 3)
        self.assertNotEqual(p.stable_id('いぬ', '犬'), p.stable_id('イヌ', '犬'))

    def test_worker_input_is_allowlisted_and_independent(self):
        job = self.claim('A')
        payload = json.loads(Path(job['input']).read_text())
        self.assertNotIn('candidate_results', payload)
        for row in payload['items']:
            self.assertEqual(set(row), {'stable_id', 'reading', 'surface'})

    def test_review_proposals_exclude_authority_metadata_and_duplicate_source_fields(self):
        self.ingest(self.claim('A'))
        self.ingest(self.claim('B'))
        job=self.claim('reviewer')
        payload=json.loads(Path(job['input']).read_text())
        independent=json.loads(Path(job['independent_input']).read_text())
        self.assertNotIn('candidate_results',independent)
        for proposals in payload['candidate_results'].values():
            for proposal in proposals:
                self.assertEqual(set(proposal['result']),p.FIELDS-{'stable_id','reading','surface'})

    def test_rejects_incomplete_duplicate_or_changed_results(self):
        rows = [self.result(pair) for pair in self.pairs.values()]
        mutations = [lambda a: a.pop(), lambda a: a.append(copy.deepcopy(a[0])),
                     lambda a: a[0].update(reading='changed'),
                     lambda a: a[0].update(surface='changed'),
                     lambda a: a[0].pop('final_category'),
                     lambda a: a[0].update(needs_review=1),
                     lambda a: a[0].update(tags=['bad']),
                     lambda a: a[0].update(final_category='../escape'),
                     lambda a: a[0].update(short_reason='a'*161),
                     lambda a: a[0].update(legacy_label='term_general')]
        for mutate in mutations:
            values = copy.deepcopy(rows)
            mutate(values)
            with self.subTest(values=values), self.assertRaises((ValueError, TypeError)):
                p.validate(values, list(self.pairs), self.pairs, self.tax)

    def test_rejects_model_and_lease_mismatch(self):
        job = self.claim('A')
        for evidence in ({'model': 'invented-model'}, {'agent_id': ''}, {'lease_token': 'stale'}):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                self.ingest(job, evidence_change=evidence)

    def test_ingest_is_idempotent_and_cannot_replace_validated_result(self):
        job = self.claim('A')
        self.ingest(job)
        self.ingest(job)
        rows = [self.result(row) for row in json.loads(Path(job['input']).read_text())['items']]
        rows[0]['short_reason'] = 'Changed accepted result.'
        with self.assertRaises(ValueError):
            self.ingest(job, rows)

    def test_expired_job_is_reissued_with_new_token(self):
        job = self.claim('A')
        with p.connect(self.run) as db:
            db.execute('UPDATE jobs SET lease_until=0 WHERE id=?', (job['job'],))
        renewed = self.claim('A')
        self.assertEqual(renewed['job'], job['job'])
        self.assertNotEqual(renewed['lease_token'], job['lease_token'])
        self.assertNotEqual(renewed['output'], job['output'])
        with self.assertRaises(ValueError):
            self.ingest(job)

    def test_unknown_requires_sol_after_reviewer(self):
        self.ingest(self.claim('A'))
        self.ingest(self.claim('B'))
        self.assertNotIn(p.stable_id('えっくす', 'X'), {
            row['id'] for row in p.connect(self.run).execute('SELECT id FROM finals')})
        self.finish()
        db = p.connect(self.run)
        origin = db.execute('SELECT j.pass FROM finals f JOIN jobs j ON j.id=f.origin WHERE f.id=?',
                            (p.stable_id('えっくす', 'X'),)).fetchone()
        self.assertEqual(origin['pass'], 'adjudicator')
        self.invoke(p.verify, complete=True)

    def test_partial_cannot_claim_completion(self):
        self.ingest(self.claim('A'))
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.invoke(p.verify, complete=True)

    def test_source_cost_tampering_is_detected(self):
        path = self.run/'source-records.json'
        rows = json.loads(path.read_text())
        rows[0][3] = '999'
        path.write_text(p.encoded(rows))
        with self.assertRaisesRegex(ValueError, 'snapshot'):
            self.invoke(p.verify, complete=False)

    def test_deterministic_export_preserves_multiset(self):
        import collections
        self.finish()
        a, b = self.base/'a', self.base/'b'
        self.invoke(p.export, output=str(a))
        self.invoke(p.export, output=str(b))
        self.assertEqual({str(f.relative_to(a)): f.read_bytes() for f in a.rglob('*') if f.is_file()},
                         {str(f.relative_to(b)): f.read_bytes() for f in b.rglob('*') if f.is_file()})
        recovered = []
        for path in a.glob('*.tsv.gz'):
            if path.name.startswith('term_tag_'):
                continue
            recovered.extend(tuple(line.rstrip('\n').split('\t')) for line in gzip.open(path, 'rt'))
        self.assertEqual(collections.Counter(recovered), collections.Counter(self.rows))

    def test_prompt_and_taxonomy_changes_are_detected(self):
        for path, error in [(self.run/'prompts/A.md', 'Prompt'), (self.run/'taxonomy.json', 'Taxonomy')]:
            original = path.read_text()
            path.write_text(original+' ' if path.suffix=='.md' else original.replace('"version":1', '"version":2'))
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, error):
                self.invoke(p.verify, complete=False)
            path.write_text(original)

    def test_host_attestation_rejects_root_and_missing_threads(self):
        import sqlite3
        database = self.base/'host.sqlite'
        with contextlib.closing(sqlite3.connect(database)) as db:
            db.execute('CREATE TABLE threads(id TEXT,source TEXT,model TEXT,rollout_path TEXT)')
            db.execute('INSERT INTO threads VALUES(?,?,?,?)', ('root', 'exec', 'gpt-6.1-sol', '/unused'))
            db.execute('INSERT INTO threads VALUES(?,?,?,?)',
                       ('child', p.encoded({'subagent': {'thread_spawn': {
                           'parent_thread_id': 'root', 'agent_path': '/root/fixture'}}}),
                        'gpt-6-luna', '/unused'))
            db.commit()
        for ident in ('root', 'missing'):
            with self.subTest(ident=ident), self.assertRaises(ValueError):
                runtime.thread_record(ident, database)
        self.assertEqual(runtime.thread_record('child', database)['model'], 'gpt-6-luna')

    def test_usage_uses_last_cumulative_value_without_double_counting(self):
        path = self.base/'rollout.jsonl'
        values = [dict(input_tokens=100, output_tokens=10), dict(input_tokens=200, output_tokens=30)]
        path.write_text('\n'.join(p.encoded({'type': 'event_msg', 'payload': {
            'type': 'token_count', 'info': {'total_token_usage': value}}}) for value in values))
        self.assertEqual(runtime.recorded_usage(path), values[-1])

    def test_runtime_requires_formal_independent_exact_model_workers(self):
        prompt = runtime.coordinator_prompt(self.run, 'pilot')
        for expected in ('formal spawn_agent', 'gpt-6-luna', 'gpt-6.1-sol',
                         'fork_turns none', 'Maximum TWO', 'Do NOT promote', 'attest'):
            self.assertIn(expected.lower(), prompt.lower())

    def test_explicit_audit_is_deterministic_and_requires_sol(self):
        self.finish()
        self.invoke(p.audit, size=3)
        original = (self.run/'audit-selection.json').read_bytes()
        self.invoke(p.audit, size=3)
        self.assertEqual(original, (self.run/'audit-selection.json').read_bytes())
        with self.assertRaises(ValueError):
            self.invoke(p.verify, complete=True)
        self.finish()
        self.invoke(p.verify, complete=True)
        with p.connect(self.run) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM finals f JOIN jobs j ON f.origin=j.id WHERE j.pass='adjudicator'").fetchone()[0], 3)

    def test_full_promotion_reuses_pilot_and_is_idempotent(self):
        self.finish()
        with p.connect(self.run) as db:
            old_jobs = db.execute('SELECT count(*) FROM jobs').fetchone()[0]
        self.invoke(p.promote,batch_size=200)
        self.invoke(p.promote)
        with p.connect(self.run) as db:
            self.assertEqual(old_jobs, db.execute('SELECT count(*) FROM jobs').fetchone()[0])
        self.assertTrue(p.config(self.run)['full'])
        self.assertEqual(p.config(self.run)['batch_size'],200)
        self.invoke(p.verify, complete=True)

    def test_export_does_not_overwrite_existing_directory(self):
        self.finish()
        output = self.base/'existing'
        output.mkdir()
        marker = output/'keep.txt'
        marker.write_text('keep')
        with self.assertRaises(ValueError):
            self.invoke(p.export, output=str(output))
        self.assertEqual(marker.read_text(), 'keep')

    def test_tags_and_alternatives_compare_as_sets(self):
        row = self.result(next(iter(self.pairs.values())))
        row.update(tags=['term_tag_idioms', 'term_tag_slang'],
                   alternative_domains=['term_animals', 'term_plants'])
        other = copy.deepcopy(row)
        other['tags'].reverse()
        other['alternative_domains'].reverse()
        self.assertEqual(p.semantic(row), p.semantic(other))
        other['ambiguity_types'] = ['polysemy']
        self.assertNotEqual(p.semantic(row), p.semantic(other))

    def test_unknown_cannot_be_hidden_as_general(self):
        row = self.result(next(iter(self.pairs.values())))
        row.update(final_category='term_unknown', primary_domain='term_general', needs_review=False)
        with self.assertRaises(ValueError):
            p.validate([row], [row['stable_id']], self.pairs, self.tax)

    def test_runtime_outputs_cannot_be_written_in_repository(self):
        with self.assertRaises(ValueError):
            p.external_path(Path(__file__).resolve().parent/'runtime-output')

    def test_report_separates_agreement_from_accuracy_and_lists_unknowns(self):
        self.finish()
        result = self.invoke(p.report)
        self.assertFalse(result['ai_audit_is_ground_truth'])
        self.assertEqual(result['agreement_rates']['compared_pairs'], 3)
        self.assertEqual(result['human_review_count'], 1)
        review = [json.loads(line) for line in (self.run/'human-review.jsonl').read_text().splitlines()]
        self.assertEqual([row['surface'] for row in review], ['X'])
        self.assertEqual(review[0]['classification_pass'], 'adjudicator')

    def test_reviewer_cannot_unilaterally_overturn_unanimous_core_labels(self):
        pair = next(row for row in self.pairs.values() if row['surface']=='犬')
        a = self.result(pair)
        reviewed = dict(a, usage_class='technical')
        self.assertTrue(p.reviewer_requires_sol(a, copy.deepcopy(a), reviewed))
        self.assertFalse(p.reviewer_requires_sol(a, copy.deepcopy(a), dict(a)))
        b = dict(a, usage_class='technical')
        self.assertFalse(p.reviewer_requires_sol(a, b, dict(a)))

    def test_literal_quotes_are_preserved_in_source_records(self):
        source=self.base/'literal.tsv'
        source.write_text('term\tりてらる\t1\t2\t-3\t"literal"\n')
        self.assertEqual(p.records(source), [['りてらる','1','2','-3','"literal"']])

    def test_spawn_attestation_requires_actual_independent_context(self):
        path=self.base/'parent-rollout.jsonl'
        for fork in ('all','none'):
            path.write_text(p.encoded({'type':'response_item','payload':{
                'type':'function_call','name':'collaboration.spawn_agent',
                'arguments':p.encoded({'task_name':'worker','model':'gpt-6-luna','fork_turns':fork})}})+'\n')
            if fork=='all':
                with self.assertRaises(ValueError):
                    runtime.independent_spawn_settings(path,'/root/worker')
            else:
                self.assertEqual(runtime.independent_spawn_settings(path,'/root/worker')['fork_turns'],'none')
        with self.assertRaises(ValueError):
            runtime.independent_spawn_settings(path,'/root/another-worker')

    def test_expanded_review_reuses_existing_judgments_and_requires_all_words(self):
        self.finish()
        with p.connect(self.run) as db:
            ab_before=[tuple(row) for row in db.execute("SELECT id,result FROM jobs WHERE pass IN ('A','B') ORDER BY id")]
        self.invoke(p.review_all)
        self.invoke(p.review_all)
        self.finish()
        with p.connect(self.run) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM result_items WHERE pass='reviewer'").fetchone()[0],3)
            self.assertEqual(ab_before,[tuple(row) for row in db.execute("SELECT id,result FROM jobs WHERE pass IN ('A','B') ORDER BY id")])
        self.invoke(p.verify,complete=True)


if __name__ == '__main__':
    unittest.main()
