# SPDX-License-Identifier: MIT
"""Rewrite version strings across tracked files for a release bump.

Usage:
    python scripts/bump-version.py 0.1.0 0.1.1

- Skips CHANGELOG.md and RELEASING.md (historical release references stay pinned).
- Refuses to run when any of the five version-carrying files has drifted off OLD.
- Walks tracked files ending in .md / .py / .js / .mdc / .json / .toml.
- Applies a small set of exact-match replacements: `vX.Y.Z`, `"X.Y.Z"`,
  `agent-style@X.Y.Z`, `// X.Y.Z`, and `EXPECTED_VERSION = "X.Y.Z"`.
"""

import os
import subprocess
import sys

if len(sys.argv) != 3:
    sys.exit("usage: bump-version.py <old> <new>")

OLD, NEW = sys.argv[1], sys.argv[2]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTS = (".md", ".py", ".js", ".mdc", ".json", ".toml")
# Both files narrate past releases by version number, so a blanket rewrite
# would falsify the record. RELEASING.md recounts which release fix-forwarded a
# packaging bug and which registry artifact still carries it; those sentences
# have to keep naming the release it happened in. Neither file holds a version
# string that a bump is supposed to advance. (Do not put a literal version in
# this comment: the script rewrites its own source too.)
SKIP = {"CHANGELOG.md", "RELEASING.md"}

PATTERNS = [
    (f"v{OLD}", f"v{NEW}"),
    (f'"{OLD}"', f'"{NEW}"'),
    (f"agent-style@{OLD}", f"agent-style@{NEW}"),
    (f"// {OLD}", f"// {NEW}"),
    (f'EXPECTED_VERSION = "{OLD}"', f'EXPECTED_VERSION = "{NEW}"'),
]

# Every file that must carry the release version. Exact-string replacement
# silently skips a value that has already drifted, which is how both tools.json
# mirrors sat at 0.2.0 across two releases. Refuse to run unless all five agree
# with OLD, so drift is reported instead of being carried forward.
VERSION_FILES = {
    "packages/pypi/pyproject.toml": f'version = "{OLD}"',
    "packages/pypi/agent_style/__init__.py": f'__version__ = "{OLD}"',
    "packages/npm/package.json": f'"version": "{OLD}"',
    "packages/pypi/agent_style/data/tools.json": f'"agent_style_version": "{OLD}"',
    "packages/npm/data/tools.json": f'"agent_style_version": "{OLD}"',
}
drift = []
for rel, needle in VERSION_FILES.items():
    path = os.path.join(ROOT, rel)
    try:
        with open(path, encoding="utf-8") as f:
            if needle not in f.read():
                drift.append(rel)
    except FileNotFoundError:
        drift.append(f"{rel} (missing)")
if drift:
    sys.exit(
        f"refusing to bump: these files do not currently carry {OLD}:\n  "
        + "\n  ".join(drift)
        + "\nFix them to the current version first, then re-run."
    )

files = subprocess.check_output(["git", "-C", ROOT, "ls-files"], text=True).splitlines()
changed = 0
for rel in files:
    if not rel.endswith(EXTS) or rel in SKIP:
        continue
    path = os.path.join(ROOT, rel)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        continue
    new_data = data
    for old, new in PATTERNS:
        new_data = new_data.replace(old.encode("utf-8"), new.encode("utf-8"))
    if new_data != data:
        with open(path, "wb") as f:
            f.write(new_data)
        changed += 1
        print(f"  updated: {rel}")
print(f"total: {changed} files")
