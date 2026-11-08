"""Package an app dictionary and an optional CLI support archive from verified runtime files."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

PREFIX = 'app/src/main/assets/english/'
SUPPORT = 'english_dictionary_runtime_support.zip'
OPTIONAL = {'grammar/bundle.properties', 'grammar/categories.erol', 'qwerty_glide_index.dat'}
CORE = {'reading.dat', 'word.dat', 'token.dat'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def archive_bytes(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            require(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts,
                    'Unsafe archive path')
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=9)
    return output.getvalue()


def asset_path(name):
    return PREFIX + ('runtime-support/' if name == 'qwerty_glide_index.dat' else '') + name


def package(args):
    require(re.fullmatch('[0-9a-f]{40}', args.revision), 'Pin the exact builder revision')
    require(not args.out.exists(), 'Use a new distribution directory')
    base_bytes = args.base_archive.read_bytes()
    require(sha(base_bytes) == args.base_archive_sha256, 'Base archive checksum mismatch')
    manifest = json.loads(args.base_manifest.read_bytes())
    with zipfile.ZipFile(io.BytesIO(base_bytes)) as base:
        names = base.namelist()
        require(len(names) == len(set(names)) and set(names) == set(manifest['files']) | {'dictionary-distribution-manifest.json'},
                'Unexpected base archive files')
        require(base.read('dictionary-distribution-manifest.json') == args.base_manifest.read_bytes(), 'Base manifest mismatch')
        for name, digest in manifest['files'].items():
            require(sha(base.read(name)) == digest, 'Base file checksum mismatch: ' + name)
        files = {name: base.read(name) for name in manifest['files'] if not name.startswith(PREFIX)}
    retained = {name: sha(data) for name, data in files.items()}
    runtime = {}
    for path in args.runtime.rglob('*'):
        require(not path.is_symlink(), 'Symlink in runtime bundle')
        if path.is_file():
            name = path.relative_to(args.runtime).as_posix()
            require(name in CORE | OPTIONAL | {'source-evidence-manifest.json', 'supplement-manifest.json'} or
                    re.fullmatch(r'grammar/notices/[^/]+', name), 'Unexpected runtime file: ' + name)
            runtime[name] = path.read_bytes()
    require(CORE | OPTIONAL | {'source-evidence-manifest.json', 'supplement-manifest.json'} <= runtime.keys(), 'Incomplete runtime')
    require(any(name.startswith('grammar/notices/') for name in runtime), 'Missing source notices')
    props = dict(line.split('=', 1) for line in runtime['grammar/bundle.properties'].decode('iso-8859-1').splitlines() if '=' in line)
    require(props.get('categories.erol.sha256') == sha(runtime['grammar/categories.erol']), 'Runtime grammar checksum mismatch')
    notices = {n: b for n, b in runtime.items() if n.startswith('grammar/notices/')}
    require(props.get('noticeCount') == str(len(notices)), 'Runtime notice count mismatch')
    for name, data in notices.items():
        require(props.get('notice.' + name.rsplit('/', 1)[1] + '.sha256') == sha(data), 'Notice checksum mismatch')
    spellings = set()
    pairs = set()
    with args.inventory.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            require(set(row) == {'reading', 'surface', 'cost'} and row['reading'] and row['surface'] and
                    isinstance(row['cost'], int) and -32768 <= row['cost'] <= 32767, 'Invalid candidate inventory')
            require((row['reading'], row['surface']) not in pairs, 'Duplicate candidate pair')
            pairs.add((row['reading'], row['surface']))
            spellings.add(row['surface'])
    require(bool(pairs), 'Empty inventory')
    payload_hashes = {n: sha(b) for n, b in runtime.items()}
    support_files = {asset_path(n): runtime[n] for n in OPTIONAL}
    support_files['english-runtime-support-manifest.json'] = encode(dict(schemaVersion=1, builderRevision=args.revision,
        requiredCorePayloadSha256={n: payload_hashes[n] for n in sorted(CORE)},
        files={n: sha(b) for n, b in support_files.items()}))
    support = archive_bytes(support_files)
    for name, data in runtime.items():
        if name in OPTIONAL:
            continue
        if name in {'reading.dat', 'token.dat'}:
            files[PREFIX + name + '.zip'] = archive_bytes({name: data})
        else:
            files[asset_path(name)] = data
    manifest['englishDictionary'] = dict(builderRevision=args.revision, baseDictionaryRelease=args.base_release,
        baseArchiveSha256=args.base_archive_sha256, source='KazumaProject/kotlin-kana-kanji-converter',
        displaySpellings=len(spellings), readingSurfacePairs=len(pairs), inventorySha256=sha(args.inventory.read_bytes()),
        assetPaths=[PREFIX + n for n in ['reading.dat.zip', 'word.dat', 'token.dat.zip']],
        runtimePayloadSha256=payload_hashes, optionalSupport=dict(file=SUPPORT, sha256=sha(support),
            purpose='CLI grammar and Glide support; overlay with the app archive to reconstruct the complete runtime'),
        verificationScope='JVM binary/CLI checks; Android device behavior unverified')
    manifest['files'] = {n: sha(b) for n, b in sorted(files.items())}
    encoded = encode(manifest)
    files['dictionary-distribution-manifest.json'] = encoded
    archive = archive_bytes(files)
    # Reopen both byte streams, verify manifests and all preserved Japanese files.
    with zipfile.ZipFile(io.BytesIO(archive)) as packed:
        require(packed.testzip() is None and set(packed.namelist()) == set(files), 'Invalid distribution archive')
        for name, digest in manifest['files'].items():
            require(sha(packed.read(name)) == digest, 'Distribution checksum mismatch')
        for name, digest in retained.items():
            require(sha(packed.read(name)) == digest, 'Changed Japanese dictionary')
    with zipfile.ZipFile(io.BytesIO(support)) as packed:
        require(packed.testzip() is None and set(packed.namelist()) == set(support_files), 'Invalid support archive')
    licenses = args.base_licenses.read_bytes() + b'\n\n=== English runtime source notices ===\n'
    for name, data in sorted(notices.items()):
        licenses += b'\n--- ' + name.encode() + b' ---\n' + data + b'\n'
    outputs = {'japanese_keyboard_dictionary_assets.zip': archive, 'dictionary-distribution-manifest.json': encoded,
               'DICTIONARY-LICENSES.txt': licenses, SUPPORT: support}
    outputs['DICTIONARY-SHA256SUMS'] = ''.join(sha(b) + '  ' + n + '\n' for n, b in sorted(outputs.items())).encode()
    args.out.mkdir(parents=True)
    for name, data in outputs.items():
        (args.out / name).write_bytes(data)
    return dict(spellings=len(spellings), pairs=len(pairs), japaneseFilesPreserved=len(retained),
        runtimeBytes=sum(map(len, runtime.values())), defaultEnglishBytes=sum(len(b) for n, b in runtime.items() if n not in OPTIONAL),
        optionalBytes=sum(len(runtime[n]) for n in OPTIONAL), files={n: len(b) for n, b in outputs.items()})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['base-archive', 'base-manifest', 'base-licenses', 'runtime', 'inventory', 'out']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--base-archive-sha256', required=True)
    p.add_argument('--base-release', required=True)
    p.add_argument('--revision', required=True)
    print(json.dumps(package(p.parse_args()), ensure_ascii=False))
