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


if __name__=='__main__':unittest.main()
