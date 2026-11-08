"""Export adopted dictionary data for PR readers; verify it against real assets."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import tempfile

import catalog_harness as c
import vocabulary_harness as h

FIELDS = ['target_id', 'surface', 'kind', 'topics', 'change', 'lexeme_id', 'lemma', 'evidence', 'licenses', 'entities']


def assigned_topics(target, entry, topics):
    memberships = set(entry['categories'].split(','))
    return ','.join(t for t in target['topics'] if topics[t]['category'] in memberships) or '-'


def verify_rows(rows, topics, pairs, analyses):
    surfaces = {surface for _, surface in pairs}
    seen = set()
    for row in rows:
        identity = row['target_id'], row['lexeme_id'], row['surface']
        h.require(identity not in seen and row['kind'] in c.world_sources.KINDS, 'Duplicate/invalid adopted record')
        seen.add(identity)
        h.require(row['surface'] in surfaces, 'Adopted spelling absent from binary: ' + row['surface'])
        required = {topics[t]['category'] for t in row['topics'].split(',') if t != '-'}
        form = next((f for f in analyses.get(row['surface'], []) if f['lexeme_id'] == row['lexeme_id']), None)
        h.require(form and form['lemma'] == row['lemma'] and required <= form['memberships'],
            'Adopted form/topic absent from dictionary: ' + row['surface'])
        h.require(row['change'] in {'new_spelling', 'case_variant', 'new_form', 'metadata_only'} and
            row['evidence'].startswith('https://') and row['licenses'], 'Missing adoption provenance')


def read(path):
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        h.require(reader.fieldnames == FIELDS, 'Invalid adopted vocabulary header')
        return list(reader)


def summary(rows, topics):
    grouped = defaultdict(list)
    for row in rows:
        for topic in row['topics'].split(','):
            if topic != '-':
                grouped[topic].append(row)
    result = {}
    for topic, records in sorted(grouped.items()):
        added = {r['surface'] for r in records if r['change'] != 'metadata_only'}
        metadata = {r['surface'] for r in records if r['change'] == 'metadata_only'} - added
        result[topic] = dict(label=topics[topic]['label'], newSpellings=len(added), annotatedSpellings=len(metadata),
            spellings=len(added | metadata))
    added = {r['surface'] for r in rows if r['change'] != 'metadata_only'}
    metadata = {r['surface'] for r in rows if r['change'] == 'metadata_only'} - added
    return dict(newSpellings=len(added), annotatedSpellings=len(metadata), totalSpellings=len(added | metadata),
        records=len(rows), categories=result)


def markdown(rows, topics, counts):
    lines = ['| カテゴリ / Category | 追加表記 / New | 既存表記への付与 / Annotated |', '| --- | ---: | ---: |']
    for topic, values in counts['categories'].items():
        lines.append(f"| {values['label']} / `{topic}` | {values['newSpellings']} | {values['annotatedSpellings']} |")
    lines += ['', 'カテゴリは重複します。各行の合計は固有表記数ではありません。',
              'Categories overlap; category totals are not additive.', '']
    for topic, values in counts['categories'].items():
        records = [r for r in rows if topic in r['topics'].split(',')]
        added = {r['surface'] for r in records if r['change'] != 'metadata_only'}
        metadata = {r['surface'] for r in records if r['change'] == 'metadata_only'} - added
        lines += [f"<details><summary>{values['label']} / {topic} — {values['spellings']}表記</summary>", '',
            '**追加表記 / Added**', '', ', '.join('`' + word.replace('`', '\\`') + '`' for word in sorted(added)) or '—', '',
            '**既存表記へのカテゴリ付与 / Existing spellings annotated**', '',
            ', '.join('`' + word.replace('`', '\\`') + '`' for word in sorted(metadata)) or '—', '', '</details>', '']
    domain_only = sorted({r['surface'] for r in rows if r['topics'] == '-'})
    if domain_only:
        lines += ['Domain-only metadata / domainのみ付与: ' + ', '.join('`' + s + '`' for s in domain_only), '']
    return '\n'.join(lines)


def export(args):
    directory = h.external(args.work_dir)
    with h.lock(directory):
        config, connection = c.checked_state(directory)
        try:
            topics = config['topics']
            targets = {r['id']: r for r in h.json_lines(directory / 'targets.jsonl')}
            rows = []
            for stored in connection.execute("select payload,result from candidates where decision='include' order by position"):
                operation = json.loads(stored['payload'])
                h.validate_decisions([json.loads(stored['result'])], [operation])
                target = targets[operation['id']]
                for entry in operation['entries'] + operation.get('metadata', []):
                    rows.append(dict(target_id=operation['id'], surface=entry['surface'], kind=target['kind'],
                        topics=assigned_topics(target, entry, topics), change=operation['change'], lexeme_id=entry['lexeme_id'],
                        lemma=entry['lemma'], evidence=entry['evidence'],
                        licenses=','.join(sorted({p['license'] for p in operation['proofs']})),
                        entities=','.join(sorted({p['entity'] for p in operation['proofs'] if p.get('entity')})) or '-'))
        finally:
            connection.close()
        with tempfile.TemporaryDirectory(dir=directory) as temp:
            pairs, analyses = c.inventory(args.assets.resolve(), args.cli.resolve(), Path(temp) / 'inventory.jsonl')
        verify_rows(rows, topics, pairs, analyses)
        output = h.external(args.out)
        h.require(not output.is_relative_to(args.assets.resolve()), 'Review output must be outside dictionary assets')
        h.require(not output.exists(), 'Review export exists; use a new directory')
        output.mkdir(parents=True)
        rows.sort(key=lambda r: (r['surface'].casefold(), r['surface'], r['target_id'], r['lexeme_id']))
        c.table(output / 'adopted.tsv', FIELDS, rows)
        counts = summary(rows, topics)
        h.dump(output / 'counts.json', counts)
        (output / 'words.md').write_text(markdown(rows, topics, counts), encoding='utf-8')
        return counts


def verify(args):
    rows = read(args.ledger)
    topics, _ = c.registry(args.taxonomy, args.scopes)
    with tempfile.TemporaryDirectory() as temp:
        pairs, analyses = c.inventory(args.assets.resolve(), args.cli.resolve(), Path(temp) / 'inventory.jsonl')
    verify_rows(rows, topics, pairs, analyses)
    return summary(rows, topics)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    for name in ['export', 'verify']:
        parser = commands.add_parser(name)
        parser.add_argument('--assets', type=Path, required=True)
        parser.add_argument('--cli', type=Path, default=h.REPO / 'english-ime/build/install/english-ime/bin/english-ime')
        if name == 'export':
            parser.add_argument('--work-dir', type=Path, required=True)
            parser.add_argument('--out', type=Path, required=True)
        else:
            parser.add_argument('--ledger', type=Path, default=c.CATALOG / 'adopted-world.tsv')
            parser.add_argument('--taxonomy', type=Path, default=c.CATALOG / 'taxonomy.json')
            parser.add_argument('--scopes', type=Path, default=c.CATALOG / 'core-targets.json')
    args = p.parse_args()
    print(json.dumps(globals()[args.command](args), ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
