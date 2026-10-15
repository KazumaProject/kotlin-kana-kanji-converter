#!/usr/bin/env python3
"""Owner Issue forms -> validated immutable requests and dictionary review overlays."""
import argparse
import collections
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import html
import json
from pathlib import Path
import re
import sys

import feedback_data as data

SEARCH = '収録先を検索（完全一致）'
ADD = '単語追加'
REPORT = '候補の問題報告'
FIELDS = {'申請の種類', '読み', '表記', '追加先', '品詞・活用種類', '希望する対応', '対象辞書', '辞書の版', '正しい候補', '補足・出典'}


def target_options(root):
    return ['システム辞書 (system)'] + [f'{name} ({key})' for key, name in data.categories(root).items()]


def field(kind, identity, label, required=False, **attributes):
    return dict(type=kind, id=identity, attributes=dict(label=label, **attributes), validations=dict(required=required))


def forms(root):
    _, profiles = data.pos_rules(root)
    shared = [field('input', 'reading', '読み', True, description='追加は基本形、問題報告は実際に入力した読み全体。例：りばーと'),
              field('input', 'surface', '表記', True, description='追加する表記、または問題の候補をそのまま入力。大文字・小文字も区別します。')]
    note = dict(type='markdown', attributes=dict(value='自分用の辞書改善フォームです。投稿内容は公開されます。1件のIssueにつき1語。除外は指定した読み・表記の完全一致だけが対象です。'))
    return {
        'dictionary-add.yml': dict(name='辞書に単語を追加', description='システム辞書・30カテゴリに単語や活用形を追加します。', title='[辞書追加] ',
            body=[note, field('dropdown', 'request', '申請の種類', True, options=[ADD]), *shared,
                  field('dropdown', 'target', '追加先', True, options=target_options(root)),
                  field('dropdown', 'pos', '品詞・活用種類', True, options=list(profiles)),
                  field('textarea', 'notes', '補足・出典', description='読み・表記・分類の根拠やURL。空欄でも本人の申請として扱います。')]),
        'dictionary-report.yml': dict(name='辞書の候補を報告', description='不要な候補や、読み・表記・分類の問題を報告します。', title='[辞書報告] ',
            body=[note, field('dropdown', 'request', '申請の種類', True, options=[REPORT]), *shared,
                  field('dropdown', 'action', '希望する対応', True, options=['除外する', '調査・修正を依頼する']),
                  field('dropdown', 'target', '対象辞書', True, options=[SEARCH, *target_options(root)]),
                  field('input', 'version', '辞書の版', description='分かればReleaseタグなどを記入してください。'),
                  field('input', 'expected', '正しい候補'), field('textarea', 'notes', '補足・出典')])}


def generate_forms(root, check=False):
    directory = root / '.github/ISSUE_TEMPLATE'
    for name, value in forms(root).items():
        # JSON is a YAML subset; keeps generated options dependency-free and unambiguous.
        expected = data.encode(value)
        path = directory / name
        if check:
            if not path.exists() or path.read_text() != expected: raise ValueError('Issue form needs regeneration: ' + name)
        else:
            directory.mkdir(parents=True, exist_ok=True); path.write_text(expected, encoding='utf-8')


def parse_body(body):
    if not isinstance(body, str) or len(body) > 20000: raise ValueError('Invalid Issue body')
    headers = list(re.finditer(r'^### ([^\r\n]+)\r?\n', body, re.M))
    values = {}
    for i, match in enumerate(headers):
        key = match[1]
        if key not in FIELDS or key in values: raise ValueError('Unknown or duplicate Issue field: ' + key)
        value = body[match.end():headers[i+1].start() if i+1 < len(headers) else len(body)].strip()
        values[key] = '' if value == '_No response_' else value
    required = {'申請の種類', '読み', '表記'}
    if not required <= values.keys() or any(not values[k] for k in required): raise ValueError('必須のフォーム項目がありません。')
    data.normalize(values['読み'], values['表記'])
    return values


def dictionary(value, root):
    if value == SEARCH: return None
    match = re.fullmatch(r'.+ \((system|categories/[a-z_]+)\)', value)
    if not match or match[1] not in {'system', *data.categories(root)}: raise ValueError('追加先・対象辞書を選択してください。')
    return match[1]


