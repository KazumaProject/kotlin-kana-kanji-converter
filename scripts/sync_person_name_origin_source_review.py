#!/usr/bin/env python3
"""Apply audited source-backed origin changes to the person dictionary source."""
import argparse
import gzip
import json
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
    review_manifest = manifest.get('source_origin_review')
    if not isinstance(review_manifest, dict):
        raise ValueError('Fixed name-origin manifest has no source-origin review')
    path = root / review_manifest['review_path']
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def apply_source_origin_review(rows, mapping, reviews, category_order):
    """Change only the reviewed origin category, preserving unrelated rows and fields."""
    review_by_key = {}
    for review in reviews:
        key = review['candidate_key']
        if review['status'] != 'applied':
            continue
        if (key in review_by_key
                or mapping.get(key) != (review['source_category_id'],
                                        review['target_category_id'])
                or review.get('previous_dictionary_category_id') not in category_order
                or review['target_category_id'] not in category_order):
            raise ValueError('Source-origin review differs from its mapping or category')
        review_by_key[key] = review

    output = []
    observed = set()
    changed_rows = 0
    changed_pairs = set()
    for source_row in rows:
        row = list(source_row)
        key = origins.candidate_key(row[1], row[5])
        review = review_by_key.get(key)
        if review is None:
            if row[0] not in category_order:
                raise ValueError(f'Unknown person taxonomy category: {row[0]}')
            output.append(row)
            continue

        previous_category = review['previous_dictionary_category_id']
        target_category = review['target_category_id']
        if row[0] == previous_category:
            row[0] = target_category
            changed_rows += 1
            changed_pairs.add(key)
            observed.add(key)
        elif row[0] == target_category:
            observed.add(key)
        # A different category for the same form is an unrelated membership.
        # Leave it intact; each reviewed pair must still have its origin row.
        output.append(row)

    if set(review_by_key) - observed:
        missing = len(set(review_by_key) - observed)
        raise ValueError(f'Source-reviewed dictionary candidates are missing or stale: {missing}')

    output.sort(key=lambda row: (
        category_order[row[0]], len(row[1]), row[1], row[5],
        int(row[2]), int(row[3]), int(row[4]), row[6],
    ))
    return output, {
        'reviewed_pairs': len(review_by_key),
        'changed_pairs': len(changed_pairs),
        'changed_rows': changed_rows,
        'records_before': len(rows),
        'records_after': len(output),
        'held_pairs': sum(review['status'] == 'held' for review in reviews),
    }


def sync(root):
    root = Path(root).resolve()
    mapping, manifest = origins.load_fixed_mapping(root)
    reviews = reviewed_rows(root, manifest)
    taxonomy = json.loads((root / origins.TAXONOMY_PATH).read_text(encoding='utf-8'))
    category_order = {row['id']: row['number'] for row in taxonomy['categories']}
    dictionary_path = root / origins.SOURCE_PATH
    source_hash = distribution.sha(dictionary_path)
    source_rows = read_rows(dictionary_path)
    result_rows, counts = apply_source_origin_review(
        source_rows, mapping, reviews, category_order)

    with tempfile.NamedTemporaryFile(dir=dictionary_path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        distribution.write_gzip(temporary_path, result_rows)
        result_hash = distribution.sha(temporary_path)
        review_manifest = manifest['source_origin_review']
        prior_artifact = review_manifest.get('dictionary_artifact', {})
        review_manifest['dictionary_artifact'] = {
            'path': origins.SOURCE_PATH,
            'previous_sha256': prior_artifact.get('previous_sha256', source_hash),
            'sha256': result_hash,
            'records_before': prior_artifact.get('records_before', len(source_rows)),
            'records': len(result_rows),
            'reviewed_pairs': counts['reviewed_pairs'],
            'changed_pairs': prior_artifact.get('changed_pairs', counts['changed_pairs']),
            'changed_rows': prior_artifact.get('changed_rows', counts['changed_rows']),
            'held_pairs': counts['held_pairs'],
        }
        temporary_path.replace(dictionary_path)
        origins.write_json(root / origins.MANIFEST_PATH, manifest)
        # Revalidate the manifest against the synchronized dictionary artifact.
        origins.load_fixed_mapping(root)
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
