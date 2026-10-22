#!/usr/bin/env python3
"""Export only standard-enabled person categories to a dictionary source file.

Classification workspaces are kept outside the repository. This command reads
those reviewed results and writes only category, reading, POS, cost, surface,
and sport tags for categories enabled by person-taxonomy.json.
"""
import argparse
import collections
import gzip
import hashlib
import json
import sys
import tempfile
from urllib.parse import urlsplit
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import review_person_classifications as reviews  # noqa: E402


def candidate_key(reading, surface):
    return hashlib.sha256((reading + "\0" + surface).encode("utf-8")).hexdigest()


def load_exclusions(path, root):
    path = path.resolve()
    root = root.resolve()
    if path == root or root in path.parents:
        raise ValueError("Restricted candidate exclusions must be outside the repository")
    allowed_categories = reviews.AGGREGATE_ONLY_CATEGORY_IDS | {"adult_related_hold"}
    excluded = {}
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"{path}:{number}: blank exclusion row")
            row = json.loads(line)
            if (not isinstance(row, dict)
                    or set(row) != {"candidate_key", "category_id"}
                    or not isinstance(row.get("candidate_key"), str)
                    or len(row["candidate_key"]) != 64
                    or any(c not in "0123456789abcdef" for c in row["candidate_key"])
                    or row.get("category_id") not in allowed_categories):
                raise ValueError(f"{path}:{number}: expected only candidate_key and a restricted category_id")
            key = row["candidate_key"]
            if key in excluded:
                raise ValueError(f"{path}:{number}: duplicate candidate key")
            excluded[key] = row["category_id"]
    if not excluded:
        raise ValueError("Restricted candidate exclusion file is empty")
    return excluded


def rows_by_key(paths, enabled_ids):
    """Read reviewed Gemini output; restricted and unresolved rows clear a key."""
    result = {}
    for path in paths:
        for row in reviews.read_jsonl(path):
            key = row.get("candidate_key")
            if not isinstance(key, str) or len(key) != 64:
                raise ValueError("Reviewed result has an invalid candidate key")
            category = row.get("category_id")
            if category in enabled_ids:
                result[key] = (
                    row["reading"], row["surface"], category,
                    set(row.get("sport_subcategories", [])),
                )
            else:
                result[key] = None
    return result


def restricted_proposal_keys(paths, category_by_code):
    """Keep Gemini's restricted-category proposals out of the fallback dictionary."""
    keys = set()
    for path in paths:
        for row in reviews.read_jsonl(path):
            code = row.get("category_code")
            category = category_by_code.get(code, {}).get("id")
            if category in reviews.AGGREGATE_ONLY_CATEGORY_IDS:
                key = row.get("candidate_key")
                if not isinstance(key, str) or len(key) != 64:
                    raise ValueError("Restricted Gemini proposal has an invalid candidate key")
                keys.add(key)
    return keys


def apply_person_additions(root, final, enabled):
    additions = {}
    additions_dir = root / "src/main/classification/person-additions"
    for path in sorted(additions_dir.glob("*.jsonl")):
        for (reading, surface), row in distribution.person_entries(root, path).items():
            key = candidate_key(reading, surface)
            if "sport" in row:
                sport = row["sport"]
                sports = row.get("sports", [sport])
                if (not isinstance(sports, list) or not sports
                        or any(value not in reviews.SPORT_LABELS for value in sports)
                        or len(sports) != len(set(sports)) or sport not in sports):
                    raise ValueError("A reviewed person addition has an unknown sport label")
                category = "sports"
                tags = set(sports)
            else:
                category = row["category_id"]
                if category not in enabled:
                    raise ValueError("A reviewed person addition uses a nonstandard category")
                tags = set()

            prior = additions.get(key)
            if prior is not None:
                if prior[2] != category:
                    raise ValueError("Reviewed person additions assign conflicting categories")
                tags.update(prior[3])
            additions[key] = (reading, surface, category, tags)

    for key, (reading, surface, category, tags) in additions.items():
        prior = final.get(key)
        if category == "sports" and prior is not None:
            tags.update(prior[3])
        if category == "thought" and prior and prior[2] not in (
                "thought", "personal_name_origin_unconfirmed"):
            raise ValueError("A category-specific person addition conflicts with a reviewed category")
        final[key] = (reading, surface, category, tags)


