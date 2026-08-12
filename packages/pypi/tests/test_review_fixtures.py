# SPDX-License-Identifier: MIT
"""Fixture-driven tests for the review primitive.

Each fixture in `data/skills/style-review/references/fixture-prose/` ships with
a `<name>.expected.json` sibling that documents the expected per-rule violation
count produced by the deterministic (mechanical + structural) detectors. This
test loads every fixture, runs the audit, and asserts the counts match exactly.

These tests are the contract for "detector behavior does not regress silently."
If a detector changes, the expected.json must change with it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent_style.review import audit


FIXTURES_DIR = (
    Path(__file__).parent.parent
    / "agent_style"
    / "data"
    / "skills"
    / "style-review"
    / "references"
    / "fixture-prose"
)


def _list_fixtures():
    """Yield (fixture_path, expected_path) pairs for every fixture on disk."""
    if not FIXTURES_DIR.is_dir():
        pytest.skip(f"fixtures directory missing: {FIXTURES_DIR}")
    for md in sorted(FIXTURES_DIR.glob("*.md")):
        expected = md.with_suffix(".expected.json")
        if expected.is_file():
            yield md, expected


@pytest.mark.parametrize(
    "fixture_md,expected_json",
    [pytest.param(md, ex, id=md.name) for md, ex in _list_fixtures()],
)
def test_audit_matches_expected(fixture_md: Path, expected_json: Path) -> None:
    """Audit each fixture; per-rule counts must equal expected.json."""
    expected = json.loads(expected_json.read_text(encoding="utf-8"))
    result = audit(str(fixture_md), mechanical_only=False, skill_host=False)

    # Total
    assert result.total_violations == expected["total_violations"], (
        f"{fixture_md.name}: expected {expected['total_violations']} total "
        f"violations, got {result.total_violations}"
    )

    # Per-rule aggregated counts (sum across all buckets for the same rule id).
    actual_counts: dict[str, int] = {}
    for rr in result.rule_results:
        if rr.count > 0:
            actual_counts[rr.rule] = actual_counts.get(rr.rule, 0) + rr.count
    expected_counts = expected["per_rule_count"]

    assert actual_counts == expected_counts, (
        f"{fixture_md.name}: per-rule count mismatch.\n"
        f"  expected: {sorted(expected_counts.items())}\n"
        f"  actual:   {sorted(actual_counts.items())}"
    )

    # Semantic / deferred-structural rules must all report status "skipped"
    # so the JSON schema is complete for the whole matrix.
    skipped_ids = {rr.rule for rr in result.rule_results if rr.status == "skipped"}
    for rid in expected.get("expected_skipped_rules", []):
        assert rid in skipped_ids, (
            f"{fixture_md.name}: expected rule {rid} to be skipped but it was not"
        )


def test_clean_control_has_zero_violations() -> None:
    """Explicit regression guard: clean-control must stay at zero."""
    fixture = FIXTURES_DIR / "clean-control.md"
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")
    result = audit(str(fixture), mechanical_only=False, skill_host=False)
    triggered = [
        (rr.rule, rr.detector, rr.count)
        for rr in result.rule_results
        if rr.status == "violation"
    ]
    assert triggered == [], (
        f"clean-control.md produced unexpected violations: {triggered}"
    )


def test_messy_real_world_fenced_code_not_flagged() -> None:
    """Regression guard: `leverages` inside a fenced code block must NOT fire RULE-06."""
    fixture = FIXTURES_DIR / "messy-real-world.md"
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")
    result = audit(str(fixture), mechanical_only=False, skill_host=False)
    for rr in result.rule_results:
        if rr.rule == "RULE-06":
            assert rr.count == 0, (
                f"RULE-06 fired on fenced-code fixture: {[v.excerpt for v in rr.violations]}"
            )


def test_audit_only_mode_excludes_semantic() -> None:
    """audit(..., skill_host=False) must skip every semantic rule."""
    fixture = FIXTURES_DIR / "mixed.md"
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")
    result = audit(str(fixture), mechanical_only=False, skill_host=False)
    semantic_violations = [
        rr for rr in result.rule_results
        if rr.detector == "semantic" and rr.status == "violation"
    ]
    assert semantic_violations == [], (
        f"semantic detectors should never produce violations without a skill host: "
        f"{[rr.rule for rr in semantic_violations]}"
    )


def test_mechanical_only_excludes_structural() -> None:
    """mechanical_only=True must skip every structural and semantic rule."""
    fixture = FIXTURES_DIR / "mixed.md"
    if not fixture.is_file():
        pytest.skip(f"fixture missing: {fixture}")
    result = audit(str(fixture), mechanical_only=True, skill_host=False)
    leaks = [
        rr for rr in result.rule_results
        if rr.detector != "mechanical" and rr.status == "violation"
    ]
    assert leaks == [], (
        f"--mechanical-only should be the deterministic parity oracle; "
        f"non-mechanical violations leaked: {[rr.rule for rr in leaks]}"
    )


# ---------------------------------------------------------------------------
# Exact-object boundary tests.
#
# The fixture tests above assert per-rule counts only, so a false positive and
# a false negative for the same rule cancel out and the suite still passes. The
# cases below build their own input and assert the complete violation object,
# which is what makes them a regression oracle rather than a tally.
# ---------------------------------------------------------------------------


def _audit_text(tmp_path: Path, text: str, rule: str) -> list[dict]:
    """Audit ``text`` through the public file path; return complete violations.

    Comparing whole objects rather than (line, column) is the point: RULE-A's
    ``detail`` string is part of the canonical JSON, so a change to it is a
    behavior change that a coordinate-only assertion would not catch.
    """
    target = tmp_path / "case.md"
    target.write_bytes(text.encode("utf-8"))
    result = audit(str(target), skill_host=False)
    return [
        {"line": v.line, "column": v.column, "excerpt": v.excerpt, "detail": v.detail}
        for rr in result.rule_results
        if rr.rule == rule
        for v in rr.violations
    ]


def _audit_text_at(tmp_path: Path, text: str, rule: str) -> list[tuple[int, int]]:
    """Coordinate-only view of :func:`_audit_text`, for the many-case tables."""
    return [(v["line"], v["column"]) for v in _audit_text(tmp_path, text, rule)]


@pytest.mark.parametrize(
    "label,newline",
    [("lf", "\n"), ("crlf", "\r\n"), ("cr", "\r")],
)
def test_rule_05_locates_a_cliche_under_every_line_ending(
    tmp_path: Path, label: str, newline: str
) -> None:
    """RULE-05 must report line 2, column 1 whatever separates the lines.

    Python reads files with universal-newline translation, so this pins the
    file path. A bare CR previously shifted the reported line because the
    offset arithmetic counted only "\n".
    """
    text = f"prefix{newline}paradigm shift{newline}tail{newline}"
    assert _audit_text(tmp_path, text, "RULE-05") == [
        {
            "line": 2,
            "column": 1,
            "excerpt": "paradigm shift",
            "detail": "cliché phrase 'paradigm shift'",
        }
    ], f"RULE-05 mislocated the cliche under {label} line endings"


@pytest.mark.parametrize(
    "label,newline",
    [("lf", "\n"), ("crlf", "\r\n"), ("cr", "\r")],
)
def test_rule_05_detector_handles_line_endings_in_direct_text(
    label: str, newline: str
) -> None:
    """Go through the detector, not just its helper.

    ``audit`` normalises line endings on read, so a direct-text caller is the
    only path that exercises RULE-05's own offset arithmetic. Asserting on the
    span helper alone would still pass if RULE-05 stopped consuming it.
    """
    from agent_style.review import detectors_mech
    from agent_style.review.loader import Rule

    rule = Rule(
        id="RULE-05",
        title="test",
        severity="medium",
        scope="",
        source="",
        directive="",
    )
    result = detectors_mech.run(rule, f"prefix{newline}paradigm shift", "memory.md")
    assert [(v.line, v.column, v.detail) for v in result.violations] == [
        (2, 1, "cliché phrase 'paradigm shift'")
    ], f"RULE-05 mislocated the cliche in direct text under {label}"


def test_rule_05_line_spans_handle_mixed_line_endings_in_direct_text() -> None:
    """The span helper's own contract, pinned separately from its caller."""
    from agent_style.review import detectors_mech

    for newline in ("\n", "\r\n", "\r"):
        spans = detectors_mech._line_spans(f"prefix{newline}paradigm shift")
        assert spans == [(0, 6), (6 + len(newline), 6 + len(newline) + 14)], (
            f"line spans wrong for {newline!r}"
        )


