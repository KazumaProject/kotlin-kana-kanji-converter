"""Run the installed CLI against the regenerated, hash-verified reviewed dictionary."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def invoke(cli, assets, text, *options):
    return subprocess.run(
        [str(cli), "convert", "--assets", str(assets), "--text", text, *options],
        capture_output=True, text=True, timeout=30,
    )


def read_conversion(cli, assets, text, *options):
    result = invoke(cli, assets, text, "--format", "json", *options)
    assert result.returncode == 0, (assets, text, options, result.stderr)
    output = json.loads(result.stdout)
    assert output["schemaVersion"] == 1 and output["input"] == text, output
    candidates = output["candidates"]
    assert candidates and len({row["text"] for row in candidates}) == len(candidates), candidates
    assert [row["rank"] for row in candidates] == list(range(1, len(candidates) + 1)), candidates
    length = len(text.encode("utf-16-le")) // 2
    for row in candidates:
        segments = row["segments"]
        assert segments and segments[0]["start"] == 0 and segments[-1]["end"] == length, row
        assert all(0 <= segment["start"] < segment["end"] <= length for segment in segments), row
        assert all(a["end"] == b["start"] for a, b in zip(segments, segments[1:])), row
        assert "".join((" " if segment["inferredSpace"] else "") + segment["surface"]
                       for segment in segments) == row["text"], row
    return output


def verify(cli, assets, supplement=False, *, reference_assets=None, inputs=None):
    def candidates(text, *options):
        actual = read_conversion(cli, assets, text, *options)
        if reference_assets is not None:
            reference = read_conversion(cli, reference_assets, text, *options)
            assert actual == reference, (
                f"Conversion differs from {reference_assets} for {text!r} {options}",
                reference, actual,
            )
        return actual["candidates"]

    if inputs is not None:
        for text in inputs:
            for mode in ("exact", "prefix"):
                candidates(text, "--mode", mode)
        print(f"English conversion CLI checks passed for {len(inputs)} inputs in both modes.")
        return

    def first(text, expected, *reasons, options=()):
        row = candidates(text, *options)[0]
        assert row["text"] == expected and set(reasons) <= set(row["reasons"]), row
        return row

    if supplement:
        for typed, expected in [
            ("yall", "y'all"),
            ("annualize", "annualize"),
            ("autofill", "autofill"),
            ("esim", "eSIM"),
            ("carryon", "carry-on"),
            ("twofactorauthentication", "two-factor authentication"),
            ("two-factor authentication", "two-factor authentication"),
        ]:
            values = candidates(typed)
            assert any(row["text"] == expected and len(row["segments"]) == 1 and
                       row["segments"][0]["kind"] == "exact" for row in values), (typed, values)
        print("Supplementary English vocabulary CLI checks passed.")

    joined = first("hecantake", "he can take", "FINITE_THIRD_SINGULAR", "BARE_AFTER_MODAL_OR_DO")
    assert [(s["start"], s["end"], s["reading"]) for s in joined["segments"]] == [
        (0, 2, "he"), (2, 5, "can"), (5, 9, "take"),
    ], joined
    assert joined["dictionaryCost"] == 4669, joined
    first("hecantake it!", "he can take it!", "BARE_AFTER_MODAL_OR_DO")

    progressive = candidates("its working")
    possessive = candidates("the dog chased its tail")
    assert progressive[0]["text"] == "it's working", progressive
    assert "BE_COMPLEMENT" in progressive[0]["reasons"], progressive[0]
    literal = next(row for row in progressive if row["text"] == "its working")
    assert progressive[0]["dictionaryCost"] > literal["dictionaryCost"], progressive
    assert possessive[0]["text"] == "the dog chased its tail", possessive
    assert any(row["text"] == "the dog chased it's tail" for row in possessive), possessive

    prefix = first("he tak", "he takes", "FINITE_THIRD_SINGULAR", options=("--mode", "prefix"))
    assert prefix["segments"][-1]["kind"] == "completion" and prefix["segments"][-1]["reading"] == "takes", prefix
    first("they tak", "they take", "FINITE_OTHER", options=("--mode", "prefix"))
    first("he has tak", "he has taken", "PERFECT_PARTICIPLE", options=("--mode", "prefix"))
    first("hecantak", "he can take", "BARE_AFTER_MODAL_OR_DO", options=("--mode", "prefix"))
    for typed, expected, max_rank in [
        ("wo", "would", 5), ("wh", "which", 10), ("ple", "please", 5),
        ("trav", "travel", 5), ("resch", "reschedule", 5),
    ]:
        result = candidates(typed, "--mode", "prefix")[:max_rank]
        assert any(row["text"] == expected for row in result), (typed, result)
    for typed, expected in [("don'", "don't"), ("don’", "don't"), ("wi-", "Wi-Fi")]:
        result = first(typed, expected, options=("--mode", "prefix"))
        assert result["segments"][0]["kind"] == "completion" and len(result["segments"]) == 1, result
        assert all(s["kind"] != "completion" for row in candidates(typed) for s in row["segments"])
    exact = candidates("he take", "--limit", "50")
    assert exact[0]["text"] == "he take" and not any(row["text"] == "he takes" for row in exact), exact
    assert all(s["kind"] != "completion" for row in candidates("he tak!", "--mode", "prefix")
               for s in row["segments"])

    first("the list of items is ready", "the list of items is ready",
          "PREPOSITIONAL_PHRASE", "FINITE_THIRD_SINGULAR")
    first("he said that she is ready", "he said that she is ready", "SUBORDINATE_CLAUSE", "BE_COMPLEMENT")
    first("he said that she are ready", "he said that she are ready",
          "SUBORDINATE_CLAUSE", "EXPECTED_FINITE_THIRD_SINGULAR")
    first("do they take it?", "do they take it?", "QUESTION_INVERSION", "BARE_AFTER_MODAL_OR_DO")
    first("he cant take", "he can't take", "BARE_AFTER_MODAL_OR_DO")
    first("were ready", "we're ready", "BE_COMPLEMENT")
    first("they were ready", "they were ready", "FINITE_OTHER", "BE_COMPLEMENT")

    phrases = candidates("google maps")
    named = next(row for row in phrases if row["text"] == "Google Maps")
    assert len(named["segments"]) == 1 and named["segments"][0]["reading"] == "google maps", named
    first("qqzxv, Wi-Fi!", "qqzxv, Wi-Fi!")
    first("🐈, Wi-Fi!", "🐈, Wi-Fi!")
    first("he  can\ttake!", "he  can\ttake!", "BARE_AFTER_MODAL_OR_DO")
    first("therapist", "therapist")
    result = invoke(cli, assets, "hecantake", "--limit", "1")
    assert result.returncode == 0 and len(result.stdout.splitlines()) == 1, result
    assert result.stdout.startswith("1\the can take\t4669\t"), result.stdout

    with tempfile.TemporaryDirectory() as directory:
        missing = invoke(cli, directory, "take")
        assert missing.returncode != 0 and "bundle.properties" in missing.stderr and not missing.stdout, missing
        path = Path(directory)
        (path / "grammar").symlink_to(assets / "grammar", target_is_directory=True)
        (path / "reading.dat").write_bytes(b"bad payload")
        corrupt = invoke(cli, directory, "take")
        assert corrupt.returncode != 0 and "reading.dat" in corrupt.stderr and not corrupt.stdout, corrupt

    print("Reviewed English conversion CLI checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--assets", required=True, type=Path)
    parser.add_argument("--supplement", action="store_true", help="Check the extended bundle")
    parser.add_argument("--reference-assets", type=Path, help="Compare complete JSON results with this bundle")
    parser.add_argument("--inputs", type=Path, help="UTF-8 JSON array of inputs to test in exact and prefix modes")
    args = parser.parse_args()
    inputs = None
    if args.inputs is not None:
        if args.supplement:
            parser.error("--inputs and --supplement select different test sets")
        try:
            inputs = json.loads(args.inputs.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            parser.error(str(error))
        if not isinstance(inputs, list) or not inputs or not all(isinstance(text, str) and text.strip() for text in inputs):
            parser.error("--inputs must contain a non-empty JSON array of nonblank strings")
    verify(args.cli.resolve(), args.assets.resolve(), args.supplement,
           reference_assets=args.reference_assets.resolve() if args.reference_assets else None, inputs=inputs)
