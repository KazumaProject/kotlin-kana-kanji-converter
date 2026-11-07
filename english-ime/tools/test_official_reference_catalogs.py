import unittest
import lexicon_pipeline as pipeline
import official_reference_catalogs as catalog
import test_lexicon_pipeline as fixtures


class OfficialReferenceTests(unittest.TestCase):
    def test_command_names_come_from_complete_article_labels_and_exact_namespaces(self):
        text=('<a href="/tools/outside">outside</a><div class="devsite-article-body clearfix">'
              '<dt><code><a href="/studio/command-line/tool">tool</a></code></dt>'
              '<a href="https://other.test/tools/evil">evil</a>'
              '<a href="/tools/wrong">partial</a><a href="/tools/Tool">Tool</a></div>'
              '<a href="/kotlin/multiplatform">Kotlin Multiplatform</a>')
        parser=catalog.Catalog('android');parser.feed(text)
        self.assertEqual({('tool','command_name'),('Kotlin Multiplatform','technology_name')},
                         {(r['label'],r['kind']) for r in parser.records})

    def test_complete_card_headings_preserve_full_names_and_program_type(self):
        azure=catalog.Catalog('azure');azure.feed('<div class="card"><div class="card-body"><h3 class="h5">Example Functions Plus</h3></div></div><h3 class="h5">Unrelated footer</h3>')
        jmi=catalog.Catalog('jmi');jmi.feed('<a class="box-lnk" href="/programs/ethno"><h3 class="title">Ethno</h3></a><h3 class="title">Unrelated news</h3>')
        self.assertEqual(['Example Functions Plus'],[r['label'] for r in azure.records])
        self.assertEqual([('Ethno','program_name')],[(r['label'],r['kind']) for r in jmi.records])

    def test_case_sensitive_commands_and_literal_manual_name_presentations_stay_distinct(self):
        facts=[dict(label=label,kind=kind,url='https://example.org/index',snapshotSha256='a'*64)
               for label,kind in [('tool','command_name'),('Example Functions','technology_name'),('Ethno','program_name')]]
        values=['tool','Tool','ExampleFunctions','ExampleFunction','ethno']
        rows=[dict(id=('raw:' if value=='ethno' else 'manual:')+str(i),surface=value,reading=value.lower(),cost=100)
              for i,value in enumerate(values)]
        model=pipeline.Lexicon(fixtures.SEED);corrections=[];catalog.attach(model,rows,facts,corrections)
        self.assertEqual({'identifier_command_prefix','domain_technology'},model.members[next(iter(model.approved['tool'])),'tool'])
        self.assertFalse(model.approved.get('Tool'));self.assertFalse(model.approved.get('ExampleFunction'))
        key=next(iter(model.approved['ExampleFunctions']));proof=model.evidence[key,'ExampleFunctions'][0]
        self.assertFalse(proof['externallyAttestedAliasSpellingClaimed'])
        members=model.members[next(iter(model.approved['Ethno'])),'Ethno']
        self.assertEqual({'noun','noun_proper','domain_entertainment'},members)
        self.assertNotIn('name_product',members);self.assertEqual(('Ethno',),pipeline.correction_targets(corrections,rows,model)['raw:4'])
        model.validate()

    def test_unknown_reference_type_is_not_silently_treated_as_a_name(self):
        with self.assertRaises(ValueError):catalog.attach(pipeline.Lexicon(fixtures.SEED),[],[dict(label='Bad',kind='unknown')],[])


if __name__=='__main__':unittest.main()
