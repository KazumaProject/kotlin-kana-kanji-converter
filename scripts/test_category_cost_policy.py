import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import classified_distribution as distribution
import specialist_distribution


class CategoryCostPolicyTest(unittest.TestCase):
    def test_release_manifest_records_exact_policy_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy_file = root / distribution.CATEGORY_COST_POLICY_PATH
            policy_file.parent.mkdir(parents=True)
            policy_file.write_bytes(Path(distribution.CATEGORY_COST_POLICY_PATH).read_bytes())
            (policy_file.parent / 'distribution-manifest.json').write_text(json.dumps({'categoryRows': {'term': 1}}))
            archive = root / 'dictionary.zip'
            with zipfile.ZipFile(archive, 'w') as stream:
                stream.writestr('app/src/main/assets/categories/term/token.dat.zip', b'fixture')
            with patch.object(specialist_distribution, 'verify_files', return_value={'categoryRows': {'medical': 1}}), \
                    patch.object(specialist_distribution, 'licenses', return_value='fixture license'):
                distribution.release_manifest(root, archive, 'test-revision')
            manifest = json.loads((root / 'dictionary-distribution-manifest.json').read_text())
            self.assertEqual(manifest['categoryCostPolicy'], dict(
                distribution.category_cost_policy(root), sourcePath=distribution.CATEGORY_COST_POLICY_PATH,
                sha256=distribution.sha(policy_file)))
            self.assertEqual(manifest['categoryCount'], 2)
            self.assertIn(distribution.sha(archive), (root / 'DICTIONARY-SHA256SUMS').read_text())

    def test_invalid_policy_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / distribution.CATEGORY_COST_POLICY_PATH
            path.parent.mkdir(parents=True)
            policy = json.loads(Path(distribution.CATEGORY_COST_POLICY_PATH).read_text())
            for field in ('unpenalizedReadingLength', 'costPerExtraCharacter', 'maximumPenalty'):
                path.write_text(json.dumps(dict(policy, **{field: -1})))
                with self.assertRaises(ValueError):
                    distribution.category_cost_policy(root)
            path.write_text(json.dumps(dict(policy, schemaVersion=2)))
            with self.assertRaises(ValueError):
                distribution.category_cost_policy(root)


if __name__ == '__main__':
    unittest.main()
