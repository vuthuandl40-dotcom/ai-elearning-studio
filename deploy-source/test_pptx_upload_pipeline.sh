#!/usr/bin/env bash
set -euo pipefail

API="${E2E_API_URL:-http://127.0.0.1:8000/api/v1}"
COOKIE="/tmp/pptx-upload-cookie.txt"
PPTX="/tmp/pptx-upload-source.pptx"
EMAIL="pptx-upload-${GITHUB_RUN_ID:-local}@example.com"
PASSWORD="PptxUploadE2E123!"

python - <<'PY'
from pptx import Presentation
from pptx.util import Inches

path="/tmp/pptx-upload-source.pptx"
prs=Presentation()
slide=prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text="QUANG HỢP Ở THỰC VẬT"
slide.placeholders[1].text="Cây xanh sử dụng ánh sáng, nước và khí carbon dioxide để tạo chất hữu cơ và giải phóng oxygen."
slide=prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text="VAI TRÒ CỦA DIỆP LỤC"
slide.placeholders[1].text="Diệp lục hấp thụ năng lượng ánh sáng. Quang hợp giúp tích lũy năng lượng hóa học trong chất hữu cơ."
slide=prs.slides.add_slide(prs.slide_layouts[5])
slide.shapes.title.text="THÍ NGHIỆM"
box=slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(2))
box.text_frame.text="Quan sát lá cây trước và sau khi được chiếu sáng để liên hệ điều kiện ánh sáng với quá trình quang hợp."
prs.save(path)
print(path)
PY

register_payload=$(printf '{"email":"%s","password":"%s","display_name":"PPTX Upload E2E","role":"teacher"}' "$EMAIL" "$PASSWORD")
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d "$register_payload" "$API/auth/register" >/tmp/pptx-upload-register.json

project_json=$(curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d '{"title":"E2E Upload PPTX","subject":"Khoa học","grade":"6","education_level":"THCS","duration_minutes":35,"source_policy":"strict","interaction_level":"medium"}' "$API/projects")
PROJECT_ID=$(printf '%s' "$project_json" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

upload_json=$(curl -fsS -c "$COOKIE" -b "$COOKIE" -F "file=@$PPTX;type=application/vnd.openxmlformats-officedocument.presentationml.presentation" "$API/projects/$PROJECT_ID/files")
printf '%s' "$upload_json" >/tmp/pptx-upload.json
python - <<'PY'
import json
d=json.load(open("/tmp/pptx-upload.json"))
assert str(d.get("file_name") or d.get("original_name") or "").lower().endswith(".pptx"), d
print("pptx-upload-api-ok", d.get("file_name") or d.get("original_name"))
PY

analyze=$(curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d '{"kind":"analyze","payload":{"use_ai":false,"create_embeddings":false,"vision_fallback":false},"max_attempts":1}' "$API/projects/$PROJECT_ID/jobs")
JOB_ID=$(printf '%s' "$analyze" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

for _ in $(seq 1 120); do
  body=$(curl -fsS -c "$COOKIE" -b "$COOKIE" "$API/jobs/$JOB_ID")
  status=$(printf '%s' "$body" | python -c 'import json,sys; print(json.load(sys.stdin)["status"])')
  if [ "$status" = "completed" ]; then break; fi
  if [ "$status" = "failed" ] || [ "$status" = "cancelled" ]; then echo "$body"; exit 1; fi
  sleep 1
done

curl -fsS -c "$COOKIE" -b "$COOKIE" "$API/projects/$PROJECT_ID/analysis/latest" >/tmp/pptx-upload-analysis.json
python - <<'PY'
import json
d=json.load(open("/tmp/pptx-upload-analysis.json"))
km=d.get("knowledge_map") or {}
raw=json.dumps(km,ensure_ascii=False).lower()
required=["quang hợp","diệp lục","ánh sáng"]
missing=[x for x in required if x not in raw]
assert not missing, f"PPTX content was not extracted into Knowledge Map; missing={missing}; map={raw[:2500]}"
topics=km.get("topics") or []
assert topics, "PPTX analysis returned no topics"
print("pptx-upload-analysis-ok", len(topics), required)
PY

curl -fsS -c "$COOKIE" -b "$COOKIE" -X DELETE "$API/projects/$PROJECT_ID" >/tmp/pptx-upload-delete.json
echo "pptx-upload-pipeline-ok"
