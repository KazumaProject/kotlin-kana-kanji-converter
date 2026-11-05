import unittest
import official_product_catalogs as p
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class OfficialCatalogTests(unittest.TestCase):
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
