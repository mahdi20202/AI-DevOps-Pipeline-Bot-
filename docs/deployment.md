# Deployment guide

This project ships with deployment-ready assets for Render, Railway, Azure App Service, and Docker.

## Render

- Commit the repository with `render.yaml` at the root.
- Create a new web service from the repo.
- Set the required environment variables.
- Keep `/health` as the health check path.

## Railway

- Create a service from the repo.
- Railway will read `railway.json` automatically.
- Define secrets in the Railway Variables tab.
- Set a persistent database only if you switch away from SQLite.

## Azure App Service

- Provision a Linux Python App Service.
- Set the startup command to `bash deploy/azure/startup.sh`.
- Add application settings for all required secrets.
- Use the included GitHub Actions template if you want CI/CD based zip deploys.

## Shared production checklist

- Replace SQLite with Postgres in production.
- Set `COOKIE_SECURE=true` behind HTTPS.
- Rotate all API keys and tokens if they are ever exposed.
- Keep `.env` local only.
