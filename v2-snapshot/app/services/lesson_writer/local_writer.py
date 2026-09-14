from __future__ import annotations

import re
from collections import defaultdict
from itertools import cycle

from app.services.lesson_writer.types import ClaimRef, InteractionBlueprint, SectionDraft, SlideBlueprint


INTERACTION_SECTIONS = {"interaction_1", "interaction_2", "interaction_3", "practice"}
SOURCE_HEAVY_SECTIONS = {
    "warmup", "lead_in", "objectives", "explore_1", "interaction_1",
    "explore_2", "interaction_2", "explore_3", "interaction_3",
    "practice", "application", "summary", "closing", "references",
}


def _compact(text: str, limit: int = 180) -> str:
    value = " ".join((text or "").split())
    if len(value) <= limit:
        return value
    cut = value[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return cut + "…"


def _first_sentence(text: str, limit: int = 170) -> str:
    compact = " ".join((text or "").split())
    parts = re.split(r"(?<=[.!?…])\s+", compact, maxsplit=1)
    return _compact(parts[0] if parts else compact, limit)


def _allocate(total: int, count: int) -> list[int]:
    if count <= 0:
        return []
    base, rem = divmod(max(0, total), count)
    return [base + (1 if i < rem else 0) for i in range(count)]


def _source_rows(section_plan: dict, chunks_by_id: dict[str, object]) -> list[object]:
    return [chunks_by_id[x] for x in section_plan.get("source_chunk_ids", []) if x in chunks_by_id]


def _source_bullets(rows: list[object], count: int = 4) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    for row in rows:
        text = _first_sentence(getattr(row, "content", ""), 165)
        if text and not any(text == old[0] for old in output):
            output.append((text, str(row.id)))
        if len(output) >= count:
            break
    return output


def _visual_type(section_key: str, planned: dict) -> str:
    direction = (planned.get("visual_direction") or "").lower()
    if "bản đồ" in direction:
        return "map"
    if "sơ đồ" in direction or section_key == "summary":
        return "concept_map"
    if "bảng" in direction:
        return "comparison"
    if section_key in INTERACTION_SECTIONS:
        return "quiz_ui"
    if section_key == "references":
        return "references"
    return "educational_illustration"


def _visual_prompts(project, section_key: str, title: str, bullets: list[str], visual_type: str, teacher_profile=None) -> tuple[str, str, str]:
    style = project.visual_style or "clean modern educational"
    teacher = ""
    if teacher_profile:
        lock = teacher_profile.character_lock or {}
        lock_text = "; ".join(f"{k}: {v}" for k, v in lock.items() if v)
        teacher = (
            f" Keep the teacher character consistent: {teacher_profile.appearance_description or ''}; "
            f"hair: {teacher_profile.hair_description or ''}; clothing: {teacher_profile.clothing_description or ''}; "
            f"style: {teacher_profile.visual_style or style}; {lock_text}."
        ).strip()
    facts = "; ".join(bullets[:3])
    visual_description = f"{visual_type}: minh họa trực quan cho ‘{title}’, ưu tiên một ý chính, dễ quan sát ở cấp {project.grade or ''}."
    image_prompt = (
        f"Create a {style} educational visual for the lesson '{project.title}', section '{title}'. "
        f"Visual type: {visual_type}. Ground the visual concept in these source-backed ideas: {facts}. "
        "16:9 composition, clear focal hierarchy, classroom-safe, no invented statistics, no unreadable text, no watermark. "
        + teacher
    ).strip()
    video_prompt = (
        f"Create a short educational 16:9 scene for '{title}' in a {style} style. "
        f"Show the concept visually using only these source-backed ideas: {facts}. "
        "Slow clear camera movement, one main learning focus, no extra factual labels or invented numbers. "
        + teacher
    ).strip()
    return visual_description, image_prompt, video_prompt


def _true_false_interaction(statement: str, chunk_id: str, difficulty: str = "understand") -> InteractionBlueprint:
    return InteractionBlueprint(
        interaction_type="true_false",
        question=f"Theo tài liệu nguồn, nhận định sau đúng hay sai? “{statement}”",
        options=["Đúng", "Sai"],
        correct_answer="Đúng",
        correct_feedback="Chính xác! Nhận định này được nêu trong tài liệu của bài học.",
        incorrect_feedback="Chưa chính xác. Em hãy đối chiếu lại ý vừa học trong học liệu.",
        explanation=statement,
        difficulty=difficulty,
        source_chunk_ids=[chunk_id],
    )


def build_local_section_draft(project, section_plan: dict, chunks_by_id: dict[str, object], objectives: list[object], teacher_profile=None) -> SectionDraft:
    key = section_plan["section_key"]
    count = max(1, int(section_plan.get("slide_count_hint") or 1))
    duration = int(section_plan.get("planned_duration_seconds") or 0)
    durations = _allocate(duration, count)
    rows = _source_rows(section_plan, chunks_by_id)
    source_pairs = _source_bullets(rows, max(4, count * 3))
    topic_titles = section_plan.get("topic_titles") or []
    title = section_plan.get("title") or key
    warnings: list[str] = []

    if key in SOURCE_HEAVY_SECTIONS and section_plan.get("source_chunk_ids") and not rows:
        warnings.append(f"{key}: không tìm thấy source chunk hợp lệ trong database; chỉ tạo khung nội dung.")

    slides: list[SlideBlueprint] = []

    if key == "introduction":
        visual_type = "hero"
        desc, img, vid = _visual_prompts(project, key, project.title, [], visual_type, teacher_profile)
        slides.append(SlideBlueprint(
            section_key=key,
            title=project.title,
            slide_type="title",
            onscreen_text=[x for x in [project.subject, f"Lớp {project.grade}" if project.grade else None, project.book_series] if x],
            teacher_script=f"Chào các em. Hôm nay chúng ta cùng tìm hiểu bài: {project.title}.",
            student_instruction="Quan sát hình ảnh chủ đề và chuẩn bị vào bài học.",
            visual_type=visual_type,
            visual_description=desc,
            image_prompt=img,
            video_prompt=vid,
            duration_seconds=durations[0],
            layout_hint="hero-title: tiêu đề lớn, ít chữ, visual chiếm 60–70% khung hình",
        ))
        return SectionDraft(section_key=key, slides=slides, warnings=warnings)

    if key == "objectives":
        obj_numbers = set(section_plan.get("objective_numbers") or [])
        selected = [o for o in objectives if not obj_numbers or o.objective_order in obj_numbers]
        items = [_compact(o.objective_text, 150) for o in selected]
        refs = []
        for o in selected:
            for cid in o.source_chunk_ids or []:
                refs.append(ClaimRef(source_chunk_id=str(cid), claim_text=o.objective_text))
        desc, img, vid = _visual_prompts(project, key, title, items, "learning_objectives", teacher_profile)
        slides.append(SlideBlueprint(
            section_key=key, title="Sau bài học, em có thể…", slide_type="objectives",
            onscreen_text=items[:6],
            teacher_script="Các em hãy đọc các yêu cầu cần đạt để biết những nhiệm vụ trọng tâm của bài học.",
            student_instruction="Đọc mục tiêu và xác định điều em cần thực hiện được sau bài học.",
            visual_type="learning_objectives", visual_description=desc, image_prompt=img, video_prompt=vid,
            duration_seconds=durations[0], layout_hint="checklist 2 cột, tối đa 6 ý", source_refs=refs,
        ))
        return SectionDraft(section_key=key, slides=slides, warnings=warnings)

    if key == "references":
        file_names = []
        for row in rows:
            name = row.source_file.original_name if getattr(row, "source_file", None) else "Tài liệu nguồn"
            if name not in file_names:
                file_names.append(name)
        slides.append(SlideBlueprint(
            section_key=key, title="Tài liệu tham khảo", slide_type="references",
            onscreen_text=file_names or ["Các tài liệu nguồn được giáo viên cung cấp cho dự án."],
            teacher_script="Các nội dung trong bài được xây dựng từ các tài liệu nguồn liệt kê trên màn hình.",
            student_instruction="Có thể mở mục Xem nguồn để đối chiếu nội dung khi cần.",
            visual_type="references", visual_description="Danh mục tài liệu sạch, dễ đọc.",
            duration_seconds=durations[0], layout_hint="reference-list",
            source_refs=[ClaimRef(source_chunk_id=str(r.id), claim_text="Nguồn tài liệu được sử dụng trong bài") for r in rows[:20]],
        ))
        return SectionDraft(section_key=key, slides=slides, warnings=warnings)

    if not source_pairs:
        source_pairs = [("Nội dung sẽ được hoàn thiện sau khi có đủ tài liệu nguồn cho phần này.", "")]

    pair_cycle = cycle(source_pairs)
    topic_cycle = cycle(topic_titles or [title])
    for index in range(count):
        pairs = [next(pair_cycle) for _ in range(min(3, len(source_pairs)))]
        bullets = [p[0] for p in pairs]
        refs = [ClaimRef(source_chunk_id=p[1], claim_text=p[0]) for p in pairs if p[1]]
        slide_title = next(topic_cycle)
        interaction = None
        slide_type = "content"
        guiding = ""

        if key == "warmup":
            slide_title = "Khởi động"
            guiding = f"Em đã biết gì về {topic_titles[0] if topic_titles else project.title}?"
            slide_type = "warmup"
            interaction = _true_false_interaction(bullets[0], pairs[0][1], "remember") if pairs[0][1] else None
        elif key == "lead_in":
            slide_title = "Tình huống vào bài"
            guiding = f"Từ thông tin trên, em dự đoán bài học sẽ giúp chúng ta giải quyết vấn đề gì?"
            slide_type = "lead_in"
        elif key.startswith("explore_"):
            slide_type = "explore"
            guiding = f"Quan sát học liệu và rút ra nhận xét về {slide_title}."
        elif key in {"interaction_1", "interaction_2", "interaction_3"}:
            slide_title = "Kiểm tra nhanh"
            slide_type = "interaction"
            interaction = _true_false_interaction(bullets[0], pairs[0][1]) if pairs[0][1] else None
        elif key == "practice":
            slide_title = f"Luyện tập {index + 1}"
            slide_type = "practice"
            interaction = _true_false_interaction(bullets[0], pairs[0][1], "understand") if pairs[0][1] else None
        elif key == "application":
            slide_title = "Vận dụng"
            slide_type = "application"
            guiding = "Hãy dùng kiến thức vừa học để giải thích hoặc đề xuất cách xử lý một tình huống phù hợp trong thực tế."
            bullets = ["Nêu ý kiến của em.", "Dẫn chứng bằng kiến thức đã học.", "Giải thích ngắn gọn vì sao."]
        elif key == "summary":
            slide_title = "Tổng kết bài học"
            slide_type = "summary"
        elif key == "closing":
            slide_title = "Ghi nhớ và nhiệm vụ tiếp theo"
            slide_type = "closing"

        visual_type = _visual_type(key, section_plan)
        desc, img, vid = _visual_prompts(project, key, slide_title, [p[0] for p in pairs], visual_type, teacher_profile)
        script_core = " ".join(bullets[:3])
        teacher_script = (
            f"Các em hãy quan sát và chú ý những ý chính sau. {script_core} "
            + (f"Sau đó, {guiding.lower()}" if guiding else "")
        ).strip()
        instruction = section_plan.get("student_activity") or "Quan sát, suy nghĩ và trả lời câu hỏi."

        slides.append(SlideBlueprint(
            section_key=key,
            title=slide_title,
            slide_type=slide_type,
            onscreen_text=bullets[:5],
            teacher_script=teacher_script,
            student_instruction=instruction,
            guiding_question=guiding,
            visual_type=visual_type,
            visual_description=desc,
            image_prompt=img,
            video_prompt=vid,
            duration_seconds=durations[index],
            layout_hint="visual-left/text-right" if slide_type in {"content", "explore"} else "single-focus",
            interaction=interaction,
            source_refs=refs,
            metadata={"local_fallback": True},
        ))

    return SectionDraft(section_key=key, slides=slides, warnings=warnings)
