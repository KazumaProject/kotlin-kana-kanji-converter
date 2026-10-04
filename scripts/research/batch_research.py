"""Recover name-bound readings from an existing Wikidata source catalog.

The catalog is a selected-field source projection, not an untouched API response.
Consumed entity records are preserved literally and pinned by their content hashes.
Only existing candidates are considered. No category or negative decision is made,
and an exact lookup without a pronunciation is not a completed research round.
"""
import argparse
import collections
import json
import pathlib
import re
import sqlite3
import time
import unicodedata

import worker as w

PARSER_VERSION = 1
PENDING = ('queued', 'ready_review', 'needs_review', 'error', 'blocked')


def name_key(value):
    value = unicodedata.normalize('NFKC', value)
    return re.sub(r'(?<=[\u3040-\u30ff\u3400-\u9fff々]) +(?=[\u3040-\u30ff\u3400-\u9fff々])', '', value)


def reading_key(value):
    return w.reading(value.replace(' ', '').replace('　', ''))


def reading_bindings(entity):
    """Unqualified P1814 binds the Japanese label, or the title when absent.

    A P5168 qualifier must explicitly supply a Japanese spelling. An unsupported
    qualifier is never silently converted into an unqualified pronunciation.
    """
    if 'missing' in entity:
        return []
    label = entity.get('labels', {}).get('ja', {}).get('value')
    title = entity.get('sitelinks', {}).get('jawiki', {}).get('title')
    result = []
    for statement in entity.get('claims', {}).get('P1814', []):
        if statement.get('rank') == 'deprecated':
            continue
        snak = statement.get('mainsnak', {})
        y = snak.get('datavalue', {}).get('value')
        if snak.get('snaktype', 'value') != 'value' or not isinstance(y, str):
            continue
        qualifiers = statement.get('qualifiers', {}).get('P5168', [])
        if qualifiers:
            names = []
            for qualifier in qualifiers:
                value = qualifier.get('datavalue', {}).get('value')
                if isinstance(value, dict) and value.get('language') == 'ja' and isinstance(value.get('text'), str):
                    names.append(value['text'])
        else:
            names = [label or title] if label or title else []
        for name in names:
            result.append((name, y, statement, bool(qualifiers)))
    return result


def observed_names(entity):
    """Aliases may provide context, but never acquire a primary pronunciation."""
    if 'missing' in entity:
        return set()
    names = {entity.get('labels', {}).get('ja', {}).get('value'),
             entity.get('sitelinks', {}).get('jawiki', {}).get('title')}
    names.update(v.get('value') for v in entity.get('aliases', {}).get('ja', []))
    names.update(name for name, _, _, _ in reading_bindings(entity))
    return {name for name in names if isinstance(name, str) and name}


def primary_kana(entity):
    if 'missing' in entity:
        return set()
    names = (entity.get('labels', {}).get('ja', {}).get('value'),
             entity.get('sitelinks', {}).get('jawiki', {}).get('title'))
    return {name for name in names if isinstance(name, str) and name and
            all('ぁ' <= c <= 'ゖ' or 'ァ' <= c <= 'ヶ' or c == 'ー' for c in name)}


def candidate_index(db):
    index = collections.defaultdict(list)
    query = 'SELECT id,reading,surface FROM candidates WHERE state IN (' + ','.join('?' for _ in PENDING) + ')'
    for row in db.execute(query, PENDING):
        index[name_key(row['surface'])].append(dict(row))
    return index


def related_rows(entity, index):
    result = {}
    for name in observed_names(entity):
        for row in index.get(name_key(name), []):
            result[row['id']] = row
    return list(result.values())


def strict_matches(entity, rows):
    bindings = reading_bindings(entity)
    kana = primary_kana(entity)
    result = []
    for row in rows:
        for name, y, statement, qualified in bindings:
            if name_key(name) == name_key(row['surface']) and reading_key(y) == reading_key(row['reading']):
                result.append((row, name, y, statement, qualified))
        for name in kana:
            if name_key(name) == name_key(row['surface']) and reading_key(name) == reading_key(row['reading']):
                result.append((row, name, name, None, False))
    return result


