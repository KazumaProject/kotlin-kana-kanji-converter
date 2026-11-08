"""Source-backed dictionary acquisition: words, forms, terms, products and names.

No typo generation, IME ranking, model calls, installation or scheduled work.
Raw downloads and acquisition manifests always stay outside Git.
"""
import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import urllib.request
from urllib.parse import urljoin

import vocabulary_sources as lexical
from extend_lexicon import categories_for, roles_for
from prepare_esdb import URL as ESDB_URL
from replay_source import require, sha

PROFILE = 'dictionary-catalog-v1'
FACETS = ('basic', 'daily', 'inflection', 'orthography', 'technology', 'product', 'person')
BASIC = {
    'ngsl-stats.csv': ('https://www.newgeneralservicelist.com/s/NGSL_12_stats.csv',
        '2098bab8955a120a9766c6282a51d7d578c6cb0a7d946600d2ffb73ba25a0b44', 2809),
    'ngsl-spoken-stats.csv': ('https://www.newgeneralservicelist.com/s/NGSL-Spoken_12_stats.csv',
        '07708940c50a07cac4f507fd1e87bdd50081d7b87713a66a99beb3c8c4d11ac8', 721),
    'ngsl-supplementary.csv': ('https://www.newgeneralservicelist.com/s/SUP_lemmatized.csv',
        '7bb4c76cbe43ae87240be4ac7ada370b9e1a0d9d631d8c4430138646965d03f6', 52),
}
CC4 = 'https://creativecommons.org/licenses/by-sa/4.0/'
MDN = 'https://developer.mozilla.org/en-US/docs/Glossary'
CATALOG = 'https://formulae.brew.sh/api/cask.json'
ANALYTICS = 'https://formulae.brew.sh/api/analytics/cask-install/90d.json'


def download(url, path, maximum=48 * 1024 * 1024):
    if path.exists():
        require(path.is_file() and not path.is_symlink(), 'Invalid cached source')
        return
    request = urllib.request.Request(url, headers={'User-Agent':
        'EnglishDictionaryHarness/1.0 (KazumaProject/kotlin-kana-kanji-converter)'})
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                remaining = maximum
                while block := response.read(min(1024 * 1024, remaining + 1)):
                    remaining -= len(block)
                    require(remaining >= 0, 'Oversized source')
                    stream.write(block)
            stream.flush()
            temporary.rename(path)
        finally:
            temporary.unlink(missing_ok=True)


