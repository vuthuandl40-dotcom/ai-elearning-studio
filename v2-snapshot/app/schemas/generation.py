from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GenerateLessonRequest(BaseModel):
    use_ai: bool = True
    preserve_teacher_edits: bool = True
    fallback_to_local: bool = True


class RegenerateSectionRequest(BaseModel):
    use_ai: bool = True
    force: bool = False
    fallback_to_local: bool = True
    instruction: str | None = Field(default=None, max_length=6000)


class GenerationRunRead(BaseModel):
    id: UUID
    project_id: UUID
    planning_run_id: UUID | None
    status: str
    writer_version: str
    generation_mode: str
    generation_json: dict[str, Any]
    warnings: list[str]
    error_message: str | None
    slide_count: int
    source_ref_count: int
    teacher_approved: bool
    approved_at: datetime | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SlideSourceRefRead(BaseModel):
    id: UUID
    slide_id: UUID
    source_chunk_id: UUID
    claim_text: str | None
    relevance_score: float | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SlideBlueprintDetail(BaseModel):
    slide: dict[str, Any]
    source_refs: list[SlideSourceRefRead]
    interactions: list[dict[str, Any]]
