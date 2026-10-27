#!/usr/bin/env python3
"""Apply the fixed manual name-type review to the checked-in person dictionary."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile

import classified_distribution as distribution
import person_name_origin_classification as origins


def read_rows(path):
    rows = []
    seen = set()
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
        for number, line in enumerate(stream, 1):
            row = line.rstrip('\n').split('\t')
            if len(row) != 7:
                raise ValueError(f'{path}:{number}: expected seven columns')
            if tuple(row) in seen:
                raise ValueError(f'{path}:{number}: duplicate person dictionary row')
            seen.add(tuple(row))
            rows.append(row)
    return rows


def reviewed_rows(root, manifest):
    review_manifest = manifest.get('manual_type_review')
    if not isinstance(review_manifest, dict):
        raise ValueError('Fixed name-origin manifest has no manual type review')
    path = root / review_manifest['review_path']
    with path.open(encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    return rows


def apply_type_review(rows, mapping, reviews, category_order, *, first_sync=False):
    """Change only reviewed output categories; preserve every candidate field otherwise."""
    review_by_key = {}
    for row in reviews:
        reading, surface = row['reading'], row['surface']
        key = origins.candidate_key(reading, surface)
        if (row.get('candidate_key') != key or key in review_by_key
                or mapping.get(key) != (row.get('source_category_id'),
                                        row.get('target_category_id'))
                or row.get('previous_dictionary_category_id') not in category_order):
            raise ValueError('Manual type review differs from its fixed mapping or category')
        review_by_key[key] = row

    output = []
    observed = set()
    changed_records = 0
    excluded_records = 0
    for source_row in rows:
        row = list(source_row)
        key = origins.candidate_key(row[1], row[5])
        review = review_by_key.get(key)
        if review is None:
            if row[0] not in category_order:
                raise ValueError(f'Unknown person taxonomy category: {row[0]}')
            output.append(row)
            continue

        observed.add(key)
        previous_category = review['previous_dictionary_category_id']
        target_category = review['target_category_id']
        if row[0] == previous_category:
            if target_category == 'excluded_non_person':
                excluded_records += 1
                continue
            row[0] = target_category
            changed_records += 1
        elif row[0] == target_category and target_category != 'excluded_non_person':
            pass  # Idempotent after the reviewed output has already been synchronized.
        else:
            raise ValueError(
                f'Reviewed dictionary row has unexpected category for {row[1]} / {row[5]}')
        output.append(row)

    required_keys = {
        key for key, review in review_by_key.items()
        if review['target_category_id'] != 'excluded_non_person'
    }
    if required_keys - observed:
        raise ValueError(f'Reviewed person candidates are missing: {len(required_keys - observed)}')
    if first_sync and observed != set(review_by_key):
        raise ValueError('Initial type-review sync requires every reviewed source candidate')

    output.sort(key=lambda row: (
        category_order[row[0]], len(row[1]), row[1], row[5],
        int(row[2]), int(row[3]), int(row[4]), row[6],
    ))
    return output, {'reviewed_pairs': len(review_by_key),
                    'changed_records': changed_records,
                    'excluded_records': excluded_records,
                    'records_before': len(rows),
                    'records_after': len(output)}


def sync(root):
    root = root.resolve()
    mapping, manifest = origins.load_fixed_mapping(root)
    reviews = reviewed_rows(root, manifest)
    taxonomy = json.loads((root / origins.TAXONOMY_PATH).read_text(encoding='utf-8'))
    category_order = {row['id']: row['number'] for row in taxonomy['categories']}
    dictionary_path = root / origins.SOURCE_PATH
    source_hash = distribution.sha(dictionary_path)
    source_rows = read_rows(dictionary_path)
    review_manifest = manifest['manual_type_review']
    first_sync = 'dictionary_artifact' not in review_manifest
    rows, counts = apply_type_review(
        source_rows, mapping, reviews, category_order, first_sync=first_sync)

    with tempfile.NamedTemporaryFile(dir=dictionary_path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        distribution.write_gzip(temporary_path, rows)
        result_hash = distribution.sha(temporary_path)
        artifact = review_manifest.get('dictionary_artifact', {})
        prior_hash = artifact.get('previous_sha256', source_hash)
        review_manifest['dictionary_artifact'] = {
            'path': origins.SOURCE_PATH,
            'previous_sha256': prior_hash,
            'sha256': result_hash,
            'records_before': artifact.get('records_before', len(source_rows)),
            'records': len(rows),
            'reviewed_pairs': counts['reviewed_pairs'],
            'changed_records': artifact.get('changed_records', counts['changed_records']),
            'excluded_records': artifact.get('excluded_records', counts['excluded_records']),
        }
        temporary_path.replace(dictionary_path)
        origins.write_json(root / origins.MANIFEST_PATH, manifest)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return {**counts, 'source_sha256': source_hash, 'result_sha256': result_hash}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=origins.ROOT)
    args = parser.parse_args()
    print(json.dumps(sync(args.root), ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
