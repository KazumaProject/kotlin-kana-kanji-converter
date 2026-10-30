"""Validate a private, committed dictionary-filter snapshot without exposing its records."""
import json
import os
from pathlib import Path
import re

REPOSITORY = 'KazumaProject/dictionary_filter_list'
STATUSES = {'source_reviewed'}
CATEGORY = re.compile(r'[a-z][a-z0-9_]*(?:/[a-z][a-z0-9_]*)*\.jsonl\Z')
REVISION = re.compile(r'[0-9a-f]{40}\Z')
SPORTS_ALLOW = 'decisions/person/protected_sports_collisions.jsonl'


def load_snapshot_details(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError('Dictionary filter snapshot is missing')
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    snapshot = json.loads((directory / 'snapshot.json').read_text(encoding='utf-8'))
    if manifest != {'schemaVersion': 1}:
        raise ValueError('Unsupported dictionary filter schema')
    revision = snapshot.get('revision')
    if (snapshot.get('schemaVersion') != 1 or snapshot.get('repository') != REPOSITORY
            or not isinstance(revision, str) or not REVISION.fullmatch(revision)):
        raise ValueError('Invalid dictionary filter snapshot metadata')
    categories = directory / 'categories'
    if not categories.is_dir():
        raise ValueError('Dictionary filter categories are missing')
    files = sorted(categories.rglob('*.jsonl'))
    if not files:
        raise ValueError('Dictionary filter categories are empty')
    pairs = set()
    for path in files:
        relative = path.relative_to(categories).as_posix()
        if not CATEGORY.fullmatch(relative) or path.is_symlink():
            raise ValueError('Invalid dictionary filter category path')
        seen = set()
        with path.open(encoding='utf-8') as stream:
            for number, line in enumerate(stream, 1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f'Invalid dictionary filter record at {relative}:{number}') from error
                if (not isinstance(row, dict) or set(row) != {'reading', 'surface', 'status', 'evidence'}
                        or any(not isinstance(row.get(field), str) or not row[field]
                               or any(c in row[field] for c in '\0\r\n\t') for field in ('reading', 'surface'))
                        or row.get('status') not in STATUSES
                        or not isinstance(row.get('evidence'), list) or not row['evidence']
                        or any(not isinstance(evidence, dict) for evidence in row['evidence'])):
                    raise ValueError(f'Invalid dictionary filter record at {relative}:{number}')
                pair = (row['reading'], row['surface'])
                if pair in seen:
                    raise ValueError(f'Duplicate dictionary filter record at {relative}:{number}')
                seen.add(pair)
                pairs.add(pair)
    protected_path = directory / SPORTS_ALLOW
    if protected_path.is_symlink():
        raise ValueError('Invalid protected sports decisions file')
    protected = set()
    if protected_path.is_file():
        with protected_path.open(encoding='utf-8') as stream:
            for number, line in enumerate(stream, 1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f'Invalid protected sports decision at line {number}') from error
                if (not isinstance(row, dict)
                        or set(row) != {'reading', 'surface', 'status', 'action', 'classification', 'sport', 'evidence'}
                        or any(not isinstance(row.get(field), str) or not row[field]
                               or any(c in row[field] for c in '\0\r\n\t')
                               for field in ('reading', 'surface', 'sport'))
                        or row.get('status') != 'source_reviewed' or row.get('action') != 'allow'
                        or row.get('classification') != 'person/sports'
                        or not isinstance(row.get('evidence'), list) or not row['evidence']
                        or any(not isinstance(evidence, dict) for evidence in row['evidence'])):
                    raise ValueError(f'Invalid protected sports decision at line {number}')
                pair = (row['reading'], row['surface'])
                if pair in protected:
                    raise ValueError(f'Duplicate protected sports decision at line {number}')
                protected.add(pair)
    pairs.difference_update(protected)
    if not pairs:
        raise ValueError('Dictionary filter has no active records')
    return revision, frozenset(pairs), frozenset(protected)


def load_snapshot(directory):
    revision, pairs, _ = load_snapshot_details(directory)
    return revision, pairs


def current_snapshot_details():
    directory = os.environ.get('DICTIONARY_FILTER_SNAPSHOT')
    if not directory:
        raise ValueError('DICTIONARY_FILTER_SNAPSHOT is required for dictionary generation')
    return load_snapshot_details(directory)


def current_snapshot():
    revision, pairs, _ = current_snapshot_details()
    return revision, pairs
