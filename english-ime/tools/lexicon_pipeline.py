"""Materialize an auditable lexicon without losing unreviewed source rows.

WordNet establishes lexical roles, not the absence of restricted senses. Its
matches therefore remain pending distribution review. Only the curated seed or
eligible Wiktionary evidence can produce inclusion decisions. No network calls.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
from urllib.parse import quote
from zipfile import ZipFile

from classification import WORDNET_SHA256, WORDNET_ROLES, WIKTIONARY_ROLES, RESTRICTED, digest

HEADERS = {
    "categories": ["category", "definition", "examples"],
    "forms": ["lexeme_id", "lemma", "surface", "evidence"],
    "memberships": ["category", "lexeme_id", "surface"],
    "relations": ["relation", "source", "target", "evidence"],
    "decisions": ["id", "reading", "surface", "cost", "decision", "lexeme_ids", "reason", "evidence"],
    "corrections": ["id", "source", "target", "relation", "evidence"],
}
WN_URL = "https://wordnetcode.princeton.edu/3.0/WordNet-3.0.tar.gz"
SOURCE_SHA256 = "33dfe992f0220f28f18a8ca21af2139a4f345871c5bd6004ce09c109e1791c8c"
INVENTORY_SHA256 = "ddc2808807ca25b85fb5b8c08c964f63514c4237e8d84bb676e9b8194e615401"
MANUAL_ROW_COUNT = 1976
SOURCE_TSV = "1-grams_score_cost_pos_combined_with_ner.txt"
EXCLUSION_REASONS = {"malformed", "wrong_mapping", "unattested", "restricted", "ineligible_senses", "ineligible_reference", "unsupported_mapping"}
# Explicit source labels mapped to the catalog's definitions. In particular,
# "engineering" is not computing, and "lifestyle" does not prove everyday use.
TOPIC_CATEGORIES = {
    "computing": "domain_technology", "programming": "domain_technology",
    "software": "domain_technology", "computer-science": "domain_technology",
    "medicine": "domain_medical", "healthcare": "domain_medical",
    "anatomy": "domain_medical", "pathology": "domain_medical", "pharmacology": "domain_medical",
    "business": "domain_business", "commerce": "domain_business", "finance": "domain_business",
    "transport": "domain_travel", "travel": "domain_travel", "tourism": "domain_travel",
    "food": "domain_food", "drink": "domain_food", "beverages": "domain_food", "cooking": "domain_food",
    "sciences": "domain_science", "science": "domain_science", "natural-sciences": "domain_science",
    "physical-sciences": "domain_science", "human-sciences": "domain_science",
    "mathematics": "domain_science", "chemistry": "domain_science", "physics": "domain_science",
    "biology": "domain_science", "astronomy": "domain_science",
    "education": "domain_education", "teaching": "domain_education", "pedagogy": "domain_education",
    "sports": "domain_sports", "sport": "domain_sports",
    "entertainment": "domain_entertainment", "performing-arts": "domain_entertainment",
    "music": "domain_entertainment", "film": "domain_entertainment", "television": "domain_entertainment",
    "theatre": "domain_entertainment", "theater": "domain_entertainment", "dance": "domain_entertainment",
}
WIKT_NOTICE = """Wiktionary-derived lexical facts; source pages are linked in evidence.jsonl.
Wiktionary contributors, CC BY-SA 4.0 and applicable GFDL terms.
https://en.wiktionary.org/wiki/Wiktionary:Copyrights
https://creativecommons.org/licenses/by-sa/4.0/
Changes: selected English entries, separated lexemes/forms, mapped tags to named
dictionaries, and joined the original dictionary inventory. Snapshot metadata
and hashes are recorded in manifest.json. Preserve these notices and attribution.
"""


def jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def read_table(path, name):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != HEADERS[name]:
            raise ValueError(f"Invalid {name} header: {path}")
        rows = list(reader)
    if any(set(row) != set(HEADERS[name]) or any(not v for v in row.values()) for row in rows):
        raise ValueError(f"Invalid {name} row: {path}")
    return rows


def table(path, name, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, HEADERS[name], delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def inventory(path):
    with path.open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    if not rows or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Inventory must contain unique IDs and at least one row")
    for row in rows:
        if (set(row) != {"id", "reading", "surface", "cost"}
                or any(not isinstance(row[key], str) or not row[key].strip() or
                       any(c in row[key] for c in "\t\r\n") for key in ("id", "reading", "surface"))
                or type(row["cost"]) is not int or not -32768 <= row["cost"] <= 32767):
            raise ValueError(f"Invalid inventory record: {row.get('id')}")
    return rows


def validate_source(path, rows):
    if digest(path) != SOURCE_SHA256:
        raise ValueError("Unexpected source ZIP SHA-256; review provenance before changing the pin")
    with ZipFile(path) as archive:
        payload = archive.read(SOURCE_TSV)
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8")), delimiter="\t")
        if reader.fieldnames != ["input_word", "output_word", "pos_tag", "score"]:
            raise ValueError("Unexpected source TSV header")
        expected = [{"id": f"tsv:{index + 2}", "reading": row["input_word"],
                     "surface": row["output_word"], "cost": int(row["score"])}
                    for index, row in enumerate(reader)]
        actual = [row for row in rows if row["id"].startswith("tsv:")]
        manual = [row for row in rows if row["id"].startswith("manual:")]
        if actual != expected or rows != actual + manual or [row["id"] for row in manual] != [
                f"manual:{index + 1}" for index in range(MANUAL_ROW_COUNT)]:
            raise ValueError("Inventory does not match the complete source TSV and ordered manual IDs")
        notices = {"SOURCE-NOTICE.md": archive.read("NOTICE.md"),
                   "CC-BY-SA-4.0.txt": archive.read("LICENSES/CC-BY-SA-4.0.txt")}
    return hashlib.sha256(payload).hexdigest(), notices


def role(category):
    if category == "verb_particle":
        return "particle"
    if category.startswith(("noun", "name_")):
        return "noun"
    if category.startswith(("verb", "aux_")):
        return "verb"
    if category.startswith("adjective"):
        return "adjective"
    if category.startswith(("adverb", "interrogative_adverb")):
        return "adverb"
    if category.startswith("det_"):
        return "determiner"
    if category.startswith("pronoun"):
        return "pronoun"
    if category.startswith("conjunction"):
        return "conjunction"
    if category.startswith("numeral"):
        return "numeral"
    return category


class Lexicon:
    def __init__(self, seed):
        self.definitions = read_table(seed / "categories.tsv", "categories")
        self.names = {row["category"] for row in self.definitions}
        if len(self.names) != len(self.definitions):
            raise ValueError("Duplicate category definitions")
        forms = read_table(seed / "forms.tsv", "forms")
        self.forms = {(row["lexeme_id"], row["surface"]): dict(row) for row in forms}
        if len(forms) != len(self.forms):
            raise ValueError("Duplicate seed form")
        members = read_table(seed / "memberships.tsv", "memberships")
        keys = [(row["category"], row["lexeme_id"], row["surface"]) for row in members]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate seed membership")
        self.members = defaultdict(set)
        for category, lexeme, surface in keys:
            if category not in self.names or (lexeme, surface) not in self.forms:
                raise ValueError("Unknown seed category or form")
            self.members[lexeme, surface].add(category)
        if set(self.members) != set(self.forms) or {row["category"] for row in members} != self.names:
            raise ValueError("Every seed form and category needs membership")
        self.evidence = defaultdict(list)
        self.seed_morphology = defaultdict(set)
        self.seed_surfaces = set()
        self.identities = defaultdict(set)
        self.approved = defaultdict(set)
        for key, form in self.forms.items():
            self.seed_surfaces.add(key[1])
            self.approved[key[1]].add(key[0])
            self.evidence[key].append({"source": "curated_seed", "url": form["evidence"]})
            for category in list(self.members[key]):
                if category.startswith("aux_") or category.startswith("verb_") and category != "verb_particle":
                    self.seed_morphology[form["lemma"], key[1]].add(category)
                generic = role(category)
                if generic in self.names:
                    self.members[key].add(generic)
                self.identities[form["lemma"], generic].add(key[0])
        self.relations = read_table(seed / "relations.tsv", "relations")
        self.validate()

    def identity(self, lemma, pos, discriminator=""):
        ids = self.identities[lemma, pos]
        if not discriminator and len(ids) == 1:
            return next(iter(ids))
        # Ambiguous identities are kept separate; never pool their inflection flags.
        key = json.dumps([lemma, pos, discriminator], ensure_ascii=False)
        identifier = "lex-" + hashlib.sha256(key.encode()).hexdigest()[:24]
        ids.add(identifier)
        return identifier

    def add(self, identifier, lemma, surface, categories, evidence, approved=False):
        categories = set(categories)
        categories.update(role(category) for category in list(categories) if role(category) in self.names)
        if not categories or not categories <= self.names:
            raise ValueError(f"Unknown or empty category: {categories - self.names}")
        key = identifier, surface
        form = {"lexeme_id": identifier, "lemma": lemma, "surface": surface, "evidence": evidence["url"]}
        if key in self.forms and self.forms[key]["lemma"] != lemma:
            raise ValueError("Conflicting lemma identity")
        if not evidence["url"].startswith("https://"):
            raise ValueError("Missing evidence URL")
        self.forms.setdefault(key, form)
        self.members[key].update(categories)
        if evidence not in self.evidence[key]:
            self.evidence[key].append(evidence)
        if approved:
            self.approved[surface].add(identifier)

    def validate(self):
        lemmas = defaultdict(set)
        for key, form in self.forms.items():
            lemmas[key[0]].add(form["lemma"])
            if not self.members[key] or not form["evidence"].startswith("https://"):
                raise ValueError("Unclassified or unreferenced form")
            if self.members[key] & {"verb_base", "aux_be_base", "aux_have_base", "aux_do_base", "adjective_base"} and key[1] != form["lemma"]:
                raise ValueError("Base role attached to an inflected surface")
        for identifier, bases in lemmas.items():
            if len(bases) != 1 or (identifier, next(iter(bases))) not in self.forms:
                raise ValueError("Lexeme requires one lemma and its base form")

    def write(self, output):
        self.validate()
        output.mkdir()
        table(output / "categories.tsv", "categories", self.definitions)
        table(output / "forms.tsv", "forms", [self.forms[key] for key in sorted(self.forms)])
        table(output / "memberships.tsv", "memberships", [
            {"category": category, "lexeme_id": key[0], "surface": key[1]}
            for key in sorted(self.members) for category in sorted(self.members[key])
        ])
        table(output / "relations.tsv", "relations", self.relations)


def wordnet(model, path, wanted):
    if digest(path) != WORDNET_SHA256:
        raise ValueError("Unexpected WordNet 3.0 SHA-256")
    with tarfile.open(path, "r:gz") as archive:
        notice = archive.extractfile("WordNet-3.0/LICENSE").read()
        for suffix, pos in WORDNET_ROLES.items():
            member = f"WordNet-3.0/dict/index.{suffix}"
            lemmas = {}
            for number, raw in enumerate(archive.extractfile(member), 1):
                if raw.startswith(b" "):
                    continue
                fields = raw.decode("ascii").split()
                if not fields:
                    continue
                lemma = fields[0].replace("_", " ")
                lemmas[lemma] = number
            targets = {lemma: {lemma} for lemma in lemmas if lemma in wanted}
            exceptions = {}
            exc_member = f"WordNet-3.0/dict/{suffix}.exc"
            for number, raw in enumerate(archive.extractfile(exc_member), 1):
                # Read underscore-separated multiword lemmas without splitting the words.
                fields = [v.decode("ascii").replace("_", " ") for v in raw.split()]
                if fields and fields[0] in wanted:
                    for lemma in fields[1:]:
                        if lemma in lemmas:
                            targets.setdefault(lemma, {lemma}).add(fields[0])
                            exceptions[fields[0], lemma] = number
            for lemma, surfaces in sorted(targets.items()):
                identifier = model.identity(lemma, pos)
                for surface in sorted(surfaces):
                    categories = {pos}
                    if pos == "verb" and surface == lemma:
                        categories.add("verb_base")
                    exception = surface != lemma
                    source_member = exc_member if exception else member
                    line = exceptions[surface, lemma] if exception else lemmas[lemma]
                    model.add(identifier, lemma, surface, categories, {
                        "source": "wordnet_3.0", "url": WN_URL + "#" + source_member,
                        "member": source_member, "line": line,
                        "relation": "inflection_unspecified" if exception else "lemma",
                    })
    return notice


def tagged_categories(pos, tags, base=False):
    tags = set(tags)
    categories = {pos}
    if pos == "verb":
        if base or "infinitive" in tags:
            categories.add("verb_base")
        if {"third-person", "singular", "present"} <= tags and "participle" not in tags:
            categories.add("verb_present_3sg")
        if "past" in tags:
            categories.add("verb_past_participle" if "participle" in tags else "verb_past")
        if {"present", "participle"} <= tags or "gerund" in tags:
            categories.add("verb_ing")
    elif pos == "noun":
        if "collective" in tags:
            categories.add("noun_collective")
        if "uncountable" in tags:
            categories.add("noun_uncountable")
        if "plural-only" in tags or "pluralia-tantum" in tags:
            categories.add("noun_plural_only")
        elif "plural" in tags and "countable" in tags:
            categories.add("noun_count_plural")
        elif "countable" in tags and ("singular" in tags or base and "plural" not in tags):
            categories.add("noun_count_singular")
    elif pos == "adjective":
        if base and "positive" in tags:
            categories.add("adjective_base")
        for tag in ("comparative", "superlative", "attributive", "predicative"):
            if tag in tags:
                categories.add("adjective_" + tag)
    elif pos == "adverb":
        for tag in ("comparative", "superlative"):
            if tag in tags:
                categories.add("adverb_" + tag)
    return categories


def constrain_morphology(model, lemma, surface, categories, evidence, pending):
    allowed = model.seed_morphology.get((lemma, surface))
    if allowed is not None:
        proposed = {category for category in categories if category.startswith("aux_") or
                    category.startswith("verb_") and category != "verb_particle"}
        conflicting = proposed - allowed
        if conflicting:
            pending.append({"surface": surface, "lemma": lemma, "reason": "conflicting_curated_morphology",
                            "proposedRoles": sorted(conflicting), "evidence": evidence})
            categories = categories - conflicting
    return categories


def sense_categories(pos, tags, topics, base=False):
    categories = tagged_categories(pos, tags, base)
    categories.update(TOPIC_CATEGORIES[topic] for topic in topics if topic in TOPIC_CATEGORIES)
    if set(tags) & {"informal", "colloquial", "slang"}:
        categories.add("register_informal")
    if "formal" in tags:
        categories.add("register_formal")
    return categories


def wiktionary(model, path, sha256, wanted):
    before = path.stat()
    if not sha256 or digest(path) != sha256:
        raise ValueError("Unexpected Wiktextract SHA-256")
    entries = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("lang_code") == "en" and row.get("word") in wanted:
                # Do not retain translations, quotations, examples, audio or gloss
                # text from the multi-gigabyte snapshot when only lexical facts
                # are used below.
                entries.append({key: row[key] for key in ("word", "pos", "tags", "etymology_number") if key in row} | {
                    "senses": [{key: sense[key] for key in ("id", "tags", "topics", "form_of", "alt_of") if key in sense}
                               for sense in row.get("senses", [])],
                    "forms": [{key: form[key] for key in ("form", "tags") if key in form}
                              for form in row.get("forms", [])],
                })
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Wiktextract changed during processing; no output published")
    pending = []
    links = []
    roots = defaultdict(set)
    for row in entries:
        surface = row["word"]
        pos = WIKTIONARY_ROLES.get(row.get("pos"))
        if not pos:
            pending.append({"surface": surface, "reason": "unsupported_lexical_role"})
            continue
        common = set(row.get("tags", []))
        etymology = row.get("etymology_number", 0)
        url = "https://en.wiktionary.org/wiki/" + quote(surface.replace(" ", "_"), safe="") + "#English"
        for index, sense in enumerate(row.get("senses", []), 1):
            tags = common | set(sense.get("tags", []))
            evidence = {"source": "wiktionary", "url": url, "etymology": etymology,
                        "sense": sense.get("id") or index, "tags": sorted(tags),
                        "topics": sorted(set(sense.get("topics", [])))}
            if tags & (RESTRICTED | {"no-gloss", "error-unknown-tag", "error-unrecognized-form"}):
                pending.append({"surface": surface, "reason": "restricted_sense" if tags & RESTRICTED
                                else "incomplete_lexical_evidence", "evidence": evidence})
                continue
            bases = [item["word"] for item in sense.get("form_of", [])]
            if bases:
                links.append((surface, pos, bases, tags, evidence))
                continue
            if sense.get("alt_of") or "form-of" in tags:
                pending.append({"surface": surface, "reason": "unresolved_spelling_relation", "evidence": evidence})
                continue
            if pos == "verb" and not any(
                    tagged_categories("verb", form.get("tags", [])) - {"verb"}
                    for form in row.get("forms", [])) and "infinitive" not in tags:
                # A verb headword without form_of is not proof of a bare infinitive:
                # raw entries for can't/couldn't and other contractions lack those links.
                pending.append({"surface": surface, "reason": "unresolved_lemma_identity", "evidence": evidence})
                continue
            # Keep Wiktionary etymologies distinct, including same-POS homographs.
            identifier = model.identity(surface, role(pos), "wiktionary:" + str(etymology))
            categories = sense_categories(pos, tags, evidence["topics"], base=True)
            categories = constrain_morphology(model, surface, surface, categories, evidence, pending)
            model.add(identifier, surface, surface, categories, evidence, approved=True)
            roots[surface, role(pos)].add(identifier)
            for form in row.get("forms", []):
                word = form.get("form")
                form_tags = set(form.get("tags", []))
                if word in wanted and not form_tags & (RESTRICTED | {"multiword-construction", "error-unrecognized-form"}):
                    # Forms from an entry's table belong to this exact etymology.
                    inherited = {"countable"} if pos == "noun" and "countable" in tags else set()
                    grammatical = tagged_categories(pos, form_tags | inherited)
                    if any(c != pos for c in grammatical):
                        categories = sense_categories(pos, form_tags | inherited, evidence["topics"])
                        categories = constrain_morphology(model, surface, word, categories, evidence, pending)
                        model.add(identifier, surface, word, categories,
                                  dict(evidence, relation="inflection_table", tags=sorted(form_tags),
                                       lemmaTags=sorted(tags)), approved=True)
    for surface, pos, bases, tags, evidence in links:
        ids = set()
        for lemma in bases:
            ids.update(roots.get((lemma, role(pos))) or model.identities.get((lemma, role(pos)), set()))
        if len(ids) != 1 or len(set(bases)) != 1:
            pending.append({"surface": surface, "reason": "ambiguous_lemma_identity", "evidence": evidence})
            continue
        identifier = next(iter(ids))
        categories = sense_categories(pos, tags, evidence["topics"])
        categories = constrain_morphology(model, bases[0], surface, categories, evidence, pending)
        model.add(identifier, bases[0], surface, categories, evidence, approved=True)
    return pending


def build(args):
    rows = inventory(args.inventory)
    source_tsv_sha256, source_notices = validate_source(args.source, rows)
    if digest(args.inventory) != INVENTORY_SHA256:
        raise ValueError("Unexpected inventory SHA-256; regenerate from the pinned Kotlin source")
    model = Lexicon(args.seed)
    wanted = {row["surface"] for row in rows}
    sources = {"inventorySha256": digest(args.inventory), "seed": {
        name: digest(args.seed / (name + ".tsv")) for name in ("categories", "forms", "memberships", "relations")}}
    sources["sourceZipSha256"] = SOURCE_SHA256
    sources["sourceTsvSha256"] = source_tsv_sha256
    notice = wordnet(model, args.wordnet, wanted)
    sources["wordnet"] = {"version": "3.0", "sha256": WORDNET_SHA256, "url": WN_URL}
    pending_evidence = []
    if args.wiktextract:
        if not args.wiktionary_dump_date or not args.extractor_revision:
            raise ValueError("Wiktionary dump date and extractor revision are required")
        pending_evidence = wiktionary(model, args.wiktextract, args.wiktextract_sha256, wanted)
        sources["wiktionary"] = {"sha256": args.wiktextract_sha256,
                                  "dumpDate": args.wiktionary_dump_date,
                                  "extractorRevision": args.extractor_revision}
    notices = dict(source_notices, **{"WORDNET-3.0-LICENSE.txt": notice, "WIKTIONARY.txt": WIKT_NOTICE.encode()})
    for path in sorted((args.seed.parent.parent / "notices").glob("*")):
        if path.is_file():
            notices[path.name] = path.read_bytes()
    return publish(model, rows, args.inventory, args.out, sources, notices, pending_evidence,
                   reviewed_decisions=args.reviewed_decisions)


def keyboard_reading(surface):
    """The declared ASCII input spelling; never a guessed lexical correction."""
    value = surface.replace('’', "'").lower()
    if not value or any(not ('a' <= c <= 'z' or '0' <= c <= '9' or c in "'-./" ) for c in value):
        return None
    result = ''.join(c for c in value if c not in "'-./")
    return result or None


def correction_targets(corrections, rows, model):
    originals = {row["id"]: row for row in rows}
    surfaces = {surface for _, surface in model.forms}
    targets = defaultdict(list)
    relations = defaultdict(set)
    seen = set()
    for item in corrections:
        original = originals.get(item["id"])
        key = item["id"], item["target"]
        spelling = item['relation'] in {'input_spelling_correction', 'input_spelling_candidates'}
        if (key in seen or original is None or item["source"] != original["surface"] or
                item["relation"] not in {"case_correction", "case_candidates", 'input_spelling_correction', 'input_spelling_candidates'} or item["source"] == item["target"] or
                item["source"] != item["source"].lower() or
                (keyboard_reading(item['source']) != original['reading'] if spelling else item["source"].lower() != item["target"].lower()) or
                keyboard_reading(item["target"]) != original["reading"] or
                item["target"] not in surfaces or
                not item["evidence"].startswith("https://")):
            raise ValueError("Invalid or duplicate source surface correction")
        targets[item["id"]].append(item["target"])
        relations[item["id"]].add(item["relation"])
        seen.add(key)
    for key, values in targets.items():
        if (len(relations[key]) != 1 or
                (next(iter(relations[key])) in {'case_correction', 'input_spelling_correction'}) != (len(values) == 1)):
            raise ValueError("Invalid or duplicate source surface correction")
    return {key: tuple(sorted(values)) for key, values in targets.items()}


def publish(model, rows, inventory_path, output, sources, notice_contents, pending_evidence,
            reviewed_decisions=None, allow_input_spellings=False, corrections=()):
    wanted = {row["surface"] for row in rows}
    if allow_input_spellings:
        sources["inputSpellingPolicy"] = "exact Unicode lowercasing preserving spaces; or ASCII alphanumeric input with apostrophes, hyphens, dots and slashes removed; declared aliases separate; no accent stripping or guessed word boundaries"
        sources["surfaceDecoderRequirement"] = "English LOUDS renderer skips sentinel node IDs 0 and 1, preserves other spaces; verified Sumire source 427baa8ef19a5917ea931d6731ec9d1fd95289d7"
    by_surface = defaultdict(set)
    for identifier, surface in model.forms:
        by_surface[surface].add(identifier)
    targets = correction_targets(corrections, rows, model)
    input_spelling_ids = {item['id'] for item in corrections if item['relation'] == 'input_spelling_candidates'}
    decisions = []
    status = []
    mappings = {(row["source"], row["target"]) for row in model.relations
                if row["relation"] in {"capitalization", "contraction"} and ' ' not in row["target"]}
    explicit_aliases = {(row["source"], row["target"]) for row in model.relations if row["relation"] == "input_alias"}
    relation_keys = {(row["relation"], row["source"], row["target"]) for row in model.relations}
    for row in rows:
        surfaces = targets.get(row["id"], (row["surface"],))
        identifiers = sorted(set().union(*(by_surface.get(surface, set()) for surface in surfaces)))
        approved = sorted(set().union(*(model.approved.get(surface, set()) for surface in surfaces)))
        # Nonidentity readings need a curated mapping review in addition to a word's role.
        def supported(surface):
            mapped_seed = (surface in model.seed_surfaces and
                           (row["reading"] == surface.lower() or (row["reading"], surface) in mappings))
            return bool(model.approved.get(surface)) and (row["reading"] == surface or mapped_seed or
                (row["reading"], surface) in explicit_aliases or
                allow_input_spellings and (keyboard_reading(surface) == row["reading"] or
                    row["reading"] == surface.lower()))
        included = all(supported(surface) for surface in surfaces)
        reason = "verified" if included else (
            "mapping_review_required" if approved else
            "sense_review_required" if identifiers else "no_lexical_evidence")
        evidence_ids = approved if included else identifiers
        urls = sorted({item["url"] for identifier in evidence_ids
                       for surface in surfaces for item in model.evidence.get((identifier, surface), [])})
        for surface in surfaces:
            if (included and allow_input_spellings and row["reading"] != surface and
                    (keyboard_reading(surface) == row["reading"] or row["reading"] == surface.lower())):
                relation = {"relation": "capitalization" if row["reading"] == surface.lower() else "input_spelling",
                            "source": row["reading"], "target": surface, "evidence": urls[0]}
                key = relation["relation"], relation["source"], relation["target"]
                if key not in relation_keys:
                    model.relations.append(relation)
                    relation_keys.add(key)
        decisions.append(dict(row, decision="include" if included else "pending",
                              lexeme_ids=",".join(evidence_ids) or "-", reason=reason,
                              evidence=urls[0] if urls else "-"))
        status.append(dict(row, classification="classified" if identifiers else "unresolved",
                           lexeme_ids=identifiers, decision="include" if included else "pending", reason=reason))
        if row["id"] in targets:
            if not included:
                raise ValueError("Surface correction lacks eligible adoption evidence")
            if len(surfaces) == 1:
                status[-1]["effective_surface"] = surfaces[0]
            else:
                status[-1]["effective_surfaces"] = list(surfaces)
                status[-1]["interpretation"] = ('input_spelling_candidates_not_disambiguated' if
                    row['id'] in input_spelling_ids
                    else "case_candidates_not_disambiguated")
    if reviewed_decisions:
        overrides = read_table(reviewed_decisions, "decisions")
        positions = {row["id"]: index for index, row in enumerate(rows)}
        seen = set()
        for override in overrides:
            identifier = override["id"]
            if identifier in seen or identifier not in positions:
                raise ValueError("Unknown or duplicate reviewed decision ID")
            seen.add(identifier)
            index = positions[identifier]
            original = rows[index]
            if (any(override[key] != original[key] for key in ("id", "reading", "surface")) or
                    int(override["cost"]) != original["cost"]):
                raise ValueError("Reviewed decision changed an original source row")
            validate_decision(override, model, targets.get(identifier))
            decisions[index] = override
            status[index].update(decision=override["decision"], reason=override["reason"])
        sources["reviewedDecisionsSha256"] = digest(reviewed_decisions)
    counts = Counter(row["decision"] for row in decisions)
    categories = {name: len({surface for (identifier, surface), values in model.members.items() if name in values})
                  for name in sorted(model.names)}
    summary = {"inputRows": len(rows), "inputSurfaces": len(wanted),
               "classifiedRows": sum(bool(row["lexeme_ids"]) for row in status),
               "classifiedInputSurfaces": len(wanted & set(by_surface)),
               "unresolvedRows": sum(not row["lexeme_ids"] for row in status),
               "includedRows": counts["include"], "excludedRows": counts["exclude"], "pendingRows": counts["pending"],
               "fallbackRows": counts["pending"],
               "lexemes": len({key[0] for key in model.forms}), "forms": len(model.forms),
               "memberships": sum(map(len, model.members.values())), "categorySurfaces": categories,
               "pendingEvidenceRecords": len(pending_evidence), "complete": counts["pending"] == 0}
    if corrections:
        summary["surfaceCorrections"] = len(corrections)
        summary["caseCandidateRows"] = sum(len(values) > 1 for values in targets.values())
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("Output already exists; use a new path to preserve earlier results")
    with tempfile.TemporaryDirectory(prefix=".lexicon-", dir=output.parent) as temporary:
        stage = Path(temporary) / "result"
        stage.mkdir()
        model.write(stage / "grammar")
        shutil.copyfile(inventory_path, stage / "inventory.jsonl")
        table(stage / "decisions.tsv", "decisions", decisions)
        if corrections:
            table(stage / "surface-corrections.tsv", "corrections", corrections)
        if reviewed_decisions:
            shutil.copyfile(reviewed_decisions, stage / "reviewed-overrides.tsv")
        jsonl(stage / "status.jsonl", status)
        jsonl(stage / "fallback.jsonl", [row for row, state in zip(rows, status) if state["decision"] == "pending"])
        jsonl(stage / "evidence.jsonl", [
            {"lexeme_id": key[0], "surface": key[1], "evidence": model.evidence[key]}
            for key in sorted(model.forms)])
        jsonl(stage / "pending-evidence.jsonl", pending_evidence)
        notices = stage / "notices"
        notices.mkdir()
        for name, content in notice_contents.items():
            (notices / name).write_bytes(content)
        files = {str(path.relative_to(stage)): digest(path) for path in sorted(stage.rglob("*")) if path.is_file()}
        manifest = {"schemaVersion": 1, "sources": sources, "summary": summary, "files": files}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        verify(stage)
        stage.rename(output)
    print(json.dumps(summary, sort_keys=True))
    return summary


def validate_decision(decision, model, effective_surface=None):
    surfaces = effective_surface or (decision["surface"],)
    if isinstance(surfaces, str):
        surfaces = (surfaces,)
    if surfaces != (decision["surface"],) and decision["decision"] != "include":
        raise ValueError("Surface corrections require an inclusion decision")
    if not decision["evidence"].startswith("https://"):
        raise ValueError("Reviewed decisions require evidence URLs")
    if decision["decision"] == "include":
        identifiers = decision["lexeme_ids"].split(',')
        if (decision["reason"] != "verified" or len(identifiers) != len(set(identifiers)) or
                any(not any((identifier, surface) in model.forms for surface in surfaces) for identifier in identifiers) or
                any(not any((identifier, surface) in model.forms for identifier in identifiers) for surface in surfaces)):
            raise ValueError("Invalid inclusion decision")
    elif decision["decision"] == "exclude":
        if decision["lexeme_ids"] != "-" or decision["reason"] not in EXCLUSION_REASONS:
            raise ValueError("Exclusion requires an explicit supported reason")
    else:
        raise ValueError("Reviewed overrides must be include or exclude")


def verify(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schemaVersion"] != 1:
        raise ValueError("Unsupported materialization manifest")
    actual = {str(path.relative_to(directory)) for path in directory.rglob("*") if path.is_file()} - {"manifest.json"}
    if actual != set(manifest["files"]):
        raise ValueError("Unexpected or missing materialization files")
    for relative, sha256 in manifest["files"].items():
        if digest(directory / relative) != sha256:
            raise ValueError(f"Changed materialization file: {relative}")
    rows = inventory(directory / "inventory.jsonl")
    if digest(directory / "inventory.jsonl") != manifest["sources"]["inventorySha256"]:
        raise ValueError("Inventory source hash mismatch")
    decisions = read_table(directory / "decisions.tsv", "decisions")
    with (directory / "status.jsonl").open(encoding="utf-8") as stream:
        states = [json.loads(line) for line in stream]
    with (directory / "fallback.jsonl").open(encoding="utf-8") as stream:
        fallback = [json.loads(line) for line in stream]
    if len(rows) != len(decisions) or len(rows) != len(states):
        raise ValueError("Every original input row needs a decision and status")
    model = Lexicon(directory / "grammar")
    by_surface = defaultdict(set)
    for identifier, surface in model.forms:
        by_surface[surface].add(identifier)
    correction_path = directory / "surface-corrections.tsv"
    corrections = read_table(correction_path, "corrections") if correction_path.is_file() else []
    targets = correction_targets(corrections, rows, model)
    for source, decision, state in zip(rows, decisions, states):
        effective_surfaces = targets.get(source["id"], (source["surface"],))
        state_surfaces = tuple(state.get("effective_surfaces", [state.get("effective_surface", source["surface"])]))
        if ({key: decision[key] for key in ("id", "reading", "surface")} !=
                {key: source[key] for key in ("id", "reading", "surface")} or
                int(decision["cost"]) != source["cost"] or
                any(state[key] != source[key] for key in source)):
            raise ValueError("Source inventory changed or reordered")
        if decision["decision"] not in {"include", "exclude", "pending"} or state["decision"] != decision["decision"]:
            raise ValueError("Invalid materialization decision")
        if (state_surfaces != effective_surfaces or
                len(effective_surfaces) > 1 and state.get("interpretation") not in {"case_candidates_not_disambiguated", 'input_spelling_candidates_not_disambiguated'} or
                state["lexeme_ids"] != sorted(set().union(*(by_surface.get(s, set()) for s in effective_surfaces))) or
                state["classification"] != ("classified" if state["lexeme_ids"] else "unresolved") or
                state["reason"] != decision["reason"]):
            raise ValueError("Classification status disagrees with the lexical data")
        for identifier in state["lexeme_ids"]:
            if not any((identifier, surface) in model.forms for surface in effective_surfaces):
                raise ValueError("Unknown status lexeme")
        if decision["decision"] != "pending":
            validate_decision(decision, model, effective_surfaces)
    summary = manifest["summary"]
    included = sum(row["decision"] == "include" for row in decisions)
    excluded = sum(row["decision"] == "exclude" for row in decisions)
    pending = sum(row["decision"] == "pending" for row in decisions)
    classified = sum(bool(row["lexeme_ids"]) for row in states)
    if fallback != [row for row, state in zip(rows, states) if state["decision"] == "pending"]:
        raise ValueError("Unreviewed fallback rows were lost, reordered or changed")
    category_counts = {name: len({surface for (_, surface), values in model.members.items() if name in values})
                       for name in sorted(model.names)}
    if (summary["inputRows"] != len(rows) or summary["includedRows"] != included or
            summary.get("surfaceCorrections", 0) != len(corrections) or
            summary.get("caseCandidateRows", 0) != sum(len(values) > 1 for values in targets.values()) or
            summary["pendingRows"] != pending or summary["classifiedRows"] != classified or
            summary["fallbackRows"] != len(fallback) or
            summary["unresolvedRows"] != len(rows) - classified or summary["complete"] != (pending == 0) or
            summary["inputSurfaces"] != len({row["surface"] for row in rows}) or
            summary["classifiedInputSurfaces"] != len(set(by_surface) & {row["surface"] for row in rows}) or
            summary["excludedRows"] != excluded or summary["forms"] != len(model.forms) or
            summary["lexemes"] != len({key[0] for key in model.forms}) or
            summary["categorySurfaces"] != category_counts or
            summary["memberships"] != sum(map(len, model.members.values()))):
        raise ValueError("Incorrect progress totals")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("build")
    for name in ("inventory", "source", "wordnet", "seed", "out"):
        command.add_argument("--" + name, type=Path, required=True)
    command.add_argument("--wiktextract", type=Path)
    command.add_argument("--wiktextract-sha256")
    command.add_argument("--wiktionary-dump-date")
    command.add_argument("--extractor-revision")
    command.add_argument("--reviewed-decisions", type=Path)
    command = commands.add_parser("verify")
    command.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        build(args)
    else:
        print(json.dumps(verify(args.directory), sort_keys=True))


if __name__ == "__main__":
    main()
