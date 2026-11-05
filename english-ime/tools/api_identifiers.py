"""Join existing manual and reviewed pending inputs to pinned public API types.

Qualified API context is retained. A class identifier does not establish an
English noun, verb, brand, inflection, installed dependency or runtime feature.
"""
import argparse
from collections import defaultdict
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
KOTLIN_PINS = {'androidx-kotlin-classes.html':'788cee0d34a2f2ede4135db93352de156d9b86094853cb82b3062e9801160842',
    'kotlinx-coroutines-pages.json':'3c8ffab3f81c28df192450582a9d11fdeaa410e1281465ec079702026a33b76b',
    'kotlinx-coroutines-LICENSE.txt':'b1febe6399dffb10d19d35e7663ab16300c93cb0476a94115df1cc0097a8ffd8'}
FIREBASE_PINS={'firebase-android-packages.html':'5c92b63c1cd83b93515d76a0f9501ba24f2001ee4463384f37d50ed0d6fe5669'}
TYPESCRIPT_REVISION='c46bcd6089ea2e5e84e7fcc60845ac884a5b0ac1'
TYPESCRIPT_PINS={'lib.es5.d.ts':'f95aebdfd972e9fc77febbc7dda452a36037510e315c52d43cd72d36ef572603',
 'lib.es2015.promise.d.ts':'bfc056732cbafefa9ac012b3540cd210fc9f7526f49bfd13d64f6e239d985e77',
 'lib.es2015.collection.d.ts':'8f2909237f2e47f247cacecb54d4096a2ee5d10d3c10e9256be9351ddf307117',
 'LICENSE.txt':'a5e9f9b1575301c7a7a03508fdaa2e05a918cc17fd21c6e898096a96d6a34f61',
 'NOTICE.txt':'7550906c9fa208c0d6065cf510ef5d22f10ab3550184f60716c2b66b59e62966',
 'CopyrightNotice.txt':'f0dc63a96c37a7f08e97780a36bd84ae705b2e1786df4c1f2ae45dec3874f0f2'}


def typescript_types(text,filename):
    """Read complete root-scope type declarations, masking comments/strings."""
    masked=list(text);i=0
    while i<len(text):
        end=None
        if text.startswith('//',i):
            end=text.find('\n',i)
            if end<0:end=len(text)
        elif text.startswith('/*',i):
            end=text.find('*/',i+2)
            if end<0:raise ValueError('Unterminated declaration comment')
            end+=2
        elif text[i] in "\"'`":
            quote=text[i];end=i+1
            while end<len(text):
                if text[end]=='\\':end+=2;continue
                if text[end]==quote:break
                end+=1
            if end>=len(text):raise ValueError('Unterminated declaration string')
            end+=1
        if end is not None:
            for pos in range(i,end):
                if masked[pos]!='\n':masked[pos]=' '
            i=end
        else:i+=1
    code=''.join(masked);depth=0;positions={m.start():m for m in re.finditer(r'^(?:declare )?(interface|class) ([A-Za-z_$][A-Za-z0-9_$]*)\b',code,re.M)}
    for pos,char in enumerate(code):
        match=positions.get(pos)
        if match and depth==0:
            name=match[2];line=text.count('\n',0,pos)+1
            url='https://github.com/microsoft/TypeScript/blob/'+TYPESCRIPT_REVISION+'/tsc/internal/bundled/libs/'+filename+'#L'+str(line)
            yield name,name,url,'typescript_global_'+match[1]
        if char=='{':depth+=1
        elif char=='}':
            depth-=1
            if depth<0:raise ValueError('Unbalanced declaration scope')
    if depth:raise ValueError('Unbalanced declaration scope')


class AndroidTypes(HTMLParser):
    def __init__(self):
        super().__init__();self.types=set()

    def handle_starttag(self,tag,attrs):
        if tag!='a':return
        target=urlsplit(dict(attrs).get('href',''))
        if target.scheme not in {'','https'} or target.netloc and target.netloc!='developer.android.com' or target.fragment or target.query:return
        match=re.fullmatch(r'/reference/(?:kotlin/)?((?:android|androidx|java|javax)/(?:[a-z][A-Za-z0-9_]*/)*([A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)*))',target.path)
        if match:self.types.add((match[2],match[1].replace('/','.'),'https://developer.android.com'+target.path))


