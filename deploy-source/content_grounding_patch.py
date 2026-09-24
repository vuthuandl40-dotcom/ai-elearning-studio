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
        from app.services.lesson_writer.v2 import rebalance_lesson_layouts
        lesson_draft = rebalance_lesson_layouts(lesson_draft)
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


# 17) Full-HD MP4 video export renderer with source gate and Vietnamese neural narration.
p=root/"requirements.txt"
s=p.read_text()
if "edge-tts" not in s:
    s += "\nedge-tts>=7.2\n"
p.write_text(s)

p=root/"app/schemas/export.py"
s=p.read_text()
s=s.replace(
    'ExportFormat = Literal["pptx", "pdf", "html5", "scorm12", "scorm2004"]',
    'ExportFormat = Literal["pptx", "pdf", "html5", "scorm12", "scorm2004", "mp4"]',
)
if "voice_enabled:" not in s:
    s=s.replace(
        "    only_approved: bool = False\n",
        '    only_approved: bool = False\n    voice_enabled: bool = True\n    voice_name: str = "vi-VN-HoaiMyNeural"\n    voice_rate: str = "+0%"\n    require_full_source_coverage: bool = True\n    scene_limit: int | None = Field(default=None, ge=1, le=20)\n'
    )
p.write_text(s)

video_renderer=root/"app/services/export_engine/video_renderer.py"
video_renderer.write_text(r'''from __future__ import annotations

import asyncio
import math
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.services.export_engine.assembler import assemble_deck
from app.services.video_lesson import build_video_storyboard

WIDTH=1920
HEIGHT=1080
FPS=30
BG=(245,247,252)
INK=(15,23,42)
MUTED=(71,85,105)
INDIGO=(79,70,229)
VIOLET=(124,58,237)
EMERALD=(5,150,105)
BORDER=(224,231,255)


def _run(args:list[str]) -> None:
    proc=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if proc.returncode:
        raise RuntimeError((proc.stderr or proc.stdout or "ffmpeg failed")[-5000:])


def _font(size:int,bold:bool=False):
    names=[
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name,size=size)
    return ImageFont.load_default()


def _wrap(text:str,font,max_width:int)->list[str]:
    words=(text or "").split()
    if not words:
        return []
    lines=[]
    current=""
    for word in words:
        candidate=(current+" "+word).strip()
        box=font.getbbox(candidate)
        if box[2]-box[0] <= max_width or not current:
            current=candidate
        else:
            lines.append(current);current=word
    if current:
        lines.append(current)
    return lines


def _rounded(draw,xy,radius,fill,outline=None,width=1):
    draw.rounded_rectangle(xy,radius=radius,fill=fill,outline=outline,width=width)


def _draw_lines(draw,lines,x,y,font,fill,line_gap=12,max_lines=None):
    if max_lines:
        lines=lines[:max_lines]
    cy=y
    for line in lines:
        draw.text((x,cy),line,font=font,fill=fill)
        cy += font.size + line_gap
    return cy


def _load_visual(path:Path|None,box:tuple[int,int,int,int])->Image.Image|None:
    if not path or not path.exists():
        return None
    try:
        if path.suffix.lower() in {".png",".jpg",".jpeg",".webp",".bmp"}:
            im=Image.open(path).convert("RGB")
            return ImageOps.fit(im,(box[2]-box[0],box[3]-box[1]),method=Image.Resampling.LANCZOS)
    except Exception:
        return None
    return None


def _draw_header(draw,title,section,scene_no):
    draw.text((72,52),section.upper(),font=_font(23,True),fill=INDIGO)
    title_lines=_wrap(title,_font(48,True),1180)
    _draw_lines(draw,title_lines,72,95,_font(48,True),INK,10,2)
    _rounded(draw,(1650,54,1848,112),20,(238,242,255))
    draw.text((1690,70),f"CẢNH {scene_no}",font=_font(20,True),fill=INDIGO)


def _draw_footer(draw,source_verified:bool,layout:str):
    draw.line((72,1010,1848,1010),fill=(226,232,240),width=2)
    draw.text((72,1028),"AI E-Learning Studio · Video bài giảng",font=_font(18),fill=(100,116,139))
    status="✓ Đã đối chiếu nguồn" if source_verified else "• Cảnh chuyển tiếp"
    draw.text((1460,1028),status,font=_font(18,True),fill=EMERALD if source_verified else MUTED)


def _render_scene_frame(scene:dict[str,Any],media_path:Path|None,target:Path)->None:
    img=Image.new("RGB",(WIDTH,HEIGHT),BG)
    draw=ImageDraw.Draw(img)
    layout=str(scene.get("visual",{}).get("layout") or "center-focus")
    _draw_header(draw,scene.get("title") or "",scene.get("scene_role") or "",scene.get("scene_number") or 0)
    items=[str(x) for x in scene.get("onscreen_text") or []]
    question=str(scene.get("question") or "").strip()
    visual=_load_visual(media_path,(1000,230,1810,880))

    if layout in {"cinematic-hero","question-spotlight","scenario-stage","center-focus"}:
        _rounded(draw,(72,245,1848,900),36,(255,255,255),BORDER,2)
        if visual:
            img.paste(visual,(1000,245))
            text_width=820
        else:
            text_width=1580
        y=315
        for idx,item in enumerate(items[:4]):
            _rounded(draw,(120,y-10,120+text_width,y+105),22,(248,250,255))
            draw.text((145,y+10),str(idx+1).zfill(2),font=_font(22,True),fill=VIOLET)
            lines=_wrap(item,_font(30,True if idx==0 else False),text_width-100)
            _draw_lines(draw,lines,205,y+5,_font(30,True if idx==0 else False),INK,8,2)
            y+=135
    elif layout in {"comparison-2-column","evidence-board","milestone-checklist","takeaway-cards"}:
        cols=2
        cards=items[:4] or [scene.get("title") or ""]
        cw=820;ch=245
        for i,item in enumerate(cards):
            col=i%cols;row=i//cols
            x=100+col*870;y=250+row*285
            _rounded(draw,(x,y,x+cw,y+ch),28,(255,255,255),BORDER,2)
            draw.text((x+30,y+26),str(i+1),font=_font(28,True),fill=INDIGO)
            lines=_wrap(item,_font(29,True if i<2 else False),cw-100)
            _draw_lines(draw,lines,x+82,y+22,_font(29,True if i<2 else False),INK,9,5)
    elif layout in {"process-timeline","cause-effect","sequence-workspace"}:
        steps=items[:5] or [scene.get("title") or ""]
        n=max(1,len(steps));gap=28;available=1700-(n-1)*gap;cw=max(240,available//n)
        y=400
        for i,item in enumerate(steps):
            x=110+i*(cw+gap)
            _rounded(draw,(x,y,x+cw,y+300),28,(255,255,255),BORDER,2)
            _rounded(draw,(x+24,y-38,x+86,y+24),22,INDIGO)
            draw.text((x+45,y-27),str(i+1),font=_font(22,True),fill=(255,255,255))
            lines=_wrap(item,_font(25),cw-54)
            _draw_lines(draw,lines,x+28,y+55,_font(25),INK,8,7)
            if i<n-1:
                draw.line((x+cw,y+150,x+cw+gap,y+150),fill=VIOLET,width=6)
    elif layout in {"annotated-visual","split-visual-explain","zoom-detail","text-left-visual-right","visual-left-text-right","full-bleed-annotated"}:
        left_visual=layout in {"annotated-visual","split-visual-explain","visual-left-text-right","full-bleed-annotated"}
        visual_box=(85,240,955,900) if left_visual else (965,240,1835,900)
        text_box=(990,240,1835,900) if left_visual else (85,240,930,900)
        _rounded(draw,visual_box,30,(229,231,255),BORDER,2)
        if visual:
            fitted=_load_visual(media_path,visual_box)
            if fitted:
                img.paste(fitted,(visual_box[0],visual_box[1]))
        else:
            cx=(visual_box[0]+visual_box[2])//2;cy=(visual_box[1]+visual_box[3])//2
            draw.ellipse((cx-115,cy-115,cx+115,cy+115),fill=(224,231,255))
            draw.text((cx-58,cy-35),"VISUAL",font=_font(28,True),fill=INDIGO)
        y=text_box[1]+20
        for i,item in enumerate(items[:5]):
            _rounded(draw,(text_box[0],y,text_box[2],y+105),18,(255,255,255),BORDER,1)
            draw.text((text_box[0]+24,y+18),"•",font=_font(30,True),fill=VIOLET)
            lines=_wrap(item,_font(27),text_box[2]-text_box[0]-90)
            _draw_lines(draw,lines,text_box[0]+60,y+16,_font(27),INK,8,3)
            y+=122
    elif layout in {"concept-map","matching-workspace","activity-board","quiz-card","fill-blank-focus","evidence-choice","real-world-scenario"}:
        center_x=960;center_y=505
        _rounded(draw,(690,410,1230,600),35,(238,242,255),INDIGO,3)
        center_lines=_wrap(scene.get("title") or "",_font(31,True),470)
        _draw_lines(draw,center_lines,735,455,_font(31,True),INK,8,3)
        cards=items[:4]
        anchors=[(110,270),(1290,270),(110,690),(1290,690)]
        for i,item in enumerate(cards):
            x,y=anchors[i]
            _rounded(draw,(x,y,x+520,y+210),25,(255,255,255),BORDER,2)
            lines=_wrap(item,_font(25),460)
            _draw_lines(draw,lines,x+30,y+35,_font(25),INK,8,5)
            draw.line((x+260 if x<900 else x,y+105,center_x,center_y),fill=(196,181,253),width=4)
    else:
        _rounded(draw,(90,245,1830,900),30,(255,255,255),BORDER,2)
        y=310
        for item in items[:6]:
            lines=_wrap(item,_font(32),1580)
            y=_draw_lines(draw,lines,150,y,_font(32),INK,10,3)+24

    if question:
        _rounded(draw,(155,905,1765,985),22,(245,243,255),(196,181,253),2)
        qlines=_wrap("? "+question,_font(23,True),1510)
        _draw_lines(draw,qlines,190,925,_font(23,True),VIOLET,6,2)
    _draw_footer(draw,bool(scene.get("source_verified")),layout)
    img.save(target,quality=95)


def _probe_duration(path:Path)->float:
    proc=subprocess.run([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",str(path)
    ],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    if proc.returncode:
        return 0.0
    try:return float(proc.stdout.strip())
    except Exception:return 0.0


async def _tts(text:str,target:Path,voice_name:str,rate:str)->None:
    import edge_tts
    communicate=edge_tts.Communicate(text=text,voice=voice_name,rate=rate)
    await communicate.save(str(target))


def _create_audio(text:str,target:Path,voice_name:str,rate:str)->None:
    if not text.strip():
        text="Tiếp tục bài học."
    try:
        asyncio.run(_tts(text,target,voice_name,rate))
    except Exception as exc:
        raise RuntimeError(f"Không tạo được giọng đọc tiếng Việt ({voice_name}): {exc}") from exc
    if not target.exists() or target.stat().st_size < 1000:
        raise RuntimeError("Dịch vụ giọng đọc trả về tệp âm thanh rỗng.")


def render_mp4(
    db,
    project_id,
    target:Path,
    *,
    voice_enabled:bool=True,
    voice_name:str="vi-VN-HoaiMyNeural",
    voice_rate:str="+0%",
    require_full_source_coverage:bool=True,
    scene_limit:int|None=None,
)->list[str]:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("Máy chủ chưa có ffmpeg/ffprobe để xuất MP4.")

    storyboard=build_video_storyboard(db,project_id)
    if require_full_source_coverage and not storyboard["ready_for_render"]:
        raise RuntimeError(
            "Chưa thể xuất video: bài giảng chưa đạt kiểm tra đối chiếu nguồn 100%. "
            + " ".join(storyboard.get("warnings") or [])
        )
    deck=assemble_deck(db,project_id,only_approved=False)
    slide_media={slide.id:[m for m in slide.media if m.path] for slide in deck.slides}

    work=target.parent/"video_work"
    if work.exists():shutil.rmtree(work)
    work.mkdir(parents=True,exist_ok=True)
    clips=[]
    warnings=[]
    scenes = storyboard["scenes"][:scene_limit] if scene_limit else storyboard["scenes"]
    for scene in scenes:
        idx=int(scene["scene_number"])
        frame=work/f"scene-{idx:03d}.png"
        audio=work/f"scene-{idx:03d}.mp3"
        clip=work/f"scene-{idx:03d}.mp4"
        media_list=slide_media.get(str(scene["source_slide_id"]),[])
        media_path=media_list[0].path if media_list else None
        _render_scene_frame(scene,media_path,frame)

        narration=str(scene.get("narration") or "").strip()
        if voice_enabled:
            _create_audio(narration,audio,voice_name,voice_rate)
            audio_duration=_probe_duration(audio)
            duration=max(float(scene.get("duration_seconds") or 8),audio_duration+float(scene.get("pause_after_question_seconds") or 0)+0.5)
            audio_args=["-i",str(audio)]
            audio_map=["-map","1:a:0","-af",f"apad=pad_dur={max(1.0,duration-audio_duration):.2f}"]
        else:
            duration=max(5.0,float(scene.get("duration_seconds") or 8))
            audio_args=["-f","lavfi","-i","anullsrc=channel_layout=stereo:sample_rate=44100"]
            audio_map=["-map","1:a:0"]

        frames=max(1,math.ceil(duration*FPS))
        vf=(
            f"scale={WIDTH}:{HEIGHT},"
            f"zoompan=z='min(zoom+0.00018,1.025)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS},format=yuv420p"
        )
        cmd=[
            "ffmpeg","-y","-loop","1","-i",str(frame),*audio_args,
            "-filter:v",vf,"-map","0:v:0",*audio_map,
            "-t",f"{duration:.3f}","-r",str(FPS),
            "-c:v","libx264","-preset","veryfast","-crf","20",
            "-c:a","aac","-b:a","160k","-ar","44100","-ac","2",
            "-movflags","+faststart",str(clip)
        ]
        _run(cmd)
        clips.append(clip)

    concat=work/"concat.txt"
    concat.write_text("\n".join("file '"+str(x.resolve()).replace("'","'\\''")+"'" for x in clips)+"\n")
    _run([
        "ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),
        "-c:v","libx264","-preset","medium","-crf","19",
        "-c:a","aac","-b:a","160k","-movflags","+faststart",str(target)
    ])
    if not target.exists() or target.stat().st_size < 10000:
        raise RuntimeError("MP4 renderer không tạo được tệp video hợp lệ.")
    if not voice_enabled:
        warnings.append("MP4 được render ở chế độ kiểm thử không TTS; production mặc định bật giọng đọc tiếng Việt.")
    if storyboard.get("warnings"):
        warnings.extend(storyboard["warnings"])
    shutil.rmtree(work,ignore_errors=True)
    return warnings
''')