def source_metadata(path, expected_sha256=None, provenance_paths=()):
    version = w.sha(path)
    if expected_sha256 and version != expected_sha256:
        raise ValueError('Wikidata catalog checksum mismatch')
    provenance = []
    for source in provenance_paths:
        source = pathlib.Path(source)
        record = {'file': source.name, 'sha256': w.sha(source)}
        if source.suffix == '.json':
            value = json.loads(source.read_text())
            if isinstance(value, dict):
                keys = ('dump', 'dumpDate', 'dumpSha256', 'dumpBytes', 'outputCatalogSha256',
                        'titleMapSha256', 'sourceRowsSha256', 'officialChecksumManifestSha256',
                        'pageSqlUrl', 'pagePropsSqlUrl', 'pageSqlSha256', 'pagePropsSqlSha256', 'notes')
                record['reportedSource'] = {key: value[key] for key in keys if key in value}
                if value.get('outputCatalogSha256'):
                    record['catalogHashMatchesReport'] = value['outputCatalogSha256'] == version
                    record['reportRelation'] = 'matching-output-report' if record['catalogHashMatchesReport'] else 'historical-projection-report; current catalog separately pinned'
        provenance.append(record)
    return {'catalogSha256': version, 'catalogFile': path.name,
            'sourceProjection': 'Selected-field Wikidata entity transcription; literal retained claims',
            'provenanceFiles': provenance, 'parserVersion': PARSER_VERSION}


def validate_entity(qid, raw):
    entity = json.loads(raw)
    actual = entity.get('id')
    redirect = entity.get('redirects', {})
    explicit_redirect = isinstance(redirect, dict) and redirect.get('from') == qid and redirect.get('to') == actual
    if not re.fullmatch(r'Q[0-9]+', qid) or not isinstance(actual, str) or not re.fullmatch(r'Q[0-9]+', actual) or (actual != qid and not explicit_redirect):
        raise ValueError('Catalog entity ID mismatch: ' + qid)
    if 'missing' in entity:
        return entity
    if any(key in entity for key in ('names', 'readings', 'nameKinds', 'readingNames', 'readingPairs')):
        raise ValueError('Catalog must contain source claims/labels, not slim derived metadata: ' + qid)
    if any(key in entity and not isinstance(entity[key], dict) for key in ('claims', 'labels', 'aliases', 'sitelinks')):
        raise ValueError('Invalid source entity field shape: ' + qid)
    # Wikibase omits empty dictionaries. Such source items supply no invented
    # claims; their independently published kana names may still be attested.
    if entity.get('type') != 'item' and not ('claims' in entity and 'labels' in entity):
        raise ValueError('Catalog must contain source claims/labels, not slim derived metadata: ' + qid)
    return entity


def title_coverage(db, source, index, metadata, *, audit=False):
    """Preserve exact-title query history independently of semantic decisions.

    An absent catalog record means unchecked. A saved empty match is only an
    exact Japanese Wikipedia-title negative, never an exhaustive name search.
    The source's recorded acquisition time is copied without fabrication.
    """
    if source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='titles'").fetchone() is None:
        return {'titleCoverageAvailable': False}
    if not audit:
        db.execute('''CREATE TABLE IF NOT EXISTS source_exact_lookups(
            candidate_id TEXT,catalog_sha256 TEXT,query TEXT,result TEXT,entity_ids TEXT,
            source_fetched_at INTEGER,projection_sha256 TEXT,
            PRIMARY KEY(candidate_id,catalog_sha256))''')
    counts = collections.Counter({'titleCoverageAvailable': True})
    for rows in index.values():
        for row in rows:
            lookup = source.execute('SELECT entity_ids,fetched_at FROM titles WHERE title=?', (row['surface'],)).fetchone()
            if lookup is None:
                result = 'unchecked'; ids = None; fetched = None
            else:
                ids = json.loads(lookup[0]); fetched = lookup[1]
                if not isinstance(ids, list) or any(not isinstance(qid, str) or not re.fullmatch(r'Q[0-9]+', qid) for qid in ids):
                    raise ValueError('Invalid exact-title lookup record: ' + row['surface'])
                result = 'exact-title-items' if ids else 'no-exact-title-match'
            counts[result] += 1
            projection = {'query': row['surface'], 'result': result, 'entityIds': ids, 'sourceFetchedAt': fetched}
            if not audit:
                db.execute('INSERT OR REPLACE INTO source_exact_lookups VALUES(?,?,?,?,?,?,?)',
                           (row['id'], metadata['catalogSha256'], row['surface'], result,
                            None if ids is None else w.canonical(ids), fetched, w.digest(w.canonical(projection))))
    if not audit:
        db.commit()
    return dict(counts)


