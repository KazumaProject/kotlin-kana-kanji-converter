#!/usr/bin/env python3
"""No model/network access. Fail closed when a research release is incomplete."""
import argparse,json,pathlib,sqlite3,sys
from distribution import verify_precision_report,verify_snapshot_dependencies

def verify(path,manifest=None):
    if not path.is_file() or path.stat().st_size>512*1024*1024: raise ValueError('Missing/oversized fixed data')
    with sqlite3.connect('file:'+str(path.resolve())+'?mode=ro',uri=True) as c:
        m=json.loads(c.execute("SELECT value FROM info WHERE key='manifest'").fetchone()[0])
        if m.get('schemaVersion')!=4: raise ValueError('Full re-examination has not produced schema 4; versioned release is stopped')
        r=m['research']
        if not r['releaseReady'] or r['unprocessed'] or r['errors']: raise ValueError('Incomplete/unapproved research')
        if r['sourceRows']!=1103684: raise ValueError('The five full inputs have not all been tracked')
        counts=dict(c.execute('SELECT status,count(*) FROM resolutions GROUP BY status'))
        if set(counts)-{'adopted','excluded_confirmed','not_distributed'} or sum(counts.values())!=r['candidates']: raise ValueError('Non-terminal/incomplete resolution set')
        a=r['acceptance']
        if not all(a.get(k) for k in ('categoryReviews','nonDistributedReview','conversionRegression','linuxBinaryParity','zipVerified')): raise ValueError('Acceptance evidence incomplete')
        if a['resolutionSha256']!=r['resolutionSha256']: raise ValueError('Acceptance belongs to different data')
        methods={}
        for raw, in c.execute("SELECT roles FROM resolutions WHERE status='adopted'"):
            for role in json.loads(raw):
                method=role.get('method')
                if not isinstance(method,str): raise ValueError('Exported role has no classification method')
                methods[method]=methods.get(method,0)+1
        verify_precision_report(r['validation'],methods)
        verify_snapshot_dependencies(c)
        if manifest is not None:
            built=json.loads(manifest.read_text())
            if built['resolutionSha256']!=r['resolutionSha256'] or built['artifacts']!=a['binaryArtifacts']: raise ValueError('Build differs from independently reviewed/Linux-validated binaries')
        print(json.dumps({'releaseReady':True,'sourceRows':r['sourceRows'],'decisions':counts,'categories':m['activeCategories']},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True,type=pathlib.Path);p.add_argument('--manifest',type=pathlib.Path);args=p.parse_args()
    try: verify(args.snapshot,args.manifest)
    except Exception as e: print('Release stopped: '+str(e),file=sys.stderr);sys.exit(2)
