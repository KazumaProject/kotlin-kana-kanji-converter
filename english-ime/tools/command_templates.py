"""Classify existing manual command examples against documented syntax.

Literal prefixes and complete parameter instantiations are different categories.
Parameter values come only from existing manual rows; they do not establish an
installed package, existing project script, valid credentials or executable run.
"""
import argparse
from collections import defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import re
import shlex
import tarfile

import documented_command_prefixes as prefixes
import extend_lexicon as extension
import lexicon_pipeline as pipeline
import tldr_commands as tldr

CHEAT_REVISION='36bdb99dcfadde210503d8c2dcf94b34ee950e1d'
CHEAT_ARCHIVE='172a3fc8c78056798485344ad501005c2d47b11e1b022b7f099942c453cfa451'
CHEAT_LICENSE='a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499'
SAFE_ARGUMENT=re.compile(r'[A-Za-z0-9_./:@+=,~%\-]+')


def template_variants(expression):
    segments=[];position=0;variables={};count=1
    for match in re.finditer(r'\{\{([^{}]*)\}\}',expression):
        segments.append([expression[position:match.start()]])
        choices=prefixes.literal_choices(match[1])
        if choices:
            count*=len(choices)
            if count>1024:return
            segments.append(choices)
        else:
            marker='DOCVAR'+str(len(variables));variables[marker]=match[1];segments.append([marker])
        position=match.end()
    segments.append([expression[position:]])
    for parts in itertools.product(*segments):
        try:tokens=shlex.split(''.join(parts),posix=True)
        except ValueError:continue
        if not tokens or tokens[0] in variables or any(token in {'|',';','&&','||','>','<'} for token in tokens):continue
        # Embedded substitutions and shell expressions are outside this small
        # grammar. Every parameter must occupy exactly one argument position.
        if any('DOCVAR' in token and token not in variables for token in tokens):continue
        yield tokens,variables


def instantiate(tokens,variables,candidate):
    try:values=shlex.split(candidate,posix=True)
    except ValueError:return None
    if len(values)!=len(tokens):return None
    parameters=[]
    for expected,actual in zip(tokens,values):
        if expected not in variables:
            if expected!=actual:return None
        elif (not SAFE_ARGUMENT.fullmatch(actual) or actual.startswith('-') or
                any(word in variables[expected].lower() for word in ['option','flag'])):
            return None
        else:parameters.append({'parameter':variables[expected],'value':actual})
    return parameters if parameters else None


def cheat_examples(text):
    lines=text.splitlines();front=False;syntax=None
    if lines and lines[0]=='---':
        for line in lines[1:]:
            if line=='---':break
            if line.startswith('syntax:'):syntax=line.split(':',1)[1].strip()
    if syntax not in {None,'bash','sh','zsh','shell'}:return
    for number,line in enumerate(lines,1):
        if line=='---':front=not front;continue
        if front or not line or line[0].isspace() or line.startswith('#'):continue
        # Only the literal prefix before a declared placeholder/shell operator.
        stop=re.search(r'<[^>]*>|\$|`|[|;&>]',line)
        yield number,(line[:stop.start()] if stop else line).rstrip(),line


