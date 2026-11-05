from argparse import Namespace
import contextlib
import gzip
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import lexicon_pipeline as pipeline


SEED = Path(__file__).resolve().parents[1] / "data" / "grammar"


class PipelineTests(unittest.TestCase):
    def test_terminal_bang_transcription_keeps_letters_and_rejects_other_new_marks(self):
        self.assertEqual('fixture',pipeline.keyboard_reading('Fixture!'))
        self.assertEqual('callin',pipeline.keyboard_reading("call-in'"))
        for spelling in ['Fix!ture','Fixture!!','C++','Fixture1!','Fixture !','!Fixture']:
            self.assertIsNone(pipeline.keyboard_reading(spelling))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.wordnet = self.root / "WordNet-3.0.tar.gz"
        files = {"LICENSE": "WordNet Release 3.0\nfixture\n"}
        for suffix, words in {
            "noun": ["dog", "man", "saw"],
            "verb": ["eat", "make", "saw", "see"],
            "adj": ["good"], "adv": ["well"],
        }.items():
            files["dict/index." + suffix] = "  comment\n" + "".join(word + " fixture\n" for word in words)
            files["dict/" + suffix + ".exc"] = {"noun": "men man\n", "verb": "ate eat\nsaw see\n"}.get(suffix, "")
        with tarfile.open(self.wordnet, "w:gz") as archive:
            for name, text in files.items():
                data = text.encode()
                info = tarfile.TarInfo("WordNet-3.0/" + name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        self.inventory = self.root / "inventory.jsonl"
        self.rows = [
            {"id": "tsv:" + str(i + 2), "reading": surface, "surface": surface, "cost": 700 + i}
            for i, surface in enumerate(["make", "eat", "ate", "saw", "dog", "men", "take", "unknownzz", "dogs"])
        ]
        self.rows.append(dict(self.rows[0], id="manual:1", cost=900))
        # A known word alone is not evidence that an arbitrary reading maps to it.
        self.rows.append({"id": "manual:2", "reading": "wrongreading", "surface": "take", "cost": 1000})
        pipeline.jsonl(self.inventory, self.rows)
        self.inventory_sha256 = pipeline.digest(self.inventory)
        self.source = self.root / "source.zip"
        with ZipFile(self.source, "w") as archive:
            archive.writestr(pipeline.SOURCE_TSV, "input_word\toutput_word\tpos_tag\tscore\n" + "".join(
                f"{row['reading']}\t{row['surface']}\tX\t{row['cost']}\n" for row in self.rows[:-2]))
            archive.writestr("NOTICE.md", "fixture attribution\n")
            archive.writestr("LICENSES/CC-BY-SA-4.0.txt", "fixture license\n")
        self.args = Namespace(inventory=self.inventory, source=self.source, wordnet=self.wordnet, seed=SEED,
                              out=self.root / "output", wiktextract=None, wiktextract_sha256=None,
                              wiktionary_dump_date=None, extractor_revision=None, reviewed_decisions=None)

    def build(self):
        with patch.object(pipeline, "WORDNET_SHA256", pipeline.digest(self.wordnet)), \
                patch.object(pipeline, "SOURCE_SHA256", pipeline.digest(self.source)), \
                patch.object(pipeline, "INVENTORY_SHA256", self.inventory_sha256), \
                patch.object(pipeline, "MANUAL_ROW_COUNT", sum(row["id"].startswith("manual:") for row in self.rows)), \
                contextlib.redirect_stdout(io.StringIO()):
            return pipeline.build(self.args)

    def read(self, name):
        return [json.loads(line) for line in (self.args.out / name).read_text().splitlines()]

    def test_materializes_roles_preserves_every_row_and_keeps_review_pending(self):
        summary = self.build()
        states = self.read("status.jsonl")
        self.assertEqual(self.rows, [{key: state[key] for key in self.rows[0]} for state in states])
        self.assertEqual(len(self.rows), summary["inputRows"])
        self.assertEqual(2, summary["unresolvedRows"])
        self.assertEqual(7, summary["classifiedInputSurfaces"])
        self.assertEqual(2, summary["includedRows"])  # saw and take; no guessed mapping
        self.assertEqual("mapping_review_required", states[-1]["reason"])
        self.assertEqual("pending", states[0]["decision"])
        self.assertFalse(summary["complete"])
        model = pipeline.Lexicon(self.args.out / "grammar")
        make = [key for key, value in model.forms.items() if value["lemma"] == "make"]
        self.assertEqual(1, len(make))
        self.assertTrue({"verb", "verb_base"} <= model.members[make[0]])
        ate = [key for key in model.forms if key[1] == "ate"]
        self.assertEqual(1, len(ate))
        self.assertEqual("eat", model.forms[ate[0]]["lemma"])
        self.assertEqual({"verb"}, model.members[ate[0]])  # .exc does not specify tense
        saw = {key[0]: value["lemma"] for key, value in model.forms.items() if key[1] == "saw"}
        self.assertEqual({"v-see": "see", "v-saw": "saw", "n-saw": "saw"}, saw)
        self.assertNotIn("verb_base", model.members["v-see", "saw"])
        self.assertTrue({"noun", "verb"} <= set(summary["categorySurfaces"]))
        self.assertIn("noun", model.members["n-book", "book"])
        self.assertNotIn("verb", model.members["word-up", "up"])
        self.assertEqual(summary, pipeline.verify(self.args.out))
        self.assertEqual(self.inventory.read_bytes(), (self.args.out / "inventory.jsonl").read_bytes())
        self.assertEqual([row for row, state in zip(self.rows, states) if state["decision"] == "pending"],
                         self.read("fallback.jsonl"))
        self.assertTrue((self.args.out / "notices/WORDNET-3.0-LICENSE.txt").is_file())

    def test_reproducible_and_rejects_duplicate_input_changed_files_and_overwrite(self):
        self.build()
        first = self.args.out
        self.args.out = self.root / "second"
        self.build()
        for path in first.rglob("*"):
            if path.is_file():
                self.assertEqual(path.read_bytes(), (self.args.out / path.relative_to(first)).read_bytes())
        with self.assertRaisesRegex(ValueError, "Output already exists"):
            self.build()
        (self.args.out / "status.jsonl").write_text("\n")
        with self.assertRaisesRegex(ValueError, "Changed materialization"):
            pipeline.verify(self.args.out)
        pipeline.jsonl(self.inventory, self.rows + self.rows[:1])
        self.args.out = self.root / "third"
        with self.assertRaisesRegex(ValueError, "unique IDs"):
            self.build()
        self.assertFalse(self.args.out.exists())

    def test_rejects_trailing_manual_row_loss_or_changed_manual_cost(self):
        pipeline.jsonl(self.inventory, self.rows[:-1])
        with self.assertRaisesRegex(ValueError, "ordered manual IDs"):
            self.build()
        changed = [dict(row) for row in self.rows]
        changed[-1]["cost"] += 1
        pipeline.jsonl(self.inventory, changed)
        with self.assertRaisesRegex(ValueError, "inventory SHA-256"):
            self.build()
        self.assertFalse(self.args.out.exists())

    def test_no_output_for_unpinned_or_truncated_wiktextract(self):
        with self.assertRaisesRegex(ValueError, "source ZIP"):
            pipeline.build(self.args)
        self.assertFalse(self.args.out.exists())
        self.args.wiktextract = self.root / "snapshot.gz"
        self.args.wiktextract.write_bytes(gzip.compress(b'{"lang_code":"en"}\n')[:-5])
        self.args.wiktextract_sha256 = pipeline.digest(self.args.wiktextract)
        self.args.wiktionary_dump_date = "2026-10-01"
        self.args.extractor_revision = "fixture"
        with self.assertRaises(EOFError):
            self.build()
        self.assertFalse(self.args.out.exists())
        self.args.wiktextract.write_bytes(gzip.compress(b'{"word":"eat","lang_code":"en","pos":"verb","senses":[{}]}\n'))
        self.args.wiktextract_sha256 = pipeline.digest(self.args.wiktextract)
        original_digest = pipeline.digest
        changed = False

        def growing_snapshot(path):
            nonlocal changed
            value = original_digest(path)
            if path == self.args.wiktextract and not changed:
                changed = True
                with path.open("ab") as stream:
                    stream.write(gzip.compress(b'{"word":"make","lang_code":"en","pos":"verb","senses":[{}]}\n'))
            return value

        with patch.object(pipeline, "digest", side_effect=growing_snapshot):
            with self.assertRaisesRegex(ValueError, "changed during processing"):
                self.build()
        self.assertFalse(self.args.out.exists())

    def test_reviewed_overrides_retain_source_and_reject_invalid_adoption(self):
        self.build()
        initial = self.args.out
        with (initial / "decisions.tsv").open() as stream:
            import csv
            decisions = list(csv.DictReader(stream, delimiter="\t"))
        self.args.reviewed_decisions = self.root / "reviews.tsv"
        self.args.out = self.root / "reviewed"
        include = dict(decisions[0], decision="include", reason="verified", evidence="https://example.org/review/make")
        exclude = dict(decisions[7], decision="exclude", reason="unattested", lexeme_ids="-",
                       evidence="https://example.org/review/unknownzz")
        pipeline.table(self.args.reviewed_decisions, "decisions", [include, exclude])
        summary = self.build()
        self.assertEqual((3, 1, 7), (summary["includedRows"], summary["excludedRows"], summary["pendingRows"]))
        self.assertEqual(self.inventory.read_bytes(), (self.args.out / "inventory.jsonl").read_bytes())
        self.assertEqual(7, len(self.read("fallback.jsonl")))
        self.assertEqual(summary, pipeline.verify(self.args.out))
        for rows in ([include, include], [dict(include, surface="changed")],
                     [dict(include, lexeme_ids="nonexistent")], [dict(exclude, reason="guess")]):
            pipeline.table(self.args.reviewed_decisions, "decisions", rows)
            self.args.out = self.root / "invalid"
            with self.assertRaises(ValueError):
                self.build()
            self.assertFalse(self.args.out.exists())

    def test_wiktionary_uses_attested_forms_and_preserves_ambiguity_and_restrictions(self):
        entries = [
            {"word": "eat", "lang_code": "en", "pos": "verb", "etymology_number": 1,
             "senses": [{"id": "consume", "tags": ["informal"], "topics": ["medicine"]}],
             "forms": [{"form": "ate", "tags": ["past"]}]},
            {"word": "dog", "lang_code": "en", "pos": "noun", "etymology_number": 1,
             "senses": [{"tags": ["countable"]}], "forms": [{"form": "dogs", "tags": ["plural"]}]},
            {"word": "dog", "lang_code": "en", "pos": "noun", "etymology_number": 2,
             "senses": [{"tags": ["countable"]}]},
            {"word": "dogs", "lang_code": "en", "pos": "noun", "senses": [
                {"tags": ["plural", "countable", "form-of"], "form_of": [{"word": "dog"}]}]},
            {"word": "unknownzz", "lang_code": "en", "pos": "noun",
             "senses": [{"tags": ["obsolete"]}]},
            {"word": "unknownzz", "lang_code": "en", "pos": "verb",
             "senses": [{"tags": ["no-gloss"]}]},
            {"word": "make", "lang_code": "xx", "pos": "verb", "senses": [{}]},
            {"word": "men", "lang_code": "en", "pos": "name", "senses": [{}]},
            {"word": "saw", "lang_code": "en", "pos": "verb", "senses": [{}],
             "forms": [{"form": "saw", "tags": ["past", "participle"]}]},
        ]
        self.args.wiktextract = self.root / "snapshot.gz"
        with gzip.open(self.args.wiktextract, "wt") as stream:
            for row in entries:
                stream.write(json.dumps(row) + "\n")
        self.args.wiktextract_sha256 = pipeline.digest(self.args.wiktextract)
        self.args.wiktionary_dump_date = "2026-10-01"
        self.args.extractor_revision = "fixture"
        self.build()
        states = {row["id"]: row for row in self.read("status.jsonl")}
        self.assertEqual("include", states["tsv:3"]["decision"])  # eat
        self.assertEqual("pending", states["tsv:2"]["decision"])  # non-English make ignored
        self.assertEqual("pending", states["tsv:9"]["decision"])  # restricted unknownzz
        self.assertEqual("classified", states["tsv:10"]["classification"])  # exact etymology's attested table
        model = pipeline.Lexicon(self.args.out / "grammar")
        ate = [(key, model.members[key]) for key in model.forms if key[1] == "ate"]
        attested = [(key, cats) for key, cats in ate if "verb_past" in cats]
        self.assertEqual(1, len(attested))
        self.assertNotIn("verb_past_participle", attested[0][1])
        self.assertIn("domain_medical", attested[0][1])
        plural = [key for key in model.forms if key[1] == "dogs"]
        self.assertEqual(1, len(plural))
        self.assertIn("noun_count_plural", model.members[plural[0]])
        pending = self.read("pending-evidence.jsonl")
        self.assertEqual({"ambiguous_lemma_identity", "restricted_sense", "incomplete_lexical_evidence",
                          "conflicting_curated_morphology"},
                         {row["reason"] for row in pending})
        self.assertTrue(all("verb_past_participle" not in model.members[key]
                            for key, form in model.forms.items() if form["lemma"] == "saw" and key[1] == "saw"))
        self.assertTrue((self.args.out / "notices/WIKTIONARY.txt").is_file())

    def test_domain_register_and_adverb_roles_require_explicit_source_labels(self):
        self.assertEqual({"verb", "verb_base", "domain_technology", "register_formal"},
                         pipeline.sense_categories("verb", {"formal"}, {"computing"}, base=True))
        self.assertEqual({"noun"}, pipeline.sense_categories("noun", set(), {"engineering", "lifestyle"}))
        self.assertEqual({"adverb", "adverb_comparative"},
                         pipeline.sense_categories("adverb", {"comparative"}, set()))

    def test_missing_inflection_links_do_not_turn_contractions_into_bare_verbs(self):
        self.rows.append({"id": "manual:3", "reading": "can't", "surface": "can't", "cost": 700})
        pipeline.jsonl(self.inventory, self.rows)
        self.inventory_sha256 = pipeline.digest(self.inventory)
        self.args.wiktextract = self.root / "snapshot.gz"
        self.args.wiktextract.write_bytes(gzip.compress(
            b'{"word":"can\'t","lang_code":"en","pos":"verb","senses":[{}]}\n'))
        self.args.wiktextract_sha256 = pipeline.digest(self.args.wiktextract)
        self.args.wiktionary_dump_date = "2026-10-01"
        self.args.extractor_revision = "fixture"
        self.build()
        self.assertEqual("pending", self.read("status.jsonl")[-1]["decision"])
        model = pipeline.Lexicon(self.args.out / "grammar")
        self.assertFalse(any(key[1] == "can't" for key in model.forms))


if __name__ == "__main__":
    unittest.main()
