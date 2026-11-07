from argparse import Namespace
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import classification


class BatchTests(unittest.TestCase):
    def test_resume_and_reject_stale_duplicate_and_changed_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = root / "inventory.jsonl"
            classification.write_jsonl(inventory, [
                {"id": "tsv:2", "reading": "saw", "surface": "saw", "cost": 700},
                {"id": "manual:1", "reading": "saw", "surface": "saw", "cost": 800},
            ])
            allowlist = root / "public.txt"
            allowlist.write_text("tsv:2\nmanual:1\n")
            categories = root / "categories.tsv"
            categories.write_text("category\tdefinition\texamples\nverb\tverb sense\tsaw\nnoun\tnoun sense\tsaw\n")
            batches = root / "batches"
            responses = root / "responses"
            responses.mkdir()
            output = root / "proposals.jsonl"
            classification.prepare(Namespace(inventory=inventory, allowlist=allowlist, categories=categories,
                                             size=1, out=batches))
            manifest = json.loads((batches / "manifest.json").read_text())
            args = Namespace(batches=batches, responses=responses, out=output)
            first = responses / "batch-00001.jsonl"
            proposal = {"id": "tsv:2", "surface": "saw", "categories": ["noun", "verb"],
                        "batchSha256": manifest["chunks"][0]["sha256"],
                        "categoriesSha256": manifest["categoriesSha256"]}
            classification.write_jsonl(first, [proposal])
            classification.verify(args)
            self.assertEqual(["tsv:2"], [row["id"] for row in classification.read_jsonl(output)])
            for rows in (
                [proposal, proposal], [],
                [dict(proposal, id="missing")], [dict(proposal, surface="seen")],
                [dict(proposal, categories=["unknown"])], [dict(proposal, batchSha256="bad")],
            ):
                classification.write_jsonl(first, rows)
                with self.assertRaises(ValueError):
                    classification.verify(args)
            classification.write_jsonl(first, [proposal])
            classification.write_jsonl(responses / "batch-00002.jsonl", [
                dict(proposal, id="manual:1", batchSha256=manifest["chunks"][1]["sha256"]),
            ])
            classification.verify(args)
            self.assertEqual(["tsv:2", "manual:1"], [row["id"] for row in classification.read_jsonl(output)])


class EvidenceTests(unittest.TestCase):
    def test_keeps_separate_english_senses_and_their_restrictions(self):
        entries = [
            {"word": "saw", "lang_code": "en", "pos": "verb", "etymology_number": 2,
             "senses": [{"tags": ["past", "form-of"], "form_of": [{"word": "see"}]}]},
            {"word": "saw", "lang_code": "en", "pos": "noun", "etymology_number": 1,
             "senses": [{"tags": ["archaic"]}, {"topics": ["carpentry"], "tags": ["proscribed"]}]},
            {"word": "saw", "lang_code": "pl", "pos": "noun", "senses": [{}]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.jsonl.gz"
            with gzip.open(path, "wt", encoding="utf-8") as stream:
                for entry in entries:
                    stream.write(json.dumps(entry) + "\n")
            evidence = classification.wiktionary(path, classification.digest(path), {"saw", "Saw"})
            self.assertEqual(set(evidence), {"saw"})
            past, archaic, current = evidence["saw"]
            self.assertEqual((past["category"], past["formOf"]), ("verb", ["see"]))
            self.assertTrue(archaic["restricted"])
            self.assertFalse(current["restricted"])
            self.assertEqual(current["topics"], ["carpentry"])
            with self.assertRaises(ValueError):
                classification.wiktionary(path, "invalid", {"saw"})
