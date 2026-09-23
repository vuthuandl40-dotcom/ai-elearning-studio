#!/usr/bin/env bash
set -euo pipefail

API="${API:-http://127.0.0.1:8000/api/v1}"
COOKIE="/tmp/large-pptx-cookie.txt"
PPTX="/tmp/large-lesson.pptx"
TEST_VARIANT="${TEST_VARIANT:-direct}"
EMAIL="large-pptx-${TEST_VARIANT}-${GITHUB_RUN_ID:-local}@example.com"
PASSWORD="LargePptxPass123!"

python - <<'PY'
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches
import zipfile

pptx=Path("/tmp/large-lesson.pptx")
blob=Path("/tmp/large-payload.bin")

prs=Presentation()
for idx,(title,body) in enumerate([
    ("BÀI 1. KINH TUYẾN VĨ TUYẾN - TỌA ĐỘ ĐỊA LÍ","Kinh tuyến là nửa đường tròn nối hai cực. Vĩ tuyến là vòng tròn vuông góc với kinh tuyến."),
    ("KINH TUYẾN GỐC","Kinh tuyến gốc đi qua đài thiên văn Greenwich và được quy ước là 0 độ."),
    ("VĨ TUYẾN GỐC","Xích đạo là vĩ tuyến gốc 0 độ, chia Trái Đất thành bán cầu Bắc và bán cầu Nam."),
    ("TỌA ĐỘ ĐỊA LÍ","Tọa độ địa lí của một điểm được xác định bằng kinh độ và vĩ độ của điểm đó."),
], start=1):
    slide=prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text=title
    slide.placeholders[1].text=body
prs.save(pptx)

with blob.open("wb") as fh:
    fh.truncate(70 * 1024 * 1024)
with zipfile.ZipFile(pptx,"a",compression=zipfile.ZIP_STORED,allowZip64=True) as zf:
    zf.write(blob,"ppt/media/large-unreferenced-payload.bin",compress_type=zipfile.ZIP_STORED)
blob.unlink()

size=pptx.stat().st_size
assert size > 50*1024*1024, size
assert size < 100*1024*1024, size
print("large-pptx-created", round(size/1024/1024,1), "MB")
PY

register_payload=$(printf '{"email":"%s","password":"%s","display_name":"Large PPTX Teacher","role":"teacher"}' "$EMAIL" "$PASSWORD")
curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d "$register_payload" "$API/auth/register" >/tmp/large-pptx-register.json

project_json=$(curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d '{"title":"Large PPTX E2E","subject":"Địa lí","grade":"6","education_level":"THCS","duration_minutes":45,"source_policy":"strict","interaction_level":"medium"}' "$API/projects")
PROJECT_ID=$(printf '%s' "$project_json" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

upload_json=$(curl --fail-with-body -sS -c "$COOKIE" -b "$COOKIE" -F "file=@$PPTX;type=application/vnd.openxmlformats-officedocument.presentationml.presentation" "$API/projects/$PROJECT_ID/files")
printf '%s' "$upload_json" >/tmp/large-pptx-upload.json
python - <<'PY'
import json
d=json.load(open("/tmp/large-pptx-upload.json"))
assert d.get("original_name")=="large-lesson.pptx", d
assert (d.get("size_bytes") or 0) > 50*1024*1024, d
print("large-pptx-upload-ok", round(d["size_bytes"]/1024/1024,1), "MB")
PY

job=$(curl -fsS -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d '{"kind":"analyze","payload":{"use_ai":false,"create_embeddings":false,"vision_fallback":false},"max_attempts":1}' "$API/projects/$PROJECT_ID/jobs")
JOB_ID=$(printf '%s' "$job" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')

for _ in $(seq 1 120); do
  body=$(curl -fsS -c "$COOKIE" -b "$COOKIE" "$API/jobs/$JOB_ID")
  status=$(printf '%s' "$body" | python -c 'import json,sys; print(json.load(sys.stdin)["status"])')
  if [ "$status" = "completed" ]; then break; fi
  if [ "$status" = "failed" ] || [ "$status" = "cancelled" ]; then echo "$body"; exit 1; fi
  sleep 1
done
[ "$status" = "completed" ]

curl -fsS -c "$COOKIE" -b "$COOKIE" "$API/projects/$PROJECT_ID/analysis/latest" >/tmp/large-pptx-analysis.json
python - <<'PY'
import json
d=json.load(open("/tmp/large-pptx-analysis.json"))
km=d.get("knowledge_map") or {}
raw=json.dumps(km,ensure_ascii=False).lower()
for phrase in ["kinh tuyến","vĩ tuyến","tọa độ"]:
    assert phrase in raw, f"missing PPTX source phrase: {phrase}"
topics=km.get("topics") or []
assert topics, "PPTX produced no knowledge topics"
print("large-pptx-analysis-ok", len(topics), "topics")
PY

curl -fsS -c "$COOKIE" -b "$COOKIE" -X DELETE "$API/projects/$PROJECT_ID" >/tmp/large-pptx-delete.json
rm -f "$PPTX" "$COOKIE"
echo "large-pptx-pipeline-ok"
