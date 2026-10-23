import contextlib
import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import collect_dictionary_terms as c
import collected_terms as terms
import classified_distribution as d
import specialist_distribution as s
import test_classified_distribution as fixtures
import test_specialist_distribution as specialist_fixtures


class ExtractionTest(unittest.TestCase):
    def setUp(self):
        self.spec = dict(id='official', category='product', kind='html', name_selector='.product',
                         urls=['https://example.com/products/'])
        self.metadata = dict(url=self.spec['urls'][0], sha256='a' * 64, checked_on='2026-10-23', encoding='utf-8')

    def extract(self, html, **options):
        return c.html_facts(html.encode(), dict(self.spec, **options), self.metadata)

    def test_kana_ruby_and_explicit_latin_reading_preserve_surfaces(self):
        rows, held, _ = self.extract('<p class="product">あずきのチカラ</p>'
                                    '<p class="product">LUMIX（ルミックス）</p>'
                                    '<p class="product"><ruby>新漢方<rt>しんかんぽう</rt></ruby>エキス</p>'
                                    '<p class="product">伊右衛門</p>')
        self.assertEqual([(r['reading'], r['surface']) for r in rows],
                         [('あずきのちから', 'あずきのチカラ'), ('るみっくす', 'LUMIX'), ('しんかんぽうえきす', '新漢方エキス')])
        self.assertEqual([r['surface'] for r in held], ['伊右衛門'])

    def test_category_parentheses_are_not_treated_as_a_brand_reading(self):
        rows, held, _ = self.extract('<p class="product">次亜塩素酸 空間除菌脱臭機（ジアイーノ）</p>'
                                    '<p class="product">LED照明器具（シーリングライトなど）</p>'
                                    '<p class="product">LUMIX（ルミックス） カメラ</p>'
                                    '<p class="product">エアコン</p>',
                                    allow_description=True, pair_surface_pattern='[A-Za-z][A-Za-z0-9 .+&-]*',
                                    allow_kana_surface=False)
        self.assertEqual([(r['reading'], r['surface']) for r in rows], [('るみっくす', 'LUMIX')])
        self.assertEqual(len(held), 3)

    def test_kana_sentinel_and_missing_ruby_reading_are_withheld(self):
        rows, held, _ = self.extract('<p class="product">ヴィーナス</p>'
                                    '<p class="product"><ruby>未知</ruby></p>'
                                    '<p class="product">ソープ（シャンプー）</p>')
        self.assertFalse(rows)
        self.assertEqual(len(held), 3)

    def test_pagination_stays_on_the_configured_host_and_path(self):
        _, _, links = self.extract('<p class="product">ブランド</p>'
                                   '<a href="/products/2.html#top">次</a>'
                                   '<a href="https://other.example/products/2.html">外部</a>'
                                   '<a href="/news/2.html">別</a>',
                                   follow_selector='a', follow_url_pattern=r'https://example.com/products/\d+\.html')
        self.assertEqual(links, ['https://example.com/products/2.html'])
        with self.assertRaisesRegex(ValueError, 'No product-name'):
            self.extract('<p>Page layout changed</p>')

    def test_partial_formula_reading_is_applied_only_to_the_extracted_formula(self):
        spec = dict(id='otc', category='kampo', items_path='data', surface_field='name', reading_field='kana',
                    surface_pattern=r'ツムラ漢方(?P<surface>.+?)(?:料)?エキス顆粒')
        raw = json.dumps({'data': [{'name': 'ツムラ漢方安中散料エキス顆粒', 'kana': 'あんちゅうさん'},
                                   {'name': 'ツムラの別製品', 'kana': 'べつせいひん'}]}).encode()
        rows, held, _ = c.json_facts(raw, spec, self.metadata)
        self.assertEqual([(r['reading'], r['surface']) for r in rows], [('あんちゅうさん', '安中散')])
        self.assertEqual(rows[0]['source_fields']['name'], 'ツムラ漢方安中散料エキス顆粒')
        self.assertEqual(len(held), 1)

    def test_known_source_spelling_conflict_is_withheld_without_silent_correction(self):
        rows, held, _ = self.extract('<p class="product">竹如温胆湯（ちくじょうんたんとう）</p>',
                                    withhold_surfaces={'竹如温胆湯': 'Official product document uses 茹'})
        self.assertFalse(rows)
        self.assertIn('source_spelling_conflict', held[0]['reason'])

    def test_batch_reextracts_the_hashed_source_and_rejects_forged_readings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'root'; root.mkdir()
            work = Path(directory) / 'cache'; (work / 'cache').mkdir(parents=True)
            raw = '<p class="product">ブランド</p>'.encode()
            metadata = dict(self.metadata, sha256=hashlib.sha256(raw).hexdigest())
            row = c.html_facts(raw, self.spec, metadata)[0][0]
            (work / 'cache' / (metadata['sha256'] + '.body')).write_bytes(raw)
            c.write_json(root / c.CONFIG, dict(schemaVersion=1, sources=[self.spec]))
            path = work / 'batch.json'
            batch = dict(schemaVersion=1, sourceConfigSha256=d.sha(root / c.CONFIG), records=[row])
            c.write_json(path, batch)
            c.validate_batch(root, work, path)
            batch['records'][0].update(reading='べつめい', source_reading='ベツメイ', evidence_method='fields')
            c.write_json(path, batch)
            with self.assertRaisesRegex(ValueError, 're-extracted'):
                c.validate_batch(root, work, path)
            batch['records'][0] = row
            c.write_json(path, batch)
            (work / 'cache' / (metadata['sha256'] + '.body')).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Missing/modified'):
                c.validate_batch(root, work, path)

    def test_exact_pair_dedup_keeps_different_spellings_and_blocks_existing_decisions(self):
        con = sqlite3.connect(':memory:')
        self.addCleanup(con.close)
        con.execute('CREATE TABLE pairs (reading,surface,reason)')
        con.execute('INSERT INTO pairs VALUES (?,?,?)', ('きぞん', '既存', 'existing_duplicate'))
        con.execute('INSERT INTO pairs VALUES (?,?,?)', ('ほりゅう', '保留', 'classification_conflict'))
        entries = [dict(reading=r, surface=w, category=cat, source_id='source') for r, w, cat in
                   [('きぞん', '既存', 'product'), ('ほりゅう', '保留', 'product'),
                    ('しんき', '新規', 'product'), ('しんき', '新規', 'kampo'), ('しんき', '新期', 'product')]]
        for e in entries:
            e['source_url'] = self.metadata['url']
        rows, held = c.select_new(entries, con)
        self.assertEqual({(r['category'], r['surface']) for r in rows}, {('kampo', '新規'), ('product', '新期')})
        self.assertEqual({r['reason'] for r in held}, {'existing_duplicate', 'classification_conflict', 'source_duplicate'})

    def test_active_sources_with_missing_urls_cannot_silently_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec = dict(self.spec); spec.pop('urls')
            c.write_json(root / c.CONFIG, dict(schemaVersion=1, sources=[spec]))
            with self.assertRaisesRegex(ValueError, 'at least one URL'):
                c.configuration(root)


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    class Response(io.BytesIO):
        def __init__(self, url, body=b'source'):
            super().__init__(body)
            from email.message import Message
            self.url = url
            self.headers = Message()
            self.headers['Content-Type'] = 'text/html; charset=utf-8'
            self.headers['ETag'] = 'v1'

    def test_resume_uses_checked_cached_bytes_and_retries_only_failures(self):
        cache = c.Cache(self.directory)
        first, second = 'https://example.com/1', 'https://example.com/2'
        with patch.object(c, 'urlopen', side_effect=[self.Response(first), HTTPError(second, 503, 'unavailable', {}, None)]):
            cache.fetch(first)
            with self.assertRaises(HTTPError): cache.fetch(second)
        resumed = c.Cache(self.directory, resume=True)
        with patch.object(c, 'urlopen', return_value=self.Response(second)) as request:
            self.assertEqual(resumed.fetch(first)[0], b'source')
            resumed.fetch(second)
            self.assertEqual(request.call_count, 1)
        body = next(self.directory.glob('*.body')); body.write_bytes(b'modified')
        with self.assertRaisesRegex(ValueError, 'Corrupted'):
            resumed.fetch(first)

    def test_conditional_refresh_uses_304_and_serializes_requests_to_one_host(self):
        url = 'https://example.com/1'
        cache = c.Cache(self.directory)
        with patch.object(c, 'urlopen', return_value=self.Response(url)):
            cache.fetch(url)
        with patch.object(c, 'urlopen', side_effect=HTTPError(url, 304, 'unchanged', {}, None)) as request:
            self.assertEqual(cache.fetch(url)[0], b'source')
            self.assertEqual(request.call_args.args[0].get_header('If-none-match'), 'v1')
        active = [0, 0]
        def respond(request, **kwargs):
            active[0] += 1; active[1] = max(active[1], active[0])
            time.sleep(.01)
            active[0] -= 1
            return self.Response(request.full_url, request.full_url.encode())
        with patch.object(c, 'urlopen', side_effect=respond), c.ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(cache.fetch, ['https://example.com/' + str(i) for i in range(2, 6)]))
        self.assertEqual(active[1], 1)

    def test_crawl_keeps_successful_page_when_the_next_page_fails(self):
        first, second = 'https://example.com/1', 'https://example.com/2'
        spec = dict(id='official', category='product', kind='html', urls=[first], name_selector='p',
                    follow_selector='a', follow_url_pattern=r'https://example.com/\d')
        body = '<p>ブランド</p><a href="/2">次</a>'.encode()
        cache = c.Cache(self.directory)
        with patch.object(c, 'urlopen', side_effect=[self.Response(first, body), HTTPError(second, 503, 'unavailable', {}, None)]):
            rows, held, failures, pages = c.collect_source(Path('.'), spec, cache)
        self.assertEqual([(r['reading'], r['surface']) for r in rows], [('ぶらんど', 'ブランド')])
        self.assertEqual((len(held), len(failures), pages), (0, 1, 2))
        self.assertEqual(failures[0]['url'], second)
        with patch.object(c, 'urlopen', return_value=self.Response(second, '<p>セカンド</p>'.encode())) as request:
            rows, _, failures, _ = c.collect_source(Path('.'), spec, c.Cache(self.directory, resume=True))
        self.assertEqual(len(rows), 2)
        self.assertFalse(failures)
        self.assertEqual(request.call_count, 1)


