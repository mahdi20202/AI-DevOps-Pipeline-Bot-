from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_email
from app.core.database import get_db
from app.schemas.github import GitHubDashboardResponse
from app.services.github_service import GitHubService

router = APIRouter()


@router.get('/dashboard', response_model=GitHubDashboardResponse)
def get_dashboard(
    repository: str | None = Query(default=None),
    branch: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user_email),
):
    return GitHubService(db).build_dashboard(repository=repository, branch=branch)
