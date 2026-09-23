import sys
from pathlib import Path

root=Path(sys.argv[1])

p=root/"app/services/source_analyzer/parsers.py"
s=p.read_text()
if "from docx.oxml.table import CT_Tbl" not in s:
    s=s.replace(
        "from docx import Document\n",
        "from docx import Document\nfrom docx.oxml.table import CT_Tbl\nfrom docx.oxml.text.paragraph import CT_P\nfrom docx.table import Table\nfrom docx.text.paragraph import Paragraph\n"
    )
start=s.index("def parse_docx(path: Path) -> ParsedDocument:")
end=s.index("\ndef parse_pptx(", start)
new_docx='''def _iter_docx_blocks(doc):
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)


def parse_docx(path: Path) -> ParsedDocument:
    doc = Document(path)
    units: list[ParsedUnit] = []
    current_heading: str | None = None
    paragraph_index = 0
    table_index = 0
    block_index = 0

    for block in _iter_docx_blocks(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                block_index += 1
                continue
            style_name = (block.style.name or "").lower() if block.style else ""
            if style_name.startswith("heading") or _looks_like_heading(text):
                current_heading = text
            units.append(
                ParsedUnit(
                    text=text,
                    heading=current_heading,
                    metadata={
                        "kind": "paragraph",
                        "paragraph_index": paragraph_index,
                        "block_index": block_index,
                        "style": block.style.name if block.style else None,
                    },
                )
            )
            paragraph_index += 1
        else:
            rows: list[str] = []
            for row_index, row in enumerate(block.rows):
                values = [" ".join(cell.text.split()) for cell in row.cells]
                if not any(values):
                    continue
                if row_index == 0:
                    for value in values:
                        if _looks_like_heading(value):
                            current_heading = value
                            break
                rows.append(" | ".join(values))
            if rows:
                units.append(
                    ParsedUnit(
                        text="\\n".join(rows),
                        heading=current_heading,
                        metadata={
                            "kind": "table",
                            "table_index": table_index,
                            "block_index": block_index,
                            "row_count": len(rows),
                            "preserved_document_order": True,
                        },
                    )
                )
            table_index += 1
        block_index += 1

    return ParsedDocument(
        units=units,
        page_count=None,
        metadata={
            "paragraph_count": paragraph_index,
            "table_count": table_index,
            "block_count": block_index,
            "preserved_document_order": True,
        },
    )

'''
s=s[:start]+new_docx+s[end+1:]
p.write_text(s)

p=root/"app/services/source_analyzer/knowledge_map.py"
s=p.read_text()
start=s.index("def build_local_knowledge_map(project_title: str, chunks: Iterable) -> KnowledgeMap:")
new_km='''def build_local_knowledge_map(project_title: str, chunks: Iterable) -> KnowledgeMap:
    """Deterministic, source-preserving fallback used when no AI key is configured."""
    grouped: OrderedDict[str, list] = OrderedDict()
    for chunk in chunks:
        heading = (chunk.heading or "Nội dung chính").strip()
        grouped.setdefault(heading, []).append(chunk)

    topics: list[KnowledgeTopic] = []
    for heading, rows in list(grouped.items())[:40]:
        ids = [str(row.id) for row in rows]
        facts: list[KnowledgeFact] = []
        for row in rows[:12]:
            compact = " ".join(row.content.split())
            if not compact:
                continue
            if len(compact) > 900:
                compact = compact[:897].rstrip() + "..."
            facts.append(KnowledgeFact(text=compact, source_chunk_ids=[str(row.id)]))
        summary = facts[0].text if facts else ""
        topics.append(
            KnowledgeTopic(
                title=heading,
                summary=summary,
                key_facts=facts,
                source_chunk_ids=ids,
            )
        )

    warnings = []
    if not topics:
        warnings.append("Không tìm thấy nội dung văn bản có thể lập bản đồ kiến thức.")
    return KnowledgeMap(
        lesson_focus=project_title,
        topics=topics,
        source_notes=[
            "Knowledge Map local giữ tối đa 40 nhóm nội dung, 12 đoạn nguồn mỗi nhóm và toàn bộ source_chunk_ids để ưu tiên độ phủ giáo án gốc."
        ],
        warnings=warnings,
    )
'''
s=s[:start]+new_km+"\n"
p.write_text(s)

p=root/"app/services/lesson_writer/local_writer.py"
s=p.read_text()
start=s.index("def _source_bullets(")
end=s.index("\ndef _visual_type(", start)
new_bullets='''def _source_bullets(rows: list[object], count: int = 4) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    for row in rows:
        raw = getattr(row, "content", "") or ""
        candidates = re.split(r"(?<=[.!?…])\\s+|\\n+", raw)
        for candidate in candidates:
            text = _compact(candidate, 210)
            if len(text) < 18:
                continue
            if text and not any(text == old[0] for old in output):
                output.append((text, str(row.id)))
            if len(output) >= count:
                return output
    return output

'''
s=s[:start]+new_bullets+s[end+1:]
p.write_text(s)

