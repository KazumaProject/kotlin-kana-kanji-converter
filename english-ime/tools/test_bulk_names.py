import gzip
import json
from pathlib import Path
import tempfile
import unittest

import bulk_names as b


class BulkNamesTest(unittest.TestCase):
    def test_explicit_roles_are_collected_to_end_without_splitting_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'raw.gz';index=root/'index';index.write_text('Fixture catalogue')
            rows=[dict(word='Alice',lang_code='en',pos='name',categories=['English female given names']),
                  dict(word='Smith',lang_code='en',pos='name',categories=['English surnames from occupations']),
                  dict(word='Alice Smith',lang_code='en',pos='name',categories=[]),
                  dict(word='foreign',lang_code='fr',pos='name',categories=['English surnames']),
                  dict(word='late name',lang_code='en',pos='name',senses=[dict(categories=['English unisex given names'])])]
            with gzip.open(source,'wt') as f:
                for row in rows:f.write(json.dumps(row)+'\n')
            b.capture(source,root/'out',index);records,manifest=b.collect(root/'out')
            self.assertEqual({'Alice','Smith','late name'},{r['surface'] for r in records})
            self.assertEqual(5,manifest['counts']['allRecords']);self.assertTrue(manifest['complete'])
            self.assertNotIn('Alice Smith',{r['surface'] for r in records})

    def test_truncated_stream_cannot_be_sealed_as_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'raw.gz';index=root/'index';index.write_text('Fixture')
            data=gzip.compress((json.dumps(dict(word='Alice',lang_code='en',pos='name',categories=['English female given names']))+'\n').encode())
            source.write_bytes(data[:-5])
            with self.assertRaises((EOFError,OSError)):b.capture(source,root/'out',index)
            self.assertFalse((root/'out/bulk.json').exists())
