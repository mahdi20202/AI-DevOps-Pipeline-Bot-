from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_email
from app.core.database import get_db
from app.schemas.jira import JiraIssueResponse
from app.services.jira_service import JiraService

router = APIRouter()


@router.get('/issues/{issue_key}', response_model=JiraIssueResponse)
def get_issue(issue_key: str, db: Session = Depends(get_db), _: str = Depends(get_current_user_email)):
    return JiraService(db).fetch_issue(issue_key)
