"""Pinned lexical leads for the vocabulary harness; no model or network calls."""
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tarfile
import tempfile
import urllib.request

from extend_lexicon import categories_for, roles_for
from prepare_esdb import REVISION, URL as ESDB_URL, prepare as prepare_esdb
from replay_source import DEFAULT_MANIFEST, sha

SUPPLEMENT = DEFAULT_MANIFEST.parent.parent / 'supplement'
FIELDS = ('lexeme_id', 'lemma', 'surface', 'categories', 'domain', 'evidence', 'source_ref')
SURFACE = re.compile(r"[A-Za-z0-9]+(?:[ '’./-][A-Za-z0-9]+)*")
DOMAINS = {'daily', 'business', 'technology', 'travel'}
RESTRICTED = re.compile(r'\b(?:archaic|obsolete|offensive|vulgar|derogatory|ethnic slur)\b', re.I)


def key(text):
    # Same contract as grammar.lookupKey; accepted supplement spellings are ASCII
    # apart from the explicitly supported curly apostrophe.
    return text.replace('’', "'").lower()


def valid_surface(text):
    return isinstance(text, str) and 1 <= len(text) <= 64 and bool(SURFACE.fullmatch(text))


def read_entries(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        if reader.fieldnames != list(FIELDS):
            raise ValueError('Invalid supplement header')
        return list(reader)


def entry_files(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    parts=sorted(n for n in manifest['files'] if re.fullmatch(r'entries-[0-9]{4}\.tsv',n))
    if parts != [f'entries-{i:04}.tsv' for i in range(1,len(parts)+1)]:
        raise ValueError('Missing/reordered supplement entry shard')
    return [directory/n for n in ['entries.tsv',*parts]]


def read_supplement_entries(directory):
    return [row for path in entry_files(directory) for row in read_entries(path)]


def write_table_shards(directory,stem,fields,rows,max_bytes=16*1024*1024,plain_first=False):
    """Bound Git/review file size without bounding the acquired vocabulary."""
    directory.mkdir(parents=True,exist_ok=True)
    def encoded(row):
        buffer=io.StringIO();writer=csv.DictWriter(buffer,fieldnames=fields,delimiter='\t',lineterminator='\n')
        if row is None:writer.writeheader()
        else:writer.writerow(row)
        return buffer.getvalue().encode('utf-8')
    header=encoded(None);stream=None;size=0;index=0;files={}
    try:
        for row in rows:
            body=encoded(row)
            if len(header)+len(body)>max_bytes:raise ValueError('A dictionary row exceeds the shard size')
            if stream is None or size+len(body)>max_bytes:
                if stream:stream.close()
                name=stem+'.tsv' if plain_first and index==0 else f'{stem}-{index:04}.tsv'
                stream=(directory/name).open('wb');stream.write(header);size=len(header)
                files[name]=dict(rows=0);index+=1
            stream.write(body);size+=len(body);files[name]['rows']+=1
        if stream is None:
            name=stem+'.tsv' if plain_first else stem+'-0000.tsv'
            (directory/name).write_bytes(header);files[name]=dict(rows=0)
    finally:
        if stream:stream.close()
    for name,value in files.items():value['sha256']=sha(directory/name)
    return files


def fetch_sources(directory, esdb):
    """Fetch only pinned public inputs, keeping downloads and the source checkout external."""
    pins = json.loads((SUPPLEMENT / 'manifest.json').read_text())['sources']
    directory.mkdir(parents=True, exist_ok=True)
    for name, record in pins.items():
        if name == 'esdb' or 'sha256' not in record:
            continue
        destination = directory / name
        if destination.exists():
            if sha(destination) != record['sha256']:
                raise ValueError('Cached source changed: ' + name)
            continue
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                with urllib.request.urlopen(record['url'], timeout=60) as response:
                    remaining = record['bytes']
                    while block := response.read(min(1024 * 1024, remaining + 1)):
                        remaining -= len(block)
                        if remaining < 0:
                            raise ValueError('Downloaded source exceeds its pinned byte length')
                        stream.write(block)
                stream.flush()
                if remaining or sha(temporary) != record['sha256']:
                    raise ValueError('Downloaded source differs from pin: ' + name)
                temporary.rename(destination)
            finally:
                temporary.unlink(missing_ok=True)
    if not esdb.exists():
        esdb.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.esdb-source-', dir=esdb.parent) as temporary:
            checkout = Path(temporary)
            for command in [['git', 'init', '-q'], ['git', 'remote', 'add', 'origin', 'https://github.com/en-wl/wordlist.git'],
                            ['git', 'fetch', '-q', '--depth=1', 'origin', REVISION], ['git', 'checkout', '-q', '--detach', 'FETCH_HEAD']]:
                subprocess.run(command, cwd=checkout, check=True)
            prepare_esdb(checkout, esdb)


def source_files(directory, esdb):
    pins = json.loads((SUPPLEMENT / 'manifest.json').read_text())['sources']
    names = ['ngsl.csv', 'bsl.csv', 'bsl-stats.csv', 'cmudict.dict',
             'wordnet.tar.gz', 'ewt-train.conllu', 'gum-train.conllu']
    records = {}
    for name in names:
        path = directory / name
        if path.is_symlink() or sha(path) != pins[name]['sha256']:
            raise ValueError('Pinned lexical source changed: ' + name)
        records[name] = pins[name]
    manifest = json.loads((esdb / 'manifest.json').read_text())
    if (manifest['revision'] != REVISION or
            manifest['recipe'] != 'combine.py create-db --raw; omit data/coca_llm merge' or
            manifest['databaseSha256'] != pins['esdb']['databaseSha256'] or
            sha(esdb / 'esdb.db') != manifest['databaseSha256']):
        raise ValueError('Unverified ESDB database')
    for name, checksum in manifest['notices'].items():
        if Path(name).name != name or sha(esdb / name) != checksum:
            raise ValueError('Changed ESDB notice')
    records['esdb'] = pins['esdb']
    return records


def corpus_words(path, corpus):
    """Training data only; count observed forms, never invent inflections."""
    counts = defaultdict(Counter)
    for block in path.read_text(encoding='utf-8').split('\n\n'):
        sid = next((line.partition(' = ')[2] for line in block.splitlines()
                    if line.startswith('# sent_id = ')), '')
        if corpus == 'ewt':
            domain = 'business' if sid.startswith('email-') else 'daily'
        elif sid.startswith('GUM_voyage_'):
            domain = 'travel'
        elif sid.startswith(('GUM_conversation_', 'GUM_vlog_', 'GUM_reddit_', 'GUM_whow_')):
            domain = 'daily'
        else:
            continue
        for line in block.splitlines():
            row = line.split('\t')
            if (len(row) == 10 and row[0].isdigit() and row[3] in {'NOUN', 'VERB', 'ADJ', 'ADV'}
                    and 'Typo=Yes' not in row[5] and valid_surface(row[1])):
                counts[domain][key(row[1])] += 1
    return counts


def wordnet(path):
    records = defaultdict(list)
    with tarfile.open(path) as archive:
        for suffix, role in [('noun', 'noun'), ('verb', 'verb'), ('adj', 'adjective'), ('adv', 'adverb')]:
            for line in io.TextIOWrapper(archive.extractfile('WordNet-3.0/dict/data.' + suffix), encoding='ascii'):
                if not line[:1].isdigit():
                    continue
                content, _, gloss = line.partition('|')
                if RESTRICTED.search(gloss):
                    continue  # Only this sense is withheld, not unrelated senses.
                fields = content.split()
                for index in range(int(fields[3], 16)):
                    surface = fields[4 + index * 2].replace('_', ' ')
                    if valid_surface(surface):
                        records[key(surface)].append((surface, role, fields[0]))
    return records


def collect(directory, esdb, categories, existing, excluded, references=None):
    sources = source_files(directory, esdb)
    wn = wordnet(directory / 'wordnet.tar.gz')
    ngsl, bsl = set(), set()
    for name, target in [('ngsl.csv', ngsl), ('bsl.csv', bsl)]:
        with (directory / name).open(encoding='utf-8-sig', newline='') as stream:
            target.update(key(row[0].strip()) for row in csv.reader(stream)
                          if row and valid_surface(row[0].strip()))
    usage = defaultdict(Counter)
    for corpus in ['ewt', 'gum']:
        for domain, counts in corpus_words(directory / (corpus + '-train.conllu'), corpus).items():
            usage[domain].update(counts)
    cmu = {key(line.split()[0].split('(')[0]) for line in
           (directory / 'cmudict.dict').read_text().splitlines() if line and not line.startswith(';')}
    grouped = {}

    def add(entry, proof, rank):
        surface = entry['surface']
        normalized = key(surface)
        memberships = set(entry['categories'].split(','))
        if (not valid_surface(surface) or not valid_surface(entry['lemma']) or
                normalized in existing or normalized in excluded or not memberships <= categories):
            return
        identity = hashlib.sha256(normalized.encode()).hexdigest()[:24]
        candidate = grouped.setdefault(normalized, dict(id=identity, surface=surface, entries=[], proofs=[], priority=rank))
        if candidate['surface'] != surface:
            return  # No unsupported case conflation or replacement of canonical spelling.
        if entry not in candidate['entries']:
            candidate['entries'].append(entry)
        proof['id'] = hashlib.sha256(json.dumps(proof, sort_keys=True).encode()).hexdigest()[:24]
        if proof not in candidate['proofs']:
            candidate['proofs'].append(proof)
        candidate['priority'] = min(rank, candidate['priority'])

    connection = sqlite3.connect((esdb / 'esdb.db').resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in connection.execute("""
            select e.*, min(s.size) as size from scowl_ s join entries e using(word_id)
            where s.size<=70 and s.variant_level<=2 and s.group_rank not in ('@','~')
              and s.entry_rank not in ('@','~') and s.usage_note=''
              and s.tag not in ('[ukfreq]','[stale]','[ukacd]','[plurals]','[-]')
              and e.base_pos in ('n','v','aj','av','n_v','aj_av') group by e.word_id
            order by size, e.word_id"""
        )]
    finally:
        connection.close()
    paradigms = defaultdict(set)
    for row in rows:
        paradigms[row['lemma_id']].add(row['pos'])
    for row in rows:
        surface, lemma = row['word'], row['lemma']
        if (not valid_surface(surface) or row['pos_class'] in {'person', 'place', 'surname', 'name', 'upper'}
                or key(lemma) in excluded):
            continue
        domain = ('business' if key(lemma) in bsl or usage['business'][key(surface)] >= 2 else
                  'travel' if usage['travel'][key(surface)] >= 2 else 'daily')
        for role in sorted(roles_for(row['base_pos'], row['pos'])):
            support = [offset for _, wn_role, offset in wn[key(lemma)] if wn_role == role]
            memberships = (categories_for(row, role, paradigms[row['lemma_id']]) & categories) | {'domain_' + domain}
            record = dict(zip(FIELDS, [f"esdb-{row['group_id']}-{row['lemma_id']}-{role}", lemma, surface,
                ','.join(sorted(memberships)), domain, ESDB_URL,
                f"esdb:{row['word_id']}:{row['lemma_id']}:{row['pos']}:size{row['size']}"]))
            proof = dict(source='esdb', url=ESDB_URL, sourceSha256=sources['esdb']['databaseSha256'],
                         wordId=row['word_id'], lemmaId=row['lemma_id'], pos=row['pos'],
                         size=row['size'], wordnetOffsets=support, cmudict=key(surface) in cmu,
                         trainingOccurrences=sum(counts[key(surface)] for counts in usage.values()),
                         listedHeadword=key(lemma) in ngsl | bsl)
            # Do not fill a vocabulary-expansion pilot with possessives of already
            # covered heads just because those lemmas appear on a common-word list.
            possessive = row['pos'] in {'np', 'nsp', 'nssp'}
            tier = (6 if possessive else 0 if key(surface) in ngsl | bsl else
                    1 if proof['trainingOccurrences'] >= 2 else
                    2 if surface == lemma and row['size'] <= 60 and support else
                    4 if row['size'] <= 60 and support and proof['cmudict'] else 5)
            rank = (tier,
                    row['size'], -proof['trainingOccurrences'], key(surface))
            add(record, proof, rank)
    for normalized, records in sorted(wn.items()):
        for surface, role, offset in records:
            if ' ' not in surface or len(surface.split()) > 4:
                continue
            domain = 'business' if normalized in bsl else 'daily'
            record = dict(zip(FIELDS, ['wn-' + role + '-' + offset + '-' + hashlib.sha256(normalized.encode()).hexdigest()[:12],
                surface, surface, ','.join(sorted({role, 'phrase', 'domain_' + domain})), domain,
                'https://wordnet.princeton.edu/', 'wordnet-3.0:' + role + ':' + offset]))
            add(record, dict(source='wordnet', url=record['evidence'], sourceSha256=sources['wordnet.tar.gz']['sha256'],
                             synset=offset, role=role), (3, 0, 0, normalized))
    if references:
        reference_manifest = json.loads(references.read_text(encoding='utf-8'))
        for reference in reference_manifest['documents']:
            path = (references.parent / reference['file']).resolve()
            if sha(path) != reference['sha256'] or not reference['url'].startswith('https://'):
                raise ValueError('Changed reference document')
            text = path.read_text(encoding='utf-8')
            if not reference.get('notices'):
                raise ValueError('Reviewed references require redistributable source notices')
            for notice in reference['notices']:
                if (not re.fullmatch(r'[A-Za-z0-9_.-]+', notice['name']) or
                        sha((references.parent / notice['file']).resolve()) != notice['sha256']):
                    raise ValueError('Invalid or changed reference notice')
            for entry in reference['entries']:
                if (set(entry) != set(FIELDS) or entry['evidence'] != reference['url'] or
                        entry['domain'] not in DOMAINS or not re.search(
                            r'(?<![A-Za-z0-9])' + re.escape(entry['surface']) + r'(?![A-Za-z0-9])', text)):
                    raise ValueError('Reference entry lacks a literal attestation')
                add(entry, dict(source='reviewed_reference', url=reference['url'], sourceSha256=reference['sha256']),
                    (1, 0, 0, key(entry['surface'])))
        sources['references'] = {'sha256': sha(references), 'documents': [
            {k: r[k] for k in ('url', 'sha256')} for r in reference_manifest['documents']],
            'notices': [dict(name=n['name'], sha256=n['sha256'], path=str((references.parent / n['file']).resolve()))
                        for r in reference_manifest['documents'] for n in r['notices']]}
    result = sorted(grouped.values(), key=lambda item: item['priority'])
    for item in result:
        item['entries'].sort(key=lambda entry: (entry['surface'], entry['lexeme_id']))
        item['proofs'].sort(key=lambda proof: proof['id'])
    return result, sources
