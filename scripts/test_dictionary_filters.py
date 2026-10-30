import json
import gzip
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import dictionary_filters
import prepare_dictionary_filter
import person_gemini_classification as gemini


class DictionaryFilterTest(unittest.TestCase):
    def make_source(self, directory):
        root = Path(directory)
        (root / 'categories/person').mkdir(parents=True)
        (root / 'manifest.json').write_text('{"schemaVersion":1}\n', encoding='utf-8')
        (root / 'categories/person/example.jsonl').write_text(json.dumps({
            'reading': 'かな', 'surface': '仮名', 'status': 'source_reviewed', 'evidence': [{'kind': 'test'}],
        }, ensure_ascii=False) + '\n', encoding='utf-8')
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        subprocess.run(['git', '-C', str(root), 'add', 'manifest.json', 'categories'], check=True)
        subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                        'commit', '-qm', 'fixture'], check=True)
        return root

    def test_preparation_uses_only_one_committed_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self.make_source(Path(temp) / 'repo')
            output = Path(temp) / 'snapshot'
            old = dict(os.environ)
            try:
                os.environ['DICTIONARY_FILTER_SOURCE'] = str(source)
                os.environ['DICTIONARY_FILTER_ALLOW_FIXTURE'] = '1'
                prepare_dictionary_filter.prepare(output)
                revision, pairs = dictionary_filters.load_snapshot(output)
                self.assertEqual(revision, subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip())
                self.assertEqual(pairs, {('かな', '仮名')})
                (source / 'categories/person/example.jsonl').write_text('not committed', encoding='utf-8')
                prepare_dictionary_filter.prepare(output)
                self.assertEqual(dictionary_filters.load_snapshot(output)[1], pairs)
            finally:
                os.environ.clear()
                os.environ.update(old)

    def test_invalid_and_duplicate_records_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self.make_source(Path(temp) / 'repo')
            (source / 'snapshot.json').write_text(json.dumps({
                'schemaVersion': 1, 'repository': dictionary_filters.REPOSITORY, 'revision': 'a' * 40,
            }), encoding='utf-8')
            category = source / 'categories/person/example.jsonl'
            row = category.read_text(encoding='utf-8')
            category.write_text(row + row, encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                dictionary_filters.load_snapshot(source)
            category.write_text('{"reading":"かな"}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Invalid'):
                dictionary_filters.load_snapshot(source)
            for status in ('hold', 'model_provisional'):
                unresolved = json.loads(row)
                unresolved['status'] = status
                category.write_text(json.dumps(unresolved, ensure_ascii=False) + '\n', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'Invalid'):
                    dictionary_filters.load_snapshot(source)

    def test_missing_snapshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises((FileNotFoundError, ValueError)):
                dictionary_filters.load_snapshot(Path(temp) / 'missing')

    def test_protected_sports_pair_overrides_an_exclusion_in_the_same_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self.make_source(Path(temp) / 'repo')
            category = source / 'categories/person/example.jsonl'
            category.write_text(category.read_text(encoding='utf-8') + json.dumps({
                'reading': 'かな', 'surface': '佳奈', 'status': 'source_reviewed', 'evidence': [{'kind': 'test'}],
            }, ensure_ascii=False) + '\n', encoding='utf-8')
            protected = source / prepare_dictionary_filter.SPORTS_ALLOW
            protected.parent.mkdir(parents=True)
            decision = {'reading': 'かな', 'surface': '佳奈', 'status': 'source_reviewed',
                        'action': 'allow', 'classification': 'person/sports', 'sport': 'athletics',
                        'evidence': [{'kind': 'test'}]}
            protected.write_text(json.dumps(decision, ensure_ascii=False) + '\n', encoding='utf-8')
            subprocess.run(['git', '-C', str(source), 'add', 'categories', 'decisions'], check=True)
            subprocess.run(['git', '-C', str(source), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                            'commit', '-qm', 'protect sports name'], check=True)
            with mock.patch.dict(os.environ, {'DICTIONARY_FILTER_SOURCE': str(source),
                                              'DICTIONARY_FILTER_ALLOW_FIXTURE': '1'}):
                snapshot = Path(temp) / 'snapshot'
                prepare_dictionary_filter.prepare(snapshot)
                self.assertEqual(dictionary_filters.load_snapshot(snapshot)[1], {('かな', '仮名')})
                decision['status'] = 'hold'
                (snapshot / prepare_dictionary_filter.SPORTS_ALLOW).write_text(
                    json.dumps(decision, ensure_ascii=False) + '\n', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'Invalid protected sports decision'):
                    dictionary_filters.load_snapshot(snapshot)

    def test_person_classification_withholds_all_shared_filter_categories(self):
        with tempfile.TemporaryDirectory() as temp:
            source = self.make_source(Path(temp) / 'repo')
            snapshot = Path(temp) / 'snapshot'
            root = Path(temp) / 'project'
            classification = root / 'src/main/classification'
            classification.mkdir(parents=True)
            original = Path(__file__).resolve().parents[1] / 'src/main/classification/person-taxonomy.json'
            (classification / 'person-taxonomy.json').write_bytes(original.read_bytes())
            with gzip.open(classification / 'distribution-candidates.tsv.gz', 'wt', encoding='utf-8') as stream:
                for reading, surface in [('かな', '仮名'), ('かな', '佳奈'), ('かな', '加奈')]:
                    stream.write(f'person\t{reading}\t1\t1\t100\t{surface}\n')
            key = lambda reading, surface: hashlib.sha256((reading + '\0' + surface).encode()).hexdigest()
            include = Path(temp) / 'include.txt'
            include.write_text('\n'.join(key('かな', surface) for surface in ('仮名', '佳奈')) + '\n')
            exclude = Path(temp) / 'exclude.jsonl'
            exclude.write_text(json.dumps({'candidate_key': key('かな', '加奈'), 'category_id': 'terrorism'}) + '\n')
            old = dict(os.environ)
            try:
                os.environ['DICTIONARY_FILTER_SOURCE'] = str(source)
                os.environ['DICTIONARY_FILTER_ALLOW_FIXTURE'] = '1'
                prepare_dictionary_filter.prepare(snapshot)
                os.environ['DICTIONARY_FILTER_SNAPSHOT'] = str(snapshot)
                manifest = gemini.manifest_for(root, 10, include, exclude)
                self.assertEqual([(item['reading'], item['surface']) for item in manifest['items']], [('かな', '佳奈')])
                self.assertEqual(manifest['filter_revision'], dictionary_filters.load_snapshot(snapshot)[0])
            finally:
                os.environ.clear()
                os.environ.update(old)


if __name__ == '__main__':
    unittest.main()
