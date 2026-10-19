"""Adversarial distribution tests using entirely synthetic person records.

Evidence URLs are fixture assertions; these tests verify bookkeeping and policy
invariants, not whether an external page proves a real person's history.
"""
import contextlib
import copy
import gzip
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest import mock

import classified_distribution as d
import person_subclassification as p
import test_classified_distribution as base_fixture


class PersonSubclassificationTest(unittest.TestCase):
    def setUp(self):
        fixture = base_fixture.DistributionTest('test_freeze_is_deterministic')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.directory = self.root / 'src/main/classification'
        self.directory.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(__file__).resolve().parents[1] /
                        'src/main/classification/person-taxonomy.json',
                        self.directory / 'person-taxonomy.json')
        # The same pair has two POS/cost records, and another pair belongs to
        # both person and place. Neither may be lost or reintroduced by export.
        with (self.root / 'src/main/bin/names.txt').open('a') as stream:
            stream.write('あ\t1\t1\t-123\t甲\n')
        with contextlib.redirect_stdout(io.StringIO()):
            fixture.freeze()
        self.workspace = self.root / 'work'
        self.output = self.root / 'output'
        self.snapshot = p.prepare(self.root, self.workspace, batch_size=1)
        self.items = p.evaluate(self.root, self.workspace)['items']
        self.by_surface = {item['surface']: item for item in self.items}
        self.proposals = self.root / 'proposals.jsonl'
        self.reviews = self.root / 'reviews.jsonl'

    def write_jsonl(self, path, records):
        path.write_text(''.join(json.dumps(record, ensure_ascii=False) + '\n'
                                for record in records), encoding='utf-8')
        return path

    def evidence(self):
        return [{'url': 'https://example.org/synthetic/credit',
                 'summary': 'Synthetic fixture: identity, kana and activity confirmed.',
                 'checked_on': '2026-10-19'}]

    def proposal(self, surface='甲', **updates):
        item = self.by_surface[surface]
        record = dict(schema_version=1, snapshot_id=self.snapshot['snapshot_id'],
                      batch_id=next(batch['batch_id'] for batch in self.snapshot['batches']
                                    if item['item_id'] in batch['item_ids']), item_id=item['item_id'],
                      classifier_id='classifier-a', run_id='classification-run-1',
                      checked_on='2026-10-19', identity_status='identified',
                      entity_ids=['https://example.org/synthetic/entity/' + surface],
                      public_aliases=[], categories=['actor'], primary_category='actor',
                      tags=[], adult_appearance_status='reviewed_no_evidence',
                      identity_evidence=self.evidence(), occupation_evidence=self.evidence(),
                      reading_evidence=self.evidence(), adult_evidence=self.evidence(),
                      search_log=[],
                      reason='Synthetic reviewed person fixture')
        record.update(updates)
        if 'search_log' not in updates:
            subjects = [dict(reading=item['reading'], surface=item['surface'])]
            subjects += [dict(reading=a['reading'], surface=a['surface'])
                         for a in record['public_aliases']]
            record['search_log'] = [dict(
                subject=subject, query=subject['surface'] + ' 成人向け 出演 ' + scope,
                scope=scope, checked_on='2026-10-19',
                urls=['https://example.org/synthetic/credit'])
                for subject in subjects for scope in ['video', 'game', 'audio']]
        return record

    def review(self, proposal, **updates):
        record = dict(schema_version=1, snapshot_id=proposal['snapshot_id'],
                      batch_id=proposal['batch_id'], item_id=proposal['item_id'],
                      proposal_sha256=p.proposal_sha(proposal), reviewer_id='reviewer-b',
                      run_id='review-run-2', checked_on='2026-10-19', decision='approve',
                      evidence=self.evidence(), reason='Independent fixture review')
        record.update(updates)
        return record

    def evaluate(self, proposals=(), reviews=None):
        if reviews is None:
            reviews = [self.review(record) for record in proposals]
        self.write_jsonl(self.proposals, proposals)
        self.write_jsonl(self.reviews, reviews)
        return p.evaluate(self.root, self.workspace,
                          proposal_paths=[self.proposals], review_paths=[self.reviews])

    def status(self, result, surface='甲'):
        item_id = self.by_surface[surface]['item_id']
        return next(row['distribution_status'] for row in result['decisions']
                    if row['item_id'] == item_id)

    def assert_closed(self, proposal, review=None):
        """Malformed evidence may reject the whole batch or hold the item."""
        try:
            result = self.evaluate([proposal], [review or self.review(proposal)])
        except (ValueError, TypeError):
            return
        self.assertNotEqual(self.status(result), 'general')

    def test_no_submissions_holds_the_full_universe(self):
        result = p.evaluate(self.root, self.workspace)
        self.assertEqual(result['item_count'], 2)
        self.assertEqual(result['counts'].get('general', 0), 0)
        self.assertEqual(result['counts'].get('adult_separate', 0), 0)
        self.assertEqual(result['counts']['hold'], 2)

    def test_approved_independent_review_admits_person(self):
        result = self.evaluate([self.proposal()])
        self.assertEqual(self.status(result), 'general')
        self.assertEqual(self.status(result, '乙'), 'hold')

    def test_missing_rejected_or_hold_review_never_admits(self):
        proposal = self.proposal()
        for decision in [None, 'reject', 'hold']:
            with self.subTest(decision=decision):
                reviews = [] if decision is None else [self.review(proposal, decision=decision)]
                self.assertEqual(self.status(self.evaluate([proposal], reviews)), 'hold')

    def test_self_review_and_same_run_fail_closed(self):
        proposal = self.proposal()
        for updates in [dict(reviewer_id=proposal['classifier_id']),
                        dict(run_id=proposal['run_id'])]:
            with self.subTest(updates=updates):
                self.assert_closed(proposal, self.review(proposal, **updates))

    def test_proposal_mutation_invalidates_existing_review(self):
        proposal = self.proposal()
        review = self.review(proposal)
        proposal['reason'] += ' changed after review'
        self.assert_closed(proposal, review)

    def test_missing_or_partial_evidence_never_admits(self):
        for field in ['identity_evidence', 'occupation_evidence', 'reading_evidence',
                      'adult_evidence', 'search_log']:
            proposal = self.proposal(**{field: []})
            with self.subTest(field=field):
                self.assert_closed(proposal)
        proposal = self.proposal()
        proposal['search_log'] = proposal['search_log'][:2]
        self.assert_closed(proposal)

    def test_bad_schema_and_provenance_fail_closed(self):
        cases = [('schema_version', 2), ('snapshot_id', 'stale'),
                 ('batch_id', 'not-assigned'), ('categories', ['invalid_category']),
                 ('primary_category', 'musician'), ('checked_on', 'not-a-date'),
                 ('entity_ids', ['file:///private/identity']),
                 ('identity_status', 'unresolved'),
                 ('adult_appearance_status', 'not_checked'),
                 ('adult_appearance_status', 'unresolved')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.assert_closed(self.proposal(**{field: value}))
        proposal = self.proposal()
        del proposal['reading_evidence']
        self.assert_closed(proposal)

    def test_review_evidence_and_snapshot_are_required(self):
        proposal = self.proposal()
        for updates in [dict(evidence=[]), dict(snapshot_id='stale'),
                        dict(proposal_sha256='0' * 64), dict(checked_on='invalid')]:
            with self.subTest(updates=updates):
                self.assert_closed(proposal, self.review(proposal, **updates))

    def test_negative_search_cannot_override_confirmed_adult_entity(self):
        adult = self.proposal(adult_appearance_status='confirmed',
                              categories=['actor', 'adult_performer'],
                              primary_category='adult_performer')
        other = self.proposal('乙', entity_ids=adult['entity_ids'])
        result = self.evaluate([adult, other])
        self.assertEqual(self.status(result), 'adult_separate')
        self.assertNotEqual(self.status(result, '乙'), 'general')

    def test_public_alias_blocks_same_pair_even_with_different_entity_id(self):
        adult = self.proposal(adult_appearance_status='confirmed',
                              categories=['adult_performer'], primary_category='adult_performer',
                              public_aliases=[dict(reading='い', surface='乙',
                                  entity_id='https://example.org/synthetic/entity/甲',
                                  evidence=self.evidence())])
        other = self.proposal('乙')
        result = self.evaluate([adult, other])
        self.assertNotEqual(self.status(result, '乙'), 'general')

    def test_name_components_need_independent_evidence(self):
        proposal = self.proposal(identity_status='name_component', entity_ids=[],
                                 categories=['surname'], primary_category='surname',
                                 adult_appearance_status='not_applicable', search_log=[])
        self.assertEqual(self.status(self.evaluate([proposal])), 'general')
        self.assert_closed(self.proposal(adult_appearance_status='not_applicable'))
        proposal['identity_evidence'] = []
        self.assert_closed(proposal)

    def test_duplicate_conflicting_submissions_do_not_admit(self):
        proposal = self.proposal()
        conflicting = copy.deepcopy(proposal)
        conflicting['adult_appearance_status'] = 'unresolved'
        try:
            result = self.evaluate([proposal, conflicting])
        except ValueError:
            return
        self.assertNotEqual(self.status(result), 'general')

    def test_changed_taxonomy_and_source_invalidate_workspace(self):
        paths = [self.directory / 'person-taxonomy.json',
                 self.directory / 'distribution-candidates.tsv.gz']
        for path in paths:
            with self.subTest(path=path.name):
                original = path.read_bytes()
                try:
                    path.write_bytes(original + b'\n')
                    with self.assertRaises(ValueError):
                        p.evaluate(self.root, self.workspace)
                finally:
                    path.write_bytes(original)


    def test_selection_only_limits_batches_not_universe(self):
        selected = self.write_jsonl(self.root / 'selection.jsonl',
                                   [dict(reading='あ', surface='甲')])
        workspace = self.root / 'selected-work'
        snapshot = p.prepare(self.root, workspace, selection=selected)
        result = p.evaluate(self.root, workspace)
        self.assertEqual(snapshot['selected_count'], 1)
        self.assertEqual(snapshot['item_count'], 2)
        self.assertEqual(len(snapshot['batches'][0]['item_ids']), 1)
        self.assertEqual(result['counts']['hold'], 2)

    def test_partial_batch_is_rejected(self):
        self.workspace = self.root / 'larger-batch-work'
        self.snapshot = p.prepare(self.root, self.workspace, batch_size=2)
        with self.assertRaises(ValueError):
            self.evaluate([self.proposal()])

    def test_prepared_artifact_tampering_is_rejected(self):
        paths = [self.workspace / 'selection.json', self.workspace / 'items.jsonl',
                 self.workspace / 'taxonomy.json', self.workspace / 'submission-schema.json',
                 self.workspace / self.snapshot['batches'][0]['path'],
                 (self.workspace / self.snapshot['batches'][0]['path']).with_suffix('.md')]
        for path in paths:
            with self.subTest(path=path.name):
                original = path.read_bytes()
                try:
                    if path.name == 'selection.json':
                        path.write_text('[{"reading":"あ","surface":"甲"}]')
                    else:
                        path.write_bytes(original + b'\n')
                    with self.assertRaises(ValueError):
                        p.evaluate(self.root, self.workspace)
                finally:
                    path.write_bytes(original)

    def read_tsv(self, path):
        return {tuple(line.split('\t')) for line in path.read_text().splitlines()}

    def test_export_partitions_records_and_filters_all_category_memberships(self):
        general = self.proposal()
        adult = self.proposal('乙', adult_appearance_status='confirmed',
                              categories=['adult_performer', 'actor'],
                              primary_category='adult_performer')
        self.evaluate([general, adult])
        source = self.directory / 'distribution-candidates.tsv.gz'
        before = source.read_bytes()
        p.export(self.root, self.workspace, self.output,
                 proposal_paths=[self.proposals], review_paths=[self.reviews])
        self.assertEqual(before, source.read_bytes())
        original = {tuple(line.split('\t'))
                    for line in gzip.decompress(before).decode().splitlines()}
        expected_person = {row for row in original if row[0] == 'person'}
        partitions = [self.read_tsv(self.output / (status + '.tsv'))
                      for status in ['general', 'adult_separate', 'hold']]
        self.assertEqual(set.union(*partitions), expected_person)
        for i, left in enumerate(partitions):
            for right in partitions[i + 1:]:
                self.assertFalse(left & right)
        self.assertEqual(len(partitions[0]), 2)  # Both cost variants preserved.
        self.assertEqual({row[4] for row in partitions[0]}, {'100', '-123'})
        filtered = self.read_tsv(self.output / 'general-candidates.tsv')
        self.assertFalse(any(row[1] == 'い' and row[5] == '乙' for row in filtered))
        self.assertEqual(filtered, {row for row in original
                                    if (row[1], row[5]) != ('い', '乙')})

    def test_export_holds_unreviewed_person_across_all_categories(self):
        p.export(self.root, self.workspace, self.output)
        self.assertEqual(self.read_tsv(self.output / 'general.tsv'), set())
        self.assertEqual(self.read_tsv(self.output / 'adult_separate.tsv'), set())
        filtered = self.read_tsv(self.output / 'general-candidates.tsv')
        self.assertFalse(any(row[5] in ['甲', '乙'] for row in filtered))
        self.assertEqual(len(self.read_tsv(self.output / 'hold.tsv')), 3)

    def test_output_tampering_cannot_be_hidden_by_updating_manifest_hash(self):
        self.evaluate([self.proposal()])
        p.export(self.root, self.workspace, self.output,
                 proposal_paths=[self.proposals], review_paths=[self.reviews])
        p.verify_output(self.root, self.workspace, self.output)
        general = self.output / 'general.tsv'
        with general.open('a') as stream:
            stream.write('person\tい\t1\t1\t200\t乙\n')
        manifest_path = self.output / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files']['general.tsv'] = p.sha(general)
        manifest['record_counts']['general.tsv'] += 1
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            p.verify_output(self.root, self.workspace, self.output)

    def test_export_copies_pinned_provenance_and_detects_its_mutation(self):
        self.evaluate([self.proposal()])
        p.export(self.root, self.workspace, self.output,
                 proposal_paths=[self.proposals], review_paths=[self.reviews])
        self.proposals.unlink()
        self.reviews.unlink()
        # Verification relies on exported provenance, not temporary inputs.
        p.verify_output(self.root, self.workspace, self.output)
        manifest = json.loads((self.output / 'manifest.json').read_text())
        copied_review = self.output / manifest['provenance']['reviews'][0]['path']
        copied_review.write_text('{}\n')
        with self.assertRaises(ValueError):
            p.verify_output(self.root, self.workspace, self.output)

    def test_adult_public_alias_only_in_nonperson_category_is_filtered(self):
        adult = self.proposal(adult_appearance_status='confirmed',
                              categories=['adult_performer'], primary_category='adult_performer',
                              public_aliases=[dict(reading='う', surface='丙',
                                  entity_id='https://example.org/synthetic/entity/甲',
                                  evidence=self.evidence())])
        self.evaluate([adult])
        p.export(self.root, self.workspace, self.output,
                 proposal_paths=[self.proposals], review_paths=[self.reviews])
        filtered = self.read_tsv(self.output / 'general-candidates.tsv')
        self.assertFalse(any(row[1] == 'う' and row[5] == '丙' for row in filtered))
        p.verify_output(self.root, self.workspace, self.output)

    def test_adult_alias_contamination_closes_over_transitive_entity_graph(self):
        # Add a third synthetic person to exercise X -> B/Y -> C/Y.
        source = self.directory / 'distribution-candidates.tsv.gz'
        with gzip.open(source, 'rt') as stream:
            rows = [tuple(line.rstrip('\n').split('\t')) for line in stream]
        rows.append(('person', 'う', '1', '1', '300', '丙'))
        d.write_gzip(source, sorted(rows))
        self.workspace = self.root / 'chain-work'
        self.snapshot = p.prepare(self.root, self.workspace, batch_size=1)
        self.items = p.evaluate(self.root, self.workspace)['items']
        self.by_surface = {item['surface']: item for item in self.items}
        adult = self.proposal(adult_appearance_status='confirmed',
                              categories=['adult_performer'], primary_category='adult_performer',
                              public_aliases=[dict(reading='い', surface='乙',
                                  entity_id='https://example.org/synthetic/entity/甲',
                                  evidence=self.evidence())])
        bridge = self.proposal('乙', public_aliases=[dict(reading='う', surface='丙',
                                   entity_id='https://example.org/synthetic/entity/乙',
                                   evidence=self.evidence())])
        final = self.proposal('丙', entity_ids=bridge['entity_ids'])
        result = self.evaluate([adult, bridge, final])
        self.assertEqual(self.status(result), 'adult_separate')
        self.assertEqual(self.status(result, '乙'), 'hold')
        self.assertEqual(self.status(result, '丙'), 'hold')

    def test_cli_repeated_proposal_and_review_options_accumulate_all_files(self):
        first, second = self.proposal(), self.proposal('乙')
        first_path = self.write_jsonl(self.proposals, [first])
        second_path = self.write_jsonl(self.root / 'second-proposals.jsonl', [second])
        first_review = self.write_jsonl(self.reviews, [self.review(first)])
        second_review = self.write_jsonl(self.root / 'second-reviews.jsonl', [self.review(second)])
        command = [sys.executable, str(Path(p.__file__).resolve()), 'status',
                   '--root', str(self.root), '--workspace', str(self.workspace),
                   '--proposals', str(first_path), '--proposals', str(second_path),
                   '--reviews', str(first_review), '--reviews', str(second_review)]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result['proposal_count'], 2)
        self.assertEqual(result['review_count'], 2)
        self.assertEqual(result['counts']['general'], 2)

    def test_negative_search_subject_and_query_must_identify_current_person(self):
        for corruption in ['no_subject', 'unrelated_subject', 'unrelated_query']:
            with self.subTest(corruption=corruption):
                proposal = self.proposal()
                for entry in proposal['search_log']:
                    if corruption == 'no_subject':
                        del entry['subject']
                    elif corruption == 'unrelated_subject':
                        entry['subject'] = dict(reading='むかんけい', surface='無関係')
                    else:
                        entry['query'] = 'unrelated anonymous performer credit'
                self.assert_closed(proposal)

    def test_negative_search_must_cover_every_public_alias_and_scope(self):
        alias = dict(reading='べつめい', surface='別名',
                     entity_id='https://example.org/synthetic/entity/甲',
                     evidence=self.evidence())
        proposal = self.proposal(public_aliases=[alias])
        self.assertEqual(self.status(self.evaluate([proposal])), 'general')
        proposal['search_log'] = [entry for entry in proposal['search_log']
                                  if not (entry['subject']['surface'] == '別名'
                                          and entry['scope'] == 'audio')]
        self.assert_closed(proposal)

    def test_changed_validator_implementation_invalidates_prior_workspace(self):
        original_sha = p.sha
        implementation = Path(p.__file__).resolve()

        def changed_sha(path):
            if Path(path).resolve() == implementation:
                return '0' * 64
            return original_sha(path)

        # Simulate a changed validator file without editing the shared source.
        with mock.patch.object(p, 'sha', side_effect=changed_sha):
            with self.assertRaisesRegex(ValueError, 'implementation'):
                p.evaluate(self.root, self.workspace)

if __name__ == '__main__':
    unittest.main()
