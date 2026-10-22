import hashlib
import unittest

import export_person_dictionary_source as exporter


class PersonDictionaryExportNameOriginTest(unittest.TestCase):
    def test_applies_origin_targets_and_preserves_dictionary_tags(self):
        reading, surface = 'たなか', '田中'
        key = hashlib.sha256((reading + '\0' + surface).encode()).hexdigest()
        final = {key: (reading, surface, 'surname_origin_unconfirmed', {'野球'})}
        count = exporter.apply_name_origin_mapping(
            final, {key: ('surname_origin_unconfirmed', 'surname_origin_japanese')})
        self.assertEqual(count, 1)
        self.assertEqual(final[key], (reading, surface, 'surname_origin_japanese', {'野球'}))

    def test_rejects_incomplete_or_wrong_source_mapping(self):
        reading, surface = 'たなか', '田中'
        key = hashlib.sha256((reading + '\0' + surface).encode()).hexdigest()
        final = {key: (reading, surface, 'surname_origin_unconfirmed', set())}
        with self.assertRaisesRegex(ValueError, 'exactly cover'):
            exporter.apply_name_origin_mapping(final, {})
        with self.assertRaisesRegex(ValueError, 'source category'):
            exporter.apply_name_origin_mapping(
                final, {key: ('given_name_origin_unconfirmed', 'given_name_origin_japanese')})


if __name__ == '__main__':
    unittest.main()
