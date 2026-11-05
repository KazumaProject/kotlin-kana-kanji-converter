import unittest
import official_product_catalogs as p
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class OfficialCatalogTests(unittest.TestCase):
    def reference_fixture(self):
        return {'microsoft-docs.html':'<a href="/en-us/outside/">Outside</a><section id="listings-section"><h2>Product directory</h2>'
            '<a href="/en-us/complete-product/">Complete <b>Product</b></a><a href="https://other.example/">Untrusted</a></section>'
            '<a href="/en-us/footer/">Footer</a>',
            'nikon-compact.html':'<h1 class="c-heading-a">Compact Digital Cameras (FIXTURE Series)</h1><h3>FIXTURE P999</h3>',
            'rockwell-trademarks-web.txt':'https://www.rockwellautomation.com/en-us/company/about-us/legal-notices/trademarks.html\n'
            'This list is a subset of trademarks owned and used by Rockwell Automation\nL1: CompleteMark^{®}\nL2: OtherMark™\n'
            'L3: ModelMark™ Micro\nL4: WrappedMark^{®\nL1: CompleteMark^{®}\n'}

    def test_reference_catalog_uses_scoped_complete_directory_series_and_trademark_rows(self):
        records=p.reference_records(self.reference_fixture())
        self.assertEqual({'Complete Product','FIXTURE','CompleteMark','OtherMark','WrappedMark'},{r['label'] for r in records})
        self.assertEqual(1,len([r for r in records if r['label']=='CompleteMark']))
        self.assertFalse(any(r['label']=='ModelMark' for r in records))
        for change in [('microsoft-docs.html','<a href="/en-us/tool/">Invented</a>'),
                       ('nikon-compact.html','<h1 class="c-heading-a">Compact Digital Cameras (FIXTURE P999 Series)</h1>')]:
            texts=self.reference_fixture();texts[change[0]]=change[1]
            with self.assertRaises(ValueError):p.reference_records(texts)

    def test_trademark_is_not_automatically_a_product_and_has_no_morphology(self):
        records=p.reference_records(self.reference_fixture());model=pipeline.Lexicon(fixtures.SEED)
        p.attach(model,[dict(id='manual:1',surface='CompleteMark'),dict(id='manual:2',surface='CompleteProduct')],records)
        key=next(iter(model.approved['CompleteMark']))
        self.assertEqual({'noun','noun_proper','name_brand','domain_technology'},model.members[key,'CompleteMark'])
        self.assertNotIn('name_product',model.members[key,'CompleteMark']);self.assertTrue(model.approved['CompleteProduct']);model.validate()

    def manufacturer_fixture(self):
        return '<div class="ds-brand-card" id="SOLIDWORKS" data-href="/products/solidworks"><div><img class="ds-list-of-brands-brand-logo" alt="SOLIDWORKS Logo"></div></div>'

    def test_brand_card_name_requires_its_own_explicit_corroborating_label(self):
        html=self.manufacturer_fixture();asus='<h2 class="seriesName">Zenfone</h2>'
        records=p.manufacturer_records(html,asus)
        self.assertEqual({'SOLIDWORKS','Zenfone'},{r['label'] for r in records})
        for bad in [html.replace('SOLIDWORKS Logo','Invented Logo'),html.replace('id="SOLIDWORKS"','id="Other"'),
                    '<img class="ds-list-of-brands-brand-logo" alt="SOLIDWORKS Logo">']:
            with self.assertRaises(ValueError):p.manufacturer_records(bad,asus)

    def test_complete_series_headings_never_extract_product_names_from_slugs_or_model_parts(self):
        records=p.manufacturer_records(self.manufacturer_fixture(),
            '<h2 class="seriesName">Zenfone</h2><h2 class="seriesName">Complete Phone Ultra</h2>'
            '<a href="/phones/invented/">Learn more</a><h2>Invented</h2><p>Marketing Phone</p>')
        self.assertEqual({'SOLIDWORKS','Zenfone','Complete Phone Ultra'},{r['label'] for r in records})
        self.assertNotIn('Complete Phone',{r['label'] for r in records})

    def test_brand_and_product_memberships_keep_literal_manual_case_without_english_inflections(self):
        records=p.manufacturer_records(self.manufacturer_fixture(),'<h2 class="seriesName">Zenfone</h2>')
        model=pipeline.Lexicon(fixtures.SEED)
        p.attach(model,[dict(id='manual:1',surface='SolidWorks'),dict(id='tsv:1',surface='solidworks')],records)
        key=next(iter(model.approved['SOLIDWORKS']))
        self.assertEqual({'noun','noun_proper','name_product','name_brand','domain_technology'},model.members[key,'SOLIDWORKS'])
        self.assertTrue(model.approved['SolidWorks']);self.assertFalse(model.approved.get('solidworks'))
        self.assertFalse(model.approved.get('SolidWork'));model.validate()

    def technology_index(self):
        identifier='doc://com.apple.documentation/documentation/CoreML'
        return dict(kind='technologies',identifier=dict(url='doc://com.apple.welcome-experience-documentation/documentation/technologies'),
            metadata=dict(title='Technologies'),references={identifier:dict(identifier=identifier,title='Core ML',
                kind='symbol',role='collection',type='topic',url='/documentation/coreml')})

    def test_official_technology_fields_keep_complete_names_and_ignore_descriptions(self):
        index=self.technology_index();index['references']['article']=dict(kind='article',role='article',title='Invented Framework')
        records=p.technology_records('<div class="owa4Ee other">Cloud SQL</div><div title="Invented Product">Marketing</div>',index)
        self.assertEqual({'Cloud SQL','Core ML'},{r['label'] for r in records})
        model=pipeline.Lexicon(fixtures.SEED)
        p.attach(model,[dict(id='manual:1',surface='CoreML'),dict(id='manual:2',surface='CloudSQL'),dict(id='manual:3',surface='Core')],records)
        self.assertTrue(model.approved['CoreML']);self.assertTrue(model.approved['CloudSQL']);self.assertFalse(model.approved.get('Core'))
        model.validate()

    def test_technology_identity_mismatch_cannot_become_a_product_name(self):
        for change in [dict(url='/documentation/coreml/factory'),dict(identifier='doc://other/CoreML')]:
            index=self.technology_index();key=next(iter(index['references']));index['references'][key].update(change)
            with self.assertRaises(ValueError):p.technology_records('',index)

    def test_product_selectors_ignore_logos_marketing_and_footer_headings(self):
        firebase=p.Labels('firebase');firebase.feed('<div class="content__title">Remote Config</div><div class="content__body">Invented Product</div>')
        self.assertEqual(['Remote Config'],[r['label'] for r in firebase.records])
        google=p.Labels('google');google.feed('<h2>Marketing</h2><img alt="Invented logo"><p class="product-filter__card-description">Verified <b>Product</b></p><p>Marketing copy</p>')
        self.assertEqual(['Verified Product'],[r['label'] for r in google.records])
        jet=p.Labels('jetbrains');jet.feed('<h3>Tool A</h3><h3>Filters</h3><h3>Company</h3>')
        self.assertEqual(['Tool A'],[r['label'] for r in jet.records])

    def test_no_guessed_short_name_and_manual_space_free_variant_is_explicit(self):
        model=pipeline.Lexicon(fixtures.SEED)
        record={'label':'Mac Studio','sourceFile':'web-excerpts.txt','url':'https://www.apple.com/sitemap/','snapshotKind':'public_web_extraction_not_raw_html'}
        p.attach(model,[{'id':'manual:1','surface':'MacStudio'},{'id':'tsv:1','surface':'macstudio'},{'id':'manual:2','surface':'Studio'}],[record])
        self.assertTrue(model.approved.get('MacStudio'));self.assertFalse(model.approved.get('macstudio'));self.assertFalse(model.approved.get('Studio'))
        model.validate()


if __name__=='__main__':unittest.main()
