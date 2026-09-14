from __future__ import annotations

from copy import deepcopy

from app.db.seed_sections import DEFAULT_SECTIONS
from app.services.lesson_writer.types import LessonDraft, SectionDraft, SlideBlueprint


CANONICAL_KEYS = [key for _, key, _, _ in DEFAULT_SECTIONS]
SOURCE_REQUIRED_KEYS = {
    "warmup", "lead_in", "objectives", "explore_1", "interaction_1",
    "explore_2", "interaction_2", "explore_3", "interaction_3",
    "practice", "application", "summary", "closing", "references",
}


class DraftValidationError(RuntimeError):
    pass


def _allocate_delta(slides: list[SlideBlueprint], target: int) -> int:
    current = sum(x.duration_seconds for x in slides)
    delta = target - current
    editable = [x for x in slides if not (x.metadata or {}).get("locked")]
    if not editable or delta == 0:
        return delta
    direction = 1 if delta > 0 else -1
    remaining = abs(delta)
    i = 0
    guard = max(100, (abs(delta) + len(editable)) * 5)
    while remaining and i < guard:
        slide = editable[i % len(editable)]
        if direction > 0 or slide.duration_seconds > 1:
            slide.duration_seconds += direction
            remaining -= 1
        i += 1
    return direction * remaining


def validate_and_repair_section(
    section: SectionDraft,
    *,
    plan_section: dict,
    valid_chunk_ids: set[str],
    source_policy: str,
) -> SectionDraft:
    result = deepcopy(section)
    key = plan_section.get("section_key")
    if result.section_key != key:
        raise DraftValidationError(f"SectionDraft key mismatch: expected {key}, got {result.section_key}")
    if not result.slides:
        raise DraftValidationError(f"Lesson Writer did not create any slide for section {key}.")
    permitted = set(plan_section.get("source_chunk_ids") or [])
    hint = max(1, int(plan_section.get("slide_count_hint") or 1))
    if len(result.slides) > hint + 1:
        result.warnings.append(f"{key}: AI tạo {len(result.slides)} slide, đã giới hạn còn {hint + 1}.")
        result.slides = result.slides[: hint + 1]
    for slide in result.slides:
        if slide.section_key != key:
            raise DraftValidationError(f"Slide '{slide.title}' returned wrong section_key {slide.section_key}; expected {key}.")
        slide.title = (slide.title or plan_section.get("title") or key).strip()[:180]
        slide.onscreen_text = [str(x).strip() for x in slide.onscreen_text if str(x).strip()][:7]
        unique_refs = []
        seen_refs = set()
        for ref in slide.source_refs:
            sig = (ref.source_chunk_id, ref.claim_text.strip())
            if ref.source_chunk_id in valid_chunk_ids and (not permitted or ref.source_chunk_id in permitted) and sig not in seen_refs:
                unique_refs.append(ref); seen_refs.add(sig)
        slide.source_refs = unique_refs
        if slide.interaction:
            slide.interaction.source_chunk_ids = list(dict.fromkeys(
                x for x in slide.interaction.source_chunk_ids
                if x in valid_chunk_ids and (not permitted or x in permitted)
            ))
        if source_policy == "strict" and key in SOURCE_REQUIRED_KEYS and permitted:
            if key != "references" and (slide.onscreen_text or slide.teacher_script) and not slide.source_refs:
                raise DraftValidationError(f"Strict source policy: slide '{slide.title}' in {key} has no valid source refs.")
            if slide.interaction and not slide.interaction.source_chunk_ids:
                raise DraftValidationError(f"Strict source policy: interaction in '{slide.title}' has no valid source refs.")
    if key in {"interaction_1", "interaction_2", "interaction_3", "practice"} and not any(x.interaction for x in result.slides):
        raise DraftValidationError(f"{key} must contain at least one interaction.")
    target = int(plan_section.get("planned_duration_seconds") or 0)
    leftover = _allocate_delta(result.slides, target)
    if leftover:
        result.warnings.append(f"{key}: không thể cân hết thời lượng do slide đã khóa; còn lệch {leftover:+d}s.")
    return result