p=root/"app/services/export_engine/service.py"
s=p.read_text()
if "video_renderer import render_mp4" not in s:
    s=s.replace(
        "from app.services.export_engine.pptx_renderer import render_pptx",
        "from app.services.export_engine.pptx_renderer import render_pptx\nfrom app.services.export_engine.video_renderer import render_mp4",
    )
if 'elif run.format == "mp4":' not in s:
    marker='''        elif run.format == "html5":
'''
    branch='''        elif run.format == "mp4":
            safe_video_stem = re.sub(r'[\\/:*?"<>|]+', "_", deck.title).strip(" ._") or "Bai_Giang"
            target = out_dir / f"{safe_video_stem}_Video_Bai_Giang.mp4"
            options = run.options or {}
            warnings.extend(render_mp4(
                db,
                run.project_id,
                target,
                voice_enabled=bool(options.get("voice_enabled", True)),
                voice_name=str(options.get("voice_name") or "vi-VN-HoaiMyNeural"),
                voice_rate=str(options.get("voice_rate") or "+0%"),
                require_full_source_coverage=bool(options.get("require_full_source_coverage", True)),
                scene_limit=int(options["scene_limit"]) if options.get("scene_limit") else None,
            ))
            mime = "video/mp4"
'''
    if marker not in s:raise RuntimeError("html5 export marker missing")
    s=s.replace(marker,branch+marker)