def attach(model,rows,pages,cheat_pages):
    extension.ensure_categories(model,{'identifier_command_prefix','identifier_command_template'})
    by_command=defaultdict(list);adopted=set()
    for row in rows:
        if row['id'].startswith('manual:'):
            try:tokens=shlex.split(row['surface'])
            except ValueError:continue
            if tokens:by_command[tokens[0]].append(row['surface'])
    for filename,text,sha in pages:
        for line,value in enumerate(text.splitlines(),1):
            if not(value.startswith('`') and value.endswith('`') and not value.startswith('```')):continue
            expression=value[1:-1]
            for tokens,variables in template_variants(expression):
                for surface in by_command[tokens[0]]:
                    parameters=instantiate(tokens,variables,surface)
                    if parameters is None:continue
                    key='command-template-'+hashlib.sha256(json.dumps([filename,line,surface]).encode()).hexdigest()[:24]
                    proof={'source':'documented_command_template','url':'https://github.com/tldr-pages/tldr/blob/'+tldr.REVISION+'/'+filename+'#L'+str(line),
                        'file':filename,'line':line,'sha256':sha,'template':expression,'parameters':parameters,
                        'scope':'complete syntactic instantiation of a documented template using existing manual literal arguments; no command execution, installed dependencies, script existence, credentials, English POS or inflections asserted','approved':True}
                    model.add(key,surface,surface,{'identifier_command_template','domain_technology'},proof,approved=True);adopted.add(surface)
    for filename,text,sha in cheat_pages:
        for line,prefix,example in cheat_examples(text):
            if not prefix:continue
            first=prefix.split(' ',1)[0]
            for surface in by_command[first]:
                if surface!=prefix and not prefix.startswith(surface+' '):continue
                key='cheat-prefix-'+hashlib.sha256(json.dumps([filename,line,surface]).encode()).hexdigest()[:24]
                proof={'source':'documented_command_prefix','url':'https://github.com/cheat/cheatsheets/blob/'+CHEAT_REVISION+'/'+filename+'#L'+str(line),
                    'revision':CHEAT_REVISION,'file':filename,'line':line,'sha256':sha,'literalExample':example,
                    'completionRequired':surface!=example,'scope':'existing manual literal command/prefix in CC0 shell documentation; no execution, lexical POS or installed/runtime feature claim','approved':True}
                model.add(key,surface,surface,{'identifier_command_prefix','domain_technology'},proof,approved=True);adopted.add(surface)
    return adopted


def extend(args):
    files=tldr.load(args.tldr)
    cheat=json.loads((args.cheat/'manifest.json').read_text())
    if cheat['revision']!=CHEAT_REVISION or cheat['archiveSha256']!=CHEAT_ARCHIVE or pipeline.digest(args.cheat/'snapshot.tar.gz')!=CHEAT_ARCHIVE:
        raise ValueError('Changed cheatsheet snapshot')
    archive_files={}
    with tarfile.open(args.cheat/'snapshot.tar.gz') as archive:
        for member in archive:
            if not member.isfile():continue
            name=member.name.split('/',1)[1]
            if '/' in name and name not in {'.github/LICENSE.txt','.github/README.md'}:continue
            archive_files[name]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    if cheat['files']!=archive_files:raise ValueError('Cheatsheet selection is not the pinned archive')
    for name,sha in cheat['files'].items():
        if pipeline.digest(args.cheat/'files'/name)!=sha:raise ValueError('Changed cheatsheet: '+name)
    if pipeline.digest(args.cheat/'files/.github/LICENSE.txt')!=CHEAT_LICENSE:raise ValueError('Changed CC0 notice')
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    states=[json.loads(x) for x in (args.base/'status.jsonl').read_text().splitlines()]
    selected=[row for row,state in zip(rows,states) if state['decision']=='pending']
    pages=[(name,(args.tldr/name).read_text(),sha) for name,sha in sorted(files.items())]
    literal=prefixes.attach(model,selected,pages)
    cheat_pages=[(name,(args.cheat/'files'/name).read_text(),sha) for name,sha in sorted(cheat['files'].items()) if '/' not in name]
    instantiated=attach(model,selected,pages,cheat_pages)
    sources['documentedCommandTemplates']={'tldrRevision':tldr.REVISION,'cheatRevision':CHEAT_REVISION,'cheatArchiveSha256':CHEAT_ARCHIVE,
        'policy':'existing manual surfaces only; documented literal alternatives, literal shell-example prefixes, or complete single-argument parameter substitutions; separate prefix/template dictionaries; no inferred option combinations, command execution or installed/runtime feature claims'}
    notices['CHEAT-SHEETS-CC0.txt']=(args.cheat/'files/.github/LICENSE.txt').read_bytes()
    notices['COMMAND-TEMPLATES-NOTICE.txt']=('tldr-pages contributors (CC BY 4.0) and cheat/cheatsheets contributors (CC0).\nhttps://github.com/tldr-pages/tldr/tree/'+tldr.REVISION+'\nhttps://github.com/cheat/cheatsheets/tree/'+CHEAT_REVISION+
        '\nChanges: selected existing manual command literals/prefixes and documented template instantiations, retaining parameters/source file/line/hash; no commands executed or code imported. Existing full CC BY 4.0 and CC0 notices retained.\n').encode()
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    prior=args.base/'reviewed-overrides.tsv'
    summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,
        reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(newLiteralPrefixSurfaces=len(literal),documentedTemplateOrCheatSurfaces=len(instantiated),**{key:summary[key] for key in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','tldr','cheat','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
