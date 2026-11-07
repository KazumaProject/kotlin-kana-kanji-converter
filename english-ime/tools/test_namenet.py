import unittest
import namenet
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


def entry(word='Example', pos='n', target='oenn-oenn-Q123-n'):
    return {'attributes': {'id': 'oenn-Example-n'}, 'lemma': {'writtenForm': word, 'partOfSpeech': pos},
            'senses': [{'id': 'Example%pseudo:n:1', 'synset': target}]}


def synset(instance=True):
    return {'attributes': {'id': 'oenn-Q123-n', 'partOfSpeech': 'n', 'members': 'oenn-Example-n', 'lexfile': 'noun.person'},
            'relations': [{'relType': 'instance_hypernym', 'target': 'oenn-00007846-n'}] if instance else []}


def audit(member=True):
    return {'entryId': 'oenn-Example-n', 'senseId': 'Example%pseudo:n:1', 'originalTarget': 'oenn-oenn-Q123-n',
            'candidateTarget': 'oenn-Q123-n', 'targetExists': True, 'exactReverseMembership': member}


class NameNetTests(unittest.TestCase):
    def setUp(self):
        self.model = pipeline.Lexicon(fixtures.SEED)

    def test_namespace_repair_requires_independent_reverse_membership(self):
        result = namenet.attach(self.model, [entry()], {'oenn-Q123-n': synset()}, [audit()])
        self.assertEqual(1, result['namespaceRepairs'])
        key = next(iter(self.model.approved['Example']))
        self.assertEqual({'noun', 'noun_proper', 'name_person'}, self.model.members[key, 'Example'])
        self.assertEqual('oenn-oenn-Q123-n', self.model.evidence[key, 'Example'][0]['originalSynset'])
        self.model.validate()

    def test_missing_or_inconsistent_membership_cannot_approve_a_label(self):
        result = namenet.attach(self.model, [entry()], {'oenn-Q123-n': synset()}, [audit(False)])
        self.assertEqual(1, result['unverifiedReferences'])
        self.assertFalse(self.model.approved.get('Example'))
        broken = synset(); broken['attributes']['members'] = 'other-entry'
        with self.assertRaisesRegex(ValueError, 'reverse membership'):
            namenet.attach(self.model, [entry()], {'oenn-Q123-n': broken}, [audit()])

    def test_noun_labels_do_not_invent_proper_names_or_inflections(self):
        namenet.attach(self.model, [entry()], {'oenn-Q123-n': synset(False)}, [audit()])
        key = next(iter(self.model.approved['Example']))
        self.assertEqual({'noun'}, self.model.members[key, 'Example'])
        substance = synset(); substance['attributes']['lexfile'] = 'noun.substance'
        other = pipeline.Lexicon(fixtures.SEED)
        namenet.attach(other, [entry()], {'oenn-Q123-n': substance}, [audit()])
        self.assertEqual({'noun'}, other.members[next(iter(other.approved['Example'])), 'Example'])
        result = namenet.attach(self.model, [entry('verbfixture', 'v')], {}, [audit()])
        self.assertEqual(1, result['nonNounLeads'])
        self.assertFalse(self.model.approved.get('verbfixture'))


if __name__ == '__main__':
    unittest.main()