p=root/"app/services/pedagogy_planner/local_planner.py"
s=p.read_text()
s=s.replace(
    'slide_count_hint=max(1, min(4, (len(group) + 1) // 2)) if group else 1,',
    'slide_count_hint=max(1, min(8, len(group))) if group else 1,'
)
p.write_text(s)

print("content-grounding-patch-ok")


# 8) Secure project read/update/delete access.
p=root/"app/api/routes/projects.py"
s=p.read_text()
if "def _require_project_permission(" not in s:
    anchor='''def _project_or_404(project_id: UUID, db: Session) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
'''
    helper=anchor+'''

def _require_project_permission(project: Project, user: AppUser, db: Session, *, write: bool = False) -> None:
    if user.role == "admin" or project.user_id == user.id:
        return
    if project.organization_id:
        membership = organization_membership(db, project.organization_id, user.id)
        if membership and membership.status == "active" and membership.role in {"owner", "admin", "teacher"}:
            return
    raise HTTPException(status_code=403, detail="Project access denied")
'''
    if anchor not in s:
        raise RuntimeError("projects.py project helper anchor not found")
    s=s.replace(anchor,helper)

s=s.replace(
'''@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: UUID, db: Session = Depends(get_db)):
    project = _project_or_404(project_id, db)
''',
'''@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: UUID, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    project = _project_or_404(project_id, db)
    _require_project_permission(project, user, db)
'''
)
s=s.replace(
'''@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: UUID, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = _project_or_404(project_id, db)
''',
'''@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: UUID, payload: ProjectUpdate, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    project = _project_or_404(project_id, db)
    _require_project_permission(project, user, db, write=True)
'''
)
s=s.replace(
'''@router.delete("/{project_id}", response_model=Message)
def delete_project(project_id: UUID, db: Session = Depends(get_db)):
    project = _project_or_404(project_id, db)
''',
'''@router.delete("/{project_id}", response_model=Message)
def delete_project(project_id: UUID, user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    project = _project_or_404(project_id, db)
    _require_project_permission(project, user, db, write=True)
'''
)
p.write_text(s)

print("project-access-patch-ok")


# 9) Enforce plan source coverage after AI/local validation.
p=root/"app/services/pedagogy_planner/service.py"
s=p.read_text()
if "def _repair_plan_source_coverage(" not in s:
    marker='''def plan_project(
'''
    helper='''def _repair_plan_source_coverage(plan: PedagogyPlan, chunks: list[SourceChunk]) -> PedagogyPlan:
    """Guarantee that source chunks are not silently dropped before lesson writing."""
    ordered_ids = [str(chunk.id) for chunk in chunks]
    if not ordered_ids:
        return plan

    explore = [section for section in plan.sections if section.section_key in {"explore_1", "explore_2", "explore_3"}]
    if not explore:
        plan.warnings.append("Không thể tự sửa độ phủ nguồn vì thiếu các section Khám phá.")
        return plan

    used_before = {
        chunk_id
        for section in plan.sections
        for chunk_id in section.source_chunk_ids
        if chunk_id in set(ordered_ids)
    }
    before_pct = round(100 * len(used_before) / max(1, len(ordered_ids)))

    heading_by_id = {
        str(chunk.id): (getattr(chunk, "heading", None) or "").strip()
        for chunk in chunks
    }

    count = len(ordered_ids)
    for index, section in enumerate(explore[:3]):
        start = (count * index) // 3
        end = (count * (index + 1)) // 3
        assigned = ordered_ids[start:end]
        merged = list(dict.fromkeys([*section.source_chunk_ids, *assigned]))
        section.source_chunk_ids = merged

        headings = []
        for chunk_id in assigned:
            heading = heading_by_id.get(chunk_id, "")
            if heading and heading not in headings:
                headings.append(heading)
        section.topic_titles = list(dict.fromkeys([*section.topic_titles, *headings]))[:12]

        # Keep cognitive load manageable while allowing enough screens for the source.
        source_screen_hint = max(1, (len(assigned) + 1) // 2)
        section.slide_count_hint = min(12, max(section.slide_count_hint, source_screen_hint))

    used_after = {
        chunk_id
        for section in plan.sections
        for chunk_id in section.source_chunk_ids
        if chunk_id in set(ordered_ids)
    }
    after_pct = round(100 * len(used_after) / max(1, len(ordered_ids)))
    if after_pct < 100:
        missing = [chunk_id for chunk_id in ordered_ids if chunk_id not in used_after]
        target = explore[-1]
        target.source_chunk_ids = list(dict.fromkeys([*target.source_chunk_ids, *missing]))
        used_after.update(missing)
        after_pct = 100

    if before_pct < 95:
        plan.warnings.append(
            f"Độ phủ nguồn của Planner được tự sửa từ {before_pct}% lên {after_pct}% "
            f"({len(ordered_ids)} source chunks)."
        )
    return plan


'''
    if marker not in s:
        raise RuntimeError("planner service marker not found")
    s=s.replace(marker,helper+marker)

