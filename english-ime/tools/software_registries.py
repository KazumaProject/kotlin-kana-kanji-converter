"""Join exact public registry labels without installing software or guessing POS.

Linguist labels and aliases describe language/format identifiers. Homebrew names
are registry display names, not a claim of vendor-canonical spelling. A registry
label does not establish corpus sense, countability, agreement or inflection.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
from wiktionary_index import Index

PINS = {
    "languages.yml": "a3b03a73993729c70c372984bc5469f9a1a041c5b6e992655a01df38f2ccc7a9",
    "languages.json": "e2a8e4833c97d1212263a6bafde657eeb5c4535e3d88fe26bff3c2d1afb41e83",
    "Linguist-MIT.txt": "7717070c5a8c85440ff2312930bb30dd19002ab5bc235c9800042767f6f5242f",
    "cask.json": "2bee08f2573cdbca45a1b5b11775797a0136864e5aec1a429717edf27c30fa49",
    "Homebrew-Cask-BSD-2-Clause.txt": "abd8be86c5738400f30c426bc88d90495b2dcfca9fe20b8d9b925599a55528b0",
}
LINGUIST_BLOB = "a670ffc0687f90c3af38d9d471a3d4615f4933d8"
LINGUIST_URL = "https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml"


def prepare(directory):
    raw = (directory / "languages.yml").read_bytes()
    if hashlib.sha1(b"blob " + str(len(raw)).encode() + b'\0' + raw).hexdigest() != LINGUIST_BLOB:
        raise ValueError("Unexpected Linguist Git blob")
    code = '''require "yaml"; require "json"
data=YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], permitted_symbols: [], aliases: false)
raise "Unexpected language mapping" unless data.is_a?(Hash) && data.keys.all? { |k| k.is_a?(String) }
puts JSON.generate(data)'''
    process = subprocess.run(["/usr/bin/ruby", "-e", code, str(directory / "languages.yml")], capture_output=True, text=True)
    if process.returncode:
        raise ValueError("Safe local YAML conversion failed: " + process.stderr[-1500:])
    normalized = (json.dumps(json.loads(process.stdout), sort_keys=True, ensure_ascii=False) + '\n').encode()
    if hashlib.sha256(normalized).hexdigest() != PINS["languages.json"]:
        raise ValueError("Unexpected normalized Linguist data")
    destination = directory / "languages.json"
    if destination.exists() and destination.read_bytes() != normalized:
        raise ValueError("Existing normalized source changed")
    if not destination.exists():
        destination.write_bytes(normalized)
    return load(directory)


def load(directory):
    for name, expected in PINS.items():
        if pipeline.digest(directory / name) != expected:
            raise ValueError("Changed registry snapshot or license: " + name)
    languages = json.loads((directory / "languages.json").read_text())
    casks = json.loads((directory / "cask.json").read_text())
    if len(languages) != 843 or len(casks) != 7807 or len({row['token'] for row in casks}) != len(casks):
        raise ValueError("Incomplete or duplicated registry source")
    return languages, casks


def attach(model, rows, languages, casks):
    wanted = {row["surface"].lower() for row in rows}
    relations = {(row['relation'], row['source'], row['target']) for row in model.relations}
    counts = Counter()
    for label, record in sorted(languages.items()):
        if label.lower() not in wanted:
            continue
        if record.get('type') not in {'programming', 'data', 'markup', 'prose'} or type(record.get('language_id')) is not int:
            raise ValueError("Unexpected language registry shape")
        values = {"identifier_computer_language", "domain_technology"}
        extension.ensure_categories(model, values)
        key = "registry-language-" + str(record['language_id'])
        model.add(key, label, label, values, {"source": "software_registry", "url": LINGUIST_URL,
            "registry": "github-linguist", "blobSha": LINGUIST_BLOB, "languageId": record['language_id'],
            "languageType": record['type'], "label": label, "scope": "registry_identifier_not_lexical_pos", "approved": True}, approved=True)
        counts['languageLabels'] += 1
        for original in rows:
            alias = original['reading']
            if (original['id'].startswith('manual:') and original['surface'] == label and alias in record.get('aliases', []) and
                    re.fullmatch(r'[a-z][a-z0-9_-]*', alias) and alias != label):
                relation = "input_alias", alias, label
                if relation not in relations:
                    model.relations.append(dict(zip(("relation", "source", "target", "evidence"), (*relation, LINGUIST_URL))))
                    relations.add(relation)
                    counts['declaredManualInputAliases'] += 1
    for record in sorted(casks, key=lambda value: value['token']):
        if record.get('tap') != 'homebrew/cask' or record.get('disabled') or record.get('deprecated'):
            continue
        for label in record['name']:
            if label.lower() not in wanted or not label.strip() or any(c in label for c in '\t\r\n'):
                continue
            commit = record.get('tap_git_head', '')
            source_path = record.get('ruby_source_path', '')
            if not re.fullmatch(r'[0-9a-f]{40}', commit) or not source_path.startswith('Casks/') or '..' in source_path:
                raise ValueError("Missing pinned Cask source path")
            url = 'https://github.com/Homebrew/homebrew-cask/blob/' + commit + '/' + source_path
            key = 'registry-cask-' + hashlib.sha256(json.dumps([record['token'], label]).encode()).hexdigest()[:24]
            model.add(key, label, label, {"name_product", "domain_technology"}, {
                "source": "software_registry", "url": url, "registry": "homebrew-cask", "token": record['token'],
                "label": label, "homepage": record.get('homepage'), "rubySourceSha256": record.get('ruby_source_checksum', {}).get('sha256'),
                "scope": "registry_display_name_not_vendor_canonical_spelling_or_lexical_pos", "approved": True}, approved=True)
            counts['softwareDisplayNames'] += 1
    return counts


def extend(args):
    languages, casks = load(args.sources)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    counts = attach(model, rows, languages, casks)
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    with (args.base / 'status.jsonl').open() as stream:
        states = [json.loads(line) for line in stream]
    unresolved = [row for row, state in zip(rows, states) if state['decision'] == 'pending' or row['id'] in reopened]
    index = Index(args.index)
    try:
        exact = {row['word'] for _, row in index.lookup({row['surface'] for row in unresolved})}
    finally:
        index.close()
    correction_path = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(correction_path, 'corrections') if correction_path.is_file() else []
    corrections += resolve_pending.cases(model, unresolved, exact)
    sources['softwareRegistries'] = {'files': PINS, 'linguistBlobSha': LINGUIST_BLOB,
        'policy': 'exact published labels only; active Casks; no vendor-casing, POS, countability or inflection inference; declared manual aliases must appear literally in Linguist aliases'}
    for name in ['Linguist-MIT.txt', 'Homebrew-Cask-BSD-2-Clause.txt']:
        notices[name] = (args.sources / name).read_bytes()
    notices['SOFTWARE-REGISTRY-CHANGES.txt'] = b'Selected exact registry labels and explicitly declared manual input aliases. Preserved source identifiers and case. No software installed; no binaries, generated extensions or inflections imported. Registry labels do not disambiguate the original corpus sense.\n'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.registry-review-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'
        pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, reopenedMachineExclusions=len(reopened), includedRows=summary['includedRows'],
                          excludedRows=summary['excludedRows'], pendingRows=summary['pendingRows']), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('prepare')
    command.add_argument('--sources', type=Path, required=True)
    command = commands.add_parser('extend')
    for name in ['base', 'seed', 'sources', 'index', 'out']:
        command.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        languages, casks = prepare(args.sources)
        print(json.dumps({'languages': len(languages), 'casks': len(casks)}))
    else:
        extend(args)
