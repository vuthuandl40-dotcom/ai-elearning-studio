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