def read_inventory(path):
    result = collections.defaultdict(list)
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            item = json.loads(line)
            if item['rawSurface'] != item['surface']:
                # A raw/binary mismatch requires investigation, never an approximate deletion.
                continue
            key = item['dictionary'], item['reading'], item['surface']
            row = [item['reading'], item['leftId'], item['rightId'], item['cost'], item['surface']]
            if row not in result[key]: result[key].append(row)
    return result


def classification_entries(root, operations, reference, reason):
    import classification_reviews as reviews
    import classified_distribution as distribution
    previous = reviews.load(root)
    directory = root / 'src/main/classification'
    with gzip.open(directory / 'distribution-decisions.tsv.gz', 'rt', encoding='utf-8') as stream:
        current = {tuple(row[:2]): row for row in (line.rstrip('\n').split('\t') for line in stream)}
    grouped = collections.defaultdict(list)
    allowed = {key for key in data.categories(root) if key not in ('categories/kampo', 'categories/medical')}
    for op in operations:
        if op['dictionary'] in allowed: grouped[(op['reading'], op['surface'])].append(op)
    entries = []
    for pair, ops in sorted(grouped.items()):
        old = previous.get(pair)
        baseline = old['baseline'] if old else current.get(pair)
        cats = set(current[pair][2].split(',')) if pair in current and current[pair][4] == 'classified' else set()
        for op in ops:
            category = op['dictionary'].split('/')[1]
            if op['action'] == 'add': cats.add(category)
            else: cats.discard(category)
        entry = dict(reading=pair[0], surface=pair[1], candidate_key=distribution.key(*pair), baseline=baseline,
                     action=('keep' if baseline else 'add') if cats else 'exclude', reason=reason)
        if old:
            for key in ('added_record', 'added_records'):
                if key in old: entry[key] = old[key]
        elif baseline is None:
            records = {tuple(row[1:4]) for op in ops for row in op['records']}
            entry['added_records'] = [dict(left_id=l, right_id=r, cost=c) for l, r, c in sorted(records)]
        if cats:
            entry['categories'] = sorted(cats)
            entry['evidence'] = dict(kind='user_confirmation', reading=pair[0], surface=pair[1], categories=entry['categories'], reference=reference)
        entries.append(entry)
    return entries


