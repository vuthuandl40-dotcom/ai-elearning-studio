#!/usr/bin/env bash
set -euo pipefail

API="http://127.0.0.1:8000/api/v1"
COOKIE="/tmp/elearning-e2e-cookie.txt"
DOCX="/tmp/elearning-e2e-lesson.docx"
EMAIL="teacher-${GITHUB_RUN_ID:-local}@example.com"
PASSWORD="E2eStrongPass123!"

python - <<'PY'
from docx import Document

path="/tmp/elearning-e2e-lesson.docx"
doc=Document()
doc.add_heading("BÀI: VÒNG TUẦN HOÀN CỦA NƯỚC", level=1)
doc.add_paragraph("Mục tiêu: Học sinh mô tả được quá trình bay hơi, ngưng tụ và mưa trong vòng tuần hoàn của nước.")
doc.add_heading("Khởi động", level=2)
doc.add_paragraph("Giáo viên cho học sinh quan sát cốc nước có thành cốc đọng giọt nước và đặt câu hỏi về nguồn gốc các giọt nước.")
table=doc.add_table(rows=5, cols=2)
table.cell(0,0).text="Hoạt động của giáo viên"
table.cell(0,1).text="Hoạt động của học sinh"
table.cell(1,0).text="Cho học sinh quan sát nước được làm nóng và nhận biết hơi nước bay lên."
table.cell(1,1).text="Học sinh quan sát và kết luận nước lỏng có thể bay hơi thành hơi nước."
table.cell(2,0).text="Đặt một bề mặt lạnh phía trên hơi nước để quan sát các giọt nước hình thành."
table.cell(2,1).text="Học sinh nhận xét hơi nước gặp lạnh ngưng tụ thành các giọt nước."
table.cell(3,0).text="Yêu cầu học sinh liên hệ sự hình thành mây và mưa trong tự nhiên."
table.cell(3,1).text="Học sinh giải thích nước bốc hơi, ngưng tụ thành mây và rơi xuống thành mưa."
table.cell(4,0).text="Tổ chức cho học sinh vẽ sơ đồ vòng tuần hoàn của nước."
table.cell(4,1).text="Học sinh vẽ mũi tên thể hiện bay hơi, ngưng tụ, mưa và nước trở về sông hồ."
doc.add_heading("Kết luận", level=2)
doc.add_paragraph("Vòng tuần hoàn của nước gồm quá trình bay hơi, ngưng tụ, mưa và sự tập trung nước trở lại ở sông, hồ, biển.")
doc.add_heading("Luyện tập", level=2)
doc.add_paragraph("Học sinh ghép các hiện tượng bay hơi, ngưng tụ và mưa với mô tả phù hợp, sau đó giải thích bằng lời của mình.")
doc.save(path)
print(path)
PY

register_payload=$(printf '{"email":"%s","password":"%s","display_name":"E2E Teacher","role":"teacher"}' "$EMAIL" "$PASSWORD")
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d "$register_payload" "$API/auth/register" >/tmp/e2e-register.json

project_json=$(curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d '{"title":"E2E Vòng tuần hoàn của nước","subject":"Khoa học","grade":"5","education_level":"Tiểu học","duration_minutes":40,"source_policy":"strict","interaction_level":"medium"}' "$API/projects")
PROJECT_ID=$(printf '%s' "$project_json" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -fsS -c "$COOKIE" -b "$COOKIE" -F "file=@$DOCX" "$API/projects/$PROJECT_ID/files" >/tmp/e2e-upload.json

job_id() {
  printf '%s' "$1" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])'
}

wait_job() {
  local id="$1"
  for _ in $(seq 1 120); do
    local body status
    body=$(curl -fsS -c "$COOKIE" -b "$COOKIE" "$API/jobs/$id")
    status=$(printf '%s' "$body" | python -c 'import json,sys; print(json.load(sys.stdin)["status"])')
    if [ "$status" = "completed" ]; then
      return 0
    fi
    if [ "$status" = "failed" ] || [ "$status" = "cancelled" ]; then
      echo "$body"
      return 1
    fi
    sleep 1
  done
  echo "job timeout: $id"
  return 1
}

