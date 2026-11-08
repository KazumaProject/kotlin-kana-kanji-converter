"""Unattended, source-verified adoption and daily build checkpoints. No implicit API calls."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re

import vocabulary_harness as h
import vocabulary_sources as s

POLICY = 'esdb-wordnet-auto-v1'


def decisions(config, candidates, source_dir, esdb_dir, references=None):
    # Re-extract from hash-verified sources. Never trust model-generated evidence
    # or edited candidate payloads as an independent attestation.
    inputs = Path(config['assets']) / 'grammar/categories.tsv'
    import csv
    with inputs.open() as stream:
        categories = {row['category'] for row in csv.DictReader(stream, delimiter='\t')}
    actual, pins = s.collect(source_dir, esdb_dir, categories, set(), set(), references)
    h.require(pins == config['sources'], 'Source configuration changed')
    actual = {row['id']: json.loads(json.dumps(row, ensure_ascii=False)) for row in actual}
    output = []
    for candidate, proposal in candidates:
        h.require(actual.get(candidate['id']) == candidate, 'Candidate differs from verified source extraction')
        esdb = [proof for proof in candidate['proofs'] if proof['source'] == 'esdb']
        eligible = (len(candidate['surface']) > 1 and bool(esdb) and
            all(proof.get('wordnetOffsets') and proof['size'] <= 60 and
                (proof.get('cmudict') or proof.get('trainingOccurrences', 0) >= 2 or proof.get('listedHeadword'))
                for proof in esdb) and all(proof['source'] in {'esdb', 'wordnet'} for proof in candidate['proofs']))
        # A model veto always wins. Uncertain entries remain available for later
        # review, rather than being declared nonwords.
        if proposal is not None and proposal['decision'] != 'include':
            eligible = False
        output.append(dict(id=candidate['id'], decision='include' if eligible else 'defer',
            reason=POLICY + ': ' + ('Exact pinned ESDB record, eligible WordNet role and spelling/usage corroboration; automated source policy, not human review.' if eligible else 'Insufficient corroboration or model veto; no nonword finding.'),
            proofIds=[p['id'] for p in candidate['proofs']]))
    return output


def adopt(args):
    directory = h.external(args.work_dir)
    with h.lock(directory):
        config, connection = h.state(directory)
        try:
            h.require(not config.get('sourceProfile'), 'Use dictionary_sources.py adopt for dictionary catalog runs')
            rows = connection.execute('select * from candidates where decision is null order by position').fetchall()
            candidates = [(json.loads(row['payload']), json.loads(row['proposal']) if row['proposal'] else None) for row in rows]
            if not candidates:
                return {'adopted': 0, 'alreadyReviewed': True}
            result = decisions(config, candidates, args.source_dir.resolve(), args.esdb_dir.resolve(), args.references)
            h.validate_decisions(result, [c for c, _ in candidates])
            log = directory / ('auto-review-' + h.replay.sha(directory / 'candidates.jsonl')[:16] + '.jsonl')
            if log.exists():
                h.require(h.json_lines(log) == result, 'Existing automatic review differs')
            else:
                h.write_lines(log, result)
            with connection:
                for item in result:
                    connection.execute('update candidates set decision=?,result=? where id=? and decision is null',
                        (item['decision'], json.dumps(item, ensure_ascii=False, sort_keys=True), item['id']))
            return {'policy': POLICY, 'adopted': sum(r['decision'] == 'include' for r in result),
                    'deferred': sum(r['decision'] == 'defer' for r in result), 'reviewFile': str(log)}
        finally:
            connection.close()


def pending_day(root, today):
    pending = sorted(p.name for p in root.iterdir() if p.is_dir() and
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name) and p.name <= today and
        (p / "run.json").exists() and not (root / (p.name + ".json")).exists())
    return pending[0] if pending else today


def daily(args):
    root = h.external(args.work_dir)
    with h.lock(root):
        # One idempotent run per local calendar day; failures resume the same run.
        from zoneinfo import ZoneInfo
        day = pending_day(root, dt.datetime.now(ZoneInfo(args.timezone)).date().isoformat())
        run = root / day
        checkpoint = root / (day + '.json')
        if checkpoint.exists():
            return h.replay.read_json(checkpoint)
        options = argparse.Namespace(**vars(args))
        options.work_dir = run
        if not (run / 'run.json').exists():
            h.prepare(options)
        adoption = adopt(options)
        config, connection = h.state(run)
        try:
            count = connection.execute("select count(*) from candidates where decision='include'").fetchone()[0]
            attempts = connection.execute('select count(*) from attempts').fetchone()[0]
        finally:
            connection.close()
        result = dict(day=day, policy=POLICY, adoption=adoption, approvedCandidates=count,
                      apiCallsThisCommand=0, recordedApiAttempts=attempts)
        if count:
            options.out = run / 'result'
            if not options.out.exists():
                h.build(options)
            result['verifiedBuild'] = h.replay.read_json(options.out / 'verification.json')
            result['supplement'] = str(options.out / 'supplement')
        h.dump(checkpoint, result)
        return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['adopt', 'daily'])
    p.add_argument('--work-dir', type=Path, required=True)
    p.add_argument('--source-dir', type=Path, required=True)
    p.add_argument('--esdb-dir', type=Path, required=True)
    p.add_argument('--references', type=Path)
    p.add_argument('--timezone', default='America/Toronto')
    p.add_argument('--assets', type=Path)
    p.add_argument('--supplement', type=Path, default=s.SUPPLEMENT)
    p.add_argument('--cli', type=Path, default=h.REPO / 'english-ime/build/install/english-ime/bin/english-ime')
    p.add_argument('--max-candidates', type=int, choices=range(1, 100001), default=1000, metavar='N')
    p.add_argument('--fetch-sources', action='store_true')
    return p


if __name__ == '__main__':
    args = parser().parse_args()
    if args.command == 'daily' and args.assets is None:
        raise SystemExit('daily requires --assets for the currently adopted supplement')
    print(json.dumps(globals()[args.command](args), ensure_ascii=False, indent=2))
