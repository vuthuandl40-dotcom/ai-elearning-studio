#!/usr/bin/env bash
set -euo pipefail

API="${API:-http://127.0.0.1:8000/api/v1}"
COOKIE="/tmp/elearning-e2e-cookie.txt"
PROJECT_ID=$(cat /tmp/e2e-project-id)

curl -fsS -c "$COOKIE" -b "$COOKIE" "$API/projects/$PROJECT_ID/slides" >/tmp/e2e-video-slides.json
python - <<'PY'
import json
from collections import Counter
slides=json.load(open("/tmp/e2e-video-slides.json"))
layouts=[str(s.get("layout_hint") or "") for s in slides if s.get("layout_hint")]
counts=Counter(layouts)
assert len(counts)>=8, f"slide layouts are too repetitive: {counts}"
dominant=max(counts.values())/max(1,len(layouts))
assert dominant<=0.35, f"one slide layout dominates {dominant:.0%}: {counts}"
print("e2e-slide-diversity-ok",len(counts),"layouts","dominant",round(dominant,3))
PY

curl -fsS -c "$COOKIE" -b "$COOKIE" "$API/projects/$PROJECT_ID/video/storyboard" >/tmp/e2e-video-storyboard.json
python - <<'PY'
import json
d=json.load(open("/tmp/e2e-video-storyboard.json"))
assert d["source_coverage_pct"]==100, d.get("warnings")
assert d["ready_for_render"] is True, d.get("warnings")
assert d["slide_count"]>=15
assert d["scene_count"]>=d["slide_count"]
assert d["content_crosswalk"], "empty content crosswalk"
checks=d.get("quality_checks") or {}
assert all(checks.values()), checks
print("e2e-video-storyboard-ok",d["slide_count"],d["scene_count"],len(d["content_crosswalk"]))
PY

payload='{"format":"mp4","include_notes":true,"include_sources":true,"include_quiz":true,"only_approved":false,"voice_enabled":false,"require_full_source_coverage":true,"scene_limit":2}'
video_http=$(curl -sS -o /tmp/e2e-video-export.json -w '%{http_code}' -c "$COOKIE" -b "$COOKIE" -H 'Content-Type: application/json' -d "$payload" "$API/projects/$PROJECT_ID/exports")
if [ "$video_http" != "201" ]; then
  echo "mp4-export-http=$video_http"
  cat /tmp/e2e-video-export.json
  exit 1
fi
video_export=$(cat /tmp/e2e-video-export.json)
VIDEO_EXPORT_ID=$(python - <<'PY'
import json
d=json.load(open("/tmp/e2e-video-export.json"))
assert d["status"]=="completed", d
assert d["mime_type"]=="video/mp4", d
assert d["file_name"].endswith("_Video_Bai_Giang.mp4"), d
print(d["id"])
PY
)

curl -fsS -c "$COOKIE" -b "$COOKIE" "$API/exports/$VIDEO_EXPORT_ID/download" -o /tmp/e2e-video.mp4
python - <<'PY'
from pathlib import Path
p=Path("/tmp/e2e-video.mp4")
assert p.exists() and p.stat().st_size>100000
assert b"ftyp" in p.read_bytes()[:64]
print("e2e-mp4-download-ok",p.stat().st_size)
PY

command -v ffprobe >/dev/null 2>&1
VIDEO_DIM=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 /tmp/e2e-video.mp4)
VIDEO_AUDIO=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=nw=1:nk=1 /tmp/e2e-video.mp4 | head -n1)
test "$VIDEO_DIM" = "1920x1080"
test -n "$VIDEO_AUDIO"
echo "e2e-mp4-fullhd-ok $VIDEO_DIM audio=$VIDEO_AUDIO"

curl -fsS -c "$COOKIE" -b "$COOKIE" -X DELETE "$API/projects/$PROJECT_ID" >/tmp/e2e-delete.json
echo "e2e-video-pipeline-ok"
