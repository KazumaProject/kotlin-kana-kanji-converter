import unittest
from restricted_references import disqualified_roles
from test_resolve_wiktionary import entry


class RestrictedReferenceTests(unittest.TestCase):
    def test_old_lemma_restriction_follows_explicit_same_role_form_chain(self):
        rows = [(1, entry('oldroot', 'noun', [{'tags': ['obsolete']}])),
                (2, entry('oldspelling', 'noun', [{'alt_of': [{'word': 'oldroot'}]}])),
                (3, entry('oldforms', 'noun', [{'form_of': [{'word': 'oldspelling'}], 'tags': ['plural']}])),
                (4, entry('oldforms', 'verb', [{'tags': ['archaic']}]))]
        words, proofs = disqualified_roles(rows)
        self.assertEqual({'oldroot', 'oldspelling', 'oldforms'}, words)
        self.assertEqual(['oldspelling', 'noun'], proofs['oldforms', 'noun'][0]['target'])

    def test_modern_sense_missing_entry_errors_wrong_role_and_cycles_are_preserved(self):
        rows = [(1, entry('oldroot', 'noun', [{'tags': ['obsolete']}])),
                (2, entry('mixedroot', 'noun', [{'tags': ['obsolete']}, {}])),
                (3, entry('modernform', 'noun', [{'form_of': [{'word': 'mixedroot'}]}])),
                (4, entry('missingform', 'noun', [{'form_of': [{'word': 'missing'}]}])),
                (5, entry('wrongrole', 'verb', [{'alt_of': [{'word': 'oldroot'}]}])),
                (6, entry('broken', 'noun', [{'tags': ['obsolete', 'no-gloss']}])),
                (7, entry('cyclea', 'noun', [{'alt_of': [{'word': 'cycleb'}]}])),
                (8, entry('cycleb', 'noun', [{'alt_of': [{'word': 'cyclea'}]}])),
                (9, entry('multiple', 'noun', [{'alt_of': [{'word': 'oldroot'}, {'word': 'missing'}]}]))]
        words, _ = disqualified_roles(rows)
        self.assertEqual({'oldroot'}, words)


if __name__ == '__main__':
    unittest.main()
