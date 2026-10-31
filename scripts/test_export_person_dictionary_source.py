import gzip
import json
import shutil
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import export_person_dictionary_source as exporter


class PersonAdditionExportTest(unittest.TestCase):
    def test_explicit_category_and_sport_additions_are_routed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resources = root / 'src/main/resources'
            classification = root / 'src/main/classification'
            additions_dir = classification / 'person-additions'
            resources.mkdir(parents=True)
            additions_dir.mkdir(parents=True)
            (resources / 'id.def').write_text('1851 名詞,一般,*,*,*,*,*\n', encoding='utf-8')
            (classification / 'person-taxonomy.json').write_text(json.dumps({
                'categories': [
                    {'id': 'comedian', 'standard_enabled': True},
                    {'id': 'sports', 'standard_enabled': True},
                ],
                'sport_subcategories': {'baseball': '野球'},
            }), encoding='utf-8')
            common = dict(left_id=1851, right_id=1851, cost=8400,
                          source_url='https://example.org/profile', checked_on='2026-10-22')
            rows = [
                dict(reading='げいにん', surface='芸人', category_id='comedian',
                     source_surface='芸人', source_reading='げいにん', **common),
                dict(reading='やきゅうせんしゅ', surface='野球選手', sport='baseball',
                     source_surface='野球選手', source_reading='やきゅうせんしゅ', **common),
            ]
            (additions_dir / 'reviewed.jsonl').write_text(
                ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                encoding='utf-8')

            comedian_key = exporter.candidate_key('げいにん', '芸人')
            final = {comedian_key: ('げいにん', '芸人', 'actor', set())}
            exporter.apply_person_additions(root, final, {'comedian', 'sports'})

            self.assertEqual(final[comedian_key], ('げいにん', '芸人', 'comedian', set()))
            self.assertEqual(final[exporter.candidate_key('やきゅうせんしゅ', '野球選手')],
                             ('やきゅうせんしゅ', '野球選手', 'sports', {'baseball'}))


class PersonNameOriginExportTest(unittest.TestCase):
    def test_applies_origin_targets_and_preserves_dictionary_tags(self):
        reading, surface = 'たなか', '田中'
        key = exporter.candidate_key(reading, surface)
        final = {key: (reading, surface, 'surname_origin_unconfirmed', {'野球'})}
        count = exporter.apply_name_origin_mapping(
            final, {key: ('surname_origin_unconfirmed', 'surname_origin_japanese')})
        self.assertEqual(count, 1)
        self.assertEqual(final[key], (reading, surface, 'surname_origin_japanese', {'野球'}))

    def test_skips_mapping_for_candidates_already_reclassified_by_a_later_review(self):
        reading, surface = 'あやなん', 'あやなん'
        key = exporter.candidate_key(reading, surface)
        final = {key: (reading, surface, 'online_creator', set())}
        mapping = {key: ('personal_name_origin_unconfirmed', 'personal_name_origin_japanese')}
        self.assertEqual(exporter.apply_name_origin_mapping(final, mapping, {key}), 0)
        self.assertEqual(final[key][2], 'online_creator')

    def test_rejects_missing_or_mismatched_origin_source(self):
        reading, surface = 'たなか', '田中'
        key = exporter.candidate_key(reading, surface)
        final = {key: (reading, surface, 'surname_origin_unconfirmed', set())}
        with self.assertRaisesRegex(ValueError, 'do not cover unresolved'):
            exporter.apply_name_origin_mapping(final, {}, {key})
        with self.assertRaisesRegex(ValueError, 'source category'):
            exporter.apply_name_origin_mapping(
                final, {key: ('given_name_origin_unconfirmed', 'surname_origin_japanese')}, {key})


