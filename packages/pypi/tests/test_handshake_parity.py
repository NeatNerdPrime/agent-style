# SPDX-License-Identifier: MIT
"""Regression tests pinning the style-review handshake to everything that quotes it.

The handshake is the sentence the skill emits when asked whether it is active.
It is written once in ``skills/style-review/SKILL.md`` and copied by hand into
the pypi and npm data trees and into the README. ``real-agent-smoke`` asserts
that a real Claude response reproduces it.

That workflow runs on ``release.published`` and manual dispatch only, so a
handshake edit and a stale assertion cannot collide until after the release is
tagged and published. It happened exactly that way on the release that first
shipped the corrected scorecard wording (do not name it here: ``bump-version.py``
rewrites version literals in this file and would falsify the account): the
handshake
changed from "21 rules" to "21-row scorecard, 19 rules checked", the workflow
kept asserting the old substring, and the static check in the same job passed
anyway because "21 rules" still appeared in the skill's frontmatter description.
The probe step against the live model was the only thing that noticed, and by
then the package was on PyPI.

These tests move both checks to push time:

  1. the handshake is byte-identical across the source skill, both packaged
     copies, and the README, and
  2. every literal the smoke workflow asserts about the skill handshake is a
     substring of that handshake, so an assertion cannot outlive the claim it
     guards.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# tests/ -> pypi/ -> packages/ -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_SKILL_REL = "skills/style-review/SKILL.md"
SOURCE_SKILL = REPO_ROOT.joinpath(*_SKILL_REL.split("/"))
PYPI_SKILL = REPO_ROOT.joinpath(
    "packages", "pypi", "agent_style", "data", *_SKILL_REL.split("/")
)
NPM_SKILL = REPO_ROOT.joinpath("packages", "npm", "data", *_SKILL_REL.split("/"))
README = REPO_ROOT / "README.md"
SMOKE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "real-agent-smoke.yml"

_HANDSHAKE_PREFIX = "style-review active:"


def _normalize(line: str) -> str:
    """Strip the wrappers each file puts around the same sentence.

    SKILL.md fences it in backticks, the README quotes it as a blockquote.
    Stripping both leaves the sentence itself, so parity is compared on content
    rather than on presentation.
    """
    return line.strip().lstrip("> ").strip().strip("`").strip()


def _handshake(path: Path) -> str:
    """Return the single style-review handshake sentence carried by ``path``.

    Anchored on the sentence *opening* the line rather than merely appearing in
    it, so the surrounding prose ("When asked \"is style-review active?\"...",
    "> Is style-review active?") does not match.
    """
    text = path.read_bytes().decode("utf-8")
    found = [
        normalized
        for normalized in (_normalize(line) for line in text.splitlines())
        if normalized.startswith(_HANDSHAKE_PREFIX)
    ]
    assert len(found) == 1, (
        f"expected exactly one line opening with {_HANDSHAKE_PREFIX!r} in {path}, "
        f"found {len(found)}"
    )
    return found[0]


def _skill_token_lists() -> list[list[str]]:
    """Return the smoke workflow's token lists that assert on the skill handshake.

    A ``for token in`` loop is treated as a skill-handshake assertion when its
    literals include ``style-review active``. The adapter jobs assert a
    different sentence (and interpolate ``$EXPECTED_VERSION``), so keying on the
    handshake opener rather than on job names or line numbers keeps this test
    correct when steps move.
    """
    text = SMOKE_WORKFLOW.read_bytes().decode("utf-8")
    lists = []
    for line in text.splitlines():
        if "for token in" not in line:
            continue
        tokens = re.findall(r'"([^"]*)"', line)
        if _HANDSHAKE_PREFIX.rstrip(":") in tokens:
            lists.append(tokens)
    return lists


def test_style_review_handshake_parity() -> None:
    """The handshake must read identically in the skill, both packages, and the README."""
    for path in (SOURCE_SKILL, PYPI_SKILL, NPM_SKILL, README):
        if not path.is_file():
            pytest.skip(f"missing (not a source checkout): {path}")

    source = _handshake(SOURCE_SKILL)
    for label, path in (
        ("pypi", PYPI_SKILL),
        ("npm", NPM_SKILL),
        ("README", README),
    ):
        assert _handshake(path) == source, (
            f"style-review handshake drifted between source and {label}:\n"
            f"  source: {source!r}\n"
            f"  {label}: {_handshake(path)!r}"
        )


def test_smoke_workflow_asserts_only_live_handshake_tokens() -> None:
    """Every literal the smoke workflow asserts must appear in the handshake itself.

    Substring containment, not equality: the workflow deliberately checks
    fragments so a reworded clause elsewhere in the sentence does not fail the
    run. What it may not do is assert a fragment the handshake no longer carries.
    """
    for path in (SOURCE_SKILL, SMOKE_WORKFLOW):
        if not path.is_file():
            pytest.skip(f"missing (not a source checkout): {path}")

    handshake = _handshake(SOURCE_SKILL)
    token_lists = _skill_token_lists()
    assert token_lists, (
        "no style-review handshake assertion found in "
        f"{SMOKE_WORKFLOW.name}; the release-time guard was removed"
    )

    for tokens in token_lists:
        for token in tokens:
            assert token in handshake, (
                f"{SMOKE_WORKFLOW.name} asserts {token!r}, which the handshake no "
                f"longer contains:\n  handshake: {handshake!r}"
            )
