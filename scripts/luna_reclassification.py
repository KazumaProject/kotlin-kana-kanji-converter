#!/usr/bin/env python3
"""Offline, exact-pair reclassification. Never invokes a model."""
import argparse
import collections
import fcntl
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unicodedata
import classified_distribution as d

REL = 'src/main/classification/luna-reclassification'
LOCAL_LEDGER_PATH = 'build/luna-classification/ledger/results.jsonl.gz'
LEGACY_LEDGER_PATH = REL + '/results.jsonl.gz'
FILES = ('distribution-decisions.tsv.gz', 'distribution-candidates.tsv.gz', 'distribution-manifest.json')
MODEL = 'gpt-5.6-luna'
EFFORT = 'max'
POLICY = 'ime-adopt-reject-v1'
HIRA = set('あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんぁぃぅぇぉゃゅょゎっゔーがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ')
REPRESENTATION_REASONS = {
    'hiragana_sentinel_changes_surface': 'かな表記が読みから再構築され、元の表記を保持できないため不採用。',
    'katakana_sentinel_changes_surface': 'カタカナ表記が読みから再構築され、元の表記を保持できないため不採用。',
    'nfc_surface_changes_or_missing_trie_lookup': '表記の正規化または辞書検索により元の表記を保持できないため不採用。',
}
KATA = {chr(ord(c)+0x60) if 'ぁ' <= c <= 'ゔ' else c for c in HIRA}

