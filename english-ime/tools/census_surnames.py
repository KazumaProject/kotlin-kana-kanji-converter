"""Retain attested surnames, including names hidden by obsolete lexical senses.

Only aggregate name/rank/count facts are used. No demographics, individual
identities, preferred casing, corpus senses, gender or inflections are inferred.
"""
import argparse
from collections import defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
from zipfile import ZipFile

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
import resolve_wiktionary as resolver
import restricted_references
from wiktionary_index import Index

ARCHIVE_SHA = '117c41cb4668727b7627b2845b6df3f83eb2a22a1813f42c0ff4bdcab86de135'
CATALOG_SHA = 'b492552723b6e7c2e67ae9db0f73eda73b5b04fb982100b826dd25d753b07d9f'
LICENSE_SHA = 'a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499'
URL = 'https://www2.census.gov/topics/genealogy/2010surnames/names.zip'


def load(directory):
    for name, expected in [('surnames-2010.zip', ARCHIVE_SHA), ('surname-catalog.json', CATALOG_SHA), ('CC0-1.0.txt', LICENSE_SHA)]:
        if pipeline.digest(directory / name) != expected:
            raise ValueError('Changed Census source or license')
    catalog = json.loads((directory / 'surname-catalog.json').read_text())['dataset'][0]
    if catalog['license'] != 'http://creativecommons.org/publicdomain/zero/1.0/' or catalog['c_vintage'] != 2010 or catalog['c_dataset'] != ['surname']:
        raise ValueError('Unexpected Census source metadata')
    with ZipFile(directory / 'surnames-2010.zip') as archive:
        data = archive.read('Names_2010Census.csv')
    values = [{'name': r['name'], 'rank': int(r['rank']), 'count': int(r['count'])}
              for r in csv.DictReader(io.StringIO(data.decode('utf-8-sig'))) if r['name'] != 'ALL OTHER NAMES']
    if len(values) != 162253 or len({r['name'] for r in values}) != len(values) or any(r['count'] < 100 for r in values):
        raise ValueError('Unexpected Census surname table')
    return values, hashlib.sha256(data).hexdigest()


def attach(model, rows, values, spellings):
    wanted = {r['surface'].lower() for r in rows}
    included = 0
    for row in values:
        if row['name'].lower() not in wanted:
            continue
        # Reuse separately documented casing when available. Otherwise retain
        # the literal uppercase source label; never manufacture TitleCase.
        variants = spellings.get(row['name'].lower()) or [(row['name'], None)]
        for surface, esdb_id in variants:
            key = 'census2010-' + hashlib.sha256(surface.encode()).hexdigest()[:24]
            proof = {'source': 'census_surname', 'url': URL + '#Names_2010Census.csv', 'archiveSha256': ARCHIVE_SHA,
                'surname': row['name'], 'rank': row['rank'], 'count': row['count'], 'vintage': 2010,
                'caseWordId': esdb_id, 'literalSourceUppercase': esdb_id is None, 'preferredCaseClaimed': False,
                'scope': 'attested surname identity only; no specific person, corpus sense, demographics or inflection claim', 'approved': True}
            model.add(key, surface, surface, {'noun', 'noun_proper', 'name_person'}, proof, approved=True)
            included += 1
    return included


def extend(args):
    values, csv_sha = load(args.sources)
    model, rows, sources, notices, pending = extension.load_base(args.base, args.seed)
    states = [json.loads(x) for x in (args.base / 'status.jsonl').read_text().splitlines()]
    selected = [r for r, s in zip(rows, states) if s['decision'] in {'pending', 'exclude'}]
    wanted = {r['surface'].lower() for r in selected}
    # Validate the existing ESDB preparation before using its spelling facts.
    esdb, _ = extension.import_esdb(model, set(), args.esdb, pending)
    spellings = defaultdict(list)
    connection = sqlite3.connect((args.esdb / 'esdb.db').resolve().as_uri() + '?mode=ro', uri=True)
    try:
        for word, word_id in connection.execute("select word,word_id from entries where base_pos='n' and (pos_class like 'name%' or pos_class in ('person','surname')) and group_rank not in ('@','~') and entry_rank not in ('@','~') and usage_note=''"):
            if word.lower() in wanted and word != word.lower():
                spellings[word.lower()].append((word, word_id))
    finally:
        connection.close()
    senses = attach(model, selected, values, spellings)
    prior = args.base / 'reviewed-overrides.tsv'
    reviews = pipeline.read_table(prior, 'decisions') if prior.is_file() else []
    reviews, reopened = resolve_pending.revalidate_machine_reviews(model, reviews, pending)
    unresolved = [r for r, s in zip(rows, states) if s['decision'] == 'pending' or r['id'] in reopened]
    index = Index(args.index)
    try:
        records = resolver.load_closure(index, {r['surface'] for r in unresolved})
    finally:
        index.close()
    disqualified, _ = restricted_references.disqualified_roles(records)
    additions = resolve_pending.cases(model, unresolved, {r['word'] for _, r in records}, disqualified)
    prior = args.base / 'surface-corrections.tsv'
    corrections = pipeline.read_table(prior, 'corrections') if prior.is_file() else []
    existing = {r['id'] for r in corrections}
    corrections += [r for r in additions if r['id'] not in existing]
    sources['censusSurnames2010'] = {'archiveSha256': ARCHIVE_SHA, 'csvSha256': csv_sha, 'catalogSha256': CATALOG_SHA,
        'license': 'CC0-1.0, declared by official dataset catalog', 'surnameRows': len(values),
        'esdbCaseDatabaseSha256': esdb['databaseSha256'],
        'policy': 'exact case-insensitive aggregate surname spelling; existing pending/excluded rows only; retain source uppercase unless independently recorded ESDB name casing exists; preferred casing/corpus sense not claimed; modern names reopen only audited machine exclusions'}
    notices['CENSUS-SURNAMES-NOTICE.txt'] = ('U.S. Census Bureau. Frequently Occurring Surnames from the 2010 Census. Names_2010Census.csv.\n' + URL +
        '\nOfficial catalog: https://api.census.gov/data/2010/surname.json ; CC0-1.0.\n'
        'Changes: select name/rank/count only for existing dictionary rows; classify verified surname identities separately from obsolete lexical readings. Retain literal source uppercase or independently documented ESDB spelling. No preferred-case, specific-person, corpus-frequency/sense, gender/race/nationality or inflection inference.\n'
        'Dictionary acceptance and classification conclusions are the implementer\'s, not the Census Bureau\'s.\n').encode()
    notices['CC0-1.0.txt'] = (args.sources / 'CC0-1.0.txt').read_bytes()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.surname-review-', dir=args.out.parent) as temporary:
        reviewed = Path(temporary) / 'reviews.tsv'; pipeline.table(reviewed, 'decisions', reviews)
        summary = pipeline.publish(model, rows, args.base / 'inventory.jsonl', args.out, sources, notices, pending,
            reviewed_decisions=reviewed, allow_input_spellings=True, corrections=corrections)
    print(json.dumps(dict(surnameForms=senses, reopenedMachineExclusions=len(reopened), newCaseRows=len({r['id'] for r in additions}),
        **{k: summary[k] for k in ['includedRows', 'excludedRows', 'pendingRows']}), sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['base', 'seed', 'sources', 'index', 'esdb', 'out']:
        parser.add_argument('--' + name, type=Path, required=True)
    extend(parser.parse_args())
