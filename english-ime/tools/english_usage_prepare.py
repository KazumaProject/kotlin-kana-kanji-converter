"""Extract local English quotation leads from the pinned Wiktextract snapshot.

This stage never approves a word, role, standalone name or exclusion. Input
rows and contextual-name labels only select evidence for subsequent review.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import time

import lexicon_pipeline as pipeline
from wiktionary_index import SNAPSHOT_SHA256

COMPONENTS_SHA = '4f2cb762b44b2481e531feba8a1aec98ea2bffa47088cd2932bf53cbed507d7d'
WORD_PATTERN = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")


class HashedReader:
    def __init__(self, stream):
        self.stream = stream
        self.hash = hashlib.sha256()

    def read(self, size=-1):
        data = self.stream.read(size)
        self.hash.update(data)
        return data

    def seekable(self):
        return False


def witnesses(number, entry, wanted, parents, records, heads, counts, max_per_form=24, identified_standalone_only=False):
    if entry.get('lang_code') != 'en':
        return
    counts['englishEntries'] += 1
    head = entry['word']
    if head.casefold() in wanted:
        heads.append(dict(entryId=number, word=head, pos=entry.get('pos'), tags=entry.get('tags', []),
            senses=[{key: value for key, value in sense.items() if key in {'id', 'senseid', 'tags', 'glosses', 'form_of', 'alt_of', 'raw_glosses'}} for sense in entry.get('senses', [])]))
    for sense_number, sense in enumerate(entry.get('senses', [])):
        for example_number, example in enumerate(sense.get('examples', [])):
            text = example.get('text')
            if not isinstance(text, str):
                continue
            if identified_standalone_only and (example.get('type') != 'quotation' or not isinstance(example.get('ref'), str) or not example['ref'].strip()):
                continue
            counts['englishQuotations' if identified_standalone_only else 'englishExamples'] += 1
            lower = text.casefold()
            for match in WORD_PATTERN.finditer(text):
                observed = match[0]
                word = observed.casefold()
                possessive = False
                if word not in wanted and word.endswith(("'s", '’s')) and word[:-2] in wanted:
                    word = word[:-2]
                    possessive = True
                if word not in wanted or len(records[word]) >= max_per_form:
                    continue
                embedded = ((match.start() > 0 and text[match.start() - 1] in './@_') or
                    (match.end() < len(text) and text[match.end()] in './@_'))
                full = []
                for parent in parents[word]:
                    offset = lower.find(parent)
                    if offset >= 0 and offset <= match.start() < offset + len(parent):
                        full.append(parent)
                if identified_standalone_only and (full or embedded):
                    continue
                records[word].append(dict(entryId=number, headword=head, pos=entry.get('pos'),
                    senseIndex=sense_number, exampleIndex=example_number, form=word, observed=observed,
                    possessive=possessive, inKnownFullName=sorted(full), embeddedInIdentifier=embedded,
                    quoteSha256=hashlib.sha256(text.encode()).hexdigest(),
                    contextBefore=text[max(0, match.start() - 100):match.start()],
                    contextAfter=text[match.end():match.end() + 130], exampleType=example.get('type'),
                    reference=example.get('ref'), EnglishLexicalEntryTags=entry.get('tags', []),
                    EnglishSenseTags=sense.get('tags', [])))


def prepare(args):
    if args.out.exists():
        raise ValueError('Output exists')
    if not 1 <= args.max_per_form <= 128:
        raise ValueError('Per-form quotation limit must be in 1..128')
    pipeline.verify(args.base)
    rows = pipeline.inventory(args.base / 'inventory.jsonl')
    states = list(map(json.loads, (args.base / 'status.jsonl').open()))
    selected = [row for row, state in zip(rows, states) if state['decision'] == 'pending']
    wanted = {row['surface'].casefold() for row in selected}
    if pipeline.digest(args.named_components) != COMPONENTS_SHA:
        raise ValueError('Changed contextual-name source')
    parents = defaultdict(set)
    for entity in map(json.loads, args.named_components.open()):
        for match in entity['matches']:
            if match['predicate'] == 'rdfs:label' and match['language'] == 'en':
                parents[match['component'].casefold()].add(match['label'].casefold())
    before = args.snapshot.stat()
    started = time.monotonic()
    records, heads, counts = defaultdict(list), [], Counter()
    with args.snapshot.open('rb') as stream:
        raw = HashedReader(stream)
        with gzip.GzipFile(fileobj=raw, mode='rb') as compressed:
            for number, line in enumerate(compressed, 1):
                if number % 1000000 == 0:
                    print(json.dumps(dict(rawEntries=number, englishEntries=counts['englishEntries'], matchedForms=len(records), seconds=round(time.monotonic() - started, 1))), flush=True)
                if b'"lang_code": "en"' in line or b'"lang_code":"en"' in line:
                    witnesses(number, json.loads(line), wanted, parents, records, heads, counts,
                        max_per_form=args.max_per_form, identified_standalone_only=args.identified_standalone_only)
        observed_sha = raw.hash.hexdigest()
    after = args.snapshot.stat()
    if observed_sha != SNAPSHOT_SHA256 or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Snapshot changed during extraction or has a different hash')
    args.out.mkdir(parents=True)
    for name, values in [('usage.jsonl', [row for key in sorted(records) for row in records[key]]), ('heads.jsonl', heads)]:
        (args.out / name).write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in values))
    manifest = dict(snapshotSha256=observed_sha, inventorySha256=pipeline.digest(args.base / 'inventory.jsonl'),
        baseManifestSha256=pipeline.digest(args.base / 'manifest.json'), namedComponentsSha256=COMPONENTS_SHA,
        inputRows=len(selected), wantedForms=len(wanted), matchedForms=len(records), records=sum(map(len, records.values())),
        counts=dict(counts), files={name:pipeline.digest(args.out / name) for name in ['usage.jsonl', 'heads.jsonl']},
        maxPerForm=args.max_per_form, identifiedStandaloneOnly=args.identified_standalone_only,
        scope='local English quotation/example leads only; no automatic standalone/name/POS admission or external transmission')
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ['base', 'snapshot', 'named-components', 'out']:
        parser.add_argument('--' + field, type=Path, required=True)
    parser.add_argument('--max-per-form', type=int, default=24)
    parser.add_argument('--identified-standalone-only', action='store_true')
    prepare(parser.parse_args())
