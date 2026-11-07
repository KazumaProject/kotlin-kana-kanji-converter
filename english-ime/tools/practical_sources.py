"""Licensed, pinned inputs for a basic-English IME diagnostic (no model calls)."""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import tempfile
import urllib.request

from replay_source import sha, require
from vocabulary_sources import key

CC4 = 'https://creativecommons.org/licenses/by-sa/4.0/'
CC3 = 'https://creativecommons.org/licenses/by-sa/3.0/'
REVISION = 'b53e95197f7c799674c785028a182e2dfd1df881'
RAW = 'https://raw.githubusercontent.com/codespell-project/codespell/' + REVISION + '/'
GENERAL = 'https://www.newgeneralservicelist.com/new-general-service-list'
SPOKEN = 'https://www.newgeneralservicelist.com/ngsl-spoken'
PINS = {
    'ngsl-stats.csv': dict(url='https://www.newgeneralservicelist.com/s/NGSL_12_stats.csv',
        sha256='2098bab8955a120a9766c6282a51d7d578c6cb0a7d946600d2ffb73ba25a0b44', bytes=62566,
        title='NGSL 1.2 basic statistics (April 2023)', attribution='Browne, C., Culligan, B., and Phillips, J.',
        license='CC-BY-SA-4.0', licenseUrl=CC4, licenseEvidence=GENERAL, kind='general', rows=2809),
    'ngsl-spoken-stats.csv': dict(url='https://www.newgeneralservicelist.com/s/NGSL-Spoken_12_stats.csv',
        sha256='07708940c50a07cac4f507fd1e87bdd50081d7b87713a66a99beb3c8c4d11ac8', bytes=17394,
        title='NGSL-Spoken 1.2 basic statistics (October 2017)', attribution='Browne, C., and Culligan, B.',
        license='CC-BY-SA-4.0', licenseUrl=CC4, licenseEvidence=SPOKEN, kind='spoken', rows=721),
    'ngsl-supplementary.csv': dict(url='https://www.newgeneralservicelist.com/s/SUP_lemmatized.csv',
        sha256='7bb4c76cbe43ae87240be4ac7ada370b9e1a0d9d631d8c4430138646965d03f6', bytes=1631,
        title='NGSL supplementary words', attribution='Browne, C., Culligan, B., and Phillips, J.',
        license='CC-BY-SA-4.0', licenseUrl=CC4, licenseEvidence=GENERAL, kind='supplementary', rows=52),
    'codespell.txt': dict(url=RAW + 'codespell_lib/data/dictionary.txt',
        sha256='154078a5877ef228b8c8b28d5c69991b053947ea8685717599044988e172ddd7', bytes=1499567,
        title='codespell spelling dictionary at ' + REVISION,
        attribution='codespell dictionary contributors; derived from English Wikipedia contributors',
        license='CC-BY-SA-3.0', licenseUrl=CC3, licenseEvidence=RAW + 'README.rst#license', kind='listed-typos'),
    'codespell-README.rst': dict(url=RAW + 'README.rst', bytes=15559,
        sha256='aeb6dbb0177013821bfb6920e0e101a68d6dc1688971189ee1ac97382d249dc2', kind='license-evidence'),
}
CHANGES = ('Select only first-column basic headwords, retain source capitalization, merge identical spellings and citations; '
    'make lowercase keyboard input, three-character prefixes, and deterministic synthetic edits. '
    'Select single unannotated codespell corrections corroborated by these basic headwords; '
    'exclude listed inputs that are themselves basic headwords; retain literal source corrections and line citations. '
    'Skip annotated/multiple corrections. No definitions, corpus sentences, codespell program or library code imported. '
    'The typo lists are labels, not an observed user-error frequency distribution or proof a spelling is universally invalid.')
WORD = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
# Project-authored scenarios, licensed with the MIT harness code. They are not corpus evidence.
PHRASES = ('thank you', 'good morning', 'see you', 'see you tomorrow', 'how are you',
    'please help', 'let me know', 'on my way', 'thank you for your help', 'have a nice day')
CONTRACTIONS = ("don't", "can't", "I'm", "it's", "I'll", "you're", "we're", "I've")
PRESERVE = ('form', 'from', 'then', 'than', 'its', "it's", 'I', 'Monday', 'Kazuma', 'abc123xyz')
NEIGHBOR = dict(zip('qwertyuiopasdfghjklzxcvbnm', 'wqwertyuio' + 'sasdfghjk' + 'xzxcvbn'))


