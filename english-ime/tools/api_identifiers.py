"""Join existing manual type identifiers to pinned public API indexes.

Qualified API context is retained. A class identifier does not establish an
English noun, verb, brand, inflection, installed dependency or runtime feature.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import zlib

import extend_lexicon as extension
import lexicon_pipeline as pipeline

ANDROID_PINS = {'classes.html':'e20ffcab086651bc3b6f8043cb9c3693a51f86288c02f445c575e25541ea4409',
    'androidx-classes.html':'72ef9e0baeadb0c514320618ab618d2c1cf1ad36e33d8e064f1fb3e7fd419488',
    'license.html':'1ffa6c6e601bef300c4caf5d0517d1e652e869d73c24be21fdb443e20b7d09df'}
PYTHON_PINS = {'objects.inv':'84e65e567815e09d47444aca1d160f6ac771fa28096874f3ec5996226f81ce3a',
    'license.html':'a5f26a87a04be9134f7d3971c3fe6790f4df225a137b860aab8f546590b90125',
    'copyright.html':'53047c6f36d2bd285a5c290b1b51fda510e50c235b56fc3af3d1709e7c170b3d'}


class AndroidTypes(HTMLParser):
    def __init__(self):
        super().__init__();self.types=set()

    def handle_starttag(self,tag,attrs):
        if tag!='a':return
        target=urlsplit(dict(attrs).get('href',''))
        if target.netloc and target.netloc!='developer.android.com' or target.fragment:return
        match=re.fullmatch(r'/reference/((?:android|androidx|java|javax)/(?:[a-z][A-Za-z0-9_]*/)*([A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)*))',target.path)
        if match:self.types.add((match[2],match[1].replace('/','.'),'https://developer.android.com'+target.path))


def python_types(raw):
    header=raw.split(b'\n',4)
    if header[:3]!=[b'# Sphinx inventory version 2',b'# Project: Python',b'# Version: 3.14']:
        raise ValueError('Unexpected Python API inventory')
    for line in zlib.decompress(header[4]).decode('utf-8').splitlines():
        qualified,role,priority,uri,display=line.split(' ',4)
        name=qualified.rsplit('.',1)[-1]
        if role not in {'py:class','py:exception'} or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name):continue
        if uri.endswith('$'):uri=uri[:-1]+qualified
        if uri.startswith('/') or '://' in uri:raise ValueError('Unexpected Python API URI')
        yield name,qualified,'https://docs.python.org/3.14/'+uri


def load(directory,pins):
    for name,expected in pins.items():
        if pipeline.digest(directory/name)!=expected:raise ValueError('Changed public API index or notice: '+name)


def attach(model,rows,records):
    extension.ensure_categories(model,{'identifier_programming_api'})
    wanted={row['surface'] for row in rows if row['id'].startswith('manual:')}
    adopted=set()
    for name,qualified,url,provider in sorted(set(records)):
        if name not in wanted:continue
        key='public-api-'+hashlib.sha256(json.dumps([provider,qualified]).encode()).hexdigest()[:24]
        proof={'source':'public_api_identifier','url':url,'provider':provider,'qualifiedIdentifier':qualified,
            'scope':'exact existing manual type identifier in a pinned public API index; no English lexical POS, brand identity, inflection or installed/runtime capability inference','approved':True}
        values={'identifier_programming_api','domain_technology'}
        model.add(key,qualified,qualified,values,dict(proof,relation='qualified_identifier'),approved=True)
        model.add(key,qualified,name,values,proof,approved=True)
        adopted.add(name)
    return adopted


def extend(args):
    load(args.android,ANDROID_PINS);load(args.python,PYTHON_PINS)
    records=[]
    for name in ['classes.html','androidx-classes.html']:
        index=AndroidTypes();index.feed((args.android/name).read_text())
        records += [(*record,'android_public_types') for record in index.types]
    records += [(*record,'python_3.14_public_types') for record in python_types((args.python/'objects.inv').read_bytes())]
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    adopted=attach(model,rows,records)
    sources['publicApiIdentifiers']={'android':ANDROID_PINS,'python314':PYTHON_PINS,
        'policy':'exact case-sensitive existing manual class/type names from official indexes, qualified identities retained; no English POS/inflection or dependency-availability inference'}
    notices['PUBLIC-API-IDENTIFIERS-NOTICE.txt']=('Public API identifier facts from the Android Open Source Project/AndroidX contributors and Python Software Foundation/contributors.\n'
        'https://developer.android.com/reference/classes\nhttps://developer.android.com/reference/androidx/classes\nhttps://developer.android.com/license\n'
        'https://docs.python.org/3.14/objects.inv\nhttps://docs.python.org/3.14/license.html\n'
        'Changes: extracted exact type identifiers and qualified documentation URLs from public indexes; joined existing manual input rows. No API prose, implementation code, images or software copied. Original documentation license statements are retained separately; public identifiers do not imply that a dependency is installed or a feature works.\n').encode()
    notices['ANDROID-API-DOCUMENTATION-LICENSE.html']=(args.android/'license.html').read_bytes()
    notices['PYTHON-3.14-LICENSE.html']=(args.python/'license.html').read_bytes()
    notices['PYTHON-3.14-COPYRIGHT.html']=(args.python/'copyright.html').read_bytes()
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    prior=args.base/'reviewed-overrides.tsv'
    summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,
        reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(documentedManualTypeSurfaces=len(adopted),**{key:summary[key] for key in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','android','python','out']:parser.add_argument('--'+name,type=Path,required=True)
    extend(parser.parse_args())
