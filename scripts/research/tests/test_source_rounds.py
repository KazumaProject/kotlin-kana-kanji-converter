import pathlib
import sqlite3
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import source_rounds as s
import worker as w


class SourceRoundsTest(unittest.TestCase):
    def proof(self, rows=None):
        rows = rows or [{'id': 'candidate', 'reading': 'やまだ', 'surface': '山田'}]
        h, n = s.cohort_hash(rows)
        tracker = s.CorpusRoundTracker(h, n, 'a' * 64)
        tracker.observe('subject', '山田', 123, '山田（やまだ）', matches=1)
        tracker.observe('named-binding', '山田', 123, '山田（やまだ）', matches=1)
        return tracker.finish(eof=True, source_checksum_verified=True, main_articles_scanned=1)

    def test_parenthetical_after_online_prefix_limit(self):
        text = '前文。' * 6000 + "\n'''山田'''（やまだ）は人物である。"
        pairs = list(s.full_body_reading_bindings(text))
        self.assertIn(('山田', 'やまだ', "'''山田'''（やまだ"), pairs)

    def test_explicit_names_are_whole_not_substrings(self):
        pairs = list(s.full_body_reading_bindings("'''井上太郎'''（いのうえたろう）は人物である。"))
        self.assertEqual(['井上太郎'], [name for name, _, _ in pairs])
        self.assertNotIn('太郎', [name for name, _, _ in pairs])

    def test_multiple_readings_stay_bound_to_the_same_written_name(self):
        pairs = list(s.full_body_reading_bindings("'''山田'''（やまだ、またはやまた）。"))
        self.assertEqual({'やまだ', 'やまた'}, {y for name, y, _ in pairs if name == '山田'})

    def test_quoted_work_title_reading_remains_whole_and_literal(self):
        for text in ("「'''一緒に'''」（いっしょに）は歌。", "'''「一緒に」'''（いっしょに）は歌。", '『一緒に』（いっしょに）は歌。'):
            with self.subTest(text=text):
                pairs=list(s.full_body_reading_bindings(text))
                self.assertTrue(any(name=='一緒に' and reading=='いっしょに' and quote in text for name,reading,quote in pairs))
                self.assertFalse(any(name=='緒に' for name,reading,quote in pairs))

    def test_full_body_ruby_is_literal(self):
        text = '前文。' * 6000 + '\n{{ruby|山田|やまだ}}'
        self.assertIn(('山田', 'やまだ', '{{ruby|山田|やまだ}}'), list(s.full_body_reading_bindings(text)))

    def test_mention_does_not_acquire_subject_category_target(self):
        self.assertEqual(('別の記事#mentioned-name:山田', 'mentioned-name'),
                         s.binding_target('別の記事', "'''別の記事'''について。\n山田（やまだ）も登場する。", '山田', 'Q1'))

    def test_explicit_article_primary_name_binds_subject(self):
        self.assertEqual(('Q1', 'primary-name'), s.binding_target('山田 (俳優)', "'''山田'''（やまだ）は俳優。", '山田', 'Q1'))

    def test_declared_primary_alias_can_bind_subject(self):
        text = '{{人物|名前=田中|芸名=山田}}\n' + "'''田中'''（たなか）は人物。"
        self.assertEqual(('Q1', 'declared-primary-alias'), s.binding_target('田中', text, '山田', 'Q1'))

    def test_another_person_infobox_alias_cannot_bind_subject(self):
        text = '{{人物|名前=別の人物|芸名=山田}}\n' + "'''田中'''（たなか）は人物。"
        self.assertEqual(('田中#mentioned-name:山田', 'mentioned-name'), s.binding_target('田中', text, '山田', 'Q1'))

    def test_later_quoted_alias_template_cannot_bind_subject(self):
        text = "'''田中'''（たなか）は人物。\n== 資料 ==\n{{引用|名前=田中|別名=山田}}"
        self.assertFalse(s.alias_of_primary_subject('田中', text, '山田'))

    def test_many_mentions_compute_primary_scope_only_once(self):
        s.page_scope.cache_clear()
        text = "'''田中'''（たなか）は人物。山田（やまだ）、鈴木（すずき）。"
        with mock.patch.object(w, 'wiki_lead', wraps=w.wiki_lead) as parse_lead:
            for _ in range(10):
                s.binding_target('田中', text, '山田', 'Q1')
                s.binding_target('田中', text, '鈴木', 'Q1')
            self.assertEqual(1, parse_lead.call_count)

    def test_two_distinct_strategies_are_required(self):
        proof = self.proof()
        self.assertEqual({'subject', 'named-binding'}, {v['strategy'] for v in proof['rounds']})
        self.assertNotEqual(proof['rounds'][0]['strategySha256'], proof['rounds'][1]['strategySha256'])

    def test_partial_scan_cannot_complete_rounds(self):
        t = s.CorpusRoundTracker('a' * 64, 1, 'b' * 64)
        t.observe('subject', '山田', 1, 'text')
        with self.assertRaises(ValueError):
            t.finish(eof=False, source_checksum_verified=True, main_articles_scanned=1)
        with self.assertRaises(ValueError):
            t.finish(eof=True, source_checksum_verified=True, main_articles_scanned=1)

    def test_all_main_articles_must_receive_both_searches(self):
        t = s.CorpusRoundTracker('a' * 64, 1, 'b' * 64)
        for key in s.STRATEGIES:
            t.observe(key, '山田', 1, 'text')
        with self.assertRaises(ValueError):
            t.finish(eof=True, source_checksum_verified=True, main_articles_scanned=2)

    def test_parsing_failure_is_not_negative_source_coverage(self):
        t = s.CorpusRoundTracker('a' * 64, 1, 'b' * 64)
        for key in s.STRATEGIES:
            t.observe(key, '山田', 1, 'text')
        t.failure('別の記事', ValueError('Unsupported content'))
        with self.assertRaises(ValueError):
            t.finish(eof=True, source_checksum_verified=True, main_articles_scanned=1)

    def test_different_article_streams_cannot_complete(self):
        t = s.CorpusRoundTracker('a' * 64, 1, 'b' * 64)
        t.observe('subject', '山田', 1, 'text')
        t.observe('named-binding', '別の記事', 1, 'text')
        with self.assertRaises(ValueError):
            t.finish(eof=True, source_checksum_verified=True, main_articles_scanned=1)

    def test_recording_completed_search_does_not_decide_or_clear_failures(self):
        db = sqlite3.connect(':memory:'); db.row_factory = sqlite3.Row; db.executescript(w.SCHEMA)
        one = w.insert_candidate(db, 'やまだ', '山田', 1, 1, 10)
        two = w.insert_candidate(db, 'たなか', '田中', 1, 1, 10)
        db.execute("UPDATE candidates SET state='needs_review' WHERE id=?", (one,))
        db.execute("UPDATE candidates SET state='blocked',error='parser failed' WHERE id=?", (two,))
        rows = list(db.execute('SELECT id,reading,surface FROM candidates ORDER BY id'))
        result = s.record_completed_rounds(db, self.proof(rows))
        self.assertEqual(0, result['qualityDecisionsMade'])
        self.assertEqual(('needs_review', 2, None), tuple(db.execute('SELECT state,research_round,error FROM candidates WHERE id=?', (one,)).fetchone()))
        self.assertEqual(('blocked', 0, 'parser failed'), tuple(db.execute('SELECT state,research_round,error FROM candidates WHERE id=?', (two,)).fetchone()))
        db.close()

    def test_other_cohort_cannot_receive_completed_rounds(self):
        db = sqlite3.connect(':memory:'); db.row_factory = sqlite3.Row; db.executescript(w.SCHEMA)
        w.insert_candidate(db, 'たなか', '田中', 1, 1, 10)
        with self.assertRaisesRegex(ValueError, 'another candidate cohort'):
            s.record_completed_rounds(db, self.proof())
        db.close()


if __name__ == '__main__':
    unittest.main()
