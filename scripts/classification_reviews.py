"""Persistent, offline review overlays; model judgments remain manual, not verified."""
import collections
import contextlib
import fcntl
import gzip
import json
import re
from pathlib import Path

DIRECTORY = Path('src/main/classification')


def resulting_origin(entry):
    baseline = entry['baseline']
    if entry['action'] in ('hold', 'exclude'):
        return ('manual' if entry.get('evidence', {}).get('kind') == 'model_review'
                else baseline[3] if baseline else 'manual')
    if entry.get('media_demographic'):
        return entry.get('classification_origin', baseline[3] if baseline else 'manual')
    return 'verified' if entry.get('evidence', {}).get('kind') == 'independent_source' else 'manual'


def paths(root):
    return sorted(str(p.relative_to(root)) for p in (root / DIRECTORY / 'reviews').glob('*.jsonl'))


def load(root, selected=None):
    import classified_distribution as d
    allowed = {c['id'] for c in json.loads((root / DIRECTORY / 'categories.json').read_text())['categories']}
    if (root / d.TERM_TAXONOMY_PATH).is_file():
        # Historic review baselines use the former structural parent ID.
        allowed.add('term')
    if (root / d.EVENT_TAXONOMY_PATH).is_file():
        # Historic event review baselines use the former structural parent ID.
        allowed.add('event')
    ids = {int(line.split(maxsplit=1)[0]) for line in (root / 'src/main/resources/id.def').read_text().splitlines()}
    latest = {}
    for relative in paths(root) if selected is None else selected:
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or path.parent != DIRECTORY / 'reviews' or path.suffix != '.jsonl':
            raise ValueError('Review files must be JSONL under src/main/classification/reviews')
        for number, line in enumerate((root / path).read_text(encoding='utf-8').splitlines(), 1):
            entry = json.loads(line)
            for field in ('reading', 'surface', 'reason', 'candidate_key'):
                value = entry.get(field)
                if not isinstance(value, str) or not value or any(c in value for c in '\t\r\n\0'):
                    raise ValueError(f'{path}:{number}: invalid {field}')
            pair = entry['reading'], entry['surface']
            if entry['candidate_key'] != d.key(*pair):
                raise ValueError('Invalid review candidate key')
            action = entry.get('action')
            if action not in ('hold', 'exclude', 'keep', 'reclassify', 'add'):
                raise ValueError('Unknown review action')
            if 'baseline' not in entry:
                raise ValueError('Review must retain its original baseline decision')
            baseline = entry['baseline']
            if baseline is not None:
                if (not isinstance(baseline, list) or len(baseline) != 5 or baseline[:2] != list(pair)
                        or not all(isinstance(x, str) for x in baseline)
                        or baseline[3] not in ('verified', 'manual', 'gemini', 'no_result')
                        or baseline[4] not in ('classified', 'excluded', 'unclassified', 'no_result')
                        or not set(filter(None, baseline[2].split(','))) <= allowed):
                    raise ValueError('Invalid review baseline')
            elif not entry.get('added_record'):
                raise ValueError('New review pair requires an added_record')
            if pair in latest and (latest[pair]['baseline'] != baseline
                                  or latest[pair].get('added_record') != entry.get('added_record')):
                raise ValueError('Review history changed the original baseline/added record')
            record = entry.get('added_record')
            if record is not None:
                if (baseline is not None or not isinstance(record, dict)
                        or any(type(record.get(k)) is not int for k in ('left_id', 'right_id', 'cost'))):
                    raise ValueError('Invalid added record')
                if (record['left_id'] not in ids or record['right_id'] not in ids
                        or not -32768 <= record['cost'] <= 32767):
                    raise ValueError('Invalid review POS/cost')
            evidence = entry.get('evidence', {})
            demographic = entry.get('media_demographic')
            demographic_categories = set(d.MEDIA_DEMOGRAPHIC_LABEL_CATEGORIES.values())
            review_categories = entry.get('categories', [])
            tagged_categories = (set(review_categories) & demographic_categories
                                 if isinstance(review_categories, list)
                                 and all(isinstance(value, str) for value in review_categories) else set())
            if demographic is not None:
                reference = evidence.get('reference')
                previous = latest.get(pair)
                expected_origin = resulting_origin(previous) if previous else baseline[3] if baseline else None
                valid_source_baseline = (
                    baseline is not None and baseline[4] == 'classified'
                    or baseline is None and isinstance(entry.get('added_record'), dict)
                )
                if (not isinstance(demographic, str) or demographic not in d.MEDIA_DEMOGRAPHIC_LABELS
                        or not valid_source_baseline
                        or entry.get('classification_origin') not in ('verified', 'manual', 'gemini')
                        or entry.get('classification_origin') != expected_origin
                        or evidence.get('kind') != 'media_demographic_source'
                        or evidence.get('reading') != pair[0] or evidence.get('surface') != pair[1]
                        or evidence.get('categories') != review_categories
                        or not isinstance(reference, str) or not reference.startswith('https://')):
                    raise ValueError('Media demographic review requires a source-backed classified pair')
                if demographic == 'adult':
                    if action != 'exclude' or review_categories != []:
                        raise ValueError('Adult media demographic reviews must exclude the pair from all dictionaries')
                else:
                    expected_category = d.MEDIA_DEMOGRAPHIC_LABEL_CATEGORIES[demographic]
                    if (action not in ('keep', 'reclassify') or expected_category not in review_categories
                            or tagged_categories != {expected_category}):
                        raise ValueError('Audience demographic reviews must include exactly their matching category')
            elif tagged_categories:
                raise ValueError('Media demographic category requires its review label and source evidence')
            if evidence.get('kind') == 'model_review':
                if (action not in ('exclude', 'reclassify') or baseline is None
                        or baseline[4] != 'classified' or record is not None
                        or action == 'exclude' and entry.get('categories')):
                    raise ValueError('Model reviews only exclude or reclassify existing admitted pairs')
                if (evidence.get('model') != 'gpt-5.6-luna'
                        or evidence.get('reasoning_effort') != 'max'
                        or evidence.get('target_revision') != '8ec94757d48d58ac6a5ca2c3baccfcbb48d45003'
                        or not isinstance(evidence.get('response_sha256'), str)
                        or not re.fullmatch('[0-9a-f]{64}', evidence['response_sha256'])
                        or evidence.get('reading') != pair[0] or evidence.get('surface') != pair[1]
                        or evidence.get('categories') != entry.get('categories', [])
                        or not isinstance(evidence.get('reference'), str) or not evidence['reference']):
                    raise ValueError('Invalid model review provenance')
            if action in ('keep', 'reclassify', 'add'):
                cats = entry.get('categories')
                if (not isinstance(cats, list) or not cats or not all(isinstance(value, str) for value in cats)
                        or len(set(cats)) != len(cats) or not set(cats) <= allowed):
                    raise ValueError('Invalid review categories')
                if evidence.get('kind') not in (
                        'user_confirmation', 'independent_source', 'media_demographic_source', 'model_review'):
                    raise ValueError('Review requires an identified evidence kind')
                if (evidence.get('reading') != pair[0] or evidence.get('surface') != pair[1]
                        or evidence.get('categories') != cats or not evidence.get('reference')):
                    raise ValueError('Review evidence must identify the reading, surface and categories')
                if action == 'add' and baseline is not None:
                    raise ValueError('Add requires a new pair')
            latest[pair] = entry
    return latest


