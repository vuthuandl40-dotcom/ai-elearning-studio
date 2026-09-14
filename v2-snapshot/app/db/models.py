from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

try:
    from pgvector.sqlalchemy import Vector
except ModuleNotFoundError:  # Allows schema/OpenAPI tooling without the optional Python adapter installed.
    from sqlalchemy.types import UserDefinedType

    class Vector(UserDefinedType):
        cache_ok = True

        def __init__(self, dimensions: int | None = None):
            self.dimensions = dimensions

        def get_col_spec(self, **kw):
            return f"VECTOR({self.dimensions})" if self.dimensions else "VECTOR"

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AppUser(Base, TimestampMixin):
    __tablename__ = "app_users"
    __table_args__ = (CheckConstraint("role IN ('admin','teacher','student')", name="ck_app_user_role"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth_user_id: Mapped[str | None] = mapped_column(Text, unique=True)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(24), default="teacher", nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    projects: Mapped[list[Project]] = relationship(back_populates="user", cascade="all, delete-orphan")
    classroom_memberships: Mapped[list[ClassroomMembership]] = relationship(back_populates="user", cascade="all, delete-orphan")
    organization_memberships: Mapped[list[OrganizationMembership]] = relationship(back_populates="user", cascade="all, delete-orphan", foreign_keys="OrganizationMembership.user_id")


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_organization_slug"),
        CheckConstraint("status IN ('active','suspended','archived')", name="ck_organization_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    memberships: Mapped[list[OrganizationMembership]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    projects: Mapped[list[Project]] = relationship(back_populates="organization")
    classrooms: Mapped[list[Classroom]] = relationship(back_populates="organization")


class OrganizationMembership(Base, TimestampMixin):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_member"),
        CheckConstraint("role IN ('owner','admin','teacher','student')", name="ck_organization_member_role"),
        CheckConstraint("status IN ('active','invited','suspended')", name="ck_organization_member_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(24), default="student", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_users.id", ondelete="SET NULL"))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[AppUser] = relationship(back_populates="organization_memberships", foreign_keys=[user_id])
    inviter: Mapped[AppUser | None] = relationship(foreign_keys=[invited_by])


class RefreshTokenSession(Base):
    __tablename__ = "refresh_token_sessions"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_refresh_token_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmailActionToken(Base):
    __tablename__ = "email_action_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_email_action_token_hash"),
        CheckConstraint("purpose IN ('verify_email','password_reset')", name="ck_email_action_token_purpose"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(12), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(80), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("duration_minutes IS NULL OR duration_minutes > 0", name="ck_project_duration"),
        CheckConstraint("lesson_periods > 0", name="ck_project_periods"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    grade: Mapped[str | None] = mapped_column(Text)
    education_level: Mapped[str | None] = mapped_column(Text)
    book_series: Mapped[str | None] = mapped_column(Text)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    lesson_periods: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="vi", nullable=False)
    visual_style: Mapped[str | None] = mapped_column(Text)
    narration_style: Mapped[str | None] = mapped_column(Text)
    interaction_level: Mapped[str | None] = mapped_column(String(16))
    source_policy: Mapped[str] = mapped_column(String(32), default="strict", nullable=False)
    extra_instructions: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    user: Mapped[AppUser] = relationship(back_populates="projects")
    organization: Mapped[Organization | None] = relationship(back_populates="projects")
    source_files: Mapped[list[SourceFile]] = relationship(back_populates="project", cascade="all, delete-orphan")
    sections: Mapped[list[LessonSection]] = relationship(back_populates="project", cascade="all, delete-orphan", order_by="LessonSection.section_order")
    slides: Mapped[list[Slide]] = relationship(back_populates="project", cascade="all, delete-orphan", order_by="Slide.slide_order")
    analysis_runs: Mapped[list[AnalysisRun]] = relationship(back_populates="project", cascade="all, delete-orphan", order_by="AnalysisRun.created_at")
    planning_runs: Mapped[list[PlanningRun]] = relationship(back_populates="project", cascade="all, delete-orphan", order_by="PlanningRun.created_at")
    generation_runs: Mapped[list[GenerationRun]] = relationship(back_populates="project", cascade="all, delete-orphan", order_by="GenerationRun.created_at")
    export_runs: Mapped[list[ExportRun]] = relationship(back_populates="project", cascade="all, delete-orphan", order_by="ExportRun.created_at")
    lms_profile: Mapped[LmsPublishProfile | None] = relationship(back_populates="project", cascade="all, delete-orphan", uselist=False)
    learner_attempts: Mapped[list[LearnerAttempt]] = relationship(back_populates="project", cascade="all, delete-orphan")
    lrs_connection: Mapped[LrsConnection | None] = relationship(back_populates="project", cascade="all, delete-orphan", uselist=False)
    assignments: Mapped[list[Assignment]] = relationship(back_populates="project", cascade="all, delete-orphan")


class SourceFile(Base, TimestampMixin):
    __tablename__ = "source_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="source_files")
    chunks: Mapped[list[SourceChunk]] = relationship(back_populates="source_file", cascade="all, delete-orphan")


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (UniqueConstraint("source_file_id", "chunk_index", name="uq_source_chunk_index"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_files.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    source_file: Mapped[SourceFile] = relationship(back_populates="chunks")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="processing", nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(32), nullable=False)
    analysis_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    knowledge_map: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    warnings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project: Mapped[Project] = relationship(back_populates="analysis_runs")


class PlanningRun(Base):
    __tablename__ = "planning_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("analysis_runs.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="processing", nullable=False)
    planner_version: Mapped[str] = mapped_column(String(32), nullable=False)
    planning_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    plan_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    warnings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    teacher_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project: Mapped[Project] = relationship(back_populates="planning_runs")


class GenerationRun(Base):
    __tablename__ = "generation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    planning_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("planning_runs.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="processing", nullable=False)
    writer_version: Mapped[str] = mapped_column(String(32), nullable=False)
    generation_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    generation_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    warnings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    slide_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_ref_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    teacher_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project: Mapped[Project] = relationship(back_populates="generation_runs")


class LessonObjective(Base, TimestampMixin):
    __tablename__ = "lesson_objectives"
    __table_args__ = (UniqueConstraint("project_id", "objective_order", name="uq_objective_order"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    objective_order: Mapped[int] = mapped_column(Integer, nullable=False)
    objective_text: Mapped[str] = mapped_column(Text, nullable=False)
    cognitive_level: Mapped[str | None] = mapped_column(String(32))
    objective_type: Mapped[str] = mapped_column(String(32), default="learning", nullable=False)
    source_chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False)
    is_teacher_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ExportRun(Base):
    __tablename__ = "export_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="processing", nullable=False)
    file_name: Mapped[str | None] = mapped_column(Text)
    storage_uri: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    options: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    warnings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="export_runs")


class LmsPublishProfile(Base, TimestampMixin):
    __tablename__ = "lms_publish_profiles"
    __table_args__ = (
        CheckConstraint("passing_score >= 0 AND passing_score <= 100", name="ck_lms_profile_passing_score"),
        CheckConstraint("completion_threshold >= 0 AND completion_threshold <= 1", name="ck_lms_profile_completion_threshold"),
        UniqueConstraint("project_id", name="uq_lms_publish_profile_project"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    default_standard: Mapped[str] = mapped_column(String(24), default="scorm2004", nullable=False)
    passing_score: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    completion_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=1, nullable=False)
    track_interactions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    resume_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    report_session_time: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    project: Mapped[Project] = relationship(back_populates="lms_profile")


class TeacherProfile(Base, TimestampMixin):
    __tablename__ = "teacher_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    reference_image_uri: Mapped[str | None] = mapped_column(Text)
    appearance_description: Mapped[str | None] = mapped_column(Text)
    hair_description: Mapped[str | None] = mapped_column(Text)
    clothing_description: Mapped[str | None] = mapped_column(Text)
    visual_style: Mapped[str | None] = mapped_column(Text)
    age_appearance: Mapped[str | None] = mapped_column(Text)
    negative_rules: Mapped[str | None] = mapped_column(Text)
    voice_profile: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    character_lock: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Classroom(Base, TimestampMixin):
    __tablename__ = "classrooms"
    __table_args__ = (
        UniqueConstraint("join_code", name="uq_classroom_join_code"),
        CheckConstraint("status IN ('active','archived')", name="ck_classroom_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    grade: Mapped[str | None] = mapped_column(Text)
    school_name: Mapped[str | None] = mapped_column(Text)
    academic_year: Mapped[str | None] = mapped_column(String(32))
    join_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    owner: Mapped[AppUser] = relationship(foreign_keys=[owner_id])
    organization: Mapped[Organization | None] = relationship(back_populates="classrooms")
    memberships: Mapped[list[ClassroomMembership]] = relationship(back_populates="classroom", cascade="all, delete-orphan")
    assignments: Mapped[list[Assignment]] = relationship(back_populates="classroom", cascade="all, delete-orphan", order_by="Assignment.created_at")


class ClassroomMembership(Base, TimestampMixin):
    __tablename__ = "classroom_memberships"
    __table_args__ = (
        UniqueConstraint("classroom_id", "user_id", name="uq_classroom_member"),
        CheckConstraint("member_role IN ('teacher','student')", name="ck_classroom_member_role"),
        CheckConstraint("status IN ('active','inactive')", name="ck_classroom_member_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    classroom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    member_role: Mapped[str] = mapped_column(String(24), default="student", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    classroom: Mapped[Classroom] = relationship(back_populates="memberships")
    user: Mapped[AppUser] = relationship(back_populates="classroom_memberships")


class Assignment(Base, TimestampMixin):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint("max_attempts IS NULL OR max_attempts > 0", name="ck_assignment_max_attempts"),
        CheckConstraint("passing_score IS NULL OR (passing_score >= 0 AND passing_score <= 100)", name="ck_assignment_passing_score"),
        CheckConstraint("status IN ('draft','published','closed','archived')", name="ck_assignment_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    classroom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_attempts: Mapped[int | None] = mapped_column(Integer)
    passing_score: Mapped[int | None] = mapped_column(Integer)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    classroom: Mapped[Classroom] = relationship(back_populates="assignments")
    project: Mapped[Project] = relationship(back_populates="assignments")
    assigner: Mapped[AppUser] = relationship(foreign_keys=[assigned_by])
    attempts: Mapped[list[LearnerAttempt]] = relationship(back_populates="assignment")


class LessonSection(Base, TimestampMixin):
    __tablename__ = "lesson_sections"
    __table_args__ = (
        UniqueConstraint("project_id", "section_key", name="uq_section_key"),
        UniqueConstraint("project_id", "section_order", name="uq_section_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    section_key: Mapped[str] = mapped_column(String(64), nullable=False)
    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    teacher_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    project: Mapped[Project] = relationship(back_populates="sections")
    slides: Mapped[list[Slide]] = relationship(back_populates="section", cascade="all, delete-orphan", order_by="Slide.slide_order")


class Slide(Base, TimestampMixin):
    __tablename__ = "slides"
    __table_args__ = (UniqueConstraint("project_id", "slide_order", name="uq_slide_order"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson_sections.id", ondelete="CASCADE"), nullable=False, index=True)
    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("generation_runs.id", ondelete="SET NULL"), index=True)
    slide_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    slide_type: Mapped[str] = mapped_column(String(32), default="content", nullable=False)
    onscreen_text: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    teacher_script: Mapped[str | None] = mapped_column(Text)
    student_instruction: Mapped[str | None] = mapped_column(Text)
    visual_type: Mapped[str | None] = mapped_column(String(32))
    visual_description: Mapped[str | None] = mapped_column(Text)
    image_prompt: Mapped[str | None] = mapped_column(Text)
    video_prompt: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    layout_hint: Mapped[str | None] = mapped_column(Text)
    media: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    design_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    ai_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    teacher_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    project: Mapped[Project] = relationship(back_populates="slides")
    section: Mapped[LessonSection] = relationship(back_populates="slides")
    interactions: Mapped[list[Interaction]] = relationship(back_populates="slide", cascade="all, delete-orphan")


class MediaAsset(Base, TimestampMixin):
    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    slide_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("slides.id", ondelete="SET NULL"), index=True)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ready", nullable=False)
    original_name: Mapped[str | None] = mapped_column(Text)
    storage_uri: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    prompt: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(64))
    provider_asset_id: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

class Interaction(Base, TimestampMixin):
    __tablename__ = "interactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slide_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slides.id", ondelete="CASCADE"), nullable=False, index=True)
    interaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    correct_answer: Mapped[object] = mapped_column(JSONB, nullable=False)
    correct_feedback: Mapped[str | None] = mapped_column(Text)
    incorrect_feedback: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str | None] = mapped_column(String(32))
    points: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=1, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    slide: Mapped[Slide] = relationship(back_populates="interactions")


class SlideSourceRef(Base):
    __tablename__ = "slide_source_refs"
    __table_args__ = (UniqueConstraint("slide_id", "source_chunk_id", "claim_text", name="uq_slide_source_claim"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slide_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("slides.id", ondelete="CASCADE"), nullable=False, index=True)
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_text: Mapped[str | None] = mapped_column(Text)
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AIReview(Base):
    __tablename__ = "ai_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    review_type: Mapped[str] = mapped_column(String(32), default="full", nullable=False)
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    knowledge_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pedagogy_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    interaction_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    multimedia_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    structure_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    findings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LearnerAttempt(Base, TimestampMixin):
    __tablename__ = "learner_attempts"
    __table_args__ = (
        UniqueConstraint("project_id", "external_attempt_id", name="uq_attempt_external_id"),
        CheckConstraint("progress >= 0 AND progress <= 1", name="ck_attempt_progress"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assignments.id", ondelete="SET NULL"), index=True)
    learner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_users.id", ondelete="SET NULL"), index=True)
    learner_key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    learner_name: Mapped[str | None] = mapped_column(Text)
    external_attempt_id: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(24), default="direct", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="in_progress", nullable=False)
    score_raw: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    score_scaled: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    progress: Mapped[Decimal] = mapped_column(Numeric(6, 5), default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    success: Mapped[bool | None] = mapped_column(Boolean)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    session_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="learner_attempts")
    assignment: Mapped[Assignment | None] = relationship(back_populates="attempts")
    learner_user: Mapped[AppUser | None] = relationship(foreign_keys=[learner_user_id])
    events: Mapped[list[LearnerEvent]] = relationship(back_populates="attempt", cascade="all, delete-orphan", order_by="LearnerEvent.event_time")


class LearnerEvent(Base):
    __tablename__ = "learner_events"
    __table_args__ = (UniqueConstraint("attempt_id", "event_id", name="uq_attempt_event_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learner_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_id: Mapped[str | None] = mapped_column(Text)
    verb_iri: Mapped[str | None] = mapped_column(Text)
    slide_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("slides.id", ondelete="SET NULL"), index=True)
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("interactions.id", ondelete="SET NULL"), index=True)
    objective_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False)
    response: Mapped[object | None] = mapped_column(JSONB)
    correct: Mapped[bool | None] = mapped_column(Boolean)
    score_raw: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    score_scaled: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    progress: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    attempt: Mapped[LearnerAttempt] = relationship(back_populates="events")


class LrsConnection(Base, TimestampMixin):
    __tablename__ = "lrs_connections"
    __table_args__ = (UniqueConstraint("project_id", name="uq_lrs_connection_project"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    endpoint: Mapped[str | None] = mapped_column(Text)
    xapi_version: Mapped[str] = mapped_column(String(24), default="1.0.3", nullable=False)
    auth_type: Mapped[str] = mapped_column(String(16), default="none", nullable=False)
    username_env: Mapped[str | None] = mapped_column(Text)
    password_env: Mapped[str | None] = mapped_column(Text)
    token_env: Mapped[str | None] = mapped_column(Text)
    verify_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    project: Mapped[Project] = relationship(back_populates="lrs_connection")


class LrsDelivery(Base):
    __tablename__ = "lrs_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("learner_attempts.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="processing", nullable=False)
    statement_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    response_excerpt: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BackgroundJob(Base, TimestampMixin):
    __tablename__ = "background_jobs"
    __table_args__ = (
        CheckConstraint("kind IN ('analyze','plan','generate','export')", name="ck_background_job_kind"),
        CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name="ck_background_job_status"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_background_job_progress"),
        CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="ck_background_job_attempts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("app_users.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
