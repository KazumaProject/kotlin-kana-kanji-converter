#!/usr/bin/env python3
"""Build/replay the supervised person distribution from frozen source evidence.

The original 28-category snapshot remains an audit input. Only independently
approved person records enter the active 51-category distribution. Neither held
people nor an optional adult category enter the standard dictionary package.
"""
import argparse
import collections
import contextlib
import gzip
import io
import json
from pathlib import Path
import shutil
import tempfile

import person_subclassification as p
import review_person_names as independent

DIRECTORY = 'src/main/classification/person-subclassification/distribution'


def compressed_copy(source, target):
    with Path(source).open('rb') as stream, Path(target).open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as output:
            shutil.copyfileobj(stream, output)


def gzip_rows(path, rows):
    with Path(path).open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as output:
            with io.TextIOWrapper(output, encoding='utf-8', newline='\n') as stream:
                for row in rows:
                    stream.write('\t'.join(row) + '\n')


@contextlib.contextmanager
def unpack_evidence(directory):
    with tempfile.TemporaryDirectory(prefix='person-evidence-replay-') as tmp:
        work = Path(tmp)
        for name in ('proposals.jsonl', 'reviews.jsonl', 'metadata.sqlite3'):
            with gzip.open(directory / 'evidence' / (name + '.gz'), 'rb') as source:
                with (work / name).open('wb') as dest:
                    shutil.copyfileobj(source, dest)
        yield work


def assert_name_evidence(root, directory, result, work):
    """Independent XML parsing, not merely the classifier's own cached labels."""
    proposals = {v['item_id']: v for v in p.read_jsonl(work / 'proposals.jsonl')}
    p.require(all(v['adult_appearance_status'] in ('not_applicable', 'not_checked') for v in proposals.values()),
              'generic-name recipe cannot assert individual appearance assessment')
    p.require(not result['counts'].get('adult_separate', 0), 'generic-name recipe cannot admit performers')
    p.require(all(proposals[d['item_id']]['adult_appearance_status'] == 'not_applicable'
                  for d in result['decisions'] if d['distribution_status'] == 'general'),
              'general name recipe requires independently typed name components')
    source = directory / 'evidence/JMnedict.xml.gz'
    audit = json.loads((directory / 'evidence/source-audit.json').read_text())
    classifier = json.loads((directory / 'evidence/classifier-manifest.json').read_text())
    p.require(audit['source_sha256'] == classifier['source']['sha256'] == p.sha(source), 'name source changed')
    p.require(audit['proposal_file_sha256'] == p.sha(work / 'proposals.jsonl') == classifier['files']['proposals.jsonl'], 'classifier proposals changed')
    p.require(audit['reviews_sha256'] == p.sha(work / 'reviews.jsonl'), 'independent reviews changed')
    p.require(audit['classifier_sidecar_sha256'] == classifier['files']['source-matches.jsonl.gz']
              == p.sha(directory / 'evidence/source-matches.jsonl.gz'), 'classifier source entries changed')
    p.require(audit['reviewer_code_sha256'] == p.sha(Path(independent.__file__)), 'reviewer implementation changed')
    p.require(classifier['implementation_sha256'] == p.sha(Path(__file__).with_name('classify_person_names.py')), 'classifier implementation changed')
    p.require(audit['snapshot_id'] == classifier['snapshot_id'] == result['snapshot_id'], 'evidence snapshot mismatch')
    p.require(classifier['unbound_draft'] is False, 'draft classifier evidence')
    matches = independent.parse_source(source, {(i['reading'], i['surface']) for i in result['items']})
    blockers, blocker_digest = independent.metadata_blockers(work / 'metadata.sqlite3')
    p.require(audit['metadata_positive_blocker_digest'] == blocker_digest, 'metadata blocker source changed')
    by_id = {i['item_id']: i for i in result['items']}
    for d in result['decisions']:
        if d['distribution_status'] != 'general':
            continue
        item = by_id[d['item_id']]
        assessment = independent.assess_match(matches.get((item['reading'], item['surface']), []))
        p.require(assessment['eligible'] and assessment['categories'] == d['categories']
                  and assessment['primary_category'] == d['primary_category'], 'unsupported name classification')
        p.require(item['surface'] not in blockers, 'known positive indicator entered general names')


def categories(root):
    old = json.loads((root / p.BASE / 'categories.json').read_text())['categories']
    names = json.loads((root / p.BASE / 'person-taxonomy.json').read_text())['categories']
    person_categories = [dict(id='person_' + c['id'], name=c['label'], definition=c['definition'],
                              standard_enabled=c['standard_enabled']) for c in names]
    standard = [c for c in old if c['id'] != 'person'] + [c for c in person_categories if c['standard_enabled']]
    p.require(len(standard) == 51 and len(person_categories) == 25, 'unexpected taxonomy topology')
    return standard, person_categories


