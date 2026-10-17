import gzip
import html
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import classified_distribution as distribution
import specialist_distribution as specialist
import write_classified_dictionary_catalog as catalog


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        source = self.root / 'src/main/classification'
        source.mkdir(parents=True)
        (source / 'runtime-cost-policy.json').write_text(
            Path('src/main/classification/runtime-cost-policy.json').read_text())
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
        self.assertIn('min(6000, 500 × max(0, 読みの長さ − 3))', (output/'index.md').read_text())
        self.assertIn('補正前の元コスト', (output/'index.md').read_text())

    def test_generation_is_deterministic_and_rejects_wrong_counts(self):
        a,b=self.root/'a',self.root/'b'
        catalog.generate(self.root,a)
        catalog.generate(self.root,b)
        self.assertEqual(catalog.hashes(a),catalog.hashes(b))
        path=self.root/'src/main/classification/distribution-manifest.json'
        manifest=json.loads(path.read_text());manifest['categoryRows']['person']=99
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'Catalog count differs'):catalog.generate(self.root,self.root/'bad')

    def test_catalog_marks_source_backed_specialist_reading_corrections(self):
        directory = self.root/'src/main/specialist'
        directory.mkdir(parents=True)
        (directory/'categories.json').write_text(Path('src/main/specialist/categories.json').read_text())
        candidates = directory/'distribution-candidates.tsv.gz'
        distribution.write_gzip(candidates, [('medical','きょぜつ','1','1','9000','巨舌')])
        provenance = directory/'provenance.jsonl.gz'
        provenance.write_bytes(specialist.compressed_json([dict(
            source='manbyo', sourceRow=78905, reading='きょぜつ', surface='巨舌', status='adopted',
            readingOrigin='curated_correction')]))
        (directory/'distribution-manifest.json').write_text(json.dumps(dict(
            rules=specialist.RULES, inputs={}, idDefSha256=distribution.sha(self.root/'src/main/resources/id.def'),
            files={'distribution-candidates.tsv.gz':distribution.sha(candidates),
                   'provenance.jsonl.gz':distribution.sha(provenance)},
            categoryRows={'kampo':0,'medical':1}, dictionaryRows=1, uniqueAdmittedPairs=1)))

        output = self.root/'catalog'
        catalog.generate(self.root, output)
        page = next((output/'medical').glob('page-*.md')).read_text()
        self.assertIn('| <code>きょぜつ</code> | <code>巨舌</code> | 1 | 1 | 9000 | 出典確認済みの読み訂正 |', page)

    def test_exclusions_are_complete_paginated_and_use_final_saved_reasons(self):
        source = self.root/'src/main/classification'
        distribution.write_gzip(source/'distribution-decisions.tsv.gz',[
            ('あ','甲<&|>','person,place','verified','classified'),('あ','乙','person','gemini','classified'),
            ('い','除外<&|>','','manual','excluded'),('う','却下','term','manual','excluded')])
        ledger = source/'luna.jsonl.gz'
        with gzip.open(ledger,'wt',encoding='utf-8') as stream:
            stream.write(json.dumps(dict(response=dict(reading='い',surface='除外<&|>'),
                effective_action='reject',effective_reason='形式<&|>の制約'),ensure_ascii=False)+'\n')
        review = source/'review.jsonl'
        review.write_text(json.dumps(dict(reading='う',surface='却下',action='exclude',reason='最終理由<&|>',
            evidence=dict(kind='user_confirmation')),ensure_ascii=False)+'\n')
        path=source/'distribution-manifest.json'
        manifest=json.loads(path.read_text())
        manifest['provenance']=dict(lunaReclassification=dict(path=str(ledger.relative_to(self.root))),
                                    reviews=[str(review.relative_to(self.root))])
        path.write_text(json.dumps(manifest))
        output=self.root/'catalog'
        with patch.object(catalog,'MAX_ROWS',1): summary=catalog.generate(self.root,output)
        self.assertEqual(summary['excluded'],dict(pairs=2,pages=2))
        first=(output/'excluded/page-0001.md').read_text()
        second=(output/'excluded/page-0002.md').read_text()
        self.assertIn('除外&lt;&amp;&#124;&gt;',first)
        self.assertIn('形式&lt;&amp;&#124;&gt;の制約',first)
        self.assertIn('最終理由&lt;&amp;&#124;&gt;',second)
        self.assertIn('ユーザー明示判断',second)
        self.assertIn('次のページ',first)
        self.assertIn('前のページ',second)
        self.assertIn('excluded/index.md',(output/'index.md').read_text())


if __name__ == '__main__':unittest.main()
