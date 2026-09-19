from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

API = os.environ.get("E2E_API_URL", "http://127.0.0.1:8000/api/v1")
run_id = os.environ.get("GITHUB_RUN_ID", "local-security")
password = "ProjectAccessE2E123!"


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
            "email": f"{label}-{run_id}@example.com",
            "password": password,
            "display_name": f"E2E {label}",
            "role": "teacher",
        },
    )
    assert status in {200, 201}, (label, status, body)

status, project = call(
    owner,
    "POST",
    "/projects",
    {
        "title": "Security ownership E2E",
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

status, sections = call(owner, "GET", f"/projects/{project_id}/sections")
assert status == 200 and sections, (status, sections)
section_id = sections[0]["id"]

status, job = call(
    owner,
    "POST",
    f"/projects/{project_id}/jobs",
    {"kind": "analyze", "payload": {"use_ai": False}, "max_attempts": 1},
)
assert status == 200, (status, job)
job_id = job["id"]

checks = [
    ("GET", f"/projects/{project_id}", None),
    ("GET", f"/projects/{project_id}/sections", None),
    ("GET", f"/projects/{project_id}/files", None),
    ("GET", f"/projects/{project_id}/chunks", None),
    ("GET", f"/projects/{project_id}/analysis/latest", None),
    ("GET", f"/projects/{project_id}/plan/latest", None),
    ("GET", f"/projects/{project_id}/generation/latest", None),
    ("GET", f"/projects/{project_id}/jobs", None),
    ("POST", f"/projects/{project_id}/jobs", {"kind": "analyze", "payload": {}, "max_attempts": 1}),
    ("GET", f"/jobs/{job_id}", None),
    ("POST", f"/jobs/{job_id}/cancel", None),
    ("GET", f"/projects/{project_id}/exports", None),
    ("PATCH", f"/sections/{section_id}", {}),
]
for method, path, payload in checks:
    status, body = call(intruder, method, path, payload)
    assert status == 403, (method, path, status, body)

# Owner retains normal access after security hardening.
for path in [
    f"/projects/{project_id}",
    f"/projects/{project_id}/sections",
    f"/projects/{project_id}/jobs",
]:
    status, body = call(owner, "GET", path)
    assert status == 200, (path, status, body)

status, body = call(owner, "DELETE", f"/projects/{project_id}")
assert status == 200, (status, body)

print("project-access-e2e-ok", len(checks), "cross-user checks blocked")
