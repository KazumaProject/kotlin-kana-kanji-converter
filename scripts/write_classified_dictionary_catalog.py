#!/usr/bin/env python3
"""Render every distributed record as paginated repository documentation."""
import argparse
import gzip
import hashlib
import html
import itertools
import heapq
import json
from pathlib import Path
import shutil
import tempfile

import classified_distribution as distribution

ORIGINS = {'verified': '資料確認済み', 'manual': 'assistant再分類（暫定）', 'gemini': 'Gemini（暫定）', 'specialist': '提供元の読み（正確性未確認）', 'inferred_reading': 'Gemini推定読み（未確認）', 'curated_correction': '出典確認済みの読み訂正'}
MAX_ROWS = 1500
MAX_BYTES = 180_000


def code(value):
    return '<code>' + html.escape(value).replace('|', '&#124;') + '</code>'


def generate_excluded(root, output, manifest):
    """Publish frozen exclusions with saved reasons, without inventing evidence."""
    source = root / 'src/main/classification'
    excluded = {}
    with gzip.open(source / 'distribution-decisions.tsv.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            reading, surface, categories, origin, status = line.rstrip('\n').split('\t')
            if status == 'excluded':
                excluded[(reading, surface)] = [categories, ORIGINS.get(origin, origin), '理由の記録なし', '固定判断']
    ledger = manifest.get('provenance', {}).get('lunaReclassification')
    if ledger:
        ledger_path = root / ledger['path']
        if ledger_path.is_file():
            with gzip.open(ledger_path, 'rt', encoding='utf-8') as stream:
                for line in stream:
                    entry = json.loads(line)
                    pair = entry['response']['reading'], entry['response']['surface']
                    if pair in excluded and entry['effective_action'] == 'reject':
                        excluded[pair][2:] = [entry['effective_reason'], 'PR #141・Luna Max（暫定）']
    for relative in manifest.get('provenance', {}).get('reviews', []):
        with (root / relative).open(encoding='utf-8') as stream:
            for line in stream:
                entry = json.loads(line)
                pair = entry['reading'], entry['surface']
                if pair in excluded and entry['action'] in ('exclude', 'hold'):
                    kind = entry.get('evidence', {}).get('kind')
                    basis = {'user_confirmation': 'ユーザー明示判断', 'model_review': 'Luna Max（暫定）',
                             'independent_source': '独立資料'}.get(kind, '保存済みレビュー')
                    excluded[pair][2:] = [entry['reason'], basis]
    directory = output / 'excluded'
    directory.mkdir()
    pages, page, size = [], [], 0
    def flush():
        nonlocal page, size
        if not page: return
        filename = f'page-{len(pages)+1:04d}.md'
        pages.append((filename, page[0][0], page[-1][0]))
        (directory / filename).write_text(''.join(line for _, line in page), encoding='utf-8')
        page, size = [], 0
    for (reading, surface), (categories, origin, reason, basis) in sorted(excluded.items()):
        line = '| ' + ' | '.join(code(value.replace('\n', ' ').replace('\r', ' '))
                                for value in (reading, surface, categories, origin, reason, basis)) + ' |\n'
        length = len(line.encode('utf-8'))
        if page and (len(page) >= MAX_ROWS or size + length > MAX_BYTES): flush()
        page.append((reading, line)); size += length
    flush()
    for index, (filename, _, _) in enumerate(pages):
        navigation = ['[不採用の目次](index.md)', '[採用語の一覧](../index.md)']
        if index: navigation.append(f'[前のページ]({pages[index-1][0]})')
        if index+1 < len(pages): navigation.append(f'[次のページ]({pages[index+1][0]})')
        nav = ' · '.join(navigation)
        path = directory / filename
        header = (f'# 不採用語 — {index+1}/{len(pages)}\n\n{nav}\n\n'
                  '不採用は不存在・読み誤りの実証を意味しません。モデルの暫定判断やユーザー基準による除外を含みます。\n\n'
                  '| 読み | 表記 | 保存カテゴリ（不採用） | 分類元 | 不採用理由 | 判断の根拠 |\n'
                  '|---|---|---|---|---|---|\n')
        path.write_text(header + path.read_text(encoding='utf-8') + '\n' + nav + '\n', encoding='utf-8')
    links = '\n'.join(f'- [{i+1}ページ]({filename}): {code(first)} ～ {code(last)}'
                      for i, (filename, first, last) in enumerate(pages))
    (directory / 'index.md').write_text(
        '# 不採用語と判断理由\n\n[採用語の一覧](../index.md)\n\n'
        f'固定判断台帳で不採用になっている **{len(excluded):,}組**を、読み順で全件掲載しています。'
        '同じ読み・表記は1回掲載し、保存済みの最終理由を表示します。\n\n'
        'PR #141・#142の不採用判断を含みます。古い処理で除外され、固定判断台帳に読み・表記が残っていない候補は対象外です。'
        '専門辞書の形式不正・既存辞書との重複による見送りは、この語彙判断の一覧には含みません。'
        '不採用は不存在・読み誤りの実証を意味しません。\n\n'
        + links + '\n\n'
        f'判断台帳SHA-256: `{manifest["files"].get("distribution-decisions.tsv.gz", "未記録")}`\n', encoding='utf-8')
    return dict(pairs=len(excluded), pages=len(pages))


def generate_sport_subcategories(directory, rows, sport_names):
    """Render the sports category again, grouped by its reviewed sport tags."""
    grouped = {sport_id: [] for sport_id in sport_names}
    for reading, surface, _left, _right, _cost, sports in rows:
        sport_ids = {value for value in sports.split(',') if value}
        if not sport_ids:
            sport_ids = {'sport_unspecified'}
        unknown = sport_ids - grouped.keys()
        if unknown:
            raise ValueError(f'Unknown sport subcategories: {sorted(unknown)}')
        for sport_id in sport_ids:
            grouped[sport_id].append((reading, surface))

    output = directory / 'by-sport'
    output.mkdir()
    summary = []
    for sport_id, label in sport_names.items():
        sport_rows = grouped[sport_id]
        pairs = sorted(set(sport_rows))
        if not pairs:
            continue

        sport_dir = output / sport_id
        sport_dir.mkdir()
        pages, page, byte_count = [], [], 0

        def flush():
            nonlocal page, byte_count
            if not page:
                return
            filename = f'page-{len(pages)+1:04d}.md'
            (sport_dir / filename).write_text(''.join(page), encoding='utf-8')
            pages.append(filename)
            page, byte_count = [], 0

        for reading, surface in pairs:
            row = f'| {code(reading)} | {code(surface)} |\n'
            size = len(row.encode('utf-8'))
            if page and (len(page) >= MAX_ROWS or byte_count + size > MAX_BYTES):
                flush()
            page.append(row)
            byte_count += size
        flush()

        for index, filename in enumerate(pages):
            navigation = ['[スポーツ関係者一覧](../../index.md)', '[競技別一覧](../index.md)']
            if index:
                navigation.append(f'[前のページ]({pages[index-1]})')
            if index + 1 < len(pages):
                navigation.append(f'[次のページ]({pages[index+1]})')
            nav = ' · '.join(navigation)
            path = sport_dir / filename
            header = (f'# {label} — {index+1}/{len(pages)}\n\n{nav}\n\n'
                      'この競技に分類された標準配布対象の読み・表記の組です。複数競技に分類された語は各競技一覧に掲載されます。\n\n'
                      '| 読み | 表記 |\n|---|---|\n')
            path.write_text(header + path.read_text(encoding='utf-8') + '\n' + nav + '\n', encoding='utf-8')

        links = '\n'.join(f'- [{index+1}ページ]({filename})' for index, filename in enumerate(pages))
        (sport_dir / 'index.md').write_text(
            f'# {label}\n\n[スポーツ関係者一覧](../../index.md) · [競技別一覧](../index.md)\n\n'
            f'レコード数: **{len(sport_rows):,}** · 読み・表記の組: **{len(pairs):,}**。\n\n{links}\n',
            encoding='utf-8')
        summary.append(dict(id=sport_id, name=label, records=len(sport_rows), pairs=len(pairs), pages=len(pages)))

    table = ['| 競技 | 読み・表記の組 | レコード数 | 全件一覧 |', '|---|---:|---:|---|']
    for item in summary:
        detail = f'{item["id"]}/index.md'
        table.append(
            f'| [{item["name"]}]({detail}) | {item["pairs"]:,} | '
            f'{item["records"]:,} | [全件]({detail}) |'
        )
    record_count = sum(item['records'] for item in summary)
    pair_count = sum(item['pairs'] for item in summary)
    (output / 'index.md').write_text(
        '# スポーツ関係者 — 競技別一覧\n\n[スポーツ関係者の全件一覧](../index.md) · [最終配布カテゴリ一覧](../../../index.md)\n\n'
        f'競技タグ別に **{len(summary)}競技**、延べ **{record_count:,}レコード**、'
        f'**{pair_count:,}組**を掲載しています。複数競技に分類された語は各競技に重複して掲載するため、競技別合計には重複があります。'
        '競技タグが未設定または特定できない語は「競技未特定」に含めています。\n\n'
        + '\n'.join(table) + '\n',
        encoding='utf-8')
    return summary


def generate_person_taxonomy(root, output, final_pairs):
    source = root / 'src/main/classification'
    taxonomy = json.loads((source / 'person-taxonomy.json').read_text(encoding='utf-8'))
    categories = [category for category in taxonomy['categories'] if category['standard_enabled']]
    category_ids = [category['id'] for category in categories]
    if len(categories) != 23 or len(set(category_ids)) != len(category_ids):
        raise ValueError('Expected 23 unique standard-enabled person categories')
    names = {category['id']: category['label'] for category in categories}
    records = {category_id: [] for category_id in category_ids}
    source_file = source / 'person-dictionary-candidates.tsv.gz'
    source_hash = distribution.sha(source_file)
    with gzip.open(source_file, 'rt', encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            fields = line.rstrip('\n').split('\t')
            if len(fields) != 7:
                raise ValueError(f'{source_file}:{number}: expected seven columns')
            category, reading, left, right, cost, surface, sports = fields
            if category not in records:
                raise ValueError(f'{source_file}:{number}: non-standard person category: {category}')
            if not reading or not surface:
                raise ValueError(f'{source_file}:{number}: empty reading or surface')
            records[category].append((reading, surface, left, right, cost, sports))
            final_pairs.add((reading, surface))

    output.mkdir(parents=True, exist_ok=True)
    summary = []
    for category in categories:
        category_id = category['id']
        rows = records[category_id]
        pairs = sorted({(row[0], row[1]) for row in rows})
        directory = output / category_id
        directory.mkdir()
        pages = []
        page = []
        byte_count = 0

        def flush():
            nonlocal page, byte_count
            if not page:
                return
            filename = f'page-{len(pages)+1:04d}.md'
            (directory / filename).write_text(''.join(page), encoding='utf-8')
            pages.append(filename)
            page, byte_count = [], 0

        for reading, surface in pairs:
            row = f'| {code(reading)} | {code(surface)} |\n'
            size = len(row.encode('utf-8'))
            if page and (len(page) >= MAX_ROWS or byte_count + size > MAX_BYTES):
                flush()
            page.append(row)
            byte_count += size
        flush()

        for index, filename in enumerate(pages):
            navigation = ['[最終配布カテゴリ一覧](../../index.md)']
            if index:
                navigation.append(f'[前のページ]({pages[index-1]})')
            if index + 1 < len(pages):
                navigation.append(f'[次のページ]({pages[index+1]})')
            nav = ' · '.join(navigation)
            path = directory / filename
            header = (f'# {names[category_id]} — {index+1}/{len(pages)}\n\n{nav}\n\n'
                      '標準配布対象の読み・表記の組を掲載しています。同じ組の複数品詞・コストレコードは一組にまとめています。\n\n'
                      '| 読み | 表記 |\n|---|---|\n')
            path.write_text(header + path.read_text(encoding='utf-8') + '\n' + nav + '\n', encoding='utf-8')

        sport_subcategories = []
        if category_id == 'sports':
            sport_subcategories = generate_sport_subcategories(
                directory, rows, taxonomy['sport_subcategories'])
        links = '\n'.join(f'- [{index+1}ページ]({filename})' for index, filename in enumerate(pages))
        if not pages:
            links = '収録0件。'
        (directory / 'index.md').write_text(
            f'# {names[category_id]}\n\n[最終配布カテゴリ一覧](../../index.md)\n\n'
            f'親カテゴリ: `person` · レコード数: **{len(rows):,}** · 読み・表記の組: **{len(pairs):,}**。\n\n'
            + ('[競技別一覧](by-sport/index.md)\n\n' if sport_subcategories else '')
            + f'{links}\n',
            encoding='utf-8')
        summary.append(dict(id=category_id, name=names[category_id], records=len(rows), pairs=len(pairs), pages=len(pages)))

    record_count = sum(item['records'] for item in summary)
    pair_count = sum(item['pairs'] for item in summary)
    return dict(categories=summary, records=record_count, uniquePairs=pair_count, sourceSha256=source_hash)


def generate_person_replacement_index(output, base_summary, person_summary):
    """List the exact 71-category replacement bundle, linking to each word list."""
    base_categories = [item for item in base_summary if item['id'] != 'person']
    person_categories = person_summary['categories']
    if len(base_categories) != 48 or len(person_categories) != 23:
        raise ValueError('Expected 48 existing non-person categories and 23 person categories')

    table = ['| カテゴリ | ID | 読み・表記の組 | レコード数 | 全件一覧 |',
             '|---|---|---:|---:|---|']
    for category in base_categories:
        category_id = category['id']
        table.append(
            f'| [{category["name"]}]({category_id}/index.md) | `{category_id}` | '
            f'{category["pairs"]:,} | {category["records"]:,} | [全件]({category_id}/index.md) |'
        )
    for category in person_categories:
        category_id = category['id']
        detail = f'person/{category_id}/index.md'
        table.append(
            f'| [{category["name"]}]({detail}) | '
            f'`{category_id}` | {category["pairs"]:,} | {category["records"]:,} | '
            f'[全件]({detail}) |'
        )

    record_count = sum(item['records'] for item in base_categories) + person_summary['records']
    pair_count = sum(item['pairs'] for item in base_categories) + person_summary['uniquePairs']
    (output / 'index.md').write_text(
        '# 人物辞書置換プレリリース — 全配布カテゴリ\n\n'
        '人物細分類辞書を含む配布ZIPのカテゴリ一覧です。通常配布の49カテゴリから汎用 `person` を除き、'
        '標準配布対象の人物細分類23カテゴリに置き換えた **71カテゴリ**を掲載しています。'
        '未分類候補と成人関連など配布対象外の候補は含めていません。\n\n'
        f'カテゴリ別レコード数の合計は **{record_count:,}**、読み・表記の組数の合計は **{pair_count:,}**です。'
        '同じ組が別カテゴリにもある場合、合計では重複して数えます。各リンクからカテゴリの全収録語を確認できます。\n\n'
        '[生成・配布手順](../classified-dictionary-distribution.md#人物細分類への置換プレリリース) · '
        '[人物分類定義](../../src/main/classification/person-taxonomy.json)\n\n'
        + '\n'.join(table) + '\n',
        encoding='utf-8')
    return dict(categories=71, records=record_count, categoryPairCount=pair_count,
                baseCategories=len(base_categories), personCategories=len(person_categories))


def generate(root, output):
    source = root / 'src/main/classification'
    manifest = json.loads((source / 'distribution-manifest.json').read_text())
    taxonomy = json.loads((source / 'categories.json').read_text())
    categories = taxonomy['categories']
    category_groups = taxonomy.get('categoryGroups', [])
    names = {c['id']: c.get('name', c['id']) for c in categories}
    origins = {}
    with gzip.open(source / 'distribution-decisions.tsv.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            reading, surface, _, origin, status = line.rstrip('\n').split('\t')
            if status == 'classified':
                origins[(reading, surface)] = origin
    specialist_dir = root / 'src/main/specialist'
    specialist_file = specialist_dir / 'distribution-manifest.json'
    specialist_rows = []
    if specialist_file.exists():
        import specialist_distribution as specialist
        extra = specialist.verify_files(root)
        categories += json.loads((specialist_dir / 'categories.json').read_text())['categories']
        names = {c['id']: c.get('name', c['id']) for c in categories}
        with gzip.open(specialist_dir / 'distribution-candidates.tsv.gz', 'rt', encoding='utf-8') as f:
            specialist_rows = [line.rstrip('\n').split('\t') for line in f]
        for _, reading, _, _, _, surface in specialist_rows:
            if (reading, surface) in origins:
                raise ValueError('Specialist catalog overlaps existing classified dictionaries')
            origins[(reading, surface)] = 'specialist'
        for record in specialist.read_json_gzip(specialist_dir / 'provenance.jsonl.gz'):
            if record['status']=='adopted' and record.get('readingOrigin')=='gemini_inferred_unverified':
                origins[(record['reading'],record['surface'])]='inferred_reading'
            if record['status']=='adopted' and record.get('readingOrigin')=='curated_correction':
                origins[(record['reading'],record['surface'])]='curated_correction'
        manifest['categoryRows'].update(extra['categoryRows'])
        manifest['uniqueAdmittedPairs'] += extra['uniqueAdmittedPairs']
        manifest['dictionaryRows'] += extra['dictionaryRows']
    output.mkdir(parents=True)
    taxonomy_source = source / 'person-taxonomy.json'
    person_source = source / 'person-dictionary-candidates.tsv.gz'
    person_taxonomy_summary = None
    final_pairs = set()
    if taxonomy_source.is_file() or person_source.is_file():
        if not taxonomy_source.is_file() or not person_source.is_file():
            raise ValueError('Person taxonomy catalog requires both taxonomy and candidate sources')
        person_taxonomy_summary = generate_person_taxonomy(root, output / 'person', final_pairs)
    summary = []
    with gzip.open(source / 'distribution-candidates.tsv.gz', 'rt', encoding='utf-8') as stream:
        rows = heapq.merge((line.rstrip('\n').split('\t') for line in stream), specialist_rows)
        for category, records in itertools.groupby(rows, key=lambda row: row[0]):
            if category == 'person' and person_taxonomy_summary is not None:
                continue
            directory = output / category
            directory.mkdir(parents=True)
            pages = []
            page = []
            byte_count = 0
            pairs = set()
            readings = set()
            count = 0
            by_origin = {}

            def flush():
                nonlocal page, byte_count
                if page:
                    filename = f'page-{len(pages)+1:04d}.md'
                    (directory / filename).write_text(''.join(page), encoding='utf-8')
                    pages.append(filename)
                    page = []
                    byte_count = 0

            for _, reading, left, right, cost, surface in records:
                origin = origins[(reading, surface)]
                final_pairs.add((reading, surface))
                row = f'| {code(reading)} | {code(surface)} | {left} | {right} | {cost} | {ORIGINS[origin]} |\n'
                size = len(row.encode('utf-8'))
                if page and (len(page) >= MAX_ROWS or byte_count + size > MAX_BYTES):
                    flush()
                page.append(row)
                byte_count += size
                pairs.add((reading, surface))
                readings.add(reading)
                by_origin[origin] = by_origin.get(origin, 0) + 1
                count += 1
            flush()
            if count != manifest['categoryRows'][category]:
                raise ValueError(f'Catalog count differs from distributed records: {category}')
            item = dict(id=category, name=names[category], pairs=len(pairs), readings=len(readings), records=count,
                        pages=len(pages), recordsByOrigin=by_origin)
            summary.append(item)
            for index, filename in enumerate(pages):
                path = directory / filename
                root_link = '../' * len(Path(category).parts)
                navigation = ['[カテゴリ目次](index.md)',
                              f'[全カテゴリ]({root_link}index.md)',
                              f'[品詞IDと品詞名]({root_link}pos.md)']
                if index: navigation.append(f'[前のページ]({pages[index-1]})')
                if index+1 < len(pages): navigation.append(f'[次のページ]({pages[index+1]})')
                nav = ' · '.join(navigation)
                header = (f'# {names[category]} — {index+1}/{len(pages)}\n\n{nav}\n\n'
                          '同じ読み・表記でも品詞・コストが異なるレコードを省略せず掲載します。品詞名は上記の対応表で確認できます。\n\n'
                          '| 読み | 表記 | 左品詞ID | 右品詞ID | コスト | 分類元 |\n'
                          '|---|---|---:|---:|---:|---|\n')
                path.write_text(header + path.read_text(encoding='utf-8') + '\n' + nav + '\n', encoding='utf-8')
            links = '\n'.join(f'- [{i+1}ページ]({filename})' for i, filename in enumerate(pages))
            root_link = '../' * len(Path(category).parts)
            (directory / 'index.md').write_text(
                f'# {names[category]} ({category})\n\n[全カテゴリ]({root_link}index.md) · [品詞名]({root_link}pos.md)\n\n'
                f'読み・表記の組: **{len(pairs):,}**、読み: **{len(readings):,}**、レコード: **{count:,}**。\n\n{links}\n', encoding='utf-8')
    present = {item['id'] for item in summary}
    for category in categories:
        if category['id'] == 'person' and person_taxonomy_summary is not None:
            continue
        if category['id'] not in present:
            directory = output / category['id']
            directory.mkdir(parents=True)
            (directory / 'index.md').write_text(f'# {names[category["id"]]}\n\n収録0件。\n', encoding='utf-8')
            summary.append(dict(id=category['id'],name=names[category['id']],pairs=0,readings=0,records=0,pages=0,recordsByOrigin={}))
    order = {c['id']: i for i,c in enumerate(categories)}
    summary.sort(key=lambda item: order[item['id']])
    table = ['| カテゴリ | 読み・表記の組 | 読み数 | レコード数 |', '|---|---:|---:|---:|']
    for item in summary:
        table.append(f'| [{item["name"]}]({item["id"]}/index.md) | {item["pairs"]:,} | {item["readings"]:,} | {item["records"]:,} |')
    category_group_text = ''
    if category_groups:
        sections = []
        for parent in category_groups:
            parent_id = parent['id']
            parent_totals = [item for item in summary if item['id'].startswith(parent_id + '/')]
            parent_pairs = sum(item['pairs'] for item in parent_totals)
            parent_records = sum(item['records'] for item in parent_totals)
            group_links = []
            parent_dir = output / parent_id
            parent_dir.mkdir(parents=True, exist_ok=True)
            for group in parent['groups']:
                group_categories = [item for item in parent_totals if item['id'].startswith(group['id'] + '/')]
                group_pairs = sum(item['pairs'] for item in group_categories)
                group_records = sum(item['records'] for item in group_categories)
                group_dir = output / group['id']
                group_dir.mkdir(parents=True, exist_ok=True)
                group_root_link = '../' * len(Path(group['id']).parts)
                leaf_links = '\n'.join(
                    f'- [{item["name"]}]({item["id"].split("/")[-1]}/index.md) — '
                    f'{item["pairs"]:,}組、{item["records"]:,}レコード'
                    for item in group_categories)
                (group_dir / 'index.md').write_text(
                    f'# {group["name"]}\n\n[{parent["name"]}](../index.md) · '
                    f'[全カテゴリ]({group_root_link}index.md)\n\n'
                    f'読み・表記の組: **{group_pairs:,}**、レコード: **{group_records:,}**。\n\n'
                    f'{leaf_links}\n', encoding='utf-8')
                group_links.append(
                    f'- [{group["name"]}]({group["id"].split("/")[-1]}/index.md) — '
                    f'{group_pairs:,}組、{group_records:,}レコード')
            (parent_dir / 'index.md').write_text(
                f'# {parent["name"]}\n\n[全カテゴリ](../index.md)\n\n'
                f'読み・表記の組: **{parent_pairs:,}**、レコード: **{parent_records:,}**。\n\n'
                + '\n'.join(group_links) + '\n', encoding='utf-8')
            sections.append(
                f'- [{parent["name"]}]({parent_id}/index.md) — {parent_pairs:,}組、{parent_records:,}レコード')
        term_group_text = '\n'.join(sections) + '\n\n'
        category_group_text = term_group_text
    hierarchy_notes = []
    for parent in category_groups:
        if parent['id'] == 'term':
            hierarchy_notes.append('用語カテゴリは一般語5分類・専門語10分類に分かれています。')
        elif parent['id'] == 'event':
            hierarchy_notes.append('イベント辞書は催し・行事、事件・事故・災害、歴史的出来事の3群に分かれ、配布対象の6分類を掲載しています。')
        else:
            hierarchy_notes.append(f'{parent["name"]}は性質ごとのサブカテゴリに分かれています。')
    hierarchy_note_text = ' '.join(hierarchy_notes)
    (output / 'index.md').write_text(
        '# 分類辞書の収録一覧\n\n'
        f'{len(categories)}カテゴリ、全体で **{manifest["uniqueAdmittedPairs"]:,}組**、カテゴリ別に **{manifest["dictionaryRows"]:,}レコード**を収録しています。\n\n'
        '「組」は読み・表記の重複を除いた件数、「レコード」は品詞・コストの違いも保持したバイナリへの収録件数です。'
        '複数カテゴリへの所属があるため、カテゴリ別の組数の合計は全体の組数と一致しません。\n\n'
        '一覧は配布対象の固定データから全件生成しています。Geminiとassistantの暫定分類・未確認の読みを含みます。'
        f'{hierarchy_note_text} その他の既存カテゴリのコストと品詞は元辞書の値です。漢方・医療は提供元の読みと空欄へのGemini推定読み（未確認）を採用し、個別の読み訂正には出典を記録します。品詞とコストは本プロジェクトで設定しています。分類取得失敗・未分類・除外候補はこの一覧には含めません。\n\n'
        '[不採用語と判断理由](excluded/index.md) · [品詞IDと品詞名](pos.md) · [生成・配布手順](../classified-dictionary-distribution.md) · [漢方・医療の出典記録](../specialist-dictionaries.md)\n\n'
        + category_group_text
        + '\n'.join(table) + '\n\n'
        f'元データSHA-256: `{manifest["files"]["distribution-candidates.tsv.gz"]}`\n\n'
        '再生成: `python3 scripts/write_classified_dictionary_catalog.py`\n'
        '整合確認: `python3 scripts/write_classified_dictionary_catalog.py --check`\n', encoding='utf-8')
    person_replacement_summary = (
        generate_person_replacement_index(output, summary, person_taxonomy_summary)
        if person_taxonomy_summary is not None else None
    )
    pos = ['# 品詞IDと品詞名', '', '各レコードの左・右品詞IDは同じid.defを参照します。', '', '| ID | 品詞名 |', '|---:|---|']
    for line in (root / 'src/main/resources/id.def').read_text(encoding='utf-8').splitlines():
        number, name = line.split(maxsplit=1)
        pos.append(f'| {number} | {code(name)} |')
    (output / 'pos.md').write_text('\n'.join(pos) + '\n', encoding='utf-8')
    final_categories = summary + (person_taxonomy_summary['categories'] if person_taxonomy_summary is not None else [])
    result = dict(schemaVersion=1, inputSha256=manifest['files']['distribution-candidates.tsv.gz'],
                  uniquePairs=len(final_pairs) if person_taxonomy_summary is not None else manifest['uniqueAdmittedPairs'],
                  records=sum(category['records'] for category in final_categories), categories=final_categories)
    result['excluded'] = generate_excluded(root, output, manifest)
    if specialist_file.exists(): result['specialistInputSha256'] = extra['files']['distribution-candidates.tsv.gz']
    (output / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    expected_records = manifest['dictionaryRows'] - manifest['categoryRows'].get('person', 0) \
        if person_taxonomy_summary is not None else manifest['dictionaryRows']
    if sum(c['records'] for c in summary) != expected_records:
        raise ValueError('Catalog total differs from distributed records')
    return result


def hashes(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file()}


def hashes_for_check(generated, frozen, luna_ledger_available):
    if luna_ledger_available:
        return generated, frozen
    ignored = lambda path: path == 'summary.json' or path.startswith('excluded/')
    return ({path: digest for path, digest in generated.items() if not ignored(path)},
            {path: digest for path, digest in frozen.items() if not ignored(path)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    destination = args.root / 'docs/classified-dictionary-catalog'
    manifest = json.loads((args.root / 'src/main/classification/distribution-manifest.json').read_text())
    luna_record = manifest.get('provenance', {}).get('lunaReclassification')
    luna_ledger_available = not luna_record or (args.root / luna_record['path']).is_file()
    if not args.check and not luna_ledger_available:
        raise SystemExit('Local Luna ledger required to regenerate excluded-reason pages')
    distribution.verify(args.root)
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory) / 'catalog'
        summary = generate(args.root, staging)
        if args.check:
            generated_hashes, frozen_hashes = hashes_for_check(
                hashes(staging), hashes(destination), luna_ledger_available)
            if generated_hashes != frozen_hashes:
                raise SystemExit('Catalog differs from frozen distribution; regenerate it')
            if not luna_ledger_available:
                print('Local Luna ledger unavailable; excluded-reason pages and summary.json comparison skipped')
        else:
            if destination.exists(): shutil.rmtree(destination)
            shutil.copytree(staging, destination)
    print(f'Catalog: {len(summary["categories"])} categories, {summary["records"]} records, {sum(c["pages"] for c in summary["categories"])} pages')


if __name__ == '__main__':main()
