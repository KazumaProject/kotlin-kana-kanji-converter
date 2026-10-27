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


    def model_entry(self, action='reclassify'):
        baseline = ['い', '乙', 'person,place', 'manual', 'classified']
        # Use the actual frozen category order as the baseline.
        with gzip.open(self.root / reviews.DIRECTORY / 'distribution-decisions.tsv.gz', 'rt') as stream:
            baseline = next(row for row in (line.rstrip('\n').split('\t') for line in stream)
                            if row[:2] == ['い', '乙'])
        categories = ['term'] if action == 'reclassify' else []
        return dict(action=action, reading='い', surface='乙', candidate_key=d.key('い', '乙'),
                    baseline=baseline, reason='IME候補としてのモデル判断', categories=categories,
                    evidence=dict(kind='model_review', reading='い', surface='乙', categories=categories,
                                  model='gpt-5.6-luna', reasoning_effort='max',
                                  target_revision='8ec94757d48d58ac6a5ca2c3baccfcbb48d45003',
                                  response_sha256='a' * 64, reference='PR128 batch response SHA-256'))

    def write_model_entry(self, entry):
        path = self.root / reviews.DIRECTORY / 'reviews/002-model.jsonl'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(entry) + '\n')

    def test_model_reclassification_preserves_variants_and_unrelated_pairs(self):
        source, _ = d.SOURCES['person']
        with (self.root / source).open('a') as stream:
            stream.write('い\t1\t1\t250\t乙\n')
        with contextlib.redirect_stdout(io.StringIO()):
            d.freeze(self.root, self.accepted, self.dispositions, self.database, self.manual, self.taxonomy)
        entry = self.model_entry()
        self.write_model_entry(entry)
        with gzip.open(self.root / reviews.DIRECTORY / 'distribution-candidates.tsv.gz', 'rt') as stream:
            before = {tuple(line.rstrip('\n').split('\t')) for line in stream}
        with contextlib.redirect_stdout(io.StringIO()):
            reviews.apply_saved(self.root, commit=True)
            frozen = (self.root / reviews.DIRECTORY / 'distribution-candidates.tsv.gz').read_bytes()
            reviews.apply_saved(self.root, commit=True)
            self.assertEqual(frozen, (self.root / reviews.DIRECTORY / 'distribution-candidates.tsv.gz').read_bytes())
            d.freeze(self.root, self.accepted, self.dispositions, self.database, self.manual, self.taxonomy)
            d.verify(self.root)
        with gzip.open(self.root / reviews.DIRECTORY / 'distribution-candidates.tsv.gz', 'rt') as stream:
            after = {tuple(line.rstrip('\n').split('\t')) for line in stream}
        self.assertEqual({r for r in after if r[1] == 'い'},
                         {('term', 'い', '1', '1', '200', '乙'), ('term', 'い', '1', '1', '250', '乙')})
        self.assertEqual({r for r in before if r[1] != 'い'}, {r for r in after if r[1] != 'い'})
        with gzip.open(self.root / reviews.DIRECTORY / 'distribution-decisions.tsv.gz', 'rt') as stream:
            self.assertIn('い\t乙\tterm\tmanual\tclassified\n', list(stream))

    def test_model_exclusion_removes_all_memberships(self):
        self.write_model_entry(self.model_entry('exclude'))
        with contextlib.redirect_stdout(io.StringIO()):
            reviews.apply_saved(self.root, commit=True)
            d.verify(self.root)
        with gzip.open(self.root / reviews.DIRECTORY / 'distribution-candidates.tsv.gz', 'rt') as stream:
            self.assertFalse(any(line.split('\t')[1] == 'い' for line in stream))

    def test_model_review_rejects_bad_provenance_and_new_or_excluded_pairs(self):
        for field, value in [('model', 'other'), ('reasoning_effort', 'high'),
                             ('response_sha256', 'invalid'), ('target_revision', 'wrong')]:
            with self.subTest(field=field):
                entry = self.model_entry()
                entry['evidence'][field] = value
                self.write_model_entry(entry)
                with self.assertRaisesRegex(ValueError, 'Invalid model review provenance'):
                    reviews.load(self.root)
        for action in ['add', 'keep', 'hold']:
            with self.subTest(action=action):
                entry = self.model_entry()
                entry['action'] = action
                self.write_model_entry(entry)
                with self.assertRaisesRegex(ValueError, 'Model reviews only'):
                    reviews.load(self.root)
        entry = self.model_entry()
        entry['baseline'][4] = 'excluded'
        self.write_model_entry(entry)
        with self.assertRaisesRegex(ValueError, 'Model reviews only'):
            reviews.load(self.root)


    def test_model_exclusion_retains_verified_baseline_without_claiming_verification(self):
        entry = self.model_entry('exclude')
        with gzip.open(self.root / reviews.DIRECTORY / 'distribution-decisions.tsv.gz', 'rt') as stream:
            baseline = next(row for row in (line.rstrip('\n').split('\t') for line in stream)
                            if row[:2] == ['あ', '甲'])
        self.assertEqual(baseline[3], 'verified')
        entry.update(reading='あ', surface='甲', candidate_key=d.key('あ', '甲'), baseline=baseline)
        entry['evidence'].update(reading='あ', surface='甲')
        self.write_model_entry(entry)
        with contextlib.redirect_stdout(io.StringIO()):
            reviews.apply_saved(self.root, commit=True)
            d.verify(self.root)
        saved = reviews.load(self.root)
        self.assertEqual(saved[('あ', '甲')]['baseline'], baseline)
        with gzip.open(self.root / reviews.DIRECTORY / 'distribution-decisions.tsv.gz', 'rt') as stream:
            self.assertIn('あ\t甲\tperson\tmanual\texcluded\n', list(stream))

    def test_model_review_cannot_add_a_new_record(self):
        entry = self.model_entry()
        entry.update(baseline=None, added_record=dict(left_id=1, right_id=1, cost=8400))
        self.write_model_entry(entry)
        with self.assertRaisesRegex(ValueError, 'Model reviews only'):
            reviews.load(self.root)

    def test_mixed_script_source_ruby_requires_explicit_full_reading_components(self):
        entry = {
            'action': 'add', 'reading': 'しふとひょう', 'surface': 'シフト表',
            'evidence': {
                'sourceName': 'MHLW Multilingual Glossary for Employment Management',
                'sourceTermMarkup': 'シフト表（ひょう）',
                'readingComponents': [
                    {'kind': 'kana', 'surface': 'シフト', 'reading': 'しふと'},
                    {'kind': 'furigana', 'surface': '表', 'reading': 'ひょう'},
                ],
            },
        }
        reviews.validate_reading_components(entry, 'review.jsonl', 1)

        entry['evidence'].pop('readingComponents')
        with self.assertRaisesRegex(ValueError, 'explicit reading components or a hold'):
            reviews.validate_reading_components(entry, 'review.jsonl', 1)

        entry['action'] = 'hold'
        reviews.validate_reading_components(entry, 'review.jsonl', 1)

    def test_reading_components_must_compose_exact_pair(self):
        entry = {
            'action': 'add', 'reading': 'しふとひょう', 'surface': 'シフト表',
            'evidence': {'readingComponents': [
                {'kind': 'kana', 'surface': 'シフト', 'reading': 'しふと'},
                {'kind': 'furigana', 'surface': '表', 'reading': 'ひょうじ'},
            ]},
        }
        with self.assertRaisesRegex(ValueError, 'do not compose'):
            reviews.validate_reading_components(entry, 'review.jsonl', 1)
