#!/usr/bin/env python3
"""Resolve one private filter revision and materialize its validated build snapshot."""
import argparse
import fcntl
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

import dictionary_filters

URL = 'https://github.com/KazumaProject/dictionary_filter_list.git'
CACHE = Path.home() / '.cache/kotlin-kana-kanji-converter/dictionary-filter-list.git'


def git(*arguments, cwd=None, binary=False):
    result = subprocess.run(['git', *map(str, arguments)], cwd=cwd, check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout if binary else result.stdout.decode('utf-8').strip()


def resolve_source():
    source = os.environ.get('DICTIONARY_FILTER_SOURCE')
    if source:
        directory = Path(source).resolve(strict=True)
        if os.environ.get('DICTIONARY_FILTER_ALLOW_FIXTURE') != '1':
            remote = git('-C', directory, 'remote', 'get-url', 'origin')
            expected = {
                URL, URL.removesuffix('.git'),
                'git@github.com:KazumaProject/dictionary_filter_list.git',
                'git@github.com:KazumaProject/dictionary_filter_list',
                'ssh://git@github.com/KazumaProject/dictionary_filter_list.git',
            }
            if remote not in expected:
                raise ValueError('Filter checkout does not point to the configured private repository')
        revision = git('-C', directory, 'rev-parse', '--verify', 'HEAD^{commit}')
        return ['-C', directory], revision
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with (CACHE.parent / 'dictionary-filter-list.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not CACHE.exists():
            with tempfile.TemporaryDirectory(prefix='dictionary-filter-clone-', dir=CACHE.parent) as temp:
                clone = Path(temp) / 'repo.git'
                git('clone', '--bare', URL, clone)
                clone.rename(CACHE)
        git('--git-dir', CACHE, 'fetch', '--no-tags', 'origin', 'main')
        revision = git('--git-dir', CACHE, 'rev-parse', '--verify', 'FETCH_HEAD^{commit}')
    return ['--git-dir', CACHE], revision


def prepare(output):
    git_prefix, revision = resolve_source()
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Filter repository revision is invalid')
    archive = git(*git_prefix, 'archive', '--format=tar', revision, binary=True)
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dictionary-filter-snapshot-', dir=output.parent) as temp:
        staging = Path(temp) / 'snapshot'
        staging.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as tar:
            for entry in tar:
                name = entry.name
                if entry.isdir():
                    continue
                if name != 'manifest.json' and not name.startswith('categories/'):
                    continue
                path = Path(name)
                if (not entry.isfile() or path.is_absolute() or '..' in path.parts
                        or (name != 'manifest.json' and path.suffix != '.jsonl')
                        or entry.size > 64 * 1024 * 1024):
                    raise ValueError('Invalid file in dictionary filter repository')
                destination = staging / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(entry) as source, destination.open('wb') as target:
                    shutil.copyfileobj(source, target)
        (staging / 'snapshot.json').write_text(json.dumps({
            'schemaVersion': 1, 'repository': dictionary_filters.REPOSITORY, 'revision': revision,
        }, sort_keys=True) + '\n', encoding='utf-8')
        _, pairs = dictionary_filters.load_snapshot(staging)
        if output.exists():
            shutil.rmtree(output)
        staging.rename(output)
    print(f'Dictionary filter snapshot: revision={revision}, activePairs={len(pairs)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    prepare(parser.parse_args().output)
