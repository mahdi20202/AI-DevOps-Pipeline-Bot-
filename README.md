# AI DevOps Enterprise Platform v3

![CI Pipeline](https://github.com/mahdi20202/AI-DevOps-Pipeline-Bot-/actions/workflows/ci.yml/badge.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-production_ready-009688?logo=fastapi)
![Deploy](https://img.shields.io/badge/deploy-Render%20%7C%20Railway%20%7C%20Azure-7c3aed)

Enterprise-ready showcase app for live Jira issue ingestion, local RAG retrieval, OpenAI or Gemini reasoning, and GitHub workflow telemetry.

## Version 3 upgrades

- Live Jira API integration with issue preview and pipeline launch by issue key
- Production-style authentication with JWT access token, refresh cookie, and account lockout logic
- Real GitHub workflow badges in the UI and README
- Deployment assets for Render, Railway, Azure App Service, and Docker
- Real charts for pipeline progress, workflow durations, deployment readiness, and stage status

## Core workflow

1. Sign in with the production-style login screen.
2. Launch a run from a live Jira issue key, uploaded JSON file, or pasted ticket text.
3. Pull local RAG context from the `docs/` directory.
4. Add live GitHub repository context and workflow telemetry.
5. Generate a delivery plan with OpenAI or Gemini.
6. Review stage-by-stage observability and hosted deployment readiness.

## Local run

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

Demo login:
- admin@example.com
- Admin123!

## Required secrets

Populate `.env` with whichever integrations you want to use:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `GITHUB_TOKEN`
- `JIRA_API_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`

## Deployments

- **Docker**: `Dockerfile`
- **Render**: `render.yaml`
- **Railway**: `railway.json`
- **Azure**: `deploy/azure/startup.sh`
- **Azure GitHub Actions template**: `.github/workflows/azure-appservice-deploy.template.yml`

See `docs/deployment.md` for the deployment checklist.