def fetch(directory, esdb):
    import vocabulary_harness as h
    directory, esdb = h.external(directory), h.external(esdb)
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / 'dictionary-sources.json'
    if manifest_path.exists():
        verify(directory)
        lexical.source_files(directory, esdb)
        return
    lexical.fetch_sources(directory, esdb)
    for name, (url, digest, _) in BASIC.items():
        download(url, directory / name)
        require(sha(directory / name) == digest, 'Changed basic source: ' + name)
    records = {}
    for name, url in [('mdn-glossary.html', MDN),
            ('mdn-license.md', 'https://raw.githubusercontent.com/mdn/content/main/LICENSE.md'),
            ('homebrew-analytics-license.txt', 'https://raw.githubusercontent.com/Homebrew/formulae.brew.sh/main/LICENSE.txt'),
            ('cask.json', CATALOG), ('cask-analytics.json', ANALYTICS)]:
        download(url, directory / name)
        records[name] = dict(url=url, sha256=sha(directory / name), bytes=(directory / name).stat().st_size)
    casks = json.loads((directory / 'cask.json').read_text())
    require(isinstance(casks, list) and casks, 'Empty product catalog')
    revision = casks[0]['tap_git_head']
    require(re.fullmatch(r'[0-9a-f]{40}', revision), 'Missing Homebrew revision')
    license_url = 'https://raw.githubusercontent.com/Homebrew/homebrew-cask/' + revision + '/LICENSE'
    download(license_url, directory / 'homebrew-license.txt')
    records['homebrew-license.txt'] = dict(url=license_url, sha256=sha(directory / 'homebrew-license.txt'),
        bytes=(directory / 'homebrew-license.txt').stat().st_size)
    require('CC-BY-SA 2.5' in (directory / 'mdn-license.md').read_text() and
            'BSD 2-Clause License' in (directory / 'homebrew-license.txt').read_text() and
            'Redistribution and use' in (directory / 'homebrew-analytics-license.txt').read_text(), 'Unexpected source licenses')
    attribution = ('Basic-word selection: NGSL and NGSL-Spoken, Browne, Culligan and Phillips (NGSL); '
        'Browne and Culligan (Spoken). CC BY-SA 4.0.\n'
        'https://www.newgeneralservicelist.com/new-general-service-list\n'
        'https://www.newgeneralservicelist.com/ngsl-spoken\n' + CC4 + '\n'
        'Changes: first-column headwords select independently attested ESDB spellings and paradigms. '
        'List family members and source capitalization are not automatically adopted.\n')
    (directory / 'NGSL-DICTIONARY-NOTICE.txt').write_text(attribution, encoding='utf-8')
    (directory / 'MDN-DICTIONARY-NOTICE.txt').write_text(
        'MDN Web Docs contributors. ' + MDN + '\nCC BY-SA 2.5 or later.\n'
        'https://creativecommons.org/licenses/by-sa/2.5/\n'
        'Changes: extract glossary-link labels and their URLs; retain exact display spelling. '
        'No definitions or code examples copied; no English POS or morphology inferred.\n', encoding='utf-8')
    for name in ['NGSL-DICTIONARY-NOTICE.txt', 'MDN-DICTIONARY-NOTICE.txt']:
        records[name] = dict(sha256=sha(directory / name), bytes=(directory / name).stat().st_size)
    manifest = dict(schemaVersion=1, profile=PROFILE, capturedAt=dt.datetime.now(dt.timezone.utc).isoformat(), files=records,
        basicPins={name: digest for name, (_, digest, _) in BASIC.items()},
        licenses={
            'esdb': dict(id='LicenseRef-ESDB', url=ESDB_URL.replace('/tree/', '/blob/') + '/Copyright',
                attribution='ESDB and component word-list contributors; retain complete Copyright and sources notices'),
            'ngsl': dict(id='CC-BY-SA-4.0', url=CC4, attribution='Browne, Culligan, Phillips; see NGSL notice'),
            'mdn': dict(id='CC-BY-SA-2.5-or-later', url='https://creativecommons.org/licenses/by-sa/2.5/',
                attribution='MDN Web Docs contributors'),
            'homebrew': dict(id='BSD-2-Clause', url=license_url, attribution='Homebrew contributors'),
            'homebrew_analytics': dict(id='BSD-2-Clause',
                url='https://github.com/Homebrew/formulae.brew.sh/blob/main/LICENSE.txt', attribution='Homebrew contributors')})
    h.dump(manifest_path, manifest)


def verify(directory):
    manifest = json.loads((directory / 'dictionary-sources.json').read_text())
    require(manifest['schemaVersion'] == 1 and manifest['profile'] == PROFILE and
            manifest['basicPins'] == {name: digest for name, (_, digest, _) in BASIC.items()}, 'Unknown dictionary source recipe')
    expected = {'mdn-glossary.html', 'mdn-license.md', 'cask.json', 'cask-analytics.json', 'homebrew-license.txt', 'homebrew-analytics-license.txt',
                'NGSL-DICTIONARY-NOTICE.txt', 'MDN-DICTIONARY-NOTICE.txt'}
    require(set(manifest['files']) == expected and set(manifest['licenses']) == {'esdb', 'ngsl', 'mdn', 'homebrew', 'homebrew_analytics'},
        'Missing source or license metadata')
    require({name: record['id'] for name, record in manifest['licenses'].items()} ==
        {'esdb': 'LicenseRef-ESDB', 'ngsl': 'CC-BY-SA-4.0', 'mdn': 'CC-BY-SA-2.5-or-later',
         'homebrew': 'BSD-2-Clause', 'homebrew_analytics': 'BSD-2-Clause'},
        'Changed source license policy')
    require(manifest['files']['mdn-glossary.html']['url'] == MDN and
        manifest['files']['cask.json']['url'] == CATALOG and
        manifest['files']['cask-analytics.json']['url'] == ANALYTICS, 'Unexpected catalog source')
    for name, record in manifest['files'].items():
        path = directory / name
        require(path.is_file() and not path.is_symlink() and sha(path) == record['sha256'] and
                path.stat().st_size == record['bytes'], 'Changed dictionary source or notice: ' + name)
    for name, (_, digest, _) in BASIC.items():
        require(sha(directory / name) == digest, 'Changed basic source: ' + name)
    return manifest


class Glossary(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = None
        self.labels = []

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get('href', '')
        if tag == 'a' and re.fullmatch(r'/en-US/docs/Glossary/[^?#]+', href):
            self.active = [href, [], self.getpos()[0]]

    def handle_data(self, text):
        if self.active is not None:
            self.active[1].append(text)

    def handle_endtag(self, tag):
        if tag == 'a' and self.active is not None:
            href, parts, line = self.active
            self.labels.append((''.join(parts).strip(), urljoin(MDN, href), line))
            self.active = None


def basic_words(directory):
    words = set()
    for name, (_, _, count) in BASIC.items():
        with (directory / name).open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.reader(stream))
        rows = rows if 'supplementary' in name else rows[1:]
        require(len(rows) == count, 'Changed basic-list row count')
        words.update(lexical.key(row[0]) for row in rows)
    return words


