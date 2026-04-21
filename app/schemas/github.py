from pydantic import BaseModel


class StageMetric(BaseModel):
    stage: str
    status: str
    duration: int


class CommitItem(BaseModel):
    sha: str
    message: str
    author: str
    time: str
    url: str | None = None


class WorkflowRun(BaseModel):
    name: str
    branch: str
    status: str
    conclusion: str
    duration_seconds: int
    started_at: str
    workflow_name: str | None = None
    workflow_file: str | None = None
    url: str | None = None


class BadgeItem(BaseModel):
    label: str
    image_url: str
    target_url: str


class GitHubDashboardResponse(BaseModel):
    repository: str
    default_branch: str
    health_score: int
    build_success_rate: float
    deployments_this_week: int
    open_issues: int
    stars: int
    pull_requests_open: int = 0
    pipeline_stages: list[StageMetric]
    commits: list[CommitItem]
    workflow_runs: list[WorkflowRun]
    badges: list[BadgeItem] = []
    integration_status: str
