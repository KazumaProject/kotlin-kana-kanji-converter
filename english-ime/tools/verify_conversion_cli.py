"""Run the installed CLI against the regenerated, hash-verified reviewed dictionary."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def verify(cli, assets):
    def invoke(text, *options, directory=assets):
        return subprocess.run(
            [str(cli), "convert", "--assets", str(directory), "--text", text, *options],
            capture_output=True, text=True, timeout=30,
        )

    def candidates(text, *options):
        result = invoke(text, "--format", "json", *options)
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout)
        assert output["schemaVersion"] == 1 and output["input"] == text, output
        values = output["candidates"]
        assert values and len({row["text"] for row in values}) == len(values), values
        assert [row["rank"] for row in values] == list(range(1, len(values) + 1)), values
        for row in values:
            segments = row["segments"]
            assert segments[0]["start"] == 0 and segments[-1]["end"] == len(text.encode("utf-16-le")) // 2, row
            assert all(a["end"] == b["start"] for a, b in zip(segments, segments[1:])), row
            assert "".join((" " if segment["inferredSpace"] else "") + segment["surface"]
                           for segment in segments) == row["text"], row
        return values

    def first(text, expected, *reasons, options=()):
        row = candidates(text, *options)[0]
        assert row["text"] == expected and set(reasons) <= set(row["reasons"]), row
        return row

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
    result = invoke("hecantake", "--limit", "1")
    assert result.returncode == 0 and len(result.stdout.splitlines()) == 1, result
    assert result.stdout.startswith("1\the can take\t4669\t"), result.stdout

    with tempfile.TemporaryDirectory() as directory:
        missing = invoke("take", directory=directory)
        assert missing.returncode != 0 and "bundle.properties" in missing.stderr and not missing.stdout, missing
        path = Path(directory)
        (path / "grammar").symlink_to(assets / "grammar", target_is_directory=True)
        (path / "reading.dat").write_bytes(b"bad payload")
        corrupt = invoke("take", directory=directory)
        assert corrupt.returncode != 0 and "reading.dat" in corrupt.stderr and not corrupt.stdout, corrupt

    print("Reviewed English conversion CLI checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--assets", required=True, type=Path)
    args = parser.parse_args()
    verify(args.cli.resolve(), args.assets.resolve())
