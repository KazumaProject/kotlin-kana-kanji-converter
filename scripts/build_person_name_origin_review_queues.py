#!/usr/bin/env python3
"""Build compact, item-level review queues from a validated handoff dry-run ledger."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


EXPECTED_COUNTS = {
    'japanese_to_foreign_ai': 6641,
    'unconfirmed_to_foreign_ai': 8908,
    'dual_placement_227': 227,
    'unresolved_238': 238,
    'non_person_51': 51,
}

QUEUE_POLICIES = {
    'japanese_to_foreign_ai': (
        'For this exact reading and surface, verify the name form and its naming convention '
        'with independent sources; compare the proposal with the fixed mapping and preserve '
        'the candidate type unless a source supports a type correction.',
        'Change origin only when a source supports the specific name form and its naming '
        'convention. Do not infer origin from a bearer, nationality, script, or model output. '
        'Otherwise keep the current category and record why.',
    ),
    'unconfirmed_to_foreign_ai': (
        'For this exact reading and surface, identify the linguistic/name use and check an '
        'independent name or reference source; verify whether it is a surname, given name, '
        'or indivisible personal name.',
        'Promote from unconfirmed only when independent evidence supports both the name form '
        'and a non-Japanese naming convention. Model confidence or a matching bearer alone '
        'does not qualify.',
    ),
    'dual_placement_227': (
        'Check this exact form for independent Japanese-origin and foreign-origin uses, '
        'including the relevant name type. Review any existing category assignments one by one.',
        'Keep both origin categories only when evidence supports both naming conventions for '
        'this exact form. Correct a confirmed wrong origin; preserve unrelated categories. '
        'Use the matching unconfirmed category if evidence does not distinguish the origins.',
    ),
    'unresolved_238': (
        'Identify whether this exact reading/surface is a person name, its name type, and any '
        'reliable sources for its use and naming convention.',
        'Adopt an origin only when independent evidence supports this form and convention. '
        'Use an existing category for a supported correction; keep origin unconfirmed when '
        'the evidence remains ambiguous.',
    ),
    'non_person_51': (
        'Resolve the exact entity behind this reading/surface using an authoritative source; '
        'check whether it names a person, group, work, product, or another entity.',
        'Remove a person-name classification only when a source identifies this exact form '
        'as non-person. Keep a same-name public person if separately evidenced; otherwise '
        'retain the current row and record the unresolved identity.',
    ),
}


def stable_json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def word_list_bytes(rows):
    """Render a small, GitHub-readable reading/surface view of a review queue."""
    lines = ['reading (読み)\tsurface (表記)\n']
    for row in sorted(rows, key=lambda item: (item['reading'], item['surface'])):
        reading = row['reading']
        surface = row['surface']
        if any(char in reading or char in surface for char in ('\t', '\r', '\n')):
            raise ValueError('Reading and surface must not contain TSV delimiters')
        lines.append(f'{reading}\t{surface}\n')
    return ''.join(lines).encode('utf-8')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def queue_for(row):
    controls = set(row.get('control_queues') or ())
    if 'dual_placement_227' in controls:
        return 'dual_placement_227'
    if 'unresolved_238' in controls:
        return 'unresolved_238'
    if 'non_person_51' in controls:
        return 'non_person_51'

    proposal = row.get('first_pass_review') or {}
    if proposal.get('proposed_origin') != 'foreign':
        return None
    categories = row.get('current_categories') or []
    if len(categories) != 1:
        return None
    current_category = categories[0]
    if current_category.startswith(('surname_origin_', 'given_name_origin_',
                                   'personal_name_origin_')) and current_category.endswith('_unconfirmed'):
        return 'unconfirmed_to_foreign_ai'
    if current_category.startswith(('surname_origin_', 'given_name_origin_',
                                   'personal_name_origin_')) and current_category.endswith('_japanese'):
        return 'japanese_to_foreign_ai'
    return None


def compact_row(row, queue_name):
    first_pass = row.get('first_pass_review') or {}
    second_pass = row.get('second_pass_review') or {}
    second_result = second_pass.get('result') if isinstance(second_pass, dict) else None
    second_placement = second_pass.get('placement') if isinstance(second_pass, dict) else None
    investigate, accept = QUEUE_POLICIES[queue_name]
    source_rows = row.get('original_rows', [])
    source_fingerprints = row.get('source_row_fingerprints') or sorted({
        source_row['row_sha256'] for source_row in source_rows
        if isinstance(source_row.get('row_sha256'), str)
    })
    return {
        'candidate_key': row['candidate_key'],
        'reading': row['reading'],
        'surface': row['surface'],
        'source_row_fingerprints': source_fingerprints,
        'source_rows': source_rows,
        'current_categories': row.get('current_categories', []),
        'current_fixed_mapping': row.get('repository_fixed_mapping'),
        'first_pass': {
            'origin': first_pass.get('proposed_origin'),
            'name_type': first_pass.get('proposed_name_type'),
            'confidence': first_pass.get('confidence'),
            'reason': first_pass.get('reason'),
            'source_verified': first_pass.get('source_verified'),
        },
        'reanalysis': {
            'present': second_result is not None,
            'origin': second_result.get('second_origin') if second_result else None,
            'name_type': second_result.get('proposed_name_type') if second_result else None,
            'placement_action': (second_result.get('placement_action')
                                 if second_result else None),
            'source_verified': second_result.get('source_verified') if second_result else None,
            'source_urls': second_result.get('source_urls', []) if second_result else [],
        },
        'effective_proposal': row.get('effective_proposal'),
        'initial_source_review_status': row.get('initial_source_review_status', []),
        'review_status': 'pending_item_level_source_review',
        'investigation_required': investigate,
        'acceptance_criteria': accept,
    }


def build(ledger_path, output_dir, baseline_sha256):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    queues = {name: [] for name in EXPECTED_COUNTS}
    with gzip.open(ledger_path, 'rt', encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            queue_name = queue_for(row)
            if queue_name:
                queues[queue_name].append(compact_row(row, queue_name))

    manifest = {
        'schema_version': 1,
        'baseline_sha256': baseline_sha256,
        'source_ledger_sha256': sha256(ledger_path),
        'queue_counts': {},
        'queue_sha256': {},
        'word_list_sha256': {},
        'reanalysis_present': {},
    }
    for queue_name, rows in queues.items():
        rows.sort(key=lambda row: row['candidate_key'])
        expected = EXPECTED_COUNTS[queue_name]
        if len(rows) != expected:
            raise ValueError(f'{queue_name}: expected {expected} rows, found {len(rows)}')
        destination = output_dir / f'{queue_name}.jsonl.gz'
        with destination.open('wb') as raw:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as stream:
                for row in rows:
                    stream.write(stable_json(row))
        word_list = output_dir / f'{queue_name}.words.tsv'
        word_list.write_bytes(word_list_bytes(rows))
        manifest['queue_counts'][queue_name] = len(rows)
        manifest['queue_sha256'][queue_name] = sha256(destination)
        manifest['word_list_sha256'][queue_name] = sha256(word_list)
        manifest['reanalysis_present'][queue_name] = sum(
            row['reanalysis']['present'] for row in rows)
    (output_dir / 'manifest.json').write_bytes(stable_json(manifest))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', type=Path, required=True,
                        help='Validated expanded handoff dry-run JSONL.GZ (kept outside Git)')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--baseline-sha256', required=True,
                        help='SHA-256 of the source dictionary baseline used for the handoff')
    args = parser.parse_args()
    if len(args.baseline_sha256) != 64 or any(
            char not in '0123456789abcdef' for char in args.baseline_sha256):
        parser.error('--baseline-sha256 must be a lowercase SHA-256')
    print(json.dumps(build(args.ledger, args.output_dir, args.baseline_sha256),
                     ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