def prepare(root, issue, inventory, now=None):
    if issue.get('user', {}).get('login') != data.OWNER: raise ValueError('Only the configured owner can submit automated requests')
    number = issue.get('number')
    if type(number) is not int or number <= 0: raise ValueError('Invalid Issue number')
    reference = f'https://github.com/{data.REPOSITORY}/issues/{number}'
    if issue.get('html_url') != reference or issue.get('pull_request') or issue.get('state', 'open') != 'open':
        raise ValueError('Expected an open Issue in the configured repository')
    body = issue.get('body') or ''
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    saved_requests = data.requests(root)
    issue_history = [entry for _, entry in saved_requests if entry['issue'] == number]
    if issue_history and issue_history[-1]['bodySha256'] == body_hash:
        return dict(status='no-change', message='同じ申請は反映済みです。', operations=[])
    fields = parse_body(body)
    reading, surface = data.normalize(fields['読み'], fields['表記'])
    existing = read_inventory(inventory)
    history = data.latest(root)
    operations = []
    def operation(target, key, value, action, records):
        identity = target, key, value
        baseline = history[identity]['baselineRecords'] if identity in history else existing.get(identity, [])
        operations.append(dict(dictionary=target, reading=key, surface=value, action=action,
                               baselineRecords=baseline, records=records))
    if fields['申請の種類'] == ADD:
        target = dictionary(fields.get('追加先', ''), root)
        expanded = data.expand(root, reading, surface, fields.get('品詞・活用種類', ''))
        groups = collections.defaultdict(list)
        for row in expanded: groups[(row[0], row[4])].append(row)
        for (key, value), rows in groups.items():
            if existing.get((target, key, value)): continue
            if target in ('categories/kampo', 'categories/medical') and any(k[1:] == (key, value) for k in existing):
                raise ValueError('漢方・医療の追加先以外に同じ読み・表記があります。収録先の確認が必要です。')
            operation(target, key, value, 'add', rows)
    elif fields['申請の種類'] == REPORT:
        targets = dictionary(fields.get('対象辞書', ''), root)
        matches = sorted(k for k in existing if k[1:] == (reading, surface) and (targets is None or k[0] == targets))
        if fields.get('希望する対応') != '除外する':
            return dict(status='needs-triage', message='調査・修正の報告として保存しました。完全一致の収録先: ' + ', '.join(k[0] for k in matches), operations=[])
        if not matches:
            return dict(status='needs-triage', message='現在の生成入力に読み・表記が完全一致するレコードがありません。別の読みは除外しません。辞書の版と配布データを確認してください。', operations=[])
        for target, key, value in matches: operation(target, key, value, 'exclude', [])
    else: raise ValueError('Unknown request type')
    if not operations: return dict(status='no-change', message='指定した追加先に登録済みです。既存の品詞・コストは変更していません。', operations=[])
    stamp = (now or datetime.now(timezone.utc)).strftime('%Y%m%dT%H%M%S%fZ')
    if saved_requests and stamp <= saved_requests[-1][1]['submitted']:
        # Preserve application order even if the wall clock moves backwards.
        stamp = (datetime.strptime(saved_requests[-1][1]['submitted'], '%Y%m%dT%H%M%S%fZ')
                 + timedelta(microseconds=1)).strftime('%Y%m%dT%H%M%S%fZ')
    dated = f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}-{stamp[9:]}'
    filename = f'{dated}-issue-{number}-{body_hash[:12]}'
    reason = f'本人のIssue申請: {reference}'
    bridge = classification_entries(root, operations, reference, reason)
    request = dict(schemaVersion=1, issue=number, issueUrl=reference, author=data.OWNER, bodySha256=body_hash,
                   submitted=stamp, input=fields, operations=operations)
    # All validation above happens before writing a new request or bridge.
    directory = root / data.DIRECTORY / 'requests'; directory.mkdir(parents=True, exist_ok=True)
    path = directory / (filename + '.json')
    if path.exists(): raise ValueError('Request timestamp collision; existing history will not be overwritten')
    path.write_text(data.encode(request), encoding='utf-8')
    if bridge:
        ledger = root / 'src/main/classification/reviews' / (filename + '.jsonl')
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(''.join(json.dumps(e, ensure_ascii=False, sort_keys=True) + '\n' for e in bridge), encoding='utf-8')
    data.write_system(root)
    return dict(status='ready', message=reason, operations=operations)


def report(result):
    lines = ['## 辞書申請の処理結果', '', result['message'], '',
             '除外は読み・表記・対象辞書の完全一致です。部分一致による除外は行いません。', '',
             '| 操作 | 辞書 | 読み | 表記 | 左品詞ID | 右品詞ID | コスト |', '|---|---|---|---|---:|---:|---:|']
    def escaped(value): return '<code>' + html.escape(str(value)).replace('|', '&#124;').replace('@', '&#64;').replace('\n', ' ') + '</code>'
    for op in result['operations']:
        for row in op['records'] if op['action'] == 'add' else op['baselineRecords']:
            lines.append('| ' + ' | '.join(map(escaped, ['追加' if op['action'] == 'add' else '除外', op['dictionary'], row[0], row[4], *row[1:4]])) + ' |')
    lines += ['', '変更した語・活用形の一覧です。実アプリの候補順位の確認結果ではありません。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('forms'); p.add_argument('--check', action='store_true')
    subs.add_parser('verify'); subs.add_parser('materialize')
    p = subs.add_parser('prepare'); p.add_argument('--issue', type=Path, required=True); p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path('build/dictionary-feedback/result.json'))
    args = parser.parse_args(); root = args.root.resolve()
    if args.command == 'forms': generate_forms(root, args.check)
    elif args.command == 'verify': data.verify(root); generate_forms(root, True)
    elif args.command == 'materialize': data.write_system(root)
    elif args.command == 'prepare':
        try: result = prepare(root, json.loads(args.issue.read_text()), args.inventory)
        except ValueError as error: result = dict(status='needs-triage', message=str(error), operations=[])
        output = root / args.output; output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(data.encode(result), encoding='utf-8')
        output.with_suffix('.md').write_text(report(result), encoding='utf-8')
        print(result['status'] + ': ' + result['message'])


if __name__ == '__main__': main()
