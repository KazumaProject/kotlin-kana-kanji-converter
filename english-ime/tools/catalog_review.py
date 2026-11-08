"""Export adopted dictionary data for PR readers; verify it against real assets."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import re
import tempfile

import catalog_harness as c
import vocabulary_harness as h
import distribution_policy

FIELDS = ['target_id', 'surface', 'kind', 'topics', 'change', 'lexeme_id', 'lemma', 'evidence', 'licenses', 'entities']
WORD_FIELDS = ['surface', 'change', 'kinds']


def assigned_topics(target, entry, topics):
    memberships = set(entry['categories'].split(','))
    return ','.join(t for t in target['topics'] if topics[t]['category'] in memberships) or '-'


def verify_rows(rows, topics, pairs, analyses, blocked=frozenset()):
    surfaces = {surface for _, surface in pairs}
    seen = set()
    for row in rows:
        identity = row['target_id'], row['lexeme_id'], row['surface']
        h.require(identity not in seen and row['kind'] in c.world_sources.KINDS, 'Duplicate/invalid adopted record')
        seen.add(identity)
        if distribution_policy.excluded(row['surface'],row['surface'],blocked):
            h.require(row['surface'] not in surfaces and not analyses.get(row['surface']),
                      'Restricted authoring record leaked into distribution: '+row['surface'])
            continue
        if distribution_policy.excluded(row['lemma'],row['lemma'],blocked):
            remaining=analyses.get(row['surface'],[])
            h.require(not any(f['lexeme_id']==row['lexeme_id'] or distribution_policy.excluded(row['surface'],f['lemma'],blocked)
                for f in remaining),'Restricted lexical analysis leaked into distribution: '+row['surface'])
            h.require(row['surface'] not in surfaces or remaining,'Restricted orphan candidate leaked into distribution: '+row['surface'])
            continue
        h.require(row['surface'] in surfaces, 'Adopted spelling absent from binary: ' + row['surface'])
        required = {topics[t]['category'] for t in row['topics'].split(',') if t != '-'}
        form = next((f for f in analyses.get(row['surface'], []) if f['lexeme_id'] == row['lexeme_id']), None)
        h.require(form and form['lemma'] == row['lemma'] and required <= form['memberships'],
            'Adopted form/topic absent from dictionary: ' + row['surface'])
        h.require(row['change'] in {'new_spelling', 'case_variant', 'new_form', 'metadata_only'} and
            row['evidence'].startswith('https://') and row['licenses'], 'Missing adoption provenance')


def read(path):
    if path.is_dir():
        index=h.replay.read_json(path/'index.json')
        h.require(index['schemaVersion']==1 and set(p.name for p in path.iterdir())=={'index.json',*index['files']},
            'Missing/unexpected adoption ledger shard')
        result=[]
        for name,record in sorted(index['files'].items()):
            h.require(re.fullmatch(r'part-[0-9]{4}\.tsv',name) and not (path/name).is_symlink() and
                h.replay.sha(path/name)==record['sha256'],'Changed adoption ledger shard')
            rows=read(path/name);h.require(len(rows)==record['rows'],'Changed adoption ledger row count');result.extend(rows)
        return result
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
    blocked=distribution_policy.for_assets(args.assets.resolve())
    verify_rows(rows, topics, pairs, analyses, blocked)
    verify_pages(args.word_lists, rows, topics)
    if getattr(args,'goals',None):verify_goals(h.replay.read_json(args.goals),topics,pairs,analyses,blocked)
    return summary(rows, topics)


def verify_goals(goals,topics,pairs,analyses,blocked):
    """Public artifact gates; source exhaustion remains a separate capture audit."""
    surfaces={s for _,s in pairs}
    for topic,words in goals['requiredSpellings'].items():
        category=topics[topic]['category']
        for word in words:
            h.require(word in surfaces and any(category in f['memberships'] for f in analyses.get(word,[])),
                'Missing required spelling/topic: '+topic+'/'+word)
    h.require(set(goals['preserveMedicalSpellings'])<=surfaces,'Missing protected ordinary/medical vocabulary')
    h.require(all(distribution_policy.excluded(s,s,blocked) for s in goals.get('requiredExclusionSpellings',[])),
        'Missing required distribution exclusion')
    h.require(not any(distribution_policy.excluded(s,s,blocked) for s in surfaces),'Restricted candidate leaked')
    if goals.get('requireNonemptyTopics'):
        represented={m for s,forms in analyses.items() if s in surfaces for f in forms for m in f['memberships']}
        h.require(all(v['category'] in represented for v in topics.values()),'Empty declared vocabulary topic')


def word_pages(rows, topics):
    pages = {}
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        for topic in row['topics'].split(','):
            if topic != '-':
                h.require(topic in topics and re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*', topic),
                          'Invalid vocabulary page topic')
                grouped[topic][row['surface']].append(row)
    for topic, words in sorted(grouped.items()):
        records = [dict(surface=s, change='metadata_only' if all(r['change'] == 'metadata_only' for r in rr) else 'added',
                        kinds=','.join(sorted({r['kind'] for r in rr})))
                   for s, rr in sorted(words.items(), key=lambda p: (p[0].casefold(), p[0]))]
        for start in range(0, len(records), 500):
            name = topic + '-' + str(start // 500 + 1).zfill(3) + '.tsv'
            pages[name] = records[start:start + 500]
    return pages


def verify_pages(directory, rows, topics):
    expected = word_pages(rows, topics)
    h.require(directory.is_dir() and {p.name for p in directory.iterdir()} == set(expected),
              'Missing or unexpected vocabulary pages')
    for name, records in expected.items():
        path = directory / name
        h.require(path.is_file() and not path.is_symlink(), 'Invalid vocabulary page: ' + name)
        with path.open(encoding='utf-8', newline='') as stream:
            reader = csv.DictReader(stream, delimiter='\t')
            h.require(reader.fieldnames == WORD_FIELDS and list(reader) == records,
                      'Vocabulary page differs from adopted ledger: ' + name)


def publish(args):
    """Combine batch ledgers relative to the PR's actual parent dictionary."""
    combined = {}
    for path in args.ledger:
        for row in read(path):
            key = row['target_id'], row['lexeme_id'], row['surface']
            if key in combined:
                previous = combined[key]
                h.require(previous['lemma'] == row['lemma'], 'Conflicting public lexical identity')
                for field in ['topics', 'licenses', 'entities']:
                    row[field] = ','.join(sorted((set(previous[field].split(',')) | set(row[field].split(','))) - {'-'})) or '-'
            combined[key] = dict(row)
    parent = {r['surface'] for r in h.json_lines(h.external(args.parent_inventory))}
    parent_keys = {c.lexical.key(s) for s in parent}
    rows = sorted(combined.values(), key=lambda r: (r['surface'].casefold(), r['target_id'], r['lexeme_id']))
    for row in rows:
        row['change'] = ('metadata_only' if row['surface'] in parent else
            'case_variant' if c.lexical.key(row['surface']) in parent_keys else
            'new_form' if row['change'] == 'new_form' else 'new_spelling')
    topics, _ = c.registry(args.taxonomy, args.scopes)
    with tempfile.TemporaryDirectory() as temp:
        pairs, analyses = c.inventory(args.assets.resolve(), args.cli.resolve(), Path(temp) / 'inventory.jsonl')
    verify_rows(rows, topics, pairs, analyses)
    output = h.external(args.out)
    h.require(not output.exists() and not output.is_relative_to(args.assets.resolve()), 'Use a new external publication directory')
    output.mkdir(parents=True)
    if getattr(args,'shard_ledger',False):
        folder=output/'adopted'
        files=c.lexical.write_table_shards(folder,'part',FIELDS,rows)
        h.dump(folder/'index.json',dict(schemaVersion=1,files=files))
    else:c.table(output / 'adopted.tsv', FIELDS, rows)
    counts = summary(rows, topics)
    h.dump(output / 'counts.json', counts)
    lists = output / 'words'; lists.mkdir()
    pages = word_pages(rows, topics)
    for name, records in pages.items():
        c.table(lists / name, WORD_FIELDS, records)
    index = ['| カテゴリ / Category | 追加表記 / Added | 既存表記への付与 / Annotated | 全語 / Words |', '| --- | ---: | ---: | --- |']
    for topic, values in counts['categories'].items():
        links = []
        for start in range(0, values['spellings'], 500):
            name = topic + '-' + str(start // 500 + 1).zfill(3) + '.tsv'
            links.append(f'[{start + 1}–{min(start + 500, values["spellings"])}](WORDS/{name})')
        index.append(f"| {values['label']} / `{topic}` | {values['newSpellings']} | {values['annotatedSpellings']} | " + ', '.join(links) + ' |')
    verify_pages(lists, rows, topics)
    (output / 'index.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    return counts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    for name in ['export', 'verify', 'publish']:
        parser = commands.add_parser(name)
        parser.add_argument('--assets', type=Path, required=True)
        parser.add_argument('--cli', type=Path, default=h.REPO / 'english-ime/build/install/english-ime/bin/english-ime')
        if name == 'export':
            parser.add_argument('--work-dir', type=Path, required=True)
            parser.add_argument('--out', type=Path, required=True)
        else:
            parser.add_argument('--ledger', type=Path, action='append' if name == 'publish' else 'store',
                default=None if name == 'publish' else c.CATALOG / 'adopted-world.tsv', required=name == 'publish')
            parser.add_argument('--taxonomy', type=Path, default=c.CATALOG / 'taxonomy.json')
            parser.add_argument('--scopes', type=Path, default=c.CATALOG / 'core-targets.json')
            if name == 'publish':
                parser.add_argument('--shard-ledger', action='store_true')
                parser.add_argument('--parent-inventory', type=Path, required=True)
                parser.add_argument('--out', type=Path, required=True)
            else:
                parser.add_argument('--word-lists', type=Path, default=c.CATALOG / 'words')
                parser.add_argument('--goals',type=Path,help='Verify the public mandatory spellings, exclusions and topic gates')
    args = p.parse_args()
    print(json.dumps(globals()[args.command](args), ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
