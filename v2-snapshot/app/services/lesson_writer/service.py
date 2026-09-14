from __future__ import annotations

from datetime import datetime, timezone
import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.db.models import (
    GenerationRun,
    Interaction,
    LessonObjective,
    LessonSection,
    PlanningRun,
    Project,
    Slide,
    SlideSourceRef,
    SourceChunk,
    TeacherProfile,
)
from app.db.seed_sections import DEFAULT_SECTIONS
from app.services.lesson_writer.local_writer import build_local_section_draft
from app.services.lesson_writer.openai_client import OpenAILessonWriter
from app.services.lesson_writer.types import ClaimRef, InteractionBlueprint, LessonDraft, SectionDraft, SlideBlueprint
from app.services.lesson_writer.validator import DraftValidationError, validate_and_repair_draft, validate_and_repair_section

WRITER_VERSION = "step5.1"
CANONICAL_KEYS = [key for _, key, _, _ in DEFAULT_SECTIONS]


class GenerationError(RuntimeError):
    pass


def _approved_plan(db: Session, project_id: UUID) -> PlanningRun | None:
    return db.scalar(
        select(PlanningRun)
        .where(
            PlanningRun.project_id == project_id,
            PlanningRun.status == "completed",
            PlanningRun.teacher_approved.is_(True),
        )
        .order_by(PlanningRun.approved_at.desc(), PlanningRun.created_at.desc())
        .limit(1)
    )


def _default_teacher_profile(db: Session, project: Project) -> TeacherProfile | None:
    return db.scalar(
        select(TeacherProfile)
        .where(TeacherProfile.user_id == project.user_id, TeacherProfile.is_default.is_(True))
        .order_by(TeacherProfile.updated_at.desc())
        .limit(1)
    )


def _objectives(db: Session, project_id: UUID) -> list[LessonObjective]:
    return list(db.scalars(
        select(LessonObjective).where(LessonObjective.project_id == project_id).order_by(LessonObjective.objective_order)
    ))


def _chunks(db: Session, project_id: UUID) -> list[SourceChunk]:
    return list(db.scalars(
        select(SourceChunk)
        .options(joinedload(SourceChunk.source_file))
        .where(SourceChunk.project_id == project_id)
        .order_by(SourceChunk.source_file_id, SourceChunk.chunk_index)
    ).unique())


def _interaction_to_blueprint(row: Interaction | None) -> InteractionBlueprint | None:
    if not row:
        return None
    ids = [str(x) for x in (row.settings or {}).get("source_chunk_ids", [])]
    return InteractionBlueprint(
        interaction_type=row.interaction_type,
        question=row.question,
        options=row.options or [],
        correct_answer=row.correct_answer,
        correct_feedback=row.correct_feedback or "Chính xác!",
        incorrect_feedback=row.incorrect_feedback or "Chưa chính xác.",
        explanation=row.explanation or "",
        difficulty=row.difficulty or "understand",
        points=float(row.points or 1),
        settings={k: v for k, v in (row.settings or {}).items() if k != "source_chunk_ids"},
        source_chunk_ids=ids,
    )


def _existing_section_blueprints(db: Session, section: LessonSection) -> list[SlideBlueprint]:
    slides = list(db.scalars(
        select(Slide)
        .where(Slide.section_id == section.id, Slide.teacher_approved.is_(True))
        .order_by(Slide.slide_order)
    ))
    output: list[SlideBlueprint] = []
    for slide in slides:
        refs = list(db.scalars(select(SlideSourceRef).where(SlideSourceRef.slide_id == slide.id)))
        interaction = db.scalar(select(Interaction).where(Interaction.slide_id == slide.id).order_by(Interaction.created_at).limit(1))
        output.append(SlideBlueprint(
            section_key=section.section_key,
            title=slide.title or section.title,
            slide_type=slide.slide_type,
            onscreen_text=[str(x) for x in (slide.onscreen_text or [])],
            teacher_script=slide.teacher_script or "",
            student_instruction=slide.student_instruction or "",
            guiding_question=(slide.ai_metadata or {}).get("guiding_question", ""),
            visual_type=slide.visual_type or "educational_illustration",
            visual_description=slide.visual_description or "",
            image_prompt=slide.image_prompt or "",
            video_prompt=slide.video_prompt or "",
            duration_seconds=slide.duration_seconds or 0,
            layout_hint=slide.layout_hint or "",
            interaction=_interaction_to_blueprint(interaction),
            source_refs=[ClaimRef(
                source_chunk_id=str(ref.source_chunk_id),
                claim_text=ref.claim_text or "",
                relevance_score=float(ref.relevance_score) if ref.relevance_score is not None else None,
            ) for ref in refs],
            metadata={"locked": True, "existing_slide_id": str(slide.id)},
        ))
    return output


