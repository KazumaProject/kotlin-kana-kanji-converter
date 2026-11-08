import bz2
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import bulk_food as food
import pantheon_sources as pantheon
import people_enrichment as enrichment
import sensitive_sources as sensitive
import vocabulary_sources as lexical
import catalog_review as review
import coverage_sources as coverage


class NamedSourcesTest(unittest.TestCase):
    def test_all_people_lookup_preserves_sports_batches_and_includes_actor_crossovers(self):
        sports=[dict(entity='wikidata:Q'+str(i),topics=['people.sports']) for i in range(1,6)]
        actors=[dict(entity='wikidata:Q'+str(i),topics=['people.actors']) for i in range(6,9)]
        old=enrichment.batches(sports,{'batchSize':3})
        expanded=enrichment.batches(sports+actors,{'batchSize':3})
        self.assertEqual(old,expanded[:len(old)])
        self.assertEqual([0,3,5],[start for start,_ in expanded])
        self.assertEqual(['Q'+str(i) for i in range(1,9)],[qid for _,batch in expanded for qid in batch])

    def test_prior_ordinary_words_and_language_identifiers_do_not_become_victim_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'grammar').mkdir()
            (root/'grammar/memberships.tsv').write_text('category\tlexeme_id\tsurface\n'
                'noun\tword\tpython\nidentifier_computer_language\tlang\tPython\n'
                'noun\tperson\tVictim Name\nnoun_proper\tperson\tVictim Name\nname_person\tperson\tVictim Name\n')
            self.assertEqual({'python','Python'},sensitive.ordinary_spellings(root))

    def test_restriction_walk_explicitly_allows_english_categories_but_not_other_languages(self):
        rule=coverage.policy(coverage.h.REPO/'english-ime/data/catalog/distribution-sources-policy.json')
        self.assertTrue(coverage.english_category('Category:English vulgarities',rule))
        self.assertFalse(coverage.english_category('Category:French vulgarities',rule))
        self.assertFalse(coverage.english_category('Category:English vulgarities',{'categoryPrefixes':['Category:en:']}))

    def test_broad_skater_and_athlete_do_not_imply_board_sports_or_olympics(self):
        rule=json.loads(enrichment.POLICY.read_text())
        row=dict(types={'value':'http://dbpedia.org/ontology/Skater|http://dbpedia.org/ontology/Athlete'},categories={'value':''})
        topics=enrichment.classified_topics(row,rule)
        self.assertNotIn('people.sports.skateboarding',topics)
        self.assertNotIn('people.sports.olympics',topics)
        row['categories']['value']='http://dbpedia.org/resource/Category:Olympic_commentators_for_Britain'
        self.assertNotIn('people.sports.olympics',enrichment.classified_topics(row,rule))
        row['categories']['value']='http://dbpedia.org/resource/Category:Athletes_at_the_2012_Summer_Olympics|http://dbpedia.org/resource/Category:Jamaican_male_sprinters'
        self.assertTrue({'people.sports.olympics','people.sports.athletics'}<=set(enrichment.classified_topics(row,rule)))
        row['categories']['value']='http://dbpedia.org/resource/Category:Olympic_archers_for_South_Korea|http://dbpedia.org/resource/Category:Japanese_surfers'
        self.assertTrue({'people.sports.archery','people.sports.surfing'}<=set(enrichment.classified_topics(row,rule)))

    def test_food_capture_reaches_late_entry_and_preserves_explicit_plural_lemma(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'food.gz'
            records=[dict(word='not food',lang_code='en',pos='noun'),
                dict(word='ramens',lang_code='en',pos='noun',senses=[dict(categories=['en:Dishes'],tags=['plural'],form_of=[{'word':'ramen'}])])]
            policy=root/'policy.json';food.h.dump(policy,dict(categoryPatterns={'daily.dishes':['^en:Dishes$']}))
            archive.write_bytes(gzip.compress(('\n'.join(json.dumps(r) for r in records)+'\n').encode()))
            value=food.capture(archive,root/'out',policy)
            selected,_,_=food.collect(root/'out',policy)
            self.assertEqual(2,value['counts']['allRecords'])
            self.assertEqual('ramen',selected[0]['attestedSourceEntry']['lemma'])
            self.assertIn('noun_count_plural',selected[0]['attestedSourceEntry']['categories'])
            archive.write_bytes(archive.read_bytes()[:-5])
            with self.assertRaises((EOFError,OSError)):food.capture(archive,root/'broken',policy)
            self.assertFalse((root/'broken/food.json').exists())

    def test_complete_wordnet_food_graph_includes_descendants_without_inventing_forms(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/'wordnet.tar.gz'
            roots=['dish','baked_goods','confectionery','sauce','condiment','beverage']
            lines=[f'{i:08} 13 n 01 {word} 0 000 | root' for i,word in enumerate(roots,1)]
            lines+=['00000007 13 n 01 ratatouille 0 001 @ 00000001 n 0000 | child',
                '00000008 13 n 01 espresso 0 001 @ 00000006 n 0000 | child',
                '00000009 03 n 01 chair 0 000 | non-food']
            with tarfile.open(archive,'w:gz') as stream:
                for name,body in [('dict/lexnames',b'13 noun.food 1\n'),('dict/data.noun',('\n'.join(lines)+'\n').encode())]:
                    info=tarfile.TarInfo(name);info.size=len(body);stream.addfile(info,io.BytesIO(body))
            rows,manifest=food.wordnet_records(archive,food.h.replay.sha(archive))
            topics={r['surface']:r['topics'] for r in rows}
            self.assertIn('daily.dishes',topics['ratatouille']);self.assertIn('daily.beverages',topics['espresso'])
            self.assertNotIn('chair',topics);self.assertNotIn('espressos',topics)
            self.assertEqual(9,manifest['nounSynsetsScanned'])
            with self.assertRaisesRegex(ValueError,'Changed WordNet'):food.wordnet_records(archive,'0'*64)

    def test_pantheon_full_stream_rejects_duplicate_identity_and_truncation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/pantheon.ARCHIVE
            body='name,wd_id,wp_id,occupation,birthyear,is_group\nAlice,Q1,1,ACTOR,1980,FALSE\nBob,Q2,2,ATHLETE,1900,FALSE\n'
            archive.write_bytes(bz2.compress(body.encode()));self.assertEqual(2,len(list(pantheon.rows(root))))
            archive.write_bytes(bz2.compress((body+'Again,Q1,3,ACTOR,1980,FALSE\n').encode()))
            with self.assertRaisesRegex(ValueError,'duplicate'):list(pantheon.rows(root))
            archive.write_bytes(bz2.compress(body.encode())[:-8])
            with self.assertRaises((EOFError,OSError)):list(pantheon.rows(root))

    def test_sensitive_decision_mode_can_change_without_mutating_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);policy=root/'policy.json'
            rule=dict(schemaVersion=1,pageSize=500,selectors=[],victimMode='all_positive_victims',
                availableVictimModes=['all_positive_victims','case_context_only'],independentPublicRolesExclude=['INSPIRATION'])
            sensitive.h.dump(policy,rule);sensitive.h.dump(root/'sensitive.json',dict(schemaVersion=1,complete=True,
                policy=rule,policySha256=sensitive.h.replay.sha(policy),pages=[]))
            original=(root/'sensitive.json').read_bytes()
            rule['victimMode']='case_context_only';sensitive.h.dump(policy,rule)
            sensitive.verify(root,policy)
            self.assertEqual(original,(root/'sensitive.json').read_bytes())
            rule['pageSize']=100;sensitive.h.dump(policy,rule)
            with self.assertRaisesRegex(ValueError,'Changed'):sensitive.verify(root,policy)

    def test_case_context_retains_public_careers_but_not_victim_only_historical_roles(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);policy=root/'policy.json'
            rule=dict(victimMode='case_context_only',independentPublicRolesExclude=['INSPIRATION'],
                selectors=[dict(id='people',provider='wikidata',reason='victim-person'),
                    dict(id='cases',provider='wikidata',reason='victim-related-subject')])
            sensitive.h.dump(policy,rule)
            people=[dict(entity='wikidata:Q1',surface='Public Artist',kind='person',topics=['people.arts'],proofs=[{'occupation':'ARTIST'}]),
                dict(entity='wikidata:Q2',surface='Victim Only',kind='person',topics=['people.history'],proofs=[{'occupation':'INSPIRATION'}])]
            records=[dict(item={'value':'http://www.wikidata.org/entity/Q'+str(i)},label={'value':s}) for i,s in
                [(1,'Public Artist'),(2,'Victim Only'),(3,'Public Actor'),(4,'Victim Case')]]
            sensitive.h.dump(root/'people.json',dict(results={'bindings':records[:3]}))
            sensitive.h.dump(root/'cases.json',dict(results={'bindings':records[3:]}))
            manifest=dict(policySha256='capture',pages=[dict(selector=s,file=s+'.json',url='https://example.org/'+s,sha256=sensitive.h.replay.sha(root/(s+'.json'))) for s in ['people','cases']])
            sensitive.h.dump(root/'sensitive.json',manifest)
            with patch.object(sensitive,'verify',return_value=manifest),patch.object(sensitive.pantheon_sources,'collect',return_value=(people,{},[],[])):
                blocked,public,retained=sensitive.collect(root,root,policy,
                    public_people=[dict(surface='Public Actor',kind='person',topics=['people.actors'])],public_people_snapshot='pinned')
            self.assertEqual({'Victim Only','Victim Case'},{r['surface'] for r in blocked})
            self.assertEqual({'Public Artist','Public Actor'},{r['surface'] for r in retained})
            self.assertEqual('pinned',public['independentNameSources'])

    def test_byte_bounded_shards_preserve_every_row_and_reject_tampered_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);rows=[{k:('word'+str(i) if k=='surface' else '-') for k in review.FIELDS} for i in range(30)]
            files=lexical.write_table_shards(root,'part',review.FIELDS,rows,max_bytes=250)
            self.assertGreater(len(files),1);self.assertTrue(all((root/n).stat().st_size<=250 for n in files))
            review.h.dump(root/'index.json',dict(schemaVersion=1,files=files));self.assertEqual(rows,review.read(root))
            name=next(iter(files));(root/name).write_text((root/name).read_text()+'changed\n')
            with self.assertRaisesRegex(ValueError,'Changed'):review.read(root)