def apply(decisions, entries, validate_baseline=True):
    result = {pair: list(row) for pair, row in decisions.items()}
    for pair, entry in entries.items():
        if validate_baseline and result.get(pair) != entry['baseline']:
            raise ValueError(f'Review baseline differs from input: {pair}')
        baseline = entry['baseline']
        if entry['action'] in ('hold', 'exclude'):
            origin = resulting_origin(entry)
            result[pair] = [*pair, baseline[2] if baseline else '', origin, 'excluded']
        else:
            cats = ','.join(sorted(entry['categories']))
            origin = resulting_origin(entry)
            result[pair] = [*pair, cats, origin, 'classified']
    return result


def restore(decisions, entries):
    result = {pair: list(row) for pair, row in decisions.items()}
    for pair, entry in entries.items():
        if entry['baseline'] is None:
            result.pop(pair, None)
        else:
            result[pair] = list(entry['baseline'])
    return result


def added_rows(entries):
    for pair, entry in entries.items():
        record = entry.get('added_record')
        if record:
            yield (pair[0], str(record['left_id']), str(record['right_id']), str(record['cost']), pair[1])


def candidate_rows(root, decisions, entries):
    import classified_distribution as d
    rows = set()
    for _, row in d.source_rows(root):
        decision = decisions.get((row[0], row[4]))
        if decision and decision[4] == 'classified':
            rows.update((category, *row) for category in decision[2].split(','))
    for row in added_rows(entries):
        decision = decisions[(row[0], row[4])]
        if decision[4] == 'classified':
            rows.update((category, *row) for category in decision[2].split(','))
    return rows


