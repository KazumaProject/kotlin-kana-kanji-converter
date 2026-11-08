"""Pack and replay the reviewed dictionary inputs without research corpora.

The public replay contract is intentionally distinct from a research
materialization. It consumes a completed ledger; it does not classify or approve
new words, and never relaxes lexicon_pipeline.verify or extend_lexicon.load_base.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gc
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from zipfile import ZipFile

import lexicon_pipeline as pipeline

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO / 'english-ime/data/1-grams_score_cost_pos_combined_with_ner.zip'
DEFAULT_MANIFEST = REPO / 'english-ime/data/reviewed/manifest.json'
KIND = 'reviewed-replay-v1'
ARCHIVE = 'reviewed-source.tar.gz'
CORE = {'inventory.jsonl', 'decisions.tsv', 'surface-corrections.tsv',
        'grammar/categories.tsv', 'grammar/forms.tsv', 'grammar/memberships.tsv',
        'grammar/relations.tsv'}
EXTRAS = {'review-provenance.jsonl', 'category-counts.tsv'}
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_PAYLOAD = 512 * 1024 * 1024
SUPPLEMENT_OUTPUTS = {
    'reading.dat', 'word.dat', 'token.dat', 'qwerty_glide_index.dat',
    'grammar/forms.tsv', 'grammar/memberships.tsv', 'grammar/categories.ecat', 'grammar/bundle.properties',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def tuples_digest(rows):
    digest = hashlib.sha256()
    for row in rows:
        digest.update((json.dumps([row[k] for k in ('id', 'reading', 'surface', 'cost')],
                                  ensure_ascii=False, separators=(',', ':')) + '\n').encode())
    return digest.hexdigest()


def valid_member(name):
    path = PurePosixPath(name)
    return (not path.is_absolute() and '..' not in path.parts and str(path) == name and
            (name in CORE | EXTRAS or bool(re.fullmatch(r'notices/[A-Za-z0-9_.-]+', name))))


class BoundedReader:
    """Count decompressed tar bytes, including metadata and trailing padding."""
    def __init__(self, source, limit):
        self.source, self.remaining = source, limit

    def read(self, size=-1):
        # Bound each underlying read before tarfile can allocate for PAX metadata.
        wanted = self.remaining + 1 if size < 0 else min(size, self.remaining + 1)
        data = self.source.read(min(wanted, 1024 * 1024))
        self.remaining -= len(data)
        require(self.remaining >= 0, 'Decompressed archive exceeds replay size limit')
        return data


def validate_manifest(manifest):
    require(manifest.get('kind') == KIND and manifest.get('schemaVersion') == 1,
            'Unsupported replay manifest')
    review = manifest['review']
    require(all(type(review[k]) is int and review[k] >= 0 for k in
                ('inputRows', 'includedRows', 'excludedRows', 'pendingRows')), 'Invalid review counts')
    require(review['complete'] is True and review['pendingRows'] == 0,
            'Replay requires completed classification with zero pending rows')
    require(review['includedRows'] + review['excludedRows'] == review['inputRows'],
            'Incorrect review totals')
    files = manifest['files']
    require(CORE <= files.keys() and all(valid_member(n) for n in files),
            'Unexpected or missing replay files')
    require(any(n.startswith('notices/') for n in files), 'Source notices are required')
    require(set(files) == set(manifest['fileBytes']) and
            all(type(n) is int and n >= 0 for n in manifest['fileBytes'].values()) and
            sum(manifest['fileBytes'].values()) <= MAX_PAYLOAD, 'Invalid payload sizes')
    require(all(re.fullmatch('[0-9a-f]{64}', h) for h in files.values()), 'Invalid file checksum')
    archive = manifest['archive']
    require(archive['file'] == ARCHIVE and 0 < archive['bytes'] <= MAX_ARCHIVE and
            re.fullmatch('[0-9a-f]{64}', archive['sha256']), 'Invalid archive contract')
    require(manifest.get('expectedOutputs') and all(
        not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts and
        re.fullmatch('[0-9a-f]{64}', h) for n, h in manifest['expectedOutputs'].items()),
        'Missing or invalid verified output hashes')


def category_counts(model, decisions, targets):
    surfaces = defaultdict(set)
    input_rows = Counter()
    selected = set()
    for row in decisions:
        if row['decision'] != 'include':
            continue
        categories = set()
        for surface in targets.get(row['id'], (row['surface'],)):
            for key in row['lexeme_ids'].split(','):
                pair = key, surface
                if pair not in model.forms:
                    continue
                selected.add(pair)
                for category in model.members[pair]:
                    categories.add(category)
                    surfaces[category].add(surface)
        input_rows.update(categories)
    references = pipeline.category_surface_counts(model)
    counts = [dict(category=category, admitted_distinct_surfaces=len(surfaces[category]),
                   admitted_input_rows=input_rows[category],
                   model_reference_surfaces=references[category]) for category in sorted(model.names)]
    return counts, selected


def validate_data(directory, manifest, source):
    """Check exact input tuples and existing grammar/mapping rules, not research approval."""
    directory, source = Path(directory), Path(source)
    inputs = manifest['sourceInputs']
    require(sha(source) == inputs['sourceZipSha256'], 'Original source ZIP changed')
    with ZipFile(source) as archive:
        payload = archive.read(pipeline.SOURCE_TSV)
    require(hashlib.sha256(payload).hexdigest() == inputs['sourcePayloadSha256'],
            'Original source payload changed')
    source_table = csv.DictReader(io.StringIO(payload.decode('utf-8')), delimiter='\t')
    require(source_table.fieldnames == ['input_word', 'output_word', 'pos_tag', 'score'],
            'Invalid source TSV header')
    expected = [dict(id=f'tsv:{i + 2}', reading=r['input_word'], surface=r['output_word'],
                     cost=int(r['score'])) for i, r in enumerate(source_table)]
    rows = pipeline.inventory(directory / 'inventory.jsonl')
    require(len(rows) == inputs['inputRows'] == manifest['review']['inputRows'] and
            tuples_digest(rows) == inputs['orderedTuplesSha256'], 'Original ordered tuples changed')
    require(rows[:len(expected)] == expected and len(expected) == inputs['tsvRows'] and
            len(rows) - len(expected) == inputs['manualRows'] and
            [r['id'] for r in rows[len(expected):]] ==
            [f'manual:{i + 1}' for i in range(inputs['manualRows'])], 'Incomplete or reordered source inventory')
    decisions = pipeline.read_table(directory / 'decisions.tsv', 'decisions')
    require(len(decisions) == len(rows), 'Every original row needs one decision')
    model = pipeline.Lexicon(directory / 'grammar')
    corrections = pipeline.read_table(directory / 'surface-corrections.tsv', 'corrections')
    targets = pipeline.correction_targets(corrections, rows, model)
    for original, decision in zip(rows, decisions):
        require(all(original[k] == decision[k] for k in ('id', 'reading', 'surface')) and
                original['cost'] == int(decision['cost']), 'A decision changed or reordered an original row')
        require(decision['decision'] in {'include', 'exclude'}, 'Incomplete review decision')
        pipeline.validate_decision(decision, model, targets.get(original['id']))
    counts = Counter(r['decision'] for r in decisions)
    require(counts['include'] == manifest['review']['includedRows'] and
            counts['exclude'] == manifest['review']['excludedRows'], 'Incorrect decision totals')
    actual = dict(forms=len(model.forms), categories=len(model.names),
                  memberships=sum(map(len, model.members.values())), relations=len(model.relations),
                  corrections=len(corrections), caseCandidateRows=sum(len(v) > 1 for v in targets.values()))
    require(actual == manifest['model'], 'Incorrect grammar or mapping totals')
    table, selected = category_counts(model, decisions, targets)
    if (directory / 'category-counts.tsv').exists():
        with (directory / 'category-counts.tsv').open(encoding='utf-8', newline='') as stream:
            recorded = list(csv.DictReader(stream, delimiter='\t'))
        require(recorded == [{k: str(v) for k, v in r.items()} for r in table], 'Incorrect admitted category counts')
    if (directory / 'review-provenance.jsonl').exists():
        seen = set()
        with (directory / 'review-provenance.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                record = json.loads(line)
                pair = record['lexeme_id'], record['surface']
                require(pair in selected and pair not in seen and record['sources'], 'Invalid provenance key')
                seen.add(pair)
        require(seen == selected, 'Missing admitted form provenance')
    return dict(inputRows=len(rows), includedRows=counts['include'], excludedRows=counts['exclude'],
                pendingRows=0, admittedFormKeys=len(selected), **actual)


def unpack(manifest_path, destination, source):
    manifest_path, destination = Path(manifest_path), Path(destination)
    manifest = read_json(manifest_path)
    validate_manifest(manifest)
    archive = manifest_path.parent / ARCHIVE
    require(archive.is_file() and not archive.is_symlink() and
            archive.stat().st_size == manifest['archive']['bytes'] and
            sha(archive) == manifest['archive']['sha256'], 'Replay archive checksum changed')
    sidecar = manifest_path.parent / 'category-counts.tsv'
    if sidecar.exists():
        require(sha(sidecar) == manifest['files'].get('category-counts.tsv'), 'Category count sidecar changed')
    require(not destination.exists(), 'Unpack destination already exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.reviewed-replay-', dir=destination.parent) as tmp:
        staging = Path(tmp) / 'sources'
        staging.mkdir()
        seen = set()
        with gzip.open(archive, 'rb') as expanded:
            # Allow bounded headers/padding in addition to payload, but count all
            # bytes before tarfile interprets or allocates for extended headers.
            bounded = BoundedReader(expanded, MAX_PAYLOAD + len(manifest['files']) * 2048 + 10240)
            with tarfile.open(fileobj=bounded, mode='r|') as stream:
                for member in stream:
                    require(member.isfile() and valid_member(member.name) and
                            member.name in manifest['files'] and member.name not in seen,
                            'Unexpected, duplicate or unsafe archive member')
                    require(member.size == manifest['fileBytes'][member.name], 'Archive member size changed')
                    seen.add(member.name)
                    target = staging / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with stream.extractfile(member) as src, target.open('xb') as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
                    require(target.stat().st_size == member.size and sha(target) == manifest['files'][member.name],
                            'Archive member checksum changed')
            # Tar ends at its terminator. Also bound trailing data/concatenated
            # gzip members and force gzip's integrity checks before publication.
            while bounded.read(1024 * 1024):
                pass
        require(seen == set(manifest['files']), 'Missing replay file or source notice')
        result = validate_data(staging, manifest, source)
        # The consumer reads this honestly typed provenance to check notice hashes.
        (staging / 'manifest.json').write_bytes(manifest_path.read_bytes())
        staging.rename(destination)
    return manifest, result


def run_cli(args):
    subprocess.run(['bash', str(REPO / 'gradlew'), ':english-ime:run', '--no-daemon',
                    '--console=plain', '--args=' + shlex.join([str(x) for x in args])],
                   cwd=REPO, check=True)


def supplement_output_names(manifest):
    return SUPPLEMENT_OUTPUTS | ({'grammar/categories.tsv'} if 'categories.tsv' in manifest['files'] else set()) | {
        'grammar/' + name for name in manifest['files'] if name.startswith('notices/')}


def supplement_outputs(directory, base_manifest):
    manifest = read_json(directory / 'manifest.json')
    version = manifest.get('schemaVersion')
    require(version in {1, 2} and manifest.get('kind') == f'reviewed-english-supplement-v{version}' and
            manifest.get('baseManifestSha256') == sha(base_manifest), 'Invalid supplement or base manifest')
    files = manifest['files']
    require('entries.tsv' in files and all(name == 'entries.tsv' or version == 2 and name in {'categories.tsv', 'metadata.tsv'} or
            re.fullmatch(r'notices/[A-Za-z0-9_.-]+', name) for name in files), 'Invalid supplement input paths')
    expected = manifest['expectedOutputs']
    require(set(expected) == supplement_output_names(manifest) and
            all(re.fullmatch('[0-9a-f]{64}', value) for value in expected.values()),
            'Invalid supplement output hashes')
    return expected


def build(manifest_path, source, output, supplement=None):
    output = Path(output).resolve()
    require(not output.exists(), 'Build output already exists')
    extension = supplement_outputs(supplement, manifest_path) if supplement is not None else {}
    with tempfile.TemporaryDirectory(prefix='english-replay-') as tmp:
        directory = Path(tmp) / 'sources'
        manifest, result = unpack(manifest_path, directory, source)
        gc.collect()
        exported = Path(tmp) / 'inventory.jsonl'
        run_cli(['export-inventory', '--source', Path(source).resolve(), '--out', exported])
        require(tuples_digest(pipeline.inventory(exported)) == manifest['sourceInputs']['orderedTuplesSha256'],
                'Current JVM source/manual inventory differs from reviewed original tuples')
        generated = Path(tmp) / 'dictionary'
        run_cli(['build-reviewed', '--source', Path(source).resolve(), '--decisions', directory / 'decisions.tsv',
                 '--lexicon', directory / 'grammar', '--relations', directory / 'grammar/relations.tsv',
                 '--corrections', directory / 'surface-corrections.tsv', '--notices', directory / 'notices',
                 '--out', generated] + (['--supplement', supplement.resolve()] if extension else []))
        expected = manifest['expectedOutputs'] | extension
        actual = {str(p.relative_to(generated)): sha(p) for p in generated.rglob('*') if p.is_file()}
        provenance = actual.pop('source-evidence-manifest.json', None)
        require(provenance == sha(manifest_path), 'Output lost its replay provenance')
        if extension:
            require(actual.pop('supplement-manifest.json', None) == sha(supplement / 'manifest.json'),
                    'Output lost its supplement provenance')
        if actual != expected:
            differences = sorted(name for name in actual.keys() | expected.keys()
                                 if actual.get(name) != expected.get(name))
            raise ValueError('Fresh JVM output differs from verified final dictionary: ' + ', '.join(differences))
        output.parent.mkdir(parents=True, exist_ok=True)
        # Copy into a sibling then rename, even when system temp is on another volume.
        with tempfile.TemporaryDirectory(prefix='.english-replay-', dir=output.parent) as sibling:
            staged = Path(sibling) / 'dictionary'
            shutil.copytree(generated, staged)
            staged.rename(output)
    if extension:
        properties = dict(line.split('=', 1) for line in
                          (output / 'grammar/bundle.properties').read_text(encoding='utf-8').splitlines())
        result['supplement'] = {name: int(properties['supplement.' + name]) for name in
                                ('formRows', 'surfaces', 'candidatePairs')}
    return dict(result, output=str(output), outputFilesVerified=len(expected), replayProvenanceVerified=True)


def thin_proof(proof):
    keys = {'source', 'url', 'member', 'line', 'relation', 'entry_id', 'sense_id', 'entryId', 'senseId',
            'sourceSha256', 'approved', 'reviewer', 'humanReviewClaimed', 'qualifiedName', 'qualifiedModule',
            'owner', 'sourceKind', 'canonicalSurface', 'sourceId'}
    result = {k: v for k, v in proof.items() if k in keys and isinstance(v, (str, int, bool))}
    fact = proof.get('sourceFact', {})
    keys = {'label', 'originalIds', 'categories', 'lemma', 'baseCategories', 'entityQualifier', 'qualifiedModule',
            'qualifiedNamedContext', 'qualifiedApiContext', 'usageLabels', 'evidenceSource', 'sourceKind',
            'inputSpellingCorrection', 'sourceProseExported', 'humanReviewClaimed', 'sourceAcquisition'}
    if fact:
        result['reviewedFact'] = {k: v for k, v in fact.items() if k in keys}
        result['reviewedFact']['witnesses'] = [{k: w[k] for k in
            ('url', 'sourceSha256', 'start', 'end', 'sha256') if k in w} for w in fact.get('contextWitnesses', [])]
    return result


def write_archive(root, paths, output):
    with Path(output).open('xb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as archive:
            for name in sorted(paths):
                path = Path(root) / name
                require(path.is_file() and not path.is_symlink() and valid_member(name), 'Invalid replay input')
                header = tarfile.TarInfo(name)
                header.size, header.mode, header.mtime = path.stat().st_size, 0o644, 0
                with path.open('rb') as stream:
                    archive.addfile(header, stream)


def pack(directory, audit_path, gold, output, source):
    directory, gold, output = Path(directory), Path(gold), Path(output)
    original = read_json(directory / 'manifest.json')
    require(original['summary']['pendingRows'] == 0 and original['summary']['complete'],
            'Cannot pack an unfinished research materialization')
    require(sha(source) == pipeline.SOURCE_SHA256, 'Pack requires the pinned original source ZIP')
    audit = read_json(audit_path)
    require(audit['roundVerificationComplete'] and audit['manifestSha256'] == sha(directory / 'manifest.json'),
            'Final all-input/grammar/actual-reader verification is required')
    for name, checksum in audit['validationProofs'].items():
        require('..' not in PurePosixPath(name).parts and not PurePosixPath(name).is_absolute() and
                sha(Path(audit_path).parent / name) == checksum, 'Changed final validation proof')
    pipeline.verify(directory)
    require(sha(gold / 'source-evidence-manifest.json') == sha(directory / 'manifest.json'),
            'Gold build does not come from this exact final materialization')
    require(not output.exists(), 'Pack output already exists')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.pack-replay-', dir=output.parent) as tmp:
        staging = Path(tmp)
        payload = staging / 'payload'
        paths = CORE | {str(p.relative_to(directory)) for p in (directory / 'notices').iterdir()}
        for name in sorted(paths):
            source_path = directory / name
            require(source_path.is_file() and not source_path.is_symlink() and valid_member(name),
                    'Invalid source table or notice')
            target = payload / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target)
        rows = pipeline.inventory(directory / 'inventory.jsonl')
        decisions = pipeline.read_table(directory / 'decisions.tsv', 'decisions')
        model = pipeline.Lexicon(directory / 'grammar')
        targets = pipeline.correction_targets(pipeline.read_table(directory / 'surface-corrections.tsv', 'corrections'), rows, model)
        counts, selected = category_counts(model, decisions, targets)
        with (payload / 'category-counts.tsv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(counts[0]), delimiter='\t', lineterminator='\n')
            writer.writeheader()
            writer.writerows(counts)
        provenance_keys = set()
        with (directory / 'evidence.jsonl').open(encoding='utf-8') as src, (payload / 'review-provenance.jsonl').open('w', encoding='utf-8') as dst:
            for line in src:
                record = json.loads(line)
                pair = record['lexeme_id'], record['surface']
                if pair in selected:
                    require(pair not in provenance_keys, 'Duplicate research evidence key')
                    provenance_keys.add(pair)
                    record['sources'] = [thin_proof(p) for p in record.pop('evidence')]
                    dst.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
        require(provenance_keys == selected, 'Missing admitted research provenance')
        paths |= EXTRAS
        summary = original['summary']
        corrections = pipeline.read_table(directory / 'surface-corrections.tsv', 'corrections')
        del model, selected
        gc.collect()
        manifest = dict(kind=KIND, schemaVersion=1,
            archive=dict(file=ARCHIVE), files={n: sha(payload / n) for n in sorted(paths)},
            fileBytes={n: (payload / n).stat().st_size for n in sorted(paths)},
            sourceInputs=dict(sourceZipSha256=sha(source), sourcePayloadSha256=original['sources'].get('sourceTsvSha256', ''),
                inventorySha256=sha(payload / 'inventory.jsonl'), orderedTuplesSha256=tuples_digest(rows),
                inputRows=len(rows), tsvRows=sum(r['id'].startswith('tsv:') for r in rows),
                manualRows=sum(r['id'].startswith('manual:') for r in rows)),
            review=dict(complete=True, inputRows=len(rows), includedRows=summary['includedRows'],
                        excludedRows=summary['excludedRows'], pendingRows=0,
                        method='Source-backed deterministic analysis and implementation-agent curation; no new human-review certification'),
            model=dict(forms=summary['forms'], categories=len(summary['categorySurfaces']),
                memberships=summary['memberships'], relations=len(pipeline.read_table(payload / 'grammar/relations.tsv', 'relations')),
                corrections=len(corrections), caseCandidateRows=summary['caseCandidateRows']),
            lineage=dict(researchManifestSha256=sha(directory / 'manifest.json'),
                researchEvidenceRedistributed=False, provenanceScope='Admitted lexical identities and source pointers only; no source prose, definitions or code',
                replayIsSemanticResearch=False),
            expectedOutputs={str(p.relative_to(gold)): sha(p) for p in sorted(gold.rglob('*'))
                             if p.is_file() and p.name != 'source-evidence-manifest.json'})
        with ZipFile(source) as archive:
            manifest['sourceInputs']['sourcePayloadSha256'] = hashlib.sha256(archive.read(pipeline.SOURCE_TSV)).hexdigest()
        validate_data(payload, manifest, source)
        write_archive(payload, paths, staging / ARCHIVE)
        manifest['archive'].update(bytes=(staging / ARCHIVE).stat().st_size, sha256=sha(staging / ARCHIVE))
        validate_manifest(manifest)
        (staging / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
        with tempfile.TemporaryDirectory(prefix='pack-replay-check-') as check:
            unpack(staging / 'manifest.json', Path(check) / 'sources', source)
        shutil.copyfile(payload / 'category-counts.tsv', staging / 'category-counts.tsv')
        payload.rename(staging / 'inputs-to-remove')
        # Own temporary inputs are not part of the public artifact.
        shutil.rmtree(staging / 'inputs-to-remove')
        staging.rename(output)
    return dict(output=str(output), archiveBytes=manifest['archive']['bytes'], review=manifest['review'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('verify', 'build'):
        command = commands.add_parser(name)
        command.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
        command.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
        command.add_argument('--out', type=Path, required=name == 'build')
        if name == 'build':
            command.add_argument('--supplement', type=Path)
    command = commands.add_parser('pack')
    for name in ('directory', 'audit', 'gold', 'out'):
        command.add_argument('--' + name, type=Path, required=True)
    command.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    try:
        if args.command == 'pack':
            result = pack(args.directory, args.audit, args.gold, args.out, args.source)
        elif args.command == 'build':
            result = build(args.manifest, args.source, args.out, args.supplement)
        elif args.out:
            _, result = unpack(args.manifest, args.out, args.source)
        else:
            with tempfile.TemporaryDirectory(prefix='verify-replay-') as tmp:
                _, result = unpack(args.manifest, Path(tmp) / 'sources', args.source)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, KeyError, OSError, tarfile.TarError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Replay failed: {error}\n')


if __name__ == '__main__':
    main()
