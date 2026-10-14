#!/usr/bin/env python3
"""Apply a complete Luna run, rebuild specialist duplicates, and verify assets."""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import sys

import luna_reclassification as reclassification


def finish(root, wait_controller=False):
    work = root / 'build/luna-classification'
    work.mkdir(parents=True, exist_ok=True)
    report = {'policy_version': reclassification.POLICY, 'state': 'validating', 'stages': []}

    def save():
        temporary = work / 'completion.json.tmp'
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        temporary.replace(work / 'completion.json')

    with (work / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | (0 if wait_controller else fcntl.LOCK_NB))
        save()
        try:
            # Exact coverage is required before any dictionary mutation.
            _, targets, _, results = reclassification.load_results(root, work / 'results')
            report.update(targets=len(targets), judged=len(results), state='applying')
            save()
            reclassification.apply(root, work / 'results')
            stages = [
                ('classification', [sys.executable, 'scripts/classified_distribution.py', 'verify']),
                ('inventory', ['./gradlew', 'exportExistingDictionaryInventory']),
                ('specialist', [sys.executable, 'scripts/specialist_distribution.py', 'freeze']),
                ('catalog', [sys.executable, 'scripts/write_classified_dictionary_catalog.py']),
                ('catalog-check', [sys.executable, 'scripts/write_classified_dictionary_catalog.py', '--check']),
                ('assets-tests', ['./gradlew', 'buildDictionaryDistributionManifest', 'test', 'check']),
                ('conversions', ['./gradlew', '--quiet', 'convertCandidates',
                                 '--args=--count 5 しろ しろい しろくろ しろあり']),
            ]
            for name, command in stages:
                report['state'] = name
                save()
                with (work / ('completion-' + name + '.log')).open('w') as output:
                    subprocess.run(command, cwd=root, stdout=output, stderr=subprocess.STDOUT, check=True)
                report['stages'].append(name)
                save()
            directory = root / 'src/main/classification'
            manifest = json.loads((directory / 'distribution-manifest.json').read_text())
            report.update(state='complete',
                          effective_actions=manifest['provenance']['lunaReclassification']['effectiveActions'],
                          dictionary_rows=manifest['dictionaryRows'],
                          archive_sha256=reclassification.d.sha(root / 'release_zips/japanese_keyboard_dictionary_assets.zip'),
                          app_candidate_ranking='unverified')
            save()
        except BaseException as error:
            report.update(state='failed', error=str(error), error_type=type(error).__name__)
            save()
            raise
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--wait-controller', action='store_true',
                        help='Wait for the currently running controller to release its lock.')
    arguments = parser.parse_args()
    print(json.dumps(finish(arguments.root.resolve(), arguments.wait_controller), ensure_ascii=False))
