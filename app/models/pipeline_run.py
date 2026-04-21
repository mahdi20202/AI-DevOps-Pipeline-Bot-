from datetime import datetime, UTC

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PipelineRun(Base):
    __tablename__ = 'pipeline_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    input_payload: Mapped[str] = mapped_column(Text, nullable=False)
    overall_status: Mapped[str] = mapped_column(String(20), default='queued', nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    stages = relationship('PipelineStage', back_populates='run', cascade='all, delete-orphan', order_by='PipelineStage.sequence')


class PipelineStage(Base):
    __tablename__ = 'pipeline_stages'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey('pipeline_runs.id'), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='pending', nullable=False)
    icon: Mapped[str] = mapped_column(String(40), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default='', nullable=False)
    details_json: Mapped[str] = mapped_column(Text, default='[]', nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    run = relationship('PipelineRun', back_populates='stages')
