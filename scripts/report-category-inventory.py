#!/usr/bin/env python3
"""Summarize actual classification audit and release ZIPs; no inferred coverage."""
import argparse, collections, csv, gzip, hashlib, json, zipfile
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--reports', default='build/reports/dictionary-quality')
p.add_argument('--category-zip', default='build/linux-ci/packages/build/category-release/categorized-dictionaries.zip')
p.add_argument('--legacy-zip', default='build/linux-ci/packages/release_zips/japanese_keyboard_dictionary_assets.zip')
p.add_argument('--output', default='docs/dictionary-inventory.json')
a = p.parse_args()
root = Path(a.reports)
source_names = {'person': 'MozcUT 人名', 'place': 'MozcUT 地名', 'wiki': 'Wiki のみ', 'neologd': 'Neologd のみ', 'common': 'Wiki・Neologd 共通'}
categories = {}
source_stats = {s: collections.Counter() for s in source_names}
category_sources = collections.defaultdict(collections.Counter)
matrix = collections.Counter()
held_reasons = collections.Counter()
normalization = collections.Counter()
reading_proofs = collections.Counter()
pairs = set()
surfaces = set()
readings = set()
multi = collections.Counter()
with gzip.open(root / 'audit.tsv.gz', 'rt', encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        if r['phase'] != 'classification':
            normalization[r['reason']] += 1
            continue
        classified = r['categories'] != 'unclassified'
        included = r['quality_status'] == 'accepted' and classified
        matrix[f"{r['quality_status']}/{'classified' if classified else 'unclassified'}"] += 1
        for source in r['sources'].split(','):
            source_stats[source]['normalizedEntries'] += 1
            source_stats[source]['includedEntries' if included else 'reviewEntries'] += 1
        if not included:
            if r['quality_status'] == 'held':
                held_reasons[r['reading_evidence']] += 1
            continue
        pair = (r['reading'], r['surface'])
        pairs.add(pair); surfaces.add(r['surface']); readings.add(r['reading'])
        cs = r['categories'].split(',')
        if len(cs) > 1:
            multi[r['categories']] += 1
        proof = r['reading_evidence']
        for name, found in [('Mozc同一読み・表記', 'mozc-exact-reading-surface' in proof), ('日本郵便', 'post.japanpost.jp' in proof), ('Wikidata読み', '#P1814' in proof), ('JMdict制約付きペア', 'edrdg.org' in proof), ('かな表記と対象確認', 'orthographic-kana' in proof), ('確認済み対応表', all(v not in proof for v in ['post.japanpost.jp','mozc-exact-reading-surface','#P1814','edrdg.org','orthographic-kana']))]:
            if found: reading_proofs[name] += 1
        for c in cs:
            item = categories.setdefault(c, {'entries': 0, 'pairs': set(), 'surfaces': set(), 'readings': set()})
            item['entries'] += 1; item['pairs'].add(pair); item['surfaces'].add(r['surface']); item['readings'].add(r['reading'])
            for source in r['sources'].split(','): category_sources[c][source] += 1
for c, item in categories.items():
    for key in ['pairs', 'surfaces', 'readings']: item[key] = len(item[key])
    item['sources'] = dict(category_sources[c])

def archive(path):
    path = Path(path)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        result = {'name': path.name, 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'files': [{'path': i.filename, 'bytes': i.file_size} for i in z.infolist()]}
        if 'manifest.json' in z.namelist():
            result['manifest'] = json.loads(z.read('manifest.json'))
            for c, item in categories.items():
                item['binaryBytes'] = sum(z.getinfo(f'{c}/{n}.dat').file_size for n in ['yomi', 'tango', 'token'])
        return result
category_zip = archive(a.category_zip)
assert {c: item['entries'] for c, item in categories.items()} == category_zip['manifest']['categories'], 'Audit/category manifest counts differ'
assert sum(matrix.values()) == json.loads((root/'summary.json').read_text())['normalizedEntries'], 'Audit/summary counts differ'
legacy_zip = archive(a.legacy_zip)
result = {'generatedFrom': {'inputManifest': category_zip['manifest'].get('inputManifest'), 'auditFile': 'audit.tsv.gz'}, 'auditSha256': hashlib.sha256((root/'audit.tsv.gz').read_bytes()).hexdigest(), 'summary': json.loads((root/'summary.json').read_text()), 'units': 'entries=reading/surface/left_id/right_id; pairs=reading/surface; source and category totals overlap', 'uniqueIncluded': {'pairs': len(pairs), 'surfaces': len(surfaces), 'readings': len(readings)}, 'qualityCategoryMatrix': dict(matrix), 'heldReasons': dict(held_reasons), 'sourceStats': {s: dict(v) for s,v in source_stats.items()}, 'categories': categories, 'multipleCategoryEntries': sum(multi.values()), 'multipleCategoryCombinations': dict(multi), 'readingProofsOverlapping': dict(reading_proofs), 'normalizationAuditReasons': dict(normalization), 'categoryArchive': category_zip, 'legacyArchive': legacy_zip}
Path(a.output).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'output': a.output, 'uniqueIncluded': result['uniqueIncluded'], 'matrix': result['qualityCategoryMatrix'], 'multipleCategoryEntries': result['multipleCategoryEntries']},ensure_ascii=False))
