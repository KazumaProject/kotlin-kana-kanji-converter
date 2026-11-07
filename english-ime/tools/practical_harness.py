"""Audit basic English and typo suggestions on the actual JVM conversion CLI.

Diagnostic only: does not add dictionary entries, correct text, call an API,
schedule work, or claim that an Android IME has passed acceptance testing.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import practical_sources as sources
import vocabulary_harness as shared
from replay_source import require, sha

POLICY = 'basic-ime-v1'


def tool_hashes():
    directory = Path(__file__).parent
    return {name: sha(directory / name) for name in
        ['practical_harness.py', 'practical_sources.py', 'vocabulary_harness.py', 'vocabulary_sources.py']}


def prepare(args):
    destination = shared.external(args.out)
    directory = shared.external(args.source_dir)
    require(not destination.exists(), 'Suite already exists; use a new output directory')
    if args.fetch_sources:
        sources.fetch(directory)
    sources.verify(directory)
    words = sources.headwords(directory)
    cases = sources.cases_for(words, (directory / 'codespell.txt').read_text(encoding='utf-8').splitlines())
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.basic-suite-', dir=destination.parent) as temporary:
        staging = Path(temporary)
        shared.write_lines(staging / 'cases.jsonl', cases)
        shared.dump(staging / 'attribution.json', sources.attribution())
        notice = ['English IME basic diagnostic data',
            'Derived evaluation collection: CC BY-SA 4.0 — ' + sources.CC4,
            'Source material retains the licenses below. Harness program code: MIT.', sources.CHANGES, '']
        for record in sources.attribution()['sources']:
            notice += [record['title'], record['attribution'], record.get('url', record['licenseUrl']),
                       record['license'] + ' — ' + record['licenseUrl'], '']
        (staging / 'ATTRIBUTION.txt').write_text('\n'.join(notice), encoding='utf-8')
        manifest = dict(schemaVersion=1, policy=POLICY, toolHashes=tool_hashes(), sourcePins=sources.PINS,
            targetSpellings=len(words), targetKeys=len({sources.key(word) for word in words}),
            cases=len(cases), groups=dict(Counter(case['scenario'] for case in cases)),
            splitPolicy='intended-spelling-casefold-sha256-mod5-v1; not lemma-family disjoint',
            splitCounts=dict(Counter(case['split'] for case in cases)),
            files={name: sha(staging / name) for name in ['cases.jsonl', 'attribution.json', 'ATTRIBUTION.txt']})
        shared.dump(staging / 'suite.json', manifest)
        staging.rename(destination)
    return dict(suite=str(destination), targetSpellings=len(words), cases=len(cases), groups=manifest['groups'])


def load_suite(directory):
    config = json.loads((directory / 'suite.json').read_text(encoding='utf-8'))
    require(config['schemaVersion'] == 1 and config['policy'] == POLICY and config['sourcePins'] == sources.PINS,
        'Unknown or changed suite source policy')
    require(set(config['files']) == {'cases.jsonl', 'attribution.json', 'ATTRIBUTION.txt'}, 'Missing suite attribution')
    for name, digest in config['files'].items():
        require(not (directory / name).is_symlink() and sha(directory / name) == digest, 'Changed suite file: ' + name)
    require(json.loads((directory / 'attribution.json').read_text()) == sources.attribution(), 'Changed source licenses')
    cases = shared.json_lines(directory / 'cases.jsonl')
    require(len(cases) == config['cases'] and len({case['id'] for case in cases}) == len(cases), 'Changed case inventory')
    return config, cases


def select_cases(cases, split, limit):
    require(limit > 0, 'Rank limit must be positive')
    groups = defaultdict(list)
    for case in cases:
        if split == 'all' or case['split'] == split:
            groups[(case['scenario'], case['operation'])].append(case)
    buckets = {group: iter(sorted(rows, key=lambda row: hashlib.sha256(row['id'].encode()).digest()))
               for group, rows in sorted(groups.items())}
    selected = []
    while buckets and len(selected) < limit:
        for group in list(buckets):
            case = next(buckets[group], None)
            if case is None:
                del buckets[group]
            else:
                selected.append(case)
                if len(selected) == limit:
                    break
    return selected


def engine_hashes(cli):
    require(cli.is_file(), 'Missing installed CLI: ' + str(cli))
    libraries = sorted((cli.parent.parent / 'lib').glob('*.jar'))
    require(libraries, 'Use an installed distribution with its lib/*.jar files')
    return dict(launcher=sha(cli), libraries={path.name: sha(path) for path in libraries})


def score(case, response):
    require(response.get('schemaVersion') == 1 and response.get('input') == case['input'], 'Unexpected CLI response')
    rows = response['candidates']
    require([row['rank'] for row in rows] == list(range(1, len(rows) + 1)), 'Invalid candidate ranks')
    # Display spelling is case-sensitive; a literal echo or partially copied word
    # cannot establish dictionary retrieval of the expected candidate.
    ranks = [shared.retrieved_rank({'candidates': [row]}, word)
             for row in rows for word in case['expected'] if row['text'] == word]
    ranks = [rank for rank in ranks if rank is not None]
    raw = next((row['rank'] for row in rows if row['text'] in case['expected']), None)
    return dict(rank=min(ranks) if ranks else None, displayRank=raw,
        top1=rows[0]['text'] if rows else None,
        top5=[row['text'] for row in rows[:5]])


def groups_for(case):
    source_groups = sorted({sources.PINS[proof['source']]['kind'] for proof in case['proofs']
                            if proof['source'] in sources.PINS})
    return (['scenario:' + case['scenario']] + (['edit:' + case['operation']] if case['operation'] else []) +
            ['source:' + group for group in source_groups])


def metrics(cases, details, pairs):
    counts = defaultdict(Counter)
    reading_keys = {reading for reading, _ in pairs}
    for case in cases:
        targets = case['expected']
        # Exact output spelling, not a casefolded inventory proxy.
        covered = any((reading, word) in pairs for word in targets for reading in shared.readings(word))
        known_input = sources.key(case['input']) in reading_keys if case['scenario'].startswith('typo-') else False
        for group in groups_for(case):
            counts[group]['cases'] += 1
            counts[group]['targetCovered'] += covered
            counts[group]['knownInputCases'] += known_input
            if case['id'] in details:
                detail = details[case['id']]
                rank = detail['rank']
                counts[group]['rankCases'] += 1
                counts[group]['dictionaryTop1'] += rank == 1
                counts[group]['dictionaryTop5'] += rank is not None and rank <= 5
                counts[group]['dictionaryTop10'] += rank is not None and rank <= 10
                counts[group]['displayTop1'] += detail['displayRank'] == 1
                if case['scenario'] == 'preserve':
                    counts[group]['preservedTop1'] += detail['displayRank'] == 1
    return {group: dict(values) for group, values in sorted(counts.items())}


def regressions(cases, before, after):
    changes = []
    for case in cases:
        old, new = before[case['id']], after[case['id']]
        old_rank, new_rank = old['rank'], new['rank']
        if case['scenario'] == 'preserve':
            lost = old['displayRank'] == 1 and new['displayRank'] != 1
        else:
            lost = (old_rank is not None and old_rank <= 5 and (new_rank is None or new_rank > 5)) or (
                case['scenario'] == 'basic-exact' and old_rank == 1 and new_rank != 1)
        if lost:
            changes.append(dict(id=case['id'], scenario=case['scenario'], input=case['input'],
                expected=case['expected'], before=old, after=new))
    return changes


def evaluate(args):
    suite = shared.external(args.suite)
    config, all_cases = load_suite(suite)
    cases = [case for case in all_cases if args.split == 'all' or case['split'] == args.split]
    require(cases, 'Empty requested split')
    selected = select_cases(cases, args.split, args.rank_limit)
    assets = {'before': args.baseline_assets.resolve(), 'after': (args.candidate_assets or args.baseline_assets).resolve()}
    clis = {'before': (args.baseline_cli or args.cli).resolve(), 'after': args.cli.resolve()}
    frozen = dict(schemaVersion=1, policy=POLICY, suiteSha256=sha(suite / 'suite.json'),
        caseSha256=config['files']['cases.jsonl'], toolHashes=tool_hashes(), split=args.split,
        rankLimit=args.rank_limit, workerLimit=args.jobs, rankCaseIds=[case['id'] for case in selected],
        samplePolicy='scenario-and-operation-round-robin-sha256-v1',
        assetHashes={label: shared.asset_hashes(path) for label, path in assets.items()},
        engineHashes={label: engine_hashes(path) for label, path in clis.items()},
        attribution=sources.attribution(), cliOnly=True, acceptanceThresholdsAgreed=False,
        limitations=['No Android app/device verification or interactive typing latency/memory measurement.',
            'Listed and synthetic typos are separate diagnostics, not a measured user-error distribution.',
            'Targets are basic headwords, not independently reviewed inflections or full everyday vocabulary.',
            'Holdout is spelling-disjoint, not lemma-family disjoint; repeated inspection consumes its independence.',
            'No automatic dictionary adoption, text replacement, billing, or recurring task.'])
    destination = shared.external(args.out)
    require(all(not destination.is_relative_to(path) and not path.is_relative_to(destination)
                for path in [suite, *assets.values(), clis['before'].parent.parent, clis['after'].parent.parent]),
        'Evaluation output must be separate from the suite, assets and installed CLI')
    with shared.lock(destination):
        run = destination / 'run.json'
        if run.exists():
            require(json.loads(run.read_text()) == frozen, 'Resume requires identical suite, assets, engine and options')
        else:
            require(set(path.name for path in destination.iterdir()) <= {'.lock'}, 'Output directory is not empty')
            shared.dump(run, frozen)
            for name in config['files']:
                shutil.copyfile(suite / name, destination / name)
        for name, digest in config['files'].items():
            require(sha(destination / name) == digest, 'Changed copied suite or attribution: ' + name)
        results, details = {}, {}
        inventories = {}
        for label in ['before', 'after']:
            fingerprint = (frozen['assetHashes'][label], frozen['engineHashes'][label])
            if label == 'after' and fingerprint == (frozen['assetHashes']['before'], frozen['engineHashes']['before']):
                details[label] = details['before']
                results[label] = results['before']
                inventories[label] = inventories['before']
                continue
            inventory = destination / (label + '-inventory.jsonl')
            # Export atomically, so a failed JVM invocation cannot become a frozen inventory.
            if not inventory.exists():
                with tempfile.TemporaryDirectory(prefix='.inventory-', dir=destination) as temporary:
                    output = Path(temporary) / 'inventory.jsonl'
                    shared.cli_run(clis[label], 'export-candidates', '--assets', assets[label], '--out', output)
                    output.rename(inventory)
            pairs = {(row['reading'], row['surface']) for row in shared.json_lines(inventory)}
            inventories[label] = pairs
            cache = destination / (label + '-ranks.jsonl')
            recorded = shared.json_lines(cache) if cache.exists() else []
            require(len({row['id'] for row in recorded}) == len(recorded) and
                {row['id'] for row in recorded} <= set(frozen['rankCaseIds']), 'Invalid saved rank cache')
            case_index = {case['id']: case for case in selected}
            require(all(score(case_index[row['id']], row['response']) == row['result'] for row in recorded),
                'Changed cached candidate evidence')
            details[label] = {row['id']: row['result'] for row in recorded}
            remaining = [case for case in selected if case['id'] not in details[label]]
            def query(case):
                return json.loads(shared.cli_run(clis[label], 'convert', '--assets', assets[label],
                    '--text', case['input'], '--mode', case['mode'], '--limit', 10, '--format', 'json', capture=True).stdout)
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                # Bound in-flight JVMs and keep the checkpoint order deterministic.
                for start in range(0, len(remaining), args.jobs):
                    chunk = remaining[start:start + args.jobs]
                    for case, response in zip(chunk, pool.map(query, chunk)):
                        result = score(case, response)
                        recorded.append(dict(id=case['id'], result=result, response=response))
                        with tempfile.TemporaryDirectory(prefix='.ranks-', dir=destination) as temporary:
                            checkpoint = Path(temporary) / 'ranks.jsonl'
                            shared.write_lines(checkpoint, recorded)
                            checkpoint.replace(cache)
                        details[label][case['id']] = result
            results[label] = metrics(cases, details[label], pairs)
        require({label: shared.asset_hashes(path) for label, path in assets.items()} == frozen['assetHashes'] and
            {label: engine_hashes(path) for label, path in clis.items()} == frozen['engineHashes'], 'Inputs changed during evaluation')
        lost = regressions(selected, details['before'], details['after'])
        old_pairs, new_pairs = inventories['before'], inventories['after']
        coverage_lost = [case['id'] for case in cases if
            any((reading, word) in old_pairs for word in case['expected'] for reading in shared.readings(word)) and not
            any((reading, word) in new_pairs for word in case['expected'] for reading in shared.readings(word))]
        missing_basic = {}
        for label in ['before', 'after']:
            pairs = inventories[label]
            missing_basic[label] = sorted({word for case in cases if case['scenario'] == 'basic-exact'
                for word in case['expected'] if not any((reading, word) in pairs for reading in shared.readings(word))})
            diagnostics = []
            for case in selected:
                detail = details[label][case['id']]
                registered = any((reading, word) in pairs for word in case['expected'] for reading in shared.readings(word))
                if case['scenario'] == 'preserve':
                    diagnosis = 'preserved' if detail['displayRank'] == 1 else 'changed-first-candidate'
                elif detail['rank'] is not None:
                    diagnosis = 'top1' if detail['rank'] == 1 else 'lower-ranked'
                else:
                    diagnosis = 'retrieval-miss' if registered else 'target-not-registered'
                diagnostics.append(case | detail | dict(targetRegistered=registered, diagnosis=diagnosis))
            path = destination / (label + '-diagnostics.jsonl')
            with tempfile.TemporaryDirectory(prefix='.diagnostics-', dir=destination) as temporary:
                checkpoint = Path(temporary) / path.name
                shared.write_lines(checkpoint, diagnostics)
                checkpoint.replace(path)
        report = frozen | dict(cases=len(cases), rankCases=len(selected), results=results,
            rankRegressions=lost, coverageRegressions=coverage_lost,
            missingBasicSpellings=missing_basic,
            noMeasuredRegression=not lost and not coverage_lost,
            evidenceFiles={path.name: sha(path) for path in destination.glob('*.jsonl')})
        shared.dump(destination / 'report.json', report)
        return dict(report=str(destination / 'report.json'), cases=len(cases), rankCases=len(selected),
            results=results, rankRegressions=len(lost), coverageRegressions=len(coverage_lost),
            noMeasuredRegression=report['noMeasuredRegression'], acceptanceThresholdsAgreed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_command = commands.add_parser('prepare')
    prepare_command.add_argument('--source-dir', type=Path, required=True)
    prepare_command.add_argument('--out', type=Path, required=True)
    prepare_command.add_argument('--fetch-sources', action='store_true')
    evaluation = commands.add_parser('evaluate')
    for name in ['suite', 'baseline-assets', 'cli', 'out']:
        evaluation.add_argument('--' + name, type=Path, required=True)
    for name in ['candidate-assets', 'baseline-cli']:
        evaluation.add_argument('--' + name, type=Path)
    evaluation.add_argument('--split', choices=['dev', 'holdout', 'all'], default='dev')
    evaluation.add_argument('--rank-limit', type=int, default=1000)
    evaluation.add_argument('--jobs', type=int, choices=range(1, 5), default=1,
        help='Maximum simultaneous read-only JVM queries (default: 1)')
    evaluation.add_argument('--fail-on-regression', action='store_true')
    args = parser.parse_args()
    try:
        result = prepare(args) if args.command == 'prepare' else evaluate(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if getattr(args, 'fail_on_regression', False) and not result['noMeasuredRegression']:
            parser.exit(1, 'Measured regression; see report.json\n')
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
