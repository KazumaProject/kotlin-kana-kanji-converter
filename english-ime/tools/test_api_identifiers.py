import unittest
import zlib
import api_identifiers as api
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class PublicApiIdentifierTests(unittest.TestCase):
    def test_android_index_accepts_qualified_types_and_rejects_other_links(self):
        index=api.AndroidTypes();index.feed('<a href="/reference/android/widget/FixtureView">FixtureView</a>'
            '<a href="/reference/android/widget/FixtureView#method">method</a>'
            '<a href="/reference/android/widget/package-summary">package</a>'
            '<a href="https://example.org/reference/android/widget/Other">Other</a>')
        self.assertEqual({('FixtureView','android.widget.FixtureView','https://developer.android.com/reference/android/widget/FixtureView')},index.types)

    def test_python_inventory_keeps_qualified_class_and_expands_sphinx_anchor(self):
        header=b'# Sphinx inventory version 2\n# Project: Python\n# Version: 3.14\n# compressed\n'
        data=b'fixture.Coroutine py:class 1 library/fixture.html#$ -\nfixture.run py:function 1 library/fixture.html#$ -\n'
        self.assertEqual([('Coroutine','fixture.Coroutine','https://docs.python.org/3.14/library/fixture.html#fixture.Coroutine')],list(api.python_types(header+zlib.compress(data))))

    def test_exact_manual_type_keeps_multiple_contexts_and_no_ordinary_lexical_pos(self):
        model=pipeline.Lexicon(fixtures.SEED)
        rows=[{'id':'manual:1','surface':'FixtureView'},{'id':'manual:2','surface':'fixtureview'},{'id':'tsv:1','surface':'CorpusView'}]
        records=[('FixtureView','one.FixtureView','https://example.org/one','fixture'),
            ('FixtureView','two.FixtureView','https://example.org/two','fixture'),
            ('CorpusView','one.CorpusView','https://example.org/three','fixture')]
        self.assertEqual({'FixtureView'},api.attach(model,rows,records))
        self.assertEqual(2,len(model.approved['FixtureView']))
        for key in model.approved['FixtureView']:
            self.assertEqual({'identifier_programming_api','domain_technology'},model.members[key,'FixtureView'])
        self.assertFalse(model.approved.get('fixtureview'));self.assertFalse(model.approved.get('CorpusView'))
        model.validate()


if __name__=='__main__':unittest.main()
