"""Preserve attested whole-word components of verified English proper names.

A component requires its full named context; it is not asserted to be a
standalone person/place name or an ordinary English noun. No substring splitting,
CamelCase splitting, foreign lexical senses or inherited inflection flags.
"""
import argparse,hashlib,json,re,tempfile
from collections import Counter,defaultdict
from pathlib import Path
import extend_lexicon as extension
import lexicon_pipeline as pipeline
import resolve_pending,yago_names as yago,yago_name_variants as variants
from wiktionary_index import Index


def component(match):
    token=match['component'];tokens=match['label'].split(' ');position=match['componentPosition']
    if (match['matchingMode']!='whole_whitespace_delimited_named_component' or len(tokens)<2 or not 0<=position<len(tokens)
            or tokens[position]!=token or not re.fullmatch(r"[^\W\d_]+(?:[-'][^\W\d_]+)*",token) or not any(c.isupper() for c in token)):
        raise ValueError('Component is not a whole capitalized word in the source name')
    if match.get('asciiAlias') not in {None,variants.ascii_name(token)}:raise ValueError('Changed ASCII derivation')
    return token


def attach(model,rows,entities,excluded_surfaces=frozenset()):
    extension.ensure_categories(model,{'identifier_named_component'})
    inputs=defaultdict(list);counts=Counter();witness_counts=Counter()
    for row in rows:inputs[row['surface'].casefold()].append(row)
    for entity in entities:
        if entity['id'].endswith('_generic_instance') or not entity['wikidataIds'] or not entity['englishWikipediaUrls']:continue
        parent_categories=variants.categories(entity)
        parent_kinds=parent_categories & {v for v in parent_categories if v.startswith('name_')}
        if not parent_kinds:continue
        for match in entity['matches']:
            # Alternative labels may contain vandalism, misspellings or long
            # descriptive strings. Components require the primary English name.
            if match['predicate']!='rdfs:label' or match['language']!='en':continue
            primary=[v['label'] for v in entity['labels'] if v['language']=='en']
            if match['label'] not in primary:continue
            token=component(match)
            if token.casefold() in excluded_surfaces or match.get('asciiAlias') and match['asciiAlias'].casefold() in excluded_surfaces:continue
            # Identity is a literal contextual token, not one person/entity per
            # witness. Keep at most three witnesses per token and parent kind.
            witness=(token,tuple(sorted(parent_kinds)))
            if witness_counts[witness]>=3:continue
            candidates=inputs[token.casefold()]+(inputs[match['asciiAlias'].casefold()] if match.get('asciiAlias') else [])
            if not candidates:continue
            witness_counts[witness]+=1;key='named-component-'+hashlib.sha256(token.encode()).hexdigest()[:24]
            proof={'source':'yago_named_component','url':yago.URL,'snapshots':yago.PINS,'entityId':entity['id'],
                'wikidataIds':entity['wikidataIds'],'englishWikipediaUrls':entity['englishWikipediaUrls'],'nameEvidence':match,
                'parentNameCategories':sorted(parent_kinds),'verifiedTypePaths':entity['paths'],'verifiedClassPaths':entity.get('classPaths',{}),
                'descriptionEvidence':entity['descriptions'],'approved':True,'requiresFullNamedContext':True,'standaloneCandidateApproved':False,
                'scope':'existing input attested as a whole whitespace-delimited capitalized token within a verified English/international proper name; contextual name component only, no standalone proper-name/POS/inflection or corpus-intent claim'}
            model.add(key,token,token,{'identifier_named_component'},proof,approved=False)
            for row in candidates:
                model.add(key,token,row['surface'],{'identifier_named_component'},dict(proof,legacySourceId=row['id'],originalSurface=row['surface'],
                    relation='existing_contextual_name_component_input',preferredCaseClaimed=False),approved=False)
                counts['inputComponentWitnesses']+=1
    return counts


def extend(args):
    meta=json.loads((args.prepared/'manifest.json').read_text())
    if not meta.get('componentMode') or meta['snapshots']!=yago.PINS or meta['roots']!={k:sorted(v) for k,v in variants.ROOTS.items()} or pipeline.digest(args.prepared/'names.jsonl')!=meta['files']['names.jsonl']:raise ValueError('Changed component extraction')
    model,rows,sources,notices,pending=extension.load_base(args.base,args.seed)
    if pipeline.digest(args.base/'inventory.jsonl')!=meta['inventorySha256']:raise ValueError('Wrong inventory')
    states=list(map(json.loads,(args.base/'status.jsonl').open()))
    excluded={r['surface'].casefold() for r,state in zip(rows,states) if state['decision']=='exclude'}
    counts=attach(model,rows,map(json.loads,(args.prepared/'names.jsonl').open()),excluded)
    prior=args.base/'reviewed-overrides.tsv';reviews=pipeline.read_table(prior,'decisions') if prior.is_file() else []
    reviews,reopened=resolve_pending.revalidate_machine_reviews(model,reviews,pending)
    # Components are exact existing input aliases and do not create corrections
    # that misrepresent them as independent proper names or ordinary words.
    prior=args.base/'surface-corrections.tsv';corrections=pipeline.read_table(prior,'corrections') if prior.is_file() else []
    sources['contextualNamedComponents']={'snapshots':yago.PINS,'preparedManifestSha256':pipeline.digest(args.prepared/'manifest.json'),
        'policy':'primary rdfs:label @en only, no alternate aliases; independently excluded spellings are not reopened from component evidence alone; whole whitespace-delimited capitalized tokens of verified English/international proper names, not substrings or CamelCase; source name, token position and named type retained; existing inputs only; contextual identifier category without standalone proper-name, ordinary POS or inflection claims; at most three deterministic witnesses per token/parent-kind'}
    notices['YAGO-NAMED-COMPONENTS-NOTICE.txt']=('YAGO 4.6, Télécom Paris YAGO team and Wikidata contributors.\nhttps://yago-knowledge.org/downloads/yago-4-6\nCC BY 4.0; full license retained separately.\nChanges: joined existing inputs to whole capitalized word tokens within primary English rdfs:label names, preserving full-name and type evidence. Alternate labels and known excluded misspellings are not admitted as components. The new category requires named context and makes no standalone proper-name or ordinary English POS claim. No substring splitting or inferred inflections.\n').encode()
    with tempfile.TemporaryDirectory(prefix='.named-component-review-',dir=args.out.parent) as temp:
        reviewed=Path(temp)/'reviews.tsv';pipeline.table(reviewed,'decisions',reviews)
        summary=pipeline.publish(model,rows,args.base/'inventory.jsonl',args.out,sources,notices,pending,reviewed_decisions=reviewed,allow_input_spellings=True,corrections=corrections)
    print(json.dumps(dict(counts,reopenedMachineExclusions=len(reopened),**{k:summary[k] for k in ['includedRows','excludedRows','pendingRows']}),sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    for name in ['prepare','extend']:
        command=commands.add_parser(name)
        for arg in (['base','sources','out'] if name=='prepare' else ['base','seed','prepared','out']):command.add_argument('--'+arg,type=Path,required=True)
    args=parser.parse_args();variants.prepare(args,components=True) if args.command=='prepare' else extend(args)