def export(args):
    exclusions = load_exclusions(args.excluded_candidates, args.root)
    taxonomy, category_by_code, category_by_id = reviews.taxonomy_maps(args.root / "src/main/classification/person-taxonomy.json")
    enabled = {row["id"] for row in taxonomy["categories"] if row.get("standard_enabled") is True}
    category_order = {row["id"]: row["number"] for row in taxonomy["categories"]}
    if len(enabled) != 23:
        raise ValueError("Expected exactly 23 standard-enabled person categories")

    overrides = reviews.load_overrides(
        args.root / "src/main/classification/person-category-overrides.jsonl",
        category_by_id,
        reviews.AGGREGATE_ONLY_CATEGORY_IDS,
    )

    with tempfile.TemporaryDirectory(prefix="person-dictionary-review-") as temp:
        temporary = Path(temp)
        initial_dir = temporary / "initial"
        recovery_dir = temporary / "recovery"
        reviews.review_gemini_results(
            args.gemini_results, initial_dir, overrides,
            category_by_id, category_by_code, require_all=True,
        )
        reviews.review_gemini_results(
            args.recovery_gemini_results, recovery_dir, overrides,
            category_by_id, category_by_code, require_all=False,
        )

        decisions = list(reviews.read_jsonl(args.source_decisions))
        confirmed_performers = {
            row["candidate_key"] for row in decisions
            if row.get("category_id") == "adult_performer"
            and row.get("status") == "adult_performer_source_confirmed"
        }
        excluded_performers = {
            key for key, category in exclusions.items()
            if category == "adult_performer"
        }
        if not confirmed_performers or excluded_performers != confirmed_performers:
            raise ValueError(
                "Adult performer exclusion hashes must exactly match source-confirmed adult performer decisions")
        for row in decisions:
            if row.get("candidate_key") in confirmed_performers and row["candidate_key"] != candidate_key(
                    row.get("reading", ""), row.get("surface", "")):
                raise ValueError("Adult performer source decision key does not match its reading and surface")
        sport_qids = reviews.wikidata_sports_by_qid(args.wikidata_sports)
        reviewed, changes, before, after, _, _ = reviews.source_review(
            decisions, sport_qids, category_by_code,
            reviews.AGGREGATE_ONLY_CATEGORY_IDS,
        )
        decision_overrides = {
            key: value for key, value in overrides.items()
            if key in {row["candidate_key"] for row in reviewed}
        }
        reviews.apply_source_overrides(
            reviewed, decision_overrides, category_by_id, category_by_code,
            changes, after,
        )

        initial = rows_by_key(sorted(initial_dir.glob("*.jsonl")), enabled)
        final = {key: value for key, value in initial.items() if value is not None}
        for key, value in rows_by_key(sorted(recovery_dir.glob("*.jsonl")), enabled).items():
            if value is None:
                final.pop(key, None)
            else:
                final[key] = value

        # The source review is the final authority for its candidate set. A
        # restricted or unresolved decision removes any earlier model label.
        source_approved_keys = set()
        for row in reviewed:
            key = row["candidate_key"]
            category = row.get("category_id")
            if category in enabled:
                final[key] = (
                    row["reading"], row["surface"], category,
                    set(row.get("sport_subcategories", [])),
                )
                source_approved_keys.add(key)
            else:
                final.pop(key, None)

        restricted_source_keys = {
            row["candidate_key"] for row in reviewed
            if row.get("category_id") in reviews.AGGREGATE_ONLY_CATEGORY_IDS
        }
        adult_related_source_keys = {
            row["candidate_key"] for row in decisions
            if str(row.get("status", "")).startswith("adult_related_")
        }
        if any(not isinstance(key, str) or len(key) != 64
               for key in adult_related_source_keys):
            raise ValueError("Adult-related source decision has an invalid candidate key")
        excluded_adult_hold_keys = {
            key for key, category in exclusions.items()
            if category == "adult_related_hold"
        }
        if not adult_related_source_keys <= excluded_adult_hold_keys:
            raise ValueError("External exclusions omit adult-related source-review candidates")
        restricted_source_keys.update(adult_related_source_keys)
        restricted_gemini_keys = restricted_proposal_keys(
            [*sorted(args.gemini_results.glob("*.jsonl")),
             *sorted(args.recovery_gemini_results.glob("*.jsonl"))],
            category_by_code,
        )
        for key in restricted_gemini_keys - source_approved_keys:
            final.pop(key, None)

    apply_person_additions(args.root, final, enabled)

    records_by_pair = defaultdict(list)
    source_keys = set()
    with gzip.open(args.root / "src/main/classification/distribution-candidates.tsv.gz", "rt", encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 6:
                raise ValueError(f"Malformed classified dictionary source row {number}")
            if fields[0] != "person":
                continue
            reading, surface = fields[1], fields[5]
            key = candidate_key(reading, surface)
            source_keys.add(key)
            if key in final:
                records_by_pair[key].append(fields[1:])

    unknown_exclusions = set(exclusions) - source_keys
    if unknown_exclusions:
        raise ValueError(f"Restricted candidate exclusion file contains {len(unknown_exclusions)} keys absent from the person source")

    # Hash-only restricted and adult-related exclusions take precedence over
    # model and source-review classifications so no individual names enter the
    # distributable person dictionary.
    for key in exclusions:
        final.pop(key, None)

    unresolved_keys = (source_keys - set(final) - set(exclusions)
                       - restricted_source_keys - restricted_gemini_keys)
    ime_filtered_keys = set()
    for key, (reading, surface, _, _) in list(final.items()):
        if reviews.ime_candidate_issue(reading, surface):
            final.pop(key)
            records_by_pair.pop(key, None)
            ime_filtered_keys.add(key)

    output_rows = []
    matched = set()
    for key, (reading, surface, category, tags) in final.items():
        if category not in enabled:
            raise ValueError("A nonstandard category reached the distribution exporter")
        sport_ids = sorted(tags)
        if not set(sport_ids) <= set(reviews.SPORT_LABELS):
            raise ValueError("A reviewed sports record has an unknown sport subcategory")
        for fields in records_by_pair.get(key, []):
            if fields[0] != reading or fields[4] != surface:
                raise ValueError("Candidate key does not match the dictionary source pair")
            output_rows.append((
                category, reading, int(fields[1]), int(fields[2]),
                int(fields[3]), surface, ",".join(sport_ids),
            ))
            matched.add(key)

    if not output_rows:
        raise ValueError("No standard-enabled person dictionary rows were produced")

    output_rows.sort(key=lambda row: (
        category_order[row[0]], len(row[1]), row[1], row[5], row[2], row[3], row[4], row[6],
    ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary_output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            for row in output_rows:
                line = "\t".join(map(str, row)) + "\n"
                compressed.write(line.encode("utf-8"))
    temporary_output.replace(args.output)

    print(json.dumps({
        "enabledCategories": len(enabled),
        "nonemptyCategories": len({row[0] for row in output_rows}),
        "dictionaryPairs": len(matched),
        "dictionaryRecords": len(output_rows),
        "unclassifiedExcludedPairs": len(unresolved_keys),
        "imeFormatExcludedPairs": len(ime_filtered_keys),
        "adultRelatedSourceExcludedPairs": len(adult_related_source_keys),
        "excludedCandidateCounts": dict(sorted(collections.Counter(exclusions.values()).items())),
        "sourceSha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    }, ensure_ascii=False, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-decisions", type=Path, required=True)
    parser.add_argument("--wikidata-sports", type=Path, required=True)
    parser.add_argument("--gemini-results", type=Path, required=True)
    parser.add_argument("--recovery-gemini-results", type=Path, required=True)
    parser.add_argument("--excluded-candidates", type=Path, required=True,
                        help="External JSONL of candidate_key/category_id rows; restricted candidates never enter the dictionary")
    parser.add_argument("--output", type=Path, required=True)
    export(parser.parse_args())


if __name__ == "__main__":
    main()
