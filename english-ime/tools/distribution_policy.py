"""Read the explicit authoring-to-distribution exclusion boundary."""
import csv
import hashlib
import re
from pathlib import Path

import vocabulary_harness as h

DEFAULT=h.REPO/'english-ime/data/supplement/distribution-exclusions.tsv'
FIELDS=['surface','match','reason','evidence','license']
REASONS={'adult-industry-person','adult-industry-product-service','sexual-slang','victim-person','victim-related-subject'}


def tokens(text):
    normalized=text.replace('’',"'")
    lowered=normalized.lower()
    return {'exact:'+normalized,'fold:'+lowered,
        'sha256-exact:'+hashlib.sha256(normalized.encode()).hexdigest(),
        'sha256-casefold:'+hashlib.sha256(lowered.encode()).hexdigest()}


def rule_key(row):
    if row['match'].startswith('sha256-'):return row['match']+':'+row['surface']
    normalized=row['surface'].replace('’',"'")
    return ('fold:'+normalized.lower()) if row['match']=='casefold' else 'exact:'+normalized


def write(path,records):
    # Plain TSV matches the production reader, including literal quotation marks.
    # It is not CSV-with-tab-delimiters; no quoting transformation is introduced.
    for row in records:
        h.require(all(not any(c in row[field] for c in '\t\r\n') for field in FIELDS),'Control character in exclusion record')
    path.write_text('\t'.join(FIELDS)+'\n'+''.join('\t'.join(r[f] for f in FIELDS)+'\n' for r in records),encoding='utf-8')


def rows(path=DEFAULT):
    if not path.exists():return []
    with path.open(encoding='utf-8',newline='') as stream:
        reader=csv.DictReader(stream,delimiter='\t',quoting=csv.QUOTE_NONE)
        h.require(reader.fieldnames==FIELDS,'Invalid distribution exclusion header')
        records=list(reader)
    for row in records:
        h.require(row['surface'] and row['match'] in {'exact','casefold','sha256-exact','sha256-casefold'} and row['reason'] in REASONS and
                  row['evidence'].startswith('https://') and row['license'] in {'CC0-1.0','CC-BY-SA-4.0','CC-BY-SA-3.0','BSD-2-Clause'},'Invalid distribution exclusion evidence')
        h.require(not row['match'].startswith('sha256-') or re.fullmatch('[0-9a-f]{64}',row['surface']),
                  'Invalid hashed distribution key')
    h.require(len({(r['surface'],r['match'],r['reason'],r['evidence']) for r in records})==len(records),'Duplicate distribution exclusion')
    return records


def keys(path=DEFAULT):return {rule_key(r) for r in rows(path)}


def for_assets(assets,path=DEFAULT):
    properties=dict(line.rstrip('\n').split('=',1) for line in (assets/'grammar/bundle.properties').read_text().splitlines()
                    if '=' in line and not line.startswith('#'))
    digest=properties.get('distribution.policy.sha256')
    if not digest:return set()
    h.require(path.is_file() and h.replay.sha(path)==digest,'Distribution policy differs from the generated assets')
    return keys(path)


def excluded(surface,lemma,blocked):return bool((tokens(surface)|tokens(lemma))&blocked)
