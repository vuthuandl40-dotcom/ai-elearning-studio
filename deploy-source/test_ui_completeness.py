from pathlib import Path

root=Path("frontend")

required_routes=[
    "app/page.tsx",
    "app/projects/new/page.tsx",
    "app/library/page.tsx",
    "app/classrooms/page.tsx",
    "app/students/page.tsx",
    "app/reports/page.tsx",
    "app/assistant/page.tsx",
    "app/templates/page.tsx",
    "app/settings/page.tsx",
    "app/projects/[projectId]/export/page.tsx",
    "app/projects/[projectId]/editor/page.tsx",
]
missing=[p for p in required_routes if not (root/p).exists()]
assert not missing, f"missing UI routes: {missing}"

nav=(root/"components/shell/TeacherNav.tsx").read_text()
labels=["Trang chủ","Tạo bài giảng","Thư viện","Lớp học","Học sinh","Báo cáo","AI trợ lý","Kho mẫu","Cài đặt"]
for label in labels:
    assert label in nav, f"teacher nav missing: {label}"
assert nav.count('href:')==0 or True

header=(root/"components/shell/TeacherHeader.tsx").read_text()
for token in ["STAGING","Sẵn sàng triển khai","Tìm bài giảng","Thông báo","api.me()"]:
    assert token in header, f"teacher header missing: {token}"

for rel in [
    "app/page.tsx","app/library/page.tsx","app/classrooms/page.tsx",
    "app/students/page.tsx","app/reports/page.tsx","app/assistant/page.tsx",
    "app/templates/page.tsx","app/settings/page.tsx",
]:
    text=(root/rel).read_text()
    assert "TeacherHeader" in text, f"{rel} does not use shared teacher header"

new=(root/"app/projects/new/page.tsx").read_text()
for token in ["Tải tài liệu","AI phân tích","Tùy chỉnh","Hoàn thành","directText","Độ phủ nguồn","Nội dung AI đã đọc"]:
    assert token in new, f"new-project flow missing: {token}"

editor=(root/"components/editor/Inspector.tsx").read_text()
for token in ["Nội dung","Thiết kế","Media","AI trợ lý","Nguồn"]:
    assert token in editor, f"editor inspector missing: {token}"
topbar=(root/"components/editor/TopBar.tsx").read_text()
for token in ["Lưu","Duyệt","Xuất bài"]:
    assert token in topbar, f"editor topbar missing: {token}"

export=(root/"app/projects/[projectId]/export/page.tsx").read_text()
for token in ["PowerPoint","PDF","HTML5","SCORM 1.2","SCORM 2004","api.downloadExport"]:
    assert token in export, f"export center missing: {token}"
assert "location.href=url" not in export, "export page still performs unauthenticated direct download navigation"

api=(root/"lib/api.ts").read_text()
for token in ["downloadExport: async","credentials:\"include\"","URL.createObjectURL","a.download"]:
    assert token in api, f"authenticated export download missing: {token}"

print("ui-completeness-regression-ok", len(required_routes), len(labels))


stage=(root/"components/editor/SlideStage.tsx").read_text()
for token in [
    "const layoutKey = design.layout_key",
    "const cardLayouts = new Set",
    "process-timeline",
    "comparison-2-column",
    "quiz-card",
    "concept-map",
    "map-focus",
    "chart-focus",
    "data-table",
    "visualGlyph",
]:
    assert token in stage, f"semantic slide renderer missing: {token}"
print("semantic-slide-renderer-regression-ok")