p.write_text(s)

print("fullhd-mp4-export-renderer-ok")


# 18) Register V2 semantic layouts in the editor visual catalog.
# Without this, ensureDesign() silently falls back to the first legacy layout
# even when lesson_writer.v2 produced a distinct layout_hint.
p=root/"app/services/visual_catalog.py"
s=p.read_text()
if "_V2_SEMANTIC_LAYOUTS" not in s:
    s += r'''

# V2 semantic eLearning layouts. Keep element names compatible with SlideStage:
# title, body, visual, question, overlay.
_V2_SEMANTIC_LAYOUTS = [
    {"key":"cinematic-hero","name":"Mở bài điện ảnh","description":"Visual toàn cảnh + tiêu đề lớn.","elements":{"visual":[0,0,100,100],"overlay":[0,0,100,100],"title":[8,18,70,25],"body":[8,48,55,24],"question":[8,79,70,11]}},
    {"key":"milestone-checklist","name":"Mục tiêu theo cột mốc","description":"Mục tiêu lớn, nội dung dạng checklist.","elements":{"title":[8,10,84,14],"body":[10,29,80,50],"question":[10,83,80,9]}},
    {"key":"question-spotlight","name":"Câu hỏi trung tâm","description":"Câu hỏi gợi mở là trọng tâm thị giác.","elements":{"title":[12,12,76,12],"visual":[8,29,34,46],"question":[47,28,45,33],"body":[47,64,45,21]}},
    {"key":"scenario-stage","name":"Sân khấu tình huống","description":"Tình huống trực quan + nhiệm vụ học tập.","elements":{"title":[7,9,86,12],"visual":[7,25,55,58],"body":[66,27,27,36],"question":[66,67,27,16]}},
    {"key":"quiz-card","name":"Thẻ câu hỏi","description":"Câu hỏi và lựa chọn nổi bật.","elements":{"title":[10,9,80,12],"question":[13,25,74,22],"body":[18,51,64,31]}},
    {"key":"fill-blank-focus","name":"Điền khuyết","description":"Khoảng trống/câu hỏi ở giữa, gợi ý phía dưới.","elements":{"title":[10,9,80,12],"body":[16,26,68,23],"question":[12,55,76,27]}},
    {"key":"evidence-choice","name":"Chọn bằng chứng","description":"Bằng chứng trực quan + câu hỏi lựa chọn.","elements":{"title":[7,9,86,12],"visual":[7,25,43,52],"body":[54,25,39,30],"question":[54,59,39,18]}},
    {"key":"real-world-scenario","name":"Vận dụng thực tế","description":"Tình huống thực tế và quyết định.","elements":{"visual":[0,0,48,100],"title":[53,12,40,15],"body":[53,32,40,31],"question":[53,68,40,19]}},
    {"key":"concept-map","name":"Sơ đồ khái niệm","description":"Trọng tâm khái niệm, nhánh kiến thức xung quanh.","elements":{"title":[20,7,60,12],"visual":[22,24,56,43],"body":[12,70,76,16],"question":[25,88,50,7]}},
    {"key":"takeaway-cards","name":"Thẻ ghi nhớ","description":"Tóm tắt bằng cụm thẻ kiến thức.","elements":{"title":[8,9,84,13],"body":[8,28,84,52],"question":[18,84,64,9]}},
    {"key":"source-list","name":"Danh mục nguồn","description":"Nguồn tham chiếu rõ ràng, dễ kiểm tra.","elements":{"title":[8,9,84,12],"body":[10,27,80,59]}},
    {"key":"activity-board","name":"Bảng luyện tập","description":"Nhiệm vụ luyện tập theo vùng làm việc.","elements":{"title":[7,8,86,12],"body":[7,25,58,56],"visual":[69,25,24,35],"question":[69,64,24,17]}},
    {"key":"matching-workspace","name":"Không gian nối cặp","description":"Hai vùng ghép/nối trực quan.","elements":{"title":[8,8,84,12],"body":[8,27,39,53],"visual":[53,27,39,53],"question":[20,84,60,8]}},
    {"key":"sequence-workspace","name":"Sắp xếp trình tự","description":"Nội dung theo chuỗi bước ngang.","elements":{"title":[8,8,84,12],"body":[8,27,84,25],"visual":[8,57,84,24],"question":[20,85,60,8]}},
    {"key":"comparison-2-column","name":"So sánh hai cột","description":"Hai phía cân bằng để đối chiếu.","elements":{"title":[8,8,84,12],"body":[7,27,41,51],"visual":[52,27,41,51],"question":[17,83,66,9]}},
    {"key":"evidence-board","name":"Bảng bằng chứng","description":"Nội dung chính + bằng chứng trực quan.","elements":{"title":[7,8,86,12],"visual":[7,25,30,56],"body":[41,25,52,41],"question":[41,70,52,11]}},
    {"key":"split-visual-explain","name":"Hình và giải thích","description":"Visual lớn bên trái, giải thích bên phải.","elements":{"visual":[0,0,48,100],"title":[53,10,40,14],"body":[53,30,40,43],"question":[53,78,40,12]}},
    {"key":"chart-focus","name":"Biểu đồ trọng tâm","description":"Biểu đồ lớn với vùng nhận xét.","elements":{"title":[8,7,84,12],"visual":[8,23,60,58],"body":[72,24,20,38],"question":[72,66,20,15]}},
    {"key":"data-table","name":"Bảng số liệu","description":"Bảng/dữ liệu chiếm vùng chính.","elements":{"title":[8,7,84,12],"visual":[7,23,86,45],"body":[8,72,54,17],"question":[66,72,27,17]}},
    {"key":"process-timeline","name":"Dòng quy trình","description":"Các bước trải dài theo trục thời gian.","elements":{"title":[8,8,84,12],"visual":[8,28,84,28],"body":[12,61,76,18],"question":[20,83,60,9]}},
    {"key":"cause-effect","name":"Nguyên nhân – kết quả","description":"Hai vùng liên kết nhân quả.","elements":{"title":[8,8,84,12],"body":[7,28,38,45],"visual":[55,28,38,45],"question":[20,80,60,11]}},
    {"key":"map-focus","name":"Bản đồ trọng tâm","description":"Bản đồ/lược đồ chiếm phần lớn màn hình.","elements":{"title":[7,7,86,11],"visual":[5,22,67,67],"body":[75,23,20,37],"question":[75,64,20,24]}},
    {"key":"annotated-visual","name":"Hình chú giải","description":"Visual lớn kèm nội dung chú giải.","elements":{"visual":[4,9,58,82],"title":[66,10,29,16],"body":[66,31,29,39],"question":[66,75,29,15]}},
    {"key":"zoom-detail","name":"Phóng to chi tiết","description":"Chi tiết trực quan lớn + giải thích ngắn.","elements":{"title":[7,7,86,12],"visual":[19,22,62,50],"body":[10,76,80,12],"question":[25,90,50,6]}},
    {"key":"full-bleed-annotated","name":"Ảnh toàn màn hình","description":"Visual phủ màn hình với lớp chữ chú thích.","elements":{"visual":[0,0,100,100],"overlay":[0,0,100,100],"title":[6,8,54,14],"body":[6,58,45,25],"question":[55,73,39,14]}},
    {"key":"visual-left-text-right","name":"Hình trái – chữ phải","description":"Visual trái, nội dung phải.","elements":{"visual":[5,17,44,68],"title":[54,12,40,15],"body":[54,32,40,42],"question":[54,79,40,11]}},
    {"key":"text-left-visual-right","name":"Chữ trái – hình phải","description":"Nội dung trái, visual phải.","elements":{"title":[6,10,46,14],"body":[6,30,44,46],"visual":[55,17,40,63],"question":[6,81,89,10]}},
    {"key":"center-focus","name":"Trọng tâm trung tâm","description":"Một trọng tâm thị giác ở giữa.","elements":{"title":[14,8,72,13],"visual":[24,25,52,39],"body":[16,68,68,16],"question":[24,87,52,7]}},
]

_v2_existing_layout_keys = {item["key"] for item in LAYOUTS}
LAYOUTS.extend(item for item in _V2_SEMANTIC_LAYOUTS if item["key"] not in _v2_existing_layout_keys)
'''
p.write_text(s)