s=s.replace(
    '        plan = validate_and_repair_plan(raw_plan, project, valid_chunk_ids)\n        _persist_plan(db, project, plan, preserve_teacher_edits)',
    '        plan = validate_and_repair_plan(raw_plan, project, valid_chunk_ids)\n        plan = _repair_plan_source_coverage(plan, chunks)\n        _persist_plan(db, project, plan, preserve_teacher_edits)'
)
p.write_text(s)

print("planner-source-coverage-patch-ok")


# 10) Gate AI writer sections by source-reference coverage and fallback locally when sparse.
p=root/"app/services/lesson_writer/service.py"
s=p.read_text()
if "def _section_ref_coverage(" not in s:
    marker='''def _build_section(
'''
    helper='''def _section_ref_coverage(section: SectionDraft, section_plan: dict) -> float:
    permitted = set(section_plan.get("source_chunk_ids") or [])
    if not permitted:
        return 1.0
    used: set[str] = set()
    for slide in section.slides:
        used.update(
            ref.source_chunk_id for ref in slide.source_refs
            if ref.source_chunk_id in permitted
        )
        if slide.interaction:
            used.update(
                chunk_id for chunk_id in slide.interaction.source_chunk_ids
                if chunk_id in permitted
            )
    return len(used) / max(1, len(permitted))


'''
    if marker not in s:
        raise RuntimeError("lesson writer build-section marker not found")
    s=s.replace(marker,helper+marker)

old='''    rows = _section_chunks(section_plan, chunks_by_id)
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
'''
new='''    rows = _section_chunks(section_plan, chunks_by_id)
    valid_chunk_ids = set(chunks_by_id)
    key = section_plan.get("section_key")
    if use_ai and writer is not None:
        try:
            candidate = writer.build_section(
                project=project,
                section_plan=section_plan,
                objectives=objectives,
                chunks=rows,
                teacher_profile=teacher_profile,
            )
            from app.services.lesson_writer.v2 import enrich_section_v2
            candidate = enrich_section_v2(
                candidate,
                plan_section=section_plan,
                chunks_by_id=chunks_by_id,
                project=project,
            )
            candidate = validate_and_repair_section(
                candidate,
                plan_section=section_plan,
                valid_chunk_ids=valid_chunk_ids,
                source_policy=project.source_policy,
            )
            coverage = _section_ref_coverage(candidate, section_plan)
            if key in {"explore_1", "explore_2", "explore_3"} and section_plan.get("source_chunk_ids") and coverage < 0.90:
                raise DraftValidationError(
                    f"{key}: AI Writer chỉ bao phủ {round(coverage * 100)}% nguồn được giao; yêu cầu tối thiểu 90%."
                )
            if key in {"explore_1", "explore_2", "explore_3"}:
                candidate.warnings.append(f"{key}: source coverage {round(coverage * 100)}%.")
            return candidate
        except Exception as exc:
            if not fallback_to_local:
                raise
            local = build_local_section_draft(project, section_plan, chunks_by_id, objectives, teacher_profile)
            from app.services.lesson_writer.v2 import enrich_section_v2
            local = enrich_section_v2(
                local,
                plan_section=section_plan,
                chunks_by_id=chunks_by_id,
                project=project,
            )
            local = validate_and_repair_section(
                local,
                plan_section=section_plan,
                valid_chunk_ids=valid_chunk_ids,
                source_policy=project.source_policy,
            )
            local.warnings.append(
                f"AI Writer không đạt yêu cầu ở {key}; đã fallback local source-grounded: {exc}"
            )
            return local

    local = build_local_section_draft(project, section_plan, chunks_by_id, objectives, teacher_profile)
    from app.services.lesson_writer.v2 import enrich_section_v2
    local = enrich_section_v2(
        local,
        plan_section=section_plan,
        chunks_by_id=chunks_by_id,
        project=project,
    )
    return validate_and_repair_section(
        local,
        plan_section=section_plan,
        valid_chunk_ids=valid_chunk_ids,
        source_policy=project.source_policy,
    )
'''
if old not in s:
    raise RuntimeError("lesson writer section builder body not found")
s=s.replace(old,new)
p.write_text(s)

