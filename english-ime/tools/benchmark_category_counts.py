"""Compare category counts and a no-op load/publish/verify extension.

Use a pinned baseline source and the same already-materialized public lexicon.
Fresh temporary output trees are compared byte-for-byte by file SHA-256.
This measures Python generation, not Android or the JVM consumer.
"""
import argparse
import ast
from collections import defaultdict
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def legacy_counts(model):
    return {name: len({surface for (_, surface), values in model.members.items() if name in values})
            for name in sorted(model.names)}


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def equivalence(model, optimized):
    expected = legacy_counts(model)
    actual = optimized(model)
    assert list(expected.items()) == list(actual.items())
    assert list(actual) == sorted(model.names)
    return expected


def worker(args):
    import extend_lexicon as extension
    calls = []
    source = args.module.read_text()
    tree = ast.parse(source)
    if args.mode == 'baseline':
        class CountSites(ast.NodeTransformer):
            def visit_Assign(self, node):
                self.generic_visit(node)
                if any(isinstance(t, ast.Name) and t.id in {'categories', 'category_counts'} for t in node.targets) and isinstance(node.value, ast.DictComp):
                    node.value = ast.copy_location(ast.Call(func=ast.Name(id='_record_category_counts', ctx=ast.Load()), args=[node.value], keywords=[]), node.value)
                return node
        tree = ast.fix_missing_locations(CountSites().visit(tree))
    namespace = {'__name__': 'benchmark_pipeline', '__file__': str(args.module),
                 '_record_category_counts': lambda result: (calls.append(len(result)), result)[1]}
    exec(compile(tree, str(args.module), 'exec'), namespace)
    if args.mode != 'baseline':
        original = namespace['category_surface_counts']
        namespace['category_surface_counts'] = lambda model: (calls.append(len(model.names)), original(model))[1]
    from types import SimpleNamespace
    pipeline = SimpleNamespace(**namespace)
    extension.pipeline = pipeline
    started = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()):
        model, rows, sources, notices, pending = extension.load_base(args.directory, args.seed)
        with tempfile.TemporaryDirectory(prefix='category-count-benchmark-', dir=args.out) as temp:
            output = Path(temp) / 'result'
            summary = pipeline.publish(model, rows, args.directory / 'inventory.jsonl', output,
                sources, notices, pending, reviewed_decisions=args.directory / 'reviewed-overrides.tsv',
                allow_input_spellings=True,
                corrections=pipeline.read_table(args.directory / 'surface-corrections.tsv', 'corrections'))
            elapsed = time.perf_counter() - started
            files = {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob('*')) if p.is_file()}
    assert len(calls) == 3, calls
    result = {'mode': args.mode, 'elapsedSeconds': elapsed, 'categoryCountCalls': len(calls),
              'files': files, 'summary': summary, 'sourceSha256': digest(args.module)}
    args.worker_result.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


