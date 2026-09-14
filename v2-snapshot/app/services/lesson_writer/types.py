from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


InteractionType = Literal[
    "single_choice",
    "multiple_choice",
    "true_false",
    "fill_blank",
    "matching",
    "drag_drop",
]
Difficulty = Literal["remember", "understand", "apply", "analyze"]


class ClaimRef(BaseModel):
    source_chunk_id: str
    claim_text: str = ""
    relevance_score: float | None = Field(default=None, ge=0, le=1)


class InteractionBlueprint(BaseModel):
    interaction_type: InteractionType
    question: str
    options: list[str | dict[str, str]] = Field(default_factory=list)
    correct_answer: str | int | bool | list[str] | list[int] | dict[str, str]
    correct_feedback: str = "Chính xác!"
    incorrect_feedback: str = "Chưa chính xác. Em hãy xem lại nội dung vừa học."
    explanation: str = ""
    difficulty: Difficulty = "understand"
    points: float = Field(default=1.0, ge=0)
    settings: dict[str, Any] = Field(default_factory=dict)
    source_chunk_ids: list[str] = Field(default_factory=list)


class SlideBlueprint(BaseModel):
    section_key: str
    title: str
    slide_type: str = "content"
    onscreen_text: list[str] = Field(default_factory=list)
    teacher_script: str = ""
    student_instruction: str = ""
    guiding_question: str = ""
    visual_type: str = "illustration"
    visual_description: str = ""
    image_prompt: str = ""
    video_prompt: str = ""
    duration_seconds: int = Field(default=0, ge=0)
    layout_hint: str = ""
    interaction: InteractionBlueprint | None = None
    source_refs: list[ClaimRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SectionDraft(BaseModel):
    section_key: str
    slides: list[SlideBlueprint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LessonDraft(BaseModel):
    lesson_title: str
    planning_run_id: str
    total_duration_seconds: int = Field(ge=0)
    slides: list[SlideBlueprint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
