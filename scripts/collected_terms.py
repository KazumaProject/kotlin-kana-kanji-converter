"""Offline validation of source-backed vocabulary facts shared by collection and builds."""
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

DIRECTORY = Path('src/main/specialist/collected-terms')
METHODS = {'kana_surface', 'parenthesized', 'ruby', 'fields'}


def reading(value):
    value = unicodedata.normalize('NFKC', value.strip())
    value = ''.join(chr(ord(c) - 0x60) if '\u30a1' <= c <= '\u30f6' else c for c in value)
    return unicodedata.normalize('NFC', re.sub(r'[\s・]', '', value))


def surface(value):
    return unicodedata.normalize('NFC', value.strip())


def validate(entry, category=None):
    for key in ('reading', 'surface', 'category', 'source_id', 'source_url', 'source_sha256',
                'source_surface', 'source_reading', 'checked_on', 'evidence_method'):
        value = entry.get(key)
        if not isinstance(value, str) or not value or any(unicodedata.category(c).startswith('C') for c in value):
            raise ValueError('Invalid collected term field: ' + key)
    if entry['category'] not in ('kampo', 'product') or category and entry['category'] != category:
        raise ValueError('Invalid collected term category')
    if (entry['evidence_method'] not in METHODS or not re.fullmatch('[ぁ-ゖー]+', entry['reading'])
            or reading(entry['source_reading']) != entry['reading']
            or surface(entry['source_surface']) != entry['surface']):
        raise ValueError('Collected term differs from its explicit reading/surface evidence')
    if entry['evidence_method'] == 'kana_surface' and (
            entry['source_reading'] != entry['source_surface']
            or not re.fullmatch(r'[ぁ-ゖァ-ヶー\s・]+', entry['source_surface'])):
        raise ValueError('Kana surface evidence must contain only kana')
    url = urlsplit(entry['source_url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password:
        raise ValueError('Invalid collected term source URL')
    if not re.fullmatch('[0-9a-f]{64}', entry['source_sha256']):
        raise ValueError('Invalid collected term source hash')
    if date.fromisoformat(entry['checked_on']).isoformat() != entry['checked_on']:
        raise ValueError('Invalid collected term confirmation date')
    return entry


def load(root):
    for path in sorted((root / DIRECTORY).glob('*.jsonl')):
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            yield path, number, validate(json.loads(line), 'kampo')


def digest(entries):
    return hashlib.sha256(encode(entries)).hexdigest()


def encode(entries):
    return ''.join(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
                   for e in entries).encode('utf-8')
