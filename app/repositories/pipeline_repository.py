import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.pipeline_run import PipelineRun, PipelineStage


class PipelineRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(self, *, source_type: str, title: str, input_payload: str) -> PipelineRun:
        run = PipelineRun(source_type=source_type, title=title, input_payload=input_payload)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def add_stage(self, run_id: int, sequence: int, stage_name: str, icon: str, summary: str, details: list[dict]) -> PipelineStage:
        stage = PipelineStage(
            run_id=run_id,
            sequence=sequence,
            stage_name=stage_name,
            icon=icon,
            summary=summary,
            details_json=json.dumps(details),
            status='pending',
            started_at=datetime.now(UTC),
        )
        self.db.add(stage)
        self.db.commit()
        self.db.refresh(stage)
        return stage

    def update_stage(self, stage: PipelineStage, *, status: str, summary: str | None = None, details: list[dict] | None = None) -> PipelineStage:
        stage.status = status
        if summary is not None:
            stage.summary = summary
        if details is not None:
            stage.details_json = json.dumps(details)
        stage.completed_at = datetime.now(UTC)
        self.db.add(stage)
        self.db.commit()
        self.db.refresh(stage)
        return stage

    def update_run(self, run: PipelineRun, *, status: str, progress: int) -> PipelineRun:
        run.overall_status = status
        run.progress_percent = progress
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def list_runs(self) -> list[PipelineRun]:
        return self.db.query(PipelineRun).order_by(PipelineRun.id.desc()).all()

    def get_run(self, run_id: int) -> PipelineRun | None:
        return self.db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