class FirebaseTypes(HTMLParser):
    def __init__(self):
        super().__init__();self.types=set();self.links=[];self.modules=defaultdict(set);self.heading=None

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='div' and 'devsite-nav-title-no-path' in attrs.get('class','').split():self.heading=[]
        if tag=='a':self.links.append(attrs.get('href',''))

    def handle_data(self,data):
        if self.heading is not None:self.heading.append(data)

    def handle_endtag(self,tag):
        if tag=='div' and self.heading is not None:
            label=''.join(self.heading).strip();self.heading=None
            if re.fullmatch('Firebase[A-Z][A-Za-z0-9]*',label):self.modules[label.lower()].add(label)

    def records(self):
        for href in self.links:
            target=urlsplit(href)
            if target.scheme not in {'','https'} or target.netloc and target.netloc!='firebase.google.com' or target.query or target.fragment:continue
            android=re.fullmatch(r'/docs/reference/android/((?:com/google)/(?:[a-z][A-Za-z0-9_]*/)*([A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)*))',target.path)
            if android:
                yield android[2],android[1].replace('/','.'),'https://firebase.google.com'+target.path,'firebase_android_public_types'
            swift=re.fullmatch(r'/docs/reference/swift/(firebase[a-z0-9]+)/api/reference/Classes/([A-Z][A-Za-z0-9_]*(?:/[A-Z][A-Za-z0-9_]*)*)',target.path)
            if swift and self.modules.get(swift[1]):
                modules=self.modules[swift[1]]
                if len(modules)!=1:raise ValueError('Ambiguous explicit Swift module label')
                name=swift[2].replace('/','.');qualified=next(iter(modules))+'.'+name
                yield name,qualified,'https://firebase.google.com'+target.path,'firebase_swift_public_types'


def coroutine_types(raw):
    """Read complete Dokka type declarations, never functions or search fragments."""
    pages=json.loads(raw)
    if not isinstance(pages,list):raise ValueError('Unexpected Kotlin API search index')
    for page in pages:
        declaration=re.match(r'^(?:(?:data|sealed|enum|annotation|value|expect|actual) )*(?:class|interface|object) ([A-Z][A-Za-z0-9_]*)\b',page['name'])
        if not declaration:continue
        name=declaration[1];qualified=page['description'];location=page['location']
        if (not re.fullmatch(r'kotlinx\.coroutines(?:\.[A-Za-z_][A-Za-z0-9_]*)+',qualified) or
                qualified.rsplit('.',1)[-1]!=name or name not in page['searchKeys'] or
                not re.fullmatch(r'[a-z0-9.-]+/(?:[a-z0-9.-]+/)*-[a-z0-9-]+/index\.html',location) or
                '..' in location.split('/')):
            raise ValueError('Incomplete or inconsistent Kotlin type identity')
        yield name,qualified,'https://kotlinlang.org/api/kotlinx.coroutines/'+location


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


