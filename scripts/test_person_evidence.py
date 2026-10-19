"""Source-provenance cache tests; historical AI text never constitutes adoption."""
import gzip
import json
from pathlib import Path
import shutil
import unittest
from unittest import mock

import person_subclassification as person
import prepare_person_evidence as evidence
import test_classified_distribution as base_fixture


class PersonEvidenceTest(unittest.TestCase):
    def setUp(self):
        fixture = base_fixture.DistributionTest('test_freeze_is_deterministic')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        names = self.root / 'src/main/bin/names.txt'
        with names.open('a') as stream:
            stream.write('あ\t1\t1\t-123\t甲\n')
        fixture.freeze()
        actual = Path(__file__).resolve().parents[1]
        directory = self.root / 'src/main/classification'
        shutil.copyfile(actual / 'src/main/classification/person-taxonomy.json',
                        directory / 'person-taxonomy.json')
        script = self.root / 'scripts/classified_distribution.py'
        script.parent.mkdir()
        shutil.copyfile(evidence.distribution.__file__, script)
        self.enterContext(mock.patch.object(evidence.distribution, '__file__', str(script)))
        legacy = directory / 'luna-reclassification'
        legacy.mkdir()
        hint = {'response': {'reading': 'あ', 'surface': '甲', 'categories': ['person']},
                'effective_action': 'adopt', 'effective_categories': ['person'],
                'effective_reason': 'Synthetic prior AI claim: actor, unverified.'}
        with gzip.open(legacy / 'results.jsonl.gz', 'wt') as stream:
            stream.write(json.dumps(hint, ensure_ascii=False) + '\n')
        target = {'reading': 'あ', 'surface': '甲',
                  'hints': [{'source': 'web', 'reason': 'Synthetic saved classifier hint'}]}
        with gzip.open(legacy / 'targets.jsonl.gz', 'wt') as stream:
            stream.write(json.dumps(target, ensure_ascii=False) + '\n')
        self.output = self.root / 'evidence-cache'
        evidence.build(self.root, self.output)

    def test_all_pairs_and_pos_costs_preserved_without_promoting_ai_hints(self):
        manifest = evidence.verify(self.root, self.output)
        items = person.collect_items(self.root)
        cached = list(evidence.jsonl(self.output / 'person-evidence.jsonl.gz'))
        self.assertEqual(len(items), 2)
        self.assertEqual(manifest['counts']['items'], 2)
        self.assertEqual(manifest['counts']['records'], 3)
        self.assertEqual([row['records'] for row in cached], [item['records'] for item in items])
        alpha = next(row for row in cached if row['surface'] == '甲')
        self.assertEqual({tuple(row[2:5]) for row in alpha['records']},
                         {('1', '1', '100'), ('1', '1', '-123')})
        self.assertIn(['person', 'あ', '1', '1', '-123', '甲'], alpha['source_rows'])
        self.assertTrue(all(row['classification_status'] == 'research_required' for row in cached))
        self.assertEqual(alpha['historical_ai_hints'][0]['verification'], 'unverified_ai_hint')
        self.assertEqual(alpha['target_hints'][0]['verification'], 'unverified_historical_hint')
        self.assertEqual(alpha['frozen_decision']['verification'], 'frozen_adoption_only')
        self.assertFalse(manifest['production_release'])
        self.assertTrue(all('adult_appearance_status' not in row and
                            'distribution_status' not in row for row in cached))

    def test_changed_raw_dictionary_source_invalidates_cache(self):
        source = self.root / 'src/main/bin/names.txt'
        with source.open('a') as stream:
            stream.write('うそ\t1\t1\t99\t合成名\n')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            evidence.verify(self.root, self.output)

    def test_changed_frozen_decision_ledger_invalidates_cache(self):
        ledger = self.root / 'src/main/classification/distribution-decisions.tsv.gz'
        raw = gzip.decompress(ledger.read_bytes())
        ledger.write_bytes(gzip.compress(raw + b'\n', mtime=0))
        with self.assertRaisesRegex(ValueError, 'source changed'):
            evidence.verify(self.root, self.output)

    def test_dropped_cache_item_fails_even_when_its_file_hash_is_updated(self):
        cache = self.output / 'person-evidence.jsonl.gz'
        records = list(evidence.jsonl(cache))
        self.assertEqual(len(records), 2)
        data = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in records[:-1])
        cache.write_bytes(gzip.compress(data.encode(), mtime=0))
        path = self.output / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['files'][cache.name] = person.sha(cache)
        person.write_json(path, manifest)
        with self.assertRaisesRegex(ValueError, 'cache universe mismatch'):
            evidence.verify(self.root, self.output)


if __name__ == '__main__':
    unittest.main()
