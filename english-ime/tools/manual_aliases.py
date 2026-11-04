"""Review existing literal input aliases, never infer new ones from a spelling."""
import argparse
import json
from pathlib import Path
import re

import extend_lexicon as extension
import lexicon_pipeline as pipeline

MANUAL_SHA256 = '60dcfc1e3b7874fed45c1641c59c82d8b40a4999d8abab200cd97fd4204f246b'
REVISION = '49403f28e24ba57e695b0559fe4e50efd86f4bb9'
EXPECTED = {'manual:890': ('cplusplus', 'C++', 10000),
            'manual:359': ('cloudflarworkers', 'CloudflareWorkers', 12000),
            'manual:1536': ('httpie', 'http', 8000),
            'manual:1537': ('bottom', 'btm', 8000)}


def attach(model, rows, source, pending):
    if pipeline.digest(source) != MANUAL_SHA256:
        raise ValueError('Legacy manual input source changed')
    text = source.read_text()
    literals = {}
    pattern = r'Dictionary\(reading = "([^"\n]+)", cost = (\d+)\.toShort\(\), word = "([^"\n]+)", withUpperCase = (true|false)\)'
    for match in re.finditer(pattern, text):
        reading, cost, surface, _ = match.groups()
        literals[reading, surface, int(cost)] = text.count('\n', 0, match.start()) + 1
    actual = {row['id']: row for row in rows}
    known = {(r['relation'], r['source'], r['target']) for r in model.relations}
    for identifier, expected in EXPECTED.items():
        row = actual[identifier]
        if ((row['reading'], row['surface'], row['cost']) != expected or expected not in literals or
                not model.approved.get(row['surface'])):
            raise ValueError('Input alias requires its original literal mapping and an independently approved target')
        url = ('https://github.com/KazumaProject/kotlin-kana-kanji-converter/blob/' + REVISION +
               '/english-ime/src/main/kotlin/Manual.kt#L' + str(literals[expected]))
        key = 'input_alias', row['reading'], row['surface']
        if key not in known:
            model.relations.append(dict(zip(['relation', 'source', 'target', 'evidence'], [*key, url])))
            known.add(key)
        pending.append({'sourceId': identifier, 'surface': row['surface'], 'reason': 'verified_legacy_literal_input_alias',
                        'reading': row['reading'], 'wordAccepted': True, 'manualSourceSha256': MANUAL_SHA256,
                        'evidence': {'url': url}, 'standardKeyboardKey': pipeline.keyboard_reading(row['surface']),
                        'scope': 'preserve the existing literal input key even when its spelling is unusual; no claim it is intentional or standard; no original row change, lexical synonym or inflection claim'})


def extend(args):
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    attach(model, rows, args.manual_source, pending)
    sources['verifiedLegacyManualAliases'] = {'sourceSha256': MANUAL_SHA256, 'revision': REVISION,
        'ids': sorted(EXPECTED), 'policy': 'exact existing literal reading/output/cost in pinned Manual.kt; independently approved target required; no invented aliases'}
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    prior = args.base / 'reviewed-overrides.tsv'
    summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
        reviewed_decisions=prior if prior.is_file() else None, allow_input_spellings=True, corrections=corrections)
    print(json.dumps({k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'manual-source', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
