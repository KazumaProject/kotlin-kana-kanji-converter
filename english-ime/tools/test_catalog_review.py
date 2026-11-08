from pathlib import Path
import tempfile
import unittest

import catalog_review as r


class CatalogReviewPagesTest(unittest.TestCase):
    def test_pages_deduplicate_spellings_merge_kinds_and_split_large_categories(self):
        rows = [dict(surface=f'word{i:04}', topics='science.test', kind='lexical', change='metadata_only')
                for i in range(501)]
        rows += [dict(surface='word0000', topics='science.test', kind='product', change='new_spelling'),
                 dict(surface='domain only', topics='-', kind='lexical', change='metadata_only')]
        pages = r.word_pages(rows, {'science.test': {}})
        self.assertEqual({'science.test-001.tsv', 'science.test-002.tsv'}, set(pages))
        self.assertEqual(500, len(pages['science.test-001.tsv']))
        self.assertEqual([dict(surface='word0500', change='metadata_only', kinds='lexical')], pages['science.test-002.tsv'])
        self.assertEqual(dict(surface='word0000', change='added', kinds='lexical,product'), pages['science.test-001.tsv'][0])

    def test_verification_rejects_stale_counts_words_and_extra_files(self):
        rows = [dict(surface='sample', topics='science.test', kind='lexical', change='metadata_only')]
        topics = {'science.test': {}}
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            pages = r.word_pages(rows, topics)
            for name, records in pages.items():
                r.c.table(directory / name, r.WORD_FIELDS, records)
            r.verify_pages(directory, rows, topics)
            page = directory / 'science.test-001.tsv'
            original = page.read_text()
            page.write_text(original.replace('sample', 'invented'))
            with self.assertRaisesRegex(ValueError, 'differs from adopted ledger'):
                r.verify_pages(directory, rows, topics)
            page.write_text(original)
            (directory / 'unexpected.tsv').write_text(original)
            with self.assertRaisesRegex(ValueError, 'unexpected vocabulary pages'):
                r.verify_pages(directory, rows, topics)


if __name__ == '__main__':
    unittest.main()
