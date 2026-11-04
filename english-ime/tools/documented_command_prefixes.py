"""Resolve existing manual command prefixes against literal documentation.

Expand only explicitly enumerated literal alternatives. Stop at the first
variable placeholder. A prefix is not represented as a complete executable
command, and no argument value, shell alias or option combination is inferred.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import tldr_commands as tldr


def literal_choices(token):
    if token.startswith('[') and token.endswith(']'):
        values = token[1:-1].split('|')
        if len(values) == 1 and not values[0].startswith('-'):
            return []  # An optional parameter name is not a literal argument.
    elif '|' in token and all(value.startswith('-') for value in token.split('|')):
        values = token.split('|')
    else:
        return []
    # Multi-token alternatives such as `-l --all` are explicitly documented,
    # rather than a flag combination invented by this importer.
    return values if all(re.fullmatch(r'[A-Za-z0-9_./+\-=:,]+(?: [A-Za-z0-9_./+\-=:,]+)*',value) for value in values) else []


def literal_prefixes(text):
    for line, value in enumerate(text.splitlines(), 1):
        if not (value.startswith('`') and value.endswith('`') and not value.startswith('```')):
            continue
        expression = value[1:-1]
        prefixes = ['']
        position = 0
        variable = False
        for match in re.finditer(r'\{\{([^{}]*)\}\}', expression):
            before = expression[position:match.start()]
            prefixes = [prefix + before for prefix in prefixes]
            token = match[1]
            choices = literal_choices(token)
            if not choices:
                # A quote opened immediately around an unspecified argument is
                # not itself part of the documented command prefix.
                prefixes = [prefix[:-1] if prefix.endswith(('"', "'")) else prefix for prefix in prefixes]
                variable = True
                break
            if len(prefixes) * len(choices) > 1024:
                prefixes = []
                break
            prefixes = [prefix + choice for prefix in prefixes for choice in choices]
            position = match.end()
        if not variable:
            prefixes = [prefix + expression[position:] for prefix in prefixes]
        for prefix in sorted(set(value.rstrip() for value in prefixes)):
            if prefix and '{{' not in prefix and '}}' not in prefix:
                yield line, prefix, expression, variable


def attach(model, rows, pages):
    wanted = {row['surface'] for row in rows if row['id'].startswith('manual:')}
    extension.ensure_categories(model, {'identifier_command_prefix'})
    adopted = set()
    for filename, text, sha in pages:
        for line, prefix, template, variable in literal_prefixes(text):
            for surface in sorted(wanted):
                # Only complete literal tokens; never the first characters of
                # an option, path, command or other token.
                if surface != prefix and not prefix.startswith(surface + ' '):
                    continue
                key = 'tldr-prefix-' + hashlib.sha256(json.dumps([filename, line, surface, prefix]).encode()).hexdigest()[:24]
                proof = {'source': 'documented_command_prefix', 'url': 'https://github.com/tldr-pages/tldr/blob/' + tldr.REVISION + '/' + filename + '#L' + str(line),
                    'revision': tldr.REVISION, 'file': filename, 'line': line, 'sha256': sha,
                    'template': template, 'literalPrefix': prefix, 'completionRequired': variable or surface != prefix,
                    'scope': 'existing manual prefix of literal documentation tokens with explicit alternatives only; no execution, argument substitution, option combination, lexical POS or completeness claim', 'approved': True}
                model.add(key, surface, surface, {'identifier_command_prefix', 'domain_technology'}, proof, approved=True)
                adopted.add(surface)
    return adopted


def extend(args):
    files = tldr.load(args.sources)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    states = [json.loads(x) for x in (args.base / 'status.jsonl').read_text().splitlines()]
    selected = [row for row, state in zip(rows, states) if state['decision'] == 'pending']
    pages = ((name, (args.sources / name).read_text(), sha) for name, sha in sorted(files.items()))
    adopted = attach(model, selected, pages)
    sources['documentedCommandPrefixes'] = {'revision': tldr.REVISION, 'files': tldr.PINS,
        'policy': 'existing manual surfaces matching whole literal tokens before a variable placeholder; expand explicit alternatives only; command prefix category with completion flag; never execute commands or infer option combinations/argument values'}
    notices['TLDR-PREFIX-CHANGES.txt'] = ('tldr-pages contributors, CC BY 4.0; source and license retained in TLDR-LICENSE.md.\n'
        'Additional changes: selected existing manual command prefixes from literal example tokens, expanding explicit enumerated choices only. Preserve original templates/file/line/hash and completion-required status. No commands executed and no lexical POS inferred.\n').encode()
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    prior = args.base / 'reviewed-overrides.tsv'
    summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
        reviewed_decisions=prior if prior.is_file() else None, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(newCommandPrefixSurfaces=len(adopted), **{k: summary[k] for k in ['includedRows','excludedRows','pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'sources', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
