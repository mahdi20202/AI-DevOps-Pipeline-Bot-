# Platform Architecture

The platform orchestrates four visible stages:
1. Data ingestion from JSON, pasted Jira text, or live Jira API issues.
2. Local RAG retrieval over project docs and repo README context.
3. LLM reasoning with OpenAI or Gemini.
4. Final output for engineering handoff.

Deployment manifests are included for Render, Railway, and Azure App Service.
