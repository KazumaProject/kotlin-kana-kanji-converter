"""Capture every published Pantheon person, preserving exact names and source classifications."""
import argparse
import bz2
from collections import Counter
import csv
from pathlib import Path
import re
from urllib.parse import quote

import dictionary_sources as download
import vocabulary_harness as h

POLICY = h.REPO/'english-ime/data/catalog/pantheon-policy.json'
ARCHIVE = 'person_2025_update.csv.bz2'


def rows(directory):
    seen=set()
    with bz2.open(directory/ARCHIVE,'rt',encoding='utf-8',newline='') as stream:
        reader=csv.DictReader(stream)
        h.require({'name','wd_id','wp_id','occupation','birthyear','is_group'}<=set(reader.fieldnames or []),
                  'Missing Pantheon fields')
        for row in reader:
            h.require(re.fullmatch(r'Q[1-9][0-9]*',row['wd_id']) and re.fullmatch(r'[1-9][0-9]*',row['wp_id']) and
                      row['wd_id'] not in seen and row['name'] and not any(c in row['name'] for c in '\t\r\n'),
                      'Invalid/duplicate Pantheon person identity')
            seen.add(row['wd_id']);yield row


def fetch(directory,policy_path=POLICY):
    directory=h.external(directory);directory.mkdir(parents=True,exist_ok=True);rule=h.replay.read_json(policy_path)
    with h.lock(directory):
        if (directory/'pantheon.json').exists():return verify(directory,policy_path)
        if not (directory/ARCHIVE).exists():download.download(rule['url'],directory/ARCHIVE,128*1024*1024)
        permission=directory/'PANTHEON-PERMISSIONS.html'
        if not permission.exists():download.download(rule['permissionsUrl'],permission,2*1024*1024)
        h.require('creativecommons.org/licenses/by-sa/4.0' in permission.read_text(),'Missing Pantheon redistribution license')
        counts=Counter();total=0
        for row in rows(directory):counts[row['occupation']]+=1;total+=1
        h.require(total>0,'Empty Pantheon source')
        notice=directory/'PANTHEON-SOURCES.txt'
        notice.write_text('Pantheon 2.0, 2025 Person Dataset. Pantheon by Datawheel and contributors. CC BY-SA 4.0.\n'
            +rule['url']+'\n'+rule['permissionsUrl']+'\n'
            'Citation requested by the publisher: Yu, A. Z., et al. (2016). Pantheon 1.0, a manually verified dataset '
            'of globally famous biographies. Scientific Data 2:150075. https://doi.org/10.1038/sdata.2015.75\n'
            'Changes: scan every published row; select exact supplied person names/QIDs; map provider occupation '
            'labels to dictionary topics; add a historical topic for supplied birth years before 1900. '
            'No HPI/rank/count cutoff, synthesized names or name splitting. Broad occupations do not establish '
            'a narrower sport or Olympic participation. Upstream classification is not an independent career audit.\n'
            'Raw dates, locations, coordinates, scores and social accounts remain outside the dictionary. '
            'Adult-industry records remain in curation and are excluded from distribution by the pinned policy.\n'
            'Preserve the full CC BY-SA 4.0 notice supplied with the dictionary.\n',encoding='utf-8')
        value=dict(schemaVersion=1,complete=True,policy=rule,policySha256=h.replay.sha(policy_path),records=total,
            occupations=dict(counts),files={ARCHIVE:dict(url=rule['url'],sha256=h.replay.sha(directory/ARCHIVE)),
                permission.name:dict(url=rule['permissionsUrl'],sha256=h.replay.sha(permission)),
                notice.name:dict(sha256=h.replay.sha(notice))})
        h.dump(directory/'pantheon.json',value);return verify(directory,policy_path)


def verify(directory,policy_path=POLICY):
    directory=h.external(directory);v=h.replay.read_json(directory/'pantheon.json');rule=h.replay.read_json(policy_path)
    h.require(v['schemaVersion']==1 and v['complete'] and v['policy']==rule and v['policySha256']==h.replay.sha(policy_path),
              'Changed/incomplete Pantheon policy')
    h.require(set(v['files'])=={ARCHIVE,'PANTHEON-PERMISSIONS.html','PANTHEON-SOURCES.txt'},'Missing/extra Pantheon inputs')
    for name,record in v['files'].items():
        path=directory/name;h.require(not path.is_symlink() and h.replay.sha(path)==record['sha256'],'Changed Pantheon source: '+name)
    counts=Counter();total=0
    for row in rows(directory):counts[row['occupation']]+=1;total+=1
    h.require(total==v['records'] and dict(counts)==v['occupations'],'Changed/incomplete Pantheon rows')
    return v


def collect(directory,policy_path=POLICY):
    directory=h.external(directory);v=verify(directory,policy_path);rule=v['policy'];records=[];restricted=[]
    for row in rows(directory):
        if row['is_group']!='FALSE':continue
        topics={'people.notable',*rule['occupationTopics'].get(row['occupation'],[])}
        if any(t.startswith('people.sports.') and t not in {'people.sports.staff','people.sports.mind_sports'} for t in topics):
            topics.add('people.sports')
        if re.fullmatch(r'-?[0-9]+',row['birthyear']) and int(row['birthyear'])<rule['historicalBornBefore']:
            topics.add('people.history')
        proof=dict(source='pantheon_2025',url='https://pantheon.world/profile/person/'+quote(row['slug'],safe=''),
            license=rule['license'],sha256=v['files'][ARCHIVE]['sha256'],entity=row['wd_id'],englishPageId=int(row['wp_id']),
            occupation=row['occupation'],classification='Provider occupation label; no narrower sport inferred')
        if 'people.history' in topics:proof['birthYear']=int(row['birthyear'])
        records.append(dict(surface=row['name'],kind='person',entity='wikidata:'+row['wd_id'],topics=sorted(topics),proofs=[proof]))
        if row['occupation'] in rule['restrictedOccupations']:
            restricted.append(dict(surface=row['name'],reason=rule['restrictedOccupations'][row['occupation']],
                evidence=proof['url'],license=rule['license']))
    public=dict(v,sourceSnapshotSha256=h.replay.sha(directory/'pantheon.json'))
    notice=directory/'PANTHEON-SOURCES.txt'
    return records,public,[dict(name=notice.name,path=str(notice),sha256=h.replay.sha(notice))],restricted


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-dir',type=Path,required=True)
    parser.add_argument('--policy',type=Path,default=POLICY);args=parser.parse_args();v=fetch(args.source_dir,args.policy)
    print(dict(complete=v['complete'],records=v['records'],occupations=v['occupations']))