print("writer-source-coverage-gate-ok")


# 11) Preserve deterministic source order during planning and always expose coverage status.
p=root/"app/services/pedagogy_planner/service.py"
s=p.read_text()
s=s.replace(
    'chunks = list(db.scalars(select(SourceChunk).where(SourceChunk.project_id == project_id)))',
    'chunks = list(db.scalars(select(SourceChunk).where(SourceChunk.project_id == project_id).order_by(SourceChunk.source_file_id, SourceChunk.chunk_index)))'
)
old='''    if before_pct < 95:
        plan.warnings.append(
            f"Độ phủ nguồn của Planner được tự sửa từ {before_pct}% lên {after_pct}% "
            f"({len(ordered_ids)} source chunks)."
        )
    return plan
'''
new='''    if before_pct < 95:
        plan.warnings.append(
            f"Độ phủ nguồn của Planner được tự sửa từ {before_pct}% lên {after_pct}% "
            f"({len(ordered_ids)} source chunks)."
        )
    plan.warnings.append(
        f"Độ phủ nguồn sau kiểm tra: {after_pct}% ({len(ordered_ids)} source chunks đã được phân bổ vào kế hoạch)."
    )
    return plan
'''
if old in s:
    s=s.replace(old,new)
p.write_text(s)

print("planner-source-order-and-coverage-status-ok")


# 12) Report final generated-lesson source coverage.
p=root/"app/services/lesson_writer/service.py"
s=p.read_text()
if "def _draft_source_coverage(" not in s:
    marker='''def _persist_draft(
'''
    helper='''def _draft_source_coverage(draft: LessonDraft, plan: dict) -> tuple[float, int, int]:
    planned: set[str] = set()
    for section in plan.get("sections", []):
        if section.get("section_key") in {"explore_1", "explore_2", "explore_3"}:
            planned.update(section.get("source_chunk_ids") or [])
    if not planned:
        return 1.0, 0, 0

    used: set[str] = set()
    for slide in draft.slides:
        used.update(ref.source_chunk_id for ref in slide.source_refs if ref.source_chunk_id in planned)
        if slide.interaction:
            used.update(chunk_id for chunk_id in slide.interaction.source_chunk_ids if chunk_id in planned)
    return len(used) / len(planned), len(used), len(planned)


'''
    if marker not in s:
        raise RuntimeError("lesson writer persist marker not found")
    s=s.replace(marker,helper+marker)

old='''        lesson_draft = validate_and_repair_draft(
            lesson_draft,
            plan=plan,
            valid_chunk_ids=valid_chunk_ids,
            source_policy=project.source_policy,
        )
        slide_count, ref_count = _persist_draft(
'''
new='''        lesson_draft = validate_and_repair_draft(
            lesson_draft,
            plan=plan,
            valid_chunk_ids=valid_chunk_ids,
            source_policy=project.source_policy,
        )
        final_coverage, used_source_count, planned_source_count = _draft_source_coverage(lesson_draft, plan)
        lesson_draft.warnings.append(
            f"Độ phủ nguồn trong bài sinh: {round(final_coverage * 100)}% "
            f"({used_source_count}/{planned_source_count} source chunks thực sự được dùng)."
        )
        if project.source_policy == "strict" and planned_source_count and final_coverage < 0.90:
            raise DraftValidationError(
                f"Bài sinh chỉ bao phủ {round(final_coverage * 100)}% nguồn trọng tâm "
                f"({used_source_count}/{planned_source_count}); yêu cầu tối thiểu 90%."
            )
        slide_count, ref_count = _persist_draft(
'''
if old not in s:
    raise RuntimeError("lesson draft validation marker not found")
s=s.replace(old,new)
p.write_text(s)

print("generation-source-coverage-report-ok")