def attach(model,rows,records,pending_ids=(),corrections=None):
    extension.ensure_categories(model,{'identifier_programming_api'})
    wanted={row['surface'] for row in rows if row['id'].startswith('manual:')}
    pending=defaultdict(list)
    for row in rows:
        if row['id'] in pending_ids and row['id'].startswith('tsv:') and row['surface']==row['surface'].lower():
            pending[row['surface']].append(row)
    if pending and corrections is None:raise ValueError('Pending API spellings require explicit correction output')
    adopted=set()
    for name,qualified,url,provider in sorted(set(records)):
        matches=[row for row in pending[name.lower()] if pipeline.keyboard_reading(name)==row['reading']]
        if name not in wanted and not matches:continue
        key='public-api-'+hashlib.sha256(json.dumps([provider,qualified]).encode()).hexdigest()[:24]
        proof={'source':'public_api_identifier','url':url,'provider':provider,'qualifiedIdentifier':qualified,
            'scope':'complete case-sensitive type identifier in a pinned public API index; exact manual spellings or verified pending ASCII input spellings only; no English lexical POS, brand identity, preferred input casing, inflection or installed/runtime capability inference','approved':True}
        values={'identifier_programming_api','domain_technology'}
        model.add(key,qualified,qualified,values,dict(proof,relation='qualified_identifier'),approved=True)
        model.add(key,qualified,name,values,proof,approved=True)
        for row in matches:
            if row['surface']==name:continue
            prior={c['target']:dict(c) for c in corrections if c['id']==row['id']}
            prior.setdefault(name,dict(id=row['id'],source=row['surface'],target=name,evidence=url))
            relation='case_correction' if len(prior)==1 else 'case_candidates'
            corrections[:]=[c for c in corrections if c['id']!=row['id']]
            corrections += [dict(c,relation=relation) for _,c in sorted(prior.items())]
        adopted.add(name)
    return adopted