def update_manifest(root, manifest, decisions, rows, selected):
    import classified_distribution as d
    previous = manifest['provenance'].get('reviews', [])
    for relative in previous:
        manifest['inputs'].pop(relative, None)
    manifest['provenance']['reviews'] = selected
    manifest['inputs'].update({path: d.sha(root / path) for path in selected})
    luna_exclusions = manifest['provenance'].get('lunaReclassification', {}).get('effectiveActions', {}).get('reject', 0)
    manifest['provenance'].setdefault('reviewBaseExcludedCandidatePairs', manifest['excludedCandidatePairs'] - luna_exclusions)
    entries = load(root, selected)
    category_data = json.loads((root / DIRECTORY / 'categories.json').read_text(encoding='utf-8'))
    category_ids = [category['id'] for category in category_data['categories']]
    demographic_taxonomy = root / d.MEDIA_DEMOGRAPHIC_TAXONOMY_PATH
    if demographic_taxonomy.is_file():
        manifest['inputs'][d.MEDIA_DEMOGRAPHIC_TAXONOMY_PATH] = d.sha(demographic_taxonomy)
        limitations = manifest.setdefault('limitations', [])
        if d.MEDIA_DEMOGRAPHIC_LIMITATION not in limitations:
            limitations.append(d.MEDIA_DEMOGRAPHIC_LIMITATION)
    manifest['categoryGroups'] = category_data.get('categoryGroups', [])
    new_exclusions = sum(int(entry['action'] in ('hold', 'exclude')) -
                         int(entry['baseline'] is not None and entry['baseline'][4] == 'excluded')
                         for entry in entries.values())
    manifest['excludedCandidatePairs'] = manifest['provenance']['reviewBaseExcludedCandidatePairs'] + new_exclusions + luna_exclusions
    origins = collections.Counter(row[3] for row in decisions.values() if row[4] == 'classified')
    counts = collections.Counter(row[0] for row in rows)
    manifest.update(admittedPairsByOrigin=dict(origins), uniqueAdmittedPairs=sum(origins.values()),
                    categoryRows={category: counts[category] for category in category_ids}, dictionaryRows=len(rows),
                    excludedClassifiedPairs=sum(row[4] == 'excluded' for row in decisions.values()),
                    unclassifiedPairs=sum(row[4] == 'unclassified' for row in decisions.values()),
                    noResultPairs=sum(row[4] == 'no_result' for row in decisions.values()))


@contextlib.contextmanager
def locked(root):
    work = root / 'build/classification-audit'; work.mkdir(parents=True, exist_ok=True)
    with (work / 'reviews.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Another review apply/recovery is running') from error
        yield


def apply_saved(root, commit=False):
    with locked(root.resolve()):
        return _apply_saved(root, commit)