# 13) Centralize project authorization across authoring child routes.
access_path=root/"app/core/project_access.py"
access_path.write_text("""from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.authorization import organization_membership
from app.db.models import (
    AppUser,
    BackgroundJob,
    ExportRun,
    LessonObjective,
    LessonSection,
    LearnerAttempt,
    MediaAsset,
    Project,
    Slide,
    SourceChunk,
)


def require_project_access(
    db: Session,
    project_id: UUID,
    user: AppUser,
    *,
    write: bool = False,
) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role == "admin" or project.user_id == user.id:
        return project
    if project.organization_id:
        membership = organization_membership(db, project.organization_id, user.id)
        if (
            membership
            and membership.status == "active"
            and membership.role in {"owner", "admin", "teacher"}
        ):
            return project
    raise HTTPException(status_code=403, detail="Project access denied")


def _entity_access(db: Session, model, entity_id: UUID, user: AppUser, *, write: bool, detail: str):
    row = db.get(model, entity_id)
    if not row:
        raise HTTPException(status_code=404, detail=detail)
    require_project_access(db, row.project_id, user, write=write)
    return row


def require_section_access(db: Session, section_id: UUID, user: AppUser, *, write: bool = False):
    return _entity_access(db, LessonSection, section_id, user, write=write, detail="Section not found")


def require_slide_access(db: Session, slide_id: UUID, user: AppUser, *, write: bool = False):
    return _entity_access(db, Slide, slide_id, user, write=write, detail="Slide not found")


def require_objective_access(db: Session, objective_id: UUID, user: AppUser, *, write: bool = False):
    return _entity_access(db, LessonObjective, objective_id, user, write=write, detail="Objective not found")


def require_chunk_access(db: Session, chunk_id: UUID, user: AppUser, *, write: bool = False):
    return _entity_access(db, SourceChunk, chunk_id, user, write=write, detail="Source chunk not found")


def require_job_access(db: Session, job_id: UUID, user: AppUser, *, write: bool = False):
    return _entity_access(db, BackgroundJob, job_id, user, write=write, detail="Job not found")


def require_attempt_access(db: Session, attempt_id: UUID, user: AppUser, *, write: bool = False):
    return _entity_access(db, LearnerAttempt, attempt_id, user, write=write, detail="Attempt not found")


def require_export_access(db: Session, export_id: UUID, user: AppUser, *, write: bool = False):
    return _entity_access(db, ExportRun, export_id, user, write=write, detail="Export not found")


def require_media_access(db: Session, asset_id: UUID, user: AppUser, *, write: bool = False):
    return _entity_access(db, MediaAsset, asset_id, user, write=write, detail="Media asset not found")
""")

import ast as _ast
import re as _re

def _ensure_import_line(source: str, line: str) -> str:
    if line in source:
        return source
    future = _re.match(r"^(from __future__ import [^\n]+\n+)", source)
    pos = future.end() if future else 0
    return source[:pos] + line + "\n" + source[pos:]


def _route_specs(source: str):
    tree = _ast.parse(source)
    specs = []
    for node in tree.body:
        if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            if not isinstance(deco, _ast.Call) or not isinstance(deco.func, _ast.Attribute):
                continue
            method = deco.func.attr.lower()
            if method not in {"get", "post", "put", "patch", "delete"} or not deco.args:
                continue
            first = deco.args[0]
            if isinstance(first, _ast.Constant) and isinstance(first.value, str):
                specs.append((node.name, method, first.value))
                break
    return specs


def _add_user_and_guard(source: str, func_name: str, guard: str) -> str:
    match = _re.search(rf"(?m)^(?P<indent>[ \t]*)(?:async[ \t]+)?def[ \t]+{_re.escape(func_name)}[ \t]*\(", source)
    if not match:
        return source
    start = match.start()
    open_pos = source.find("(", match.start(), match.end() + 2)
    depth = 0
    close_pos = None
    for idx in range(open_pos, len(source)):
        ch = source[idx]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                close_pos = idx
                break
    if close_pos is None:
        raise RuntimeError(f"Cannot locate signature end for {func_name}")

    signature = source[start:close_pos + 1]
    if "user: AppUser = Depends(get_current_user)" not in signature:
        before = source[:close_pos].rstrip()
        separator = "" if before.endswith(("(", ",")) else ", "
        source = source[:close_pos] + separator + "user: AppUser = Depends(get_current_user)" + source[close_pos:]
        close_pos += len(separator) + len("user: AppUser = Depends(get_current_user)")

    # Re-locate the function after signature mutation and insert the guard as the first body statement.
    match = _re.search(rf"(?m)^(?P<indent>[ \t]*)(?:async[ \t]+)?def[ \t]+{_re.escape(func_name)}[ \t]*\(", source)
    open_pos = source.find("(", match.start(), match.end() + 2)
    depth = 0
    close_pos = None
    for idx in range(open_pos, len(source)):
        if source[idx] == "(":
            depth += 1
        elif source[idx] == ")":
            depth -= 1
            if depth == 0:
                close_pos = idx
                break
    colon_pos = source.find(":", close_pos)
    newline_pos = source.find("\n", colon_pos)
    if newline_pos < 0:
        raise RuntimeError(f"Cannot locate body for {func_name}")
    body_indent = match.group("indent") + "    "
    guard_line = body_indent + guard
    body_preview = source[newline_pos + 1:newline_pos + 1 + len(guard_line) + 4]
    if guard not in body_preview:
        source = source[:newline_pos + 1] + guard_line + "\n" + source[newline_pos + 1:]
    return source