@pytest.mark.parametrize(
    "label,body",
    [
        ("imperative checklist", "1. Stop the service.\n2. Rotate the credentials.\n3. Restart the workers.\n"),
        ("repeated-opener checklist", "1. Run the migration.\n2. Run the tests.\n3. Run the service.\n"),
        ("preposition-led enumeration", "- For Linux, use apt.\n- For macOS, use brew.\n- For Windows, use winget.\n"),
        ("uniform per enumeration", "- Per minute limits\n- Per user limits\n- Per region limits\n"),
        ("short independent labels", "- Linux\n- macOS\n- Windows\n"),
    ],
)
def test_rule_a_leaves_genuine_enumerations_alone(
    tmp_path: Path, label: str, body: str
) -> None:
    """RULE-A's directive names checklist steps as a genuine list.

    Shortness is not evidence, and neither is a repeated opening word; both
    describe these lists as much as they describe fragmented prose.
    """
    assert _audit_text(tmp_path, f"Heading:\n\n{body}", "RULE-A") == [], (
        f"RULE-A flagged a genuine enumeration: {label}"
    )


@pytest.mark.parametrize(
    "label,body",
    [
        ("connective shards", "- Training a contrastive embedder\n- Because this improves recall\n- Which matters downstream\n"),
        ("emphasis-wrapped connective", "- Training an embedder\n- **Because** this improves recall\n- **Which** matters\n"),
        ("leading and", "- A misconfigured load balancer rule\n- An outdated auth-v1 service\n- And insufficient alerting\n"),
        ("mixed per fragments", "- Free tier\n- 100 requests\n- Per minute\n- Per user\n"),
        ("repeated subject and copula", "- It is fast\n- It is accurate\n- It is easy to use\n"),
        ("numbered causal chain", "1. Because retrieval is hard\n2. Therefore we add reranking\n3. And this improves recall\n"),
    ],
)
def test_rule_a_flags_prose_shredded_into_bullets(
    tmp_path: Path, label: str, body: str
) -> None:
    """Each of RULE-A's own BAD shapes must fire, at the first item's line."""
    assert _audit_text_at(tmp_path, f"Heading:\n\n{body}", "RULE-A") == [(3, 1)], (
        f"RULE-A missed shredded prose: {label}"
    )