def materialize(db, e, entity, raw, rows, matches, metadata):
    qid = entity['id']; raw_bytes = raw.encode('utf-8'); raw_hash = w.digest(raw_bytes)
    revision = str(entity['lastrevid']) if entity.get('lastrevid') is not None else 'sha256:' + raw_hash
    acquisition = {**metadata, 'entityRecordSha256': raw_hash,
                   'revisionKnown': entity.get('lastrevid') is not None,
                   'originInterface': 'https://www.wikidata.org/w/api.php',
                   'entityModified': entity.get('modified')}
    # The URL identifies the original subject. We do not pretend a projected
    # entity record is an API response envelope or fabricate a revision/time.
    did = e.save('https://www.wikidata.org/wiki/Special:EntityData/' + qid + '.json',
                 revision, raw_bytes, 'Wikidata CC0; selected-field source projection')
    import wikidata
    bindings = reading_bindings(entity)
    bound = collections.defaultdict(list)
    for name, y, _, _ in bindings:
        if y not in bound[name]:
            bound[name].append(y)
    body = {'source': 'Wikidata', 'id': qid, 'revision': revision,
            'label': entity.get('labels', {}).get('ja', {}).get('value'),
            'title': entity.get('sitelinks', {}).get('jawiki', {}).get('title'),
            'aliases': [v['value'] for v in entity.get('aliases', {}).get('ja', []) if isinstance(v.get('value'), str)],
            'types': [v['id'] for v, _ in wikidata.values(entity, 'P31') if isinstance(v, dict) and isinstance(v.get('id'), str)],
            'parents': [v['id'] for v, _ in wikidata.values(entity, 'P279') if isinstance(v, dict) and isinstance(v.get('id'), str)],
            'nameBoundReadings': dict(bound), 'primaryReadings': [y for _, y, _, qualified in bindings if not qualified],
            'acquisition': acquisition}
    for row in rows:
        e.fact('', row['surface'], 'context', [], qid, did, body)
    new = set()
    for row, name, y, statement, qualified in matches:
        cy, cs = w.pair(row['reading'], row['surface'])
        existed = db.execute("SELECT 1 FROM facts WHERE active=1 AND kind='reading' AND surface=? AND reading=? LIMIT 1", (cs, cy)).fetchone()
        proof = {'source': 'Wikidata' if statement is not None else 'attested-canonical-kana',
                 'name': name, 'reading': y, 'revision': revision, 'acquisition': acquisition,
                 'binding': 'qualified-name' if qualified else 'primary-name'}
        if statement is not None:
            proof.update({'property': 'P1814', 'statementId': statement.get('id'),
                          'statementSha256': w.digest(w.canonical(statement)), 'quotation': w.canonical(statement)})
        else:
            proof['binding'] = 'Wikidata primary Japanese name'
        e.fact(row['reading'], row['surface'], 'reading', [], qid, did, proof)
        if not existed:
            new.add(row['id'])
    return new