def main(args):
    args.out.mkdir(parents=True, exist_ok=False)
    baseline = load_module(args.baseline, 'counts_baseline')
    candidate = load_module(args.candidate, 'counts_candidate')
    started = time.perf_counter()
    model = baseline.Lexicon(args.directory / 'grammar')
    load_seconds = time.perf_counter() - started
    expected = equivalence(model, candidate.category_surface_counts)
    # Include empty categories, homographs, overlapping memberships and an
    # unknown category; all are counted with the legacy lookup semantics.
    from types import SimpleNamespace
    fixture = SimpleNamespace(names={'verb', 'noun', 'empty', 'proper'}, members={
        ('noun-1','saw'):{'noun'}, ('verb-1','saw'):{'verb'},
        ('noun-2','saw'):{'noun','proper'}, ('noun-3','Saw'):{'proper'},
        ('unicode','é'):{'noun','outside'}, ('unassigned','unused'):set()})
    equivalence(fixture, candidate.category_surface_counts)
    local = {'baseline': [], 'candidate': []}
    functions = {'baseline': legacy_counts, 'candidate': candidate.category_surface_counts}
    for i in range(args.local_repetitions):
        for name in (['baseline','candidate'] if i % 2 == 0 else ['candidate','baseline']):
            started = time.perf_counter(); actual = functions[name](model); elapsed = time.perf_counter() - started
            assert list(actual.items()) == list(expected.items())
            local[name].append(elapsed)
            print(json.dumps({'phase':'local','mode':name,'seconds':elapsed}), flush=True)
    member_forms = len(model.members)
    membership_count = sum(map(len, model.members.values()))
    del model
    import gc
    gc.collect()
    end_to_end = {'baseline': [], 'candidate': []}; reference_files = None
    env = dict(os.environ, PYTHONHASHSEED='0')
    for i in range(args.e2e_repetitions):
        for name in (['baseline','candidate'] if i % 2 == 0 else ['candidate','baseline']):
            result_path = args.out / f'e2e-{i+1}-{name}.json'
            cmd = [sys.executable, str(Path(__file__).resolve()), '--worker', '--mode', name,
                '--module', str(args.baseline if name == 'baseline' else args.candidate),
                '--directory', str(args.directory), '--seed', str(args.seed), '--tools', str(args.tools),
                '--out', str(args.out), '--worker-result', str(result_path)]
            with (args.out / f'e2e-{i+1}-{name}.log').open('x') as log:
                completed = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
            assert completed.returncode == 0, (name, i, completed.returncode)
            result = json.loads(result_path.read_text())
            if reference_files is None: reference_files = result['files']
            assert result['files'] == reference_files, 'Generated file bytes differ'
            end_to_end[name].append(result['elapsedSeconds'])
            print(json.dumps({'phase':'end_to_end','mode':name,'repetition':i+1,'seconds':result['elapsedSeconds'],'categoryCountCalls':result['categoryCountCalls'],'allFileHashesEqual':True}), flush=True)
    output = {'python':sys.version,'executable':sys.executable,'platform':platform.platform(),
        'baseManifestSha256':digest(args.directory/'manifest.json'), 'base':str(args.directory),
        'baselineSha256':digest(args.baseline),'candidateSha256':digest(args.candidate),
        'modelLoadSeconds':load_seconds, 'memberForms':member_forms,'categories':len(expected),
        'memberships':membership_count, 'legacyCategoryProbesPerCall':member_forms*len(expected),
        'callsPerNoOpExtension':3,'localSeconds':local,'endToEndSeconds':end_to_end,
        'equivalentOrderedCounts':True,'equivalentEveryGeneratedFileHash':True,
        'emptyAndHomographFixturePassed':True,'categoryCounts':expected,
        'scope':'No-op extension: load_base verify + publish + staged verify, including existing input/cost/order/evidence preservation; no external-source reimport, JVM or Android timing',
        'measurementConditions':'Alternating sequential modes, identical interpreter/input, child PYTHONHASHSEED=0; no parallel benchmark workers'}
    for label, values in [('local',local),('endToEnd',end_to_end)]:
        output[label+'MedianSeconds']={k:statistics.median(v) for k,v in values.items()}
        output[label+'Speedup']=statistics.median(values['baseline'])/statistics.median(values['candidate'])
    (args.out/'result.json').write_text(json.dumps(output,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in output.items() if 'Speedup' in k or 'MedianSeconds' in k}),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','candidate','directory','seed','tools','out','module','worker-result']:
        p.add_argument('--'+name,type=Path)
    p.add_argument('--local-repetitions',type=int,default=7)
    p.add_argument('--e2e-repetitions',type=int,default=3)
    p.add_argument('--worker',action='store_true');p.add_argument('--mode',choices=['baseline','candidate'])
    args=p.parse_args();sys.path.insert(0,str(args.tools.resolve()))
    if args.worker:worker(args)
    else:main(args)
