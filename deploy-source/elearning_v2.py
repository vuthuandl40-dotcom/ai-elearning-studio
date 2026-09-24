from __future__ import annotations

import re
from typing import Any

from app.services.lesson_writer.types import InteractionBlueprint

V2_VERSION = "2.1"

_ADMIN = (
    "chương ", "tên bài dạy", "môn học:", "thiết bị dạy học", "học liệu",
    "tiến trình dạy học", "bảng tiêu chí", "rubric", "phát triển năng lực",
    "năng lực số", "i. mục tiêu", "ii. thiết bị", "iii. tiến trình",
    "yêu cầu cần đạt", "phẩm chất", "năng lực chung", "năng lực đặc thù",
)


def _clean(text: str) -> str:
    return " ".join((text or "").replace("\u00a0", " ").split()).strip(" -+•\t")


def _is_admin(text: str) -> bool:
    value = _clean(text).lower()
    if not value or value in {"a.", "b.", "c.", "d.", "i.", "ii.", "iii."}:
        return True
    return any(value.startswith(marker) for marker in _ADMIN)


def _sentences(text: str) -> list[str]:
    compact = _clean(text)
    if not compact:
        return []
    parts = re.split(r"(?<=[.!?…])\s+|\n+|\s*[;|]\s*", compact)
    out: list[str] = []
    for part in parts:
        item = _clean(part)
        if len(item) < 22 or len(item) > 220 or _is_admin(item):
            continue
        if item not in out:
            out.append(item)
    return out


def _ref_id(ref: Any) -> str | None:
    if isinstance(ref, dict):
        return str(ref.get("source_chunk_id") or "") or None
    value = getattr(ref, "source_chunk_id", None)
    return str(value) if value else None


