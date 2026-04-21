from __future__ import annotations

import re
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.jira import JiraIssueResponse


class JiraService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def fetch_issue(self, issue_key: str) -> JiraIssueResponse:
        if not self.settings.jira_api_base_url or not self.settings.jira_email or not self.settings.jira_api_token:
            raise HTTPException(status_code=400, detail='Jira integration is not configured. Set JIRA_API_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN.')
        issue_key = issue_key.strip().upper()
        if '-' not in issue_key:
            issue_key = f"{(self.settings.jira_default_project or '').upper()}-{issue_key}" if self.settings.jira_default_project else issue_key
        data = self._get_json(f'/rest/api/3/issue/{issue_key}', params={'fields': 'summary,description,priority,status,assignee,issuetype,project'})
        fields = data.get('fields', {})
        description = self._flatten_description(fields.get('description'))
        return JiraIssueResponse(
            key=data.get('key', issue_key),
            summary=fields.get('summary') or issue_key,
            status=(fields.get('status') or {}).get('name') or 'Unknown',
            priority=(fields.get('priority') or {}).get('name'),
            assignee=((fields.get('assignee') or {}).get('displayName')),
            issue_type=(fields.get('issuetype') or {}).get('name'),
            project=(fields.get('project') or {}).get('key'),
            description=description,
            acceptance_criteria=self._extract_acceptance_criteria(description),
            url=f"{self.settings.jira_api_base_url}/browse/{data.get('key', issue_key)}",
        )

    def build_requirement_text(self, issue_key: str) -> str:
        issue = self.fetch_issue(issue_key)
        criteria = '\n'.join(f'- {item}' for item in issue.acceptance_criteria) or '- Define implementation checkpoints'
        return (
            f"Jira Issue: {issue.key}\n"
            f"Summary: {issue.summary}\n"
            f"Status: {issue.status}\n"
            f"Priority: {issue.priority or 'Unspecified'}\n"
            f"Assignee: {issue.assignee or 'Unassigned'}\n"
            f"Issue Type: {issue.issue_type or 'Task'}\n"
            f"Description:\n{issue.description}\n\n"
            f"Acceptance Criteria:\n{criteria}"
        )

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        auth = (self.settings.jira_email or '', self.settings.jira_api_token or '')
        headers = {'Accept': 'application/json'}
        try:
            with httpx.Client(base_url=self.settings.jira_api_base_url, timeout=self.settings.jira_request_timeout_seconds) as client:
                response = client.get(path, params=params, headers=headers, auth=auth)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f'Jira API request failed: {exc}') from exc
        if response.status_code >= 400:
            detail = response.text or response.reason_phrase
            raise HTTPException(status_code=response.status_code, detail=f'Jira API error: {detail}')
        return response.json()

    def _flatten_description(self, value: Any) -> str:
        chunks: list[str] = []
        def walk(node: Any):
            if isinstance(node, dict):
                node_type = node.get('type')
                if node_type == 'text' and node.get('text'):
                    chunks.append(node['text'])
                for child in node.get('content', []) or []:
                    walk(child)
            elif isinstance(node, list):
                for item in node:
                    walk(item)
            elif isinstance(node, str):
                chunks.append(node)
        walk(value)
        return ' '.join(part.strip() for part in chunks if part and part.strip()) or 'No description provided.'

    @staticmethod
    def _extract_acceptance_criteria(text: str) -> list[str]:
        matches = re.findall(r'(?:AC\d+|acceptance criteria|criteria)[:\-]?\s*([^\n]+)', text, re.IGNORECASE)
        bullets = re.findall(r'[-•]\s+([^\n]+)', text)
        values = matches + bullets
        deduped: list[str] = []
        for value in values:
            cleaned = value.strip(' .')
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)
        return deduped[:6]