class ApplyTest(unittest.TestCase):
    def setUp(self):
        fixtures.DistributionTest.setUp(self)
        taxonomy = json.loads(self.taxonomy.read_text()); taxonomy['categories'][-1]['id'] = 'product'
        self.taxonomy.write_text(json.dumps(taxonomy))
        with contextlib.redirect_stdout(io.StringIO()):
            d.freeze(self.root, self.accepted, self.dispositions, self.database, self.manual, self.taxonomy)
        self.work_temp = tempfile.TemporaryDirectory(); self.addCleanup(self.work_temp.cleanup)
        self.work = Path(self.work_temp.name)
        directory = self.root / s.DIRECTORY
        (directory / 'sources').mkdir(parents=True)
        (directory / 'notices').mkdir()
        c.write_json(directory / 'categories.json', dict(categories=[dict(id='kampo'), dict(id='medical')]))
        c.write_json(directory / 'sources.json', dict(sources=[]))
        c.write_json(directory / 'reading-corrections.json', dict(schemaVersion=1, corrections=[]))
        self.fake_export(self.root, self.work / 'inventory.gz')
        with contextlib.redirect_stdout(io.StringIO()): s.freeze(self.root, self.work / 'inventory.gz')
        self.specs = [dict(id='product', category='product', kind='html', urls=['https://example.com/products/'], name_selector='p'),
                      dict(id='kampo', category='kampo', kind='html', urls=['https://example.com/kampo/'], name_selector='p')]
        c.write_json(self.root / c.CONFIG, dict(schemaVersion=1, sources=self.specs))
        (self.work / 'cache').mkdir()
        records = []
        for spec, raw in zip(self.specs, ['<p>テストブランド</p>', '<p>新漢方（しんかんぽう）</p>']):
            raw = raw.encode(); digest = hashlib.sha256(raw).hexdigest()
            (self.work / 'cache' / (digest + '.body')).write_bytes(raw)
            records += c.html_facts(raw, spec, dict(url=spec['urls'][0], sha256=digest, checked_on='2026-10-23'))[0]
        self.batch = self.work / 'batch.json'
        c.write_json(self.batch, dict(schemaVersion=1, sourceConfigSha256=d.sha(self.root / c.CONFIG), records=records))

    @staticmethod
    def fake_export(root, output, classified_directory=None, log=None):
        directory = classified_directory or root / 'src/main/classification'
        rows = []
        with gzip.open(directory / 'distribution-candidates.tsv.gz', 'rt') as stream:
            for line in stream:
                row = line.rstrip('\n').split('\t')
                rows.append(dict(dictionary='categories/' + row[0], reading=row[1], surface=row[5]))
        output.write_bytes(s.compressed_json(rows))

    def snapshot(self):
        return {str(p.relative_to(self.root)): d.sha(p) for folder in (c.reviews.DIRECTORY, Path(s.DIRECTORY))
                for p in (self.root / folder).rglob('*') if p.is_file()}

    def test_apply_both_families_then_reapply_adds_nothing(self):
        with patch.object(c, 'inventory_export', side_effect=self.fake_export), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(c.apply_batch(self.root, self.work, self.batch), 2)
            snapshot = self.snapshot()
            self.assertEqual(c.apply_batch(self.root, self.work, self.batch), 0)
            self.assertEqual(self.snapshot(), snapshot)
            d.verify(self.root)
            s.verify(self.root, self.root / 'build/specialist/existing-pairs.jsonl.gz')
        review = next((self.root / c.reviews.DIRECTORY / 'reviews').glob('collection-*.jsonl'))
        self.assertEqual(json.loads(review.read_text())['added_record']['cost'], 9400)
        self.assertTrue(list((self.root / terms.DIRECTORY).glob('*.jsonl')))

    def test_staged_export_failure_leaves_all_repository_inputs_unchanged(self):
        before = self.snapshot()
        def export(root, output, classified_directory=None, log=None):
            if classified_directory:
                raise RuntimeError('staged inventory failed')
            return self.fake_export(root, output, log=log)
        with patch.object(c, 'inventory_export', side_effect=export), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'staged inventory'):
                c.apply_batch(self.root, self.work, self.batch)
        self.assertEqual(self.snapshot(), before)

    def test_recover_validates_all_backups_before_restoring_any_file(self):
        target = self.root / s.DIRECTORY / 'sources.json'
        backup = self.work / 'backup/sources.json'; backup.parent.mkdir()
        backup.write_bytes(target.read_bytes())
        original = d.sha(backup)
        target.write_text('interrupted')
        other = self.root / s.DIRECTORY / 'categories.json'
        other_backup = self.work / 'backup/categories.json'; other_backup.write_bytes(other.read_bytes())
        other.write_text('also interrupted')
        journal = dict(root=str(self.root), files=[
            dict(path=str(target.relative_to(self.root)), backup=str(backup), sha256=original),
            dict(path=str(other.relative_to(self.root)), backup=str(other_backup), sha256='0' * 64)])
        c.write_json(self.work / 'apply-journal.json', journal)
        with self.assertRaisesRegex(ValueError, 'Invalid recovery backup'):
            c.recover(self.root, self.work)
        self.assertEqual(target.read_text(), 'interrupted')
        journal['files'][1]['sha256'] = d.sha(other_backup)
        c.write_json(self.work / 'apply-journal.json', journal)
        with contextlib.redirect_stdout(io.StringIO()): c.recover(self.root, self.work)
        self.assertEqual(d.sha(target), original)
        self.assertFalse((self.work / 'apply-journal.json').exists())

    def test_explicitly_excluded_pair_cannot_be_added_by_collection(self):
        raw = '<p>丁（え）</p>'.encode(); digest = hashlib.sha256(raw).hexdigest()
        (self.work / 'cache' / (digest + '.body')).write_bytes(raw)
        row = c.html_facts(raw, self.specs[0], dict(url=self.specs[0]['urls'][0], sha256=digest, checked_on='2026-10-23'))[0][0]
        c.write_json(self.batch, dict(schemaVersion=1, sourceConfigSha256=d.sha(self.root / c.CONFIG), records=[row]))
        before = self.snapshot()
        with patch.object(c, 'inventory_export', side_effect=self.fake_export):
            with self.assertRaisesRegex(ValueError, 'classification/exclusion'):
                c.apply_batch(self.root, self.work, self.batch)
        self.assertEqual(self.snapshot(), before)