def standard_rows(root, result):
    decisions = {d['item_id']: d for d in result['decisions']}
    for row in p.output_rows(root, result, 'general-candidates.tsv'):
        if row[0] == 'person':
            decision = decisions[p.item_id(row[1], row[5])]
            yield ['person_' + decision['primary_category'], *row[1:]]
        else:
            yield row


def admitted_person_rows(result):
    decisions = {d['item_id']: d for d in result['decisions']}
    for item in result['items']:
        d = decisions[item['item_id']]
        if d['distribution_status'] == 'general':
            for row in item['records']:
                yield ['person_' + d['primary_category'], *row[1:]]


def emit(root, directory, result):
    standard, names = categories(root)
    p.write_json(directory / 'categories.json', {'version': 1, 'categories': standard})
    p.write_json(directory / 'person-categories.json', {'version': 1, 'categories': names})
    gzip_rows(directory / 'distribution-candidates.tsv.gz', standard_rows(root, result))
    gzip_rows(directory / 'person-records.tsv.gz', admitted_person_rows(result))
    gzip_rows(directory / 'held-records.tsv.gz', p.output_rows(root, result, 'hold.tsv'))
    gzip_rows(directory / 'adult-records.tsv.gz', p.output_rows(root, result, 'adult_separate.tsv'))
    person_dir = directory / 'person-dictionaries'
    person_dir.mkdir()
    p.write_json(person_dir / 'categories.json', {'version': 1, 'categories': names})
    person_rows = list(admitted_person_rows(result))
    gzip_rows(person_dir / 'distribution-candidates.tsv.gz', person_rows)
    for category in names:
        gzip_rows(person_dir / (category['id'] + '.tsv.gz'), (r for r in person_rows if r[0] == category['id']))
    records = collections.Counter(r[0] for r in standard_rows(root, result))
    pairs = collections.defaultdict(set)
    for row in person_rows:
        pairs[row[0]].add((row[1], row[5]))
    files = {str(path.relative_to(directory)): p.sha(path) for path in sorted(directory.rglob('*'))
             if path.is_file() and path != directory / 'distribution-manifest.json'}
    manifest = {'schema_version': 1, 'snapshot_id': result['snapshot_id'],
                'sources': p.source_hashes(root), 'implementation_sha256': p.sha(Path(__file__)),
                'categoryRows': {c['id']: records[c['id']] for c in standard},
                'personCategoryPairs': {c['id']: len(pairs[c['id']]) for c in names},
                'dictionaryRows': sum(records.values()), 'personCounts': result['counts'],
                'personItems': result['item_count'], 'proposalCount': result['proposal_count'],
                'reviewCount': result['review_count'], 'files': files,
                'standard_excludes': ['adult_performer', 'held'],
                'source_inventory_policy': 'Original frozen inventory remains a conservative superset for specialist duplicate exclusions.',
                'appearance_scope': 'Only independently sourced generic name components admitted; individual appearance histories not asserted.'}
    p.write_json(directory / 'distribution-manifest.json', manifest)
    return manifest


