from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_email
from app.core.database import get_db
from app.schemas.pipeline import PipelineRunCreateResponse, PipelineRunDetail, PipelineRunListResponse
from app.services.pipeline_service import PipelineService

router = APIRouter()


@router.post('/runs', response_model=PipelineRunCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_run(
    ticket_text: str | None = Form(default=None),
    json_file: UploadFile | None = File(default=None),
    jira_issue_key: str | None = Form(default=None),
    provider: str = Form(default='openai'),
    model_name: str | None = Form(default=None),
    github_repository: str | None = Form(default=None),
    github_branch: str | None = Form(default=None),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email),
):
    if not ticket_text and not json_file and not jira_issue_key:
        raise HTTPException(status_code=400, detail='Provide a Jira issue key, Jira ticket, or upload a JSON file.')
    return PipelineService(db).create_run(
        ticket_text=ticket_text,
        json_file=json_file,
        jira_issue_key=jira_issue_key,
        provider=provider,
        model_name=model_name,
        github_repository=github_repository,
        github_branch=github_branch,
    )


@router.get('/runs', response_model=PipelineRunListResponse)
def list_runs(db: Session = Depends(get_db), _: str = Depends(get_current_user_email)):
    return PipelineService(db).list_runs()


@router.get('/runs/{run_id}', response_model=PipelineRunDetail)
def get_run(run_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user_email)):
    run = PipelineService(db).get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail='Run not found')
    return run
