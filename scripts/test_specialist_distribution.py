import csv
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import classified_distribution as base
import specialist_distribution as s


class SpecialistTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.directory = self.root / s.DIRECTORY
        self.directory.mkdir(parents=True)
        (self.root/'src/main/resources').mkdir(parents=True)
        (self.root/'src/main/resources/id.def').write_text('0 BOS/EOS,*,*,*,*,*,*\n1 '+s.NOUN+'\n')
        (self.directory/'categories.json').write_text(json.dumps({'categories':[{'id':'kampo'},{'id':'medical'}]}))
        (self.directory/'sources').mkdir(); (self.directory/'notices').mkdir()
        (self.directory/'notices/license.txt').write_text('test notice')
        sources=[dict(id=i,category=c) for i,c in [('kampo','kampo'),('manbyo','medical'),('hyakuyaku','medical')]]
        (self.directory/'sources.json').write_text(json.dumps({'sources':sources}))
        self.inventory=self.root/'existing.jsonl.gz'
        self.inventory.write_bytes(s.compressed_json([
            dict(dictionary='system',reading='あ',surface='甲'),
            dict(dictionary='categories/term',reading='い',surface='乙'),
            dict(dictionary='single_kanji',reading='う',surface='丙')]))
        self.source('kampo',[('か','漢方'),('あ','甲'),('か','漢方')])
        self.source('manbyo',[('あ','甲'),('い','乙'),('う','丙'),('か','漢方'),
                              ('え','甲'),('お','症状'),('お','別症状'),('き','医薬'),('カナ','カナ'),
                              ('ろ','ローマ'),('め\t','医'),('abc','医'),('','医'),('く','[AMB]')])
        self.source('hyakuyaku',[('き','医薬'),('さ','薬品')])

    def source(self, name, rows):
        values=[dict(row=i,reading=r,surface=t) for i,(r,t) in enumerate(rows,2)]
        (self.directory/'sources'/f'{name}.jsonl.gz').write_bytes(s.compressed_json(values))

    def freeze(self): s.freeze(self.root,self.inventory)

    def rows(self):
        with gzip.open(self.directory/'distribution-candidates.tsv.gz','rt') as f:
            return [line.rstrip('\n').split('\t') for line in f]

    def test_existing_pair_only_cross_category_priority_and_multiple_provenance(self):
        self.freeze(); s.verify(self.root,self.inventory)
        rows=self.rows(); pairs={(r[0],r[1],r[5]) for r in rows}
        self.assertNotIn(('medical','あ','甲'),pairs)
        self.assertNotIn(('medical','い','乙'),pairs)
        self.assertNotIn(('medical','う','丙'),pairs)
        self.assertNotIn(('medical','か','漢方'),pairs)
        self.assertIn(('kampo','か','漢方'),pairs)
        self.assertIn(('medical','え','甲'),pairs)
        self.assertIn(('medical','お','症状'),pairs);self.assertIn(('medical','お','別症状'),pairs)
        self.assertTrue(all(r[2:5]==['1','1','9000'] for r in rows))
        provenance=list(s.read_json_gzip(self.directory/'provenance.jsonl.gz'))
        both=[r for r in provenance if r['reading']=='き' and r['surface']=='医薬']
        self.assertEqual({r['source'] for r in both},{'manbyo','hyakuyaku'})
        self.assertEqual(sorted(r['status'] for r in both),['adopted','source_duplicate'])

    def test_gemini_missing_reading_preserves_raw_and_hashes_provenance(self):
        entry=dict(source='manbyo', sourceRow=14, surface='医', reading='い', model='gemini-3.5-flash-lite',
                   readingStatus='gemini_inferred_unverified',requestSha256='a'*64,responseSha256='b'*64)
        path=self.directory/'gemini-readings.jsonl.gz'
        path.write_bytes(s.compressed_json([entry]))
        self.freeze();s.verify(self.root,self.inventory)
        row=next(r for r in s.read_json_gzip(self.directory/'provenance.jsonl.gz') if r['source']=='manbyo' and r['sourceRow']==14)
        self.assertEqual((row['originalReading'],row['reading'],row['readingOrigin']),('','い','gemini_inferred_unverified'))
        self.assertEqual(row['inference'],entry)
        entry['sourceRow']=2;entry['surface']='甲';path.write_bytes(s.compressed_json([entry]))
        with self.assertRaisesRegex(ValueError,'missing source reading'):self.freeze()
        entry['sourceRow']=999;path.write_bytes(s.compressed_json([entry]))
        with self.assertRaisesRegex(ValueError,'Unknown Gemini'):self.freeze()

    def test_normalization_preserves_width_case_variants_and_internal_spaces(self):
        self.assertEqual(s.key(' ｶﾞﾝ ',' 癌 '),('がん','癌'))
        self.assertEqual(s.key('ガン','癌'),('がん','癌'))
        for surface in ['ＡＢ','AB','Ab','A B','﨑']:
            self.assertEqual(s.normalize_surface(surface),surface)
        self.assertNotEqual(s.key('あ','ＡＢ'),s.key('あ','AB'))

    def test_invalid_readings_and_sentinel_surface_are_withheld(self):
        self.freeze()
        statuses={r['originalReading']:r['status'] for r in s.read_json_gzip(self.directory/'provenance.jsonl.gz') if r['source']=='manbyo'}
        self.assertEqual(statuses['ろ'],'unsupported_kana_surface')
        self.assertEqual(statuses['め\t'],'control_character')
        self.assertEqual(statuses['abc'],'non_kana_reading')
        self.assertEqual(statuses[''],'missing_or_placeholder')
        self.assertEqual(statuses['カナ'],'adopted')
        # The current builder does not turn ゔ into ヴ; do not silently fix its behavior here.
        self.assertEqual(s.invalid_reason('ゔ','ヴ','ゔ','ヴ'),'unsupported_kana_surface')

    def test_deterministic_freeze(self):
        self.freeze(); first={p.name:p.read_bytes() for p in self.directory.glob('distribution-*')}
        first['provenance']= (self.directory/'provenance.jsonl.gz').read_bytes()
        self.freeze()
        self.assertEqual(first,{**{p.name:p.read_bytes() for p in self.directory.glob('distribution-*')},
                                'provenance':(self.directory/'provenance.jsonl.gz').read_bytes()})

    def test_removed_classified_pair_is_not_reintroduced_as_specialist(self):
        directory = self.root / 'src/main/classification'
        directory.mkdir()
        path = directory / 'distribution-decisions.tsv.gz'
        base.write_gzip(path, [('え', '甲', 'term', 'manual', 'excluded')])
        self.freeze()
        s.verify(self.root, self.inventory)
        self.assertFalse(any(row[1] == 'え' and row[5] == '甲' for row in self.rows()))
        record = next(row for row in s.read_json_gzip(self.directory/'provenance.jsonl.gz')
                      if row['reading'] == 'え' and row['surface'] == '甲')
        self.assertEqual(record['status'], 'excluded_by_classification_review')
        self.assertTrue(any(row[1] == 'お' and row[5] == '症状' for row in self.rows()))
        base.write_gzip(path, [('え', '甲', 'term', 'manual', 'classified')])
        with self.assertRaisesRegex(ValueError, 'input hash mismatch'):
            s.verify(self.root, self.inventory)

    def test_changed_existing_inventory_is_rejected(self):
        self.freeze();self.inventory.write_bytes(s.compressed_json([]))
        with self.assertRaisesRegex(ValueError,'inventory changed'):s.verify(self.root,self.inventory)

    def test_changed_source_notice_and_id_def_are_rejected(self):
        self.freeze()
        for path in [self.directory/'sources/manbyo.jsonl.gz',self.directory/'notices/license.txt',self.root/'src/main/resources/id.def']:
            original=path.read_bytes();path.write_bytes(original+b'changed')
            with self.assertRaisesRegex(ValueError,'hash mismatch|id.def changed'):s.verify(self.root,self.inventory)
            path.write_bytes(original)

    def test_rehashing_corrupt_outputs_does_not_hide_changed_selection(self):
        self.freeze(); path=self.directory/'distribution-candidates.tsv.gz'
        base.write_gzip(path,[('medical','あ','1','1','9000','甲')])
        mpath=self.directory/'distribution-manifest.json';m=json.loads(mpath.read_text())
        m['files'][path.name]=base.sha(path);base.write_json(mpath,m)
        with self.assertRaisesRegex(ValueError,'recomputed source selection'):s.verify(self.root,self.inventory)

    def test_manifest_count_tampering_is_rejected(self):
        self.freeze();path=self.directory/'distribution-manifest.json';m=json.loads(path.read_text())
        m['categoryRows']['medical']+=1;base.write_json(path,m)
        with self.assertRaisesRegex(ValueError,'manifest differs'):s.verify(self.root,self.inventory)

    def test_csv_quotes_multiline_and_encoding_only_extract_selected_columns(self):
        for encoding in ['utf-8-sig','cp932']:
            text=io.StringIO(newline='');writer=csv.writer(text)
            writer.writerow(['表記','読み','ICDコード']);writer.writerow(['薬,剤','ヤクザイ','SECRET'])
            writer.writerow(['病\n名','ビョウメイ','SECRET2'])
            buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,'w') as z:z.writestr('source.csv',text.getvalue().encode(encoding))
            spec=dict(id='csv',member='source.csv',encoding=encoding,surfaceColumn='表記',readingColumn='読み')
            rows=list(s.extract_pairs(buffer.getvalue(),spec))
            self.assertEqual(rows,[dict(row=2,reading='ヤクザイ',surface='薬,剤'),dict(row=3,reading='ビョウメイ',surface='病\n名')])
            self.assertNotIn('SECRET',json.dumps(rows))

    def test_missing_csv_columns_fail(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:z.writestr('source.csv','表記,OTHER\n病,あ\n')
        spec=dict(id='csv',member='source.csv',encoding='utf-8',surfaceColumn='表記',readingColumn='読み')
        with self.assertRaisesRegex(ValueError,'columns missing'):list(s.extract_pairs(buffer.getvalue(),spec))


if __name__=='__main__':unittest.main()
