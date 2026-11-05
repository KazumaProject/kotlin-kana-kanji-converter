import contextlib
import gzip
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import wiktionary_index
import test_lexicon_pipeline as fixtures
SEED = fixtures.SEED


class ExtensionTests(unittest.TestCase):
    def test_reviewed_command_and_function_approvals_survive_reload_without_trusting_unknown_sources(self):
        kinds=['reviewed_official_command_example','reviewed_formal_command_prefix','reviewed_public_api_function','reviewed_tatoeba_interjection']
        cases=[(kind,{},True) for kind in kinds]+[(kind,{'approved':False},False) for kind in kinds]+[(kind,{'requiresFullNamedContext':True},False) for kind in kinds]+[('unreviewed_unknown_source',{},False)]
        added=[]
        for number,(kind,flags,expected) in enumerate(cases):
            row=dict(id='manual:'+str(3+number),reading='fixture'+str(number),surface='fixture'+str(number),cost=500+number)
            self.fixture.rows.append(row);added.append((row,kind,flags,expected))
        pipeline.jsonl(self.fixture.inventory,self.fixture.rows);self.fixture.inventory_sha256=pipeline.digest(self.fixture.inventory);self.fixture.build()
        model,rows,sources,notices,pending=extension.load_base(self.fixture.args.out,SEED)
        extension.ensure_categories(model,{'identifier_command_prefix','identifier_programming_api'})
        for row,kind,flags,expected in added:
            category='identifier_programming_api' if kind=='reviewed_public_api_function' else 'interjection' if kind=='reviewed_tatoeba_interjection' else 'identifier_command_prefix'
            proof=dict(source=kind,url='https://example.org/explicit-review',approved=True,**{k:v for k,v in flags.items() if k!='approved'})
            if 'approved' in flags:proof['approved']=flags['approved']
            model.add('fixture-'+row['id'],row['surface'],row['surface'],{category},proof,approved=expected or kind=='unreviewed_unknown_source')
        output=self.root/'reviewed-proofs'
        with contextlib.redirect_stdout(io.StringIO()):pipeline.publish(model,rows,self.fixture.inventory,output,sources,notices,pending,allow_input_spellings=True)
        restored,restored_rows,restored_sources,restored_notices,restored_pending=extension.load_base(output,SEED)
        for row,kind,flags,expected in added:self.assertEqual(expected,bool(restored.approved.get(row['surface'])),(kind,flags))
        final=self.root/'reviewed-proofs-reloaded'
        with contextlib.redirect_stdout(io.StringIO()):pipeline.publish(restored,restored_rows,self.fixture.inventory,final,restored_sources,restored_notices,restored_pending,allow_input_spellings=True)
        with (final/'status.jsonl').open() as stream:states={r['id']:r for r in map(json.loads,stream)}
        for row,kind,flags,expected in added:
            self.assertEqual('include' if expected else 'pending',states[row['id']]['decision'])
            self.assertEqual(row,{k:states[row['id']][k] for k in row})

    def setUp(self):
        self.fixture = fixtures.PipelineTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.esdb = self.root / "esdb"
        self.esdb.mkdir()
        database = self.esdb / "esdb.db"
        connection = sqlite3.connect(database)
        connection.executescript("""create table entries (
            word_id integer,group_id integer,lemma_id integer,lemma text,lemma_pos text,
            base_pos text,pos_class text,defn_note text,usage_note text,group_rank text,
            word text,pos text,entry_rank text);
            create view scowl_ as select *,35 as size,case when word='iii' then 'roman-numerals' else '' end as category,'[12dicts]' as tag,
                '_' as spelling,0 as variant_level from entries;""")
        rows = [
            (101, 10, 101, "make", "v0", "v", "", "", "", "", "make", "v0", ""),
            (102, 10, 101, "make", "v0", "v", "", "", "", "", "making", "vg", ""),
            (103, 10, 101, "make", "v0", "v", "", "", "", "", "makes", "vs", ""),
            (104, 10, 101, "make", "v0", "v", "", "", "", "", "made", "vd", ""),
            (201, 20, 201, "dog", "n0", "n", "", "", "", "", "dog", "n0", ""),
            (202, 20, 201, "dog", "n0", "n", "", "", "", "", "dogs", "ns", ""),
            (301, 30, 301, "unknownzz", "m0", "m", "", "", "", "", "unknownzz", "m0", ""),
            (302, 31, 302, "unknownzz", "n0", "n", "", "", "vulgar-1", "", "unknownzz", "n0", ""),
            (401, 40, 401, "can't", "s", "s", "", "", "", "", "can't", "s", ""),
            (501, 50, 501, "iii", "x", "x", "", "", "", "", "iii", "x", ""),
            (502, 51, 502, "rs", "x", "x", "", "", "", "", "rs", "x", ""),
        ]
        connection.executemany("insert into entries values (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        connection.commit()
        connection.close()
        for name in ("ESDB-Copyright.txt", "ESDB-Sources.md"):
            (self.esdb / name).write_text("fixture notice\n")
        manifest = {"schemaVersion": 1, "revision": extension.REVISION,
                    "recipe": "combine.py create-db --raw; omit data/coca_llm merge",
                    "databaseSha256": pipeline.digest(database), "url": extension.URL,
                    "notices": {name: pipeline.digest(self.esdb / name)
                                for name in ("ESDB-Copyright.txt", "ESDB-Sources.md")}}
        (self.esdb / "manifest.json").write_text(json.dumps(manifest))

    def test_incremental_adoption_keeps_pending_wordnet_and_source_rows_distinct(self):
        self.fixture.rows.append({"id": "manual:3", "reading": "cant", "surface": "can't", "cost": 700})
        pipeline.jsonl(self.fixture.inventory, self.fixture.rows)
        self.fixture.inventory_sha256 = pipeline.digest(self.fixture.inventory)
        self.fixture.build()
        model, rows, sources, notices, pending = extension.load_base(self.fixture.args.out, SEED)
        self.assertFalse(model.approved.get("make"))
        extension.import_esdb(model, {row["surface"] for row in rows}, self.esdb, pending)
        self.assertTrue(model.approved["make"])
        self.assertFalse(model.approved.get("unknownzz"))
        output = self.root / "extended"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.publish(model, rows, self.fixture.inventory, output, sources, notices, pending,
                             allow_input_spellings=True)
        states = [json.loads(line) for line in (output / "status.jsonl").read_text().splitlines()]
        by_id = {row["id"]: row for row in states}
        self.assertEqual("include", by_id["tsv:2"]["decision"])
        self.assertEqual("include", by_id["manual:3"]["decision"])
        self.assertEqual("pending", by_id["manual:2"]["decision"])
        self.assertEqual(self.fixture.rows, [{key: row[key] for key in self.fixture.rows[0]} for row in states])
        self.assertIn("noun_count_plural", model.members["esdb-20-201-noun", "dogs"])
        self.assertIn("verb_present_non3sg", model.members["esdb-10-101-verb", "make"])
        self.assertEqual({"contraction"}, model.members["esdb-40-401-contraction", "can't"])
        self.assertIn("input_spelling\tcant\tcan't", (output / "grammar/relations.tsv").read_text())

    def test_defective_modals_and_uncertain_source_pos_do_not_become_infinitives(self):
        record = {"pos": "v0", "lemma": "may", "usage_note": "", "pos_class": "", "base_pos": "v"}
        self.assertEqual({"verb"}, extension.categories_for(record, "verb", {"v0", "vd", "vs"}))
        self.assertEqual(set(), extension.roles_for("m", "m0"))
        self.assertEqual(set(), extension.roles_for("a", "a0"))
        self.assertIsNone(pipeline.keyboard_reading("two words"))
        self.assertEqual("wifi", pipeline.keyboard_reading("Wi-Fi"))
        self.assertEqual("usa", pipeline.keyboard_reading("U.S.A."))
        self.assertEqual("cicd", pipeline.keyboard_reading("CI/CD"))

    def test_changed_source_database_is_rejected(self):
        self.fixture.build()
        model, rows, sources, notices, pending = extension.load_base(self.fixture.args.out, SEED)
        with (self.esdb / "esdb.db").open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "Changed or unapproved"):
            extension.import_esdb(model, {row["surface"] for row in rows}, self.esdb, pending)

    def test_only_explicit_roman_numeral_source_rows_get_a_numeric_role(self):
        model = pipeline.Lexicon(SEED)
        extension.import_esdb(model, {"iii", "rs"}, self.esdb, [])
        self.assertTrue(model.approved["iii"])
        self.assertFalse(model.approved.get("rs"))
        self.assertEqual({"numeral", "numeral_roman"}, model.members["esdb-50-501-numeral", "iii"])

    def test_unicode_case_mapping_preserves_accents_and_does_not_strip_them(self):
        self.fixture.rows += [
            {"id": "manual:3", "reading": "pokémon", "surface": "Pokémon", "cost": 700},
            {"id": "manual:4", "reading": "pokemon", "surface": "Pokémon", "cost": 800},
        ]
        pipeline.jsonl(self.fixture.inventory, self.fixture.rows)
        self.fixture.inventory_sha256 = pipeline.digest(self.fixture.inventory)
        self.fixture.build()
        model, rows, sources, notices, pending = extension.load_base(self.fixture.args.out, SEED)
        model.add("fixture-pokemon", "Pokémon", "Pokémon", {"noun_proper"},
                  {"source": "wiktionary", "url": "https://en.wiktionary.org/wiki/Pok%C3%A9mon", "approved": True}, approved=True)
        output = self.root / "unicode-case"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.publish(model, rows, self.fixture.inventory, output, sources, notices, pending, allow_input_spellings=True)
        states = [json.loads(line) for line in (output / "status.jsonl").read_text().splitlines()]
        self.assertEqual(["include", "pending"], [row["decision"] for row in states[-2:]])
        self.assertEqual("mapping_review_required", states[-1]["reason"])

    def test_case_mapping_preserves_declared_word_boundaries(self):
        self.fixture.rows += [
            {"id": "manual:3", "reading": "google docs", "surface": "Google Docs", "cost": 700},
            {"id": "manual:4", "reading": "googledocs", "surface": "Google Docs", "cost": 800},
        ]
        pipeline.jsonl(self.fixture.inventory, self.fixture.rows)
        self.fixture.inventory_sha256 = pipeline.digest(self.fixture.inventory)
        self.fixture.build()
        model, rows, sources, notices, pending = extension.load_base(self.fixture.args.out, SEED)
        model.add("fixture-google", "Google Docs", "Google Docs", {"noun_proper"},
                  {"source": "wiktionary", "url": "https://en.wiktionary.org/wiki/Google_Docs", "approved": True}, approved=True)
        output = self.root / "mapped-spaces"
        with contextlib.redirect_stdout(io.StringIO()):
            pipeline.publish(model, rows, self.fixture.inventory, output, sources, notices, pending, allow_input_spellings=True)
        states = [json.loads(line) for line in (output / "status.jsonl").read_text().splitlines()]
        self.assertEqual(["include", "pending"], [row["decision"] for row in states[-2:]])
        self.assertEqual("google docs", states[-2]["reading"])
        self.assertEqual("Google Docs", states[-2]["surface"])