def _source_ids(slide: Any, plan_section: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for ref in getattr(slide, "source_refs", []) or []:
        cid = _ref_id(ref)
        if cid and cid not in ids:
            ids.append(cid)
    for cid in plan_section.get("source_chunk_ids", []) or []:
        value = str(cid)
        if value not in ids:
            ids.append(value)
    return ids


def _source_facts(slide: Any, plan_section: dict[str, Any], chunks_by_id: dict[str, Any]) -> list[str]:
    facts: list[str] = []
    for cid in _source_ids(slide, plan_section)[:8]:
        chunk = chunks_by_id.get(cid)
        if not chunk:
            continue
        for sentence in _sentences(getattr(chunk, "content", "")):
            if sentence not in facts:
                facts.append(sentence)
            if len(facts) >= 12:
                return facts
    return facts


def _existing_bullets(slide: Any) -> list[str]:
    values = getattr(slide, "onscreen_text", []) or []
    if isinstance(values, str):
        values = [values]
    out: list[str] = []
    for value in values:
        item = _clean(str(value))
        if not item or _is_admin(item):
            continue
        if item not in out:
            out.append(item)
    return out


def _rich_bullets(
    slide: Any,
    plan_section: dict[str, Any],
    chunks_by_id: dict[str, Any],
    *,
    slide_index: int = 0,
) -> list[str]:
    bullets = _existing_bullets(slide)
    facts = _source_facts(slide, plan_section, chunks_by_id)
    if facts:
        shift = (max(0, slide_index) * 2) % len(facts)
        facts = facts[shift:] + facts[:shift]
    for fact in facts:
        if len(bullets) >= 4:
            break
        low = fact.lower()
        if any(low == old.lower() or low in old.lower() or old.lower() in low for old in bullets):
            continue
        bullets.append(fact)
    return bullets[:4]


def _profile(section_key: str) -> dict[str, str]:
    key = section_key or ""
    if key.startswith("explore_"):
        return {"bloom": "Understand–Analyze", "purpose": "Khám phá kiến thức từ học liệu", "interaction": "observe-compare-reveal", "assessment": "formative"}
    if key.startswith("interaction_"):
        return {"bloom": "Remember–Understand", "purpose": "Kiểm tra hiểu biết ngay sau khám phá", "interaction": "mcq-with-feedback", "assessment": "formative"}
    if key == "practice":
        return {"bloom": "Apply–Analyze", "purpose": "Luyện tập và củng cố", "interaction": "classify-match-sequence", "assessment": "practice"}
    if key == "application":
        return {"bloom": "Apply–Evaluate", "purpose": "Vận dụng vào tình huống thực tiễn", "interaction": "scenario-response", "assessment": "performance"}
    if key == "summary":
        return {"bloom": "Understand–Evaluate", "purpose": "Tổ chức lại kiến thức và tự kiểm tra", "interaction": "concept-map-self-check", "assessment": "self-check"}
    if key in {"introduction", "intro", "warmup", "lead_in"}:
        return {"bloom": "Engage", "purpose": "Tạo hứng thú và kích hoạt kiến thức nền", "interaction": "predict-poll-observe", "assessment": "diagnostic"}
    if key == "objectives":
        return {"bloom": "Orient", "purpose": "Làm rõ đích học tập", "interaction": "goal-check", "assessment": "none"}
    if key in {"closing", "ending", "references"}:
        return {"bloom": "Reflect", "purpose": "Kết thúc và định hướng học tiếp", "interaction": "reflection", "assessment": "none"}
    return {"bloom": "Understand", "purpose": "Phát triển nội dung bài học", "interaction": "guided-observation", "assessment": "formative"}


def _guiding(title: str, profile: dict[str, str], bullets: list[str]) -> str:
    pattern = profile["interaction"]
    if pattern == "observe-compare-reveal":
        return f"Những thông tin nào giúp em giải thích rõ nhất về {title.lower()}, và chúng liên hệ với nhau như thế nào?"
    if pattern == "mcq-with-feedback":
        return f"Em dựa vào chi tiết nào trong học liệu để chọn phương án đúng về {title.lower()}?"
    if pattern == "classify-match-sequence":
        return f"Em sẽ dùng tiêu chí nào để phân loại, ghép hoặc sắp xếp thông tin về {title.lower()}?"
    if pattern == "scenario-response":
        return f"Nếu gặp một tình huống thực tế liên quan đến {title.lower()}, em sẽ lựa chọn cách xử lí nào và căn cứ vào kiến thức nào?"
    if pattern == "concept-map-self-check":
        return f"Ba ý nào cần có trong sơ đồ tóm tắt về {title.lower()}, và ý nào em còn chưa chắc?"
    if pattern == "predict-poll-observe":
        return f"Trước khi học sâu hơn, em dự đoán điều gì về {title.lower()} và căn cứ vào dấu hiệu nào?"
    if bullets:
        return f"Từ các ý trên, em rút ra kết luận quan trọng nào về {title.lower()}?"
    return f"Em cần ghi nhớ điều gì quan trọng nhất về {title.lower()}?"


def _student_action(profile: dict[str, str], title: str) -> str:
    pattern = profile["interaction"]
    if pattern == "observe-compare-reveal":
        return f"Quan sát học liệu về {title.lower()}, ghi 2 phát hiện, chọn 1 bằng chứng hỗ trợ và nêu kết luận bằng 1–2 câu."
    if pattern == "mcq-with-feedback":
        return "Chọn đáp án, chỉ ra từ khóa/bằng chứng đã dùng, đọc phản hồi và sửa lại câu trả lời nếu cần."
    if pattern == "classify-match-sequence":
        return "Hoàn thành nhiệm vụ ghép/phân loại/sắp xếp, kiểm tra lại kết quả và giải thích ít nhất một lựa chọn."
    if pattern == "scenario-response":
        return "Phân tích tình huống, đề xuất phương án, nêu căn cứ từ bài học và dự đoán một hệ quả có thể xảy ra."
    if pattern == "concept-map-self-check":
        return "Hoàn thiện sơ đồ 3 ý chính, viết 1 câu kết luận và tự đánh dấu nội dung đã hiểu/chưa chắc."
    if pattern == "predict-poll-observe":
        return "Quan sát tình huống, đưa ra dự đoán ban đầu, nêu một lí do và đối chiếu lại dự đoán sau khi học."
    if pattern == "goal-check":
        return "Đọc mục tiêu, chọn nội dung mình đã biết/chưa biết và xác định một điều muốn trả lời sau bài học."
    if pattern == "reflection":
        return "Viết một điều đã hiểu rõ, một điều còn băn khoăn và một việc sẽ làm tiếp theo."
    return "Đọc/quan sát học liệu, ghi ý chính, trả lời câu hỏi gợi mở và nêu một bằng chứng từ nội dung bài học."


def _feedback(profile: dict[str, str]) -> str:
    if profile["assessment"] == "formative":
        return "Phản hồi ngay theo 3 bước: xác nhận ý đúng → chỉ ra từ khóa/bằng chứng → gợi ý cách sửa phần chưa đúng."
    if profile["assessment"] == "practice":
        return "Cho phép thử lại; lần 1 gợi ý từ khóa, lần 2 chỉ vùng nội dung cần xem lại, sau đó mới hiển thị giải thích đầy đủ."
    if profile["assessment"] == "performance":
        return "Phản hồi theo tiêu chí: đúng kiến thức, có căn cứ, phù hợp tình huống và giải thích được hệ quả."
    if profile["assessment"] == "self-check":
        return "Cho người học tự đánh giá trước, sau đó hiển thị sơ đồ/đáp án mẫu để so sánh và bổ sung."
    return "Không chấm điểm; phản hồi ngắn giúp người học biết mình cần chú ý điều gì ở màn hình kế tiếp."


def _learning_evidence(profile: dict[str, str]) -> str:
    pattern = profile["interaction"]
    if pattern == "observe-compare-reveal":
        return "2 phát hiện + 1 bằng chứng + 1 kết luận ngắn"
    if pattern == "mcq-with-feedback":
        return "1 lựa chọn + 1 căn cứ từ học liệu"
    if pattern == "classify-match-sequence":
        return "Kết quả ghép/phân loại/sắp xếp + giải thích một lựa chọn"
    if pattern == "scenario-response":
        return "Phương án xử lí + căn cứ + hệ quả dự kiến"
    if pattern == "concept-map-self-check":
        return "Sơ đồ 3 ý chính + 1 câu kết luận + tự đánh giá"
    if pattern == "predict-poll-observe":
        return "Dự đoán ban đầu + lí do + đối chiếu sau học"
    return "Ý chính ghi lại + câu trả lời cho câu hỏi gợi mở"


def _teacher_script(existing: str, title: str, question: str, profile: dict[str, str], bullets: list[str]) -> str:
    script = _clean(existing)
    if len(script) < 90:
        if profile["interaction"] == "predict-poll-observe":
            script = f"Các em chưa cần trả lời ngay. Hãy quan sát tình huống về {title.lower()}, dự đoán điều có thể xảy ra và nêu lí do cho dự đoán của mình."
        elif profile["interaction"] == "observe-compare-reveal":
            script = f"Các em tập trung vào {title.lower()}. Hãy quan sát học liệu, tìm các chi tiết nổi bật và thử nối chúng thành một nhận xét có căn cứ."
        elif profile["interaction"] == "classify-match-sequence":
            script = f"Ở phần {title.lower()}, nhiệm vụ của các em là tổ chức lại thông tin thay vì chỉ nhớ từng ý rời rạc."
        elif profile["interaction"] == "scenario-response":
            script = f"Bây giờ chúng ta chuyển kiến thức về {title.lower()} sang một tình huống gần thực tế để kiểm tra khả năng vận dụng."
        elif profile["interaction"] == "concept-map-self-check":
            script = f"Trước khi kết thúc, các em hãy hệ thống lại {title.lower()} bằng các ý thật ngắn và tự kiểm tra phần mình còn chưa chắc."
        else:
            script = f"Các em tập trung vào {title.lower()}. Hãy đọc hoặc quan sát học liệu và xác định thông tin quan trọng nhất."

    key_points = [x for x in bullets[:3] if x and x.lower() not in script.lower()]
    if key_points:
        script += " Các ý cần chốt gồm: " + " ".join(f"{i + 1}) {item}" for i, item in enumerate(key_points)) + "."

    if "?" not in script:
        script += f" {question}"
    if "chuyển" not in script.lower():
        script += " Sau khi học sinh trả lời, giáo viên chốt bằng chứng chính, sửa hiểu nhầm nếu có và chuyển sang nhiệm vụ kế tiếp."
    return script

def _fill_blank_from_statement(statement: str) -> tuple[str, str] | None:
    words = re.findall(r"[^\W\d_]{6,}", statement or "", flags=re.UNICODE)
    candidates = [w for w in words if w.lower() not in {"những", "chúng", "trong", "được", "không", "người", "thông", "nội dung", "trường"}]
    if not candidates:
        return None
    answer = max(candidates, key=len)
    question = re.sub(rf"\b{re.escape(answer)}\b", "_____", statement, count=1)
    if question == statement:
        return None
    return question, answer


def _fallback_interaction(
    *,
    section_key: str,
    title: str,
    facts: list[str],
    bullets: list[str],
    ids: list[str],
) -> InteractionBlueprint:
    pool: list[str] = []
    for value in [*facts, *bullets]:
        item = _clean(value)
        if item and item not in pool:
            pool.append(item)

    statement = pool[0] if pool else f"Phần này tập trung vào nội dung: {title}."
    difficulty = "understand" if section_key.startswith("interaction_") else "apply"
    base_settings = {
        "max_attempts": 2,
        "allow_retry": True,
        "show_hint_after_attempt": 1,
        "v2_generated_interaction": True,
    }

    if section_key == "interaction_2":
        blank = _fill_blank_from_statement(statement)
        if blank:
            question_text, answer = blank
            return InteractionBlueprint(
                interaction_type="fill_blank",
                question=f"Điền từ còn thiếu dựa vào học liệu: “{question_text}”",
                options=[],
                correct_answer=answer,
                correct_feedback=f"Chính xác. Từ cần điền là “{answer}”.",
                incorrect_feedback="Chưa chính xác. Hãy đọc lại câu trong học liệu và chú ý từ khóa bị khuyết.",
                explanation=statement,
                difficulty="understand",
                points=1.0,
                settings={**base_settings, "hint": "Tìm đúng câu có cấu trúc gần giống trong học liệu."},
                source_chunk_ids=ids[:2],
            )

    if section_key == "interaction_3" and len(pool) >= 2:
        options = pool[:4]
        return InteractionBlueprint(
            interaction_type="single_choice",
            question=f"Ý nào dưới đây được dùng làm ý trọng tâm đầu tiên để làm rõ nội dung “{title}”?",
            options=options,
            correct_answer=options[0],
            correct_feedback="Chính xác. Đây là ý trọng tâm được ưu tiên ở màn hình này.",
            incorrect_feedback="Chưa chính xác. Hãy đối chiếu thứ tự các ý chính trên màn hình rồi thử lại.",
            explanation=options[0],
            difficulty="analyze",
            points=1.0,
            settings={**base_settings, "hint": "Chú ý ý xuất hiện đầu tiên trong phần nội dung trọng tâm."},
            source_chunk_ids=ids[:2],
        )

    if section_key == "practice" and len(pool) >= 2:
        pairs: list[tuple[str, str]] = []
        for statement_item in pool[:4]:
            words = statement_item.split()
            if len(words) < 8:
                continue
            cut = max(3, min(len(words) - 3, len(words) // 2))
            left = " ".join(words[:cut]).rstrip(" ,;:") + "…"
            right = "… " + " ".join(words[cut:]).lstrip(" ,;:")
            if left and right and all(left != old_left and right != old_right for old_left, old_right in pairs):
                pairs.append((left, right))
        if len(pairs) >= 2:
            mapping = {left: right for left, right in pairs}
            return InteractionBlueprint(
                interaction_type="matching",
                question=f"Ghép hai vế để khôi phục các ý đúng từ học liệu về “{title}”.",
                options=[{"left": left, "right": right} for left, right in pairs],
                correct_answer=mapping,
                correct_feedback="Chính xác. Em đã ghép đúng các ý theo nội dung học liệu.",
                incorrect_feedback="Chưa chính xác. Hãy đối chiếu ý nghĩa giữa hai vế và thử ghép lại.",
                explanation="Các cặp đều được tách trực tiếp từ các ý xuất hiện trong nội dung bài học.",
                difficulty="apply",
                points=1.0,
                settings={**base_settings, "hint": "Đọc trọn ý trong học liệu rồi ghép phần mở đầu với phần kết thúc phù hợp."},
                source_chunk_ids=ids[:2],
            )
        options = pool[:4]
        return InteractionBlueprint(
            interaction_type="multiple_choice",
            question=f"Chọn các ý xuất hiện trực tiếp trong nội dung luyện tập về “{title}”.",
            options=options,
            correct_answer=options,
            correct_feedback="Chính xác. Em đã nhận diện đầy đủ các ý có trong học liệu.",
            incorrect_feedback="Chưa đủ hoặc có lựa chọn chưa phù hợp. Hãy đối chiếu từng phương án với học liệu rồi thử lại.",
            explanation="Các phương án đúng đều được lấy trực tiếp từ nội dung màn hình/học liệu.",
            difficulty="apply",
            points=1.0,
            settings={**base_settings, "hint": "Đối chiếu từng phương án với nội dung vừa học; không chọn theo suy đoán."},
            source_chunk_ids=ids[:2],
        )

    return InteractionBlueprint(
        interaction_type="true_false",
        question=f"Dựa vào nội dung bài học, nhận định sau đúng hay sai? “{statement}”",
        options=["Đúng", "Sai"],
        correct_answer="Đúng",
        correct_feedback=f"Chính xác. Nội dung trọng tâm là: {statement}",
        incorrect_feedback="Chưa chính xác. Hãy xem lại nội dung trên màn hình, đối chiếu từ khóa rồi thử lại.",
        explanation=statement,
        difficulty=difficulty,
        points=1.0,
        settings={**base_settings, "hint": "Đối chiếu nhận định với nội dung chính trên màn hình trước khi trả lời lại."},
        source_chunk_ids=ids[:2],
    )


def _enhance_interaction(slide: Any, section_key: str, plan_section: dict[str, Any], chunks_by_id: dict[str, Any]) -> InteractionBlueprint | None:
    current = getattr(slide, "interaction", None)
    facts = _source_facts(slide, plan_section, chunks_by_id)
    ids = _source_ids(slide, plan_section)
    should_assess = section_key.startswith("interaction_") or section_key == "practice"

    if current is None and should_assess:
        bullets = _existing_bullets(slide)
        title = _clean(str(getattr(slide, "title", ""))) or "nội dung bài học"
        current = _fallback_interaction(
            section_key=section_key,
            title=title,
            facts=facts,
            bullets=bullets,
            ids=ids,
        )

    if current is None:
        return None

    settings = dict(current.settings or {})
    settings.setdefault("max_attempts", 2)
    settings.setdefault("allow_retry", True)
    settings.setdefault("show_hint_after_attempt", 1)
    settings.setdefault("hint", "Đối chiếu lại học liệu và chú ý các từ khóa chính trước khi trả lời lại.")
    settings["elearning_v2"] = True
    correct = _clean(current.correct_feedback)
    incorrect = _clean(current.incorrect_feedback)
    explanation = _clean(current.explanation)
    if len(correct) < 35:
        correct = "Chính xác. Em đã xác định đúng thông tin trọng tâm trong học liệu."
    if len(incorrect) < 45:
        incorrect = "Chưa chính xác. Hãy đọc lại phần học liệu liên quan, đối chiếu từ khóa và thử lại."
    if len(explanation) < 30 and facts:
        explanation = facts[0]
    return current.model_copy(update={
        "correct_feedback": correct,
        "incorrect_feedback": incorrect,
        "explanation": explanation,
        "settings": settings,
        "source_chunk_ids": current.source_chunk_ids or ids[:2],
    })



def _design_profile(
    section_key: str,
    slide_index: int,
    current_visual: str,
    title: str,
    bullets: list[str],
    *,
    interaction_type: str = "",
    previous_layouts: list[str] | None = None,
) -> dict[str, str]:
    """Choose a source-safe semantic composition and actively avoid layout monotony."""
    key = section_key or ""
    current = _clean(current_visual).lower()
    semantic_text = " ".join([title, *bullets]).lower()
    previous_layouts = previous_layouts or []

    def choose(family: list[tuple[str, str, str]], seed: int = 0) -> dict[str, str]:
        if not family:
            return {"layout": "center-focus", "visual": "infographic", "motion": "center-reveal"}
        start_index = seed % len(family)
        ordered = family[start_index:] + family[:start_index]
        # Never repeat the same layout three times; prefer a layout not used
        # immediately before and then one with the lowest section-local count.
        recent = previous_layouts[-2:]
        candidates = [item for item in ordered if not (len(recent) == 2 and recent[0] == recent[1] == item[0])]
        if not candidates:
            candidates = ordered
        min_count = min(previous_layouts.count(item[0]) for item in candidates)
        candidates = [item for item in candidates if previous_layouts.count(item[0]) == min_count]
        layout, visual, motion = candidates[0]
        return {"layout": layout, "visual": visual, "motion": motion}

    # Pedagogical role has the highest priority.
    fixed_roles = {
        "introduction": ("cinematic-hero", "hero", "slow-zoom-title"),
        "objectives": ("milestone-checklist", "learning_objectives", "staggered-reveal"),
        "warmup": ("question-spotlight", "hook_visual", "question-pause"),
        "lead_in": ("scenario-stage", "scenario", "scene-reveal"),
        "application": ("real-world-scenario", "scenario", "scenario-decision"),
        "summary": ("concept-map", "concept_map", "branch-reveal"),
        "closing": ("takeaway-cards", "takeaway", "card-reveal"),
        "references": ("source-list", "references", "none"),
    }
    if key in fixed_roles:
        layout, visual, motion = fixed_roles[key]
        return {"layout": layout, "visual": visual, "motion": motion}

    if key.startswith("interaction_"):
        interaction_families = {
            "fill_blank": [("fill-blank-focus", "quiz_ui", "blank-answer-feedback")],
            "matching": [("matching-workspace", "matching_ui", "pair-reveal")],
            "drag_drop": [("activity-board", "drag_drop_ui", "drag-feedback")],
            "multiple_choice": [("evidence-choice", "quiz_ui", "evidence-feedback"), ("quiz-card", "quiz_ui", "choice-feedback")],
            "single_choice": [("quiz-card", "quiz_ui", "choice-feedback"), ("evidence-choice", "quiz_ui", "evidence-feedback")],
            "true_false": [("question-spotlight", "quiz_ui", "choice-feedback"), ("quiz-card", "quiz_ui", "choice-feedback")],
        }
        return choose(interaction_families.get(interaction_type, [("quiz-card", "quiz_ui", "choice-feedback")]), slide_index)

    if key == "practice":
        interaction_families = {
            "matching": [
                ("matching-workspace", "matching_ui", "pair-reveal"),
                ("activity-board", "practice_board", "task-reveal"),
            ],
            "drag_drop": [
                ("activity-board", "drag_drop_ui", "drag-feedback"),
                ("sequence-workspace", "sequence_ui", "step-reveal"),
            ],
            "fill_blank": [
                ("fill-blank-focus", "quiz_ui", "blank-answer-feedback"),
                ("activity-board", "practice_board", "task-reveal"),
            ],
        }
        return choose(
            interaction_families.get(
                interaction_type,
                [
                    ("activity-board", "practice_board", "task-reveal"),
                    ("matching-workspace", "matching_ui", "pair-reveal"),
                    ("sequence-workspace", "sequence_ui", "step-reveal"),
                ],
            ),
            slide_index,
        )

    explore_offsets = {"explore_1": 0, "explore_2": 1, "explore_3": 2}
    semantic_index = slide_index + explore_offsets.get(key, 0)

    # Explicit semantic families. Order matters: a data table is not a chart,
    # and coordinates are not automatically a map task.
    families: list[tuple[tuple[str, ...], list[tuple[str, str, str]]]] = [
        (
            ("bảng số liệu", "bảng dữ liệu", "dữ liệu bảng", "table", "bảng thống kê"),
            [
                ("data-table", "table", "row-reveal"),
                ("evidence-board", "table", "card-reveal"),
                ("comparison-2-column", "table", "paired-reveal"),
            ],
        ),
        (
            ("biểu đồ", "chart", "đồ thị", "biểu đồ cột", "biểu đồ tròn", "biểu đồ đường", "cơ cấu"),
            [
                ("chart-focus", "chart", "progressive-reveal"),
                ("evidence-board", "chart", "card-reveal"),
                ("split-visual-explain", "chart", "left-right-reveal"),
            ],
        ),
        (
            ("nguyên nhân", "kết quả", "hệ quả", "tác động", "ảnh hưởng", "dẫn đến", "cause", "effect"),
            [
                ("cause-effect", "cause_effect_diagram", "connector-reveal"),
                ("comparison-2-column", "cause_effect_diagram", "paired-reveal"),
                ("evidence-board", "evidence_cards", "card-reveal"),
            ],
        ),
        (
            ("so sánh", "khác nhau", "giống nhau", "đối chiếu", "compare", "versus"),
            [
                ("comparison-2-column", "comparison", "paired-reveal"),
                ("evidence-board", "comparison", "card-reveal"),
                ("split-visual-explain", "comparison", "left-right-reveal"),
            ],
        ),
        (
            ("trình tự", "giai đoạn", "quá trình", "các bước", "quy trình", "timeline", "sequence"),
            [
                ("process-timeline", "process_diagram", "step-reveal"),
                ("sequence-workspace", "sequence_ui", "step-reveal"),
                ("cause-effect", "cause_effect_diagram", "connector-reveal"),
            ],
        ),
        (
            ("sơ đồ tư duy", "mối quan hệ", "sơ đồ khái niệm", "concept map"),
            [
                ("concept-map", "concept_map", "branch-reveal"),
                ("evidence-board", "concept_map", "card-reveal"),
                ("cause-effect", "concept_map", "connector-reveal"),
            ],
        ),
        (
            ("cấu tạo", "đặc điểm", "bộ phận", "quan sát hình", "hình ảnh", "chú giải", "chi tiết"),
            [
                ("annotated-visual", "annotated_image", "hotspot-reveal"),
                ("zoom-detail", "closeup_diagram", "zoom-and-label"),
                ("split-visual-explain", "educational_illustration", "left-right-reveal"),
            ],
        ),
    ]

    if key in explore_offsets:
        for cues, family in families:
            if any(cue in semantic_text for cue in cues):
                return choose(family, semantic_index)

        # A map layout requires an actual map-oriented learning action or an
        # explicit map/atlas/diagram source cue. Subject vocabulary such as
        # "kinh tuyến", "vĩ tuyến", "tọa độ" alone is NOT sufficient.
        map_objects = ("bản đồ", "lược đồ", "atlat", "atlas")
        map_actions = (
            "xác định vị trí", "chỉ trên", "quan sát bản đồ", "quan sát lược đồ",
            "đọc bản đồ", "khai thác bản đồ", "phân bố", "khu vực", "vị trí địa lí",
            "vị trí địa lý",
        )
        explicit_map = any(cue in semantic_text for cue in map_objects)
        map_task = explicit_map or (
            current == "map" and any(cue in semantic_text for cue in map_actions)
        )
        if map_task:
            map_family = [
                ("map-focus", "map", "progressive-reveal"),
                ("annotated-visual", "map", "hotspot-reveal"),
                ("split-visual-explain", "map", "left-right-reveal"),
                ("zoom-detail", "map", "zoom-and-label"),
            ]
            # map-focus itself is capped at one use per section; later map
            # screens rotate to annotation/zoom/explanation compositions.
            if "map-focus" in previous_layouts:
                map_family = [item for item in map_family if item[0] != "map-focus"]
            return choose(map_family, semantic_index)

        # Geography concepts that mention coordinates/longitude/latitude but
        # are explanatory rather than map-reading should use concept/diagram
        # layouts instead of pretending every screen is a map.
        geo_concepts = ("kinh tuyến", "vĩ tuyến", "tọa độ", "toạ độ", "kinh độ", "vĩ độ", "latitude", "longitude")
        if any(cue in semantic_text for cue in geo_concepts):
            return choose(
                [
                    ("annotated-visual", "diagram", "hotspot-reveal"),
                    ("comparison-2-column", "comparison", "paired-reveal"),
                    ("zoom-detail", "closeup_diagram", "zoom-and-label"),
                    ("concept-map", "concept_map", "branch-reveal"),
                ],
                semantic_index,
            )

    # General exploration palettes deliberately differ by knowledge block.
    if key == "explore_1":
        family = [
            ("annotated-visual", "annotated_image", "hotspot-reveal"),
            ("split-visual-explain", "educational_illustration", "left-right-reveal"),
            ("zoom-detail", "closeup_diagram", "zoom-and-label"),
            ("center-focus", "infographic", "center-reveal"),
        ]
    elif key == "explore_2":
        family = [
            ("comparison-2-column", "comparison", "paired-reveal"),
            ("evidence-board", "evidence_cards", "card-reveal"),
            ("text-left-visual-right", "educational_illustration", "right-focus"),
            ("annotated-visual", "annotated_image", "hotspot-reveal"),
        ]
    elif key == "explore_3":
        family = [
            ("process-timeline", "process_diagram", "step-reveal"),
            ("cause-effect", "cause_effect_diagram", "connector-reveal"),
            ("full-bleed-annotated", "annotated_image", "pan-and-label"),
            ("visual-left-text-right", "educational_illustration", "left-right-reveal"),
        ]
    else:
        family = [
            ("visual-left-text-right", "educational_illustration", "left-right-reveal"),
            ("text-left-visual-right", "educational_illustration", "right-focus"),
            ("center-focus", "infographic", "center-reveal"),
            ("evidence-board", "evidence_cards", "card-reveal"),
        ]
    return choose(family, semantic_index)


def _visual_direction_text(design: dict[str, str], title: str, bullets: list[str]) -> str:
    focus = bullets[0] if bullets else title
    return (
        f"{design['visual']} cho nội dung '{title}', bố cục {design['layout']}; "
        f"một trọng tâm thị giác rõ ràng; ưu tiên minh họa trực tiếp ý: {focus}. "
        "Không thêm số liệu, địa danh hay kiến thức ngoài học liệu."
    )


def _copy(model: Any, updates: dict[str, Any]) -> Any:
    if hasattr(model, "model_copy"):
        return model.model_copy(update=updates)
    for key, value in updates.items():
        try:
            setattr(model, key, value)
        except Exception:
            pass
    return model


def enrich_section_v2(section_draft: Any, *, plan_section: dict[str, Any], chunks_by_id: dict[str, Any], project: Any) -> Any:
    """Source-safe pedagogical enrichment; factual claims remain grounded in source chunks."""
    section_key = str(plan_section.get("section_key") or getattr(section_draft, "section_key", ""))
    profile = _profile(section_key)
    enriched: list[Any] = []
    for index, slide in enumerate(getattr(section_draft, "slides", []) or []):
        title = _clean(str(getattr(slide, "title", ""))) or f"Màn hình {index + 1}"
        bullets = _rich_bullets(slide, plan_section, chunks_by_id, slide_index=index)
        question = _clean(str(getattr(slide, "guiding_question", ""))) or _guiding(title, profile, bullets)
        student = _clean(str(getattr(slide, "student_instruction", "")))
        if len(student) < 45:
            student = _student_action(profile, title)
        script = _teacher_script(str(getattr(slide, "teacher_script", "")), title, question, profile, bullets)
        interaction = _enhance_interaction(slide, section_key, plan_section, chunks_by_id)
        interaction_type = str(getattr(interaction, "interaction_type", "") or "")
        design = _design_profile(
            section_key,
            index,
            str(getattr(slide, "visual_type", "") or ""),
            title,
            bullets,
            interaction_type=interaction_type,
            previous_layouts=used_layouts,
        )
        used_layouts.append(design["layout"])
        metadata = dict(getattr(slide, "metadata", {}) or {})
        metadata["elearning_v2"] = {
            "version": V2_VERSION,
            "screen_purpose": profile["purpose"],
            "bloom_level": profile["bloom"],
            "interaction_pattern": profile["interaction"],
            "assessment_role": profile["assessment"],
            "student_action": student,
            "feedback_strategy": _feedback(profile),
            "learning_evidence": _learning_evidence(profile),
            "completion_criteria": "Người học tạo được sản phẩm/đầu ra học tập theo yêu cầu và dùng ít nhất một chi tiết từ học liệu để giải thích.",
            "accessibility_alt": f"Minh họa học tập cho nội dung: {title}.",
            "transition": "Nhận phản hồi → chốt ý → kết nối với nhiệm vụ kế tiếp.",
            "screen_sequence": "Gợi mở → học liệu → hành động của học sinh → phản hồi → chốt kiến thức.",
            "source_safe": True,
            "content_depth": "rich" if len(bullets) >= 3 else "needs-review",
            "scored_interaction": interaction is not None,
            "layout_family": design["layout"],
            "visual_family": design["visual"],
            "motion_pattern": design["motion"],
            "layout_reason": f"{section_key}:{design['visual']}",
            "semantic_role": profile["purpose"],
        }
        enriched.append(_copy(slide, {
            "onscreen_text": bullets or getattr(slide, "onscreen_text", []),
            "teacher_script": script,
            "student_instruction": student,
            "guiding_question": question,
            "interaction": interaction,
            "layout_hint": design["layout"],
            "visual_type": design["visual"],
            "visual_description": _visual_direction_text(design, title, bullets),
            "metadata": metadata,
        }))
    result = _copy(section_draft, {"slides": enriched})
    warnings = list(getattr(result, "warnings", []) or [])
    sparse = sum(1 for slide in enriched if len(_existing_bullets(slide)) < 3)
    if sparse:
        warnings.append(f"E-Learning V2: {sparse} màn hình chưa đủ 3 ý nguồn; nên bổ sung học liệu hoặc kiểm tra lại trước khi duyệt.")
        result = _copy(result, {"warnings": warnings})
    return result
