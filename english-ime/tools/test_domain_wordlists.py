from pathlib import Path
import tempfile
import unittest

import domain_wordlists as domains
import lexicon_pipeline as pipeline
from test_lexicon_pipeline import SEED


class DomainListTests(unittest.TestCase):
    def test_imports_headwords_without_rule_generated_or_case_folded_forms(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "supplement.csv"
            path.write_text("March,Marchs,marched,marching\nMay,Mays\n")
            words = domains.headwords(path, None, 2)
            self.assertEqual([(1, "March"), (2, "May")], words)
            with self.assertRaisesRegex(ValueError, "structure or headword count"):
                domains.headwords(path, None, 3)
            model = pipeline.Lexicon(SEED)
            counts = domains.attach(model, "fixture", words, "domain_daily", domains.NGSL_URL, "fixture-sha")
            self.assertEqual(2, counts["classificationOnly"])
            self.assertFalse(model.approved.get("May"))
            self.assertNotIn("Marchs", {surface for _, surface in model.forms})
            self.assertFalse(any(key[0].startswith("domain-list-") and key[1] == "may" for key in model.forms))

    def test_membership_corroboration_does_not_invent_pos_or_inflection_flags(self):
        model = pipeline.Lexicon(SEED)
        counts = domains.attach(model, "fixture", [(1, "can"), (2, "unknownzz")],
                                "domain_daily", domains.NGSL_URL, "fixture-sha")
        self.assertEqual(1, counts["withIndependentEligibleReading"])
        self.assertFalse(model.approved.get("unknownzz"))
        for key, values in model.members.items():
            if key[0].startswith("domain-list-"):
                self.assertEqual({"domain_daily"}, values)
                self.assertEqual("word_level_not_sense_disambiguated", model.evidence[key][0]["scope"])
        model.validate()


if __name__ == "__main__":
    unittest.main()
