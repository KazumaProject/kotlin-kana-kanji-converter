"""Full-document literal reading search and auditable bulk research rounds.

Two strategies are distinct: direct article/subject lookup, and whole-corpus
explicit name/reading bindings (including names mentioned in other articles).
Exact-title absence alone never proves completion. This helper makes no quality
decision and never clears acquisition/parse failures or invents pronunciations.
"""
import collections
import hashlib
import html
import re
from functools import lru_cache

import worker as w
from batch_research import name_key

VERSION = 2
STRATEGIES = {
    'subject': 'Every main-namespace article title and explicitly stated primary name; direct subject reading bindings',
    'named-binding': 'Every main-namespace article full text; explicit whole-name parenthetical, ruby, and name/reading fields',
}


def full_body_reading_bindings(text):
    """Enumerate explicit pairs over the full document, with whole-name bounds.

    This extends the online parser's first-12,000-character parenthetical search.
    It does not search a candidate as a substring or infer a name from a reading.
    """
    if not isinstance(text, str):
        raise ValueError('Article content must be decoded text')
    kana = r'([ぁ-ゖァ-ヶー 　・]+(?:[、,][ぁ-ゖァ-ヶー 　・]+)*)(?=[、,)）])'
    marked = r"(?:[「『〈《])?'''([^\n]{1,256}?)'''[」』〉》]?\s*[（(]" + kana
    tuples = [(m[1], m[2], m[0]) for m in re.finditer(marked, text)]
    plain = html.unescape(re.sub(r'<[^>]+>', '', re.sub(marked, ' ', text))).replace("''", '')
    names = r"(?<![\w々〆])(?:[「『〈《])?([\w々〆ー・'’=＝\- 　]{1,256})[」』〉》]?\s*[（(]" + kana
    tuples.extend((m[1].strip(), m[2], m[0]) for m in re.finditer(names, plain))
    seen = set()
    for name, readings, quote in tuples:
        name=name.strip()
        for opening,closing in (('「','」'),('『','』'),('〈','〉'),('《','》')):
            if name.startswith(opening) and name.endswith(closing): name=name[1:-1]
        for n, y in enumerate(re.split('[、,]', readings)):
            if n:
                y = re.sub(r'^(?:または|もしくは)', '', y.strip())
            item = (name, y.replace(' ', '').replace('　', '').replace('・', ''), quote)
            if item not in seen:
                seen.add(item); yield item
    for item in w.explicit_reading_bindings(text):
        if item not in seen:
            seen.add(item); yield item


@lru_cache(maxsize=8)
def page_scope(title, content):
    """Calculate a page's subject/alias scope once, even with many matched names."""
    lead = re.split(r'\n\s*==', content, maxsplit=1)[0]
    first = re.search(r"'''([^'\n]+)'''", w.wiki_lead(content))
    primary = first[1] if first else title
    accepted = set()
    for match in re.finditer(r'\{\{[^{}]+\}\}', lead):
        names = re.findall(r'\|\s*(?:名前|名称|name)\s*=\s*([^\n|}]+)', match[0], re.I)
        if len(names) != 1:
            continue
        clean = lambda value: html.unescape(re.sub('<[^>]+>', '', value)).replace("'''", '').strip()
        declared = clean(names[0])
        if not (w.same_name(declared, title) or w.same_name(declared, primary)):
            continue
        aliases = re.findall(r'\|\s*(?:別名|芸名|名義|通称)\s*=\s*([^\n|}]+)', match[0])
        accepted.update(name_key(clean(alias)) for alias in aliases)
    return primary, frozenset(accepted)


def alias_of_primary_subject(title, content, surface):
    """Accept aliases only in a flat, explicitly subject-bound lead template.

    Another person's infobox or a later quoted template cannot attach that
    person's pronunciation/category to this article's subject. Ambiguous and
    nested fields remain unresolved.
    """
    return name_key(surface) in page_scope(title, content)[1]


def binding_target(title, content, surface, qid=None):
    subject = qid or title
    if w.same_name(title, surface):
        return subject, 'primary-name'
    primary, aliases = page_scope(title, content)
    if w.same_name(primary, surface):
        return subject, 'primary-name'
    if name_key(surface) in aliases:
        return subject, 'declared-primary-alias'
    return title + '#mentioned-name:' + surface, 'mentioned-name'


def cohort_hash(rows):
    """Rows must be ordered by ID; bind the searched readings and spellings too."""
    h = hashlib.sha256(); previous = None; count = 0
    for row in rows:
        cid = row['id']
        if previous is not None and cid <= previous:
            raise ValueError('Research cohort must have unique increasing candidate IDs')
        h.update(w.canonical([cid, row['reading'], row['surface']]).encode()); h.update(b'\n')
        previous = cid; count += 1
    if not count:
        raise ValueError('Empty research cohort')
    return h.hexdigest(), count