print("v2-semantic-visual-catalog-ok")


# 19) Normalize local/OpenAI writer layout hints to exact semantic catalog keys.
p=root/"app/services/lesson_writer/local_writer.py"
s=p.read_text()
s=s.replace(
    'layout_hint="hero-title: tiêu đề lớn, ít chữ, visual chiếm 60–70% khung hình"',
    'layout_hint="cinematic-hero"'
)
s=s.replace(
    'layout_hint="checklist 2 cột, tối đa 6 ý"',
    'layout_hint="milestone-checklist"'
)
s=s.replace(
    'layout_hint="reference-list"',
    'layout_hint="source-list"'
)
s=s.replace(
    'layout_hint="visual-left/text-right" if slide_type in {"content", "explore"} else "single-focus"',
    'layout_hint="annotated-visual" if slide_type in {"content", "explore"} else "quiz-card"'
)
p.write_text(s)

p=root/"app/services/lesson_writer/openai_client.py"
s=p.read_text()
if "LAYOUT DIVERSITY RULES" not in s:
    marker="16. Do not output citations as prose. Put traceability only in source_refs / interaction.source_chunk_ids."
    addition="""16. Do not output citations as prose. Put traceability only in source_refs / interaction.source_chunk_ids.
17. LAYOUT DIVERSITY RULES: layout_hint must be an exact key from this list:
    cinematic-hero, milestone-checklist, question-spotlight, scenario-stage,
    quiz-card, fill-blank-focus, evidence-choice, real-world-scenario,
    concept-map, takeaway-cards, source-list, activity-board,
    matching-workspace, sequence-workspace, comparison-2-column,
    evidence-board, split-visual-explain, chart-focus, data-table,
    process-timeline, cause-effect, map-focus, annotated-visual,
    zoom-detail, full-bleed-annotated, visual-left-text-right,
    text-left-visual-right, center-focus.
18. Do not use the same layout on more than two consecutive slides. Prefer a visibly different composition when the learning action changes.
19. Use map-focus ONLY when the screen actually asks learners to read/locate/identify/discuss a map, atlas or spatial distribution. Words such as longitude, latitude or coordinates by themselves do not justify a map layout.
20. Use data-table for data tables; chart-focus for charts; cause-effect for causes/results; comparison-2-column for comparison; process-timeline for processes/sequences; annotated-visual or zoom-detail for image/feature observation."""
    if marker in s:
        s=s.replace(marker,addition)
p.write_text(s)

print("writer-semantic-layout-hints-ok")