def collect(directory, esdb, categories, existing, excluded, references=None, audit_dir=None):
    directory, esdb = directory.resolve(), esdb.resolve()
    require(references is None, 'Dictionary profile uses its frozen catalogs; use the legacy profile for reviewed references')
    manifest = verify(directory)
    pinned = lexical.source_files(directory, esdb)
    common = basic_words(directory)
    wn = lexical.wordnet(directory / 'wordnet.tar.gz')
    usage = Counter()
    for domain in lexical.corpus_words(directory / 'ewt-train.conllu', 'ewt').values():
        usage.update(domain)
    lemma_usage = Counter()
    form_usage = Counter()
    for line in (directory / 'ewt-train.conllu').read_text(encoding='utf-8').splitlines():
        row = line.split('\t')
        if len(row) == 10 and row[0].isdigit() and 'Typo=Yes' not in row[5] and lexical.valid_surface(row[2]):
            lemma_usage[lexical.key(row[2]), row[3]] += 1
            form_usage[lexical.key(row[1]), lexical.key(row[2]), row[3]] += 1
    upos = {'noun': {'NOUN'}, 'verb': {'VERB', 'AUX'}, 'adjective': {'ADJ'}, 'adverb': {'ADV'},
        'pronoun': {'PRON'}, 'determiner': {'DET'}, 'preposition': {'ADP'},
        'conjunction': {'CCONJ', 'SCONJ'}, 'interjection': {'INTJ'}}
    grouped, withheld, observed = {}, [], Counter()
    existing_keys = {lexical.key(surface) for surface in existing}

    def add(entry, proof, facets, priority):
        surface = entry['surface']
        observed.update(facets)
        reason = ('unsupported-format' if not lexical.valid_surface(surface) or not lexical.valid_surface(entry['lemma']) else
            'base-exclusion' if lexical.key(surface) in excluded or lexical.key(entry['lemma']) in excluded else
            'already-registered-spelling' if surface in existing else
            'unsupported-categories' if not set(entry['categories'].split(',')) <= categories else None)
        if reason:
            withheld.append(dict(surface=surface, lemma=entry['lemma'], facets=sorted(facets), reason=reason, proof=proof))
            return
        identifier = hashlib.sha256(surface.encode()).hexdigest()[:24]
        item = grouped.setdefault(surface, dict(id=identifier, surface=surface, entries=[], proofs=[], facets=[], priority=priority,
            facetPriorities={}))
        if entry not in item['entries']:
            item['entries'].append(entry)
        proof = dict(proof, id=hashlib.sha256(json.dumps(proof, sort_keys=True).encode()).hexdigest()[:24])
        if proof not in item['proofs']:
            item['proofs'].append(proof)
        item['facets'] = sorted(set(item['facets']) | set(facets))
        item['priority'] = min(item['priority'], priority)
        for facet in facets:
            item['facetPriorities'][facet] = min(priority, item['facetPriorities'].get(facet, priority))

    connection = sqlite3.connect(esdb.resolve().joinpath('esdb.db').as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in connection.execute("""select e.*, min(s.size) as size
            from scowl_ s join entries e using(word_id)
            where s.size<=60 and s.variant_level<=2 and s.group_rank not in ('@','~')
              and s.entry_rank not in ('@','~') and s.usage_note=''
              and s.tag not in ('[ukfreq]','[stale]','[ukacd]','[plurals]','[-]')
            group by e.word_id order by size,e.word_id""")]
    finally:
        connection.close()
    paradigms = defaultdict(set)
    for row in rows:
        paradigms[row['lemma_id']].add(row['pos'])
    for row in rows:
        person = row['pos_class'] in {'person', 'surname'} and row['base_pos'] == 'n'
        if person and row['pos'] not in {'n0', 'm0'}:
            continue  # Names are collected as attested head spellings, without filling the batch with possessives.
        basic = lexical.key(row['lemma']) in common
        daily = bool(wn.get(lexical.key(row['lemma']))) and usage[lexical.key(row['word'])] >= 2
        if not person and (row['pos_class'] not in {'', 'upper'} or not (basic or daily)):
            continue
        for role in sorted(roles_for(row['base_pos'], row['pos'])):
            members = categories_for(row, role, paradigms[row['lemma_id']]) | {'domain_daily'}
            if row['base_pos'] == 'n' and row['word'] in {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                    'Saturday', 'Sunday', 'January', 'February', 'March', 'April', 'May', 'June', 'July',
                    'August', 'September', 'October', 'November', 'December'}:
                members.add('noun_proper')
            facets = {'person'} if person else ({'basic'} if basic else {'daily'})
            if row['word'] != row['lemma'] and not person:
                facets.add('inflection')
                witnesses = sum(lemma_usage[lexical.key(row['lemma']), pos] for pos in upos.get(role, set()))
                form_witnesses = sum(form_usage[lexical.key(row['word']), lexical.key(row['lemma']), pos]
                    for pos in upos.get(role, set()))
                if form_witnesses < 2:
                    withheld.append(dict(surface=row['word'], lemma=row['lemma'], facets=sorted(facets),
                        reason='inflection-needs-usage-review', proof=dict(source='dictionary_esdb',
                            wordId=row['word_id'], lemmaId=row['lemma_id'], pos=row['pos'],
                            lemmaPosOccurrences=witnesses, formPosOccurrences=form_witnesses,
                            observedOccurrences=usage[lexical.key(row['word'])])))
                    continue
            if row['word'] != lexical.key(row['word']) and lexical.key(row['word']) in existing_keys:
                facets.add('orthography')
            entry = dict(zip(lexical.FIELDS, [f"esdb-{row['group_id']}-{row['lemma_id']}-{role}", row['lemma'], row['word'],
                ','.join(sorted(members)), 'daily', ESDB_URL, f"esdb:{row['word_id']}:{row['lemma_id']}:{row['pos']}"]))
            add(entry, dict(source='dictionary_esdb', sourceSha256=pinned['esdb']['databaseSha256'],
                wordId=row['word_id'], lemmaId=row['lemma_id'], pos=row['pos'], posClass=row['pos_class'],
                size=row['size'], basicHeadword=basic, observedOccurrences=usage[lexical.key(row['word'])],
                lemmaPosOccurrences=sum(lemma_usage[lexical.key(row['lemma']), pos] for pos in upos.get(role, set())),
                formPosOccurrences=sum(form_usage[lexical.key(row['word']), lexical.key(row['lemma']), pos]
                    for pos in upos.get(role, set())),
                licenseId='LicenseRef-ESDB'), facets, (row['size'], -usage[lexical.key(row['word'])], row['word']))

    parser = Glossary()
    parser.feed((directory / 'mdn-glossary.html').read_text(encoding='utf-8'))
    require(len(parser.labels) >= 100, 'Glossary extraction incomplete')
    for label, url, line in sorted(set(parser.labels)):
        entry = dict(zip(lexical.FIELDS, ['mdn-' + hashlib.sha256(url.encode()).hexdigest()[:20], label, label,
            'domain_technology', 'technology', url, 'mdn-glossary:' + str(line)]))
        add(entry, dict(source='dictionary_mdn', sourceSha256=manifest['files']['mdn-glossary.html']['sha256'],
            label=label, url=url, line=line, licenseId='CC-BY-SA-2.5-or-later'), {'technology'}, (0, 0, label))
    casks = json.loads((directory / 'cask.json').read_text())
    analytics = json.loads((directory / 'cask-analytics.json').read_text())
    ranks = {record['cask']: int(record['number']) for record in analytics['items']}
    for record in casks:
        if record.get('disabled') or record.get('deprecated'):
            continue
        for label in record['name']:
            entry = dict(zip(lexical.FIELDS, ['cask-' + hashlib.sha256((record['token'] + '\0' + label).encode()).hexdigest()[:20],
                label, label, 'domain_technology,name_product,noun,noun_proper', 'technology',
                'https://formulae.brew.sh/cask/' + record['token'], 'homebrew-cask:' + record['token']]))
            add(entry, dict(source='dictionary_homebrew', sourceSha256=manifest['files']['cask.json']['sha256'],
                token=record['token'], label=label, field='name', revision=record['tap_git_head'],
                licenseId='BSD-2-Clause', catalogRank=ranks.get(record['token']),
                rankSnapshotSha256=manifest['files']['cask-analytics.json']['sha256'],
                rankStart=analytics['start_date'], rankEnd=analytics['end_date']), {'product', 'technology'},
                (1, ranks.get(record['token'], 1000000), label))
    candidates = sorted(grouped.values(), key=lambda item: item['priority'])
    for item in candidates:
        item['entries'].sort(key=lambda e: (e['surface'], e['lexeme_id']))
        item['proofs'].sort(key=lambda p: p['id'])
    notices = [dict(name='DICTIONARY-' + name.replace('.md', '.txt'), path=str(directory / name), sha256=sha(directory / name))
        for name in ['mdn-license.md', 'homebrew-license.txt', 'homebrew-analytics-license.txt',
            'NGSL-DICTIONARY-NOTICE.txt', 'MDN-DICTIONARY-NOTICE.txt']]
    if audit_dir:
        import vocabulary_harness as h
        h.write_lines(audit_dir / 'dictionary-withheld.jsonl', withheld)
    return candidates, dict(pinned, dictionaryCatalog=dict(manifestSha256=sha(directory / 'dictionary-sources.json'),
        manifest=manifest, observedFacetRows=dict(observed), withheldReasons=dict(Counter(r['reason'] for r in withheld)),
        availableFacets=dict(Counter(f for c in candidates for f in c['facets'])),
        scope='Exact source spellings and ESDB paradigms only; no typo/ranking behavior, generated morphology, or current product availability claim'),
        references=dict(notices=notices))


