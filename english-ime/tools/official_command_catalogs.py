"""Join existing manual literals to pinned official command catalogs and syntax.

Catalog names are prefixes, not claims of complete executable invocations.
Script shorthand is a syntax template, never proof of a project's scripts.
This module reads local sources only and never executes an imported command.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit

import extend_lexicon as extension
import lexicon_pipeline as pipeline
import manual_aliases

PNPM_REVISION='0470052291b2ba369be93a9b696e0a0097722ba5'
PINS={
    'helm-cli-index.html':'e6cb763d165e2fb23ba42a94022f1eddcb2a8aab5c8e6d9b3bea1ce9e6627d7e',
    'node-cli.html':'4c362482b8b797be6506c8da5247597a781ac90fe935b1742ba9bac024c24777',
    'typescript-cli.html':'a4b6fe67cc84b7c9b45413b877ce6399fa673e27f7c128bd2d86a2387a9de052',
    'docker-cli-index.html':'2513d7220c7782e8816064bf95e8087ffbaa984ac09f99131b8acf2e2b0d9bcd',
    'yarn-cli-index.html':'843af66085f827b60a5b1978dc0ddc078503bab81e4f983a4d92b9002a82e3b7',
    'yarn-cli-run.html':'b07f72c04ec34ee1c33df4cc09e3a8f267d95e0f1e6a4dc12a3c16a8f3c018f1',
    'pnpm-cli-run.html':'86ab1a5d7ae2f1127acfee3b1d721bfbe8f7e97d1bad6a7a27fede4dc14be660',
    'pnpm-cli-commands.rs':'ae2d5ecc1ea3b1efcf7b8e672cc2d26063dffbde97b6559d65589537afb59175',
    'node-LICENSE.txt':'3ebb7123f4d2b9b916338e11748380972d4339d66f54cb3258270f99bb62faf5',
    'typescript-LICENSE.txt':'d6239afa918961b465b07bf7411cbe34ff6685854f58553db7966f4881a0211f',
    'docker-LICENSE.txt':'089009c932d3cc296355e429fa9d6faf80ac89597da866e2424b4ea09add64b1',
    'yarn-LICENSE.txt':'238d933f5c226cc197bd1dae2ad0c468e157b4cba8ed844f81549ba6db777dc4',
    'pnpm-LICENSE.txt':'079f959308fbf90a7c8f82df8b3f9c52475c62e36738609222e1365df211a489',
    'pnpm-code-LICENSE.txt':'4b8e2a57502758b2d034ece9cabf19dd098c5609003ed8dbdafd085274f25bd9',
}
URLS={'helm-cli-index.html':'https://helm.sh/docs/helm/',
    'node-cli.html':'https://nodejs.org/docs/latest/api/cli.html',
    'typescript-cli.html':'https://www.typescriptlang.org/docs/handbook/compiler-options.html',
    'docker-cli-index.html':'https://docs.docker.com/reference/cli/docker/',
    'yarn-cli-index.html':'https://yarnpkg.com/cli',
    'yarn-cli-run.html':'https://yarnpkg.com/cli/run',
    'pnpm-cli-run.html':'https://pnpm.io/cli/run',
    'pnpm-cli-commands.rs':'https://github.com/pnpm/pnpm/blob/'+PNPM_REVISION+'/pnpm/crates/cli/src/cli_args/cli_command/commands.rs'}


class Facts(HTMLParser):
    def __init__(self):
        super().__init__();self.active=[];self.links=[];self.rows=[];self.text=[];self.row=None;self.cell=None

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='a':self.active.append((attrs.get('href',''),[]))
        if tag=='tr':self.row=(attrs,[])
        if tag in {'td','th'} and self.row is not None:self.cell=[]

    def handle_data(self,data):
        self.text.append(data)
        for _,value in self.active:value.append(data)
        if self.cell is not None:self.cell.append(data)

    def handle_endtag(self,tag):
        if tag=='a' and self.active:
            href,value=self.active.pop();self.links.append((href,' '.join(''.join(value).split())))
        if tag in {'td','th'} and self.cell is not None:
            self.row[1].append(' '.join(''.join(self.cell).split()));self.cell=None
        if tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None;self.cell=None


def pnpm_names(text):
    """Read the complete frozen clap enum, including explicit aliases."""
    if 'pub enum CliCommand {' not in text:raise ValueError('Missing command enum')
    body=text.split('pub enum CliCommand {',1)[1].split('\n}',1)[0];names=set();position=0
    for match in re.finditer(r'^    ([A-Z][A-Za-z0-9]*)(?:\([^\n]*\))?,\s*$',body,re.MULTILINE):
        prefix='\n'.join(line for line in body[position:match.start()].splitlines() if not line.lstrip().startswith('//'))
        position=match.end()
        if 'external_subcommand' in prefix:continue
        explicit=re.search(r'\bname\s*=\s*"([a-z][a-z0-9-]*)"',prefix)
        name=explicit[1] if explicit else re.sub(r'(?<!^)([A-Z])',r'-\1',match[1]).lower()
        names.add(name)
        for alias in re.findall(r'\bvisible_alias(?:es)?\s*=\s*(\[[^\]]*\]|"[^"]*")',prefix):
            names.update(re.findall(r'"([a-z][a-z0-9-]*)"',alias))
    if not names or position==0:raise ValueError('Incomplete command catalog')
    return names


def records(texts):
    facts={name:Facts() for name in texts if name.endswith('.html')}
    for name,value in facts.items():value.feed(texts[name])
    found=[]
    def add(surface,file,url,category='identifier_command_prefix',**extra):
        found.append(dict(surface=surface,file=file,url=url,category=category,**extra))
    for file,root,path,pattern in [
            ('helm-cli-index.html','helm','/docs/helm/',r'helm(?: [a-z0-9-]+)+'),
            ('docker-cli-index.html','docker','/reference/cli/docker/',r'docker(?: [a-z0-9-]+)+'),
            ('yarn-cli-index.html','yarn','/cli/',r'yarn(?: [a-z0-9-]+)+')]:
        for href,label in facts[file].links:
            url=urljoin(URLS[file],href);target=urlsplit(url)
            if (target.netloc!=urlsplit(URLS[file]).netloc or not target.path.startswith(path) or target.query or
                    target.fragment or not re.fullmatch(pattern,label)):continue
            add(label,file,url,catalogLabel=label)
    file='node-cli.html'
    for href,label in facts[file].links:
        if not href.startswith('cli.html#') or not re.fullmatch(r'-[A-Za-z0-9-]+(?:, -[A-Za-z0-9-]+)*',label):continue
        for flag in label.split(', '):add('node '+flag,file,urljoin(URLS[file],href),documentedOptionLabel=label)
    file='typescript-cli.html'
    for attrs,cells in facts[file].rows:
        if (len(cells)>=2 and cells[0]=='--'+attrs.get('name','') and cells[1]=='boolean' and
                re.fullmatch('--[A-Za-z][A-Za-z0-9]*',cells[0])):
            add('tsc '+cells[0],file,URLS[file],documentedOption=cells[0],optionType='boolean')
    file='pnpm-cli-commands.rs';builtins=pnpm_names(texts[file])
    for name in sorted(builtins):add('pnpm '+name,file,URLS[file],catalogLabel=name)
    yarn_builtins={r['surface'].split()[1] for r in found if r['surface'].startswith('yarn ')}
    return found,{'pnpm':builtins,'yarn':yarn_builtins},facts


def attach(model,rows,texts,literals):
    extension.ensure_categories(model,{'identifier_command_prefix','identifier_command_template'})
    catalog,builtins,facts=records(texts);by_surface={}
    for item in catalog:by_surface.setdefault(item['surface'],[]).append(item)
    grammar={
        'pnpm':('pnpm-cli-run.html',['pnpm run watch','pnpm watch','shorthand','not a pnpm command']),
        'yarn':('yarn-cli-run.html',['yarn run <scriptName>','without the "run" keyword','yarn test'])}
    for root,(file,cues) in grammar.items():
        plain=' '.join(' '.join(facts[file].text).split())
        if not all(cue in plain for cue in cues):raise ValueError('Changed script-shorthand grammar: '+root)
    adopted=set()
    for row in rows:
        literal=row['reading'],row['surface'],row['cost']
        if not row['id'].startswith('manual:') or literal not in literals:continue
        items=list(by_surface.get(row['surface'],[]))
        match=re.fullmatch(r'(pnpm|yarn) ([a-z][a-z0-9:_-]*)',row['surface'])
        if match and match[2] not in builtins[match[1]]:
            file=grammar[match[1]][0]
            items.append(dict(surface=row['surface'],file=file,url=URLS[file],category='identifier_command_template',
                template=match[1]+' <scriptName>',parameter=match[2],builtinCatalogFile='pnpm-cli-commands.rs' if match[1]=='pnpm' else 'yarn-cli-index.html'))
        for item in items:
            category=item['category'];key='official-command-'+hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()[:24]
            proof=dict(item,source='documented_command_template' if category.endswith('_template') else 'documented_command_prefix',
                sha256=hashlib.sha256(texts[item['file']].encode()).hexdigest(),approved=True,
                legacySourceId=row['id'],manualSourceSha256=manual_aliases.MANUAL_SHA256,manualLine=literals[literal],
                completionRequired=None if category.endswith('_prefix') else False,
                scope='complete literal official catalog name or option prefix, or syntactic script-shorthand instantiation checked against pinned built-in names; no option combination, execution, project/script/package existence, installed version, English lexical POS or inflection assertion; a prefix may need arguments')
            model.add(key,row['surface'],row['surface'],{category,'domain_technology'},proof,approved=True);adopted.add(row['surface'])
    return adopted


def extend(args):
    for name,expected in PINS.items():
        if pipeline.digest(args.sources/name)!=expected:raise ValueError('Changed official command source or notice: '+name)
    texts={name:(args.sources/name).read_bytes().decode('utf-8') for name in URLS}
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    states={r['id']:r for r in map(json.loads,(args.base/'status.jsonl').open())}
    selected=[row for row in rows if states[row['id']]['decision']=='pending']
    adopted=attach(model,selected,texts,manual_aliases.literal_mappings(args.manual_source))
    sources['officialCommandCatalogs']=dict(files=PINS,urls=URLS,pnpmRevision=PNPM_REVISION,manualSourceSha256=manual_aliases.MANUAL_SHA256,
        policy='existing exact manual literals only; catalog names/options are prefixes, script shorthand requires pinned grammar and built-in precedence check; no inferred flag combination, execution or installed/project capability assertion')
    for name in PINS:
        if 'LICENSE' in name:notices['OFFICIAL-COMMAND-'+name]=(args.sources/name).read_bytes()
    notices['OFFICIAL-COMMAND-CATALOGS-NOTICE.txt']=('Official identifier/syntax facts from Helm authors (documentation CC BY 4.0), Node.js contributors (MIT and retained third-party notices), TypeScript website contributors (CC BY 4.0), Docker authors (Apache 2.0), Yarn contributors (BSD 2-Clause), pnpm contributors (MIT).\n'
        +'\n'.join(URLS.values())+'\nChanges: extracted exact documented names/options and existing manual script-shorthand syntax, retaining source hash, namespace, parameters and prefix/template scope. No prose, executable implementation or commands copied/executed. Full applicable notices retained; Helm documentation content is not mislabeled with its website-code MIT license.\n').encode()
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    prior=args.base/'reviewed-overrides.tsv'
    summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,
        reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(officialCommandSurfaces=len(adopted),**{key:summary[key] for key in ['includedRows','excludedRows','pendingRows']})))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','sources','manual-source','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
