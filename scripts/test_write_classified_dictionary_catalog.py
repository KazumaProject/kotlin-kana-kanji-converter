import gzip
import html
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import classified_distribution as distribution
import write_classified_dictionary_catalog as catalog


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        source = self.root / 'src/main/classification'
        source.mkdir(parents=True)
        (self.root / 'src/main/resources').mkdir()
        (self.root / 'src/main/resources/id.def').write_text('0 BOS/EOS,*,*,*,*,*,*\n1 名詞,一般,*,*,*,*,*\n')
        categories = json.loads(Path('src/main/classification/categories.json').read_text())
        (source / 'categories.json').write_text(json.dumps(categories, ensure_ascii=False))
        self.rows = [('person','あ','1','1','100','甲<&|>'),('person','あ','1','1','200','乙'),('place','あ','1','1','100','甲<&|>')]
        distribution.write_gzip(source / 'distribution-candidates.tsv.gz', self.rows)
        distribution.write_gzip(source / 'distribution-decisions.tsv.gz', [
            ('あ','甲<&|>','person,place','verified','classified'),('あ','乙','person','gemini','classified')])
        counts = {c['id']: sum(row[0] == c['id'] for row in self.rows) for c in categories['categories']}
        (source / 'distribution-manifest.json').write_text(json.dumps({
            'categoryRows':counts, 'uniqueAdmittedPairs':2, 'dictionaryRows':3,
            'files':{'distribution-candidates.tsv.gz':distribution.sha(source/'distribution-candidates.tsv.gz')}}))

    def test_complete_paginated_list_preserves_values_and_escapes_markup(self):
        output = self.root / 'catalog'
        with patch.object(catalog,'MAX_ROWS',1): summary=catalog.generate(self.root,output)
        self.assertEqual(sum(c['pages'] for c in summary['categories']),3)
        rows=[]
        for page in sorted(output.glob('*/page-*.md')):
            for line in page.read_text().splitlines():
                match=re.fullmatch(r'\| <code>(.*?)</code> \| <code>(.*?)</code> \| (\d+) \| (\d+) \| (-?\d+) \| (.*?) \|',line)
                if match:
                    reading,surface,left,right,cost,_=match.groups()
                    rows.append((page.parent.name,html.unescape(reading),left,right,cost,html.unescape(surface)))
        self.assertEqual(rows,self.rows)
        person=next(c for c in summary['categories'] if c['id']=='person')
        self.assertEqual((person['pairs'],person['readings'],person['records']),(2,1,2))
        self.assertIn('次のページ',(output/'person/page-0001.md').read_text())
        self.assertIn('前のページ',(output/'person/page-0002.md').read_text())
        self.assertIn('名詞,一般',(output/'pos.md').read_text())

    def test_generation_is_deterministic_and_rejects_wrong_counts(self):
        a,b=self.root/'a',self.root/'b'
        catalog.generate(self.root,a)
        catalog.generate(self.root,b)
        self.assertEqual(catalog.hashes(a),catalog.hashes(b))
        path=self.root/'src/main/classification/distribution-manifest.json'
        manifest=json.loads(path.read_text());manifest['categoryRows']['person']=99
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'Catalog count differs'):catalog.generate(self.root,self.root/'bad')


if __name__ == '__main__':unittest.main()
