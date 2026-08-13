# SPDX-License-Identifier: MIT
"""Regression tests for the replay identity that ``docs/bench-0.3.0-rescored.md`` prints.

The report names three things: the drafts tree it scored, the scoring-source
manifest that computed the corrected column, and the set of published scorecards
the original column is read from. Each identity is only worth printing if it
actually constrains the run, so each is tested here for the way it could go
quietly wrong.

The scoring-source manifest is the one with a real hole under it.
``agent_style.review.loader.load_rules()`` prefers a project-local
``.agent-style/RULES.md``, discovered by walking up from the working directory,
and the replay runs the engine from ``packages/pypi``. A copy dropped anywhere
on that path would supply the rule metadata while the manifest went on hashing
the bundled file, so the report would name a source that did not score it.
``discover_scope()`` now refuses any answer but ``package-bundle``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest


# tests/ -> pypi/ -> packages/ -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RESCORE = REPO_ROOT / "scripts" / "bench" / "rescore.py"


def _load_rescore():
    """Import ``scripts/bench/rescore.py`` by path; it is not an installed module.

    Registered in ``sys.modules`` under its spec name before execution, because
    the module defines dataclasses and ``dataclasses`` resolves each annotation
    through ``sys.modules[cls.__module__]``.
    """
    if not RESCORE.is_file():
        pytest.skip(f"missing (not a source checkout): {RESCORE}")
    # `rescore.py` imports its sibling `aggregate` as a top-level module, the
    # way `scripts/bench/` scripts are run.
    bench = str(RESCORE.parent)
    if bench not in sys.path:
        sys.path.insert(0, bench)
    spec = importlib.util.spec_from_file_location("agent_style_rescore", RESCORE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fake_probe(rescore, rules_source: str) -> subprocess.CompletedProcess:
    """A scope-probe result that is valid except for where its rules came from.

    The rule list is taken from the module's own expected set, so this fixture
    isolates the source check instead of also re-asserting the scope check.
    """
    results = [
        {"rule": rule, "detector": "mechanical", "status": "ok"}
        for rule in sorted(rescore.EXPECTED_MECHANICAL)
    ]
    results += [
        {"rule": rule, "detector": "structural", "status": "skipped"}
        for rule in sorted(set(rescore.RULES) - rescore.EXPECTED_MECHANICAL)
    ]
    payload = {"rules_source": rules_source, "rule_results": results}
    return subprocess.CompletedProcess(
        args=[], returncode=0, stdout=json.dumps(payload), stderr=""
    )


def test_scope_probe_rejects_rules_that_did_not_come_from_the_bundle() -> None:
    """A project-local override must fail the replay rather than be scored with."""
    rescore = _load_rescore()
    with patch.object(
        rescore.subprocess, "run", return_value=_fake_probe(rescore, "project-local")
    ):
        with pytest.raises(RuntimeError) as excinfo:
            rescore.discover_scope()
    message = str(excinfo.value)
    assert "package-bundle" in message
    assert "project-local" in message


def test_scope_probe_accepts_the_bundled_rules() -> None:
    """The guard must not reject the source the replay is supposed to use.

    Paired with the test above so that a guard inverted to always-raise cannot
    pass the suite.
    """
    rescore = _load_rescore()
    with patch.object(
        rescore.subprocess, "run", return_value=_fake_probe(rescore, "package-bundle")
    ):
        concrete, skipped = rescore.discover_scope()
    assert concrete == rescore.EXPECTED_MECHANICAL


def _probe_in_sandbox(rescore, bundled: Path, seed_override: bool) -> str | None:
    """Run the scope probe in a temporary tree; return the failure message or None.

    ``discover_scope()`` runs the engine with ``cwd=ROOT/"packages"/"pypi"``,
    and the loader walks up from there, so repointing ``ROOT`` puts the whole
    ancestor walk inside the sandbox. Nothing a concurrent reader, a parallel
    test job, or a hard kill could observe is touched. ``DRAFTS_ROOT`` is bound
    at import from the real root and is only read, so the probe still scores a
    genuine draft.
    """
    with tempfile.TemporaryDirectory(prefix="agent-style-ancestor-") as temp:
        sandbox = Path(temp)
        (sandbox / "packages" / "pypi").mkdir(parents=True)
        if seed_override:
            override_dir = sandbox / "packages" / "pypi" / ".agent-style"
            override_dir.mkdir()
            # Byte-identical to the bundle, so the only thing under test is
            # which path the loader chose, not whether different rules change
            # the verdict.
            (override_dir / "RULES.md").write_bytes(bundled.read_bytes())

        real_root = rescore.ROOT
        rescore.ROOT = sandbox
        # The engine is launched as `python -m agent_style.cli` from the
        # sandbox, which is not an import root, so the real package has to stay
        # findable.
        previous = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = str(REPO_ROOT / "packages" / "pypi")
        try:
            rescore.discover_scope()
            return None
        except RuntimeError as exc:
            return str(exc)
        finally:
            rescore.ROOT = real_root
            if previous is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = previous


def test_a_seeded_ancestor_override_really_does_reach_the_replay() -> None:
    """Prove the hole the guard closes is reachable, not hypothetical.

    Without this, the two tests above would keep passing after a loader change
    that stopped consulting ancestors at all, and the guard would be dead code
    guarding nothing.

    The override is seeded in a temporary tree rather than in the real
    ``packages/pypi/``, so no shared checkout is mutated at any point.
    """
    rescore = _load_rescore()
    bundled = REPO_ROOT / "packages" / "pypi" / "agent_style" / "data" / "RULES.md"
    if not bundled.is_file():
        pytest.skip(f"missing (not a source checkout): {bundled}")

    # Two equivalently built sandboxes, differing only in the override. Without
    # it the probe must succeed, which is what proves the seeded run fails
    # because of the override and not because the sandbox broke the probe.
    assert _probe_in_sandbox(rescore, bundled, seed_override=False) is None
    message = _probe_in_sandbox(rescore, bundled, seed_override=True)
    assert message is not None, "a seeded ancestor override was scored with, not rejected"
    assert "package-bundle" in message
    assert "project-local" in message


def _engine_identity_rels(rescore) -> tuple[str, ...]:
    """Every path ``engine_identity()`` reads: the manifest plus the version marker."""
    return tuple(rescore.SCORER_RELS) + ("packages/pypi/agent_style/__init__.py",)


@contextmanager
def _sandboxed_root(rescore, rels):
    """Run the digest functions against a throwaway copy of the hashed files.

    The obvious way to test "editing this file moves the digest" is to edit the
    file and put it back. That leaves a window where an interrupted run has
    rewritten tracked source in a shared checkout, and ``finally`` does not
    cover a kill. Every path resolves through the module-global ``ROOT`` at call
    time, so pointing ``ROOT`` at a copied tree exercises the same code against
    files nothing else can be harmed by.
    """
    with tempfile.TemporaryDirectory(prefix="agent-style-provenance-") as temp:
        sandbox = Path(temp)
        for rel in rels:
            source = REPO_ROOT / rel
            if not source.is_file():
                pytest.skip(f"missing (not a source checkout): {source}")
            target = sandbox / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        real_root = rescore.ROOT
        rescore.ROOT = sandbox
        try:
            yield sandbox
        finally:
            rescore.ROOT = real_root


def test_the_published_scorecards_are_hashed_as_replay_inputs() -> None:
    """Every original column comes from these four files, so they carry an identity.

    They are not in the scoring-source manifest on purpose: they are evidence
    the replay reads, not code that computes anything. What matters is that
    editing one moves the digest the report prints.
    """
    rescore = _load_rescore()
    cards = tuple(
        sorted(r.original.relative_to(REPO_ROOT).as_posix() for r in rescore.RUNNERS)
    )
    # Named exactly, so dropping a runner from RUNNERS fails here rather than
    # silently shrinking what the published digest covers.
    assert cards == (
        "docs/bench-0.3.0-claude.md",
        "docs/bench-0.3.0-codex.md",
        "docs/bench-0.3.0-copilot.md",
        "docs/bench-0.3.0-gemini.md",
    )

    # Each card in turn: an implementation that kept hashing the first one and
    # quietly dropped the rest would pass a test that only perturbs cards[0].
    for card in cards:
        with _sandboxed_root(rescore, cards) as sandbox:
            before = rescore.inputs_identity()
            assert len(before) == 64
            target = sandbox / card
            target.write_bytes(target.read_bytes() + b"\n<!-- perturbed by a test -->\n")
            assert rescore.inputs_identity() != before, f"{card} does not move the digest"


def test_the_digest_identifies_committed_content_not_one_checkout() -> None:
    """CRLF and LF copies of the same file must hash alike.

    ``.gitattributes`` declares ``*.py text eol=lf``, so a fresh clone holds LF
    everywhere, while an older working tree can still hold CRLF that ``git
    diff`` reports as no change. Hashing raw bytes made the published identity
    depend on which working tree ran the replay, so recomputing it from the
    release tree, which ``RELEASING.md`` requires before tagging, would have
    disagreed with the report for no substantive reason.
    """
    rescore = _load_rescore()
    rel = "packages/pypi/agent_style/review/primitive.py"
    with _sandboxed_root(rescore, _engine_identity_rels(rescore)) as sandbox:
        target = sandbox / rel
        lf = target.read_bytes().replace(b"\r\n", b"\n")
        crlf = lf.replace(b"\n", b"\r\n")
        if lf == crlf:
            pytest.skip(f"no line endings to vary in {rel}")

        target.write_bytes(lf)
        as_lf = rescore.engine_identity()[1]
        target.write_bytes(crlf)
        as_crlf = rescore.engine_identity()[1]
    assert as_lf == as_crlf


def test_the_scorer_manifest_covers_more_than_the_mechanical_detector() -> None:
    """An earlier manifest hashed one module, so editing the rest changed nothing.

    Checks the two paths that regression was found through, plus the property
    that made it invisible: the digest has to move when they do.
    """
    rescore = _load_rescore()
    rels = set(rescore.SCORER_RELS)
    for required in (
        "packages/pypi/agent_style/review/primitive.py",
        "packages/pypi/agent_style/review/detectors_mech.py",
        "packages/pypi/agent_style/data/RULES.md",
        "scripts/bench/run.sh",
    ):
        assert required in rels, f"{required} is not covered by the scorer manifest"

    with _sandboxed_root(rescore, _engine_identity_rels(rescore)) as sandbox:
        before = rescore.engine_identity()[1]
        target = sandbox / "packages/pypi/agent_style/review/primitive.py"
        target.write_bytes(target.read_bytes() + b"\n# perturbed by a test\n")
        assert rescore.engine_identity()[1] != before
