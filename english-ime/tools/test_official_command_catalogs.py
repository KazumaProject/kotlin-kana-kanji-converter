import unittest

import lexicon_pipeline as pipeline
import official_command_catalogs as commands
import test_lexicon_pipeline as fixtures


def sources():
    return {
        'helm-cli-index.html':'<a href="/docs/helm/helm_list">helm list</a><a href="https://other.test/docs/helm/helm_evil">helm evil</a>',
        'docker-cli-index.html':'<a href="/reference/cli/docker/compose/build/">docker compose build</a>',
        'yarn-cli-index.html':'<a href="/cli/install">yarn install</a><a href="/other">yarn invented</a>',
        'node-cli.html':'<a href="cli.html#version">-v, --version</a><a href="cli.html#eval">--eval=script</a>',
        'typescript-cli.html':'<tr name="noEmit"><td>--noEmit</td><td>boolean</td></tr><tr name="outDir"><td>--outDir</td><td>string</td></tr>',
        'yarn-cli-run.html':'yarn run &lt;scriptName&gt; ... Same thing, but without the &quot;run&quot; keyword: yarn test',
        'pnpm-cli-run.html':'pnpm run watch. pnpm watch is a shorthand. Only if not a pnpm command.',
        'pnpm-cli-commands.rs':'pub enum CliCommand {\n    #[clap(visible_aliases = ["up", "upgrade"])]\n    Update(UpdateArgs),\n    #[clap(external_subcommand)]\n    External(Vec<String>),\n}',
    }


class OfficialCommandTests(unittest.TestCase):
    def test_prefixes_use_exact_official_literals_without_flag_or_alias_invention(self):
        records,builtins,_=commands.records(sources());surfaces={r['surface'] for r in records}
        self.assertTrue({'helm list','docker compose build','node -v','node --version','tsc --noEmit','pnpm up'}<=surfaces)
        self.assertFalse(surfaces&{'helm evil','yarn invented','node --eval','tsc --outDir','docker build','pnpm external'})
        self.assertEqual({'update','up','upgrade'},builtins['pnpm'])

    def test_script_shorthand_keeps_builtin_precedence_and_no_existing_script_claim(self):
        model=pipeline.Lexicon(fixtures.SEED)
        values=['pnpm dev','pnpm update','yarn build','pnpm dev;remove','yarn -x','node --version']
        rows=[dict(id='manual:'+str(i),surface=v,reading=v,cost=100) for i,v in enumerate(values)]
        literals={(r['reading'],r['surface'],r['cost']):42 for r in rows}
        adopted=commands.attach(model,rows,sources(),literals)
        self.assertEqual({'pnpm dev','pnpm update','yarn build','node --version'},adopted)
        for surface,category in [('pnpm dev','identifier_command_template'),('pnpm update','identifier_command_prefix')]:
            key=next(iter(model.approved[surface]))
            self.assertEqual({category,'domain_technology'},model.members[key,surface])
            self.assertIn('no option combination, execution, project/script/package existence',model.evidence[key,surface][0]['scope'])
        model.validate()

    def test_unknown_shorthand_grammar_and_changed_literal_cannot_admit_rows(self):
        row=dict(id='manual:1',surface='yarn build',reading='yarn build',cost=100)
        model=pipeline.Lexicon(fixtures.SEED);changed=sources();changed['yarn-cli-run.html']='Unverified syntax'
        with self.assertRaises(ValueError):commands.attach(model,[row],changed,{('yarn build','yarn build',100):42})
        self.assertFalse(commands.attach(model,[row],sources(),{('yarn build','yarn build',99):42}))


if __name__=='__main__':unittest.main()