def _secure_authoring_routes(rel_path: str) -> None:
    p = root / rel_path
    source = p.read_text()
    helpers = {
        "project_id": "require_project_access",
        "section_id": "require_section_access",
        "slide_id": "require_slide_access",
        "objective_id": "require_objective_access",
        "chunk_id": "require_chunk_access",
        "job_id": "require_job_access",
        "export_id": "require_export_access",
        "asset_id": "require_media_access",
    }
    specs = _route_specs(source)
    used_helpers = set()
    patches = []
    for func_name, method, route_path in specs:
        helper = var_name = None
        # Prefer the most specific entity id over project_id when both ever coexist.
        for candidate in ("section_id", "slide_id", "objective_id", "chunk_id", "job_id", "export_id", "asset_id", "project_id"):
            if "{" + candidate + "}" in route_path:
                var_name = candidate
                helper = helpers[candidate]
                break
        if not helper:
            continue
        write = method in {"post", "put", "patch", "delete"}
        if helper == "require_project_access":
            guard = f"{helper}(db, {var_name}, user, write={write})"
        else:
            guard = f"{helper}(db, {var_name}, user, write={write})"
        patches.append((func_name, guard))
        used_helpers.add(helper)

    if not patches:
        return
    source = _ensure_import_line(source, "from app.core.security import get_current_user")
    source = _ensure_import_line(source, "from app.db.models import AppUser")
    source = _ensure_import_line(
        source,
        "from app.core.project_access import " + ", ".join(sorted(used_helpers)),
    )
    for func_name, guard in patches:
        source = _add_user_and_guard(source, func_name, guard)
    p.write_text(source)


for _rel in [
    "app/api/routes/analysis.py",
    "app/api/routes/planning.py",
    "app/api/routes/generation.py",
    "app/api/routes/sections.py",
    "app/api/routes/slides.py",
    "app/api/routes/sources.py",
    "app/api/routes/jobs.py",
    "app/api/routes/interactions.py",
    "app/api/routes/copilot.py",
    "app/api/routes/exports.py",
]:
    _secure_authoring_routes(_rel)

print("project-child-route-security-patch-ok")


# 14) Protect teacher/admin LMS, LRS, Visual and analytics report routes.
def _secure_named_routes(rel_path: str, rules: list[tuple[str, str, str, bool]]) -> None:
    p = root / rel_path
    source = p.read_text()
    helper_names = sorted({helper for _, helper, _, _ in rules})
    source = _ensure_import_line(source, "from app.core.security import get_current_user")
    source = _ensure_import_line(source, "from app.db.models import AppUser")
    source = _ensure_import_line(
        source,
        "from app.core.project_access import " + ", ".join(helper_names),
    )
    for func_name, helper, var_name, write in rules:
        source = _add_user_and_guard(
            source,
            func_name,
            f"{helper}(db, {var_name}, user, write={write})",
        )
    p.write_text(source)


_secure_named_routes(
    "app/api/routes/lms.py",
    [
        ("get_lms_profile", "require_project_access", "project_id", False),
        ("upsert_lms_profile", "require_project_access", "project_id", True),
        ("xapi_template", "require_project_access", "project_id", False),
        ("validate_exported_scorm", "require_export_access", "export_id", False),
    ],
)

_secure_named_routes(
    "app/api/routes/lrs.py",
    [
        ("get_connection", "require_project_access", "project_id", False),
        ("save_connection", "require_project_access", "project_id", True),
        ("test_lrs", "require_project_access", "project_id", True),
        ("push_to_lrs", "require_attempt_access", "attempt_id", True),
        ("list_deliveries", "require_project_access", "project_id", False),
        ("sync_from_lrs", "require_project_access", "project_id", True),
    ],
)

_secure_named_routes(
    "app/api/routes/visual.py",
    [
        ("apply_project_theme", "require_project_access", "project_id", True),
        ("apply_slide_theme", "require_slide_access", "slide_id", True),
        ("apply_slide_layout", "require_slide_access", "slide_id", True),
        ("list_media", "require_project_access", "project_id", False),
        ("upload_media", "require_project_access", "project_id", True),
        ("media_from_prompt", "require_slide_access", "slide_id", True),
        ("attach_media", "require_slide_access", "slide_id", True),
        ("delete_media", "require_media_access", "asset_id", True),
        # media_content intentionally remains readable for lesson delivery.
    ],
)

_secure_named_routes(
    "app/api/routes/analytics.py",
    [
        ("analytics_summary", "require_project_access", "project_id", False),
        ("analytics_learners", "require_project_access", "project_id", False),
        ("analytics_objectives", "require_project_access", "project_id", False),
        ("analytics_attempts", "require_project_access", "project_id", False),
        ("analytics_attempt_detail", "require_attempt_access", "attempt_id", False),
        # Tracking POST endpoints intentionally remain on the learner/SCORM path.
    ],
)