class CorpusRoundTracker:
    """Observe both searches as they execute, then certify only a complete scan.

    The caller must invoke both observation methods for every main-namespace
    article, including zero-match articles, and confirm the XML reader reached
    EOF with the official compressed source checksum verified. Unvisited pages,
    incomplete runs, and parser errors cannot produce completed rounds.
    """
    def __init__(self, cohort_sha256, candidate_count, corpus_sha256):
        if not all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) for v in (cohort_sha256, corpus_sha256)) or candidate_count <= 0:
            raise ValueError('Pinned cohort and corpus hashes are required')
        self.cohort = cohort_sha256; self.candidates = candidate_count; self.corpus = corpus_sha256
        self.counts = collections.Counter(); self.errors = []
        self.transcripts = {key: hashlib.sha256() for key in STRATEGIES}

    def observe(self, strategy, title, revision, content, *, matches=0):
        if strategy not in STRATEGIES or not isinstance(title, str) or not isinstance(content, str) or revision is None:
            raise ValueError('Invalid completed article search')
        identity = w.canonical([title, str(revision), w.digest(content)])
        self.transcripts[strategy].update(identity.encode()); self.transcripts[strategy].update(b'\n')
        self.counts[strategy + 'Articles'] += 1
        self.counts[strategy + 'Matches'] += matches

    def failure(self, title, error):
        self.errors.append({'title': title, 'error': str(error)})

    def finish(self, *, eof, source_checksum_verified, main_articles_scanned):
        if not eof or not source_checksum_verified or self.errors:
            raise ValueError('Incomplete/failed corpus research cannot complete rounds')
        if main_articles_scanned <= 0 or any(self.counts[key + 'Articles'] != main_articles_scanned for key in STRATEGIES):
            raise ValueError('Both strategies must inspect every main-namespace article')
        transcripts = {key: h.hexdigest() for key, h in self.transcripts.items()}
        if len(set(transcripts.values())) != 1:
            raise ValueError('The two strategies did not inspect the same complete article stream')
        rounds = [{'round': n, 'strategy': key, 'strategyDescription': description,
                   'strategySha256': w.digest(w.canonical([VERSION, key, description])),
                   'articleTranscriptSha256': transcripts[key], 'articles': main_articles_scanned,
                   'matchedCandidates': self.counts[key + 'Matches']}
                  for n, (key, description) in enumerate(STRATEGIES.items(), 1)]
        return {'schemaVersion': VERSION, 'cohortSha256': self.cohort, 'candidateCount': self.candidates,
                'corpusSha256': self.corpus, 'sourceChecksumVerified': True, 'eof': True,
                'errors': [], 'rounds': rounds,
                'interpretation': 'Two completed bounded source searches; missing evidence is not proof of a wrong word'}


def record_completed_rounds(db, proof):
    """Bind a completed full-input corpus search without making dispositions.

    This requires that the frozen cohort was all existing input candidates, not
    a partial export. Failed candidate states/errors survive, with rounds still
    pending; no missing-evidence case is silently changed into non-distribution.
    """
    actual, count = cohort_hash(db.execute('SELECT id,reading,surface FROM candidates ORDER BY id'))
    if actual != proof.get('cohortSha256') or count != proof.get('candidateCount'):
        raise ValueError('Completed source search belongs to another candidate cohort')
    rounds = proof.get('rounds', [])
    if (proof.get('schemaVersion') != VERSION or proof.get('eof') is not True or
        proof.get('sourceChecksumVerified') is not True or proof.get('errors') != [] or len(rounds) != 2):
        raise ValueError('Incomplete source research proof')
    if not isinstance(proof.get('corpusSha256'), str) or not re.fullmatch('[0-9a-f]{64}', proof['corpusSha256']):
        raise ValueError('Missing corpus checksum')
    for n, (key, description) in enumerate(STRATEGIES.items(), 1):
        item = rounds[n - 1]
        if (item.get('round') != n or item.get('strategy') != key or
            item.get('strategySha256') != w.digest(w.canonical([VERSION, key, description])) or
            not isinstance(item.get('articles'), int) or item['articles'] <= 0 or
            not isinstance(item.get('articleTranscriptSha256'), str) or not re.fullmatch('[0-9a-f]{64}', item['articleTranscriptSha256'])):
            raise ValueError('Unrecognized/unfinished source search strategy')
    if (rounds[0]['articles'] != rounds[1]['articles'] or
        rounds[0]['articleTranscriptSha256'] != rounds[1]['articleTranscriptSha256']):
        raise ValueError('Source search article coverage differs')
    key = w.digest(w.canonical(proof))
    db.execute('CREATE TABLE IF NOT EXISTS completed_source_searches(id TEXT PRIMARY KEY,cohort_sha256 TEXT,corpus_sha256 TEXT,proof TEXT)')
    db.execute('INSERT OR IGNORE INTO completed_source_searches VALUES(?,?,?,?)',
               (key, actual, proof['corpusSha256'], w.canonical(proof)))
    changed = db.execute("UPDATE candidates SET research_round=MAX(research_round,2) WHERE error IS NULL AND state NOT IN ('error','blocked') AND research_round<2").rowcount
    w.info(db, 'completedBulkSourceSearch', {'proofSha256': key, 'source': proof['corpusSha256'],
                                          'cohortSha256': actual, 'candidates': count, 'updated': changed})
    return {'proofSha256': key, 'candidates': count, 'updated': changed, 'qualityDecisionsMade': 0}
