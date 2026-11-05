import unittest
import manual_named_aliases as n
import extend_lexicon as e
import lexicon_pipeline as p
import test_lexicon_pipeline as f


class ManualNamedAliasTests(unittest.TestCase):
    def fixture(self,canonical='Fixture Product',surface='FixtureProduct',relation='case_space'):
        row=dict(id='manual:1',surface=surface,reading='fixtureproduct',cost=700)
        review=dict(row,canonical=canonical,separatorRelation=relation,reviewer='implementation_agent',rationale='Complete original literal presentation of the same independently documented name.')
        return row,review,{(row['reading'],surface,700):42}

    def test_original_literal_name_keeps_identity_mapping_cost_and_no_attestation_claim(self):
        model=p.Lexicon(f.SEED);model.add('product','Fixture Product','Fixture Product',{'noun','noun_proper','name_product'},
            {'source':'official_product_label','url':'https://example.org/product'},approved=True)
        row,review,literals=self.fixture();n.attach(model,[row],[review],literals)
        self.assertEqual({'product'},model.approved['FixtureProduct'])
        self.assertEqual('Fixture Product',model.forms['product','FixtureProduct']['lemma'])
        self.assertFalse(model.evidence['product','FixtureProduct'][0]['externallyAttestedAliasSpellingClaimed'])
        self.assertIn(('fixtureproduct','FixtureProduct'),{(r['source'],r['target']) for r in model.relations if r['relation']=='input_alias'})
        self.assertEqual(700,row['cost']);model.validate()
        with self.assertRaises(ValueError):n.attach(model,[row],[dict(review,cost=701)],literals)

    def test_hyphen_boundaries_need_explicit_review_and_nouns_commands_or_api_types_cannot_supply_name(self):
        for values in [{'noun'},{'identifier_command_line'},{'identifier_programming_api'},{'noun','noun_proper'}]:
            model=p.Lexicon(f.SEED);e.ensure_categories(model,values);model.add('fixture','Fixture-Product','Fixture-Product',values,
                {'source':'curated_seed','url':'https://example.org/fixture'},approved=True)
            row,review,literals=self.fixture('Fixture-Product','Fixture Product','reviewed_space_hyphen')
            with self.assertRaises(ValueError):n.attach(model,[row],[review],literals)
        model=p.Lexicon(f.SEED);model.add('product','Fixture-Product','Fixture-Product',{'noun','noun_proper','name_product'},
            {'source':'official_product_label','url':'https://example.org/product'},approved=True)
        n.attach(model,[row],[review],literals)
        with self.assertRaises(ValueError):n.attach(model,[row],[dict(review,separatorRelation='case_space')],literals)
        for wrong in ['Fixture Product Plus','Fixture-Product+','FixtureProduct']:
            with self.assertRaises(ValueError):n.attach(model,[row],[dict(review,canonical=wrong)],literals)

    def test_identity_input_does_not_add_an_invalid_self_relation(self):
        model=p.Lexicon(f.SEED);model.add('product','Fixture Product','Fixture Product',{'noun','noun_proper','name_product'},
            {'source':'official_product_label','url':'https://example.org/product'},approved=True)
        row=dict(id='manual:1',reading='fixture-product',surface='fixture-product',cost=700)
        review=dict(row,canonical='Fixture Product',separatorRelation='reviewed_space_hyphen',reviewer='implementation_agent',rationale='Existing literal separated name presentation.')
        n.attach(model,[row],[review],{('fixture-product','fixture-product',700):42})
        self.assertTrue(model.approved['fixture-product'])
        self.assertFalse(any(r['source']==r['target'] for r in model.relations));model.validate()


if __name__=='__main__':unittest.main()
