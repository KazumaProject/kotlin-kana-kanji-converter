import copy
import json
from pathlib import Path
import tempfile
import unittest

import world_sources as w
import catalog_review as r


class WorldSourcesTest(unittest.TestCase):
    def entity(self):
        return dict(id='Q42', labels={'mul': {'value': 'Douglas Adams'}}, aliases={'en': [{'value': 'Douglas Noel Adams'}]},
            sitelinks={'enwiki': {'title': 'Douglas Adams'}}, claims={'P31': [dict(rank='normal', mainsnak={'datavalue': {'value': {'id': 'Q5'}}})]})

    def test_default_language_and_explicit_alias_are_attested_without_generating_names(self):
        entity = self.entity()
        spec = dict(surface='Douglas Adams', kind='person', title='Douglas Adams')
        self.assertEqual([('Douglas Adams', 'label:mul')], w.wikidata_attestation(spec, entity))
        self.assertEqual([('Douglas Noel Adams', 'alias:en')], w.wikidata_attestation(dict(spec, surface='Douglas Noel Adams'), entity))
        self.assertEqual([], w.wikidata_attestation(dict(spec, surface='Adams Douglas'), entity))
        self.assertEqual([], w.wikidata_attestation(dict(spec, surface='douglas adams'), entity))

    def test_human_identity_and_article_binding_are_required(self):
        spec = dict(surface='Douglas Adams', kind='person', title='Douglas Adams')
        entity = self.entity()
        self.assertFalse(w.wikidata_attestation(dict(spec, title='Another person'), entity))
        self.assertFalse(w.wikidata_attestation(dict(spec, kind='product'), entity))
        entity['claims']['P31'] = []
        self.assertFalse(w.wikidata_attestation(spec, entity))

    def test_english_article_title_can_attest_a_name_without_reordering_it(self):
        entity = self.entity()
        entity['labels'] = {'en': {'value': 'Adams Douglas'}}
        spec = dict(surface='Douglas Adams', kind='person', title='Douglas Adams')
        self.assertEqual([('Douglas Adams', 'sitelink:enwiki')], w.wikidata_attestation(spec, entity))
        entity['sitelinks']['enwiki']['title'] = 'Douglas Adams (writer)'
        self.assertFalse(w.wikidata_attestation(dict(spec, title='Douglas Adams (writer)'), entity))

    def test_disambiguation_entities_are_never_dictionary_evidence(self):
        entity = self.entity()
        entity['claims']['P31'][0]['mainsnak']['datavalue']['value']['id'] = 'Q4167410'
        self.assertFalse(w.wikidata_attestation(dict(surface='Douglas Adams', kind='lexical', title='Douglas Adams'), entity))

    def test_english_section_is_not_inferred_from_foreign_entries_or_quotations(self):
        self.assertIsNone(w.english_section('==French==\nEnglish is mentioned here\n===Noun===\n'))
        text = '==English==\n===Noun===\nword\n==Spanish==\nother'
        self.assertIn('word', w.english_section(text))
        self.assertNotIn('other', w.english_section(text))

    def test_obo_reader_does_not_merge_terms_or_treat_typedefs_as_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'terms.obo'
            p.write_text('[Term]\nid: CHEBI:1\nname: glucose\nsubset: 3_STAR\n\n[Term]\nid: CHEBI:2\nname: obsolete\nis_obsolete: true\n[Typedef]\nid: relation\n')
            terms = list(w.obo_terms(p))
            self.assertEqual(['glucose', 'obsolete'], [x['name'][0] for x in terms])

    def test_proof_matching_never_changes_proper_name_case_or_uses_unrequested_sources(self):
        index = {'name': [dict(source='wikidata', kind='person')], 'term': [dict(source='qudt')]}
        self.assertFalse(w.matching(index, 'Name', 'person', ['wikidata']))
        self.assertFalse(w.matching(index, 'term', 'lexical', ['wiktionary']))
        self.assertEqual([dict(source='qudt')], w.matching(index, 'term', 'lexical', ['qudt']))
        evidence = w.matching(index, 'term', 'lexical', ['qudt'])
        evidence[0]['id'] = 'assigned-by-catalog'
        self.assertNotIn('id', index['term'][0])

    def test_reader_counts_unique_spellings_separately_from_overlapping_categories(self):
        topics = {'a': {'label': 'A'}, 'b': {'label': 'B'}}
        rows = [dict(surface='new', change='new_spelling', topics='a,b'),
                dict(surface='new', change='new_spelling', topics='a'),
                dict(surface='known', change='metadata_only', topics='b')]
        result = r.summary(rows, topics)
        self.assertEqual((1, 1, 2), (result['newSpellings'], result['annotatedSpellings'], result['totalSpellings']))
        self.assertEqual(1, result['categories']['a']['newSpellings'])
        text = r.markdown(rows, topics, result)
        self.assertIn('<details>', text)
        self.assertIn('`known`', text)

    def test_public_review_counts_only_topics_actually_assigned_by_the_operation(self):
        topics = {'existing': {'category': 'topic_existing', 'label': 'Existing'}, 'added': {'category': 'topic_added', 'label': 'Added'}}
        target = dict(topics=['existing', 'added'])
        entry = dict(categories='domain_science,topic_added')
        assigned = r.assigned_topics(target, entry, topics)
        self.assertEqual('added', assigned)
        row = dict(surface='word', change='metadata_only', topics=assigned)
        counts = r.summary([row], topics)
        self.assertNotIn('existing', counts['categories'])
        self.assertNotIn('Existing /', r.markdown([row], topics, counts))
        row['topics'] = r.assigned_topics(target, dict(categories='domain_science'), topics)
        counts = r.summary([row], topics)
        self.assertEqual({}, counts['categories'])
        self.assertEqual(1, counts['annotatedSpellings'])
        self.assertIn('`word`', r.markdown([row], topics, counts))

    def test_frozen_adapters_select_exact_curated_evidence_and_reject_source_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            scopes = p / 'scopes.json'
            scopes.write_text(json.dumps(dict(worldSources=1, entityTargets='entities.json', scopes=[
                dict(kind='lexical', sources=['wiktionary', 'qudt', 'chebi'], terms=['torque', 'glucose', 'related only', 'old name']),
                dict(kind='person', sources=['wikidata'], terms=['Douglas Adams'])])))
            (p / 'entities.json').write_text(json.dumps(dict(schemaVersion=1, entities=[
                dict(surface='Douglas Adams', title='Douglas Adams', kind='person', reason='Fixture scope')])))
            _, words, pins = w.specifications(scopes)
            entity = self.entity(); entity['lastrevid'] = 42
            payloads = {'wikidata': dict(entities={'Q42': entity}), 'wiktionary': dict(query=dict(pages={
                '1': dict(ns=0, title='torque', revisions=[dict(revid=13, slots={'main': {'*': '==English==\n===Noun===\n{{en-noun|-}}\n'}})]),
                '2': dict(ns=0, title='related only', revisions=[dict(revid=14, slots={'main': {'*': '==French==\n'}})])}))}
            files, batches = {}, []
            for provider, titles in [('wikidata', ['Douglas Adams']), ('wiktionary', words)]:
                url = w.batch_url(provider, titles)
                name = provider + '-' + w.hashlib.sha256(url.encode()).hexdigest()[:24] + '.json'
                (p / name).write_text(json.dumps(payloads[provider]))
                files[name] = dict(url=url, sha256=w.h.replay.sha(p / name))
                batches.append(dict(provider=provider, file=name, titles=titles))
            for _, (name, url, notice, notice_url, _) in w.STATIC.items():
                for f, u in [(name, url), (notice, notice_url)]:
                    (p / f).write_text('Fixture notice')
                    files[f] = dict(url=u, sha256=w.h.replay.sha(p / f))
            (p / 'qudt.ttl').write_text('@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
                '<http://qudt.org/vocab/quantitykind/Torque> rdfs:label "Torque"@en .')
            (p / 'chebi.obo').write_text('[Term]\nid: CHEBI:1\nname: glucose\nsubset: 3_STAR\n'
                'synonym: "related only" RELATED []\n[Term]\nid: CHEBI:2\nname: old name\nsubset: 3_STAR\nis_obsolete: true\n')
            for name in ['qudt.ttl', 'chebi.obo']:
                files[name]['sha256'] = w.h.replay.sha(p / name)
            for name, url in w.NOTICES.items():
                (p / name).write_text('Fixture notice'); files[name] = dict(url=url, sha256=w.h.replay.sha(p / name))
            (p / 'WORLD-SOURCE-ATTRIBUTION.txt').write_text('Fixture attribution')
            files['WORLD-SOURCE-ATTRIBUTION.txt'] = dict(sha256=w.h.replay.sha(p / 'WORLD-SOURCE-ATTRIBUTION.txt'))
            w.h.dump(p / 'world-sources.json', dict(schemaVersion=1, pins=pins, files=files, batches=batches))
            index, _ = w.indices(p, scopes)
            self.assertEqual({'wiktionary', 'qudt'}, {r['source'] for r in index['torque']})
            self.assertEqual('noun', next(r['headRole'] for r in index['torque'] if r['source'] == 'wiktionary'))
            self.assertEqual('chebi', index['glucose'][0]['source'])
            self.assertNotIn('old name', index)
            self.assertNotIn('related only', index)
            self.assertEqual('Q42', index['Douglas Adams'][0]['entity'])
            (p / 'WORLD-CC0-1.0.txt').write_text('Changed notice')
            with self.assertRaisesRegex(ValueError, 'Changed world source/notice'):
                w.verify(p, scopes)

    def test_review_list_requires_real_candidate_and_exact_lexical_topic_binding(self):
        topic = {'a': {'category': 'topic_a'}}
        row = dict(target_id='one', surface='word', kind='lexical', topics='a', change='metadata_only', lexeme_id='form',
            lemma='word', evidence='https://example.org/source', licenses='CC0-1.0')
        form = dict(lexeme_id='form', lemma='word', memberships={'topic_a'})
        r.verify_rows([row], topic, {('word', 'word')}, {'word': [form]})
        with self.assertRaisesRegex(ValueError, 'absent from binary'):
            r.verify_rows([row], topic, set(), {'word': [form]})
        with self.assertRaisesRegex(ValueError, 'form/topic absent'):
            r.verify_rows([dict(row, lexeme_id='different')], topic, {('word', 'word')}, {'word': [form]})


if __name__ == '__main__':
    unittest.main()
