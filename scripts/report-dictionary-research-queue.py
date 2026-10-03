#!/usr/bin/env python3
"""Preserve unresolved candidates without interpreting missing evidence as error."""
import argparse
import collections
import csv
import gzip
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--audit', default='build/reports/dictionary-quality/audit.tsv.gz')
p.add_argument('--output', default='build/reports/dictionary-quality/research')
a = p.parse_args()
out = Path(a.output)
out.mkdir(parents=True, exist_ok=True)
counts = collections.Counter()
with gzip.open(a.audit, 'rt') as source, gzip.open(out / 'pending.tsv.gz', 'wt') as target:
    fields = ['group', 'priority', 'reading', 'surface', 'left_id', 'right_id', 'sources', 'categories', 'verification_issue', 'semantic_issue', 'reading_evidence', 'reason']
    writer = csv.DictWriter(target, fieldnames=fields, delimiter='\t', lineterminator='\n')
    writer.writeheader()
    for row in csv.DictReader(source, delimiter='\t'):
        if row['phase'] != 'classification' or (row['quality_status'] == 'accepted' and row['categories'] != 'unclassified'):
            continue
        if row['quality_status'] == 'accepted':
            group = 'classification-missing'
        elif row['verification_issue'] == 'entity-reading-unresolved-not-pair-error':
            group = 'name-reading-binding-unresolved'
        elif row['categories'] == 'unclassified':
            group = 'reading-and-referent-missing'
        else:
            group = 'reading-missing'
        priority = '1' if any(c in row['categories'].split(',') for c in ['general', 'technical', 'food', 'product']) else ('2' if row['categories'] != 'unclassified' else '3')
        counts[(group, priority)] += 1
        writer.writerow({'group': group, 'priority': priority, **{k: row[k] for k in fields[2:]}})
result = {'unresolved': sum(counts.values()), 'groups': {'/'.join(k): n for k, n in sorted(counts.items())}, 'meaning': 'Missing reading, referent binding or classification is not a confirmed wrong candidate. Explicit wrong pairs are excluded in the audit, not in this queue.'}
(out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
