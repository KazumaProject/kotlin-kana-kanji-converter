import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import luna_reclassification as l

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.directory=self.root/'results'; self.directory.mkdir()
        self.target={'candidate_key':l.d.key('よみ','字'),'reading':'よみ','surface':'字','original_status':'unclassified'}
        self.manifest={'files':{'targets.jsonl.gz':'snapshot'},'baselineManifest':{'categoryRows':{'term':0}}}
        self.row={'candidate_key':self.target['candidate_key'],'reading':'よみ','surface':'字','action':'adopt','categories':['term'],'reason':'test','policy_version':l.POLICY,'model':l.MODEL,'reasoning_effort':l.EFFORT}
        self.meta={'target_sha256':'snapshot','candidate_keys':[self.target['candidate_key']],'policy_version':l.POLICY,'model':l.MODEL,'reasoning_effort':l.EFFORT}
        self.mock=patch.object(l,'snapshot',return_value=(self.manifest,[self.target],{})); self.mock.start()
    def tearDown(self): self.mock.stop(); self.temp.cleanup()
    def write(self, rows=None, meta=None):
        l.write_jsonl(self.directory/'000000.jsonl',rows if rows is not None else [self.row])
        l.d.write_json(self.directory/'000000.meta.json',meta or self.meta)
    def test_valid_and_exact_variants(self):
        self.write(); result=l.load_results(self.root,self.directory)[3]
        self.assertEqual(result[self.target['candidate_key']]['effective_categories'],['term'])
    def test_invalid(self):
        cases=[dict(self.row,surface='別'),dict(self.row,categories=['unknown']),dict(self.row,reason=''),dict(self.row,model='other'),dict(self.row,policy_version='legacy'),dict(self.row,action='hold'),dict(self.row,action='hold',categories=[])]
        for row in cases:
            with self.subTest(row=row):
                self.write([row])
                with self.assertRaises(ValueError): l.load_results(self.root,self.directory)
    def test_duplicate_missing_and_unknown(self):
        for rows in ([self.row,self.row],[],[dict(self.row,candidate_key='unknown')]):
            self.write(rows)
            with self.assertRaises(ValueError): l.load_results(self.root,self.directory)
    def test_reject_and_unrepresentable_adopt(self):
        self.write([dict(self.row,action='reject',categories=[])])
        result=l.load_results(self.root,self.directory)[3][self.target['candidate_key']]
        self.assertEqual(result['effective_action'],'reject')
        self.assertEqual(result['effective_reason'],self.row['reason'])
        self.assertEqual(result['batch_provenance']['batch_stem'],'000000')
        self.assertEqual(result['batch_provenance']['candidate_key_position'],0)
        self.target.update(surface='べつ',candidate_key=l.d.key('よみ','べつ'))
        self.row.update(surface='べつ',candidate_key=self.target['candidate_key'])
        self.meta['candidate_keys']=[self.target['candidate_key']]
        self.write()
        result=l.load_results(self.root,self.directory)[3][self.target['candidate_key']]
        self.assertEqual(result['response']['action'],'adopt')
        self.assertEqual(result['effective_action'],'reject')
        self.assertEqual(result['representation_error'],'hiragana_sentinel_changes_surface')
        self.assertEqual(result['effective_categories'],[])
        self.assertEqual(result['effective_reason'],l.REPRESENTATION_REASONS[result['representation_error']])
        self.assertEqual(result['response']['reason'],self.row['reason'])
    def test_partial_dry_run_only(self):
        with self.assertRaises(ValueError): l.apply(self.root,self.directory,allow_partial=True)
        self.assertEqual(l.load_results(self.root,self.directory,True)[3],{})
    def test_sentinels(self):
        self.assertIsNone(l.representation_error('よみ','ヨミ'))
        self.assertIsNone(l.representation_error('ゔ','ゔ'))
        self.assertIsNotNone(l.representation_error('よみ','べつ'))
        self.assertIsNotNone(l.representation_error('ゔ','ヴ')) # runtime excludes ゔ from hiraToKata
        self.assertIsNotNone(l.representation_error('が','か\u3099'))
    def test_deterministic_jsonl(self):
        a=self.root/'a.gz'; b=self.root/'b.gz'
        l.write_jsonl(a,[self.row]); l.write_jsonl(b,[self.row])
        self.assertEqual(a.read_bytes(),b.read_bytes()); self.assertEqual(l.jsonl(a),[self.row])
    def test_recover(self):
        backup=self.root/'build/luna-classification/apply-backup'; backup.mkdir(parents=True)
        paths=[l.REL+'/results.jsonl.gz',*['src/main/classification/'+n for n in l.FILES]]
        existing=paths[1:]
        for p in paths:
            dest=self.root/p; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text('changed')
            if p in existing:
                old=backup/p; old.parent.mkdir(parents=True,exist_ok=True); old.write_text('original')
        l.d.write_json(backup/'journal.json',{'paths':paths,'existing':existing})
        l.recover(self.root)
        for p in existing: self.assertEqual((self.root/p).read_text(),'original')
        self.assertFalse((self.root/paths[0]).exists())
    def test_recovery_refuses_unrelated_paths(self):
        backup=self.root/'build/luna-classification/apply-backup'; backup.mkdir(parents=True)
        protected=self.root/'protected'; protected.write_text('safe')
        l.d.write_json(backup/'journal.json',{'paths':['protected'],'existing':[]})
        with self.assertRaises(ValueError): l.recover(self.root)
        self.assertEqual(protected.read_text(),'safe')
    def test_recovery_refuses_active_apply(self):
        import fcntl
        build=self.root/'build/luna-classification'; build.mkdir(parents=True)
        with (build/'apply.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            with self.assertRaisesRegex(ValueError,'active'): l.recover(self.root)

class FixtureTests(unittest.TestCase):
    def test_export_apply_idempotence_and_offline_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); directory=root/'src/main/classification'; directory.mkdir(parents=True)
            categories={f'c{i}':0 for i in range(28)}
            l.d.write_json(directory/'categories.json',{'categories':[{'id':c} for c in categories]})
            resource=root/'src/main/resources/id.def'; resource.parent.mkdir(); resource.write_text('1 noun\n')
            source=root/'fixture.txt'; source.write_text('よみ\t1\t1\t5\t字\nよみ\t1\t1\t9\t字\nほりゅう\t1\t1\t8\t保留\nすみ\t1\t1\t3\t済\nみぶんるい\t1\t1\t4\t未分類\nじょがい\t1\t1\t4\t除外\n')
            source_map={'fixture':('fixture.txt',None)}
            dispositions=root/'dispositions.gz'
            l.d.write_gzip(dispositions,[('held','{"ime":[],"surfaceOnly":["c1"]}','fixture','ほりゅう','保留','unverified','{}','[]','["reason"]','[]'),('held','{"ime":[],"surfaceOnly":[]}','fixture','すみ','済','unverified','{}','[]','[]','[]')])
            base=[('みぶんるい','未分類','','gemini','unclassified'),('よみ','字','','no_result','no_result'),('すみ','済','c0','verified','classified'),('じょがい','除外','','manual','excluded')]
            l.d.write_gzip(directory/l.FILES[0],base)
            l.d.write_gzip(directory/l.FILES[1],[('c0','すみ','1','1','3','済')])
            manifest={'schemaVersion':1,'precedence':['verified','manual','gemini'],'provenance':{'dispositionsSha256':l.d.sha(dispositions)},'inputs':{'fixture.txt':l.d.sha(source)},'files':{n:l.d.sha(directory/n) for n in ('categories.json',*l.FILES[:2])},'idDefSha256':l.d.sha(resource),'sourceRows':{'fixture':6},'categoryRows':dict(categories,c0=1),'dictionaryRows':1,'admittedPairsByOrigin':{'verified':1},'uniqueAdmittedPairs':1,'excludedCandidatePairs':1,'excludedClassifiedPairs':1,'unclassifiedPairs':1,'noResultPairs':1}
            l.d.write_json(directory/l.FILES[2],manifest)
            with patch.object(l.d,'SOURCES',source_map):
                l.export(root,dispositions,'revision')
                pinned=(root/l.REL/'manifest.json').read_bytes()
                l.export(root,dispositions,'revision')
                self.assertEqual(pinned,(root/l.REL/'manifest.json').read_bytes())
                targets=l.jsonl(root/l.REL/'targets.jsonl.gz')
                self.assertEqual(len(targets),3)
                self.assertEqual(len(next(t for t in targets if t['reading']=='よみ')['source_rows']),2)
                l.batches(root,200)
                l.batches(root,200)
                request_path=root/'build/luna-classification/requests'
                (request_path/'extra.jsonl').write_text('stale')
                with self.assertRaises(ValueError): l.batches(root,200)
                (request_path/'extra.jsonl').unlink()
                results=root/'build/luna-classification/results'; results.mkdir()
                rows=[{**{k:t[k] for k in ('candidate_key','reading','surface')},'action':'adopt','categories':['c1'],'reason':'fixture','policy_version':l.POLICY,'model':l.MODEL,'reasoning_effort':l.EFFORT} for t in targets]
                for row in rows:
                    if row['reading']=='ほりゅう': row.update(action='reject',categories=[],reason='IMEに不適切な候補というfixture判断')
                l.write_jsonl(results/'000000.jsonl',rows)
                import shutil
                response_meta=json.loads((root/'build/luna-classification/requests/000000.meta.json').read_text())
                response_meta['policy_version']=l.POLICY
                response_meta['reply_sha256']='fixture-reply-sha'
                response_meta['evidence']={'request':'fixture'}
                l.d.write_json(results/'000000.meta.json',response_meta)
                # A manifest-only edit must fail before any dictionary writes.
                manifest_path=directory/l.FILES[2]
                original_manifest=manifest_path.read_bytes()
                edited=json.loads(original_manifest); edited['provenance']['unexpected']='tamper'
                l.d.write_json(manifest_path,edited)
                with self.assertRaises(ValueError): l.apply(root,results)
                manifest_path.write_bytes(original_manifest)
                snapshot_manifest=root/l.REL/'manifest.json'
                targets_path=root/l.REL/'targets.jsonl.gz'
                original_snapshot=snapshot_manifest.read_bytes(); original_targets=targets_path.read_bytes()
                def altered_targets(rows):
                    l.write_jsonl(targets_path,rows)
                    metadata=json.loads(original_snapshot)
                    metadata['files']['targets.jsonl.gz']=l.d.sha(targets_path)
                    metadata['targetCount']=len(rows)
                    metadata['targetCounts']=dict(l.collections.Counter(t['original_status'] for t in rows))
                    l.d.write_json(snapshot_manifest,metadata)
                for changed in ([*targets,targets[0]], [t for t in targets if t['original_status']!='unclassified'],
                                [dict(t,candidate_key='invalid') if i==0 else t for i,t in enumerate(targets)],
                                [dict(t,source_rows=[]) if i==0 else t for i,t in enumerate(targets)],
                                [dict(t,source_rows=[['fixture','wrong','1','1','1',t['surface']]]) if i==0 else t for i,t in enumerate(targets)]):
                    altered_targets(changed)
                    with self.assertRaises(ValueError): l.snapshot(root)
                targets_path.write_bytes(original_targets); snapshot_manifest.write_bytes(original_snapshot)
                before={n:(directory/n).read_bytes() for n in l.FILES}
                real_replace=l.os.replace
                mutations=[0]
                def fail_second(src,dst):
                    mutations[0]+=1
                    if mutations[0]==2: raise OSError('simulated interruption')
                    return real_replace(src,dst)
                with patch.object(l.os,'replace',side_effect=fail_second):
                    with self.assertRaises(OSError): l.apply(root,results)
                self.assertEqual(before,{n:(directory/n).read_bytes() for n in l.FILES})
                self.assertFalse((root/l.REL/'results.jsonl.gz').exists())
                l.apply(root,results)
                after=[l.d.sha(directory/n) for n in l.FILES]
                l.apply(root,results)
                self.assertEqual(after,[l.d.sha(directory/n) for n in l.FILES])
                self.assertEqual(l.decisions(directory/l.FILES[0])[('すみ','済')],list(base[2]))
                ledger=l.jsonl(root/l.REL/'results.jsonl.gz')
                self.assertTrue(all(r['batch_provenance']['reply_sha256']=='fixture-reply-sha' for r in ledger))
                self.assertTrue(all(r['batch_provenance']['evidence']=={'request':'fixture'} for r in ledger))
                self.assertTrue(all('candidate_keys' not in r['batch_provenance'] for r in ledger))
                final_manifest=(directory/l.FILES[2]).read_bytes()
                for field,value in [('effectiveActions',{'hold':3}),('model','wrong'),('reasoningEffort','low'),('policy_version','legacy')]:
                    edited=json.loads(final_manifest)
                    edited['provenance']['lunaReclassification'][field]=value
                    l.d.write_json(directory/l.FILES[2],edited)
                    with self.assertRaises(ValueError): l.verify_ledger(root)
                (directory/l.FILES[2]).write_bytes(final_manifest)
                l.verify_ledger(root)
                final=json.loads((directory/l.FILES[2]).read_text())
                self.assertEqual(final['excludedCandidatePairs'],2)
                self.assertEqual(final['excludedClassifiedPairs'],2)
                self.assertEqual(final['unclassifiedPairs'],0)
                self.assertEqual(final['noResultPairs'],0)
                self.assertEqual(l.decisions(directory/l.FILES[0])[('じょがい','除外')],list(base[3]))
                self.assertEqual(l.decisions(directory/l.FILES[0])[('ほりゅう','保留')][4],'excluded')
                with gzip.open(directory/l.FILES[1],'rt') as f: self.assertEqual(len(list(f)),4)

