"""A manually started collection campaign; batch budgets are not completion goals."""
import argparse
import json
from pathlib import Path
import time

import coverage_sources
import discovery_sources
import vocabulary_harness as h


def run(args):
    root=h.external(args.work_dir);root.mkdir(parents=True,exist_ok=True)
    previous=args.resume_from;failures=0;batch=0
    while True:
        output=root/f'batch-{batch:04}'
        if args.provider=='coverage':
            coverage_sources.fetch(argparse.Namespace(source_dir=output,policy=args.policy,max_requests=args.batch_requests,
                resume_from=previous,advice=None,metadata_only=False))
            manifest=coverage_sources.verify(output,args.policy);filename='coverage.json'
        elif args.provider=='typed':
            manifest=discovery_sources.fetch(output,args.policy,args.batch_requests,previous);filename='discovery.json'
        status=dict(snapshot=str(output),sourceManifest=filename,complete=manifest['complete'],batch=batch)
        h.dump(root/'campaign.json',status)
        if manifest['complete']:return status
        if args.provider=='coverage':errors=manifest.get('errors') or (manifest['missingCategories'] and not manifest['remainingCategories'])
        elif args.provider=='typed':errors=any(not s['complete'] and 'budget' not in s.get('pendingReason','').lower() for s in manifest['states'].values())
        failures=failures+1 if errors else 0
        if failures>=args.max_source_failures:
            status.update(stopReason='unresolved_source_errors',complete=False);h.dump(root/'campaign.json',status)
            raise ValueError('Campaign has unresolved sources; preserved checkpoint at '+str(output))
        if errors:time.sleep(args.retry_delay)
        previous=output;batch+=1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--provider',choices=['coverage','typed'],required=True)
    p.add_argument('--work-dir',type=Path,required=True);p.add_argument('--policy',type=Path,required=True)
    p.add_argument('--resume-from',type=Path);p.add_argument('--batch-requests',type=int,default=300)
    p.add_argument('--max-source-failures',type=int,default=3);p.add_argument('--retry-delay',type=float,default=65)
    args=p.parse_args();h.require(args.batch_requests>0 and args.max_source_failures>0 and args.retry_delay>=60,'Invalid campaign budget/backoff')
    print(json.dumps(run(args),ensure_ascii=False))


if __name__=='__main__':main()
