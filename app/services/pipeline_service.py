from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.repositories.pipeline_repository import PipelineRepository
from app.schemas.pipeline import (
    PipelineRunCreateResponse,
    PipelineRunDetail,
    PipelineRunListResponse,
    PipelineRunSummary,
    PipelineStageSchema,
)
from app.services.github_service import GitHubService
from app.services.jira_service import JiraService
from app.services.llm_service import LLMService
from app.services.rag_service import LocalRAGService


class PipelineService:
    STAGES = [
        ('Data Ingestion', 'database-zap'),
        ('RAG Retrieval', 'search-check'),
        ('LLM Reasoning', 'brain-circuit'),
        ('Final Output', 'rocket'),
    ]

    def __init__(self, db: Session):
        self.db = db
        self.repo = PipelineRepository(db)
        self.rag = LocalRAGService()
        self.llm = LLMService(db)
        self.github = GitHubService(db)
        self.jira = JiraService(db)

    def create_run(
        self,
        *,
        ticket_text: str | None,
        json_file: UploadFile | None,
        provider: str,
        model_name: str | None,
        github_repository: str | None,
        github_branch: str | None,
        jira_issue_key: str | None = None,
    ) -> PipelineRunCreateResponse:
        source_type, title, raw_requirement, payload_preview = self._resolve_requirement(ticket_text, json_file, jira_issue_key)
        run = self.repo.create_run(source_type=source_type, title=title, input_payload=payload_preview)
        stage_models = [self.repo.add_stage(run.id, idx, name, icon, 'Queued', []) for idx, (name, icon) in enumerate(self.STAGES, start=1)]

        stage1_details = self._ingest_requirement(raw_requirement, github_repository, jira_issue_key)
        self.repo.update_stage(stage_models[0], status='success', summary='Requirement normalized and structured for downstream processing.', details=stage1_details)
        self.repo.update_run(run, status='running', progress=25)

        retrieved_chunks = self.rag.retrieve(raw_requirement, limit=4)
        repo_context = self.github.fetch_repository_context(github_repository, github_branch) if github_repository else []
        stage2_details = [
            {'label': 'Primary evidence', 'value': retrieved_chunks[0].source if retrieved_chunks else 'No local docs matched', 'tone': 'info'},
            {'label': 'Repository context', 'value': github_repository or 'Not linked', 'tone': 'success' if github_repository else 'warning'},
            {'label': 'Retrieved chunks', 'value': str(len(retrieved_chunks)), 'tone': 'neutral'},
            {'label': 'Repo context slices', 'value': str(len(repo_context)), 'tone': 'neutral'},
        ]
        self.repo.update_stage(stage_models[1], status='success', summary='Hybrid local retrieval and live repo telemetry assembled.', details=stage2_details)
        self.repo.update_run(run, status='running', progress=55)

        llm_result = self.llm.generate_delivery_plan(
            requirement_text=raw_requirement,
            retrieved_chunks=retrieved_chunks,
            repo_context=repo_context,
            provider=provider,
            model_name=model_name,
        )
        plan = llm_result.get('plan', [])
        risks = llm_result.get('risks', [])
        self.repo.update_stage(stage_models[2], status='success', summary=llm_result.get('summary') or 'Implementation plan and risks generated.', details=[
            {'label': 'Provider', 'value': provider, 'tone': 'info'},
            {'label': 'Model', 'value': llm_result.get('model_name') or 'Configured default', 'tone': 'success'},
            {'label': 'Plan items', 'value': str(len(plan)), 'tone': 'success'},
            {'label': 'Risk items', 'value': str(len(risks)), 'tone': 'warning' if risks else 'success'},
        ])
        self.repo.update_run(run, status='running', progress=80)

        acceptance = llm_result.get('acceptance_criteria', [])
        final_summary = llm_result.get('final_output') or 'Release package ready for engineering handoff.'
        self.repo.update_stage(stage_models[3], status='success', summary=final_summary, details=[
            {'label': 'Acceptance criteria', 'value': str(len(acceptance)), 'tone': 'success'},
            {'label': 'Top action', 'value': plan[0] if plan else 'Review generated plan', 'tone': 'info'},
            {'label': 'Top risk', 'value': risks[0] if risks else 'No blocking risk detected', 'tone': 'warning' if risks else 'success'},
        ])
        self.repo.update_run(run, status='completed', progress=100)
        return PipelineRunCreateResponse(run_id=run.id, message='Pipeline run created successfully.')

    def list_runs(self) -> PipelineRunListResponse:
        runs = [self._to_summary(run) for run in self.repo.list_runs()]
        return PipelineRunListResponse(runs=runs)

    def get_run(self, run_id: int) -> PipelineRunDetail | None:
        run = self.repo.get_run(run_id)
        if not run:
            return None
        return PipelineRunDetail(
            **self._to_summary(run).model_dump(),
            stages=[
                PipelineStageSchema(
                    id=stage.id,
                    sequence=stage.sequence,
                    stage_name=stage.stage_name,
                    status=stage.status,
                    icon=stage.icon,
                    summary=stage.summary,
                    details=json.loads(stage.details_json or '[]'),
                )
                for stage in run.stages
            ],
        )

    def _resolve_requirement(self, ticket_text: str | None, json_file: UploadFile | None, jira_issue_key: str | None) -> tuple[str, str, str, str]:
        if jira_issue_key:
            text = self.jira.build_requirement_text(jira_issue_key)
            return 'jira_live', f'Live Jira issue {jira_issue_key.upper()}', text, text[:4000]
        if ticket_text:
            cleaned = ticket_text.strip()
            title = cleaned.splitlines()[0][:120]
            return 'jira_text', title, cleaned, cleaned[:4000]
        if json_file:
            try:
                body = json_file.file.read().decode('utf-8')
                data = json.loads(body)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f'Invalid JSON file: {exc}') from exc
            title = data.get('title') or data.get('name') or json_file.filename or 'JSON requirement'
            normalized = json.dumps(data, indent=2)
            return 'json_upload', title, normalized, normalized[:4000]
        raise HTTPException(status_code=400, detail='Provide a Jira issue key, Jira ticket text, or upload a JSON file.')

    @staticmethod
    def _ingest_requirement(raw_requirement: str, github_repository: str | None, jira_issue_key: str | None) -> list[dict[str, Any]]:
        return [
            {'label': 'Characters', 'value': str(len(raw_requirement)), 'tone': 'info'},
            {'label': 'Input type', 'value': 'Live Jira' if jira_issue_key else ('Jira text' if raw_requirement.startswith('JIRA') or raw_requirement.startswith('Jira Issue') else 'JSON upload'), 'tone': 'success'},
            {'label': 'Repo linked', 'value': github_repository or 'None', 'tone': 'success' if github_repository else 'warning'},
            {'label': 'Structured sections', 'value': str(max(1, raw_requirement.count('\n\n') + 1)), 'tone': 'neutral'},
        ]

    @staticmethod
    def _to_summary(run) -> PipelineRunSummary:
        return PipelineRunSummary(
            id=run.id,
            title=run.title,
            source_type=run.source_type,
            overall_status=run.overall_status,
            progress_percent=run.progress_percent,
            created_at=run.created_at,
        )
