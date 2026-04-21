from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'AI DevOps Enterprise Platform'
    app_env: str = 'development'
    secret_key: str = 'change-me-in-production'
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = 20
    refresh_token_expire_minutes: int = 60 * 24 * 7
    demo_username: str = 'admin@example.com'
    demo_password: str = 'Admin123!'
    admin_full_name: str = 'Platform Administrator'
    database_url: str = 'sqlite:///./ai_devops_enterprise.db'
    cookie_secure: bool = False
    cookie_domain: str | None = None
    allow_user_registration: bool = False
    max_failed_logins: int = 5
    lockout_minutes: int = 15

    github_token: str | None = None
    github_api_base_url: str = 'https://api.github.com'
    github_default_repo: str | None = None
    github_default_branch: str = 'main'

    jira_api_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    jira_default_project: str | None = None

    openai_api_key: str | None = None
    openai_model: str = 'gpt-5-mini'

    gemini_api_key: str | None = None
    gemini_model: str = 'gemini-2.5-flash'

    rag_docs_path: str = 'docs'
    llm_request_timeout_seconds: int = 60
    github_request_timeout_seconds: int = 30
    jira_request_timeout_seconds: int = 30
    allow_provider_fallback_stub: bool = True

    @field_validator('github_default_repo')
    @classmethod
    def normalize_repo(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value.strip().strip('/')

    @field_validator('jira_api_base_url')
    @classmethod
    def normalize_jira_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value.rstrip('/')


@lru_cache
def get_settings() -> Settings:
    return Settings()