def import_catalog(db, args, catalog, *, audit=False, expected_sha256=None,
                   provenance_paths=(), max_entities=None, max_seconds=None):
    """One resumable ordered pass. Audit uses no ledger or document writes."""
    path = pathlib.Path(catalog).resolve()
    metadata = source_metadata(path, expected_sha256, provenance_paths)
    key = 'rawWikidataCatalog:' + metadata['catalogSha256'] + ':' + str(PARSER_VERSION)
    receipt = None if audit else w.info(db, key)
    if receipt and receipt.get('complete'):
        return receipt
    cursor = receipt.get('cursor', 0) if receipt else 0
    counters = collections.Counter(receipt.get('counts', {}) if receipt else {})
    index = candidate_index(db); e = None if audit else w.Evidence(db, args)
    started = time.monotonic(); scanned = 0; found = set(); paused = False
    source = sqlite3.connect('file:' + path.as_posix() + '?mode=ro', uri=True)
    try:
        coverage = title_coverage(db, source, index, metadata, audit=audit)
        for rowid, qid, raw in source.execute('SELECT rowid,id,body FROM entities WHERE rowid>? ORDER BY rowid', (cursor,)):
            entity = validate_entity(qid, raw)
            rows = related_rows(entity, index)
            matches = strict_matches(entity, rows)
            counters['entitiesScanned'] += 1
            counters['missingEntities'] += 'missing' in entity
            counters['relevantEntities'] += bool(rows)
            counters['strictReadingMatches'] += len(matches)
            if audit:
                for row, *_ in matches:
                    cy, cs = w.pair(row['reading'], row['surface'])
                    if not db.execute("SELECT 1 FROM facts WHERE active=1 AND kind='reading' AND surface=? AND reading=? LIMIT 1", (cs, cy)).fetchone():
                        found.add(row['id'])
            elif rows:
                new = materialize(db, e, entity, raw, rows, matches,
                                  {**metadata, 'catalogEntityKey': qid, 'entityRedirect': entity.get('redirects')})
                counters['newReadingCandidates'] += len(new)
            cursor = rowid; scanned += 1
            if not audit and scanned % 1000 == 0:
                w.info(db, key, {'source': metadata, 'cursor': cursor, 'complete': False, 'counts': dict(counters)})
                db.commit()
                w.emit({'phase': 'raw-wikidata-catalog', 'counts': dict(counters), 'cursor': cursor})
            if (max_entities and scanned >= max_entities) or (max_seconds and time.monotonic() - started >= max_seconds):
                paused = True
                break
    finally:
        source.close()
    if audit:
        counters['newReadingCandidates'] = len(found)
    result = {'source': metadata, 'cursor': cursor, 'complete': not paused,
              'counts': dict(counters), 'modelsCalled': 0, 'networkRequests': 0,
              'exactTitleCoverage': coverage,
              'negativeResearchRoundsRecorded': 0, 'secondsThisRun': round(time.monotonic() - started, 2)}
    if not audit:
        w.info(db, key, result); db.commit()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['import', 'audit'])
    p.add_argument('--catalog', required=True)
    p.add_argument('--catalog-sha256')
    p.add_argument('--provenance', action='append', default=[])
    p.add_argument('--ledger', default='build/research/ledger.sqlite')
    p.add_argument('--config', default=str(w.DEFAULT_CONFIG))
    p.add_argument('--documents', default='build/research/documents')
    p.add_argument('--max-entities', type=int)
    p.add_argument('--max-seconds', type=float)
    args = p.parse_args()
    if any(value is not None and value <= 0 for value in (args.max_entities, args.max_seconds)):
        p.error('Execution limits must be positive')
    audit = args.action == 'audit'
    if audit:
        db = sqlite3.connect('file:' + pathlib.Path(args.ledger).resolve().as_posix() + '?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        try:
            w.emit(import_catalog(db, args, args.catalog, audit=True, expected_sha256=args.catalog_sha256,
                                  provenance_paths=args.provenance, max_entities=args.max_entities, max_seconds=args.max_seconds))
        finally:
            db.close()
    else:
        with w.coordinator_lock(args.ledger), w.connect(args.ledger) as db:
            if not w.info(db, 'prepared') or not w.info(db, 'bulkComplete'):
                raise ValueError('Prepared ledger and mandatory bulk validation are required')
            w.emit(import_catalog(db, args, args.catalog, expected_sha256=args.catalog_sha256,
                                  provenance_paths=args.provenance, max_entities=args.max_entities, max_seconds=args.max_seconds))


if __name__ == '__main__':
    main()
