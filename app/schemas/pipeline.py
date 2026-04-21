from datetime import datetime
from pydantic import BaseModel, Field


class StageDetail(BaseModel):
    label: str
    value: str
    tone: str = 'neutral'


class PipelineStageSchema(BaseModel):
    id: int
    sequence: int
    stage_name: str
    status: str
    icon: str
    summary: str
    details: list[StageDetail]


class PipelineRunSummary(BaseModel):
    id: int
    title: str
    source_type: str
    overall_status: str
    progress_percent: int
    created_at: datetime


class PipelineRunCreateResponse(BaseModel):
    run_id: int
    message: str


class PipelineRunListResponse(BaseModel):
    runs: list[PipelineRunSummary]


class PipelineRunDetail(PipelineRunSummary):
    stages: list[PipelineStageSchema]


class PipelineLaunchRequest(BaseModel):
    provider: str = Field(default='openai')
    model_name: str | None = None
    github_repository: str | None = None
    github_branch: str | None = None
    jira_issue_key: str | None = None