class EmptyExportTests(unittest.TestCase):
    def test_empty_snapshot_and_atomic_export_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); directory=root/'src/main/classification'; directory.mkdir(parents=True)
            categories={f'c{i}':0 for i in range(28)}
            l.d.write_json(directory/'categories.json',{'categories':[{'id':c} for c in categories]})
            resource=root/'src/main/resources/id.def'; resource.parent.mkdir(); resource.write_text('1 noun\n')
            source=root/'fixture.txt'; source.write_text('')
            dispositions=root/'dispositions.gz'; l.d.write_gzip(dispositions,[])
            for name in l.FILES[:2]: l.d.write_gzip(directory/name,[])
            manifest={'schemaVersion':1,'precedence':['verified','manual','gemini'],'provenance':{'dispositionsSha256':l.d.sha(dispositions)},'inputs':{'fixture.txt':l.d.sha(source)},'files':{n:l.d.sha(directory/n) for n in ('categories.json',*l.FILES[:2])},'idDefSha256':l.d.sha(resource),'sourceRows':{},'categoryRows':categories,'dictionaryRows':0,'admittedPairsByOrigin':{},'uniqueAdmittedPairs':0,'excludedCandidatePairs':0,'excludedClassifiedPairs':0,'unclassifiedPairs':0,'noResultPairs':0}
            l.d.write_json(directory/l.FILES[2],manifest)
            with patch.object(l.d,'SOURCES',{'fixture':('fixture.txt',None)}):
                with patch.object(l.os,'replace',side_effect=OSError('interrupt')):
                    with self.assertRaises(OSError): l.export(root,dispositions,'revision')
                self.assertFalse((root/l.REL).exists())
                self.assertEqual(list(directory.glob('.luna-export-*')),[])
                l.export(root,dispositions,'revision')
                m,targets,baseline=l.snapshot(root)
                self.assertEqual(m['targetCount'],0); self.assertEqual(targets,[]); self.assertEqual(baseline,{})
                l.batches(root,200); l.batches(root,200)
                self.assertEqual(list((root/'build/luna-classification/requests').iterdir()),[])

if __name__=='__main__': unittest.main()
