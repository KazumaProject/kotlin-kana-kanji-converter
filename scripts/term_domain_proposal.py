#!/usr/bin/env python3
"""Verify and export the frozen term-domain proposal without model/network calls."""
import argparse
import collections
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import tempfile


DIRECTORY = Path('src/main/classification/term-domain-proposal')
SOURCE = Path('src/main/classification/distribution-candidates.tsv.gz')
REPORT = Path('docs/term-domain-proposal.md')
COLUMNS = ('reading', 'surface', 'category', 'confidence', 'tags', 'method',
           'evidence', 'reference_ids')
CONFIDENCE = ('high', 'medium', 'low')
CONFIDENCE_NAMES = {'high': '高', 'medium': '中', 'low': '低'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_rows(root):
    rows = []
    with gzip.open(root / SOURCE, 'rt', encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            fields = line.rstrip('\n').split('\t')
            if fields[0] != 'term':
                continue
            if len(fields) != 6 or not fields[1] or not fields[5]:
                raise ValueError(f'Invalid source term record at line {number}')
            for value in fields[2:5]:
                if not re.fullmatch(r'-?\d+', value):
                    raise ValueError(f'Invalid source POS/cost at line {number}')
            rows.append(tuple(fields[1:]))
    return rows


def term_digest(rows):
    """Pin the term multiset, without invalidating unrelated category updates."""
    canonical = ''.join('\t'.join(row) + '\n' for row in sorted(rows))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def read_assignments(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError('Unexpected assignment columns')
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError('Malformed assignment row')
            yield row


def summarize(rows, assignments, taxonomy):
    domains = {item['id']: item for item in taxonomy['domains']}
    tags = {item['id']: item for item in taxonomy['tags']}
    all_ids = list(domains) + list(tags)
    if (len(all_ids) != len(set(all_ids))
            or any(not re.fullmatch(r'[a-z][a-z0-9_]*', ident) for ident in all_ids)):
        raise ValueError('Duplicate or unsafe taxonomy IDs')
    if len(domains) != len(taxonomy['domains']) or len(tags) != len(taxonomy['tags']):
        raise ValueError('Duplicate taxonomy IDs')
    allowed_methods = set(taxonomy['assignmentMethods'])
    pairs = {(row[0], row[4]) for row in rows}
    indexed = {}
    domain_pairs = collections.Counter()
    tag_pairs = collections.Counter()
    confidence = collections.Counter()
    per_domain = collections.defaultdict(collections.Counter)
    methods = collections.Counter()
    for row in assignments:
        pair = row['reading'], row['surface']
        if pair in indexed:
            raise ValueError(f'Duplicate assignment: {pair}')
        if pair not in pairs:
            raise ValueError(f'Assignment outside source term inventory: {pair}')
        if row['category'] not in domains:
            raise ValueError(f'Unknown primary category: {row["category"]}')
        if row['confidence'] not in CONFIDENCE:
            raise ValueError(f'Unknown confidence: {row["confidence"]}')
        if row['method'] not in allowed_methods or not row['evidence'].strip():
            raise ValueError(f'Invalid assignment evidence: {pair}')
        labels = row['tags'].split(',') if row['tags'] else []
        if len(labels) != len(set(labels)) or not set(labels) <= set(tags):
            raise ValueError(f'Unknown or duplicate tags: {pair}')
        if row['reference_ids'] and not re.fullmatch(r'\d+(?:,\d+)*', row['reference_ids']):
            raise ValueError(f'Invalid JMdict entry IDs: {pair}')
        indexed[pair] = row
        domain_pairs[row['category']] += 1
        tag_pairs.update(labels)
        confidence[row['confidence']] += 1
        per_domain[row['category']][row['confidence']] += 1
        methods[row['method']] += 1
    missing = pairs - set(indexed)
    if missing:
        raise ValueError(f'Missing assignments: {len(missing)}')
    domain_records = collections.Counter()
    tag_records = collections.Counter()
    for reading, _left, _right, _cost, surface in rows:
        assignment = indexed[(reading, surface)]
        domain_records[assignment['category']] += 1
        tag_records.update(assignment['tags'].split(',') if assignment['tags'] else [])
    summary = dict(
        sourcePairs=len(pairs), sourceRecords=len(rows), unassigned=0,
        domainPairs={ident: domain_pairs[ident] for ident in domains},
        domainRecords={ident: domain_records[ident] for ident in domains},
        tagPairs={ident: tag_pairs[ident] for ident in tags},
        tagRecords={ident: tag_records[ident] for ident in tags},
        confidencePairs={level: confidence[level] for level in CONFIDENCE},
        domainConfidence={ident: {level: per_domain[ident][level] for level in CONFIDENCE}
                          for ident in domains},
        assignmentMethods=dict(sorted(methods.items())),
    )
    return summary, indexed


def verify(root):
    directory = root / DIRECTORY
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schemaVersion') != 1 or manifest.get('status') != 'provisional':
        raise ValueError('Unknown proposal schema or status')
    if manifest.get('semanticAccuracyVerified') is not False:
        raise ValueError('This proposal must not claim verified semantic accuracy')
    if set(manifest['files']) != {'taxonomy.json', 'assignments.tsv.gz'}:
        raise ValueError('Unexpected proposal file inventory')
    for name, digest in manifest['files'].items():
        if sha(directory / name) != digest:
            raise ValueError(f'Proposal hash differs: {name}')
    taxonomy = json.loads((directory / 'taxonomy.json').read_text(encoding='utf-8'))
    rows = source_rows(root)
    if term_digest(rows) != manifest['source']['termRecordsSha256']:
        raise ValueError('Source term records changed; rebuild and review the proposal')
    summary, indexed = summarize(rows, read_assignments(directory / 'assignments.tsv.gz'), taxonomy)
    if summary != manifest['counts']:
        raise ValueError('Proposal counts differ from frozen assignments')
    return manifest, taxonomy, rows, indexed


def export(root, output):
    manifest, taxonomy, rows, indexed = verify(root)
    output = output.resolve()
    if output.exists():
        raise ValueError(f'Output must be a new directory: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    labels = taxonomy['domains'] + taxonomy['tags']
    with tempfile.TemporaryDirectory(prefix='term-proposal-', dir=output.parent) as temporary:
        staging = Path(temporary)
        written = collections.Counter()
        handles = {}
        try:
            for label in labels:
                handles[label['id']] = (staging / (label['id'] + '.tsv')).open(
                    'w', encoding='utf-8', newline='')
            for row in sorted(rows):
                assignment = indexed[(row[0], row[4])]
                ids = [assignment['category']]
                ids.extend(assignment['tags'].split(',') if assignment['tags'] else [])
                for ident in ids:
                    handles[ident].write('\t'.join((ident, *row)) + '\n')
                    written[ident] += 1
        finally:
            for handle in handles.values():
                handle.close()
        # Read every generated row back before exposing the directory.
        original = collections.Counter(rows)
        primary = collections.Counter()
        expected_rows = collections.defaultdict(collections.Counter)
        for source in rows:
            item = indexed[(source[0], source[4])]
            for ident in [item['category']] + (item['tags'].split(',') if item['tags'] else []):
                expected_rows[ident][source] += 1
        for label in labels:
            ident = label['id']
            parsed = []
            for line in (staging / (ident + '.tsv')).read_text(encoding='utf-8').splitlines():
                fields = tuple(line.split('\t'))
                if len(fields) != 6 or fields[0] != ident:
                    raise ValueError(f'Invalid exported record: {ident}')
                source = fields[1:]
                if source not in original:
                    raise ValueError(f'Exported record outside source: {ident}')
                item = indexed[(source[0], source[4])]
                allowed = [item['category']] + (item['tags'].split(',') if item['tags'] else [])
                if ident not in allowed:
                    raise ValueError(f'Exported record in wrong dictionary: {ident}')
                parsed.append(source)
            counts = manifest['counts']
            primary_ids = counts['domainRecords']
            expected = primary_ids.get(ident, counts['tagRecords'].get(ident))
            if len(parsed) != expected:
                raise ValueError(f'Exported record count differs: {ident}')
            if collections.Counter(parsed) != expected_rows[ident]:
                raise ValueError(f'Exported POS/cost multiset differs: {ident}')
            if ident in primary_ids:
                primary.update(parsed)
        if primary != original:
            raise ValueError('Primary exports do not preserve original POS/cost records')
        for name in ('manifest.json', 'taxonomy.json'):
            (staging / name).write_bytes((root / DIRECTORY / name).read_bytes())
        (staging / 'README.txt').write_text(
            '暫定分類案の辞書ソースです。IME用バイナリではありません。\n'
            '主カテゴリは各語1つ、追加タグは重複します。分類の全件確認は未実施です。\n'
            '列: カテゴリID・読み・左品詞ID・右品詞ID・コスト・表記。\n'
            '語の出典・条件は元辞書のLICENSE-DATA.mdと第三者表記を維持します。\n'
            'JMdict由来の分類注釈はCC BY-SA 4.0。James William BREEN / EDRDG。\n'
            'https://www.edrdg.org/edrdg/licence.html\n', encoding='utf-8')
        # Move individual files into a newly created output directory. Never remove
        # or overwrite a user-supplied directory, including an existing empty one.
        output.mkdir()
        for path in sorted(staging.iterdir()):
            path.rename(output / path.name)
    return dict(dictionaries=len(labels), records=dict(written))


def render_report(manifest, taxonomy):
    counts = manifest['counts']
    lines = [
        '# 一般語・専門用語の分野分類案', '',
        '[既存の収録一覧](classified-dictionary-catalog/term/index.md)', '',
        '**レビュー用の暫定案です。配布辞書やIMEの読み込み先は変更していません。**', '',
        f'一般語・専門用語の **{counts["sourcePairs"]:,}組・{counts["sourceRecords"]:,}レコード**だけを対象に、'
        f'主カテゴリ{len(taxonomy["domains"])}種類と追加タグ{len(taxonomy["tags"])}種類へ分類しました。'
        '生活用品・衣食住は一般語・日常表現へ統合しています。', '',
        f'全語に主カテゴリを1つ付け、未分類は{counts["unassigned"]}組です。'
        f'ただし低確信度の推定 **{counts["confidencePairs"]["low"]:,}組**を含みます。'
        '未分類ゼロは意味・読み・分類の全件確認済みを意味しません。', '',
        '## 主カテゴリ', '',
        '「組」は読み・表記の組数です。品詞・コスト違いはレコードとして保持します。', '',
        '| 主カテゴリ | 組 | レコード | 確信度 高 | 中 | 低 |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for item in taxonomy['domains']:
        ident = item['id']
        values = [counts['domainPairs'][ident], counts['domainRecords'][ident]]
        values.extend(counts['domainConfidence'][ident][level] for level in CONFIDENCE)
        lines.append('| ' + item['name'] + ' | ' + ' | '.join(f'{v:,}' for v in values) + ' |')
    lines.extend([
        f'| **合計** | **{counts["sourcePairs"]:,}** | **{counts["sourceRecords"]:,}** | '
        + ' | '.join(f'**{counts["confidencePairs"][level]:,}**' for level in CONFIDENCE) + ' |',
        '', '## 重複する追加タグ', '',
        '追加タグは主カテゴリ・他のタグと重複します。主カテゴリの合計へ足しません。'
        'タグ判定にも誤検出・見逃しがあります。', '',
        '| タグ | 組 | レコード |', '|---|---:|---:|',
    ])
    for item in taxonomy['tags']:
        ident = item['id']
        lines.append(f'| {item["name"]} | {counts["tagPairs"][ident]:,} | {counts["tagRecords"][ident]:,} |')
    lines.extend([
        '', '## 固定データと根拠', '',
        '- [分類定義](../src/main/classification/term-domain-proposal/taxonomy.json)',
        '- [分類結果（gzip圧縮TSV）](../src/main/classification/term-domain-proposal/assignments.tsv.gz)',
        '- [件数・ハッシュ・手順・出典](../src/main/classification/term-domain-proposal/manifest.json)', '',
        '分類TSVはヘッダー付きUTF-8です。列は `reading`・`surface`・`category`・`confidence`・'
        '`tags`・`method`・`evidence`・`reference_ids`。タグとJMdictの項目IDはカンマ区切りです。', '',
        'JMdictの分野タグ・語義から作った学習ラベルでローカルの文字n-gram分類器を学習し、'
        '読みと表記の特徴、分野を示す語幹・接尾辞、抜き取り時の意味判断で補正しました。'
        '分類注釈を固定しており、検証・書き出し時にモデル推論や外部通信は行いません。', '',
        '確信度「高」はJMdictの単一分野タグとの対応、「中」は語形・語義等からの推定、'
        '「低」はモデル推定、複数分野、根拠間の不一致等です。正答確率として校正した値ではありません。'
        '独立資料による読み確認や専門家による全件確認とは区別します。', '',
        '曖昧な語や複数語義のある語も主カテゴリを1つに仮分類しています。'
        '一般語の頻度・実用性は評価していません。追加タグが付かないことは、その性質がないことの証明ではありません。', '',
        '## ローカル検証と辞書ソースの書き出し', '', '```sh',
        'python3 scripts/term_domain_proposal.py verify',
        'python3 scripts/term_domain_proposal.py report --check',
        'python3 -m unittest discover -s scripts -p test_term_domain_proposal.py -v',
        'python3 scripts/term_domain_proposal.py export --output build/term-domain-proposal',
        '```', '',
        'Python標準ライブラリのみで実行できます。出力先は未作成のディレクトリを指定します。'
        '主カテゴリ26種類とタグ5種類の6列TSVを生成し、元の品詞・コストを含む全レコードを読み戻して照合します。'
        '既存の本番カテゴリ定義・固定判断・配布バイナリは更新しません。', '',
        '固定分類の再集計・照合・辞書ソース生成が再現対象です。分類器の再学習は対象外で、'
        'モデル、JMdictキャッシュ、ローカル環境、個人の絶対パスは含めていません。'
        '後続の修正では語単位の分類根拠を見直し、分類ファイル・件数・ハッシュ・本書を合わせて更新します。', '',
        '## 配布への切り替え', '',
        'この案を本番へ採用する場合は、既存の分類判断と衝突を解決したうえで、'
        'カテゴリ定義・追加語の分類方法・固定配布データ・カタログ・利用側IMEの読み込み先を更新する必要があります。'
        '追加タグは同じ語を重複収録するため、利用側での読み込み・重複排除方針も決めます。'
        'IME用バイナリの生成、実アプリの表示・順位・互換性は、この提案では検証していません。', '',
        '## 出典とライセンス', '',
        '語・読み・品詞・コストは既存の `term` レコードです。別カテゴリや追加の医療・漢方辞書から語を追加していません。'
        '元の出典条件は [LICENSE-DATA.md](../LICENSE-DATA.md) と第三者表記を維持します。', '',
        '分類注釈はJMdictを用いた加工データとして **CC BY-SA 4.0** で提供します。'
        'James William BREEN / Electronic Dictionary Research and Development Group（EDRDG）。'
        '[公式ライセンス](https://www.edrdg.org/edrdg/licence.html)・'
        '[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)。'
        '加工は分野ラベル・表現タグの対応付け、モデル推定、語形による補正と確信度の記録です。'
        '元の辞書語の権利・条件を一律に変更するものではありません。', '',
        f'基準リビジョン: `{manifest["source"]["revision"]}`。'
        f'対象termレコードのSHA-256: `{manifest["source"]["termRecordsSha256"]}`。',
        '他カテゴリのみの更新は検証対象外とし、termの読み・表記・品詞・コストが変わった場合は再確認を要求します。', '',
        'English: This is a frozen, provisional classification proposal for all original term pairs. '
        'Household vocabulary is merged into general vocabulary. Confidence remains separate from category membership. '
        'The export preserves source POS/cost variants; no production dictionary or IME integration is changed.', '',
    ])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('verify')
    command = commands.add_parser('export')
    command.add_argument('--output', type=Path, required=True)
    command = commands.add_parser('report')
    command.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.command == 'export':
        print(json.dumps(export(args.root, args.output), ensure_ascii=False, indent=2))
        return
    manifest, taxonomy, _rows, _indexed = verify(args.root)
    if args.command == 'report':
        text = render_report(manifest, taxonomy)
        path = args.root / REPORT
        if args.check:
            if not path.is_file() or path.read_text(encoding='utf-8') != text:
                raise ValueError('Proposal report differs; regenerate it')
        else:
            path.write_text(text, encoding='utf-8')
    else:
        print(json.dumps(dict(status='verified', semanticAccuracyVerified=False,
                              **manifest['counts']), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