class CollectedSpecialistTest(unittest.TestCase):
    def setUp(self):
        specialist_fixtures.SpecialistTest.setUp(self)

    def test_collected_kampo_precedes_medical_and_changed_or_removed_evidence_is_detected(self):
        self.source('kampo', [])
        self.source('manbyo', [('しんかんぽう', '新漢方')])
        self.source('hyakuyaku', [])
        path = self.root / terms.DIRECTORY / 'batch.jsonl'; path.parent.mkdir()
        entry = dict(category='kampo', reading='しんかんぽう', surface='新漢方', source_id='official',
                     source_url='https://example.com/', source_sha256='a' * 64, checked_on='2026-10-23',
                     source_surface='新漢方', source_reading='シンカンポウ', evidence_method='fields')
        path.write_bytes(terms.encode([entry]))
        with contextlib.redirect_stdout(io.StringIO()):
            s.freeze(self.root, self.inventory)
            s.verify(self.root, self.inventory)
        manifest = json.loads((self.directory / 'distribution-manifest.json').read_text())
        self.assertEqual(manifest['categoryRows'], {'kampo': 1, 'medical': 0})
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'Collected specialist terms changed'):
            s.verify_files(self.root)

    source = specialist_fixtures.SpecialistTest.source


if __name__ == '__main__':
    unittest.main()
