import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import named_campaign as n


class NamedCampaignTest(unittest.TestCase):
    def test_admission_continues_until_newly_eligible_metadata_is_exhausted(self):
        self._fixed_point(False)

    def test_repeated_pending_fingerprint_stops_as_incomplete(self):
        self._fixed_point(True)

    def _fixed_point(self,stalled):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            config=dict(sourcePaths=dict(taxonomy=str(root/'taxonomy'),scopes=str(root/'scopes'),ordinary_assets=str(root/'original-assets')),catalogOptions={'all_software':True})
            class Connection:
                def close(self):pass
            pending=dict(complete=False,remainingOperationsSha256='same',remainingEligibleOperations=11,sources={'complete':True},scopeLimit='Fixture scope')
            done=dict(pending,complete=True,remainingEligibleOperations=0)
            args=argparse.Namespace(work_dir=root,cli=root/'cli',goals=root/'goals',restriction_dir=root/'source')
            with patch.object(n.c,'checked_state',side_effect=lambda _: (config,Connection())), \
                 patch.object(n.h,'verify_assets'),patch.object(n,'check',side_effect=[pending,pending if stalled else done]), \
                 patch.object(n.c,'prepare') as prepare,patch.object(n.c,'adopt'),patch.object(n.h,'build') as build, \
                 patch.object(n.c,'report'),patch.object(n.catalog_review,'export'),patch.object(n.catalog_review,'publish',return_value={}) as publish:
                if stalled:
                    with self.assertRaisesRegex(ValueError,'no admission progress'):n.finish(args)
                    self.assertFalse(publish.called)
                    self.assertFalse((root/'campaign.json').exists())
                else:
                    result=n.finish(args);self.assertTrue(result['complete']);self.assertEqual(2,result['passes'])
                    self.assertEqual(root/'original-assets',prepare.call_args.args[0].ordinary_assets)
                    self.assertEqual(root.resolve()/'adoption/baseline.jsonl',publish.call_args.args[0].parent_inventory)
                    self.assertEqual(2,len(publish.call_args.args[0].ledger))
                self.assertEqual(1,build.call_count)

    def test_page_categories_do_not_remove_medical_or_ordinary_homonyms(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records = [dict(surface=s, topics=['restricted.sex', 'restricted.vulgar'],
                proofs=[dict(url='https://en.wiktionary.org/wiki/'+s, license='CC-BY-SA-4.0')])
                for s in ['AIDS', 'banana', 'unambiguous slang', 'missing evidence']]
            rows = [dict(word='AIDS', senses=[dict(tags=['medicine']), dict(tags=['vulgar'])]),
                dict(word='banana', senses=[dict(tags=[]), dict(tags=['vulgar'])]),
                dict(word='unambiguous slang', senses=[dict(tags=['slang', 'vulgar'])])]
            n.h.write_lines(root/'sense-review.jsonl', rows)
            with patch.object(n.coverage_sources, 'collect', return_value=(records, {'complete':True}, [])), \
                 patch.object(n.bulk_names, 'verify'):
                excluded, ambiguous = n.sexual_records(root, root/'policy', root)
            self.assertEqual(['unambiguous slang'], [r['surface'] for r in excluded])
            self.assertEqual({'AIDS', 'banana', 'missing evidence'}, {r['surface'] for r in ambiguous})

    def test_incomplete_source_cannot_authorize_distribution_exclusions(self):
        with patch.object(n.coverage_sources, 'collect', return_value=([], {'complete':False}, [])):
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                n.sexual_records(Path('/tmp'), Path('/tmp/policy'), Path('/tmp'))

    def test_completion_rejects_one_pending_operation_even_with_large_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            goals = root/'goals.json'
            n.h.dump(goals, dict(requiredSources=['bulkNames','middleNames','dbpedia','sexualSlang','allActiveSoftware'],
                requiredSpellings={}, preserveMedicalSpellings=[], scopeLimit='Fixture source scope'))
            n.h.write_lines(root/'targets.jsonl', [])
            n.h.write_lines(root/'baseline.jsonl', [])
            class Connection:
                def execute(self, query): return self
                def fetchone(self): return (0,)
                def close(self): pass
            config = dict(sourcePaths={k:str(root) for k in ['bulk_dir','role_dir','dbpedia_dir','dbpedia_policy','pantheon_dir','food_dir','enrichment_dir','sensitive_dir']},
                catalogOptions={'all_software':True}, topics={},sources={'catalogV2':{'wordnetFood':{'complete':True}}})
            args = argparse.Namespace(work_dir=root, assets=root/'assets', cli=root/'cli', goals=goals, restriction_dir=root)
            with patch.object(n.c,'checked_state',return_value=(config, Connection())), \
                 patch.object(n.bulk_names,'verify',return_value={'complete':True}), \
                 patch.object(n.role_sources,'verify',return_value={'complete':True}), \
                 patch.object(n.dbpedia_sources,'verify',return_value={'complete':True}), \
                 patch.object(n.coverage_sources,'verify',return_value={'complete':True}), \
                 patch.object(n.pantheon_sources,'verify',return_value={'complete':True}), \
                 patch.object(n.bulk_food,'verify',return_value={'complete':True}), \
                 patch.object(n.people_enrichment,'verify',return_value={'complete':True}), \
                 patch.object(n.sensitive_sources,'verify',return_value={'complete':True}), \
                 patch.object(n.c,'inventory',return_value=({('word','word')},{})), \
                 patch.object(n.distribution_policy,'for_assets',return_value=set()), \
                 patch.object(n.c,'excluded_inputs',return_value=set()), \
                 patch.object(n.c,'audit',return_value=([],[{'id':'unfinished'}])):
                with self.assertRaisesRegex(ValueError,'Campaign incomplete'):n.check(args)
            self.assertEqual(1, n.h.replay.read_json(root/'completion.json')['remainingEligibleOperations'])

    def test_declared_empty_topic_does_not_complete_after_source_exhaustion(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);goals=root/'goals.json'
            n.h.dump(goals,dict(requiredSources=['bulkNames'],requiredSpellings={},preserveMedicalSpellings=[],
                requireNonemptyTopics=True,scopeLimit='Fixture scope'))
            n.h.write_lines(root/'targets.jsonl',[]);n.h.write_lines(root/'baseline.jsonl',[])
            class Connection:
                def execute(self,_):return self
                def fetchone(self):return (0,)
                def close(self):pass
            config=dict(sourcePaths={k:str(root) for k in ['bulk_dir','role_dir','dbpedia_dir','dbpedia_policy','pantheon_dir','food_dir','enrichment_dir','sensitive_dir']},
                catalogOptions={'all_software':True},topics={'people.sports.archery':{'category':'topic_archery'}},
                sources={'catalogV2':{'wordnetFood':{'complete':True}}})
            args=argparse.Namespace(work_dir=root,assets=root,cli=root/'cli',goals=goals,restriction_dir=root)
            providers=[n.bulk_names,n.role_sources,n.dbpedia_sources,n.coverage_sources,n.pantheon_sources,n.bulk_food,n.people_enrichment,n.sensitive_sources]
            from contextlib import ExitStack
            with ExitStack() as stack:
                stack.enter_context(patch.object(n.c,'checked_state',return_value=(config,Connection())))
                for provider in providers:stack.enter_context(patch.object(provider,'verify',return_value={'complete':True}))
                stack.enter_context(patch.object(n.c,'inventory',return_value=({('other','other')},{})))
                stack.enter_context(patch.object(n.distribution_policy,'for_assets',return_value=set()))
                stack.enter_context(patch.object(n.c,'excluded_inputs',return_value=set()))
                stack.enter_context(patch.object(n.c,'audit',return_value=([],[])))
                with self.assertRaisesRegex(ValueError,'Campaign incomplete'):n.check(args)
            self.assertEqual(['people.sports.archery'],n.h.replay.read_json(root/'completion.json')['emptyRequiredTopics'])
