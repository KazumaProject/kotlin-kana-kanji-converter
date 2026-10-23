#!/usr/bin/env python3
"""Collect explicit vocabulary facts without model calls; apply them through offline validators."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
from http.client import HTTPException
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from urllib.error import HTTPError
from urllib.parse import urldefrag, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

import classification_reviews as reviews
import classified_distribution as distribution
import collected_terms as terms
import specialist_distribution as specialist

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path('src/main/collection/sources.json')
DEFAULT_WORK = Path.home() / '.cache/kotlin-kana-kanji-converter/term-collection'
KANA = re.compile(r'[ぁ-ゖァ-ヶー\s・]+')
PAIR = re.compile(r'^([^（）()]+?)[\s]*[（(]([ぁ-ゖァ-ヶー\s・]+)[）)](.*)$')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.tmp')
    pending.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    pending.replace(path)


def external_work(root, path):
    path = path.expanduser().resolve()
    if path == root or root in path.parents:
        raise ValueError('--work-dir must be outside the repository')
    path.mkdir(parents=True, exist_ok=True)
    return path


def configuration(root, path=CONFIG):
    document = json.loads((root / path).read_text(encoding='utf-8'))
    if document.get('schemaVersion') != 1 or not document.get('sources'):
        raise ValueError('Invalid collection configuration')
    ids = set()
    for spec in document['sources']:
        if spec['id'] in ids or spec['category'] not in ('kampo', 'product'):
            raise ValueError('Duplicate source ID or invalid category')
        ids.add(spec['id'])
        if spec['kind'] not in ('html', 'json', 'snapshot', 'wikidata'):
            raise ValueError('Unsupported source kind')
        if spec.get('enabled') is not False and spec['kind'] in ('html', 'json'):
            if not isinstance(spec.get('urls'), list) or not spec['urls']:
                raise ValueError('Active HTML/JSON sources require at least one URL: ' + spec['id'])
            if spec['kind'] == 'html' and not spec.get('name_selector'):
                raise ValueError('Active HTML sources require a product-name selector: ' + spec['id'])
    return document


class Cache:
    """One in-flight request per host; successful responses survive interrupted runs."""
    def __init__(self, directory, resume=False):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.resume = resume
        self.locks = {}
        self.guard = threading.Lock()

    def fetch(self, url):
        host = urlsplit(url).hostname
        if urlsplit(url).scheme != 'https' or not host:
            raise ValueError('Only HTTPS sources are supported')
        with self.guard:
            lock = self.locks.setdefault(host, threading.Lock())
        with lock:
            return self._fetch(url)

    def _fetch(self, url):
        key = hashlib.sha256(url.encode()).hexdigest()
        meta_path = self.directory / (key + '.json')
        metadata = json.loads(meta_path.read_text()) if meta_path.exists() else None
        if metadata:
            body = self.directory / (metadata['sha256'] + '.body')
            if not body.exists() or distribution.sha(body) != metadata['sha256'] or metadata['url'] != url:
                raise ValueError('Corrupted source cache: ' + url)
            if self.resume:
                return body.read_bytes(), metadata
        headers = {'User-Agent': 'kana-kanji-dictionary-source/1.0', 'Accept': 'application/json,text/html;q=0.9'}
        if metadata:
            for name, field in [('If-None-Match', 'etag'), ('If-Modified-Since', 'last_modified')]:
                if metadata.get(field):
                    headers[name] = metadata[field]
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                if urlsplit(response.url).hostname != urlsplit(url).hostname:
                    raise ValueError('Source redirected to a different host: ' + response.url)
                raw = response.read()
                digest = hashlib.sha256(raw).hexdigest()
                body = self.directory / (digest + '.body')
                with tempfile.NamedTemporaryFile(dir=self.directory, delete=False) as pending:
                    pending.write(raw)
                    pending_path = Path(pending.name)
                pending_path.replace(body)
                metadata = dict(url=url, sha256=digest, encoding=response.headers.get_content_charset(),
                                etag=response.headers.get('ETag'), last_modified=response.headers.get('Last-Modified'))
        except HTTPError as error:
            if error.code != 304 or not metadata:
                raise
            raw = body.read_bytes()
        metadata['checked_on'] = datetime.now(timezone.utc).date().isoformat()
        write_json(meta_path, metadata)
        return raw, metadata


def fact(spec, metadata, source_surface, source_reading, method):
    entry = dict(category=spec['category'], source_id=spec['id'], source_url=metadata['url'],
                 source_sha256=metadata['sha256'], checked_on=metadata['checked_on'],
                 source_surface=source_surface.strip(), source_reading=source_reading.strip(),
                 surface=terms.surface(source_surface), reading=terms.reading(source_reading), evidence_method=method)
    terms.validate(entry)
    if entry['surface'] in spec.get('withhold_surfaces', {}):
        raise ValueError('source_spelling_conflict: ' + spec['withhold_surfaces'][entry['surface']])
    reason = specialist.invalid_reason(entry['source_reading'], entry['source_surface'], entry['reading'], entry['surface'])
    if reason:
        raise ValueError(reason)
    return entry


def soup_document(raw, metadata):
    # The collector is the only online/build-independent code requiring this package.
    from bs4 import BeautifulSoup
    return BeautifulSoup(raw, 'html.parser', from_encoding=metadata.get('encoding'))


def html_facts(raw, spec, metadata):
    soup = soup_document(raw, metadata)
    nodes = soup.select(spec['name_selector'])
    if not nodes:
        raise ValueError('No product-name nodes matched; check source markup/selector')
    result, withheld = [], []
    for node in nodes:
        text = node.get_text('', strip=False).strip()
        if not text:
            continue
        try:
            if node.find('ruby'):
                copy = soup_document(str(node).encode('utf-8'), {'encoding': 'utf-8'})
                original = soup_document(str(node).encode('utf-8'), {'encoding': 'utf-8'})
                for ruby in copy.find_all('ruby'):
                    rt = ruby.find_all('rt')
                    if not rt:
                        raise ValueError('ruby_missing_reading')
                    ruby.replace_with(''.join(t.get_text() for t in rt))
                for annotation in original.select('rt, rp'):
                    annotation.decompose()
                result.append(fact(spec, metadata, original.get_text().strip(), copy.get_text().strip(), 'ruby'))
            else:
                match = PAIR.fullmatch(text)
                if (match and (not match[3].strip() or spec.get('allow_description', False))
                        and re.fullmatch(spec.get('pair_surface_pattern', '.+'), match[1].strip())):
                    result.append(fact(spec, metadata, match[1], match[2], 'parenthesized'))
                elif KANA.fullmatch(text) and (spec.get('allow_kana_surface', True) or text in spec.get('kana_allowlist', [])):
                    result.append(fact(spec, metadata, text, text, 'kana_surface'))
                else:
                    withheld.append(dict(surface=text, reason='reading_not_explicit', source_url=metadata['url']))
        except ValueError as error:
            withheld.append(dict(surface=text, reason=str(error), source_url=metadata['url']))
    links = []
    for node in soup.select(spec.get('follow_selector', 'a.__no_collection_links__')):
        url = urldefrag(urljoin(metadata['url'], node.get('href', '')))[0]
        if (urlsplit(url).hostname == urlsplit(spec['urls'][0]).hostname
                and re.fullmatch(spec['follow_url_pattern'], url)):
            links.append(url)
    return result, withheld, sorted(set(links))


def json_facts(raw, spec, metadata):
    data = json.loads(raw)
    for part in spec.get('items_path', '').split('.'):
        if part:
            data = data[part]
    if not isinstance(data, list) or not data:
        raise ValueError('Missing/non-list product data')
    result, withheld = [], []
    for item in data:
        name = item.get(spec['surface_field'])
        kana = item.get(spec['reading_field'])
        if not isinstance(name, str) or not isinstance(kana, str):
            raise ValueError('Product fields changed or missing')
        try:
            original_name, original_kana = name, kana
            if spec.get('surface_prefix'):
                if not name.startswith(spec['surface_prefix']) or not kana.startswith(spec['reading_prefix']):
                    raise ValueError('source_prefix_mismatch')
                name, kana = name[len(spec['surface_prefix']):], kana[len(spec['reading_prefix']):]
            if spec.get('surface_pattern'):
                match = re.fullmatch(spec['surface_pattern'], name)
                if not match:
                    raise ValueError('source_surface_pattern_mismatch')
                name = match['surface']
            entry = fact(spec, metadata, name, kana, 'fields')
            entry['source_fields'] = {spec['surface_field']: original_name, spec['reading_field']: original_kana}
            result.append(entry)
        except ValueError as error:
            withheld.append(dict(surface=name, reason=str(error), source_url=metadata['url']))
    return result, withheld, []


def collect_source(root, spec, cache):
    result, withheld, failures = [], [], []
    if spec.get('enabled') is False:
        return [], [], [dict(source_id=spec['id'], url=spec['urls'][0], error=spec['disabled_reason'])], 0
    visited, pending = set(), set(spec.get('urls', []))
    if spec['kind'] == 'snapshot':
        path = root / spec['path']
        metadata = dict(url=spec['page'], sha256=distribution.sha(path), checked_on=datetime.now(timezone.utc).date().isoformat())
        for row in specialist.read_json_gzip(path):
            try:
                entry = fact(spec, metadata, row['surface'], row['reading'], 'fields')
                # These are preserved upstream readings, not newly independently verified facts.
                entry['upstream_only'] = True
                result.append(entry)
            except ValueError as error:
                withheld.append(dict(surface=row['surface'], reason=str(error), source_url=spec['page']))
        return result, withheld, failures, 1
    if spec['kind'] == 'wikidata':
        query = ('SELECT DISTINCT ?item ?itemLabel ?reading WHERE { VALUES ?type { wd:Q431289 wd:Q2424752 } '
                 '?item wdt:P31 ?type; wdt:P1814 ?reading. '
                 'SERVICE wikibase:label { bd:serviceParam wikibase:language "ja". } } ORDER BY ?item ?reading')
        pending = {'https://query.wikidata.org/sparql?' + urlencode({'query': query, 'format': 'json'})}
    while pending:
        url = min(pending)
        pending.remove(url)
        if url in visited:
            continue
        visited.add(url)
        try:
            raw, metadata = cache.fetch(url)
            if spec['kind'] == 'wikidata':
                for row in json.loads(raw)['results']['bindings']:
                    withheld.append(dict(surface=row['itemLabel']['value'], reading=row['reading']['value'],
                                         source_url=row['item']['value'], reason='needs_official_confirmation'))
                continue
            entries, held, links = (json_facts(raw, spec, metadata) if spec['kind'] == 'json'
                                    else html_facts(raw, spec, metadata))
            result.extend(entries)
            withheld.extend(held)
            pending.update(set(links) - visited)
        except (OSError, ValueError, KeyError, TypeError, HTTPException) as error:
            failures.append(dict(source_id=spec['id'], url=url, error=str(error)))
    return result, withheld, failures, len(visited)


def build_index(root, inventory, work):
    if not inventory.is_file():
        raise ValueError('Missing actual dictionary inventory; run ./gradlew exportExistingDictionaryInventory first')
    decisions_path = root / 'src/main/classification/distribution-decisions.tsv.gz'
    specialist_path = root / specialist.DIRECTORY / 'distribution-candidates.tsv.gz'
    signature = ':'.join(distribution.sha(p) for p in (inventory, decisions_path, specialist_path))
    path = work / 'existing.sqlite3'
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE IF NOT EXISTS metadata (signature TEXT)')
    if con.execute('SELECT signature FROM metadata').fetchone() == (signature,):
        return con
    with con:
        con.execute('DROP TABLE IF EXISTS pairs')
        con.execute('CREATE TABLE pairs (reading TEXT, surface TEXT, reason TEXT, PRIMARY KEY (reading,surface)) WITHOUT ROWID')
        def inventories():
            for row in specialist.read_json_gzip(inventory):
                yield (*specialist.key(row['reading'], row['surface']), 'existing_duplicate')
            with gzip.open(specialist_path, 'rt', encoding='utf-8') as stream:
                for line in stream:
                    row = line.rstrip('\n').split('\t')
                    yield (*specialist.key(row[1], row[5]), 'existing_duplicate')
            with gzip.open(decisions_path, 'rt', encoding='utf-8') as stream:
                for line in stream:
                    row = line.rstrip('\n').split('\t')
                    yield (*specialist.key(row[0], row[1]), 'classification_conflict')
        con.executemany('INSERT OR IGNORE INTO pairs VALUES (?,?,?)', inventories())
        con.execute('DELETE FROM metadata')
        con.execute('INSERT INTO metadata VALUES (?)', (signature,))
    return con


def select_new(entries, con):
    selected, held, seen = [], [], set()
    for entry in sorted(entries, key=lambda e: (e['category'] != 'kampo', e['reading'], e['surface'], e['source_id'])):
        pair = entry['reading'], entry['surface']
        found = con.execute('SELECT reason FROM pairs WHERE reading=? AND surface=?', pair).fetchone()
        reason = found[0] if found else 'source_duplicate' if pair in seen else 'upstream_reading_unverified' if entry.get('upstream_only') else None
        if reason:
            held.append(dict(surface=entry['surface'], reading=entry['reading'], reason=reason, source_url=entry['source_url']))
        else:
            selected.append(entry)
            seen.add(pair)
    return selected, held


def collect(root, work, inventory, selected_sources, resume):
    config = configuration(root)
    disabled = {s['id']: s['disabled_reason'] for s in config['sources'] if s.get('enabled') is False}
    specs = [s for s in config['sources'] if (selected_sources == ['all'] and s.get('enabled') is not False)
             or s['id'] in selected_sources]
    if not specs or selected_sources != ['all'] and set(selected_sources) != {s['id'] for s in specs}:
        raise ValueError('Unknown source; use an ID from sources.json or all')
    cache = Cache(work / 'cache', resume)
    entries, held, failures, counts = [], [], [], {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        for spec, output in zip(specs, executor.map(lambda s: collect_source(root, s, cache), specs)):
            rows, withheld, errors, pages = output
            entries.extend(rows); held.extend(withheld); failures.extend(errors)
            counts[spec['id']] = dict(pages=pages, extracted=len(rows), withheld=len(withheld), failed=len(errors))
    con = build_index(root, inventory, work)
    try:
        selected, duplicates = select_new(entries, con)
    finally:
        con.close()
    held.extend(duplicates)
    batch = dict(schemaVersion=1, sourceConfigSha256=distribution.sha(root / CONFIG),
                 baseInventorySha256=distribution.sha(inventory), records=selected)
    batch_id = hashlib.sha256(terms.encode([batch])).hexdigest()[:16]
    directory = work / 'batches' / batch_id
    write_json(directory / 'batch.json', batch)
    report = dict(batch=str(directory / 'batch.json'), sources=counts, accepted=len(selected),
                  acceptedByCategory={c: sum(e['category'] == c for e in selected) for c in ('kampo', 'product')},
                  withheld=held, failures=failures, disabledSources=disabled, complete=not failures)
    write_json(directory / 'report.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('withheld',)}, ensure_ascii=False))
    return report


def validate_batch(root, work, path):
    batch = json.loads(path.read_text(encoding='utf-8'))
    if batch.get('schemaVersion') != 1 or batch.get('sourceConfigSha256') != distribution.sha(root / CONFIG):
        raise ValueError('Batch configuration changed; collect again')
    specs = {s['id']: s for s in configuration(root)['sources']}
    seen, parsed = set(), {}
    for entry in batch['records']:
        terms.validate(entry)
        pair = entry['reading'], entry['surface']
        if pair in seen:
            raise ValueError('Duplicate pair in batch')
        seen.add(pair)
        spec = specs[entry['source_id']]
        if spec['category'] != entry['category'] or spec['kind'] not in ('html', 'json'):
            raise ValueError('Batch source/category is not an explicit official reading source')
        url = entry['source_url']
        if url not in spec['urls'] and not (spec.get('follow_url_pattern') and re.fullmatch(spec['follow_url_pattern'], url)):
            raise ValueError('Batch URL is outside configured collection paths')
        key = entry['source_id'], url, entry['source_sha256'], entry['checked_on']
        if key not in parsed:
            raw_path = work / 'cache' / (entry['source_sha256'] + '.body')
            if not raw_path.is_file() or distribution.sha(raw_path) != entry['source_sha256']:
                raise ValueError('Missing/modified source body; restore the collection cache')
            metadata = dict(url=url, sha256=entry['source_sha256'], checked_on=entry['checked_on'], encoding=spec.get('encoding'))
            output = json_facts(raw_path.read_bytes(), spec, metadata) if spec['kind'] == 'json' else html_facts(raw_path.read_bytes(), spec, metadata)
            parsed[key] = output[0]
        if entry not in parsed[key]:
            raise ValueError('Batch entry does not match re-extracted source evidence')
    return batch


def noun_id(root):
    ids = [int(i) for i, name in (line.split(maxsplit=1) for line in
           (root / 'src/main/resources/id.def').read_text().splitlines()) if name == specialist.NOUN]
    if len(ids) != 1:
        raise ValueError('Missing/ambiguous noun context')
    return ids[0]


def inventory_export(root, output, classified_directory=None, log=None):
    command = [str(root / 'gradlew'), '--quiet', 'exportExistingDictionaryInventory',
               '-PexistingDictionaryInventoryOutput=' + str(output)]
    if classified_directory:
        command.append('-PexistingDictionaryClassificationDirectory=' + str(classified_directory))
    with log.open('w') as stream:
        try:
            subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT, check=True)
        except subprocess.CalledProcessError as error:
            raise ValueError(f'Dictionary inventory export failed (exit {error.returncode}); see {log}') from error


def stage_inputs(root, staging):
    for name in ('classification', 'specialist'):
        shutil.copytree(root / 'src/main' / name, staging / 'src/main' / name)
    for child in (root / 'src/main').iterdir():
        target = staging / 'src/main' / child.name
        if not target.exists():
            target.symlink_to(child, target_is_directory=child.is_dir())


def apply_batch(root, work, batch_path):
    root, work = root.resolve(), work.resolve()
    batch = validate_batch(root, work, batch_path)
    print('Exporting the current runtime dictionary inventory...', flush=True)
    inventory = work / 'apply-existing-pairs.jsonl.gz'
    inventory_export(root, inventory, log=work / 'apply-inventory.log')
    con = build_index(root, inventory, work)
    try:
        selected, held = select_new(batch['records'], con)
    finally:
        con.close()
    if any(r['reason'] == 'classification_conflict' for r in held):
        raise ValueError('Batch conflicts with a current classification/exclusion; collect again')
    if not selected:
        print('Added 0 pairs (already present)')
        return 0
    # Validate both dictionary families in isolation before replacing any repository file.
    batch_id = terms.digest(selected)[:16]
    with tempfile.TemporaryDirectory(prefix='apply-', dir=work) as temporary:
        staging = Path(temporary)
        stage_inputs(root, staging)
        products = [e for e in selected if e['category'] == 'product']
        kampo = [e for e in selected if e['category'] == 'kampo']
        if products:
            print(f'Validating {len(products)} staged product additions against saved reviews...', flush=True)
            context = noun_id(root)
            documents = [dict(reading=e['reading'], surface=e['surface'], candidate_key=distribution.key(e['reading'], e['surface']),
                              action='add', baseline=None, categories=['product'],
                              reason='公式製品一覧の明示された表記・読みを機械抽出。',
                              added_record=dict(left_id=context, right_id=context, cost=9400),
                              evidence=dict(kind='independent_source', reading=e['reading'], surface=e['surface'], categories=['product'],
                                            reference=e['source_url'], collection=e)) for e in products]
            target = staging / reviews.DIRECTORY / 'reviews' / ('collection-' + batch_id + '.jsonl')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(terms.encode(documents))
            reviews.apply_saved(staging, commit=True)
        if kampo:
            target = staging / terms.DIRECTORY / (batch_id + '.jsonl')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(terms.encode(kampo))
        staged_inventory = staging / 'existing-pairs.jsonl.gz'
        print('Exporting the staged inventory and checking specialist duplicates...', flush=True)
        inventory_export(root, staged_inventory, staging / reviews.DIRECTORY, work / 'staged-inventory.log')
        specialist.freeze(staging, staged_inventory)
        specialist.verify(staging, staged_inventory)
        # Product classifications were verified by apply_saved; the Kampo-only
        # path leaves the already-verified classification snapshot unchanged.
        changes = []
        for parent in (reviews.DIRECTORY, Path(specialist.DIRECTORY)):
            for source in sorted((staging / parent).rglob('*')):
                if not source.is_file():
                    continue
                relative = source.relative_to(staging)
                target = root / relative
                if not target.exists() or source.read_bytes() != target.read_bytes():
                    changes.append((relative, source, target))
        backup = work / ('backup-' + batch_id)
        journal = work / 'apply-journal.json'
        if journal.exists():
            raise ValueError('Interrupted apply detected; restore files using apply-journal.json before retrying')
        records = []
        for relative, source, target in changes:
            saved = backup / relative
            if target.exists():
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(target, saved)
            records.append(dict(path=str(relative), backup=str(saved) if target.exists() else None,
                                sha256=distribution.sha(saved) if target.exists() else None))
        write_json(journal, dict(root=str(root), files=records))
        try:
            for relative, source, target in changes:
                target.parent.mkdir(parents=True, exist_ok=True)
                pending = target.with_name(target.name + '.tmp')
                shutil.copyfile(source, pending)
                pending.replace(target)
        except BaseException:
            for record in records:
                target = root / record['path']
                if record['backup']:
                    shutil.copyfile(record['backup'], target)
                else:
                    target.unlink(missing_ok=True)
            journal.unlink()
            raise
        journal.unlink()
        final_inventory = root / 'build/specialist/existing-pairs.jsonl.gz'
        final_inventory.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(staged_inventory, final_inventory)
    print(json.dumps(dict(added=len(selected), product=len(products), kampo=len(kampo)), ensure_ascii=False))
    return len(selected)


def recover(root, work):
    root, work = root.resolve(), work.resolve()
    journal = work / 'apply-journal.json'
    record = json.loads(journal.read_text())
    if Path(record.get('root', '')).resolve() != root:
        raise ValueError('Recovery journal belongs to another checkout')
    # Validate every backup/path before restoring the first file.
    for item in record['files']:
        relative = Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts or not any(
                parent in relative.parents for parent in (reviews.DIRECTORY, Path(specialist.DIRECTORY))):
            raise ValueError('Invalid recovery target')
        if item['backup']:
            backup = Path(item['backup']).resolve()
            if work not in backup.parents or distribution.sha(backup) != item['sha256']:
                raise ValueError('Invalid recovery backup')
    for item in record['files']:
        target = root / item['path']
        if item['backup']:
            shutil.copyfile(item['backup'], target)
        else:
            target.unlink(missing_ok=True)
    journal.unlink()
    print('Restored the previous dictionary snapshot; apply the batch again to resume')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['collect', 'apply', 'verify', 'recover'])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--work-dir', type=Path, default=DEFAULT_WORK)
    parser.add_argument('--source', nargs='+', default=['all'])
    parser.add_argument('--existing-index', type=Path)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--batch', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    work = external_work(root, args.work_dir)
    # Also prevents two collectors from racing over the same cache/index/journal.
    with (work / 'collection.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == 'recover':
            with reviews.locked(root):
                recover(root, work)
            return
        if (work / 'apply-journal.json').exists():
            raise ValueError('Interrupted apply: run recover first')
        if args.command == 'collect':
            inventory = args.existing_index or root / 'build/specialist/existing-pairs.jsonl.gz'
            report = collect(root, work, inventory, args.source, args.resume)
            if report['failures']:
                raise SystemExit(2)
        else:
            if not args.batch:
                parser.error('--batch is required for apply/verify')
            if args.command == 'verify':
                batch = validate_batch(root, work, args.batch)
                print('Verified offline source evidence:', len(batch['records']))
            else:
                with reviews.locked(root):
                    apply_batch(root, work, args.batch)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
