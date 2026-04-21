from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.github import BadgeItem, CommitItem, GitHubDashboardResponse, StageMetric, WorkflowRun


class GitHubService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def build_dashboard(self, repository: str | None = None, branch: str | None = None) -> GitHubDashboardResponse:
        repository = (repository or self.settings.github_default_repo or '').strip('/')
        if not repository or '/' not in repository:
            raise HTTPException(status_code=400, detail='Provide a GitHub repository in owner/name format.')

        owner, repo = repository.split('/', 1)
        repo_data = self._get_json(f'/repos/{owner}/{repo}')
        default_branch = branch or repo_data.get('default_branch') or self.settings.github_default_branch
        workflow_runs_payload = self._get_json(f'/repos/{owner}/{repo}/actions/runs', params={'per_page': 10, 'branch': default_branch})
        workflows_payload = self._get_json(f'/repos/{owner}/{repo}/actions/workflows')
        commits_payload = self._get_json(f'/repos/{owner}/{repo}/commits', params={'per_page': 6, 'sha': default_branch})
        pulls_payload = self._get_json(f'/repos/{owner}/{repo}/pulls', params={'state': 'open', 'per_page': 1})

        workflow_file_map = {item.get('id'): item for item in workflows_payload.get('workflows', [])}
        workflow_runs = [self._map_workflow_run(item, workflow_file_map.get(item.get('workflow_id'))) for item in workflow_runs_payload.get('workflow_runs', [])]
        commits = [self._map_commit(item) for item in commits_payload[:5]]
        stages = self._build_stage_metrics(workflow_runs)
        health_score, build_success_rate = self._derive_health(workflow_runs)
        deployments_this_week = sum(1 for run in workflow_runs if 'deploy' in (run.name or '').lower())
        badges = self._build_badges(repository, workflow_runs)

        return GitHubDashboardResponse(
            repository=repository,
            default_branch=default_branch,
            health_score=health_score,
            build_success_rate=build_success_rate,
            deployments_this_week=deployments_this_week,
            open_issues=repo_data.get('open_issues_count', 0),
            stars=repo_data.get('stargazers_count', 0),
            pull_requests_open=len(pulls_payload) if isinstance(pulls_payload, list) else 0,
            pipeline_stages=stages,
            commits=commits,
            workflow_runs=workflow_runs,
            badges=badges,
            integration_status='live',
        )

    def fetch_repository_context(self, repository: str | None, branch: str | None = None) -> list[str]:
        if not repository:
            return []
        repository = repository.strip('/')
        if '/' not in repository:
            return []
        owner, repo = repository.split('/', 1)
        try:
            repo_data = self._get_json(f'/repos/{owner}/{repo}')
            readme = self._get_json(f'/repos/{owner}/{repo}/readme', headers={'Accept': 'application/vnd.github.raw+json'})
            workflows = self._get_json(f'/repos/{owner}/{repo}/actions/workflows')
        except HTTPException:
            return []

        workflow_names = ', '.join(w.get('name', 'unnamed') for w in workflows.get('workflows', [])[:5]) or 'No workflows found'
        default_branch = branch or repo_data.get('default_branch') or 'main'
        readme_text = readme if isinstance(readme, str) else str(readme)
        return [
            f"GitHub repository: {repository}",
            f"Description: {repo_data.get('description') or 'No description provided.'}",
            f"Default branch: {default_branch}",
            f"Stars: {repo_data.get('stargazers_count', 0)} | Open issues: {repo_data.get('open_issues_count', 0)}",
            f"Workflows: {workflow_names}",
            f"README excerpt: {readme_text[:1800]}",
        ]

    def _build_badges(self, repository: str, runs: list[WorkflowRun]) -> list[BadgeItem]:
        badges: list[BadgeItem] = []
        seen: set[str] = set()
        for run in runs:
            workflow_file = run.workflow_file or ''
            if not workflow_file or workflow_file in seen:
                continue
            seen.add(workflow_file)
            encoded_repo = quote(repository, safe='')
            image_url = f'https://github.com/{repository}/actions/workflows/{workflow_file}/badge.svg'
            target_url = f'https://github.com/{repository}/actions/workflows/{workflow_file}'
            badges.append(BadgeItem(label=run.workflow_name or run.name, image_url=image_url, target_url=target_url))
            badges.append(BadgeItem(label='Repo', image_url=f'https://img.shields.io/badge/repo-{encoded_repo}-111827?logo=github', target_url=f'https://github.com/{repository}'))
            break
        return badges[:3]

    def _build_stage_metrics(self, runs: list[WorkflowRun]) -> list[StageMetric]:
        buckets = {'Intake': [], 'Build': [], 'Test': [], 'Deploy': []}
        for run in runs:
            lowered = (run.name or '').lower()
            if 'deploy' in lowered or 'release' in lowered:
                buckets['Deploy'].append(run)
            elif 'test' in lowered:
                buckets['Test'].append(run)
            elif 'build' in lowered or 'ci' in lowered:
                buckets['Build'].append(run)
            else:
                buckets['Intake'].append(run)

        stages: list[StageMetric] = []
        for label in ['Intake', 'Build', 'Test', 'Deploy']:
            related = buckets[label]
            if related:
                latest = related[0]
                status = latest.conclusion if latest.conclusion and latest.conclusion != 'null' else latest.status
                duration = latest.duration_seconds
            else:
                status = 'unknown'
                duration = 0
            stages.append(StageMetric(stage=label, status=status or 'unknown', duration=duration))
        return stages

    def _derive_health(self, runs: list[WorkflowRun]) -> tuple[int, float]:
        completed = [run for run in runs if run.status == 'completed']
        if not completed:
            return 0, 0.0
        successes = sum(1 for run in completed if run.conclusion == 'success')
        rate = round((successes / len(completed)) * 100, 1)
        health = min(100, max(15, int(rate)))
        return health, rate

    def _map_commit(self, item: dict) -> CommitItem:
        commit = item.get('commit', {})
        author = commit.get('author', {})
        sha = item.get('sha', '')[:7]
        timestamp = author.get('date') or datetime.now(UTC).isoformat()
        return CommitItem(
            sha=sha,
            message=(commit.get('message') or '').split('\n', 1)[0],
            author=author.get('name') or item.get('author', {}).get('login') or 'Unknown',
            time=self._humanize_time(timestamp),
            url=item.get('html_url'),
        )

    def _map_workflow_run(self, item: dict, workflow_meta: dict | None) -> WorkflowRun:
        created = item.get('created_at') or datetime.now(UTC).isoformat()
        updated = item.get('updated_at') or created
        duration = self._duration_seconds(created, updated)
        return WorkflowRun(
            name=item.get('name') or item.get('display_title') or 'Workflow',
            branch=item.get('head_branch') or 'unknown',
            status=item.get('status') or 'unknown',
            conclusion=item.get('conclusion') or 'running',
            duration_seconds=duration,
            started_at=created,
            workflow_name=workflow_meta.get('name') if workflow_meta else item.get('name'),
            workflow_file=workflow_meta.get('path', '').split('/')[-1] if workflow_meta else None,
            url=item.get('html_url'),
        )

    def _get_json(self, path: str, params: dict | None = None, headers: dict | None = None):
        request_headers = {
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'ai-devops-enterprise-platform',
        }
        if self.settings.github_token:
            request_headers['Authorization'] = f'Bearer {self.settings.github_token}'
        if headers:
            request_headers.update(headers)

        try:
            with httpx.Client(base_url=self.settings.github_api_base_url, timeout=self.settings.github_request_timeout_seconds) as client:
                response = client.get(path, params=params, headers=request_headers)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f'GitHub API request failed: {exc}') from exc
        if response.status_code >= 400:
            detail = response.json().get('message') if response.headers.get('content-type', '').startswith('application/json') else response.text
            raise HTTPException(status_code=response.status_code, detail=f'GitHub API error: {detail}')
        if 'application/vnd.github.raw+json' in request_headers.get('Accept', ''):
            return response.text
        return response.json()

    @staticmethod
    def _duration_seconds(started_at: str, finished_at: str) -> int:
        try:
            start = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            end = datetime.fromisoformat(finished_at.replace('Z', '+00:00'))
            return max(0, int((end - start).total_seconds()))
        except ValueError:
            return 0

    @staticmethod
    def _humanize_time(timestamp: str) -> str:
        try:
            created = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return timestamp
        delta = datetime.now(UTC) - created.astimezone(UTC)
        minutes = int(delta.total_seconds() / 60)
        if minutes < 60:
            return f'{minutes}m ago'
        hours = minutes // 60
        if hours < 24:
            return f'{hours}h ago'
        days = hours // 24
        return f'{days}d ago'
