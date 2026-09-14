from __future__ import annotations

try:
    from openai import OpenAI
except (ImportError, ModuleNotFoundError):  # keeps local/OpenAPI tooling usable without SDK
    OpenAI = None

from app.core.config import get_settings
from app.services.lesson_writer.types import SectionDraft


class OpenAILessonWriter:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        if OpenAI is None:
            raise RuntimeError("OpenAI Python SDK is not installed correctly")
        self.client = OpenAI(api_key=self.settings.openai_api_key)

    def build_section(
        self,
        *,
        project,
        section_plan: dict,
        objectives: list[object],
        chunks: list[object],
        teacher_profile=None,
    ) -> SectionDraft:
        max_chars = self.settings.writer_max_source_chars_per_section
        blocks: list[str] = []
        used = 0
        for chunk in chunks:
            source_name = chunk.source_file.original_name if getattr(chunk, "source_file", None) else "unknown"
            block = (
                f"[CHUNK_ID={chunk.id}]\n"
                f"SOURCE={source_name}\n"
                f"PAGE={chunk.page_start or '-'}\n"
                f"HEADING={chunk.heading or '-'}\n"
                f"{chunk.content}\n"
            )
            if used + len(block) > max_chars:
                break
            blocks.append(block)
            used += len(block)

        objective_text = "\n".join(
            f"- OBJ {o.objective_order}: {o.objective_text} | level={o.cognitive_level or 'understand'} | source_chunk_ids={[str(x) for x in (o.source_chunk_ids or [])]}"
            for o in objectives
        ) or "- No explicit objective rows"

        teacher_lock = ""
        if teacher_profile:
            teacher_lock = f"""
TEACHER CHARACTER LOCK (only use when a teacher appears in a visual/video):
Name: {teacher_profile.name}
Appearance: {teacher_profile.appearance_description or ''}
Hair: {teacher_profile.hair_description or ''}
Clothing: {teacher_profile.clothing_description or ''}
Visual style: {teacher_profile.visual_style or ''}
Negative rules: {teacher_profile.negative_rules or ''}
Character lock JSON: {teacher_profile.character_lock or {}}
""".strip()

        prompt = f"""
You are the Lesson Writer and Slide Blueprint Director inside an AI E-Learning authoring app.
Write ONLY the current pedagogical section, not the whole lesson.

PROJECT
Title: {project.title}
Subject: {project.subject or ''}
Grade: {project.grade or ''}
Education level: {project.education_level or ''}
Book series: {project.book_series or ''}
Language: {project.language or 'vi'}
Visual style: {project.visual_style or 'clean modern educational'}
Narration style: {project.narration_style or 'tự nhiên, dễ hiểu'}
Interaction level: {project.interaction_level or 'medium'}
Extra instructions: {project.extra_instructions or ''}

CURRENT APPROVED SECTION PLAN
{section_plan}

LEARNING OBJECTIVES
{objective_text}

{teacher_lock}

NON-NEGOTIABLE WRITING RULES
1. Use ONLY the source chunks supplied below for factual claims. Never add outside facts, dates, statistics, names, examples, or definitions.
2. Every source-based slide must have source_refs. Each source_ref.source_chunk_id must be an exact CHUNK_ID supplied below, and claim_text must state the supported claim concisely.
3. An interaction must cite source_chunk_ids that directly support its correct answer. Never create a distractor that introduces a new factual claim unless it is obviously marked as false and does not need outside knowledge.
4. Keep each slide focused on ONE learning idea. onscreen_text: preferably 2–5 short bullets, maximum 7. Do not paste long paragraphs from the source.
5. teacher_script should sound natural and teach the idea, not merely read the bullets. Keep it proportionate to duration_seconds.
6. student_instruction must describe an observable learner action when appropriate: observe, compare, classify, answer, explain, drag, match, etc.
7. guiding_question should be a concise question that drives thinking. It can be empty for title/reference slides.
8. For interaction_1/2/3, create at least one interaction and assess only the immediately preceding Explore content indicated by the plan.
9. For practice, create interactions that collectively cover the approved objectives assigned to practice.
10. For application, prefer an open real-world task appropriate to the grade; do not invent a factual scenario requiring knowledge outside the source.
11. image_prompt and video_prompt are production prompts, not slide text. They must preserve source accuracy, avoid invented labels/numbers, specify 16:9, and request no watermark/unreadable text.
12. visual_type should be one of: hero, photo, educational_illustration, map, diagram, concept_map, infographic, comparison, timeline, quiz_ui, references, video_scene.
13. Follow slide_count_hint closely. You may differ by one slide only when necessary for cognitive load.
14. The sum of duration_seconds in this section must equal planned_duration_seconds exactly.
15. Return Vietnamese unless the project/source explicitly requires another language.
16. Do not output citations as prose. Put traceability only in source_refs / interaction.source_chunk_ids.

SOURCE CHUNKS FOR THIS SECTION
{''.join(blocks) if blocks else '[No source chunks supplied for this section]'}
""".strip()

        response = self.client.responses.parse(
            model=self.settings.lesson_writer_model,
            input=prompt,
            text_format=SectionDraft,
        )
        parsed = None
        for output in response.output:
            if getattr(output, "type", None) != "message":
                continue
            for item in output.content:
                if getattr(item, "type", None) == "output_text" and getattr(item, "parsed", None):
                    parsed = item.parsed
                    break
            if parsed:
                break
        if parsed is None:
            raise RuntimeError("AI response did not contain a parsed SectionDraft")
        return parsed