def test_rule_a_strong_signal_survives_a_long_item(tmp_path: Path) -> None:
    """An explicit connective shard is evidence regardless of item length.

    Gating every signal behind "all items are short" made a list with one long
    item silently clean even when it contained a literal `Because` fragment.
    """
    body = (
        "- Training a contrastive embedder on a very large corpus of documents\n"
        "- Because this improves recall\n"
        "- Which matters downstream\n"
    )
    assert _audit_text_at(tmp_path, f"Heading:\n\n{body}", "RULE-A") == [(3, 1)]


# ---------------------------------------------------------------------------
# List-container and block-boundary cases.
#
# These were verified in a local matrix before they were committed, which is
# exactly the gap this block closes: an uncommitted matrix cannot stop the next
# edit from regressing them.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,body",
    [
        ("nested children not flattened into parent", "- Rate limits:\n  - Per minute\n  - Per user\n"),
        ("only one item is not a Per fragment", "- Global\n- Per user\n- Per project\n"),
        ("bare one-word connective labels", "- And\n- But\n- Or\n"),
    ],
)
def test_rule_a_list_containers_stay_clean(
    tmp_path: Path, label: str, body: str
) -> None:
    """A marker and an opening word are not evidence about list structure."""
    assert _audit_text(tmp_path, f"Heading:\n\n{body}", "RULE-A") == [], (
        f"RULE-A flagged a genuine list container: {label}"
    )


def test_rule_a_parent_list_survives_a_nested_block(tmp_path: Path) -> None:
    """A nested child block must not split its parent list into fragments.

    Breaking out of the group at the first deeper line turned this three-item
    parent list into groups of one and two, so the connective shards in it
    stopped being visible at all.
    """
    body = (
        "- Training a contrastive embedder\n"
        "  - Local negatives\n"
        "  - Hard negatives\n"
        "- Because this improves recall\n"
        "- Which matters downstream\n"
    )
    assert _audit_text_at(tmp_path, f"Heading:\n\n{body}", "RULE-A") == [(3, 1)]


def test_rule_a_one_tab_is_deeper_than_one_space(tmp_path: Path) -> None:
    """A tab child under a one-space parent is nested, not a sibling.

    Raw character length calls both depth 1, which flattens the children into
    the parent and reports a three-item list nobody wrote.
    """
    body = (
        " - Parent item\n"
        "\t- Because nested reason\n"
        "\t- Which nested consequence\n"
    )
    assert _audit_text(tmp_path, f"Heading:\n\n{body}", "RULE-A") == []


def test_rule_a_four_spaces_and_one_tab_are_the_same_depth(tmp_path: Path) -> None:
    """Both land on column 4, so these are siblings and the shards are visible.

    Raw character length calls them depths 4 and 1, splitting one list into two
    groups and losing the positive entirely.
    """
    body = (
        "    - Training a contrastive embedder\n"
        "\t- Because this improves recall\n"
        "\t- Which matters downstream\n"
    )
    assert _audit_text_at(tmp_path, f"Heading:\n\n{body}", "RULE-A") == [(3, 1)]


@pytest.mark.parametrize(
    "label,body,expected",
    [
        ("heading separates two prose blocks", "Additionally, first.\n## Section\nMoreover, second.\n", []),
        ("adjacent list items are separate blocks", "- Additionally, first.\n- Moreover, second.\n", []),
        ("blockquoted heading separates blocks", "> Additionally, first.\n> ## Section\n> Moreover, second.\n", []),
        ("blockquoted list items are separate blocks", "> - Additionally, first.\n> - Moreover, second.\n", []),
        (
            "two openers in one real paragraph still fire",
            "The first passed. Additionally, the second passed. Furthermore, the third passed.\n",
            [(1, 52)],
        ),
    ],
)
def test_rule_d_uses_markdown_block_boundaries(
    tmp_path: Path, label: str, body: str, expected: list
) -> None:
    """The one-transition allowance is per block, not per blank-line run."""
    assert _audit_text_at(tmp_path, body, "RULE-D") == expected, (
        f"RULE-D block segmentation wrong for: {label}"
    )
