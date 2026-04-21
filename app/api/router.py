from fastapi import APIRouter

from app.api.routes import auth, github, jira, pipeline

api_router = APIRouter()
api_router.include_router(auth.router, prefix='/auth', tags=['auth'])
api_router.include_router(pipeline.router, prefix='/pipeline', tags=['pipeline'])
api_router.include_router(github.router, prefix='/github', tags=['github'])
api_router.include_router(jira.router, prefix='/jira', tags=['jira'])
