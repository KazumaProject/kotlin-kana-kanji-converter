#!/usr/bin/env python3
"""Small GitHub adapter. Issue text is JSON data, never shell code or a branch/ref."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request

import feedback_data as data

WORK = Path('build/dictionary-feedback')
MARKER = '<!-- dictionary-feedback -->'
CONTEXT = 'dictionary-feedback/verification'
BOT = 'github-actions[bot]'


def api(path, body=None, method=None):
    token = os.environ['GH_TOKEN']
    url = 'https://api.github.com' + path
    request = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
        method=method or ('GET' if body is None else 'POST'), headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'dictionary-feedback',
            'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            result = json.loads(raw) if raw else None
            if isinstance(result, dict) and result.get('errors'):
                raise RuntimeError('GitHub GraphQL operation was rejected')
            return result
    except urllib.error.HTTPError as error:
        # Do not print tokens, headers or raw user-controlled responses.
        raise RuntimeError(f'GitHub API {error.code}: {method or request.method} {path}') from None


def repo(path): return '/repos/' + data.REPOSITORY + path


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def output(name, value):
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream: stream.write(f'{name}={value}\n')


def load_context(): return json.loads((WORK / 'context.json').read_text())


def fresh(context):
    issue = api(repo('/issues/' + str(context['issue'])))
    if (issue.get('user', {}).get('login') != data.OWNER or issue.get('state') != 'open'
            or hashlib.sha256((issue.get('body') or '').encode()).hexdigest() != context['bodySha256']):
        raise ValueError('Issue changed during processing; the next Issue event must regenerate the proposal')
    return issue


def find_pr(number):
    query = urllib.parse.urlencode({'state': 'open', 'head': data.OWNER + ':dictionary-feedback/issue-' + str(number)})
    values = api(repo('/pulls?' + query))
    if len(values) > 1: raise ValueError('Multiple open PRs for one Issue')
    if values and values[0]['user']['login'] != BOT: raise ValueError('Existing branch is not owned by the automation')
    return values[0] if values else None


def comment(number, body):
    existing = api(repo(f'/issues/{number}/comments?per_page=100'))
    match = next((item for item in existing if item.get('user', {}).get('login') == BOT and item['body'].startswith(MARKER)), None)
    text = MARKER + '\n' + body
    if match: api(repo('/issues/comments/' + str(match['id'])), dict(body=text), 'PATCH')
    else: api(repo(f'/issues/{number}/comments'), dict(body=text))


def draft(pr, ready=False):
    if ready and not pr['draft'] or not ready and pr['draft']: return
    mutation = 'markPullRequestReadyForReview' if ready else 'convertPullRequestToDraft'
    api('/graphql', dict(query='mutation($id:ID!){' + mutation + '(input:{pullRequestId:$id}){pullRequest{id}}}', variables=dict(id=pr['node_id'])))


def status(sha, state, description):
    api(repo('/statuses/' + sha), dict(state=state, context=CONTEXT, description=description,
        target_url=f'https://github.com/{data.REPOSITORY}/actions/runs/{os.environ["GITHUB_RUN_ID"]}'))


def fetch(event_path):
    event = json.loads(event_path.read_text())
    if os.environ.get('GITHUB_REPOSITORY') != data.REPOSITORY: raise ValueError('Unexpected repository')
    actor = os.environ.get('GITHUB_ACTOR')
    if actor != data.OWNER: raise ValueError('Only the configured owner may trigger this workflow')
    number = event.get('issue', {}).get('number') or event.get('inputs', {}).get('issue_number')
    if not str(number).isdigit() or int(number) <= 0: raise ValueError('Invalid Issue number')
    issue = api(repo('/issues/' + str(int(number))))
    if issue.get('user', {}).get('login') != data.OWNER or issue.get('pull_request') or issue.get('state') != 'open':
        output('active', 'false'); return
    if '### 申請の種類' not in (issue.get('body') or ''):
        output('active', 'false'); return
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / 'issue.json').write_text(data.encode(issue))
    context = dict(issue=int(number), bodySha256=hashlib.sha256((issue.get('body') or '').encode()).hexdigest())
    (WORK / 'context.json').write_text(data.encode(context))
    output('active', 'true'); output('issue', int(number))


def publish():
    context = load_context(); fresh(context)
    result = json.loads((WORK / 'result.json').read_text())
    if result['status'] != 'ready': raise ValueError('No validated proposal')
    previous = find_pr(context['issue'])
    branch = 'dictionary-feedback/issue-' + str(context['issue'])
    remote = git('ls-remote', '--heads', 'origin', 'refs/heads/' + branch)
    old_sha = remote.split()[0] if remote else None
    if old_sha:
        if previous and previous['head']['sha'] != old_sha: raise ValueError('Existing branch differs from its automation PR')
        commits = (api(repo(f'/pulls/{previous["number"]}/commits?per_page=100')) if previous
                   else [api(repo('/commits/' + old_sha))])
        if len(commits) >= 100 or any((c.get('author') or {}).get('login') != BOT for c in commits):
            raise ValueError('Manual commits detected; automation will not overwrite this branch')
        if previous: draft(previous)
    git('checkout', '-b', branch)
    # Stage only generated dictionary data and catalogs. Never stage downloaded resources or code.
    tracked_roots = ['src/main/dictionary-feedback/requests', 'src/main/dictionary-feedback/system.json',
                     'src/main/classification/reviews', 'src/main/classification/distribution-candidates.tsv.gz',
                     'src/main/classification/distribution-decisions.tsv.gz', 'src/main/classification/distribution-manifest.json',
                     'src/main/specialist/distribution-candidates.tsv.gz', 'src/main/specialist/provenance.jsonl.gz',
                     'src/main/specialist/distribution-manifest.json', 'docs/classified-dictionary-catalog']
    for path in tracked_roots:
        if Path(path).exists(): git('add', '--', path)
    git('-c', 'user.name=' + BOT, '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
        'commit', '-m', 'Dictionary update from #' + str(context['issue']))
    sha = git('rev-parse', 'HEAD')
    args = ['push']
    if old_sha: args.append('--force-with-lease=refs/heads/' + branch + ':' + old_sha)
    else: args.append('--force-with-lease=refs/heads/' + branch + ':')
    git(*args, 'origin', 'HEAD:refs/heads/' + branch)
    body = (WORK / 'result.md').read_text() + '\n\n検証中です。成功後にレビュー可能になります。\n\nCloses #' + str(context['issue'])
    if previous:
        pr = api(repo('/pulls/' + str(previous['number'])), dict(body=body), 'PATCH')
    else:
        repository = api(repo(''))
        pr = api(repo('/pulls'), dict(title='辞書更新 #' + str(context['issue']), head=branch,
            base=repository['default_branch'], body=body, draft=True))
    context.update(sha=sha, pr=pr['number'], url=pr['html_url'])
    (WORK / 'published.json').write_text(data.encode(context))
    output('sha', sha)
    status(sha, 'pending', 'Dictionary verification is running')
    comment(context['issue'], '変更案を作成しました: ' + pr['html_url'] + '\n\n検証中です。')


def notify():
    context = load_context(); fresh(context)
    result = json.loads((WORK / 'result.json').read_text())
    pr = find_pr(context['issue'])
    if pr:
        draft(pr)
        status(pr['head']['sha'], 'failure', 'Issue changed; this proposal requires regeneration')
    comment(context['issue'], (WORK / 'result.md').read_text())
    output('status', result['status'])


def finish(success):
    path = WORK / 'published.json'
    if not path.exists():
        # Also report setup/generation failures; do not leave a silent pending request.
        if not success and (WORK / 'context.json').exists():
            context = load_context()
            comment(context['issue'], '処理が失敗しました。辞書への反映は完了していません。' +
                f'\n\n[Actionsの検証ログ](https://github.com/{data.REPOSITORY}/actions/runs/{os.environ["GITHUB_RUN_ID"]})を確認してください。')
        return
    context = json.loads(path.read_text())
    pr = api(repo('/pulls/' + str(context['pr'])))
    if pr['head']['sha'] != context['sha']: raise ValueError('PR head changed during verification')
    if success:
        try: fresh(context)
        except ValueError: success = False
    status(context['sha'], 'success' if success else 'failure', 'Dictionary verification passed' if success else 'Dictionary verification failed or Issue changed')
    if success:
        body = (WORK / 'result.md').read_text() + '\n\n生成した配布ZIPの検証とテストに成功しました。実アプリの候補順位は未確認です。\n\nCloses #' + str(context['issue'])
        api(repo('/pulls/' + str(context['pr'])), dict(body=body), 'PATCH')
        draft(pr, ready=True)
    comment(context['issue'], ('検証に成功しました。PRを確認してマージできます: ' if success else '検証が完了しませんでした。Draft PRとActionsログを確認してください: ') + context['url'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['fetch', 'publish', 'notify', 'finish'])
    parser.add_argument('--event', type=Path)
    parser.add_argument('--success', choices=['true', 'false'], default='false')
    args = parser.parse_args()
    if args.command == 'fetch': fetch(args.event)
    elif args.command == 'publish': publish()
    elif args.command == 'notify': notify()
    else: finish(args.success == 'true')


if __name__ == '__main__': main()