def balanced(candidates, limit):
    buckets = {facet: iter(sorted([c for c in candidates if facet in c['facets']],
        key=lambda c: c.get('facetPriorities', {}).get(facet, c['priority']))) for facet in FACETS}
    selected, seen = [], set()
    quota = (limit + len(FACETS) - 1) // len(FACETS)
    taken = Counter()
    while buckets and len(selected) < limit:
        for facet in list(buckets):
            if taken[facet] >= quota:
                del buckets[facet]
                continue
            candidate = next((c for c in buckets[facet] if c['id'] not in seen), None)
            if candidate is None:
                del buckets[facet]
            else:
                selected.append(candidate)
                seen.add(candidate['id'])
                taken[facet] += 1
                if len(selected) == limit:
                    break
    return selected


def adopt(args):
    import vocabulary_harness as h
    directory = h.external(args.work_dir)
    with h.lock(directory):
        config, connection = h.state(directory)
        try:
            require(config.get('sourceProfile') == PROFILE, 'Not a dictionary catalog run')
            require(h.asset_hashes(Path(config['assets'])) == config['assetHashes'], 'Baseline assets changed')
            with (directory / 'base-inputs/grammar/categories.tsv').open() as stream:
                categories = {r['category'] for r in csv.DictReader(stream, delimiter='\t')}
            with (directory / 'base-inputs/decisions.tsv').open() as stream:
                excluded = {lexical.key(r['surface']) for r in csv.DictReader(stream, delimiter='\t') if r['decision'] == 'exclude'}
            fresh, source_manifest = collect(args.source_dir.resolve(), args.esdb_dir.resolve(), categories,
                {r['surface'] for r in h.json_lines(directory / 'baseline.jsonl')}, excluded)
            require(source_manifest == config['sources'], 'Dictionary source snapshot changed')
            by_id = {c['id']: c for c in fresh}
            rows = connection.execute('select * from candidates where decision is null order by position').fetchall()
            decisions = []
            for row in rows:
                candidate = json.loads(row['payload'])
                require(json.loads(json.dumps(by_id.get(candidate['id']))) == candidate, 'Candidate differs from source extraction')
                proposal = json.loads(row['proposal']) if row['proposal'] else None
                action = 'include' if proposal is None or proposal['decision'] == 'include' else 'defer'
                decisions.append(dict(id=candidate['id'], decision=action,
                    reason=PROFILE + ': exact frozen source record and license verified; automated source adoption, not human review.',
                    proofIds=[p['id'] for p in candidate['proofs']]))
            h.validate_decisions(decisions, [json.loads(row['payload']) for row in rows])
            if decisions:
                log = directory / ('dictionary-decisions-' + config['candidatesSha256'][:16] + '.jsonl')
                if log.exists():
                    require(h.json_lines(log) == decisions, 'Existing dictionary source decisions changed')
                else:
                    h.write_lines(log, decisions)
            with connection:
                for item in decisions:
                    connection.execute('update candidates set decision=?,result=? where id=?',
                        (item['decision'], json.dumps(item, sort_keys=True), item['id']))
            return dict(adopted=sum(d['decision'] == 'include' for d in decisions), deferred=sum(d['decision'] == 'defer' for d in decisions),
                apiCalls=0, policy=PROFILE)
        finally:
            connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['fetch', 'adopt'])
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--esdb-dir', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path)
    args = parser.parse_args()
    if args.command == 'fetch':
        fetch(args.source_dir, args.esdb_dir)
    else:
        require(args.work_dir is not None, 'adopt requires --work-dir')
        print(json.dumps(adopt(args), sort_keys=True))
