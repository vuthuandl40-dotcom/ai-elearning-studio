from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

repo=Path.cwd()
target=Path("/tmp/ai-elearning-ui-src")
if target.exists():
    shutil.rmtree(target)
target.mkdir(parents=True)

archive=repo/"source.tar.xz"
if not archive.exists():
    raise SystemExit("source.tar.xz not found; reconstruct source first")

subprocess.run(["tar","-xJf",str(archive),"-C",str(target)],check=True)
for rel in [
    "deploy-source/patches/0001-lesson-editor-null-project.patch",
    "deploy-source/patches/0002-safe-response-error-body.patch",
    "deploy-source/patches/0004-editable-objectives.patch",
    "deploy-source/patches/0005b-section-regeneration-frontend.patch",
    "deploy-source/patches/0007-learner-interaction-ui.patch",
]:
    with open(repo/rel,"rb") as fh:
        subprocess.run(["patch","-d",str(target),"-p1"],stdin=fh,check=True)

subprocess.run(["node",str(repo/"deploy-source/ui_v2_patch.mjs"),str(target)],check=True)
subprocess.run(["python",str(repo/"deploy-source/test_ui_completeness.py")],cwd=target,check=True)
print("v2-ui-regression-runner-ok")
