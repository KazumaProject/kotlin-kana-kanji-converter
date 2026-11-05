import json
import unittest
import zlib
import api_identifiers as api
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class PublicApiIdentifierTests(unittest.TestCase):
    def test_typescript_types_are_complete_global_declarations_not_comments_strings_or_nested_members(self):
        text='''/*\ninterface CommentFake {}\n*/
interface RegExp { source: string; }
declare var RegExp: RegExpConstructor;
declare namespace Other {
interface NestedFake {}
}
type Example = `
interface StringFake {}
`;
interface RegExpExecArray extends Array<string> {}
'''
        records=list(api.typescript_types(text,'lib.es5.d.ts'))
        self.assertEqual({'RegExp','RegExpExecArray'},{r[0] for r in records})
        self.assertTrue(all(r[0]==r[1] and r[3]=='typescript_global_interface' for r in records))
        self.assertIn('#L4',next(r[2] for r in records if r[0]=='RegExp'))
        model=pipeline.Lexicon(fixtures.SEED)
        api.attach(model,[dict(id='manual:1',surface='RegExp')],records)
        key=next(iter(model.approved['RegExp']))
        self.assertEqual({'identifier_programming_api','domain_technology'},model.members[key,'RegExp'])

    def test_typescript_malformed_scope_or_unterminated_comment_is_not_a_valid_index(self):
        for text in ['/* interface Fake {}','declare namespace X {\ninterface Fake {}','}\ninterface Fake {}']:
            with self.assertRaises(ValueError):list(api.typescript_types(text,'lib.es5.d.ts'))

    def test_firebase_keeps_android_namespaces_and_explicit_swift_module_labels(self):
        index=api.FirebaseTypes();index.feed('<div class="devsite-nav-title-no-path"><span>FirebaseFeature</span></div>'
            '<a href="/docs/reference/android/com/google/firebase/auth/FirebaseAuth">FirebaseAuth</a>'
            '<a href="/docs/reference/swift/firebasefeature/api/reference/Classes/Feature/Nested">Nested</a>'
            '<a href="/docs/reference/swift/firebasefeature/api/reference/Functions/run">run</a>'
            '<a href="/docs/reference/android/com/google/firebase/auth/FirebaseAuth#method">method</a>'
            '<a href="https://other.test/docs/reference/android/com/google/firebase/auth/Invented">Invented</a>')
        records=list(index.records())
        self.assertEqual({'com.google.firebase.auth.FirebaseAuth','FirebaseFeature.Feature.Nested'},{r[1] for r in records})
        self.assertEqual({'FirebaseAuth','Feature.Nested'},{r[0] for r in records})

    def test_swift_namespace_is_not_guessed_from_a_url_slug(self):
        index=api.FirebaseTypes();index.feed('<a href="/docs/reference/swift/firebasefeature/api/reference/Classes/Feature">Feature</a>')
        self.assertFalse(list(index.records()))
        index.feed('<div class="devsite-nav-title-no-path">FirebaseFeature</div><div class="devsite-nav-title-no-path">FirebaseFEATURE</div>')
        with self.assertRaises(ValueError):list(index.records())

    def test_pending_lowercase_input_keeps_complete_documented_type_and_explicit_case_mapping(self):
        model=pipeline.Lexicon(fixtures.SEED)
        rows=[dict(id='tsv:1',surface='fixtureview',reading='fixtureview',cost=700),
            dict(id='tsv:2',surface='view',reading='view',cost=701),
            dict(id='tsv:3',surface='fixtureview',reading='different',cost=702),
            dict(id='manual:1',surface='fIxTuReViEw',reading='fixtureview',cost=703)]
        records=[('FixtureView','android.view.FixtureView','https://example.org/type','fixture')]
        corrections=[];api.attach(model,rows,records,{r['id'] for r in rows},corrections)
        self.assertEqual(('FixtureView',),pipeline.correction_targets(corrections,rows,model)['tsv:1'])
        self.assertEqual({'tsv:1'},{r['id'] for r in corrections})
        self.assertFalse(model.approved.get('view'));self.assertFalse(model.approved.get('fixtureview'))
        self.assertFalse(model.approved.get('fIxTuReViEw'))
        self.assertEqual({'identifier_programming_api','domain_technology'},model.members[next(iter(model.approved['FixtureView'])),'FixtureView'])

    def test_android_index_accepts_qualified_types_and_rejects_other_links(self):
        index=api.AndroidTypes();index.feed('<a href="/reference/android/widget/FixtureView">FixtureView</a>'
            '<a href="/reference/android/widget/FixtureView#method">method</a>'
            '<a href="javascript:/reference/android/widget/Invented">Invented</a>'
            '<a href="/reference/android/widget/package-summary">package</a>'
            '<a href="https://example.org/reference/android/widget/Other">Other</a>')
        self.assertEqual({('FixtureView','android.widget.FixtureView','https://developer.android.com/reference/android/widget/FixtureView')},index.types)

    def test_python_inventory_keeps_qualified_class_and_expands_sphinx_anchor(self):
        header=b'# Sphinx inventory version 2\n# Project: Python\n# Version: 3.14\n# compressed\n'
        data=b'fixture.Coroutine py:class 1 library/fixture.html#$ -\nfixture.run py:function 1 library/fixture.html#$ -\n'
        self.assertEqual([('Coroutine','fixture.Coroutine','https://docs.python.org/3.14/library/fixture.html#fixture.Coroutine')],list(api.python_types(header+zlib.compress(data))))

    def test_kotlin_index_retains_language_url_and_rejects_members_and_queries(self):
        index=api.AndroidTypes();index.feed('<a href="/reference/kotlin/androidx/compose/ui/text/input/ImeOptions">ImeOptions</a>'
            '<a href="/reference/kotlin/androidx/compose/ui/text/input/ImeOptions#copy">copy</a>'
            '<a href="/reference/kotlin/androidx/compose/ui/text/input/ImeOptions?query=other">other</a>')
        self.assertEqual({('ImeOptions','androidx.compose.ui.text.input.ImeOptions',
            'https://developer.android.com/reference/kotlin/androidx/compose/ui/text/input/ImeOptions')},index.types)

    def test_dokka_index_requires_whole_type_declaration_and_qualified_identity(self):
        entry=dict(name='interface SharedFlow<out T> : Flow<T> ',description='kotlinx.coroutines.flow.SharedFlow',
            location='kotlinx-coroutines-core/kotlinx.coroutines.flow/-shared-flow/index.html',searchKeys=['SharedFlow'])
        function=dict(entry,name='fun SharedFlow.asFlow()',location='kotlinx-coroutines-core/kotlinx.coroutines.flow/as-flow.html')
        self.assertEqual([('SharedFlow','kotlinx.coroutines.flow.SharedFlow',
            'https://kotlinlang.org/api/kotlinx.coroutines/'+entry['location'])],list(api.coroutine_types(json.dumps([entry,function]))))
        for changed in [dict(description='kotlinx.coroutines.flow.Other'),dict(location='../other/index.html'),dict(searchKeys=['Flow'])]:
            with self.assertRaises(ValueError):list(api.coroutine_types(json.dumps([dict(entry,**changed)])))

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