def replay(root, directory):
    manifest = json.loads((directory / 'distribution-manifest.json').read_text())
    p.require(manifest['implementation_sha256'] == p.sha(Path(__file__)), 'distribution verifier changed')
    p.require(manifest['sources'] == p.source_hashes(root), 'baseline sources changed')
    actual_files = {str(path.relative_to(directory)) for path in directory.rglob('*')
                    if path.is_file() and path != directory / 'distribution-manifest.json'}
    p.require(set(manifest['files']) == actual_files, 'missing/extra distribution files')
    for name, expected in manifest['files'].items():
        relative = Path(name)
        p.require(not relative.is_absolute() and '..' not in relative.parts, 'invalid distribution path')
        p.require(p.sha(directory / relative) == expected, 'distribution file changed: ' + name)
    with unpack_evidence(directory) as work:
        workspace = work / 'workspace'
        p.prepare(root, workspace, batch_size=100)
        result = p.evaluate(root, workspace, [work / 'proposals.jsonl'], [work / 'reviews.jsonl'])
        p.require(result['proposal_count'] == result['review_count'] == result['item_count'], 'full-corpus proposals/reviews missing')
        assert_name_evidence(root, directory, result, work)
        for name, rows in [('distribution-candidates.tsv.gz', standard_rows(root, result)),
                           ('person-records.tsv.gz', admitted_person_rows(result)),
                           ('held-records.tsv.gz', p.output_rows(root, result, 'hold.tsv')),
                           ('adult-records.tsv.gz', p.output_rows(root, result, 'adult_separate.tsv'))]:
            expected = iter('\t'.join(row) + '\n' for row in rows)
            with gzip.open(directory / name, 'rt', encoding='utf-8') as stream:
                for line in stream:
                    p.require(line == next(expected, None), 'record partition/filter differs: ' + name)
            p.require(next(expected, None) is None, 'records missing: ' + name)
        standard, names = categories(root)
        p.require(json.loads((directory / 'categories.json').read_text()) == {'version': 1, 'categories': standard}, 'standard categories changed')
        p.require(json.loads((directory / 'person-categories.json').read_text()) == {'version': 1, 'categories': names}, 'person categories changed')
        counts = collections.Counter(r[0] for r in standard_rows(root, result))
        p.require(manifest['categoryRows'] == {c['id']: counts[c['id']] for c in standard}
                  and manifest['dictionaryRows'] == sum(counts.values()), 'manifest record counts differ')
        p.require(manifest['personCounts'] == result['counts'] and manifest['personItems'] == result['item_count']
                  and manifest['proposalCount'] == result['proposal_count'] and manifest['reviewCount'] == result['review_count'], 'manifest audit counts differ')
        # The active pair set is a subset of the original exclusion inventory.
        original = {(r[1], r[5]) for r in p.candidates(root)}
        p.require(all((r[1], r[5]) in original for r in standard_rows(root, result)), 'new pair outside frozen source inventory')
        person_rows = list(admitted_person_rows(result))
        pairs = collections.defaultdict(set)
        for row in person_rows:
            pairs[row[0]].add((row[1], row[5]))
        p.require(manifest['personCategoryPairs'] == {c['id']: len(pairs[c['id']]) for c in names}, 'person pair counts differ')
        # Independently check the downloadable per-category text dictionaries too.
        expected_person_files = {'categories.json', 'distribution-candidates.tsv.gz'} | {c['id'] + '.tsv.gz' for c in names}
        p.require({f.name for f in (directory / 'person-dictionaries').iterdir()} == expected_person_files, 'person dictionary files differ')
        p.require(json.loads((directory / 'person-dictionaries/categories.json').read_text()) == {'version': 1, 'categories': names}, 'person-only category definitions differ')
        for category in [None, *names]:
            name = 'distribution-candidates.tsv.gz' if category is None else category['id'] + '.tsv.gz'
            expected_rows = person_rows if category is None else [r for r in person_rows if r[0] == category['id']]
            with gzip.open(directory / 'person-dictionaries' / name, 'rt', encoding='utf-8') as stream:
                p.require(stream.read() == ''.join('\t'.join(r) + '\n' for r in expected_rows), 'person dictionary rows differ')
    return manifest


def build(root, workspace, source, proposals, reviews, classifier_manifest, source_audit, metadata, notices):
    root, workspace = Path(root).resolve(), Path(workspace).resolve()
    target = root / DIRECTORY
    p.require(not target.exists(), 'distribution already exists; refusing overwrite')
    result = p.evaluate(root, workspace, [proposals], [reviews])
    p.require(result['proposal_count'] == result['review_count'] == result['item_count'], 'full-corpus proposals/reviews required')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.person-distribution-', dir=target.parent) as temp:
        stage = Path(temp) / 'distribution'
        (stage / 'evidence').mkdir(parents=True)
        (stage / 'notices').mkdir()
        shutil.copyfile(source, stage / 'evidence/JMnedict.xml.gz')
        compressed_copy(proposals, stage / 'evidence/proposals.jsonl.gz')
        compressed_copy(reviews, stage / 'evidence/reviews.jsonl.gz')
        compressed_copy(metadata, stage / 'evidence/metadata.sqlite3.gz')
        shutil.copyfile(classifier_manifest, stage / 'evidence/classifier-manifest.json')
        shutil.copyfile(Path(classifier_manifest).parent / 'source-matches.jsonl.gz', stage / 'evidence/source-matches.jsonl.gz')
        shutil.copyfile(source_audit, stage / 'evidence/source-audit.json')
        for path in notices:
            shutil.copyfile(path, stage / 'notices' / Path(path).name)
        p.require(any((stage / 'notices').iterdir()), 'source notices required')
        emit(root, stage, result)
        replay(root, stage)
        stage.rename(target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'verify'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    for name in ('workspace', 'source', 'proposals', 'reviews', 'classifier-manifest', 'source-audit', 'metadata'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--notices', type=Path, nargs='+', default=[])
    args = parser.parse_args()
    try:
        if args.command == 'build':
            for name in ('workspace', 'source', 'proposals', 'reviews', 'classifier_manifest', 'source_audit', 'metadata'):
                if getattr(args, name) is None:
                    parser.error('--' + name.replace('_', '-') + ' required')
            build(args.root, args.workspace, args.source, args.proposals, args.reviews,
                  args.classifier_manifest, args.source_audit, args.metadata, args.notices)
        else:
            replay(args.root.resolve(), args.root.resolve() / DIRECTORY)
        print('Full-corpus person distribution verified against independent source evidence.')
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f'error: {error}\n')


if __name__ == '__main__':
    main()
