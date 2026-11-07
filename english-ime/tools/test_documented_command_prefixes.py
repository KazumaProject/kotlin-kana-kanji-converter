import unittest
import documented_command_prefixes as commands
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class DocumentedPrefixTests(unittest.TestCase):
    def test_explicit_multi_token_choices_and_bare_option_choices_are_literal(self):
        self.assertEqual(['-la','-l --all'],commands.literal_choices('[-la|-l --all]'))
        self.assertEqual(['--context','--before-context'],commands.literal_choices('--context|--before-context'))
        self.assertEqual([],commands.literal_choices('[arguments]'))
        self.assertEqual([],commands.literal_choices('[-l|$(secret)]'))
        values=list(commands.literal_prefixes('`ls {{[-la|-l --all]}}`\n'))
        self.assertEqual({'ls -la','ls -l --all'},{value[1] for value in values})

    def test_explicit_choices_and_quoted_argument_keep_literal_prefix_only(self):
        values = list(commands.literal_prefixes('`git commit {{[-m|--message]}} "{{message}}"`\n`git add {{path}}`\n'))
        self.assertEqual({'git commit -m', 'git commit --message', 'git add'}, {value[1] for value in values})
        self.assertTrue(all(value[3] for value in values))

    def test_no_variable_substitution_option_combining_or_token_fragment(self):
        model = pipeline.Lexicon(fixtures.SEED)
        words = ['git commit -m', 'git commit -', 'git commit -am', 'git commit -m hello', 'npm run dev']
        rows = [{'id': 'manual:' + str(i), 'surface': word} for i, word in enumerate(words)]
        rows.append({'id': 'tsv:1', 'surface': 'git commit --message'})
        pages = [('pages/common/fixture.md', '`git commit {{[-m|--message]}} "{{message}}"`\n`npm run {{script_name}}`\n', 'fixture')]
        self.assertEqual({'git commit -m'}, commands.attach(model, rows, pages))
        key = next(iter(model.approved['git commit -m']))
        self.assertEqual({'identifier_command_prefix', 'domain_technology'}, model.members[key, 'git commit -m'])
        self.assertTrue(model.evidence[key, 'git commit -m'][0]['completionRequired'])
        for word in words[1:]: self.assertFalse(model.approved.get(word))
        self.assertFalse(model.approved.get('git commit --message'))
        model.validate()


if __name__ == '__main__': unittest.main()