def jsonl(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as f:
        return [json.loads(line) for line in f]

def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as raw:
        stream = gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) if str(path).endswith('.gz') else raw
        try:
            for row in rows:
                stream.write((json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode())
        finally:
            if stream is not raw: stream.close()

def decisions(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return {tuple(r[:2]): r for r in (line.rstrip('\n').split('\t') for line in f)}

def subsequent_reviews(root, current, baseline):
    """Allow registered review overlays while keeping the original snapshot pinned."""
    import classification_reviews as reviews
    original = baseline['provenance'].get('reviews', [])
    selected = current['provenance'].get('reviews', [])
    if not set(original) <= set(selected):
        raise ValueError('Baseline review history is missing')
    added = [path for path in selected if path not in original]
    entries = reviews.load(root, added)
    provenance = dict(current['provenance'])
    provenance.pop('lunaReclassification', None)
    if 'reviews' in baseline['provenance']:
        provenance['reviews'] = original
    else:
        provenance.pop('reviews', None)
    if 'reviewBaseExcludedCandidatePairs' not in baseline['provenance']:
        if provenance.pop('reviewBaseExcludedCandidatePairs', baseline['excludedCandidatePairs']) != baseline['excludedCandidatePairs']:
            raise ValueError('Review baseline exclusion count changed')
    additions = person_additions_after_baseline(root, current, baseline)
    if 'personAdditions' in baseline['provenance']:
        provenance['personAdditions'] = baseline['provenance']['personAdditions']
    else:
        provenance.pop('personAdditions', None)
    if 'personDictionaryExclusions' not in baseline['provenance']:
        # Person dictionary exclusions were introduced after this Luna snapshot.
        # Validate the retained source-backed exclusion hashes, then treat their
        # metadata as a supported person-policy overlay while comparing the snapshot.
        d.person_dictionary_exclusions(current)
        provenance.pop('personDictionaryExclusions', None)
    inputs = dict(current['inputs'])
    term_data = d.term_classification_data(root) if 'termClassification' in provenance else None
    if 'termClassification' in provenance:
        if term_data is None:
            raise ValueError('Frozen term classification input is missing')
        expected_term_provenance = {key: value for key, value in term_data['metadata'].items()
                                    if key != 'schemaVersion'}
        if provenance.pop('termClassification', None) != expected_term_provenance:
            raise ValueError('Term classification provenance differs from its frozen input')
        for path in (d.TERM_TAXONOMY_PATH, d.TERM_CLASSIFICATIONS_PATH,
                     d.TERM_CLASSIFICATIONS_MANIFEST_PATH):
            if inputs.pop(path, None) != d.sha(root/path):
                raise ValueError('Term classification input hash mismatch')
    if 'eventClassification' in provenance:
        event_data = d.event_classification_data(root)
        if event_data is None:
            raise ValueError('Frozen event classification input is missing')
        expected_event_provenance = {key: value for key, value in event_data['metadata'].items()
                                     if key != 'schemaVersion'}
        if provenance.pop('eventClassification', None) != expected_event_provenance:
            raise ValueError('Event classification provenance differs from its frozen input')
        for path in (d.EVENT_TAXONOMY_PATH, d.EVENT_CLASSIFICATIONS_PATH,
                     d.EVENT_CLASSIFICATIONS_MANIFEST_PATH):
            if inputs.pop(path, None) != d.sha(root/path):
                raise ValueError('Event classification input hash mismatch')
    for path in added:
        if inputs.pop(path, None) != d.sha(root/path):
            raise ValueError('Subsequent review input hash mismatch')
    for batch, _ in additions:
        if inputs.pop(batch['path'], None) != batch['sha256']:
            raise ValueError('Subsequent person-addition input hash mismatch')
    taxonomy_path = 'src/main/classification/person-taxonomy.json'
    if taxonomy_path not in baseline['inputs'] and taxonomy_path in inputs:
        if inputs.pop(taxonomy_path) != d.sha(root/taxonomy_path):
            raise ValueError('Person taxonomy input hash mismatch')
    demographic_path = d.MEDIA_DEMOGRAPHIC_TAXONOMY_PATH
    if demographic_path not in baseline['inputs'] and demographic_path in inputs:
        if inputs.pop(demographic_path) != d.sha(root/demographic_path):
            raise ValueError('Media demographic taxonomy input hash mismatch')
    if PERSON_SOURCE in baseline['inputs']:
        restored = restore_person_source(root, current, baseline, additions)
        if hashlib.sha256(restored).hexdigest() != baseline['inputs'][PERSON_SOURCE]:
            raise ValueError('Person additions do not restore the source snapshot')
        inputs[PERSON_SOURCE] = baseline['inputs'][PERSON_SOURCE]
    if (provenance != baseline['provenance'] or inputs != baseline['inputs']
            or current['idDefSha256'] != baseline['idDefSha256']):
        provenance_diff = sorted(key for key in set(provenance) | set(baseline['provenance'])
                                 if provenance.get(key) != baseline['provenance'].get(key))
        input_missing = sorted(set(baseline['inputs']) - set(inputs))
        input_extra = sorted(set(inputs) - set(baseline['inputs']))
        input_hash_diff = sorted(path for path in set(inputs) & set(baseline['inputs'])
                                 if inputs[path] != baseline['inputs'][path])
        raise ValueError(
            'Unrelated distribution provenance changed: '
            f'provenanceKeys={provenance_diff}, inputMissing={input_missing}, '
            f'inputExtra={input_extra}, inputHashes={input_hash_diff}, '
            f'idDefMismatch={current["idDefSha256"] != baseline["idDefSha256"]}')
    return entries


PERSON_SOURCE = 'src/main/bin/names.txt'
TERM_PARENT_DEFINITION = '独立した語義と読みが辞書原資料で対応する一般語・専門用語。未分類語の受け皿にはしない。'
EVENT_PARENT_DEFINITION = '日付・場所等を持つ個別の出来事、催事、大会、祭り、式典。'
FACILITY_PARENT_DEFINITION = '建物、施設、固定された交通インフラ。'


def person_additions_after_baseline(root, current, baseline):
    """Load only new, manifest-registered person additions layered over the Luna snapshot."""
    base_batches = baseline.get('provenance', {}).get('personAdditions', [])
    current_batches = current.get('provenance', {}).get('personAdditions', [])
    if current_batches[:len(base_batches)] != base_batches:
        raise ValueError('Baseline person-addition provenance is missing or changed')
    additions = []
    for batch in current_batches[len(base_batches):]:
        path = batch.get('path')
        if (not isinstance(path, str) or not path.startswith('src/main/classification/person-additions/')
                or not path.endswith('.jsonl') or batch.get('sha256') != d.sha(root/path)
                or current.get('inputs', {}).get(path) != batch.get('sha256')):
            raise ValueError('Invalid subsequent person-addition provenance')
        entries = d.person_entries(root, root/path)
        added_pairs = [tuple(pair) for pair in batch.get('addedPairs', [])]
        appended_pairs = [tuple(pair) for pair in batch.get('appendedPairs', [])]
        if (len(entries) != batch.get('reviewedPairs') or not added_pairs
                or len(added_pairs) != len(set(added_pairs))
                or not set(added_pairs) <= entries.keys()
                or len(appended_pairs) != batch.get('addedSourceRows')
                or len(appended_pairs) != len(set(appended_pairs))
                or not set(appended_pairs) <= set(added_pairs)):
            raise ValueError('Person-addition rows differ from recorded provenance')
        additions.append((batch, entries))
    return additions


def restore_person_source(root, current, baseline, additions):
    """Remove recorded appended person rows and return the pinned source bytes."""
    if current.get('inputs', {}).get(PERSON_SOURCE) != d.sha(root/PERSON_SOURCE):
        raise ValueError('Current person source hash differs from distribution manifest')
    appended = []
    for batch, entries in additions:
        for pair in (tuple(pair) for pair in batch['appendedPairs']):
            entry = entries[pair]
            appended.append('\t'.join((pair[0], str(entry['left_id']), str(entry['right_id']),
                                       str(entry['cost']), pair[1])).encode('utf-8') + b'\n')
    current_bytes = (root/PERSON_SOURCE).read_bytes()
    suffix = b''.join(appended)
    if suffix and not current_bytes.endswith(suffix):
        raise ValueError('Recorded person additions are not the appended source rows')
    candidate = current_bytes[:-len(suffix)] if suffix else current_bytes
    expected = baseline.get('inputs', {}).get(PERSON_SOURCE)
    hashes = {hashlib.sha256(candidate).hexdigest(): candidate}
    if candidate.endswith(b'\n'):
        without_separator = candidate[:-1]
        hashes[hashlib.sha256(without_separator).hexdigest()] = without_separator
    if expected not in hashes:
        raise ValueError('Appended person rows do not restore the original source hash')
    return hashes[expected]


def term_hierarchy_restores_baseline(root, current, baseline):
    """Allow only saved taxonomy leaf replacements of pinned structural parents."""
    replacements = []
    term_data = d.term_taxonomy(root)
    event_data = d.event_taxonomy(root)
    media_data = d.media_demographic_taxonomy(root)
    facility_data = d.facility_classification_data(root)
    if term_data is not None and 'termClassification' in current.get('provenance', {}):
        replacements.append(('term', term_data[0], term_data[1], TERM_PARENT_DEFINITION))
    if event_data is not None and 'eventClassification' in current.get('provenance', {}):
        replacements.append(('event', event_data[0], event_data[1], EVENT_PARENT_DEFINITION))
    if facility_data is not None and 'facilityClassification' in current.get('provenance', {}):
        facility_structure = dict(facility_data['taxonomy'], name='施設')
        replacements.append(('facility', facility_structure, facility_data['categories'], FACILITY_PARENT_DEFINITION))
    if not replacements:
        return False
    expanded = json.loads((root/'src/main/classification/categories.json').read_text(encoding='utf-8'))
    replacement_map = {
        parent_id: (structure, {category['id'] for category in leaves}, definition)
        for parent_id, structure, leaves, definition in replacements
    }
    demographic_ids = {category['id'] for category in media_data[1]} if media_data is not None else set()
    collapsed_current_categories = []
    collapsed_baseline_categories = []
    inserted_parents = set()
    for category in expanded.get('categories', []):
        parent_id = next((parent for parent, (_, leaf_ids, _) in replacement_map.items()
                          if category.get('id') in leaf_ids), None)
        if parent_id is not None:
            if parent_id not in inserted_parents:
                structure, _, definition = replacement_map[parent_id]
                parent_category = {
                    'id': parent_id, 'name': structure['name'], 'definition': definition,
                }
                collapsed_current_categories.append(parent_category)
                collapsed_baseline_categories.append(parent_category)
                inserted_parents.add(parent_id)
        elif category.get('id') in demographic_ids:
            collapsed_current_categories.append(category)
        else:
            collapsed_current_categories.append(category)
            collapsed_baseline_categories.append(category)
    if inserted_parents != set(replacement_map):
        return False
    collapsed_current = dict(expanded)
    collapsed_current.pop('categoryGroups', None)
    collapsed_current['categories'] = collapsed_current_categories
    if d.merged_categories(collapsed_current, term_data if 'term' in replacement_map else None,
                          event_data if 'event' in replacement_map else None, media_data,
                          facility_data if 'facility' in replacement_map else None) != expanded:
        return False
    collapsed_baseline = dict(expanded)
    collapsed_baseline.pop('categoryGroups', None)
    collapsed_baseline['categories'] = collapsed_baseline_categories
    reconstructed = json.dumps(collapsed_baseline, ensure_ascii=False, indent=2) + '\n'
    expected_hash = baseline.get('files', {}).get('categories.json')
    if hashlib.sha256(reconstructed.encode('utf-8')).hexdigest() != expected_hash:
        return False
    category_ids = {category['id'] for category in expanded['categories']}
    if 'term' in replacement_map:
        data = d.term_classification_data(root, category_ids)
        expected_provenance = ({key: value for key, value in data['metadata'].items()
                                if key != 'schemaVersion'} if data is not None else None)
        if expected_provenance is None or current['provenance'].get('termClassification') != expected_provenance:
            return False
        for relative in (d.TERM_TAXONOMY_PATH, d.TERM_CLASSIFICATIONS_PATH,
                         d.TERM_CLASSIFICATIONS_MANIFEST_PATH):
            if current.get('inputs', {}).get(relative) != d.sha(root/relative):
                return False
    if 'event' in replacement_map:
        data = d.event_classification_data(root, category_ids)
        expected_provenance = ({key: value for key, value in data['metadata'].items()
                                if key != 'schemaVersion'} if data is not None else None)
        if expected_provenance is None or current['provenance'].get('eventClassification') != expected_provenance:
            return False
        for relative in (d.EVENT_TAXONOMY_PATH, d.EVENT_CLASSIFICATIONS_PATH,
                         d.EVENT_CLASSIFICATIONS_MANIFEST_PATH):
            if current.get('inputs', {}).get(relative) != d.sha(root/relative):
                return False
    if 'facility' in replacement_map:
        data = d.facility_classification_data(root, category_ids)
        expected_provenance = ({key: value for key, value in data['metadata'].items()
                                if key not in ('schemaVersion', 'taxonomySha256', 'classificationSha256')}
                               if data is not None else None)
        if expected_provenance is None or current['provenance'].get('facilityClassification') != expected_provenance:
            return False
        for relative in (d.FACILITY_TAXONOMY_PATH, d.FACILITY_CLASSIFICATIONS_PATH,
                         d.FACILITY_CLASSIFICATIONS_MANIFEST_PATH):
            if current.get('inputs', {}).get(relative) != d.sha(root / relative):
                return False
    return True


def snapshot(root):
    out = root / REL
    m = json.loads((out/'manifest.json').read_text())
    expected_files = {'targets.jsonl.gz','baseline-decisions.tsv.gz','baseline-candidates.tsv.gz'}
    if set(m['files']) != expected_files: raise ValueError('Invalid snapshot files')
    for name, value in m['files'].items():
        if d.sha(out/name) != value: raise ValueError('Snapshot hash mismatch: '+name)
    baseline = m['baselineManifest']
    current = json.loads((root/'src/main/classification/distribution-manifest.json').read_text())
    additions = person_additions_after_baseline(root, current, baseline)
    restored_person_source = (restore_person_source(root, current, baseline, additions)
                              if PERSON_SOURCE in baseline['inputs'] else None)
    for name in FILES[:2]:
        if m['files']['baseline-'+name.removeprefix('distribution-')] != baseline['files'][name]:
            raise ValueError('Baseline snapshot hash mismatch')
    for path, expected in baseline['inputs'].items():
        actual = (hashlib.sha256(restored_person_source).hexdigest()
                  if path == PERSON_SOURCE and restored_person_source is not None else d.sha(root/path))
        if actual != expected: raise ValueError('Source input hash mismatch: '+path)
    if d.sha(root/'src/main/resources/id.def') != baseline['idDefSha256']:
        raise ValueError('id.def changed since export')
    if (d.sha(root/'src/main/classification/categories.json') != baseline['files']['categories.json']
            and not term_hierarchy_restores_baseline(root, current, baseline)):
        raise ValueError('Taxonomy changed since export')
    if 'lunaReclassification' not in current['provenance']:
        if current != baseline: raise ValueError('Distribution manifest changed since export')
    else:
        subsequent_reviews(root, current, baseline)
    if m['heldSourceSha256'] != baseline['provenance']['dispositionsSha256']:
        raise ValueError('Held source provenance mismatch')
    targets = jsonl(out/'targets.jsonl.gz')
    base = decisions(out/'baseline-decisions.tsv.gz')
    pairs = set(); keys = set()
    variants = collections.defaultdict(set)
    for t in targets:
        if not isinstance(t,dict) or not isinstance(t.get('reading'),str) or not isinstance(t.get('surface'),str):
            raise ValueError('Invalid target schema')
        pair = t['reading'],t['surface']
        if not all(pair) or pair in pairs or t.get('candidate_key') != d.key(*pair) or t['candidate_key'] in keys:
            raise ValueError('Duplicate or invalid target key')
        pairs.add(pair); keys.add(t['candidate_key'])
        prior = base.get(pair)
        if (prior and (prior[4] not in ('unclassified','no_result') or t.get('original_status') != prior[4]
                       or t.get('original_origin') != prior[3])) or (not prior and (t.get('original_status') != 'held' or t.get('original_origin') is not None)):
            raise ValueError('Invalid target baseline status')
        rows = t.get('source_rows')
        if not isinstance(rows,list) or not rows or any(not isinstance(r,list) or len(r)!=6 or any(not isinstance(v,str) for v in r) for r in rows):
            raise ValueError('Invalid target source variants')
        variants[pair] = {tuple(r) for r in rows}
        if len(variants[pair]) != len(rows): raise ValueError('Duplicate source variants')
    unresolved = {pair for pair,row in base.items() if row[4] in ('unclassified','no_result')}
    if not unresolved <= pairs: raise ValueError('Missing baseline unresolved target')
    if len(targets) != m['targetCount'] or dict(collections.Counter(t['original_status'] for t in targets)) != m['targetCounts']:
        raise ValueError('Snapshot counts mismatch')
    actual = collections.defaultdict(set)
    for source,row in d.source_rows(root):
        pair=row[0],row[4]
        if pair in pairs: actual[pair].add((source,*row))
    if dict(actual) != dict(variants): raise ValueError('Target source variants mismatch')
    return m, targets, base

def export(root, dispositions, revision):
    d.verify(root)
    directory = root/'src/main/classification'
    m = json.loads((directory/'distribution-manifest.json').read_text())
    if d.sha(dispositions) != m['provenance']['dispositionsSha256']: raise ValueError('Held source hash mismatch')
    base = decisions(directory/FILES[0])
    targets = {pair: {'original_status': row[4], 'original_origin': row[3], 'hints': []} for pair,row in base.items() if row[4] in ('unclassified','no_result')}
    with gzip.open(dispositions,'rt',encoding='utf-8') as f:
        for line in f:
            row = line.rstrip('\n').split('\t')
            pair = tuple(row[3:5])
            if row[0] == 'held' and pair not in base:
                targets.setdefault(pair, {'original_status':'held', 'original_origin':None, 'hints': []})['hints'].append({'source':row[2], 'categories':json.loads(row[1]), 'reason':json.loads(row[8]), 'source_hints':json.loads(row[9])})
    variants = collections.defaultdict(set)
    for source,row in d.source_rows(root):
        pair = (row[0],row[4])
        if pair in targets: variants[pair].add((source,*row))
    if set(targets)-set(variants): raise ValueError('Target missing from source')
    out=root/REL
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.luna-export-',dir=out.parent) as temp:
        staged=Path(temp)/'snapshot'; staged.mkdir()
        write_jsonl(staged/'targets.jsonl.gz', ({'candidate_key':d.key(*pair),'reading':pair[0],'surface':pair[1], **info,'source_rows':[list(r) for r in sorted(variants[pair])]} for pair,info in sorted(targets.items())))
        for name in FILES[:2]: shutil.copyfile(directory/name,staged/('baseline-'+name.removeprefix('distribution-')))
        manifest={'schemaVersion':1,'revision':revision,'heldSourceSha256':d.sha(dispositions),'baselineManifest':m,'targetCounts':dict(collections.Counter(x['original_status'] for x in targets.values())), 'targetCount':len(targets), 'files':{name:d.sha(staged/name) for name in ('targets.jsonl.gz','baseline-decisions.tsv.gz','baseline-candidates.tsv.gz')}}
        d.write_json(staged/'manifest.json',manifest)
        if out.exists():
            if (out/'manifest.json').read_bytes()!=(staged/'manifest.json').read_bytes() or any(d.sha(out/n)!=h for n,h in manifest['files'].items()):
                raise ValueError('Existing snapshot differs from requested export')
            snapshot(root)
            print('Reused identical snapshot')
        else: os.replace(staged,out)
    print(json.dumps({'targetCount':len(targets),'targetCounts':manifest['targetCounts'],'target_sha256':manifest['files']['targets.jsonl.gz']}))

def batches(root, size):
    if size <= 0: raise ValueError('Batch size must be positive')
    m,targets,_=snapshot(root)
    out=root/'build/luna-classification/requests'
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.luna-requests-',dir=out.parent) as temp:
        staged=Path(temp)/'requests'; staged.mkdir()
        count=0
        for index,start in enumerate(range(0,len(targets),size)):
            rows=targets[start:start+size]; stem=f'{index:06d}'; count+=1
            write_jsonl(staged/(stem+'.jsonl'),rows)
            d.write_json(staged/(stem+'.meta.json'),{'target_sha256':m['files']['targets.jsonl.gz'],'candidate_keys':[r['candidate_key'] for r in rows], 'model':MODEL,'reasoning_effort':EFFORT})
        if out.exists():
            names={p.name for p in staged.iterdir()}
            if {p.name for p in out.iterdir()}!=names or any(d.sha(out/n)!=d.sha(staged/n) for n in names):
                raise ValueError('Existing request batches differ; refusing to overwrite active controller inputs')
            print(f'Reused {count} identical request batches')
        else:
            os.replace(staged,out)
            print(f'Wrote {count} request batches')

def representation_error(reading,surface):
    normalized=unicodedata.normalize('NFC',surface)
    if reading == surface: return None
    if normalized and set(normalized)<=HIRA:
        if surface != reading: return 'hiragana_sentinel_changes_surface'
    elif normalized and set(normalized)<=KATA:
        reconstructed=''.join(chr(ord(c)+0x60) if '\u3041'<=c<='\u3093' else c for c in reading)
        if surface != reconstructed: return 'katakana_sentinel_changes_surface'
    elif normalized != surface: return 'nfc_surface_changes_or_missing_trie_lookup'
    return None

def load_results(root, directory, allow_partial=False):
    m,targets,base=snapshot(root)
    by_key={r['candidate_key']:r for r in targets}
    results={}
    for path in sorted(directory.glob('*.jsonl')):
        meta=json.loads(path.with_suffix('.meta.json').read_text())
        if (meta.get('policy_version') != POLICY or meta.get('target_sha256') != m['files']['targets.jsonl.gz'] or meta.get('model') != MODEL or meta.get('reasoning_effort') != EFFORT): raise ValueError('Batch provenance mismatch')
        expected=meta['candidate_keys']
        if len(expected)!=len(set(expected)) or not set(expected)<=by_key.keys(): raise ValueError('Invalid expected batch keys')
        batch=jsonl(path)
        if any(not isinstance(r,dict) or not isinstance(r.get('candidate_key'),str) for r in batch): raise ValueError('Invalid result row schema')
        keys=[r.get('candidate_key') for r in batch]
        if len(keys)!=len(set(keys)) or set(keys)!=set(expected): raise ValueError('Duplicate or missing batch IDs')
        positions={k:i for i,k in enumerate(expected)}
        for row in batch:
            k=row['candidate_key']
            if k in results: raise ValueError('Duplicate result ID')
            target=by_key[k]
            if (row.get('reading'),row.get('surface')) != (target['reading'],target['surface']): raise ValueError('Changed reading/surface')
            if row.get('policy_version')!=POLICY or row.get('model')!=MODEL or row.get('reasoning_effort')!=EFFORT: raise ValueError('Invalid model identity or policy')
            cats=row.get('categories')
            allowed=set(m['baselineManifest']['categoryRows'])
            if not isinstance(cats,list) or any(not isinstance(c,str) for c in cats) or len(cats)!=len(set(cats)) or not set(cats)<=allowed: raise ValueError('Invalid categories')
            if row.get('action') not in ('adopt','reject') or bool(cats)!=(row['action']=='adopt') or not isinstance(row.get('reason'),str) or not row['reason'].strip(): raise ValueError('Invalid action/reason')
            error=representation_error(target['reading'],target['surface']) if row['action']=='adopt' else None
            results[k]={'response':row,'effective_action':'reject' if error else row['action'],'effective_categories':[] if error else sorted(cats),'representation_error':error,'effective_reason':REPRESENTATION_REASONS[error] if error else row['reason'],
                        'batch_provenance':{**{field:value for field,value in meta.items() if field!='candidate_keys'},
                                            'batch_stem':path.stem,'candidate_key_position':positions[k]}}
    if not allow_partial and results.keys()!=by_key.keys(): raise ValueError(f'Incomplete results: {len(results)}/{len(by_key)}')
    return m,targets,base,results

def verify_ledger(root, required=False):
    directory=root/'src/main/classification'
    manifest=json.loads((directory/FILES[2]).read_text())
    record=manifest.get('provenance',{}).get('lunaReclassification')
    if not record: return True
    path=root/record['path']
    if not path.is_file():
        if required:
            raise FileNotFoundError(f'Local Luna ledger is missing: {path}')
        return False
    m,targets,base=snapshot(root)
    if record.get('snapshotManifestSha256')!=d.sha(root/REL/'manifest.json'):
        raise ValueError('Snapshot manifest hash mismatch')
    entries = subsequent_reviews(root, manifest, m['baselineManifest'])
    if d.sha(path)!=record['sha256']: raise ValueError('Result ledger hash mismatch')
    ledger=jsonl(path)
    by_key={r['candidate_key']:r for r in targets}
    if len(by_key)!=m['targetCount'] or dict(collections.Counter(r['original_status'] for r in targets))!=m['targetCounts']:
        raise ValueError('Snapshot counts mismatch')
    if len(ledger)!=len(by_key) or len({r['response']['candidate_key'] for r in ledger})!=len(by_key): raise ValueError('Incomplete ledger')
    for r in ledger:
        row=r['response']; k=row['candidate_key']
        if k not in by_key: raise ValueError('Ledger contains unrelated pair')
        t=by_key[k]
        batch=r.get('batch_provenance')
        if (not isinstance(batch,dict) or batch.get('target_sha256')!=m['files']['targets.jsonl.gz']
                or batch.get('policy_version')!=POLICY or batch.get('model')!=MODEL
                or batch.get('reasoning_effort')!=EFFORT or not isinstance(batch.get('batch_stem'),str)
                or not batch['batch_stem'] or type(batch.get('candidate_key_position')) is not int
                or batch['candidate_key_position']<0):
            raise ValueError('Invalid ledger batch provenance')
        if (row['reading'],row['surface'])!=(t['reading'],t['surface']): raise ValueError('Ledger changed pair')
        if row.get('policy_version')!=POLICY or row.get('model')!=MODEL or row.get('reasoning_effort')!=EFFORT or not isinstance(row.get('reason'),str) or not row['reason'].strip():
            raise ValueError('Invalid ledger response provenance')
        cats=row.get('categories')
        if (not isinstance(cats,list) or any(not isinstance(c,str) for c in cats) or len(cats)!=len(set(cats))
                or not set(cats)<=set(m['baselineManifest']['categoryRows'])
                or row.get('action') not in ('adopt','reject') or bool(cats)!=(row['action']=='adopt')):
            raise ValueError('Invalid ledger response classification')
        error=representation_error(t['reading'],t['surface']) if row['action']=='adopt' else None
        if (r['representation_error']!=error or r['effective_action']!=('reject' if error else row['action'])
                or r['effective_categories']!=([] if error else sorted(cats))
                or r.get('effective_reason')!=(REPRESENTATION_REASONS[error] if error else row['reason'])):
            raise ValueError('Ledger effective decision mismatch')
        pair=(t['reading'],t['surface'])
        prior=base.get(pair)
        if (prior and (prior[4] not in ('unclassified','no_result') or prior[4]!=t['original_status'] or prior[3]!=t['original_origin'])) or (not prior and t['original_status']!='held'):
            raise ValueError('Invalid baseline target')
        base[pair]=[*pair,','.join(r['effective_categories']),'manual','classified' if r['effective_action']=='adopt' else 'excluded']
    import classification_reviews as reviews
    before_excluded = sum(r[4]=='excluded' for r in base.values())
    base = reviews.apply(base, entries)
    for batch, person_entries in person_additions_after_baseline(root, manifest, m['baselineManifest']):
        for reading, surface in batch['addedPairs']:
            pair = reading, surface
            if pair in base or pair not in person_entries:
                raise ValueError('Person addition conflicts with the pinned decision ledger')
            base[pair] = [reading, surface, 'person', 'verified', 'classified']
    base = d.apply_term_classifications(
        root, base, force='termClassification' in manifest['provenance'], reviewed_pairs=entries)
    base = d.apply_event_classifications(
        root, base, force='eventClassification' in manifest['provenance'], reviewed_pairs=entries)
    base = d.apply_facility_classifications(
        root, base, force='facilityClassification' in manifest['provenance'], reviewed_pairs=entries)
    person_exclusions = d.person_dictionary_exclusions(manifest)
    for pair in list(base):
        if d.key(*pair) in person_exclusions:
            row = base[pair]
            remaining = set(filter(None, row[2].split(','))) - {'person'}
            if remaining:
                row[2] = ','.join(sorted(remaining))
            else:
                del base[pair]
    exclusion_delta = sum(r[4]=='excluded' for r in base.values()) - before_excluded
    if (manifest['excludedCandidatePairs']!=m['baselineManifest']['excludedCandidatePairs']+sum(r['effective_action']=='reject' for r in ledger)+exclusion_delta
            or manifest['excludedClassifiedPairs']!=sum(r[4]=='excluded' for r in base.values())):
        raise ValueError('Exclusion counts differ from ledger')
    saved_decisions = decisions(directory/FILES[0])
    if base != saved_decisions:
        missing = sorted(set(base) - set(saved_decisions))
        extra = sorted(set(saved_decisions) - set(base))
        changed = sorted(pair for pair in set(base) & set(saved_decisions)
                         if base[pair] != saved_decisions[pair])
        raise ValueError(
            'Decisions differ from baseline plus ledger: '
            f'missing={len(missing)} {missing[:5]}, extra={len(extra)} {extra[:5]}, '
            f'changed={len(changed)} {[(pair, base[pair], saved_decisions[pair]) for pair in changed[:5]]}')
    if (record['targetSha256']!=m['files']['targets.jsonl.gz'] or record['completedPairs']!=len(ledger)
            or record.get('policy_version')!=POLICY or record.get('model')!=MODEL or record.get('reasoningEffort')!=EFFORT
            or record.get('effectiveActions')!=dict(collections.Counter(r['effective_action'] for r in ledger))): raise ValueError('Ledger provenance mismatch')
    return True

def apply(root, results_dir, dry_run=False, allow_partial=False):
    if allow_partial and not dry_run: raise ValueError('--allow-partial requires --dry-run')
    m,targets,base,results=load_results(root,results_dir,allow_partial)
    counts=collections.Counter(r['effective_action'] for r in results.values())
    if dry_run:
        print(json.dumps({'validatedPairs':len(results),'effectiveActions':dict(counts)})); return
    directory=root/'src/main/classification'
    (root/'build/luna-classification').mkdir(parents=True,exist_ok=True)
    with (root/'build/luna-classification/apply.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        ledger=[results[k] for k in sorted(results)]
        with tempfile.TemporaryDirectory(prefix='luna-apply-') as temp:
            staging=Path(temp)
            staged=staging/'src/main/classification'; staged.mkdir(parents=True)
            for path in (root/'src/main/classification').iterdir():
                if path.name not in FILES: (staged/path.name).symlink_to(path.resolve(),target_is_directory=path.is_dir())
            # The result ledger must be staged locally instead of writing through a symlink.
            (staged/'luna-reclassification').unlink()
            shutil.copytree(root/REL,staging/REL)
            ledger_path=staging/LOCAL_LEDGER_PATH; write_jsonl(ledger_path,ledger)
            (staging/LEGACY_LEDGER_PATH).unlink(missing_ok=True)
            current=json.loads((directory/FILES[2]).read_text())
            old=current['provenance'].get('lunaReclassification')
            if old:
                if old['sha256']==d.sha(ledger_path):
                    local_ledger=root/LOCAL_LEDGER_PATH
                    if not local_ledger.exists():
                        local_ledger.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(ledger_path,local_ledger)
                    d.verify(root); print('Already applied identical results'); return
                raise ValueError('Different results already applied')
            if any(d.sha(directory/name)!=m['baselineManifest']['files'][name] for name in FILES[:2]): raise ValueError('Distribution changed since export')
            for t in targets:
                r=results[t['candidate_key']]; pair=t['reading'],t['surface']
                base[pair]=[*pair,','.join(r['effective_categories']),'manual','classified' if r['effective_action']=='adopt' else 'excluded']
            if 'reviews' in current.get('provenance', {}):
                import classification_reviews as reviews
                review_entries=reviews.load(root,current['provenance']['reviews'])
                rows=reviews.candidate_rows(root,base,review_entries)
            else:
                rows=set()
                for _,row in d.source_rows(root):
                    pair=row[0],row[4]; decision=base.get(pair)
                    if decision and decision[4]=='classified': rows.update((cat,*row) for cat in decision[2].split(','))
            d.write_gzip(staged/FILES[0],(base[p] for p in sorted(base)))
            d.write_gzip(staged/FILES[1],sorted(rows))
            origins=collections.Counter(r[3] for r in base.values() if r[4]=='classified')
            cats=collections.Counter(r[0] for r in rows)
            current.update(excludedClassifiedPairs=sum(r[4]=='excluded' for r in base.values()),excludedCandidatePairs=m['baselineManifest']['excludedCandidatePairs']+counts['reject'],admittedPairsByOrigin=dict(origins),uniqueAdmittedPairs=sum(origins.values()),dictionaryRows=len(rows),categoryRows={c:cats[c] for c in current['categoryRows']},unclassifiedPairs=sum(r[4]=='unclassified' for r in base.values()),noResultPairs=sum(r[4]=='no_result' for r in base.values()))
            current['files'].update({name:d.sha(staged/name) for name in FILES[:2]})
            current['provenance']['lunaReclassification']={'path':LOCAL_LEDGER_PATH,'snapshotManifestSha256':d.sha(root/REL/'manifest.json'),'sha256':d.sha(ledger_path),'targetSha256':m['files']['targets.jsonl.gz'],'completedPairs':len(results),'effectiveActions':dict(counts),'policy_version':POLICY,'model':MODEL,'reasoningEffort':EFFORT}
            d.write_json(staged/FILES[2],current)
            for relative in [*current['inputs'],'src/main/resources/id.def']:
                target=staging/relative; target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists(): target.symlink_to((root/relative).resolve())
            d.verify(staging)
            changes=[LOCAL_LEDGER_PATH,LEGACY_LEDGER_PATH,*['src/main/classification/'+n for n in FILES]]
            backup=root/'build/luna-classification/apply-backup'
            if backup.exists(): raise ValueError('Interrupted apply backup exists; run recover')
            backup.mkdir(parents=True)
            for p in changes:
                if (root/p).exists():
                    dst=backup/p; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(root/p,dst)
            d.write_json(backup/'journal.json',{'paths':changes,'existing':[p for p in changes if (root/p).exists()]})
            try:
                for p in changes:
                    if p==LEGACY_LEDGER_PATH:
                        (root/p).unlink(missing_ok=True)
                        continue
                    dst=root/p; dst.parent.mkdir(parents=True,exist_ok=True)
                    tmp=dst.with_name(dst.name+'.luna-tmp'); shutil.copyfile(staging/p,tmp); os.replace(tmp,dst)
                d.verify(root)
            except BaseException:
                _recover_unlocked(root); raise
            shutil.rmtree(backup)
    print(json.dumps({'appliedPairs':len(results),'effectiveActions':dict(counts)}))

def _recover_unlocked(root):
    backup=root/'build/luna-classification/apply-backup'
    journal=json.loads((backup/'journal.json').read_text())
    repository_paths={'src/main/classification/'+n for n in FILES}
    allowed={LOCAL_LEDGER_PATH,LEGACY_LEDGER_PATH,*repository_paths}
    legacy_allowed={LEGACY_LEDGER_PATH,*repository_paths}
    if (not isinstance(journal.get('paths'),list) or len(journal['paths'])!=len(set(journal['paths']))
            or set(journal['paths']) not in (allowed,legacy_allowed) or not isinstance(journal.get('existing'),list)
            or not set(journal['existing'])<=set(journal['paths'])):
        raise ValueError('Invalid recovery journal paths')
    if any(not (backup/p).is_file() for p in journal['existing']):
        raise ValueError('Incomplete recovery backup')
    for p in journal['paths']:
        if p in journal['existing']:
            (root/p).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(backup/p,root/p)
        else: (root/p).unlink(missing_ok=True)
        (root/p).with_name(Path(p).name+'.luna-tmp').unlink(missing_ok=True)
    shutil.rmtree(backup)

def recover(root):
    (root/'build/luna-classification').mkdir(parents=True,exist_ok=True)
    with (root/'build/luna-classification/apply.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('Apply is active; recovery refused')
        _recover_unlocked(root)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['export','batches','apply','recover','verify'])
    p.add_argument('--root',type=Path,default=Path('.')); p.add_argument('--dispositions',type=Path); p.add_argument('--revision',default='local'); p.add_argument('--results',type=Path); p.add_argument('--batch-size',type=int,default=200); p.add_argument('--dry-run',action='store_true'); p.add_argument('--allow-partial',action='store_true')
    a=p.parse_args(); root=a.root.resolve()
    if a.command=='export': export(root,a.dispositions,a.revision)
    elif a.command=='batches':
        if a.batch_size<=0: p.error('batch size must be positive')
        batches(root,a.batch_size)
    elif a.command=='apply': apply(root,a.results,a.dry_run,a.allow_partial)
    elif a.command=='recover': recover(root)
    else: verify_ledger(root,required=True)
