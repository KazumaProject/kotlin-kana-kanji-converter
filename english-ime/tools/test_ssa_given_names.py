import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending
import ssa_given_names as names
import test_lexicon_pipeline as fixtures


class GivenNameTests(unittest.TestCase):
    def test_aggregate_retains_literal_case_and_witnesses_without_demographics(self):
        result = names.aggregate([(1880, 'McFixture', 5), (2017, 'McFixture', 7), (2000, 'Other', 8)])
        self.assertEqual(dict(name='McFixture', firstYear=1880, lastYear=2017,
            aggregateOccurrences=12, publishedRows=2, witnessRows=[0, 1]), result[0])
        self.assertNotIn('sex', result[0])
        self.assertNotIn('gender', result[0])

    def test_invalid_source_rows_are_rejected(self):
        for row in [(1879, 'Fixture', 5), (2018, 'Fixture', 5), (2000, '', 5), (2000, 'Fixture', 4), (2000, 'bad\tname', 5)]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                names.aggregate([row])

    def test_only_independent_literal_name_is_approved(self):
        model = pipeline.Lexicon(fixtures.SEED)
        count = names.attach(model, [{'surface': 'mcfixture'}], [dict(name='McFixture', aggregateOccurrences=5), dict(name='Unrelated')])
        self.assertEqual(1, count)
        self.assertTrue(model.approved['McFixture'])
        self.assertFalse(model.approved.get('mcfixture'))
        self.assertFalse(model.approved.get('Unrelated'))
        key = next(iter(model.approved['McFixture']))
        self.assertEqual({'noun', 'noun_proper', 'name_person'}, model.members[key, 'McFixture'])
        self.assertFalse(model.evidence[key, 'McFixture'][0]['individualPersonClaimed'])
        model.validate()

    def test_case_alternative_does_not_override_unresolved_exact_english_reading(self):
        model = pipeline.Lexicon(fixtures.SEED)
        names.attach(model, [{'surface': 'mcfixture'}], [dict(name='McFixture')])
        row = dict(id='tsv:1', surface='mcfixture', reading='mcfixture', cost=700)
        self.assertEqual([], resolve_pending.cases(model, [row], {'mcfixture'}))
        result = resolve_pending.cases(model, [row], set())
        self.assertEqual('McFixture', result[0]['target'])
        self.assertEqual('case_correction', result[0]['relation'])

    def test_materialization_preserves_standalone_name_admission(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model = pipeline.Lexicon(fixtures.SEED)
            row = dict(id='tsv:1', surface='McFixture', reading='mcfixture', cost=700)
            names.attach(model, [row], [dict(name='McFixture')])
            inventory = root / 'inventory.jsonl'
            pipeline.jsonl(inventory, [row])
            sources = dict(inventorySha256=pipeline.digest(inventory), seed={name:pipeline.digest(fixtures.SEED / (name + '.tsv')) for name in ['categories', 'forms', 'memberships', 'relations']})
            with contextlib.redirect_stdout(io.StringIO()):
                first = pipeline.publish(model, [row], inventory, root / 'base', sources, {}, [], allow_input_spellings=True)
                loaded, *_ = extension.load_base(root / 'base', fixtures.SEED)
                second = pipeline.publish(loaded, [row], inventory, root / 'second', sources, {}, [], allow_input_spellings=True)
            self.assertEqual(1, first['includedRows'])
            self.assertEqual(1, second['includedRows'])
            self.assertTrue(loaded.approved['McFixture'])


if __name__ == '__main__':
    unittest.main()
