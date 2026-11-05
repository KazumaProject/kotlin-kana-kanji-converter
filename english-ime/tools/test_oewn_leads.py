import io
import unittest

import lexicon_pipeline as pipeline
import oewn_leads as oewn
import test_lexicon_pipeline as fixtures


class OewnLeadTests(unittest.TestCase):
    def test_sense_specific_leads_never_approve_usage_case_or_inflections(self):
        xml = b'''<LexicalResource><Lexicon language="en"><LexicalEntry id="entry-1">
        <Lemma writtenForm="Fixture" partOfSpeech="n"/><Sense id="person" synset="s1"/>
        <Sense id="place" synset="s2"/></LexicalEntry><LexicalEntry id="entry-2">
        <Lemma writtenForm="saw" partOfSpeech="v"/><Form writtenForm="saws"/>
        <Sense id="verb" synset="s3"/></LexicalEntry>
        <Synset id="s1" lexfile="noun.person"><SynsetRelation relType="instance_hypernym" target="person"/></Synset>
        <Synset id="s2" lexfile="noun.location"><SynsetRelation relType="hypernym" target="place"/></Synset>
        <Synset id="s3" lexfile="verb.contact"/></Lexicon></LexicalResource>'''
        entries, synsets = oewn.extract(io.BytesIO(xml), {'fixture', 'saw'})
        model = pipeline.Lexicon(fixtures.SEED)
        pending = []
        counts = oewn.attach(model, [{'id': '1', 'surface': 'fixture'}, {'id': '2', 'surface': 'saw'}], entries, synsets, pending)
        self.assertEqual(3, counts['senseLeads'])
        new = {key: cats for key, cats in model.members.items() if key[0].startswith('oewn-')}
        self.assertEqual(3, len(new))
        self.assertIn({'noun', 'noun_proper', 'name_person'}, new.values())
        self.assertIn({'noun'}, new.values())
        self.assertIn({'verb'}, new.values())
        self.assertFalse(any('verb_base' in cats or 'verb_past' in cats or 'verb_past_participle' in cats for cats in new.values()))
        self.assertFalse(model.approved.get('Fixture'))
        self.assertTrue(all(not item['wordAccepted'] for item in pending))
        self.assertFalse(any(row['relation'] == 'capitalization' and row['target'] == 'Fixture' for row in model.relations))
        model.validate()

    def test_missing_source_synset_cannot_be_silently_imported(self):
        xml = b'<LexicalResource><LexicalEntry id="entry"><Lemma writtenForm="fixture" partOfSpeech="n"/><Sense id="x" synset="missing"/></LexicalEntry></LexicalResource>'
        with self.assertRaisesRegex(ValueError, 'Missing OEWN synset'):
            oewn.extract(io.BytesIO(xml), {'fixture'})


if __name__ == '__main__':
    unittest.main()