def fetch(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for name, record in PINS.items():
        destination = directory / name
        if destination.exists():
            require(not destination.is_symlink() and sha(destination) == record['sha256'], 'Changed source: ' + name)
            continue
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                with urllib.request.urlopen(record['url'], timeout=45) as response:
                    remaining = record['bytes']
                    while block := response.read(min(1024 * 1024, remaining + 1)):
                        remaining -= len(block)
                        require(remaining >= 0, 'Oversized source: ' + name)
                        stream.write(block)
                stream.flush()
                require(not remaining and sha(temporary) == record['sha256'], 'Source differs from pin: ' + name)
                temporary.rename(destination)
            finally:
                temporary.unlink(missing_ok=True)


def verify(directory):
    for name, record in PINS.items():
        path = directory / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == record['bytes'] and
                sha(path) == record['sha256'], 'Missing or changed pinned source: ' + name)


def headwords(directory):
    words = defaultdict(list)
    for name, record in PINS.items():
        if 'rows' not in record:
            continue
        with (directory / name).open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.reader(stream))
        offset = 0 if record['kind'] == 'supplementary' else 1
        require(len(rows) - offset == record['rows'], 'Unexpected basic-list size')
        if offset:
            require(rows[0][0] == 'Lemma', 'Unexpected basic-list header')
        for line, row in enumerate(rows[offset:], offset + 1):
            require(row and WORD.fullmatch(row[0]), 'Unsupported basic headword')
            words[row[0]].append(dict(source=name, line=line, column=1))
    return dict(words)


def edits(word, known):
    """One example per operation; skip basic real-word collisions, without claiming nonwords."""
    if not word.isascii() or not word.isalpha() or not 4 <= len(word) <= 16:
        return
    positions = sorted(range(len(word)), key=lambda i: (abs(i - len(word) // 2), i))
    operations = {
        'deletion': lambda i: word[:i] + word[i + 1:],
        'insertion': lambda i: word[:i] + word[i] + word[i:],
        'substitution': lambda i: word[:i] + NEIGHBOR[word[i]] + word[i + 1:],
        'transposition': lambda i: word[:i] + word[i:i + 2][::-1] + word[i + 2:],
    }
    for operation, transform in operations.items():
        for position in positions:
            changed = transform(position)
            if changed != word and key(changed) not in known:
                yield operation, changed, position
                break


def cases_for(words, typo_lines):
    cases = []
    known = {key(word) for word in words}

    def add(text, expected, scenario, mode, refs, operation='', **extra):
        identity = [text, expected, scenario, operation]
        identifier = hashlib.sha256(json.dumps(identity, ensure_ascii=True).encode()).hexdigest()[:24]
        # Keep all input variants for one intended spelling in the same split.
        split = 'holdout' if int(hashlib.sha256(key(expected[0]).encode()).hexdigest()[:8], 16) % 5 == 0 else 'dev'
        cases.append(dict(id=identifier, input=text, expected=expected, scenario=scenario, mode=mode,
            operation=operation, split=split, proofs=refs, **extra))

    for word, proofs in sorted(words.items()):
        add(key(word), [word], 'basic-exact', 'exact', proofs)
        if len(word) > 3 and word.isalpha():
            add(key(word)[:3], [word], 'basic-prefix', 'prefix', proofs)
        for operation, text, position in edits(key(word), known):
            add(text, [word], 'typo-synthetic', 'exact', proofs, operation,
                editPosition=position, synthetic=True)

    by_key = defaultdict(list)
    for word in sorted(words):
        by_key[key(word)].append(word)
    for line, raw in enumerate(typo_lines, 1):
        wrong, separator, correction = raw.partition('->')
        if (separator and WORD.fullmatch(wrong) and WORD.fullmatch(correction) and
                key(wrong) not in known and key(correction) in by_key):
            expected = by_key[key(correction)]
            refs = [dict(source='codespell.txt', line=line, sourceCorrection=correction)]
            refs += [proof for word in expected for proof in words[word]]
            add(key(wrong), expected, 'typo-listed', 'exact', refs, 'listed', synthetic=False)

    authored = [dict(source='project-authored', line=0)]
    for phrase in PHRASES:
        add(phrase.replace(' ', ''), [phrase], 'phrase', 'exact', authored)
    for word in CONTRACTIONS:
        add(key(word).replace("'", ''), [word], 'contraction', 'exact', authored)
    for word in PRESERVE:
        add(word, [word], 'preserve', 'exact', authored)
    require(len({case['id'] for case in cases}) == len(cases), 'Duplicate case identity')
    return cases


def attribution():
    records = [{**record, 'file': name} for name, record in PINS.items() if 'license' in record]
    records.append(dict(file='project-authored', title='Project-authored example scenarios',
        attribution='kotlin-kana-kanji-converter contributors', license='MIT',
        licenseUrl='https://github.com/KazumaProject/kotlin-kana-kanji-converter/blob/main/LICENSE'))
    return dict(sources=records, changes=CHANGES, collectionLicense='CC-BY-SA-4.0', collectionLicenseUrl=CC4)
