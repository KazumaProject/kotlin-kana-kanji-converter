import contextlib
import copy
import io
import tempfile
import unittest
from pathlib import Path

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import reviewed_usage as usage
import test_lexicon_pipeline as fixtures


def witness(**kwargs):
    return dict(form='fixture', entryId=1, headword='unrelated verb', senseIndex=0, exampleIndex=0,
        quoteSha256='a' * 64, observed='Fixture', possessive=False, inKnownFullName=[],
        embeddedInIdentifier=False, contextBefore='the band ', contextAfter=' performed',
        exampleType='quotation', reference='2000, A, Example', **kwargs)


def named():
    return dict(form='fixture', decision='include_name', target='Fixture', categories=['noun', 'noun_proper'],
        reviewer='implementation_agent', rationale='Independent band name, not a component', witnesses=[witness()])


class UsageReviewTests(unittest.TestCase):
    def setUp(self):
        self.model = pipeline.Lexicon(fixtures.SEED)
        self.rows = [dict(id='tsv:1', surface='fixture', reading='fixture', cost=700)]

    def test_reviewed_name_keeps_its_own_role_not_containing_entry_role(self):
        corrections, excluded, audit = [], [], []
        usage.attach(self.model, self.rows, [named()], corrections, excluded, audit)
        key = next(iter(self.model.approved['Fixture']))
        self.assertEqual({'noun', 'noun_proper'}, self.model.members[key, 'Fixture'])
        self.assertEqual('Fixture', corrections[0]['target'])
        proof = self.model.evidence[key, 'Fixture'][0]
        self.assertFalse(proof['humanReviewClaimed'])
        self.assertNotIn('contextBefore', proof['witnesses'][0])

    def test_full_name_component_and_identifier_are_rejected(self):
        for field, value in [('inKnownFullName', ['Fixture Company']), ('embeddedInIdentifier', True)]:
            review = named()
            review['witnesses'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                usage.attach(self.model, self.rows, [review], [], [], [])

    def test_unattested_case_and_ordinary_morphology_are_rejected(self):
        for field, value in [('target', 'FIXTURE'), ('categories', ['noun', 'noun_proper', 'verb_base'])]:
            review = named()
            review[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                usage.attach(self.model, self.rows, [review], [], [], [])

    def test_existing_manual_case_is_kept_separate_from_preferred_source_case(self):
        row = dict(id='manual:1', surface='FIXTURE', reading='fixture', cost=700)
        usage.attach(self.model, [row], [named()], [], [], [])
        self.assertTrue(self.model.approved['FIXTURE'])
        self.assertTrue(self.model.approved['Fixture'])

    def test_named_and_punctuation_alternatives_preserve_both_candidates_and_citations(self):
        proof = dict(source='curated_seed', url='https://example.org/original-word')
        self.model.add('punctuated-word', 'fix-ture', 'fix-ture', {'noun'}, proof, approved=True)
        corrections = [dict(id='tsv:1', source='fixture', target='fix-ture', relation='input_spelling_correction', evidence=proof['url'])]
        usage.attach(self.model, self.rows, [named()], corrections, [], [])
        self.assertEqual({'Fixture', 'fix-ture'}, {row['target'] for row in corrections})
        self.assertTrue(all(row['relation']=='input_spelling_candidates' for row in corrections))
        self.assertEqual(proof['url'], next(row['evidence'] for row in corrections if row['target']=='fix-ture'))
        self.assertEqual(('Fixture', 'fix-ture'), pipeline.correction_targets(corrections, self.rows, self.model)['tsv:1'])

    def test_fragment_needs_positive_boundaries_two_quotes_and_no_valid_counterevidence(self):
        row = dict(id='tsv:1', surface='doesn', reading='doesn', cost=700)
        first = witness(); first.update(form='doesn', observed='doesn', contextAfter='′t work')
        second = copy.deepcopy(first); second['quoteSha256'] = 'b' * 64
        review = dict(form='doesn', decision='exclude_fragment', fragmentKind='negative_contraction_prefix',
            reviewer='implementation_agent', rationale='Token ends inside attested negative contraction', witnesses=[first, second])
        excluded, audit = [], []
        usage.attach(self.model, [row], [review], [], excluded, audit)
        self.assertEqual('malformed', excluded[0]['reason'])
        self.assertFalse(audit[0]['absenceOnlyExclusion'])
        review['witnesses'][1]['contextAfter'] = ' works'
        with self.assertRaises(ValueError):
            usage.attach(self.model, [row], [review], [], [], [])
        review['witnesses'][1]['contextAfter'] = '′t work'
        self.model.add('independent-name', 'Doesn', 'Doesn', {'noun', 'noun_proper'},
            dict(source='curated_seed', url='https://example.org/name'), approved=True)
        with self.assertRaises(ValueError):
            usage.attach(self.model, [row], [review], [], [], [])

    def test_single_or_duplicate_quotation_is_not_fragment_proof(self):
        review = dict(form='fixture', decision='exclude_fragment', fragmentKind='censored_word_suffix',
            reviewer='implementation_agent', rationale='fixture', witnesses=[witness(), witness()])
        with self.assertRaises(ValueError):
            usage.attach(self.model, self.rows, [review], [], [], [])

    def test_separate_occurrences_in_one_quotation_are_not_conflated(self):
        first = witness()
        second = copy.deepcopy(first)
        second.update(contextAfter=' Group', inKnownFullName=['fixture group'])
        self.assertNotEqual(usage.identity(first), usage.identity(second))

    def test_reviewed_admission_survives_materialization_without_promoting_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            corrections = []
            usage.attach(self.model, self.rows, [named()], corrections, [], [])
            inventory = root / 'inventory.jsonl'
            pipeline.jsonl(inventory, self.rows)
            sources = dict(inventorySha256=pipeline.digest(inventory), seed={name:pipeline.digest(fixtures.SEED / (name + '.tsv')) for name in ['categories', 'forms', 'memberships', 'relations']})
            with contextlib.redirect_stdout(io.StringIO()):
                pipeline.publish(self.model, self.rows, inventory, root / 'base', sources, {}, [], allow_input_spellings=True, corrections=corrections)
                loaded, *_ = extension.load_base(root / 'base', fixtures.SEED)
            self.assertTrue(loaded.approved['Fixture'])
            self.assertFalse(loaded.approved.get('fixture'))


if __name__ == '__main__':
    unittest.main()