def _section_chunks(section_plan: dict, chunks_by_id: dict[str, SourceChunk]) -> list[SourceChunk]:
    return [chunks_by_id[x] for x in section_plan.get("source_chunk_ids", []) if x in chunks_by_id]


_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?|[^\W\d_]+", re.UNICODE)
_STOPWORDS = {
    "và", "của", "có", "là", "cho", "với", "các", "một", "những", "được", "về", "trong", "theo",
    "phần", "này", "slide", "nội", "dung", "bài", "học", "sinh", "giáo", "viên", "địa", "lí", "lý",
    "tạo", "lại", "toàn", "bộ", "ngắn", "gọn", "làm", "rõ", "dễ", "hiểu", "không", "nguồn",
}


def _tokens(text: str) -> set[str]:
    return {x.lower() for x in _TOKEN_RE.findall(text or "") if len(x) > 1 and x.lower() not in _STOPWORDS}


def _chunk_score(chunk: SourceChunk, query: str) -> int:
    q = _tokens(query)
    if not q:
        return 0
    heading_tokens = _tokens(chunk.heading or "")
    content_tokens = _tokens(chunk.content or "")
    overlap = q & content_tokens
    heading_overlap = q & heading_tokens
    numeric = {x for x in q if any(ch.isdigit() for ch in x)}
    numeric_overlap = numeric & content_tokens
    return len(overlap) + 2 * len(heading_overlap) + 4 * len(numeric_overlap)


def _rank_chunks(chunks: list[SourceChunk], query: str, limit: int = 4) -> list[SourceChunk]:
    ranked = sorted(((_chunk_score(chunk, query), chunk) for chunk in chunks), key=lambda item: item[0], reverse=True)
    positive = [chunk for score, chunk in ranked if score >= 2]
    return positive[:limit]


