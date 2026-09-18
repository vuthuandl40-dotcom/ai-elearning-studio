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

def _enhance_interaction(slide: Any, section_key: str, plan_section: dict[str, Any], chunks_by_id: dict[str, Any]) -> InteractionBlueprint | None:
    current = getattr(slide, "interaction", None)
    facts = _source_facts(slide, plan_section, chunks_by_id)
    ids = _source_ids(slide, plan_section)
    should_assess = section_key.startswith("interaction_") or section_key == "practice"

    if current is None and should_assess:
        bullets = _existing_bullets(slide)
        title = _clean(str(getattr(slide, "title", ""))) or "nội dung bài học"
        statement = facts[0] if facts else (bullets[0] if bullets else f"Phần này tập trung vào nội dung: {title}.")
        current = InteractionBlueprint(
            interaction_type="true_false",
            question=f"Dựa vào nội dung bài học, nhận định sau đúng hay sai? “{statement}”",
            options=["Đúng", "Sai"],
            correct_answer="Đúng",
            correct_feedback=f"Chính xác. Nội dung trọng tâm là: {statement}",
            incorrect_feedback="Chưa chính xác. Hãy xem lại nội dung trên màn hình, đối chiếu từ khóa rồi thử lại.",
            explanation=statement,
            difficulty="understand" if section_key.startswith("interaction_") else "apply",
            points=1.0,
            settings={
                "max_attempts": 2,
                "allow_retry": True,
                "show_hint_after_attempt": 1,
                "hint": "Đối chiếu nhận định với nội dung chính trên màn hình trước khi trả lời lại.",
                "v2_fallback_interaction": not bool(facts),
            },
            source_chunk_ids=ids[:2],
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
        }
        enriched.append(_copy(slide, {
            "onscreen_text": bullets or getattr(slide, "onscreen_text", []),
            "teacher_script": script,
            "student_instruction": student,
            "guiding_question": question,
            "interaction": interaction,
            "metadata": metadata,
        }))
    result = _copy(section_draft, {"slides": enriched})
    warnings = list(getattr(result, "warnings", []) or [])
    sparse = sum(1 for slide in enriched if len(_existing_bullets(slide)) < 3)
    if sparse:
        warnings.append(f"E-Learning V2: {sparse} màn hình chưa đủ 3 ý nguồn; nên bổ sung học liệu hoặc kiểm tra lại trước khi duyệt.")
        result = _copy(result, {"warnings": warnings})
    return result
