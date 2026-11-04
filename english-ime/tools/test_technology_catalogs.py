import unittest
import technology_catalogs as t
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class CatalogTests(unittest.TestCase):
    def test_catalog_identifiers_keep_raw_manual_case_without_preferred_casing_or_pos(self):
        model=pipeline.Lexicon(fixtures.SEED)
        rows=[{'id':'manual:1','surface':'JupyterLab'},{'id':'tsv:1','surface':'jupyterlab'},{'id':'tsv:2','surface':'JUPYTERLAB'}]
        t.attach(model,rows,[{'name':'jupyterlab','altnames':[]}],[])
        key=next(iter(model.approved['JupyterLab']))
        self.assertEqual({'identifier_software_catalog','domain_technology'},model.members[key,'JupyterLab'])
        self.assertTrue(model.approved.get('jupyterlab'));self.assertFalse(model.approved.get('JUPYTERLAB'))
        self.assertFalse(model.approved.get('JupyterLabs'));model.validate()

    def test_aws_labels_and_manual_space_free_aliases_only_no_invented_aws_abbreviation(self):
        model=pipeline.Lexicon(fixtures.SEED)
        rows=[{'id':'manual:1','surface':'AmazonEC2'},{'id':'manual:2','surface':'AWSEC2'},{'id':'tsv:1','surface':'AmazonEC2'}]
        service={'archiveMember':'fixture/service-2.json.gz','memberSha256':'fixture','metadata':{'serviceId':'EC2','serviceFullName':'Amazon Elastic Compute Cloud','serviceAbbreviation':'Amazon EC2'}}
        t.attach(model,rows,[],[service]);key=next(iter(model.approved['AmazonEC2']))
        self.assertEqual('Amazon Elastic Compute Cloud',model.forms[key,'AmazonEC2']['lemma'])
        self.assertFalse(model.approved.get('AWSEC2'));self.assertFalse(model.approved.get('AmazonEC2s'));model.validate()
        self.assertEqual(1,len(model.evidence[key,'AmazonEC2']))

    def test_homebrew_package_and_executable_identities_are_distinct(self):
        formulas=[dict(name='fixturepkg',full_name='fixturepkg',aliases=['fxalias'],oldnames=[],executables=['fixturecmd'],homepage='https://example.org',post_install='never evaluate this')]
        records=t.homebrew_records(formulas,[])
        model=pipeline.Lexicon(fixtures.SEED)
        rows=[dict(id='tsv:1',surface='fixturepkg'),dict(id='manual:1',surface='fixturecmd'),dict(id='tsv:2',surface='fxalias')]
        t.attach_homebrew(model,rows,records)
        package=next(iter(model.approved['fixturepkg']));command=next(iter(model.approved['fixturecmd']))
        self.assertEqual({'identifier_software_catalog','domain_technology'},model.members[package,'fixturepkg'])
        self.assertEqual({'identifier_command_line','domain_technology'},model.members[command,'fixturecmd'])
        self.assertNotEqual(package,command);self.assertTrue(model.approved['fxalias']);model.validate()
        self.assertTrue(all('post_install' not in row for row in records))

    def test_homebrew_display_names_keep_manual_alias_scope_and_no_name_guess_from_slug(self):
        records=t.homebrew_records([], [dict(token='fixture-app',full_token='fixture-app',old_tokens=[],name=['Fixture App'],homepage='https://example.org')])
        model=pipeline.Lexicon(fixtures.SEED)
        rows=[dict(id='manual:1',surface='FixtureApp'),dict(id='manual:2',surface='Fixture App'),dict(id='tsv:1',surface='fixtureapp')]
        t.attach_homebrew(model,rows,records)
        self.assertTrue(model.approved['FixtureApp']);self.assertTrue(model.approved['Fixture App'])
        self.assertFalse(model.approved.get('fixtureapp'));self.assertFalse(model.approved.get('Fixture-App'))
        key=next(iter(model.approved['FixtureApp']))
        self.assertEqual({'noun','noun_proper','name_product','domain_technology'},model.members[key,'FixtureApp'])
        self.assertFalse(model.evidence[key,'FixtureApp'][0]['preferredVendorCaseClaimed']);model.validate()


if __name__=='__main__':unittest.main()
