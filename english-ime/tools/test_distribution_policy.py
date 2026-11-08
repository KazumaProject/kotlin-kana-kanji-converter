from pathlib import Path
import tempfile
import unittest
import hashlib

import distribution_policy as d
import catalog_review as review


class DistributionPolicyTest(unittest.TestCase):
    def test_removed_named_analysis_can_leave_an_independent_ordinary_homonym(self):
        row=dict(target_id='r',lexeme_id='restricted-name',surface='python',lemma='Python',kind='person')
        normal=dict(lexeme_id='ordinary-word',lemma='python')
        review.verify_rows([row],{},{('python','python')},{'python':[normal]},{'exact:Python'})
        with self.assertRaisesRegex(ValueError,'lexical analysis leaked'):
            review.verify_rows([row],{},{('python','python')},{'python':[normal,dict(lexeme_id='restricted-name',lemma='Python')]},{'exact:Python'})
        with self.assertRaisesRegex(ValueError,'orphan'):
            review.verify_rows([row],{},{('python','python')},{},{'exact:Python'})

    def test_exact_proper_names_and_hashed_keys_preserve_lowercase_homonyms(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'policy.tsv'
            records=[dict(surface=hashlib.sha256(b'She').hexdigest(),match='sha256-exact',reason='victim-person',
                evidence='https://www.wikidata.org/wiki/Property:P1196',license='CC0-1.0'),
                dict(surface='Belladonna',match='exact',reason='adult-industry-person',evidence='https://example.org/person',license='CC-BY-SA-3.0'),
                dict(surface='literal "quotation"',match='casefold',reason='sexual-slang',evidence='https://example.org/word',license='CC-BY-SA-4.0')]
            d.write(p,records);self.assertEqual(records,d.rows(p));keys=d.keys(p)
            for s in ['She','Belladonna','literal "quotation"']:self.assertTrue(d.excluded(s,s,keys))
            for s in ['she','belladonna','shell']:self.assertFalse(d.excluded(s,s,keys))
            self.assertNotIn('She',p.read_text())

    def test_explicit_exclusion_preserves_authoring_and_is_not_a_substring_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'policy.tsv';p.write_text('surface\tmatch\treason\tevidence\tlicense\nrestricted\tcasefold\tsexual-slang\thttps://example.org\tCC-BY-SA-4.0\n')
            keys=d.keys(p)
            self.assertTrue(d.excluded('Restricted','Restricted',keys))
            self.assertTrue(d.excluded('restricted form','restricted',keys))
            self.assertFalse(d.excluded('unrestricted','unrestricted',keys))
            self.assertFalse(d.excluded('contraception','contraception',keys))
            self.assertEqual(1,len(d.rows(p)))

    def test_legacy_adoption_record_is_allowed_only_when_restricted_data_is_absent(self):
        row=dict(target_id='r',lexeme_id='l',surface='restricted',lemma='restricted',kind='person')
        review.verify_rows([row],{},set(),{}, {'fold:restricted'})
        with self.assertRaisesRegex(ValueError,'leaked'):
            review.verify_rows([row],{}, {('restricted','restricted')},{}, {'fold:restricted'})
