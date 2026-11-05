"""Classify exact existing manual command identifiers from pinned English docs.

Reads Markdown only. Commands are never executed. Templates, inferred aliases,
new input rows and lexical POS/inflection claims are outside this importer.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending

REVISION = '841ad2a521240271a190deaac1a5c2f95ae6a5de'
PINS = {'LICENSE.md': '826498c9793c53709035760c33bd6681e48380d34031320447febe675420ef4d',
        'english-page-hashes.json': '4ca400ec6fbf9d385657340c837f679cdd55d4b566d6f3eef4ed245afa3b3dff'}


def expressions(text):
    for line, value in enumerate(text.splitlines(), 1):
        if value.startswith('# '):
            yield line, value[2:], 'heading'
        elif (value.startswith('`') and value.endswith('`') and not value.startswith('```') and
              '{' not in value and '}' not in value):
            yield line, value[1:-1], 'literal_example'


def load(directory):
    for name, expected in PINS.items():
        if pipeline.digest(directory / name) != expected:
            raise ValueError('Changed tldr source or notice: ' + name)
    files = json.loads((directory / 'english-page-hashes.json').read_text())
    actual = {str(path.relative_to(directory)) for path in (directory / 'pages').rglob('*.md') if not path.is_symlink()}
    if len(files) != 7610 or set(files) != actual:
        raise ValueError('Incomplete or changed English page selection')
    for name, expected in files.items():
        if pipeline.digest(directory / name) != expected:
            raise ValueError('Changed English command page: ' + name)
    return files


def attach(model, rows, pages):
    wanted = {row['surface'] for row in rows if row['id'].startswith('manual:')}
    extension.ensure_categories(model, {'identifier_command_line'})
    counts = Counter()
    for filename, text, sha in pages:
        for line, value, kind in expressions(text):
            if value not in wanted:
                continue
            key = 'tldr-' + hashlib.sha256(json.dumps([filename, line, value]).encode()).hexdigest()[:24]
            proof = {'source': 'tldr_command', 'url': 'https://github.com/tldr-pages/tldr/blob/' + REVISION + '/' + filename + '#L' + str(line),
                     'revision': REVISION, 'file': filename, 'line': line, 'sha256': sha, 'kind': kind,
                     'scope': 'exact_existing_manual_command_identifier_not_lexical_POS_or_corpus_sense', 'approved': True}
            model.add(key, value, value, {'identifier_command_line', 'domain_technology'}, proof, approved=True)
            counts[kind] += 1
    return counts


def extend(args):
    files = load(args.sources)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    pages = ((name, (args.sources / name).read_text(), sha) for name, sha in sorted(files.items()))
    counts = attach(model, rows, pages)
    sources['tldrCommands'] = {'revision': REVISION, 'files': PINS, 'englishPages': len(files),
        'policy': 'exact headings or verbatim non-template code examples matching existing manual surfaces; no command execution, new inventory entries, inferred aliases or lexical POS'}
    notices['TLDR-LICENSE.md'] = (args.sources / 'LICENSE.md').read_bytes()
    notices['TLDR-CHANGES.txt'] = ('tldr-pages team and contributors, https://github.com/tldr-pages/tldr/tree/' + REVISION +
        '. English documentation is CC BY 4.0 (the scripts MIT license is not the documentation license). Selected exact command headings and non-template literal examples matching existing manual rows, with source file/line/hash. No commands executed, scripts imported, or POS/inflections inferred.\n').encode()
    if pipeline.digest(args.base / 'notices/CC-BY-4.0.txt') != '9ba9550ad48438d0836ddab3da480b3b69ffa0aac7b7878b5a0039e7ab429411':
        raise ValueError('Missing full CC BY 4.0 notice')
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.command-review-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'
        pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(counts, reopenedMachineExclusions=len(reopened),
        **{k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'sources', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
