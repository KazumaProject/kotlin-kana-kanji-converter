import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import feedback_data as data
import github_dictionary_feedback as github


class GitHubFeedbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.work_patch = patch.object(github, 'WORK', self.work); self.work_patch.start(); self.addCleanup(self.work_patch.stop)
        self.env = patch.dict(os.environ, GITHUB_REPOSITORY=data.REPOSITORY, GITHUB_ACTOR=data.OWNER, GITHUB_RUN_ID='123')
        self.env.start(); self.addCleanup(self.env.stop)
        self.body = '### 申請の種類\n\n単語追加'
        self.issue = dict(number=4, user=dict(login=data.OWNER), state='open', body=self.body)
        self.context = dict(issue=4, bodySha256=hashlib.sha256(self.body.encode()).hexdigest())
        (self.work / 'context.json').write_text(json.dumps(self.context))

    def event(self, value):
        path = self.work / 'event.json'; path.write_text(json.dumps(value)); return path

    @patch.object(github, 'api')
    def test_other_actors_cannot_trigger_processing(self, api):
        with patch.dict(os.environ, GITHUB_ACTOR='someone'):
            with self.assertRaisesRegex(ValueError, 'owner'): github.fetch(self.event(dict(issue=dict(number=4))))
        api.assert_not_called()

    @patch.object(github, 'output')
    @patch.object(github, 'api')
    def test_fetch_uses_fresh_issue_and_ignores_non_owner_or_non_form_issues(self, api, output):
        api.return_value = self.issue
        github.fetch(self.event(dict(issue=dict(number=4, body='stale event'))))
        self.assertEqual(json.loads((self.work / 'issue.json').read_text())['body'], self.body)
        output.assert_any_call('active', 'true')
        api.return_value = dict(self.issue, user=dict(login='someone'))
        github.fetch(self.event(dict(issue=dict(number=4))))
        output.assert_called_with('active', 'false')
        api.return_value = dict(self.issue, body='unrelated bug report')
        github.fetch(self.event(dict(issue=dict(number=4))))
        output.assert_called_with('active', 'false')

    @patch.object(github, 'api')
    def test_stale_issue_is_rejected_before_any_git_mutation(self, api):
        api.return_value = dict(self.issue, body=self.body + ' edited')
        with patch.object(github, 'git') as git:
            with self.assertRaisesRegex(ValueError, 'changed'): github.publish()
            git.assert_not_called()

    def test_existing_manual_commits_are_not_force_pushed(self):
        (self.work / 'result.json').write_text(json.dumps(dict(status='ready')))
        pr = dict(number=3, head=dict(sha='a' * 40), user=dict(login=github.BOT))
        with patch.object(github, 'fresh'), patch.object(github, 'find_pr', return_value=pr), \
                patch.object(github, 'git', return_value='a' * 40 + '\trefs/heads/dictionary-feedback/issue-4') as git, \
                patch.object(github, 'api', return_value=[dict(author=dict(login=data.OWNER))]):
            with self.assertRaisesRegex(ValueError, 'Manual commits'): github.publish()
            self.assertEqual(git.call_count, 1)

    def test_changed_noop_issue_invalidates_previous_proposal(self):
        (self.work / 'result.json').write_text(json.dumps(dict(status='needs-triage')))
        (self.work / 'result.md').write_text('exact match not found')
        pr = dict(head=dict(sha='a' * 40))
        with patch.object(github, 'fresh'), patch.object(github, 'find_pr', return_value=pr), \
                patch.object(github, 'draft') as draft, patch.object(github, 'status') as status, \
                patch.object(github, 'comment') as comment, patch.object(github, 'output'):
            github.notify(); draft.assert_called_once_with(pr)
            self.assertEqual(status.call_args.args[1], 'failure')
            comment.assert_called_once_with(4, 'exact match not found')

    def test_failed_or_stale_verification_does_not_mark_pr_ready(self):
        (self.work / 'published.json').write_text(json.dumps(dict(self.context, sha='a' * 40, pr=3, url='pr-url')))
        pr = dict(head=dict(sha='a' * 40), draft=True)
        with patch.object(github, 'api', return_value=pr), patch.object(github, 'draft') as draft, \
                patch.object(github, 'status') as status, patch.object(github, 'comment'), \
                patch.object(github, 'fresh', side_effect=ValueError('changed')):
            github.finish(True)
            draft.assert_not_called(); self.assertEqual(status.call_args.args[1], 'failure')


if __name__ == '__main__': unittest.main()