class PersonFilterExportTest(unittest.TestCase):
    def test_protected_sports_pair_survives_legacy_and_external_exclusions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'project'
            classification = root / 'src/main/classification'
            classification.mkdir(parents=True)
            protected = ('かな', '仮名')
            restricted = ('かな', '佳奈')
            protected_key = exporter.candidate_key(*protected)
            crime_keys = classification / 'crime-offender-exclusion-keys.sha256'
            crime_keys.write_text(protected_key + '\n')
            with gzip.open(classification / 'distribution-candidates.tsv.gz', 'wt', encoding='utf-8') as stream:
                for reading, surface in (protected, restricted):
                    stream.write(f'person\t{reading}\t1\t1\t100\t{surface}\n')
            initial, recovery = root / 'initial', root / 'recovery'
            initial.mkdir()
            recovery.mkdir()
            initial_rows = [dict(reading=r, surface=s, candidate_key=exporter.candidate_key(r, s),
                                 category_id='actor', category_code=4) for r, s in (protected, restricted)]
            (initial / 'batch.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in initial_rows))
            (recovery / 'batch.jsonl').write_text('')
            decisions = root / 'decisions.jsonl'
            decisions.write_text(json.dumps(dict(reading=protected[0], surface=protected[1],
                                                 candidate_key=protected_key, category_id='adult_performer',
                                                 status='adult_performer_source_confirmed'), ensure_ascii=False) + '\n')
            external = Path(temporary) / 'external-exclusions.jsonl'
            external.write_text(json.dumps({'candidate_key': protected_key, 'category_id': 'adult_performer'}) + '\n')
            categories = [dict(id='actor', number=4, standard_enabled=True),
                          dict(id='sports', number=12, standard_enabled=True)] + [
                dict(id=f'category_{i}', number=100 + i, standard_enabled=True) for i in range(27)
            ]
            args = SimpleNamespace(root=root, excluded_candidates=external, source_decisions=decisions,
                                   wikidata_sports=root / 'sports.jsonl', gemini_results=initial,
                                   recovery_gemini_results=recovery, output=root / 'output.tsv.gz')

            def reviewed_results(input_dir, output_dir, *_args, **_kwargs):
                output_dir.mkdir(parents=True)
                shutil.copyfile(input_dir / 'batch.jsonl', output_dir / 'batch.jsonl')

            def add_sports(_root, final, _enabled):
                final[protected_key] = (*protected, 'sports', {'athletics'})

            with mock.patch.object(exporter.dictionary_filters, 'current_snapshot_details',
                                   return_value=('a' * 40, {restricted}, {protected})), \
                    mock.patch.object(exporter.reviews, 'taxonomy_maps', return_value=({'categories': categories}, {4: {'id': 'actor'}}, {})), \
                    mock.patch.object(exporter.reviews, 'load_overrides', return_value={}), \
                    mock.patch.object(exporter.reviews, 'review_gemini_results', side_effect=reviewed_results), \
                    mock.patch.object(exporter.reviews, 'wikidata_sports_by_qid', return_value={}), \
                    mock.patch.object(exporter.reviews, 'source_review', return_value=([], {}, {}, {}, {}, {})), \
                    mock.patch.object(exporter.reviews, 'apply_source_overrides'), \
                    mock.patch.object(exporter, 'apply_person_additions', side_effect=add_sports), \
                    mock.patch.object(exporter.name_origins, 'load_fixed_mapping', return_value=({}, {})):
                exporter.export(args)
            with gzip.open(args.output, 'rt', encoding='utf-8') as stream:
                rows = [line.rstrip('\n').split('\t') for line in stream]
            self.assertEqual([(row[1], row[5], row[0]) for row in rows], [(*protected, 'sports')])
            self.assertEqual(crime_keys.read_text(), protected_key + '\n')

    def test_shared_exclusions_take_precedence_over_person_additions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            classification = root / 'src/main/classification'
            classification.mkdir(parents=True)
            (classification / 'crime-offender-exclusion-keys.sha256').write_text('0' * 64 + '\n')
            restricted = ('かな', '仮名')
            allowed = ('かな', '佳奈')
            with gzip.open(classification / 'distribution-candidates.tsv.gz', 'wt', encoding='utf-8') as stream:
                for reading, surface in (restricted, allowed):
                    stream.write(f'person\t{reading}\t1\t1\t100\t{surface}\n')
            initial = root / 'initial'
            recovery = root / 'recovery'
            initial.mkdir()
            recovery.mkdir()
            initial_rows = [dict(reading=r, surface=s, candidate_key=exporter.candidate_key(r, s),
                                 category_id='actor', category_code=4) for r, s in (restricted, allowed)]
            (initial / 'batch.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in initial_rows))
            (recovery / 'batch.jsonl').write_text('')
            decisions = root / 'decisions.jsonl'
            decisions.write_text('')
            categories = [dict(id='actor', number=4, standard_enabled=True)] + [
                dict(id=f'category_{i}', number=100 + i, standard_enabled=True) for i in range(28)
            ]
            args = SimpleNamespace(root=root, excluded_candidates=None, source_decisions=decisions,
                                   wikidata_sports=root / 'sports.jsonl', gemini_results=initial,
                                   recovery_gemini_results=recovery, output=root / 'output.tsv.gz')

            def reviewed_results(input_dir, output_dir, *_args, **_kwargs):
                output_dir.mkdir(parents=True)
                shutil.copyfile(input_dir / 'batch.jsonl', output_dir / 'batch.jsonl')

            def add_restricted_again(_root, final, _enabled):
                final[exporter.candidate_key(*restricted)] = (*restricted, 'actor', set())

            with mock.patch.object(exporter.dictionary_filters, 'current_snapshot_details', return_value=('a' * 40, {restricted}, set())), \
                    mock.patch.object(exporter.reviews, 'taxonomy_maps', return_value=({'categories': categories}, {4: {'id': 'actor'}}, {})), \
                    mock.patch.object(exporter.reviews, 'load_overrides', return_value={}), \
                    mock.patch.object(exporter.reviews, 'review_gemini_results', side_effect=reviewed_results), \
                    mock.patch.object(exporter.reviews, 'wikidata_sports_by_qid', return_value={}), \
                    mock.patch.object(exporter.reviews, 'source_review', return_value=([], {}, {}, {}, {}, {})), \
                    mock.patch.object(exporter.reviews, 'apply_source_overrides'), \
                    mock.patch.object(exporter, 'apply_person_additions', side_effect=add_restricted_again), \
                    mock.patch.object(exporter.name_origins, 'load_fixed_mapping', return_value=({}, {})):
                exporter.export(args)
            with gzip.open(args.output, 'rt', encoding='utf-8') as stream:
                rows = [line.rstrip('\n').split('\t') for line in stream]
            self.assertEqual([(row[1], row[5]) for row in rows], [allowed])


if __name__ == '__main__':
    unittest.main()
