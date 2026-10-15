import contextlib
from datetime import datetime, timedelta, timezone
import gzip
import io
import json
from pathlib import Path
import shutil
import unittest

import classified_distribution as distribution
import classification_reviews as reviews
import dictionary_feedback as feedback
import feedback_data as data
import specialist_distribution as specialist
import test_classified_distribution as fixtures

ROOT = Path(__file__).resolve().parent.parent


class FeedbackTest(unittest.TestCase):
    def setUp(self):
        fixtures.DistributionTest.setUp(self)
        shutil.copyfile(ROOT / 'src/main/resources/id.def', self.root / 'src/main/resources/id.def')
        shutil.copytree(ROOT / data.DIRECTORY / 'mozc', self.root / data.DIRECTORY / 'mozc')
        shutil.copyfile(ROOT / 'src/main/classification/categories.json', self.taxonomy)
        extra = self.root / 'src/main/specialist'; extra.mkdir(parents=True)
        shutil.copyfile(ROOT / 'src/main/specialist/categories.json', extra / 'categories.json')
        with contextlib.redirect_stdout(io.StringIO()):
            distribution.freeze(self.root, self.accepted, self.dispositions, self.database, self.manual, self.taxonomy)
        data.write_system(self.root)
        self.inventory = self.root / 'inventory.jsonl.gz'
        self.set_inventory([])
        self.now = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)

    def set_inventory(self, rows):
        with gzip.open(self.inventory, 'wt', encoding='utf-8') as stream:
            for target, reading, surface in rows:
                stream.write(json.dumps(dict(dictionary=target, reading=reading, surface=surface, rawSurface=surface,
                                             leftId=1, rightId=1, cost=1234)) + '\n')

    def issue(self, values, number=1, user=data.OWNER):
        return dict(number=number, html_url=f'https://github.com/{data.REPOSITORY}/issues/{number}',
                    user=dict(login=user), state='open', body='\n\n'.join(f'### {k}\n\n{v}' for k, v in values.items()))

    def addition(self, target='system', reading='ぐぐる', surface='ググる', profile='動詞ラ行五段', number=1):
        label = next(value for value in feedback.target_options(self.root) if value.endswith('(' + target + ')'))
        return self.issue({'申請の種類': feedback.ADD, '読み': reading, '表記': surface,
                           '追加先': label, '品詞・活用種類': profile}, number)

    def exclusion(self, reading, surface, target=feedback.SEARCH, number=1):
        return self.issue({'申請の種類': feedback.REPORT, '読み': reading, '表記': surface,
                           '希望する対応': '除外する', '対象辞書': target}, number)

    def prepare(self, issue):
        return feedback.prepare(self.root, issue, self.inventory, self.now)

    def test_exact_exclusion_preserves_river_and_case_variants_in_all_records(self):
        self.set_inventory([('categories/work_music', 'りばー', 'RIVER'), ('categories/term', 'りばー', 'River'),
                            ('system', 'りばーと', 'RIVERと'), ('system', 'りばーと', 'Riverと'),
                            ('system', 'りばーと', 'riverと')])
        for index, surface in enumerate(('RIVERと', 'Riverと'), 1):
            result = self.prepare(self.exclusion('りばーと', surface, number=index))
            self.assertEqual(result['status'], 'ready')
            self.assertEqual([(op['reading'], op['surface']) for op in result['operations']], [('りばーと', surface)])
        system = data.system_document(self.root)
        self.assertEqual(system['exclusions'], [['りばーと', 'RIVERと'], ['りばーと', 'Riverと']])
        self.assertFalse(list((self.root / reviews.DIRECTORY / 'reviews').glob('*.jsonl')))

    def test_missing_exact_candidate_does_not_strip_suffix_or_delete_river(self):
        self.set_inventory([('system', 'りばー', 'RIVER')])
        result = self.prepare(self.exclusion('りばーと', 'RIVERと'))
        self.assertEqual(result['status'], 'needs-triage')
        self.assertFalse(data.requests(self.root))
        self.assertEqual(data.system_document(self.root)['exclusions'], [])

    def test_all_31_destinations_accept_additions_and_materialize_classifications(self):
        for i, target in enumerate(['system', *data.categories(self.root)]):
            with self.subTest(target=target):
                result = self.prepare(self.addition(target, 'しんご', '新語' + str(i), '名詞', i + 1))
                self.assertEqual(result['status'], 'ready')
                self.assertEqual(result['operations'][0]['dictionary'], target)
        with contextlib.redirect_stdout(io.StringIO()):
            reviews.apply_saved(self.root, commit=True)
            distribution.verify(self.root)
        entries = reviews.load(self.root)
        self.assertEqual(len(entries), 28)
        self.assertEqual(len(data.requests(self.root)), 31)
        self.assertEqual(len(data.system_document(self.root)['additions']), 1)

    def test_inflection_expansion_matches_pinned_mozc_forms(self):
        for reading, surface, profile, expected in [
                ('ぐぐる', 'ググる', '動詞ラ行五段', ('ぐぐっ', 'ググっ')),
                ('たべる', '食べる', '動詞一段', ('たべ', '食べ')),
                ('けんさする', '検査する', '動詞サ変', ('けんさし', '検査し')),
                ('くる', '来る', '動詞カ変', ('こ', '来')),
                ('あたらしい', '新しい', '形容詞', ('あたらしく', '新しく'))]:
            with self.subTest(profile=profile):
                rows = data.expand(self.root, reading, surface, profile)
                self.assertIn(expected, {(r[0], r[4]) for r in rows})
                self.assertTrue(all(r[3] == 9000 for r in rows))
        with self.assertRaisesRegex(ValueError, '基本形'): data.expand(self.root, 'かく', '書く', '動詞ラ行五段')
        with self.assertRaises(ValueError): data.expand(self.root, 'わーど', 'ワド', '名詞')

    def test_multiple_pos_for_same_reading_survive_apply_and_refreeze(self):
        self.prepare(self.addition('categories/term', 'たべる', '食べる', '動詞一段'))
        with contextlib.redirect_stdout(io.StringIO()):
            reviews.apply_saved(self.root, commit=True)
            first = (self.root / reviews.DIRECTORY / 'distribution-candidates.tsv.gz').read_bytes()
            distribution.freeze(self.root, self.accepted, self.dispositions, self.database, self.manual, self.taxonomy)
            distribution.verify(self.root)
        self.assertEqual(first, (self.root / reviews.DIRECTORY / 'distribution-candidates.tsv.gz').read_bytes())
        self.assertTrue(any(len(reviews.records(e)) > 1 for e in reviews.load(self.root).values()))

    def test_idempotence_and_already_registered_preserve_pos_cost(self):
        issue = self.addition()
        self.prepare(issue)
        snapshot = {p: (self.root / p).read_bytes() for p, _ in data.requests(self.root)}
        self.assertEqual(self.prepare(issue)['status'], 'no-change')
        self.assertEqual(snapshot, {p: (self.root / p).read_bytes() for p, _ in data.requests(self.root)})
        self.set_inventory([('system', 'しんご', '新語')])
        self.assertEqual(self.prepare(self.addition('system', 'しんご', '新語', '名詞', 2))['status'], 'no-change')

    def test_edited_issue_appends_history(self):
        self.prepare(self.addition('system', 'しんご', '新語', '名詞'))
        self.prepare(self.addition('system', 'べつご', '別語', '名詞'))
        self.assertEqual(len(data.requests(self.root)), 2)
        self.assertEqual(len(data.system_document(self.root)['additions']), 2)

    def test_edit_back_to_previous_request_appends_instead_of_overwriting_history(self):
        addition = self.addition('system', 'しんご', '新語', '名詞')
        self.prepare(addition)
        first = self.root / data.requests(self.root)[0][0]; original = first.read_bytes()
        self.set_inventory([('system', 'しんご', '新語')])
        self.prepare(self.exclusion('しんご', '新語'))
        self.set_inventory([]); self.now += timedelta(seconds=1)
        self.assertEqual(self.prepare(addition)['status'], 'ready')
        self.assertEqual(len(data.requests(self.root)), 3)
        self.assertEqual(first.read_bytes(), original)
        self.assertEqual(data.system_document(self.root)['exclusions'], [])

    def test_owner_gate_duplicate_fields_and_raw_surface_mismatch(self):
        issue = self.addition(); issue['user']['login'] = 'someone'
        with self.assertRaisesRegex(ValueError, 'owner'): self.prepare(issue)
        issue = self.addition(); issue['body'] += '\n\n### 読み\n\nりばー'
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.prepare(issue)
        self.assertFalse(data.requests(self.root))
        self.assertEqual(data.normalize(' リバーと ', ' Riverと '), ('りばーと', 'Riverと'))
        for value in ('りばー\tと', 'りばー\nと', 'abc'):
            with self.assertRaises(ValueError): data.normalize(value, 'RIVERと')

    def test_history_and_pinned_rule_tampering_are_detected(self):
        self.prepare(self.addition()); data.verify(self.root)
        path = self.root / data.requests(self.root)[0][0]
        entry = json.loads(path.read_text()); entry['operations'][0]['records'][0][3] = -32000
        path.write_text(data.encode(entry))
        with self.assertRaisesRegex(ValueError, 'data/history'): data.verify(self.root)
        rules = self.root / data.DIRECTORY / 'mozc/cforms.def'; rules.write_text(rules.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'): data.pos_rules(self.root)

    def test_forms_options_are_generated_and_control_characters_cannot_be_commands(self):
        feedback.generate_forms(self.root); feedback.generate_forms(self.root, True)
        form = json.loads((self.root / '.github/ISSUE_TEMPLATE/dictionary-add.yml').read_text())
        target = next(f for f in form['body'] if f.get('id') == 'target')
        self.assertEqual(len(target['attributes']['options']), 31)
        # Shell metacharacters are ordinary surface data and are escaped in Markdown output.
        result = self.prepare(self.addition('system', 'しんご', '新語$(touch /tmp/nope)|<x>', '名詞'))
        self.assertEqual(result['status'], 'ready')
        rendered = feedback.report(result)
        self.assertIn('&#124;&lt;x&gt;', rendered)
        self.assertNotIn('<x>', rendered)

    def test_specialist_manual_addition_and_exact_exclusion_keep_other_pairs(self):
        # Request history applies to source-derived specialist rows and keeps POS variants.
        self.set_inventory([('categories/medical', 'りばーと', 'Riverと'), ('categories/medical', 'りばー', 'River')])
        self.prepare(self.exclusion('りばーと', 'Riverと'))
        self.prepare(self.addition('categories/medical', 'しんご', '新語', '名詞', 2))
        rows = [('medical', 'りばーと', '1', '1', '1', 'Riverと'), ('medical', 'りばー', '1', '1', '1', 'River')]
        actual = data.specialist_rows(self.root, rows, {})
        self.assertIn(rows[1], actual); self.assertNotIn(rows[0], actual)
        self.assertTrue(any(row[1] == 'しんご' for row in actual))
        with self.assertRaisesRegex(ValueError, 'conflicts'): data.specialist_rows(self.root, rows, {('しんご', '新語'): {'system'}})

    def test_category_specific_exclusion_preserves_other_memberships(self):
        self.set_inventory([('categories/person', 'い', '乙'), ('categories/place', 'い', '乙')])
        target = next(v for v in feedback.target_options(self.root) if v.endswith('(categories/person)'))
        self.prepare(self.exclusion('い', '乙', target))
        with contextlib.redirect_stdout(io.StringIO()):
            reviews.apply_saved(self.root, commit=True); distribution.verify(self.root)
        with gzip.open(self.root / reviews.DIRECTORY / 'distribution-candidates.tsv.gz', 'rt') as stream:
            pairs = [line.rstrip('\n').split('\t') for line in stream]
        self.assertFalse(any(r[0] == 'person' and r[1] == 'い' and r[5] == '乙' for r in pairs))
        self.assertTrue(any(r[0] == 'place' and r[1] == 'い' and r[5] == '乙' for r in pairs))

    def test_reviewed_term_addition_can_be_excluded_without_erasing_its_evidence(self):
        path = self.root / distribution.TERM_ADDITIONS_PATH
        path.write_text('しんご\t1\t1\t9000\t新語\thttps://example.com/term\t2026-10-15\n')
        original = path.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            distribution.freeze(self.root, self.accepted, self.dispositions, self.database, self.manual, self.taxonomy)
        self.set_inventory([('categories/term', 'しんご', '新語')])
        self.prepare(self.exclusion('しんご', '新語'))
        with contextlib.redirect_stdout(io.StringIO()):
            reviews.apply_saved(self.root, commit=True)
            distribution.freeze(self.root, self.accepted, self.dispositions, self.database, self.manual, self.taxonomy)
            distribution.verify(self.root)
        self.assertEqual(path.read_bytes(), original)
        with gzip.open(self.root / reviews.DIRECTORY / 'distribution-candidates.tsv.gz', 'rt') as stream:
            self.assertNotIn('新語', stream.read())

    def test_specialist_full_freeze_replays_manual_inflections_and_exclusions(self):
        directory = self.root / 'src/main/specialist'
        (directory / 'sources').mkdir(); (directory / 'notices').mkdir()
        (directory / 'sources.json').write_text(json.dumps(dict(sources=[dict(id='kampo', category='kampo'), dict(id='manbyo', category='medical')])))
        for name, reading, surface in [('kampo', 'かんぽう', '漢方'), ('manbyo', 'しんだん', '診断')]:
            (directory / 'sources' / (name + '.jsonl.gz')).write_bytes(specialist.compressed_json([dict(row=2, reading=reading, surface=surface)]))
        index = self.root / 'existing-pairs.jsonl.gz'; index.write_bytes(specialist.compressed_json([]))
        self.set_inventory([('categories/medical', 'しんだん', '診断')])
        self.prepare(self.exclusion('しんだん', '診断'))
        self.prepare(self.addition('categories/medical', 'たべる', '食べる', '動詞一段', 2))
        with contextlib.redirect_stdout(io.StringIO()):
            specialist.freeze(self.root, index); specialist.verify(self.root, index)
            first = (directory / 'distribution-candidates.tsv.gz').read_bytes()
            specialist.freeze(self.root, index); specialist.verify(self.root, index)
        self.assertEqual(first, (directory / 'distribution-candidates.tsv.gz').read_bytes())
        manifest = json.loads((directory / 'distribution-manifest.json').read_text())
        self.assertGreater(manifest['dictionaryRows'], manifest['uniqueAdmittedPairs'])
        self.assertGreater(manifest['readingOrigins']['user_confirmation'], 0)
        with gzip.open(directory / 'distribution-candidates.tsv.gz', 'rt') as stream:
            self.assertNotIn('診断', stream.read())
        import write_classified_dictionary_catalog as catalog
        summary = catalog.generate(self.root, self.root / 'catalog')
        medical = next(item for item in summary['categories'] if item['id'] == 'medical')
        self.assertGreater(medical['records'], medical['pairs'])


if __name__ == '__main__': unittest.main()