print("teacher-tool-route-security-patch-ok")


# 15) Raise source upload limit for large PPTX/DOCX files used in real lesson plans.
p=root/"app/core/config.py"
s=p.read_text()
s=s.replace("max_upload_mb: int = 50", "max_upload_mb: int = 100")
p.write_text(s)

p=root/"app/services/storage.py"
s=p.read_text()
s=s.replace(
    'raise ValueError(f"File exceeds {settings.max_upload_mb} MB limit")',
    'raise ValueError(f"Tệp vượt quá giới hạn {settings.max_upload_mb} MB")'
)
p.write_text(s)

print("large-source-upload-limit-ok")


# 16) Video lesson storyboard and strict content crosswalk.
video_service = root / "app/services/video_lesson.py"
video_service.write_text(r'''from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Slide, SlideSourceRef, SourceChunk
from app.services.export_engine.assembler import assemble_deck


def _source_dict(source) -> dict[str, Any]:
    return {
        "file_name": source.file_name,
        "heading": source.heading,
        "page_start": source.page_start,
        "page_end": source.page_end,
        "claim_text": source.claim_text,
        "content_excerpt": source.content_excerpt,
    }


def _scene_role(slide_type: str, section_title: str) -> str:
    value = (slide_type or "").lower()
    title = (section_title or "").lower()
    if value in {"title", "warmup"} or "khởi động" in title:
        return "Mở đầu/khởi động"
    if value in {"interaction", "practice"}:
        return "Hoạt động/nhiệm vụ học tập"
    if value == "application":
        return "Vận dụng"
    if value in {"summary", "closing"}:
        return "Củng cố/kết thúc"
    if value == "objectives":
        return "Mục tiêu bài học"
    return "Hình thành kiến thức"


def _split_items(items: list[str], duration: int) -> list[list[str]]:
    clean = [str(x).strip() for x in items if str(x).strip()]
    if len(clean) <= 3 or duration < 35:
        return [clean]
    cut = max(2, (len(clean) + 1) // 2)
    return [clean[:cut], clean[cut:]]


def build_video_storyboard(db: Session, project_id: UUID) -> dict[str, Any]:
    deck = assemble_deck(db, project_id, only_approved=False)
    if not deck.slides:
        raise ValueError("Project has no slides to build video storyboard")

    all_chunk_ids = {
        str(x) for x in db.scalars(
            select(SourceChunk.id).where(SourceChunk.project_id == project_id)
        )
    }
    used_chunk_ids = {
        str(x) for x in db.scalars(
            select(SlideSourceRef.source_chunk_id)
            .join(Slide, SlideSourceRef.slide_id == Slide.id)
            .where(Slide.project_id == project_id)
        )
    }
    covered = used_chunk_ids & all_chunk_ids
    coverage_pct = round(100 * len(covered) / max(1, len(all_chunk_ids))) if all_chunk_ids else 100
    missing = sorted(all_chunk_ids - used_chunk_ids)

    scenes: list[dict[str, Any]] = []
    slide_scene_ids: dict[str, list[str]] = defaultdict(list)
    for slide in sorted(deck.slides, key=lambda x: x.order):
        duration = max(8, int(slide.duration_seconds or 15))
        groups = _split_items(slide.onscreen_text, duration)
        per_scene = max(8, round(duration / max(1, len(groups))))
        interaction_question = slide.interactions[0].question if slide.interactions else None
        question = slide.guiding_question or interaction_question
        for part_index, items in enumerate(groups, start=1):
            scene_id = f"s{slide.order:03d}-{part_index}"
            slide_scene_ids[slide.id].append(scene_id)
            narration = (slide.teacher_script or "").strip() if part_index == 1 else ""
            if not narration:
                if question and part_index == len(groups):
                    narration = question
                elif slide.student_instruction:
                    narration = slide.student_instruction
                else:
                    narration = " ".join(items)
            scene = {
                "scene_id": scene_id,
                "scene_number": len(scenes) + 1,
                "source_slide_id": slide.id,
                "source_slide_order": slide.order,
                "section_title": slide.section_title,
                "scene_role": _scene_role(slide.slide_type, slide.section_title),
                "title": slide.title,
                "onscreen_text": items,
                "visual": {
                    "layout": slide.layout_key,
                    "theme": slide.theme_key,
                    "media": [
                        {
                            "asset_id": media.asset_id,
                            "asset_type": media.asset_type,
                            "role": media.role,
                            "original_name": media.original_name,
                        }
                        for media in slide.media
                    ],
                },
                "narration": narration,
                "student_activity": slide.student_instruction,
                "question": question if part_index == len(groups) else None,
                "pause_after_question_seconds": 4 if question and part_index == len(groups) else 0,
                "duration_seconds": per_scene + (4 if question and part_index == len(groups) else 0),
                "transition": "smooth",
                "sources": [_source_dict(x) for x in slide.sources],
                "source_verified": bool(slide.sources) or slide.slide_type in {"title", "objectives", "references"},
            }
            scenes.append(scene)

    crosswalk: list[dict[str, Any]] = []
    for slide in sorted(deck.slides, key=lambda x: x.order):
        scene_ids = slide_scene_ids.get(slide.id, [])
        crosswalk.append({
            "kind": "Tiêu đề",
            "content": slide.title,
            "source_slide_order": slide.order,
            "scene_ids": scene_ids,
            "kept": True,
        })
        if slide.student_instruction:
            crosswalk.append({
                "kind": "Nhiệm vụ học tập",
                "content": slide.student_instruction,
                "source_slide_order": slide.order,
                "scene_ids": scene_ids,
                "kept": True,
            })
        if slide.guiding_question:
            crosswalk.append({
                "kind": "Câu hỏi",
                "content": slide.guiding_question,
                "source_slide_order": slide.order,
                "scene_ids": scene_ids,
                "kept": True,
            })
        for source in slide.sources:
            crosswalk.append({
                "kind": "Kiến thức nguồn",
                "content": source.claim_text or source.content_excerpt or source.heading or source.file_name,
                "source_document": source.file_name,
                "heading": source.heading,
                "page_start": source.page_start,
                "page_end": source.page_end,
                "source_slide_order": slide.order,
                "scene_ids": scene_ids,
                "kept": True,
            })
        if slide.slide_type in {"summary", "closing"}:
            crosswalk.append({
                "kind": "Kết luận",
                "content": " ".join(slide.onscreen_text),
                "source_slide_order": slide.order,
                "scene_ids": scene_ids,
                "kept": True,
            })

    warnings: list[str] = []
    if coverage_pct < 100:
        warnings.append(
            f"Video chưa được phép render: độ phủ nguồn {coverage_pct}%, còn thiếu {len(missing)} source chunks."
        )
    scenes_without_source = [
        x["scene_id"] for x in scenes
        if not x["source_verified"] and x["scene_role"] in {"Hình thành kiến thức", "Hoạt động/nhiệm vụ học tập", "Vận dụng"}
    ]
    if scenes_without_source:
        warnings.append(
            "Các cảnh kiến thức chưa có dẫn chiếu nguồn: " + ", ".join(scenes_without_source[:20])
        )

    ready = coverage_pct == 100 and not scenes_without_source
    return {
        "project_id": str(project_id),
        "title": deck.title,
        "language": "vi-VN",
        "audience": "THCS" if (deck.education_level or "").upper() == "THCS" else deck.education_level,
        "video_spec": {
            "aspect_ratio": "16:9",
            "width": 1920,
            "height": 1080,
            "container": "mp4",
            "quality": "high",
            "voice": "Vietnamese teacher",
            "background_music": "light, non-distracting, licensed/royalty-free only",
        },
        "source_coverage_pct": coverage_pct,
        "source_chunk_count": len(all_chunk_ids),
        "used_source_chunk_count": len(covered),
        "missing_source_chunk_ids": missing,
        "slide_count": len(deck.slides),
        "scene_count": len(scenes),
        "estimated_duration_seconds": sum(int(x["duration_seconds"]) for x in scenes),
        "content_crosswalk": crosswalk,
        "scenes": scenes,
        "quality_checks": {
            "all_source_content_covered": coverage_pct == 100,
            "slide_order_preserved": True,
            "all_slides_mapped_to_scenes": len(slide_scene_ids) == len(deck.slides),
            "questions_have_pause": all(
                (not x.get("question")) or int(x.get("pause_after_question_seconds") or 0) >= 3
                for x in scenes
            ),
            "source_verified_learning_scenes": not scenes_without_source,
        },
        "ready_for_render": ready,
        "warnings": warnings,
    }
''')

p = root / "app/api/routes/exports.py"
s = p.read_text()
if "video/storyboard" not in s:
    s = s.replace(
        "from app.services.export_engine.service import execute_export",
        "from app.services.export_engine.service import execute_export\nfrom app.services.video_lesson import build_video_storyboard",
    )
    marker = '@router.post("/projects/{project_id}/exports"'
    endpoint = '''@router.get("/projects/{project_id}/video/storyboard")
def video_storyboard(project_id: UUID, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    require_project_access(db, project_id, user, write=False)
    try:
        return build_video_storyboard(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


'''
    if marker not in s:
        raise RuntimeError("exports route insertion marker not found")
    s = s.replace(marker, endpoint + marker)
p.write_text(s)

print("video-storyboard-and-crosswalk-ok")
