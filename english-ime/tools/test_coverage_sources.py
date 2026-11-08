import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlparse

import coverage_sources as s
import coverage_harness as controller
import gemini_acquisition as seeds


class CoverageSourcesTest(unittest.TestCase):
    def fixture(self,root,budget=20):
        rule=dict(schemaVersion=1,provider='wiktionary',language='en',pageSize=500,
            roots=[dict(topic='science.medicine',category='Category:en:Medicine')],excludeCategoryPatterns=['Taxonomic names'])
        path=root/'policy.json';s.h.dump(path,rule)
        return argparse.Namespace(source_dir=root/'source',policy=path,max_requests=budget,resume_from=None,advice=None,metadata_only=False)

    def download(self,url,path,maximum):
        args=parse_qs(urlparse(url).query);category=args['cmtitle'][0];children=args['cmtype']==['subcat']
        rows=[];continuation=None
        if children:
            if category=='Category:en:Medicine':rows=[dict(ns=14,pageid=2,title='Category:en:Anatomy',type='subcat'),dict(ns=14,pageid=3,title='Category:en:Taxonomic names',type='subcat')]
            else:rows=[dict(ns=14,pageid=1,title='Category:en:Medicine',type='subcat')]
        elif category=='Category:en:Medicine':
            if 'cmcontinue' not in args:
                rows=[dict(ns=0,pageid=i+100,title='medical term '+str(i),type='page') for i in range(500)]
                continuation={'continue':'-||','cmcontinue':'second-page'}
            else:rows=[dict(ns=0,pageid=999,title='later-page term',type='page')]
        else:rows=[dict(ns=0,pageid=1000,title='bone marrow',type='page')]
        value={'query':{'categorymembers':rows,'pages':{'1':{'ns':14,'title':category,'categoryinfo':{'pages':502}}}}}
        if 'cmcontinue' in args:value['query'].pop('pages')
        if continuation:value['continue']=continuation
        path.write_text(json.dumps(value))

    def test_follows_pagination_and_child_categories_beyond_one_hundred_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.fixture(Path(tmp))
            with patch.object(s.download,'download',self.download),patch.object(s.time,'sleep'):
                result=s.fetch(args)
            words,manifest,_=s.collect(args.source_dir,args.policy)
            self.assertTrue(result['complete'])
            self.assertEqual(502,len(words))
            self.assertIn('later-page term',{r['surface'] for r in words})
            self.assertIn('bone marrow',{r['surface'] for r in words})
            self.assertEqual(2,len(manifest['nodes']))
            self.assertEqual(1,len(manifest['exclusions']))
            self.assertTrue(all('Taxonomic names' not in n['category'] for n in manifest['nodes'].values()))

    def test_request_budget_is_pending_not_vocabulary_completion_and_resumes_without_refetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);args=self.fixture(root,budget=2)
            with patch.object(s.download,'download',self.download),patch.object(s.time,'sleep'):s.fetch(args)
            original=s.h.replay.sha(args.source_dir/'coverage.json')
            manifest=s.verify(args.source_dir,args.policy)
            self.assertFalse(manifest['complete']);self.assertEqual('request_budget',manifest['stopReason'])
            self.assertGreater(manifest['remainingCategories'],0)
            previous=args.source_dir;args=argparse.Namespace(**vars(args));args.source_dir=root/'resumed';args.resume_from=previous;args.max_requests=20
            calls=[]
            def fresh(url,path,maximum):calls.append(url);self.download(url,path,maximum)
            with patch.object(s.download,'download',fresh),patch.object(s.time,'sleep'):result=s.fetch(args)
            self.assertTrue(result['complete']);self.assertEqual(3,len(calls))
            self.assertEqual(original,s.h.replay.sha(previous/'coverage.json'))

    def test_interrupt_checkpoint_keeps_inflight_request_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.fixture(Path(tmp))
            with patch.object(s.download,'download',side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):s.fetch(args)
            checkpoint=s.h.replay.read_json(args.source_dir/'checkpoint.json')
            self.assertEqual(1,checkpoint['requests']);self.assertEqual('inflight',checkpoint['requestLog'][0]['status'])
            with patch.object(s.download,'download',self.download),patch.object(s.time,'sleep'):s.fetch(args)
            manifest=s.verify(args.source_dir,args.policy)
            self.assertEqual(6,manifest['sourceRequests']);self.assertEqual(6,len(manifest['requestLog']))
            self.assertTrue(manifest['complete'])

    def test_tampered_page_and_false_completion_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.fixture(Path(tmp),budget=2)
            with patch.object(s.download,'download',self.download),patch.object(s.time,'sleep'):s.fetch(args)
            p=args.source_dir/'coverage.json';manifest=s.h.replay.read_json(p);manifest['complete']=True;s.h.dump(p,manifest)
            with self.assertRaisesRegex(ValueError,'completion differs'):s.verify(args.source_dir,args.policy)
            manifest['complete']=False;s.h.dump(p,manifest)
            (args.source_dir/manifest['pages'][0]['file']).write_text('{}')
            with self.assertRaisesRegex(ValueError,'Changed source-tree payload'):s.verify(args.source_dir,args.policy)

    def test_advice_cannot_invent_source_nodes_and_counts_never_finish_pending_sources(self):
        batch=[dict(id='node-1')]
        def reply(items):return json.dumps(dict(modelVersion=s.h.MODEL,candidates=[dict(finishReason='STOP',content={'parts':[{'text':json.dumps(dict(items=items))}]})])).encode()
        rows,_=controller.response(reply([dict(id='node-1',priority='high',reason='practical subfield')]),batch)
        self.assertEqual('node-1',rows[0]['node'])
        with self.assertRaisesRegex(ValueError,'Unknown/invalid'):controller.response(reply([dict(id='invented',priority='high',reason='x')]),batch)
        node=dict(phase='terms',missing=False,termRows=100000)
        self.assertEqual('source_pending',controller.category_status([node]))
        self.assertEqual('source_not_declared',controller.category_status([]))
        self.assertEqual('source_missing',controller.category_status([dict(phase='missing',missing=True)]))

    def test_seed_selection_has_no_fifty_word_eligibility_cutoff(self):
        topics={'daily.home':dict(category='topic_home',label='Home',definition='Daily words')}
        analyses={f'word{i}':[dict(memberships={'topic_home'})] for i in range(1000)}
        selected=seeds.sparse_topics(topics,analyses,set(analyses),dict(topics=[dict(topic='daily.home',kind='lexical')],maximumExistingSpellings=None))
        self.assertEqual(1000,selected[0]['existingCount'])

    def test_stalled_page_is_a_source_error_not_a_success_or_an_endless_cache_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.fixture(Path(tmp))
            def stalled(url,path,maximum):
                self.download(url,path,maximum)
                query=parse_qs(urlparse(url).query)
                if 'cmcontinue' in query:
                    value=json.loads(path.read_text());value['continue']={'continue':'-||','cmcontinue':'second-page'};path.write_text(json.dumps(value))
            with patch.object(s.download,'download',stalled),patch.object(s.time,'sleep'):result=s.fetch(args)
            self.assertFalse(result['complete']);self.assertEqual('source_error',result['stopReason'])
            manifest=s.verify(args.source_dir,args.policy)
            self.assertTrue(manifest['errors'])
            self.assertIn('terms',{n['phase'] for n in manifest['nodes'].values()})

    def test_public_provenance_contains_pins_without_model_decisions_or_queue_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.fixture(Path(tmp),budget=2)
            with patch.object(s.download,'download',self.download),patch.object(s.time,'sleep'):s.fetch(args)
            manifest=s.verify(args.source_dir,args.policy)
            manifest['advisor']=dict(model='test',promptSha256='p',files={'response.json':'digest'},
                decisions=[dict(reason='model response text')],dictionaryCounts={'topic':42})
            public=s.provenance(args.source_dir,manifest)
            self.assertEqual(s.h.replay.sha(args.source_dir/'coverage.json'),public['sourceSnapshotSha256'])
            self.assertEqual(manifest['files'],public['files'])
            self.assertNotIn('decisions',public['advisor']);self.assertNotIn('nodes',public)


if __name__=='__main__':unittest.main()
