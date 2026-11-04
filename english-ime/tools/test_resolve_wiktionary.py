import contextlib
import io
import json
import unittest

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_wiktionary as resolver
import resolve_pending as pending_resolver
import test_lexicon_pipeline as fixtures


def entry(word, pos, senses, forms=()):
    return {"word": word, "pos": pos, "senses": senses, "forms": list(forms)}


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.model = pipeline.Lexicon(fixtures.SEED)
        self.pending = []

    def test_explicit_equivalent_spelling_is_separate_from_inflection_and_misspelling(self):
        rows = [
            (1, entry("favourite", "noun", [{"tags": ["countable"]}])),
            (2, entry("favorite", "noun", [{"tags": ["US", "alt-of", "standard"], "alt_of": [{"word": "favourite"}]}])),
            (3, entry("favrite", "noun", [{"tags": ["alt-of", "misspelling"], "alt_of": [{"word": "favourite"}]}])),
            (4, entry("favorites", "noun", [{"tags": ["form-of", "plural"], "form_of": [{"word": "favorite"}]}])),
        ]
        counts = resolver.import_records(self.model, rows, {"favorites"}, self.pending)
        self.assertEqual(1, counts["spellingSensesResolved"])
        self.assertEqual(1, counts["formReferencesResolved"])
        self.assertTrue(self.model.approved["favorite"])
        self.assertTrue(self.model.approved["favorites"])
        self.assertFalse(self.model.approved.get("favrite"))
        self.assertIn(("spelling_variant", "favorite", "favourite"),
                      {(r["relation"], r["source"], r["target"]) for r in self.model.relations})
        self.model.validate()

    def test_ambiguous_root_senses_do_not_pool_inflection_roles_or_invent_bare_forms(self):
        rows = [
            (10, entry("saw", "noun", [{"tags": ["countable"]}])),
            (11, entry("see", "verb", [{}, {}], [{"form": "seeing", "tags": ["present", "participle"]}])),
            (12, entry("saw", "verb", [{"tags": ["form-of", "past"], "form_of": [{"word": "see"}]}])),
            (13, entry("can't", "verb", [{}])),
        ]
        resolver.import_records(self.model, rows, {"saw"}, self.pending)
        new = [(key, values) for key, values in self.model.members.items() if key[0].startswith("wikt-index-") and key[1] == "saw"]
        self.assertEqual(2, len(new))
        self.assertEqual(1, sum("verb_past" in values for _, values in new))
        self.assertFalse(any("verb_base" in values or "verb_past_participle" in values for _, values in new))
        self.assertFalse(self.model.approved.get("can't"))
        self.model.validate()

    def test_explicit_heads_symbols_and_abbreviations_do_not_require_invented_paradigms(self):
        records = [
            (1, dict(entry("rmb", "verb", [{}]), head_templates=[{"name": "head", "args": {"2": "verb"}}])),
            (2, dict(entry("can't", "verb", [{}]), head_templates=[{"name": "head", "args": {"2": "verb form"}}])),
            (3, entry("fm", "symbol", [{}])),
            (4, entry("kk", "phrase", [{}])),
            (5, entry("UEFA", "name", [{"tags": ["abbreviation", "acronym", "alt-of"],
                                         "alt_of": [{"word": "Union of European Football Associations"}]}])),
        ]
        counts = resolver.import_records(self.model, records, set(), self.pending)
        self.assertEqual(1, counts["verbHeadsWithoutInfinitiveClaim"])
        self.assertEqual(1, counts["attestedAbbreviationsWithoutExpansionLemma"])
        self.assertEqual({"verb"}, self.model.members[next(iter(self.model.approved["rmb"])), "rmb"])
        self.assertFalse(self.model.approved.get("can't"))
        self.assertEqual({"symbol"}, self.model.members[next(iter(self.model.approved["fm"])), "fm"])
        self.assertEqual({"phrase"}, self.model.members[next(iter(self.model.approved["kk"])), "kk"])
        self.assertIn("abbreviation", self.model.members[next(iter(self.model.approved["UEFA"])), "UEFA"])
        self.assertTrue(self.pending[-1]["wordAccepted"])
        self.model.validate()

    def test_adverb_subtypes_use_exact_eligible_senses_and_do_not_pool_labels(self):
        records = [
            (1, dict(entry("unknownzz", "adv", [{}]), categories=["English frequency adverbs"])),
            (2, entry("fixturely", "adv", [{"categories": ["English frequency adverbs"]},
                                          {"categories": ["English manner adverbs"]}])),
            (3, entry("oldly", "adv", [{"tags": ["archaic"], "categories": ["English frequency adverbs"]}])),
            (4, entry("betterly", "adv", [{"tags": ["comparative"], "categories": ["English manner adverbs"]}])),
            (5, entry("timeverb", "verb", [{"categories": ["English point-in-time adverbs"]}])),
        ]
        counts = resolver.enrich_adverbs(self.model, records, self.pending)
        self.assertEqual(2, counts["senseAdverbReadings"])
        self.assertFalse(self.model.approved.get("unknownzz"))
        self.assertFalse(self.model.approved.get("oldly"))
        self.assertFalse(self.model.approved.get("betterly"))
        self.assertFalse(self.model.approved.get("timeverb"))
        values = {frozenset(self.model.members[key, "fixturely"]) for key in self.model.approved["fixturely"]}
        self.assertEqual({frozenset({"adverb", "adverb_frequency"}), frozenset({"adverb", "adverb_manner"})}, values)

    def test_prepositional_phrase_abbreviations_do_not_become_prepositions_or_infinitives(self):
        records = [(1, entry("tbh", "prep_phrase", [{"tags": ["abbreviation", "alt-of", "initialism"],
                     "alt_of": [{"word": "to be honest"}]}]))]
        resolver.import_records(self.model, records, {"tbh"}, self.pending)
        key = next(iter(self.model.approved["tbh"]))
        self.assertEqual({"phrase", "abbreviation"}, self.model.members[key, "tbh"])
        self.assertEqual("abbreviation_expansion_reference_pending", self.pending[-1]["reason"])
        self.assertTrue(self.pending[-1]["wordAccepted"])
        self.model.validate()

    def test_case_correction_requires_no_exact_entry_and_one_canonical_spelling(self):
        rows = [(1, entry("London", "name", [{"categories": ["en:Cities in England"]}])),
                (2, entry("May", "name", [{}])), (3, entry("may", "noun", [{}])),
                (4, entry("Tim", "name", [{}])), (5, entry("TIM", "abbrev", [{}])),
                (6, entry("react", "verb", [{}], [{"form": "reacting", "tags": ["present", "participle"]}]))]
        resolver.import_records(self.model, rows, set(), self.pending)
        inventory = [{"id": str(i), "reading": word.lower(), "surface": word, "cost": 700}
                     for i, word in enumerate(["london", "may", "tim", "React"])]
        corrections = resolver.case_corrections(self.model, inventory, rows)
        self.assertEqual(["london"], [r["source"] for r in corrections])
        self.assertEqual("London", corrections[0]["target"])
        london_id = next(iter(self.model.approved["London"]))
        self.assertIn("name_place", self.model.members[london_id, "London"])
        self.assertFalse(any("noun_proper" in values for (key, surface), values in self.model.members.items() if surface == "may"))

    def test_correction_ledger_preserves_raw_rows_and_verifies_effective_membership(self):
        fixture = fixtures.PipelineTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original = {"id": "manual:3", "reading": "london", "surface": "london", "cost": 811}
        fixture.rows.append(original)
        pipeline.jsonl(fixture.inventory, fixture.rows)
        fixture.inventory_sha256 = pipeline.digest(fixture.inventory)
        fixture.build()
        model, rows, sources, notices, pending = extension.load_base(fixture.args.out, fixtures.SEED)
        records = [(1, entry("London", "name", [{}]))]
        resolver.import_records(model, records, set(), pending)
        corrections = resolver.case_corrections(model, rows, records)
        output = fixture.root / "corrected"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.publish(model, rows, fixture.inventory, output, sources, notices, pending,
                             allow_input_spellings=True, corrections=corrections)
        states = [json.loads(line) for line in (output / "status.jsonl").read_text().splitlines()]
        self.assertEqual(original, {key: states[-1][key] for key in original})
        self.assertEqual("London", states[-1]["effective_surface"])
        self.assertEqual("include", states[-1]["decision"])
        self.assertEqual(1, pipeline.verify(output)["surfaceCorrections"])
        with self.assertRaisesRegex(ValueError, "Invalid or duplicate"):
            pipeline.correction_targets(corrections + corrections, rows, model)

    def test_multiple_verified_case_candidates_preserve_ambiguity_and_all_targets(self):
        fixture = fixtures.PipelineTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original = {"id": "manual:3", "reading": "tim", "surface": "tim", "cost": 811}
        fixture.rows.append(original)
        pipeline.jsonl(fixture.inventory, fixture.rows)
        fixture.inventory_sha256 = pipeline.digest(fixture.inventory)
        fixture.build()
        model, rows, sources, notices, pending = extension.load_base(fixture.args.out, fixtures.SEED)
        records = [(1, entry("Tim", "name", [{}])), (2, entry("TIM", "abbrev", [{}]))]
        resolver.import_records(model, records, set(), pending)
        corrections = pending_resolver.cases(model, rows, set())
        self.assertEqual({"Tim", "TIM"}, {r["target"] for r in corrections})
        self.assertEqual({"case_candidates"}, {r["relation"] for r in corrections})
        self.assertEqual([], pending_resolver.cases(model, rows, {"tim"}))
        output = fixture.root / "case-candidates"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.publish(model, rows, fixture.inventory, output, sources, notices, pending,
                             allow_input_spellings=True, corrections=corrections)
        state = json.loads((output / "status.jsonl").read_text().splitlines()[-1])
        self.assertEqual(["TIM", "Tim"], state["effective_surfaces"])
        self.assertEqual("case_candidates_not_disambiguated", state["interpretation"])
        self.assertEqual(original, {key: state[key] for key in original})
        self.assertEqual(1, pipeline.verify(output)["caseCandidateRows"])
        with self.assertRaisesRegex(ValueError, "Invalid or duplicate"):
            pipeline.correction_targets(corrections[:1], rows, model)
        with self.assertRaisesRegex(ValueError, "Invalid or duplicate"):
            pipeline.correction_targets([dict(r, relation="case_correction") for r in corrections], rows, model)

    def test_exclusion_requires_explicit_labels_on_every_sense_and_no_eligible_exact_reading(self):
        originals = [{"id": str(i), "reading": w, "surface": w, "cost": 700}
                     for i, w in enumerate(["oldzz", "typozz", "mixedzz", "emptyzz", "missingzz", "modernzz", "oldnamedzz"])]
        records = [(1, entry("oldzz", "noun", [{"tags": ["archaic"]}, {"tags": ["obsolete"]}])),
                   (2, entry("typozz", "noun", [{"tags": ["misspelling"]}])),
                   (3, entry("mixedzz", "noun", [{"tags": ["vulgar"]}, {}])),
                   (4, entry("emptyzz", "noun", [])),
                   (5, entry("modernzz", "noun", [{"tags": ["obsolete"]}])),
                   (6, entry("oldnamedzz", "noun", [{"tags": ["obsolete"]}]))]
        self.model.add("fixture-modern", "modernzz", "modernzz", {"noun"},
                       {"source": "esdb", "url": "https://example.org/", "approved": True}, approved=True)
        self.model.add("fixture-name", "Oldnamedzz", "Oldnamedzz", {"noun_proper", "noun"},
                       {"source": "esdb", "url": "https://example.org/", "approved": True}, approved=True)
        reviews = pending_resolver.exclusions(self.model, originals, records, set(), self.pending)
        self.assertEqual({"oldzz": "restricted", "typozz": "malformed"}, {r["surface"]: r["reason"] for r in reviews})
        self.assertEqual(3, len(self.pending))
        self.assertIn("senseTags", self.pending[0]["evidence"]["entries"][0])
        self.assertEqual("restricted_surface_has_eligible_case_alternative", self.pending[-1]["reason"])

    def test_machine_exclusions_reopen_after_new_evidence_without_removing_changed_or_human_reviews(self):
        self.model.add("fixture-ost", "OST", "OST", {"abbreviation"},
                       {"source": "wiktionary", "url": "https://en.wiktionary.org/wiki/OST", "approved": True}, approved=True)
        rows = [{"id": str(i), "reading": "ost", "surface": "ost", "cost": "700", "decision": "exclude",
                 "lexeme_ids": "-", "reason": "restricted", "evidence": url}
                for i, url in enumerate(["https://en.wiktionary.org/wiki/ost", "https://example.org/human", "https://example.org/changed"])]
        events = [{"reason": "source_label_exclusion", "sourceId": str(i), "surface": "ost", "decisionReason": "restricted",
                   "evidence": {"url": "https://en.wiktionary.org/wiki/ost"}} for i in [0, 2]]
        kept, reopened = pending_resolver.revalidate_machine_reviews(self.model, rows, events)
        self.assertEqual({"0"}, reopened)
        self.assertEqual(["1", "2"], [row["id"] for row in kept])
        self.assertEqual(["OST"], events[-1]["eligibleSurfaces"])

    def test_machine_typo_exclusion_reopens_only_for_valid_independently_approved_spelling(self):
        proof={'source':'curated_seed','url':'https://example.org/abbreviation'}
        self.model.add('fixture-abbreviation','FIX.','FIX.',{'abbreviation'},proof,approved=True)
        row=dict(id='fixture:1',surface='fix',reading='fix',cost='700',decision='exclude',lexeme_ids='-',reason='malformed',evidence='https://example.org/typos')
        event=dict(reason='source_label_exclusion',sourceId=row['id'],surface='fix',decisionReason='malformed',evidence={'url':row['evidence']})
        correction=dict(id=row['id'],source='fix',target='FIX.',relation='input_spelling_correction',evidence=proof['url'])
        kept,reopened=pending_resolver.revalidate_machine_reviews(self.model,[row],[event])
        self.assertEqual([row],kept);self.assertFalse(reopened)
        kept,reopened=pending_resolver.revalidate_machine_reviews(self.model,[row],[event],[correction])
        self.assertEqual([],kept);self.assertEqual({row['id']},reopened)
        kept,reopened=pending_resolver.revalidate_machine_reviews(self.model,[dict(row,evidence='https://example.org/human')],[event],[correction])
        self.assertEqual(1,len(kept));self.assertFalse(reopened)
        with self.assertRaises(ValueError):pending_resolver.revalidate_machine_reviews(self.model,[row],[event],[dict(correction,target='DIFFERENT')])

    def test_explicitly_disqualified_readings_do_not_remove_verified_names(self):
        records = [(1, entry('taylor', 'noun', [{'tags': ['obsolete']}])),
                   (2, entry('Taylor', 'name', [{}])),
                   (3, entry('taylorr', 'noun', [{'tags': ['misspelling']} , {'tags': ['archaic']}])),
                   (4, entry('unresolvedzz', 'noun', [{'tags': ['obsolete', 'no-gloss']}])),
                   (5, entry('modernzz', 'noun', [{'tags': ['obsolete']}, {}])),
                   (6, entry('emptyzz', 'noun', []))]
        resolver.import_records(self.model, records, set(), self.pending)
        disqualified = pending_resolver.ineligible_exact_words(records)
        self.assertEqual({'taylor', 'taylorr'}, disqualified)
        rows = [{'id': 'raw:1', 'reading': 'taylor', 'surface': 'taylor', 'cost': 456}]
        corrections = pending_resolver.cases(self.model, rows, {r['word'] for _, r in records}, disqualified)
        self.assertEqual(['Taylor'], [r['target'] for r in corrections])
        self.assertEqual([], pending_resolver.exclusions(self.model, rows, records, {'raw:1'}, self.pending))
        typo = [{'id': 'raw:2', 'reading': 'taylorr', 'surface': 'taylorr', 'cost': 567}]
        reviews = pending_resolver.exclusions(self.model, typo, records, set(), self.pending)
        self.assertEqual('ineligible_senses', reviews[0]['reason'])
        pipeline.validate_decision(reviews[0], self.model)

    def test_spelling_reference_can_use_an_attested_abbreviation_role(self):
        records = [(1, entry('JK', 'phrase', [{'tags': ['abbreviation', 'initialism', 'alt-of'],
                     'alt_of': [{'word': 'just kidding'}]}])),
                   (2, entry('jk', 'phrase', [{'tags': ['alt-of'], 'alt_of': [{'word': 'JK'}]}])),
                   (3, entry('æ', 'character', [{'tags': ['letter']} ])),
                   (4, entry('ae', 'symbol', [{'tags': ['alt-of'], 'alt_of': [{'word': 'æ'}]}]))]
        resolver.import_records(self.model, records, {'jk', 'ae'}, self.pending)
        self.assertTrue(self.model.approved['jk'])
        self.assertTrue(self.model.approved['ae'])
        self.assertEqual({'phrase'}, self.model.members[next(iter(self.model.approved['jk'])), 'jk'])
        self.assertEqual({'symbol'}, self.model.members[next(iter(self.model.approved['ae'])), 'ae'])
        self.model.validate()


if __name__ == "__main__":
    unittest.main()