analyze=$(curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d '{"kind":"analyze","payload":{"use_ai":false,"create_embeddings":false,"vision_fallback":false},"max_attempts":1}' "$API/projects/$PROJECT_ID/jobs")
wait_job "$(job_id "$analyze")"

curl -fsS -c "$COOKIE" -b "$COOKIE" "$API/projects/$PROJECT_ID/analysis/latest" >/tmp/e2e-analysis.json
python - <<'PY'
import json
d=json.load(open("/tmp/e2e-analysis.json"))
km=d.get("knowledge_map") or {}
topics=km.get("topics") or []
assert len(topics)>=3, f"too few knowledge topics: {len(topics)}"
raw=json.dumps(km, ensure_ascii=False).lower()
for word in ["bay hơi","ngưng tụ","mưa"]:
    assert word in raw, f"source knowledge missing: {word}"
print("e2e-analysis-source-ok", len(topics))
PY

plan=$(curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d '{"kind":"plan","payload":{"use_ai":false,"preserve_teacher_edits":false},"max_attempts":1}' "$API/projects/$PROJECT_ID/jobs")
wait_job "$(job_id "$plan")"

curl -fsS -c "$COOKIE" -b "$COOKIE" "$API/projects/$PROJECT_ID/plan/latest" >/tmp/e2e-plan.json
PLAN_ID=$(python -c 'import json; print(json.load(open("/tmp/e2e-plan.json"))["id"])')
python - <<'PY'
import json,re
d=json.load(open("/tmp/e2e-plan.json"))
warnings=[str(x) for x in d.get("warnings") or []]
line=next((x for x in warnings if "Độ phủ nguồn sau kiểm tra" in x), "")
assert line, warnings
m=re.search(r"(\d+)%", line)
assert m and int(m.group(1))>=95, line
sections=(d.get("plan_json") or {}).get("sections") or []
explore=[s for s in sections if s.get("section_key") in {"explore_1","explore_2","explore_3"}]
assert len(explore)==3
assert all(s.get("source_chunk_ids") for s in explore)
print("e2e-plan-coverage-ok", line)
PY

curl -fsS -c "$COOKIE" -b "$COOKIE" -X POST "$API/projects/$PROJECT_ID/plan/$PLAN_ID/approve" >/tmp/e2e-approve.json

generate=$(curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d '{"kind":"generate","payload":{"use_ai":false,"preserve_teacher_edits":false,"fallback_to_local":true},"max_attempts":1}' "$API/projects/$PROJECT_ID/jobs")
wait_job "$(job_id "$generate")"

curl -fsS -c "$COOKIE" -b "$COOKIE" "$API/projects/$PROJECT_ID/slides" >/tmp/e2e-slides.json
python - <<'PY'
import json
slides=json.load(open("/tmp/e2e-slides.json"))
assert len(slides)>=15, f"too few slides: {len(slides)}"
text=" ".join(
    [str(s.get("title") or "")+" "+" ".join(map(str,s.get("onscreen_text") or []))+" "+str(s.get("teacher_script") or "") for s in slides]
).lower()
hits=sum(word in text for word in ["bay hơi","ngưng tụ","mưa"])
assert hits>=2, f"generated lesson lost source concepts; hits={hits}"
nonempty=sum(bool((s.get("onscreen_text") or []) or (s.get("teacher_script") or "").strip()) for s in slides)
assert nonempty>=12, f"too many empty slides: {nonempty}/{len(slides)}"
print("e2e-generate-source-grounding-ok", len(slides), hits, nonempty)
PY

curl -fsS -c "$COOKIE" -b "$COOKIE" -X DELETE "$API/projects/$PROJECT_ID" >/tmp/e2e-delete.json
echo "e2e-lesson-plan-pipeline-ok"