def validate_and_repair_draft(
    draft: LessonDraft,
    *,
    plan: dict,
    valid_chunk_ids: set[str],
    source_policy: str,
) -> LessonDraft:
    result = deepcopy(draft)
    plan_sections = {x["section_key"]: x for x in plan.get("sections", [])}
    if set(plan_sections) != set(CANONICAL_KEYS):
        raise DraftValidationError("Approved plan is missing one or more canonical 15 sections.")

    valid_slides: list[SlideBlueprint] = []
    by_key: dict[str, list[SlideBlueprint]] = {k: [] for k in CANONICAL_KEYS}
    for slide in result.slides:
        if slide.section_key not in by_key:
            result.warnings.append(f"Loại slide có section_key không hợp lệ: {slide.section_key}")
            continue
        slide.onscreen_text = [str(x).strip() for x in slide.onscreen_text if str(x).strip()][:7]
        slide.title = slide.title.strip()[:180]
        slide.teacher_script = slide.teacher_script.strip()
        slide.student_instruction = slide.student_instruction.strip()
        unique_refs = []
        seen_refs = set()
        for ref in slide.source_refs:
            key_ref = (ref.source_chunk_id, ref.claim_text.strip())
            if ref.source_chunk_id in valid_chunk_ids and key_ref not in seen_refs:
                unique_refs.append(ref)
                seen_refs.add(key_ref)
        slide.source_refs = unique_refs
        if slide.interaction:
            slide.interaction.source_chunk_ids = list(dict.fromkeys(x for x in slide.interaction.source_chunk_ids if x in valid_chunk_ids))
        by_key[slide.section_key].append(slide)

    for key in CANONICAL_KEYS:
        slides = by_key[key]
        if not slides:
            raise DraftValidationError(f"Lesson Writer did not create any slide for section {key}.")
        plan_section = plan_sections[key]
        hint = max(1, int(plan_section.get("slide_count_hint") or 1))
        if len(slides) > hint + 1:
            result.warnings.append(f"{key}: AI tạo {len(slides)} slide, vượt xa gợi ý {hint}; đã giữ {hint + 1} slide đầu để hạn chế tải nhận thức.")
            slides = slides[: hint + 1]
            by_key[key] = slides
        elif len(slides) < max(1, hint - 1):
            result.warnings.append(f"{key}: chỉ có {len(slides)} slide so với gợi ý {hint}; giáo viên nên kiểm tra độ bao phủ nội dung.")
        permitted = set(plan_section.get("source_chunk_ids") or [])
        if permitted:
            for slide in slides:
                slide.source_refs = [r for r in slide.source_refs if r.source_chunk_id in permitted]
                if slide.interaction:
                    slide.interaction.source_chunk_ids = [x for x in slide.interaction.source_chunk_ids if x in permitted]
        if source_policy == "strict" and key in SOURCE_REQUIRED_KEYS and permitted:
            for slide in slides:
                if key != "references" and (slide.onscreen_text or slide.teacher_script) and not slide.source_refs:
                    raise DraftValidationError(f"Strict source policy: slide '{slide.title}' in {key} has no valid source refs.")
                if slide.interaction and not slide.interaction.source_chunk_ids:
                    raise DraftValidationError(f"Strict source policy: interaction in '{slide.title}' has no valid source refs.")
        if key in {"interaction_1", "interaction_2", "interaction_3"} and not any(s.interaction for s in slides):
            raise DraftValidationError(f"{key} must contain at least one interaction.")
        if key == "practice" and not any(s.interaction for s in slides):
            raise DraftValidationError("practice must contain at least one interaction.")
        target = int(plan_section.get("planned_duration_seconds") or 0)
        leftover = _allocate_delta(slides, target)
        if leftover:
            result.warnings.append(f"{key}: giữ nguyên thời lượng slide đã duyệt; lệch {leftover:+d}s so với kế hoạch section.")
        valid_slides.extend(slides)

    result.slides = valid_slides
    target_total = int(plan.get("total_duration_seconds") or 0)
    actual_total = sum(x.duration_seconds for x in result.slides)
    if actual_total != target_total:
        leftover = _allocate_delta(result.slides, target_total)
        repaired = sum(x.duration_seconds for x in result.slides)
        if leftover:
            result.warnings.append(f"Không thể cân tuyệt đối thời lượng do có slide đã khóa; tổng hiện tại {repaired}s, kế hoạch {target_total}s.")
        else:
            result.warnings.append(f"Đã cân lại tổng thời lượng slide từ {actual_total}s về {target_total}s theo kế hoạch được duyệt.")
    result.total_duration_seconds = target_total
    return result
