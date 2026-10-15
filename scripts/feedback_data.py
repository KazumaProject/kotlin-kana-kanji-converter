"""Offline, append-only owner requests shared by dictionary generators."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata

DIRECTORY = Path('src/main/dictionary-feedback')
REPOSITORY = 'KazumaProject/kotlin-kana-kanji-converter'
OWNER = 'KazumaProject'
COST = 9000


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n'


def categories(root):
    result = {}
    for directory in ('classification', 'specialist'):
        for item in json.loads((root / 'src/main' / directory / 'categories.json').read_text())['categories']:
            result['categories/' + item['id']] = item.get('name', item['id'])
    return result


def text(value, name):
    if (not isinstance(value, str) or not value or len(value) > 1000
            or any(unicodedata.category(c).startswith('C') for c in value)):
        raise ValueError('Invalid ' + name)
    return value


def normalize(reading, surface):
    text(reading, 'reading'); text(surface, 'surface')
    reading = unicodedata.normalize('NFKC', reading.strip())
    reading = unicodedata.normalize('NFC', ''.join(chr(ord(c) - 0x60) if '\u30a1' <= c <= '\u30f6' else c for c in reading))
    surface = unicodedata.normalize('NFC', surface.strip())
    if not re.fullmatch('[ぁ-ゖー]+', reading) or not surface:
        raise ValueError('読みはかな、表記は空でない文字列を入力してください。')
    return reading, surface


def pos_rules(root):
    directory = root / DIRECTORY / 'mozc'
    source = json.loads((directory / 'source.json').read_text())
    for name in ('user_pos.def', 'cforms.def'):
        if digest(directory / name) != source['files']['src/data/rules/' + name]:
            raise ValueError('Pinned Mozc rule hash mismatch: ' + name)
    if digest(root / 'src/main/resources/id.def') != source['files']['src/data/dictionary_oss/id.def']:
        raise ValueError('Mozc id.def differs from pinned feedback rules')
    ids = [line.rstrip('\n').split(maxsplit=1) for line in (root / 'src/main/resources/id.def').read_text().splitlines()]
    forms = {}
    for line in (directory / 'cforms.def').read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        kind, form, surface, reading, *_ = line.split()
        forms.setdefault(kind, []).append((form, '' if surface == '*' else surface, '' if reading == '*' else reading))
    profiles = {}
    for line in (directory / 'user_pos.def').read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        label, _, kind, feature, *_ = line.split()
        # Special user-only IDs are outside the static connection matrix.
        if label in ('品詞なし', '短縮よみ', 'サジェストのみ', '抑制単語'): continue
        variants = [(None, '', '')] if kind == '*' else forms.get(kind, [])
        entries = []
        for form, surface, reading in variants:
            prefix = feature.replace('<cform>', form or '')
            match = next((int(i) for i, name in ids if name.startswith(prefix)), None)
            if match is not None: entries.append((surface, reading, match))
        if entries: profiles[label] = entries
    return source, profiles


def expand(root, reading, surface, profile):
    """Use Mozc user_pos/cforms base-suffix replacement, never guess a conjugation."""
    _, profiles = pos_rules(root)
    if profile not in profiles: raise ValueError('未対応の品詞・活用種類です: ' + profile)
    variants = profiles[profile]
    value_suffix, key_suffix, _ = variants[0]
    if not reading.endswith(key_suffix) or not surface.endswith(value_suffix):
        raise ValueError('基本形の語尾が選択した活用種類と一致しません。')
    key_stem = reading[:-len(key_suffix)] if key_suffix else reading
    value_stem = surface[:-len(value_suffix)] if value_suffix else surface
    result = set()
    import specialist_distribution as specialist
    for value_suffix, key_suffix, context_id in variants:
        key, value = key_stem + key_suffix, value_stem + value_suffix
        reason = specialist.invalid_reason(key, value, key, value)
        if reason: raise ValueError('配布形式で扱えない活用形: ' + reason + ': ' + key + ' / ' + value)
        result.add((key, context_id, context_id, COST, value))
    return [list(row) for row in sorted(result)]


def requests(root):
    paths = sorted((root / DIRECTORY / 'requests').glob('*.json'))
    if not paths: return []
    allowed = {'system', *categories(root)}
    id_count = len((root / 'src/main/resources/id.def').read_text().splitlines())
    result = []
    for path in paths:
        entry = json.loads(path.read_text())
        if (entry.get('schemaVersion') != 1 or entry.get('author') != OWNER
                or type(entry.get('issue')) is not int or entry['issue'] <= 0
                or entry.get('issueUrl') != f'https://github.com/{REPOSITORY}/issues/{entry["issue"]}'
                or not re.fullmatch('[a-f0-9]{64}', entry.get('bodySha256', ''))
                or not re.fullmatch('[0-9]{8}T[0-9]{12}Z', entry.get('submitted', ''))
                or not entry.get('operations')):
            raise ValueError('Invalid feedback request: ' + str(path))
        seen = set()
        for op in entry['operations']:
            pair = text(op.get('reading'), 'reading'), text(op.get('surface'), 'surface')
            identity = op.get('dictionary'), *pair
            if op.get('dictionary') not in allowed or op.get('action') not in ('add', 'exclude') or identity in seen:
                raise ValueError('Invalid or duplicate feedback operation')
            seen.add(identity)
            for field in ('baselineRecords', 'records'):
                if not isinstance(op.get(field), list): raise ValueError('Missing feedback records')
                for row in op[field]:
                    if (not isinstance(row, list) or len(row) != 5
                            or row[0] != pair[0] or row[4] != pair[1]
                            or any(type(row[i]) is not int for i in (1, 2, 3))
                            or not all(0 <= row[i] < id_count for i in (1, 2))
                            or not -32768 <= row[3] <= 32767):
                        raise ValueError('Invalid feedback POS/cost/identity')
            if op['action'] == 'add' and not op['records']: raise ValueError('Empty feedback addition')
        result.append((str(path.relative_to(root)), entry))
    return result


def latest(root, dictionary=None):
    result = {}
    for _, request in requests(root):
        for op in request['operations']:
            if dictionary is None or op['dictionary'] == dictionary:
                result[(op['dictionary'], op['reading'], op['surface'])] = op
    return result


def system_document(root):
    selected = requests(root)
    additions, exclusions = set(), set()
    for (_, reading, surface), op in latest(root, 'system').items():
        if op['action'] == 'exclude': exclusions.add((reading, surface))
        else: additions.update(tuple(row) for row in op['records'])
    return dict(schemaVersion=1, idDefSha256=digest(root / 'src/main/resources/id.def'),
                requests={path: digest(root / path) for path, _ in selected},
                additions=[list(row) for row in sorted(additions)], exclusions=[list(pair) for pair in sorted(exclusions)])


def write_system(root):
    (root / DIRECTORY / 'system.json').write_text(encode(system_document(root)), encoding='utf-8')


def verify(root):
    pos_rules(root)
    expected = encode(system_document(root))
    path = root / DIRECTORY / 'system.json'
    if not path.exists() or path.read_text() != expected:
        raise ValueError('Feedback system data/history changed: regenerate with dictionary_feedback.py materialize')


def specialist_rows(root, records, existing):
    """Apply to source-derived rows; leave upstream snapshots untouched."""
    rows = {tuple(row) for row in records}
    for (target, reading, surface), op in latest(root).items():
        if target not in ('categories/kampo', 'categories/medical'): continue
        category = target.split('/')[1]
        if op['action'] == 'exclude':
            rows = {row for row in rows if not (row[0] == category and row[1] == reading and row[5] == surface)}
            continue
        if (reading, surface) in existing:
            raise ValueError('Specialist feedback conflicts with existing dictionary: ' + reading + ' / ' + surface)
        if any(row[1] == reading and row[5] == surface and row[0] != category for row in rows):
            raise ValueError('Specialist feedback conflicts with another specialist category')
        # Existing source POS/cost are retained; a new pair can have multiple POS records.
        if not any(row[0] == category and row[1] == reading and row[5] == surface for row in rows):
            rows.update((category, str(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4])) for r in op['records'])
    return sorted(rows)