def extend(args):
    typescript=getattr(args,'typescript',None)
    load(args.android,ANDROID_PINS);load(args.python,PYTHON_PINS)
    records=[]
    for name in ['classes.html','androidx-classes.html']:
        index=AndroidTypes();index.feed((args.android/name).read_text())
        records += [(*record,'android_public_types') for record in index.types]
    records += [(*record,'python_3.14_public_types') for record in python_types((args.python/'objects.inv').read_bytes())]
    if args.kotlin:
        load(args.kotlin,KOTLIN_PINS)
        index=AndroidTypes();index.feed((args.kotlin/'androidx-kotlin-classes.html').read_text())
        records += [(*record,'androidx_kotlin_public_types') for record in index.types]
        records += [(*record,'kotlinx_coroutines_public_types') for record in coroutine_types((args.kotlin/'kotlinx-coroutines-pages.json').read_text())]
    if args.firebase:
        load(args.firebase,FIREBASE_PINS)
        index=FirebaseTypes();index.feed((args.firebase/'firebase-android-packages.html').read_text());records+=list(index.records())
    if typescript:
        load(typescript,TYPESCRIPT_PINS)
        for name in TYPESCRIPT_PINS:
            if name.endswith('.d.ts'):records+=list(typescript_types((typescript/name).read_text(),name))
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    states=list(map(json.loads,(args.base/'status.jsonl').open()));ids={r['id'] for r in states if r['decision']=='pending'}
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    adopted=attach(model,rows,records,ids,corrections)
    prior_kotlin=sources.get('publicApiIdentifiers',{}).get('kotlin')
    sources['publicApiIdentifiers']={'android':ANDROID_PINS,'python314':PYTHON_PINS,
        'policy':'complete type names from official indexes, qualified identities retained; exact manual spellings or verified pending ASCII TSV input spellings with explicit canonical-case candidates; no arbitrary case edits, title/name-component extraction, English POS/inflection or dependency-availability inference'}
    if args.kotlin:
        sources['publicApiIdentifiers']['kotlin']=KOTLIN_PINS
        notices['KOTLIN-PUBLIC-API-NOTICE.txt']=('Public API type identifier facts from AndroidX contributors and JetBrains/Kotlin contributors.\n'
            'https://developer.android.com/reference/kotlin/androidx/classes\nhttps://developer.android.com/license\n'
            'https://kotlinlang.org/api/kotlinx.coroutines/scripts/pages.json\n'
            'Changes: extracted complete Kotlin type declarations and qualified identities; no functions, search fragments, prose or implementation code copied. Android documentation content is CC BY 4.0 and code samples Apache 2.0; the Kotlin project Apache 2.0 notice is retained separately. No installed dependency, English POS or runtime capability inferred.\n').encode()
        notices['KOTLINX-COROUTINES-LICENSE.txt']=(args.kotlin/'kotlinx-coroutines-LICENSE.txt').read_bytes()
    elif prior_kotlin:
        sources['publicApiIdentifiers']['kotlin']=prior_kotlin
    if args.firebase:
        sources['firebasePublicApiIdentifiers']={'files':FIREBASE_PINS,
            'policy':'whole Android types or whole Swift class paths qualified by explicitly printed module labels in the pinned SDK reference navigation; no namespace case guessed from URL slugs, leaf extraction, functions or lexical POS inference'}
        notices['FIREBASE-PUBLIC-API-NOTICE.txt']=('Firebase SDK contributors, Google. https://firebase.google.com/docs/reference/android/com/google/firebase/package-summary\n'
            'https://developers.google.com/terms/site-policies\n'
            'Identifier facts only from the Android and Swift type navigation: preserve complete type/class paths, explicitly printed Swift modules, qualified identities and documentation URLs. No prose, implementation or code samples redistributed. Reference content is CC BY 4.0 and code samples Apache 2.0 unless otherwise noted; existing full notices retained. No installed dependency, English POS, current availability or runtime feature implied.\n').encode()
    if typescript:
        sources['typescriptPublicApiTypes']={'revision':TYPESCRIPT_REVISION,'files':TYPESCRIPT_PINS,
            'policy':'complete root-scope interface/class type declarations from pinned upstream standard-library files; comments, strings and nested namespaces masked, global context and declaration line retained; no declaration implementation, prose, constructibility, installed compiler or released-runtime capability claim'}
        notices['TYPESCRIPT-API-ATTRIBUTION.txt']=('Microsoft Corporation and TypeScript contributors. https://github.com/microsoft/TypeScript/tree/'+TYPESCRIPT_REVISION+'\n'
            'Factual public type names from tsc/internal/bundled/libs/lib.es5.d.ts, lib.es2015.promise.d.ts and lib.es2015.collection.d.ts. Complete global interface/class declarations only; source locations and revision retained. No library implementation, declaration bodies or comments redistributed. An interface is a type identity, not a promise of constructibility, installed dependencies or released runtime support. Apache-2.0 license, copyright and notices retained separately.\n').encode()
        for name in ['LICENSE.txt','NOTICE.txt','CopyrightNotice.txt']:notices['TYPESCRIPT-'+name]=(typescript/name).read_bytes()
    notices['PUBLIC-API-IDENTIFIERS-NOTICE.txt']=('Public API identifier facts from the Android Open Source Project/AndroidX contributors and Python Software Foundation/contributors.\n'
        'https://developer.android.com/reference/classes\nhttps://developer.android.com/reference/androidx/classes\nhttps://developer.android.com/license\n'
        'https://docs.python.org/3.14/objects.inv\nhttps://docs.python.org/3.14/license.html\n'
        'Changes: extracted complete exact type identifiers and qualified documentation URLs from public indexes; joined exact manual spellings and reviewed pending ASCII input spellings with explicit canonical-case candidates. No API prose, implementation code, images or software copied. Original documentation license statements are retained separately; public identifiers do not imply that a dependency is installed or a feature works.\n').encode()
    notices['ANDROID-API-DOCUMENTATION-LICENSE.html']=(args.android/'license.html').read_bytes()
    notices['PYTHON-3.14-LICENSE.html']=(args.python/'license.html').read_bytes()
    notices['PYTHON-3.14-COPYRIGHT.html']=(args.python/'copyright.html').read_bytes()
    prior=args.base/'reviewed-overrides.tsv'
    summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,
        reviewed_decisions=prior if prior.is_file() else None,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(documentedTypeSurfaces=len(adopted),documentedManualTypeSurfaces=len(adopted & {r['surface'] for r in rows if r['id'].startswith('manual:')}),**{key:summary[key] for key in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['base','seed','android','python','out']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--kotlin',type=Path,help='Optional pinned Kotlin public type indexes and notice')
    parser.add_argument('--firebase',type=Path,help='Optional pinned Firebase Android/Swift type navigation')
    parser.add_argument('--typescript',type=Path,help='Optional pinned complete upstream TypeScript standard-library declarations and notices')
    extend(parser.parse_args())
