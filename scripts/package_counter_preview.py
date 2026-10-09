"""Package the tested .dat, editable sources and verification evidence for a preview release."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import zipfile


def package():
    source_commit = os.environ["GITHUB_SHA"]
    repository = os.environ["GITHUB_REPOSITORY"]
    run_url = f"https://github.com/{repository}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    reports = Path("build/reports/counter")
    build = json.loads((reports / "build.json").read_text())
    golden = json.loads((reports / "golden.json").read_text())
    suites = [ET.parse(p).getroot() for p in Path("build/test-results/counterTest").glob("TEST-*.xml")]
    tests = {key: sum(int(s.attrib[key]) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    assert tests["tests"] > 0 and tests["failures"] == tests["errors"] == tests["skipped"] == 0, tests
    assert golden["total"] > 0 and golden["failed"] == 0, golden
    dictionary = Path("src/main/resources/counter/counter_rules.dat").read_bytes()
    assert len(dictionary) == build["bytes"] and len(dictionary) <= 65536
    output = Path("build/counter-preview")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    dictionary_path = "app/src/main/assets/counter/counter_rules.dat"
    manifest = {
        "repository": repository,
        "sourceCommit": source_commit,
        "workflowRunUrl": run_url,
        "mozcCommit": os.environ["MOZC_COMMIT"],
        "dictionaryPathInZip": dictionary_path,
        "dictionarySha256": hashlib.sha256(dictionary).hexdigest(),
        "dictionaryBytes": len(dictionary),
        "build": build,
        "counterTests": tests,
        "goldenCases": golden,
        "androidDeviceVerified": False,
    }
    (output / "counter_rules.dat").write_bytes(dictionary)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme = f"""# 助数詞辞書の検証用成果物 / Counter dictionary preview

Source: https://github.com/{repository}/tree/{source_commit}
Actions: {run_url}

辞書 / Dictionary: `{dictionary_path}`
形式 / Format: JKCR v1; see docs/counter-dictionary.md.
SHA-256: {manifest['dictionarySha256']}
JUnit: {tests['tests']} passed; golden cases: {golden['total']} passed.

Kotlinソース・編集用TSV・説明資料・このActions実行のレポートを同梱しています。
このZIPは調査用資料です。CLIのビルド・実行は上記コミットのリポジトリで行ってください。
The ZIP includes Kotlin sources, editable TSVs, documentation, and reports from this run.
Build and run the CLI from the repository at the source commit above.

Android / Pixel 4 performance remains unverified.
連文節エンジンへの統合は含みません。Exact quantity/time API; no sentence-engine integration.
"""
    with zipfile.ZipFile(output / "counter_dictionary_preview.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(dictionary_path, dictionary)
        archive.writestr("manifest.json", (output / "manifest.json").read_bytes())
        archive.writestr("README.md", readme)
        for pattern in ("src/main/counter/*.tsv", "src/main/kotlin/counter/*.kt", "src/test/kotlin/counter/*.kt", "docs/counter*.md", "build/reports/counter/*.json", "build/test-results/counterTest/TEST-*.xml"):
            paths = sorted(Path(".").glob(pattern))
            assert paths, f"Missing preview inputs: {pattern}"
            for path in paths:
                archive.write(path, path.as_posix())
        archive.write("LICENSE", "LICENSE")
    with zipfile.ZipFile(output / "counter_dictionary_preview.zip") as archive:
        assert archive.read(dictionary_path) == dictionary
        assert archive.testzip() is None
    names = ("counter_rules.dat", "counter_dictionary_preview.zip", "manifest.json")
    (output / "SHA256SUMS").write_text("".join(f"{hashlib.sha256((output / name).read_bytes()).hexdigest()}  {name}\n" for name in names), encoding="utf-8")
    (output / "RELEASE_NOTES.md").write_text(
        f"助数詞辞書のマージ前検証用配布です。成果物は[GitHub Actions]({run_url})で生成・テストしています。\n\n"
        f"Pre-merge counter dictionary preview, built and tested by [GitHub Actions]({run_url}).\n\n"
        f"Source commit: `{source_commit}`\n\n"
        f"Dictionary: {len(dictionary):,} bytes; JUnit: {tests['tests']} passed; golden cases: {golden['total']} passed.\n\n"
        "`counter_rules.dat`は辞書本体、`counter_dictionary_preview.zip`はソース・説明・実行レポート付きです。\n\n"
        "Use `SHA256SUMS` to verify the downloads. Android/Pixel 4 performance and sentence-engine integration are not verified.\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    package()
