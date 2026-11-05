import unittest

import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures
import tldr_commands as tldr


class CommandEvidenceTests(unittest.TestCase):
    def test_templates_and_prose_do_not_establish_literal_commands(self):
        text = '# git status\n\n`git status`\n`git add {{path}}`\nProse: git branch\n```shell\nignored\n```\n'
        self.assertEqual([(1, 'git status', 'heading'), (3, 'git status', 'literal_example')], list(tldr.expressions(text)))

    def test_only_existing_manual_surfaces_get_identifier_membership_without_pos(self):
        model = pipeline.Lexicon(fixtures.SEED)
        rows = [{'id': 'manual:1', 'surface': 'git status'}, {'id': 'tsv:2', 'surface': 'new-command'},
                {'id': 'manual:2', 'surface': 'git add'}]
        pages = [('pages/common/git-status.md', '# git status\n`git add {{file}}`\n# new-command\n', 'fixture')]
        counts = tldr.attach(model, rows, pages)
        self.assertEqual(1, counts['heading'])
        self.assertTrue(model.approved['git status'])
        self.assertFalse(model.approved.get('git add'))
        self.assertFalse(model.approved.get('new-command'))
        key = next(iter(model.approved['git status']))
        self.assertEqual({'identifier_command_line', 'domain_technology'}, model.members[key, 'git status'])
        self.assertFalse(any(row['relation'] == 'input_alias' for row in model.relations))
        model.validate()


if __name__ == '__main__':
    unittest.main()
