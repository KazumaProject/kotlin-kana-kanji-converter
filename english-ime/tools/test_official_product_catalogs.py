import unittest
import official_product_catalogs as p
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class OfficialCatalogTests(unittest.TestCase):
    def test_product_selectors_ignore_logos_marketing_and_footer_headings(self):
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
