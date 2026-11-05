import contextlib
import io
import unittest

import audit_lexicon
import lexicon_pipeline as pipeline
import software_registries as software
import test_lexicon_pipeline as fixtures


class SoftwareRegistryTests(unittest.TestCase):
    def test_registry_labels_and_declared_aliases_do_not_become_inflections_or_arbitrary_mappings(self):
        model = pipeline.Lexicon(fixtures.SEED)
        rows = [
            {"id": "manual:1", "reading": "csharp", "surface": "C#", "cost": 700},
            {"id": "manual:2", "reading": "cplusplus", "surface": "C++", "cost": 800},
            {"id": "tsv:2", "reading": "csharp", "surface": "C#", "cost": 900},
            {"id": "manual:3", "reading": "registryapp", "surface": "RegistryApp", "cost": 1000},
            {"id": "manual:4", "reading": "retiredapp", "surface": "RetiredApp", "cost": 1100},
        ]
        languages = {"C#": {"type": "programming", "language_id": 1, "aliases": ["csharp"]},
                     "C++": {"type": "programming", "language_id": 2, "aliases": ["cpp"]}}
        casks = [{"token": "registryapp", "tap": "homebrew/cask", "name": ["RegistryApp"],
                  "tap_git_head": "a" * 40, "ruby_source_path": "Casks/r/registryapp.rb", "ruby_source_checksum": {"sha256": "fixture"}},
                 {"token": "retiredapp", "tap": "homebrew/cask", "name": ["RetiredApp"], "disabled": True}]
        counts = software.attach(model, rows, languages, casks)
        self.assertEqual(1, counts["declaredManualInputAliases"])
        self.assertTrue(model.approved["C#"])
        self.assertTrue(model.approved["RegistryApp"])
        self.assertFalse(model.approved.get("RetiredApp"))
        aliases = {(row["source"], row["target"]) for row in model.relations if row["relation"] == "input_alias"}
        self.assertEqual({("csharp", "C#")}, aliases)
        for key, members in model.members.items():
            if key[0].startswith("registry-"):
                self.assertFalse(members & {"verb_base", "noun_proper", "noun_count_singular", "noun_count_plural"})
        model.validate()

    def test_only_independent_eligible_evidence_can_corroborate_daily_membership(self):
        url = "https://example.org/"
        self.assertFalse(audit_lexicon.independently_eligible([{"source": "ngsl_list", "url": url, "approved": True}], []))
        self.assertFalse(audit_lexicon.independently_eligible([{"source": "wiktionary", "url": url, "tags": ["archaic"], "approved": True}], []))
        self.assertTrue(audit_lexicon.independently_eligible([{"source": "wiktionary", "url": url, "tags": [], "approved": True}], []))
        self.assertFalse(audit_lexicon.independently_eligible([{"source": "esdb", "url": url, "approved": False}], []))

    def test_existing_manual_alias_is_used_without_changing_original_rows(self):
        fixture = fixtures.PipelineTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.rows += [{"id": "manual:3", "reading": "csharp", "surface": "C#", "cost": 700}]
        pipeline.jsonl(fixture.inventory, fixture.rows)
        fixture.inventory_sha256 = pipeline.digest(fixture.inventory)
        fixture.build()
        model, rows, sources, notices, pending = software.extension.load_base(fixture.args.out, fixtures.SEED)
        software.attach(model, rows, {"C#": {"type": "programming", "language_id": 1, "aliases": ["csharp"]}}, [])
        with contextlib.redirect_stdout(io.StringIO()):
            summary = pipeline.publish(model, rows, fixture.inventory, fixture.root / "aliases", sources, notices, pending,
                                       allow_input_spellings=True)
        decisions = pipeline.read_table(fixture.root / "aliases/decisions.tsv", "decisions")
        self.assertEqual("include", decisions[-1]["decision"])
        self.assertEqual("csharp", decisions[-1]["reading"])
        self.assertEqual("C#", decisions[-1]["surface"])


if __name__ == "__main__":
    unittest.main()