class IndexTests(unittest.TestCase):
    def test_index_retains_lexical_proof_and_omits_quotes_and_non_english_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "snapshot.gz"
            entries = [
                {"word": "favorite", "lang_code": "en", "pos": "noun", "senses": [
                    {"alt_of": [{"word": "favourite"}], "tags": ["US"], "glosses": ["Alternative spelling of favourite."],
                     "examples": [{"text": "not needed"}]}]},
                {"word": "favorite", "lang_code": "xx", "pos": "noun", "senses": [{}]},
            ]
            source.write_bytes(gzip.compress(('\n'.join(json.dumps(row) for row in entries) + '\n').encode()))
            notices = root / "notices"
            notices.mkdir()
            for name in ("WIKTIONARY.txt", "CC-BY-SA-4.0.txt"):
                (notices / name).write_text("fixture\n")
            with patch.object(wiktionary_index, "SNAPSHOT_SHA256", pipeline.digest(source)), contextlib.redirect_stdout(io.StringIO()):
                wiktionary_index.build(source, root / "index", notices)
                index = wiktionary_index.Index(root / "index")
                self.addCleanup(index.close)
                rows = list(index.lookup(["FAVORITE"], folded=True))
                self.assertEqual(1, len(rows))
                self.assertEqual([{"word": "favourite"}], rows[0][1]["senses"][0]["alt_of"])
                self.assertNotIn("examples", rows[0][1]["senses"][0])
                self.assertEqual(1, index.manifest["englishEntries"])


if __name__ == "__main__":
    unittest.main()