def _first_source_sentence(text: str, limit: int = 170) -> str:
    compact = " ".join((text or "").split())
    if not compact:
        return ""
    sentence = re.split(r"(?<=[.!?…])\s+", compact, maxsplit=1)[0]
    if len(sentence) <= limit:
        return sentence
    cut = sentence[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return cut + "…"


def _looks_administrative(text: str) -> bool:
    value = (text or "").strip().lower()
    bad = (
        "chương ", "tên bài dạy", "môn học:", "thiết bị dạy học", "tiến trình dạy học",
        "bảng tiêu chí", "rubric", "phát triển năng lực số", "mục tiêu", "i. mục tiêu", "ii. thiết bị",
    )
    return any(value.startswith(x) for x in bad)


def _instruction_specs(instruction: str) -> list[dict[str, object]]:
    lines = [line.strip() for line in (instruction or "").splitlines() if line.strip()]
    specs: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in lines:
        match = re.match(r"(?i)^slide\s+(\d+)\b(.*)$", line)
        if match:
            rest = match.group(2).strip(" :-")
            quoted = re.search(r"[“\"]([^”\"]+)[”\"]", rest)
            if quoted:
                title = quoted.group(1).strip()
            else:
                title = re.split(r"\.|Nội dung|Làm rõ", rest, maxsplit=1, flags=re.I)[0].strip(" :.-")
            current = {"order": int(match.group(1)), "title": title or f"Slide {match.group(1)}", "bullets": []}
            specs.append(current)
            continue
        if current is not None and re.match(r"^[-•+]\s+", line):
            bullet = re.sub(r"^[-•+]\s+", "", line).strip()
            if bullet:
                current["bullets"].append(bullet)
    return sorted(specs, key=lambda row: int(row["order"]))


def _instruction_local_section(
    project: Project,
    section_plan: dict,
    chunks: list[SourceChunk],
    instruction: str,
) -> tuple[SectionDraft | None, list[str]]:
    specs = _instruction_specs(instruction)
    if not specs:
        return None, []
    if section_plan.get("section_key") in {"interaction_1", "interaction_2", "interaction_3", "practice"}:
        return None, []

    warnings: list[str] = []
    total_duration = int(section_plan.get("planned_duration_seconds") or 0)
    count = len(specs)
    base, remainder = divmod(max(0, total_duration), max(1, count))
    durations = [base + (1 if i < remainder else 0) for i in range(count)]
    slides: list[SlideBlueprint] = []

    for idx, spec in enumerate(specs):
        title = str(spec["title"])
        requested = [str(x) for x in spec.get("bullets", [])]
        query = " ".join([title, *requested])
        matched = _rank_chunks(chunks, query, 5)
        if project.source_policy == "strict" and not matched:
            raise GenerationError(f"Không tìm thấy đoạn nguồn phù hợp để tạo lại slide ‘{title}’ theo chế độ Source: strict.")

        source_bullets: list[str] = []
        refs: list[ClaimRef] = []
        for chunk in matched:
            sentence = _first_source_sentence(chunk.content)
            if not sentence or _looks_administrative(sentence) or sentence in source_bullets:
                continue
            source_bullets.append(sentence)
            refs.append(ClaimRef(source_chunk_id=str(chunk.id), claim_text=sentence))
            if len(source_bullets) >= 4:
                break

        if not source_bullets:
            if project.source_policy == "strict":
                raise GenerationError(f"Nguồn phù hợp với ‘{title}’ chỉ chứa tiêu đề/hành chính; chưa đủ dữ liệu để tái sinh an toàn.")
            source_bullets = requested[:4] or ["Nội dung được tạo theo yêu cầu của giáo viên."]
            warnings.append(f"{title}: không có source chunk đủ rõ; dùng yêu cầu giáo viên làm nội dung local.")

        visual_type = "map" if any(x in query.lower() for x in ("bản đồ", "vị trí", "phạm vi", "lãnh thổ")) else "educational_illustration"
        facts = "; ".join(source_bullets[:3])
        guiding = f"Từ học liệu, em rút ra nhận xét gì về {title.lower()}?"
        script = f"Các em hãy quan sát học liệu về {title.lower()}. " + " ".join(source_bullets[:3]) + f" Sau đó, {guiding.lower()}"
        slides.append(SlideBlueprint(
            section_key=str(section_plan["section_key"]),
            title=title,
            slide_type="explore" if str(section_plan["section_key"]).startswith("explore_") else "content",
            onscreen_text=source_bullets[:4],
            teacher_script=script,
            student_instruction="Quan sát học liệu, xác định thông tin chính và trao đổi câu trả lời.",
            guiding_question=guiding,
            visual_type=visual_type,
            visual_description=f"{visual_type}: minh họa trực quan cho ‘{title}’, ưu tiên một ý chính, dễ quan sát ở cấp {project.grade or ''}.",
            image_prompt=(f"Create a {project.visual_style or 'clean modern educational'} 16:9 educational visual for '{title}'. "
                          f"Ground the visual only in these source-backed ideas: {facts}. No invented labels, statistics or watermark."),
            video_prompt=(f"Create a short 16:9 educational scene for '{title}'. Use only these source-backed ideas: {facts}. "
                          "Slow clear camera movement, no invented factual labels."),
            duration_seconds=durations[idx],
            layout_hint="visual-left/text-right",
            source_refs=refs,
            metadata={"local_instruction_regeneration": True, "teacher_instruction": instruction[:2000]},
        ))
    return SectionDraft(section_key=str(section_plan["section_key"]), slides=slides, warnings=warnings), warnings


def _build_section(
    *,
    project: Project,
    section_plan: dict,
    objectives: list[LessonObjective],
    chunks_by_id: dict[str, SourceChunk],
    teacher_profile: TeacherProfile | None,
    use_ai: bool,
    fallback_to_local: bool,
    writer: OpenAILessonWriter | None,
) -> SectionDraft:
    rows = _section_chunks(section_plan, chunks_by_id)
    if use_ai and writer is not None:
        try:
            return writer.build_section(
                project=project,
                section_plan=section_plan,
                objectives=objectives,
                chunks=rows,
                teacher_profile=teacher_profile,
            )
        except Exception as exc:
            if not fallback_to_local:
                raise
            local = build_local_section_draft(project, section_plan, chunks_by_id, objectives, teacher_profile)
            local.warnings.append(f"AI Writer lỗi ở {section_plan['section_key']}; đã fallback local: {exc}")
            return local
    return build_local_section_draft(project, section_plan, chunks_by_id, objectives, teacher_profile)


def _persist_draft(
    db: Session,
    *,
    project: Project,
    run: GenerationRun,
    draft: LessonDraft,
    preserve_teacher_edits: bool,
) -> tuple[int, int]:
    sections = list(db.scalars(
        select(LessonSection).where(LessonSection.project_id == project.id).order_by(LessonSection.section_order)
    ))
    section_map = {x.section_key: x for x in sections}

    existing = list(db.scalars(select(Slide).where(Slide.project_id == project.id).order_by(Slide.slide_order)))
    locked_ids = {str(x.id) for x in existing if preserve_teacher_edits and x.teacher_approved}

    for idx, slide in enumerate(existing, start=1):
        if str(slide.id) in locked_ids:
            slide.slide_order = 100000 + idx
    db.flush()

    if preserve_teacher_edits:
        db.execute(delete(Slide).where(Slide.project_id == project.id, Slide.teacher_approved.is_(False)))
    else:
        db.execute(delete(Slide).where(Slide.project_id == project.id))
    db.flush()

    slide_count = 0
    ref_count = 0
    global_order = 0
    for blueprint in draft.slides:
        global_order += 1
        section = section_map[blueprint.section_key]
        existing_id = blueprint.metadata.get("existing_slide_id") if blueprint.metadata else None
        if existing_id and existing_id in locked_ids:
            slide = db.get(Slide, UUID(existing_id))
            if not slide:
                raise GenerationError(f"Approved slide disappeared during persistence: {existing_id}")
            slide.slide_order = global_order
            slide_count += 1
            ref_count += len(blueprint.source_refs)
            continue

        slide = Slide(
            project_id=project.id,
            section_id=section.id,
            generation_run_id=run.id,
            slide_order=global_order,
            title=blueprint.title,
            slide_type=blueprint.slide_type,
            onscreen_text=blueprint.onscreen_text,
            teacher_script=blueprint.teacher_script,
            student_instruction=blueprint.student_instruction,
            visual_type=blueprint.visual_type,
            visual_description=blueprint.visual_description,
            image_prompt=blueprint.image_prompt,
            video_prompt=blueprint.video_prompt,
            duration_seconds=blueprint.duration_seconds,
            layout_hint=blueprint.layout_hint,
            media=[],
            ai_metadata={
                **(blueprint.metadata or {}),
                "guiding_question": blueprint.guiding_question,
                "writer_version": WRITER_VERSION,
                "generation_run_id": str(run.id),
            },
            teacher_approved=False,
            version=1,
        )
        db.add(slide)
        db.flush()
        slide_count += 1

        for ref in blueprint.source_refs:
            db.add(SlideSourceRef(
                slide_id=slide.id,
                source_chunk_id=UUID(ref.source_chunk_id),
                claim_text=ref.claim_text,
                relevance_score=Decimal(str(ref.relevance_score)) if ref.relevance_score is not None else None,
            ))
            ref_count += 1

        if blueprint.interaction:
            interaction = blueprint.interaction
            settings = dict(interaction.settings or {})
            settings["source_chunk_ids"] = interaction.source_chunk_ids
            settings["objective_numbers"] = ((section.metadata_json or {}).get("ai_plan") or {}).get("objective_numbers", [])
            db.add(Interaction(
                slide_id=slide.id,
                interaction_type=interaction.interaction_type,
                question=interaction.question,
                options=interaction.options,
                correct_answer=interaction.correct_answer,
                correct_feedback=interaction.correct_feedback,
                incorrect_feedback=interaction.incorrect_feedback,
                explanation=interaction.explanation,
                difficulty=interaction.difficulty,
                points=Decimal(str(interaction.points)),
                settings=settings,
            ))

    return slide_count, ref_count


def generate_lesson(
    db: Session,
    project_id: UUID,
    *,
    use_ai: bool = True,
    preserve_teacher_edits: bool = True,
    fallback_to_local: bool = True,
) -> GenerationRun:
    settings = get_settings()
    project = db.get(Project, project_id)
    if not project:
        raise GenerationError("Project not found")
    plan_run = _approved_plan(db, project_id)
    if not plan_run:
        raise GenerationError("No teacher-approved Pedagogy Plan. Approve Step 4 before generating slides.")
    plan = plan_run.plan_json or {}
    if len(plan.get("sections", [])) != 15:
        raise GenerationError("Approved plan is invalid: expected 15 canonical sections.")

    objectives = _objectives(db, project_id)
    chunks = _chunks(db, project_id)
    chunks_by_id = {str(x.id): x for x in chunks}
    valid_chunk_ids = set(chunks_by_id)
    if project.source_policy == "strict" and not chunks:
        raise GenerationError("Strict source policy requires source chunks before slide generation.")

    teacher_profile = _default_teacher_profile(db, project)
    ai_enabled = bool(use_ai and settings.openai_api_key)
    writer = OpenAILessonWriter() if ai_enabled else None
    run = GenerationRun(
        project_id=project.id,
        planning_run_id=plan_run.id,
        status="processing",
        writer_version=WRITER_VERSION,
        generation_mode="ai" if ai_enabled else "local",
        generation_json={},
        warnings=[],
    )
    db.add(run)
    project.status = "generating"
    db.commit()
    db.refresh(run)

    try:
        section_rows = list(db.scalars(
            select(LessonSection).where(LessonSection.project_id == project.id).order_by(LessonSection.section_order)
        ))
        section_row_map = {x.section_key: x for x in section_rows}
        slide_blueprints: list[SlideBlueprint] = []
        warnings: list[str] = []

        for section_plan in sorted(plan["sections"], key=lambda x: x["section_order"]):
            key = section_plan["section_key"]
            row = section_row_map.get(key)
            if not row:
                raise GenerationError(f"Missing canonical section row: {key}")
            existing_locked = _existing_section_blueprints(db, row) if preserve_teacher_edits else []
            if existing_locked:
                warnings.append(f"{key}: giữ nguyên {len(existing_locked)} slide đã được giáo viên duyệt; không tái sinh section này.")
                slide_blueprints.extend(existing_locked)
                continue
            draft = _build_section(
                project=project,
                section_plan=section_plan,
                objectives=objectives,
                chunks_by_id=chunks_by_id,
                teacher_profile=teacher_profile,
                use_ai=ai_enabled,
                fallback_to_local=fallback_to_local,
                writer=writer,
            )
            warnings.extend(draft.warnings)
            slide_blueprints.extend(draft.slides)

        lesson_draft = LessonDraft(
            lesson_title=project.title,
            planning_run_id=str(plan_run.id),
            total_duration_seconds=int(plan.get("total_duration_seconds") or (project.duration_minutes or 45) * 60),
            slides=slide_blueprints,
            warnings=warnings,
        )
        lesson_draft = validate_and_repair_draft(
            lesson_draft,
            plan=plan,
            valid_chunk_ids=valid_chunk_ids,
            source_policy=project.source_policy,
        )
        slide_count, ref_count = _persist_draft(
            db,
            project=project,
            run=run,
            draft=lesson_draft,
            preserve_teacher_edits=preserve_teacher_edits,
        )

        if use_ai and not settings.openai_api_key:
            lesson_draft.warnings.append("OPENAI_API_KEY chưa cấu hình; Lesson Writer tự chuyển sang local deterministic.")
        run.status = "completed"
        run.generation_json = lesson_draft.model_dump(mode="json")
        run.warnings = list(dict.fromkeys(lesson_draft.warnings))
        run.slide_count = slide_count
        run.source_ref_count = ref_count
        run.completed_at = datetime.now(timezone.utc)
        project.status = "editing"
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        run_id = run.id
        db.rollback()
        failed_run = db.get(GenerationRun, run_id)
        current_project = db.get(Project, project_id)
        if failed_run:
            failed_run.status = "failed"
            failed_run.error_message = str(exc)
            failed_run.completed_at = datetime.now(timezone.utc)
        if current_project:
            current_project.status = "planned"
        db.commit()
        if isinstance(exc, GenerationError):
            raise
        if isinstance(exc, DraftValidationError):
            raise GenerationError(str(exc)) from exc
        raise GenerationError(str(exc)) from exc


def _full_draft_from_existing(db: Session, project: Project, plan_run: PlanningRun) -> LessonDraft:
    sections = list(db.scalars(
        select(LessonSection).where(LessonSection.project_id == project.id).order_by(LessonSection.section_order)
    ))
    slides_out: list[SlideBlueprint] = []
    for section in sections:
        rows = list(db.scalars(select(Slide).where(Slide.section_id == section.id).order_by(Slide.slide_order)))
        for slide in rows:
            refs = list(db.scalars(select(SlideSourceRef).where(SlideSourceRef.slide_id == slide.id)))
            interaction = db.scalar(select(Interaction).where(Interaction.slide_id == slide.id).order_by(Interaction.created_at).limit(1))
            slides_out.append(SlideBlueprint(
                section_key=section.section_key,
                title=slide.title or section.title,
                slide_type=slide.slide_type,
                onscreen_text=[str(x) for x in (slide.onscreen_text or [])],
                teacher_script=slide.teacher_script or "",
                student_instruction=slide.student_instruction or "",
                guiding_question=(slide.ai_metadata or {}).get("guiding_question", ""),
                visual_type=slide.visual_type or "educational_illustration",
                visual_description=slide.visual_description or "",
                image_prompt=slide.image_prompt or "",
                video_prompt=slide.video_prompt or "",
                duration_seconds=slide.duration_seconds or 0,
                layout_hint=slide.layout_hint or "",
                interaction=_interaction_to_blueprint(interaction),
                source_refs=[ClaimRef(source_chunk_id=str(r.source_chunk_id), claim_text=r.claim_text or "", relevance_score=float(r.relevance_score) if r.relevance_score is not None else None) for r in refs],
                metadata={"existing_slide_id": str(slide.id), "locked": slide.teacher_approved},
            ))
    return LessonDraft(
        lesson_title=project.title,
        planning_run_id=str(plan_run.id),
        total_duration_seconds=int((plan_run.plan_json or {}).get("total_duration_seconds") or 0),
        slides=slides_out,
    )


def regenerate_section(
    db: Session,
    project_id: UUID,
    section_key: str,
    *,
    use_ai: bool = True,
    force: bool = False,
    fallback_to_local: bool = True,
    instruction: str | None = None,
) -> GenerationRun:
    settings = get_settings()
    project = db.get(Project, project_id)
    if not project:
        raise GenerationError("Project not found")
    plan_run = _approved_plan(db, project_id)
    if not plan_run:
        raise GenerationError("No teacher-approved Pedagogy Plan")
    plan = plan_run.plan_json or {}
    section_plan = next((x for x in plan.get("sections", []) if x.get("section_key") == section_key), None)
    if not section_plan:
        raise GenerationError("Section is not part of the approved plan")
    instruction = (instruction or "").strip()
    effective_section_plan = dict(section_plan)
    section = db.scalar(select(LessonSection).where(LessonSection.project_id == project_id, LessonSection.section_key == section_key))
    if not section:
        raise GenerationError("Section not found")
    all_section_rows = list(db.scalars(select(LessonSection).where(LessonSection.project_id == project_id)))
    section_ids_with_slides = set(db.scalars(select(Slide.section_id).where(Slide.project_id == project_id)))
    missing_other_sections = [x.section_key for x in all_section_rows if x.id != section.id and x.id not in section_ids_with_slides]
    if missing_other_sections:
        raise GenerationError("Run full /generate first before regenerating one section; missing slides in: " + ", ".join(sorted(missing_other_sections)))

    approved_slides = list(db.scalars(select(Slide).where(Slide.section_id == section.id, Slide.teacher_approved.is_(True))))
    if approved_slides and not force:
        raise GenerationError("Section contains teacher-approved slides. Set force=true to regenerate intentionally.")

    objectives = _objectives(db, project_id)
    chunks = _chunks(db, project_id)
    chunks_by_id = {str(x.id): x for x in chunks}

    if instruction:
        specs = _instruction_specs(instruction)
        query = instruction + " " + " ".join(str(x.get("title") or "") for x in specs)
        matched = _rank_chunks(chunks, query, max(8, len(specs) * 4 if specs else 8))
        if project.source_policy == "strict" and not matched:
            raise GenerationError("Không tìm thấy nguồn phù hợp với yêu cầu tạo lại section trong chế độ Source: strict.")
        if matched:
            effective_section_plan["source_chunk_ids"] = [str(x.id) for x in matched]
        if specs:
            effective_section_plan["slide_count_hint"] = len(specs)
            effective_section_plan["topic_titles"] = [str(x["title"]) for x in specs]
        effective_section_plan["teacher_regeneration_instruction"] = instruction

        updated_sections = []
        for row in plan.get("sections", []):
            updated_sections.append(effective_section_plan if row.get("section_key") == section_key else row)
        plan = {**plan, "sections": updated_sections}
        plan_run.plan_json = plan
        db.add(plan_run)
        db.commit()

    ai_enabled = bool(use_ai and settings.openai_api_key)
    writer = OpenAILessonWriter() if ai_enabled else None
    teacher_profile = _default_teacher_profile(db, project)

    run = GenerationRun(
        project_id=project.id,
        planning_run_id=plan_run.id,
        status="processing",
        writer_version=WRITER_VERSION,
        generation_mode="ai" if ai_enabled else "local",
        generation_json={},
        warnings=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        section_draft = None
        if instruction and not ai_enabled:
            section_draft, _ = _instruction_local_section(project, effective_section_plan, chunks, instruction)
        if section_draft is None:
            section_draft = _build_section(
                project=project, section_plan=effective_section_plan, objectives=objectives,
                chunks_by_id=chunks_by_id, teacher_profile=teacher_profile,
                use_ai=ai_enabled, fallback_to_local=fallback_to_local, writer=writer,
            )
        section_draft = validate_and_repair_section(
            section_draft, plan_section=effective_section_plan, valid_chunk_ids=set(chunks_by_id), source_policy=project.source_policy
        )
        from app.services.lesson_writer.v2 import enrich_section_v2
        section_draft = enrich_section_v2(
            section_draft, plan_section=effective_section_plan, chunks_by_id=chunks_by_id, project=project)
        db.execute(delete(Slide).where(Slide.section_id == section.id))
        db.flush()

        # Persist the new section first with temporary orders; then normalize all slide orders.
        new_ids: list[UUID] = []
        for idx, blueprint in enumerate(section_draft.slides, start=1):
            slide = Slide(
                project_id=project.id, section_id=section.id, generation_run_id=run.id,
                slide_order=90000 + idx, title=blueprint.title, slide_type=blueprint.slide_type,
                onscreen_text=blueprint.onscreen_text, teacher_script=blueprint.teacher_script,
                student_instruction=blueprint.student_instruction, visual_type=blueprint.visual_type,
                visual_description=blueprint.visual_description, image_prompt=blueprint.image_prompt,
                video_prompt=blueprint.video_prompt, duration_seconds=blueprint.duration_seconds,
                layout_hint=blueprint.layout_hint, media=[],
                ai_metadata={**(blueprint.metadata or {}), "guiding_question": blueprint.guiding_question, "writer_version": WRITER_VERSION, "generation_run_id": str(run.id)},
            )
            db.add(slide); db.flush(); new_ids.append(slide.id)
            for ref in blueprint.source_refs:
                if ref.source_chunk_id in chunks_by_id:
                    db.add(SlideSourceRef(slide_id=slide.id, source_chunk_id=UUID(ref.source_chunk_id), claim_text=ref.claim_text,
                                          relevance_score=Decimal(str(ref.relevance_score)) if ref.relevance_score is not None else None))
            if blueprint.interaction:
                interaction = blueprint.interaction
                settings_json = dict(interaction.settings or {}); settings_json["source_chunk_ids"] = interaction.source_chunk_ids
                settings_json["objective_numbers"] = ((section.metadata_json or {}).get("ai_plan") or {}).get("objective_numbers", [])
                db.add(Interaction(slide_id=slide.id, interaction_type=interaction.interaction_type, question=interaction.question,
                                   options=interaction.options, correct_answer=interaction.correct_answer,
                                   correct_feedback=interaction.correct_feedback, incorrect_feedback=interaction.incorrect_feedback,
                                   explanation=interaction.explanation, difficulty=interaction.difficulty,
                                   points=Decimal(str(interaction.points)), settings=settings_json))

        all_sections = list(db.scalars(select(LessonSection).where(LessonSection.project_id == project.id).order_by(LessonSection.section_order)))
        all_slides: list[Slide] = []
        for sec in all_sections:
            all_slides.extend(list(db.scalars(select(Slide).where(Slide.section_id == sec.id).order_by(Slide.slide_order))))
        for i, slide in enumerate(all_slides, start=1):
            slide.slide_order = 200000 + i
        db.flush()
        for i, slide in enumerate(all_slides, start=1):
            slide.slide_order = i
        db.flush()

        full = _full_draft_from_existing(db, project, plan_run)
        full = validate_and_repair_draft(full, plan=plan, valid_chunk_ids=set(chunks_by_id), source_policy=project.source_policy)
        # Apply validator duration repairs only to newly regenerated slides, leaving other teacher work untouched.
        duration_by_new = {x.metadata.get("existing_slide_id"): x.duration_seconds for x in full.slides if x.metadata.get("existing_slide_id") in {str(i) for i in new_ids}}
        for sid, duration in duration_by_new.items():
            row = db.get(Slide, UUID(sid)); row.duration_seconds = duration

        run.status = "completed"
        run.generation_json = SectionDraft(section_key=section_key, slides=section_draft.slides, warnings=section_draft.warnings).model_dump(mode="json")
        run.warnings = section_draft.warnings
        run.slide_count = len(section_draft.slides)
        run.source_ref_count = sum(len(x.source_refs) for x in section_draft.slides)
        run.completed_at = datetime.now(timezone.utc)
        project.status = "editing"
        db.commit(); db.refresh(run)
        return run
    except Exception as exc:
        run_id = run.id
        db.rollback()
        failed_run = db.get(GenerationRun, run_id)
        if failed_run:
            failed_run.status = "failed"
            failed_run.error_message = str(exc)
            failed_run.completed_at = datetime.now(timezone.utc)
        db.commit()
        if isinstance(exc, GenerationError):
            raise
        raise GenerationError(str(exc)) from exc


def approve_generation(db: Session, project_id: UUID, run_id: UUID) -> GenerationRun:
    project = db.get(Project, project_id)
    if not project:
        raise GenerationError("Project not found")
    run = db.get(GenerationRun, run_id)
    if not run or run.project_id != project_id:
        raise GenerationError("Generation run not found")
    if run.status != "completed":
        raise GenerationError("Only a completed generation run can be approved")
    run.teacher_approved = True
    run.approved_at = datetime.now(timezone.utc)
    generated_slides = list(db.scalars(select(Slide).where(Slide.generation_run_id == run.id)))
    for slide in generated_slides:
        slide.teacher_approved = True
    project.status = "editing"
    db.commit(); db.refresh(run)
    return run