def _apply_saved(root, commit=False):
    """Validate staged data before replacing it; retain recovery copies and a journal."""
    import classified_distribution as d
    import shutil
    import tempfile
    root = root.resolve()
    journal = root / 'build/classification-audit/apply-journal.json'
    if journal.exists():
        raise ValueError('Interrupted apply: run recover-reviews before applying again')
    d.verify(root, allow_pending_reviews=True)
    directory = root / DIRECTORY
    manifest = json.loads((directory / 'distribution-manifest.json').read_text())
    old_entries = load(root, manifest['provenance'].get('reviews', []))
    with gzip.open(directory / 'distribution-decisions.tsv.gz', 'rt', encoding='utf-8') as f:
        decisions = {tuple(row[:2]): row for row in (line.rstrip('\n').split('\t') for line in f)}
    baseline = restore(decisions, old_entries)
    selected = paths(root)
    entries = load(root, selected)
    # Removing a registered ledger would silently erase audit history.
    if not set(manifest['provenance'].get('reviews', [])) <= set(selected):
        raise ValueError('Registered review history is missing')
    reviewed = apply(baseline, entries)
    reviewed = d.apply_term_classifications(root, reviewed, reviewed_pairs=entries)
    reviewed = d.apply_event_classifications(root, reviewed, reviewed_pairs=entries)
    rows = candidate_rows(root, reviewed, entries)
    before = manifest['dictionaryRows']
    old_counts = dict(manifest['categoryRows'])
    update_manifest(root, manifest, reviewed, rows, selected)
    summary = dict(before=before, after=len(rows), reviewedPairs=len(entries),
                   categoryChanges={c: manifest['categoryRows'].get(c, 0) - old_counts.get(c, 0)
                                    for c in manifest['categoryRows']
                                    if manifest['categoryRows'].get(c, 0) != old_counts.get(c, 0)})
    if not commit:
        print(json.dumps(summary, ensure_ascii=False))
        return summary
    work = root / 'build/classification-audit'; work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='classification-review-', dir=work) as temporary:
        staging = Path(temporary)
        staged = staging / DIRECTORY; staged.mkdir(parents=True)
        staged_paths = list(dict.fromkeys([
            *manifest['inputs'], 'src/main/resources/id.def',
            str(DIRECTORY / 'categories.json')]))
        taxonomy_path = str(DIRECTORY / 'person-taxonomy.json')
        if taxonomy_path not in staged_paths and (root / taxonomy_path).is_file():
            staged_paths.append(taxonomy_path)
        person_dictionary_path = str(DIRECTORY / 'person-dictionary-candidates.tsv.gz')
        if person_dictionary_path not in staged_paths and (root / person_dictionary_path).is_file():
            staged_paths.append(person_dictionary_path)
        for relative in staged_paths:
            target = staging / relative; target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(root / relative)
        # The original snapshot and result ledger are also required by offline verification.
        if 'lunaReclassification' in manifest['provenance']:
            (staged / 'luna-reclassification').symlink_to(directory / 'luna-reclassification', target_is_directory=True)
        d.write_gzip(staged / 'distribution-decisions.tsv.gz', (reviewed[p] for p in sorted(reviewed)))
        d.write_gzip(staged / 'distribution-candidates.tsv.gz', sorted(rows))
        for name in manifest['files']:
            manifest['files'][name] = d.sha(staged / name)
        d.write_json(staged / 'distribution-manifest.json', manifest)
        d.verify(staging)
        changed = ['distribution-decisions.tsv.gz', 'distribution-candidates.tsv.gz', 'distribution-manifest.json']
        if all((directory / name).read_bytes() == (staged / name).read_bytes() for name in changed):
            print(json.dumps(summary, ensure_ascii=False)); return summary
        snapshot = d.sha(directory / 'distribution-manifest.json')
        backup = work / ('backup-' + snapshot); backup.mkdir(exist_ok=True)
        for name in changed:
            target = backup / name
            if not target.exists(): shutil.copyfile(directory / name, target)
        d.write_json(journal, dict(backup=str(backup), files=changed))
        for name in changed:
            pending = directory / (name + '.tmp')
            shutil.copyfile(staged / name, pending); pending.replace(directory / name)
        journal.unlink()
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def recover(root):
    with locked(root.resolve()):
        return _recover(root)


def _recover(root):
    """Restore the previous validated snapshot after an interrupted multi-file commit."""
    import classified_distribution as d
    import shutil
    root = root.resolve()
    work = root / 'build/classification-audit'
    journal = work / 'apply-journal.json'
    if not journal.exists():
        raise ValueError('No interrupted review apply to recover')
    record = json.loads(journal.read_text())
    backup = Path(record['backup']).resolve()
    files = ['distribution-decisions.tsv.gz', 'distribution-candidates.tsv.gz', 'distribution-manifest.json']
    if backup.parent != work.resolve() or not backup.name.startswith('backup-') or record['files'] != files:
        raise ValueError('Invalid recovery journal')
    manifest = json.loads((backup / 'distribution-manifest.json').read_text())
    for filename in files[:-1]:
        if d.sha(backup / filename) != manifest['files'][filename]:
            raise ValueError('Recovery backup hash mismatch')
    for filename in files:
        target = root / DIRECTORY / filename
        pending = target.with_name(target.name + '.tmp')
        shutil.copyfile(backup / filename, pending); pending.replace(target)
    d.verify(root, allow_pending_reviews=True)
    journal.unlink()
    print('Recovered previous review snapshot; pending review files remain available')
