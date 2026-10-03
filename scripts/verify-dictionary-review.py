#!/usr/bin/env python3
"""Stop publication if the current audit has not received the recorded review."""
import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--audit', default='build/reports/dictionary-quality/audit.tsv.gz')
p.add_argument('--review-dir', default='src/main/dictionary-quality')
a = p.parse_args()
root = Path(a.review_dir)
summary = json.loads((root / 'review-v2-summary.json').read_text())
audit_hash = hashlib.file_digest(open(a.audit, 'rb'), 'sha256').hexdigest()
assert audit_hash == summary['currentAuditSha256'], 'Audit differs from reviewed edition; review the changed candidates before publication'
samples = {}
for name in ('review-v2-adopted.tsv', 'review-v2-held.tsv'):
    file = root / name
    assert hashlib.file_digest(file.open('rb'), 'sha256').hexdigest() == summary['files'][name], f'Review checksum mismatch: {name}'
    with file.open() as f:
        samples[name] = list(csv.DictReader(f, delimiter='\t'))
positive = samples['review-v2-adopted.tsv']
counts = Counter(r['category'] for r in positive)
assert dict(counts) == summary['adoptedReviewCounts']
assert all(n >= min(100, summary['newAdoptedByCategory'][c]) for c, n in counts.items())
assert len(counts) == 12 and len(samples['review-v2-held.tsv']) == 500
assert len({tuple(r[k] for k in ('reading', 'surface', 'left_id', 'right_id')) for r in samples['review-v2-held.tsv']}) == 500
assert all(r['finding'] and r['method'] for rows in samples.values() for r in rows)
targets = {(r['reading'], r['surface'], r['left_id'], r['right_id'], r['category']) for r in positive}
with gzip.open(a.audit, 'rt') as f:
    for row in csv.DictReader(f, delimiter='\t'):
        if row['phase'] == 'classification' and row['quality_status'] == 'accepted':
            for category in row['categories'].split(','):
                targets.discard((row['reading'], row['surface'], row['left_id'], row['right_id'], category))
assert not targets, 'Reviewed positive entries are missing from current dictionaries'
print(json.dumps({'auditSha256': audit_hash, 'adoptedReviewed': len(positive), 'heldReviewed': 500, 'passed': True}))
