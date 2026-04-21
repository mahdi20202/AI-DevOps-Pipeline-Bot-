from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import Base, engine, session_scope
from app.models.pipeline_run import PipelineRun, PipelineStage
from app.models.user import User
from app.services.auth_service import AuthService
from app.web import web_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with session_scope() as session:
        AuthService(session).ensure_admin_user(
            email=settings.demo_username,
            password=settings.demo_password,
            full_name=settings.admin_full_name,
        )
    yield


app = FastAPI(title=settings.app_name, version='3.0.0', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(web_router)
app.include_router(api_router, prefix='/api')
app.mount('/static', StaticFiles(directory='app/static'), name='static')


@app.get('/health')
def health():
    return {'status': 'ok', 'environment': settings.app_env, 'version': '3.0.0'}
