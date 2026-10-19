#!/usr/bin/env python3
"""Replay saved pilot proposals and independent reviews against frozen inputs."""
import argparse
from pathlib import Path
import tempfile

import person_subclassification as pipeline


def check(root):
    directory = root / 'src/main/classification/person-subclassification'
    with tempfile.TemporaryDirectory(prefix='person-pilot-') as temporary:
        workspace = Path(temporary) / 'workspace'
        snapshot = pipeline.prepare(root, workspace, batch_size=25,
                                    selection=directory / 'pilot-selection-2026-10-19.jsonl')
        result = pipeline.evaluate(root, workspace,
                                   [directory / 'pilot-proposals-2026-10-19.jsonl'],
                                   [directory / 'pilot-reviews-2026-10-19.jsonl'])
        pipeline.require(result['proposal_count'] == result['review_count'] == snapshot['selected_count'] == 8,
                         'pilot must contain eight independently reviewed proposals')
        pipeline.require(result['counts'] == {'hold': result['item_count']},
                         'pilot contains no completed appearance checks; all items must remain held')
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        check(args.root)
        print('Saved subagent proposals and independent reviews verified; no pilot items admitted.')
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f'error: {error}\n')
