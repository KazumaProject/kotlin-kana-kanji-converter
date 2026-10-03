#!/usr/bin/env python3
"""Produce a stable stratified review sample. Selection does not mark it reviewed."""
import argparse, collections, csv, gzip, hashlib, heapq, json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--before', default='build/reports/dictionary-quality-before/audit.tsv.gz')
parser.add_argument('--after', default='build/reports/dictionary-quality/audit.tsv.gz')
parser.add_argument('--output', default='build/reports/dictionary-quality/review-sample.tsv')
parser.add_argument('--count', type=int, default=500)
args = parser.parse_args()
def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        yield from csv.DictReader(handle, delimiter='\t')
def key(row):
    return row['reading'], row['surface'], row['left_id'], row['right_id']
before = {key(r): set(r['categories'].split(',')) for r in rows(args.before) if r['phase'] == 'classification'}
counts = collections.Counter()
strata = collections.defaultdict(list)
for row in rows(args.after):
    if row['phase'] != 'classification' or row['quality_status'] != 'accepted' or row['categories'] == 'unclassified':
        continue
    old = before.get(key(row), {'unclassified'})
    if old != {'unclassified'} and not (set(row['categories'].split(',')) - old):
        continue
    bucket = row['categories'], row['sources']
    counts[bucket] += 1
    digest = int(hashlib.sha256('\t'.join(key(row)).encode()).hexdigest(), 16)
    heap = strata[bucket]
    item = (-digest, key(row), row)
    if len(heap) < args.count:
        heapq.heappush(heap, item)
    elif item > heap[0]:
        heapq.heapreplace(heap, item)
queues = {bucket: [r for _, _, r in sorted(heap, reverse=True)] for bucket, heap in strata.items()}
selected = []
while len(selected) < args.count and any(queues.values()):
    for bucket in sorted(queues):
        if queues[bucket]:
            selected.append(queues[bucket].pop(0))
            if len(selected) == args.count:
                break
assert len(selected) == args.count, f'Only {len(selected)} eligible entries'
output = Path(args.output)
output.parent.mkdir(parents=True, exist_ok=True)
columns = ['reading', 'surface', 'categories', 'sources', 'reading_evidence', 'reason', 'left_id', 'right_id', 'verdict', 'review_note']
with output.open('w', encoding='utf-8', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=columns, delimiter='\t')
    writer.writeheader()
    for row in selected:
        writer.writerow({**{k: row[k] for k in columns if k in row}, 'verdict': 'pending', 'review_note': ''})
summary = {'eligibleNewEntries': sum(counts.values()), 'selectedEntries': len(selected), 'beforeSha256': hashlib.sha256(Path(args.before).read_bytes()).hexdigest(), 'afterSha256': hashlib.sha256(Path(args.after).read_bytes()).hexdigest(), 'strata': [{'categories': k[0], 'sources': k[1], 'eligible': v, 'selected': sum((r['categories'],r['sources']) == k for r in selected)} for k,v in sorted(counts.items())]}
output.with_suffix('.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'eligibleNewEntries':sum(counts.values()),'selectedEntries':len(selected),'strata':len(counts)}))
