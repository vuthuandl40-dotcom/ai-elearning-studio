from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

API = os.environ.get("E2E_API_URL", "http://127.0.0.1:8000/api/v1")
run_id = os.environ.get("GITHUB_RUN_ID", "local-teacher-tools")
password = "TeacherToolsE2E123!"


def client():
    jar = CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(opener, method: str, path: str, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with opener.open(req, timeout=20) as res:
            body = res.read().decode("utf-8")
            return res.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else None
        except Exception:
            parsed = body
        return exc.code, parsed


owner = client()
intruder = client()
for opener, label in [(owner, "owner"), (intruder, "intruder")]:
    status, body = call(
        opener,
        "POST",
        "/auth/register",
        {
            "email": f"teacher-tools-{label}-{run_id}@example.com",
            "password": password,
            "display_name": f"Teacher tools {label}",
            "role": "teacher",
        },
    )
    assert status in {200, 201}, (label, status, body)

status, project = call(
    owner,
    "POST",
    "/projects",
    {
        "title": "Teacher tools security E2E",
        "subject": "Khoa học",
        "grade": "5",
        "education_level": "Tiểu học",
        "duration_minutes": 35,
        "source_policy": "strict",
        "interaction_level": "medium",
    },
)
assert status == 201, (status, project)
project_id = project["id"]

checks = [
    ("GET", f"/projects/{project_id}/lms/profile", None),
    ("GET", f"/projects/{project_id}/xapi/template", None),
    ("GET", f"/projects/{project_id}/lrs/connection", None),
    ("POST", f"/projects/{project_id}/lrs/test", None),
    ("GET", f"/projects/{project_id}/lrs/deliveries", None),
    ("POST", f"/projects/{project_id}/lrs/sync", None),
    ("GET", f"/projects/{project_id}/media", None),
    ("POST", f"/projects/{project_id}/visual/theme", {"theme_key": "default"}),
    ("GET", f"/projects/{project_id}/analytics/summary", None),
    ("GET", f"/projects/{project_id}/analytics/learners", None),
    ("GET", f"/projects/{project_id}/analytics/objectives", None),
    ("GET", f"/projects/{project_id}/analytics/attempts", None),
]
for method, path, payload in checks:
    status, body = call(intruder, method, path, payload)
    assert status == 403, (method, path, status, body)

status, body = call(owner, "GET", f"/projects/{project_id}/lms/profile")
assert status == 200, (status, body)
status, body = call(owner, "GET", f"/projects/{project_id}/lrs/connection")
assert status == 200, (status, body)
status, body = call(owner, "GET", f"/projects/{project_id}/media")
assert status == 200, (status, body)

status, body = call(owner, "DELETE", f"/projects/{project_id}")
assert status == 200, (status, body)

print("teacher-tool-access-e2e-ok", len(checks), "cross-user checks blocked")
