from pydantic import BaseModel


class JiraIssueResponse(BaseModel):
    key: str
    summary: str
    status: str
    priority: str | None = None
    assignee: str | None = None
    issue_type: str | None = None
    project: str | None = None
    description: str
    acceptance_criteria: list[str] = []
    url: str | None = None
    integration_status: str = 'live'
