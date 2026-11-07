import unittest
import command_templates as commands
import lexicon_pipeline as pipeline
import test_lexicon_pipeline as fixtures


class CommandTemplateTests(unittest.TestCase):
    def test_existing_literal_parameter_value_is_syntactic_not_runtime_evidence(self):
        tokens,variables=next(commands.template_variants('npm run {{script_name}}'))
        self.assertEqual([{'parameter':'script_name','value':'dev'}],commands.instantiate(tokens,variables,'npm run dev'))
        self.assertIsNone(commands.instantiate(tokens,variables,'npm run --unknown'))
        self.assertIsNone(commands.instantiate(tokens,variables,'npm run dev; rm -rf'))
        self.assertIsNone(commands.instantiate(tokens,variables,'other run dev'))

    def test_options_are_not_invented_and_positional_arguments_are_not_reordered(self):
        variants=list(commands.template_variants('pnpm add {{module_name}} {{[-D|--save-dev]}}'))
        self.assertTrue(any(commands.instantiate(t,v,'pnpm add fixture -D') for t,v in variants))
        self.assertFalse(any(commands.instantiate(t,v,'pnpm add -D') for t,v in variants))
        self.assertFalse(any(commands.instantiate(t,v,'pnpm add -D fixture') for t,v in variants))
        self.assertEqual([],list(commands.template_variants('cat {{file}} | grep {{pattern}}')))

    def test_only_manual_candidates_get_separate_identifier_categories(self):
        model=pipeline.Lexicon(fixtures.SEED)
        rows=[{'id':'manual:1','surface':'npm run dev'},{'id':'manual:2','surface':'rm -rf'},{'id':'tsv:1','surface':'npm run build'}]
        pages=[('pages/common/npm-run.md','`npm run {{script_name}}`\n','fixture')]
        sheets=[('rm','---\nsyntax: bash\n---\n# An example\nrm -rf <directory>\n','fixture')]
        self.assertEqual({'npm run dev','rm -rf'},commands.attach(model,rows,pages,sheets))
        self.assertFalse(model.approved.get('npm run build'))
        self.assertEqual({'identifier_command_template','domain_technology'},model.members[next(iter(model.approved['npm run dev'])),'npm run dev'])
        self.assertEqual({'identifier_command_prefix','domain_technology'},model.members[next(iter(model.approved['rm -rf'])),'rm -rf'])
        model.validate()

    def test_non_shell_cheatsheet_is_not_treated_as_a_command_document(self):
        self.assertEqual([],list(commands.cheat_examples('---\nsyntax: python\n---\nprint fixture\n')))


if __name__=='__main__':unittest.main()
