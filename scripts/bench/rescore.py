# SPDX-License-Identifier: MIT
"""Replay the v0.3.0 benchmark drafts and publish a corrected scorecard.

This script delegates every draft score to ``scripts/bench/run.sh``. The replay
mode in that harness uses the review package from this clone and preserves the
published ``review --mechanical-only --audit-only`` scoring contract.

Usage:
    python scripts/bench/rescore.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from aggregate import format_delta, parse_scorecard


ROOT = Path(__file__).resolve().parents[2]
RUN_SH = ROOT / "scripts" / "bench" / "run.sh"
DRAFTS_REL = "docs/bench-0.3.0-drafts"
DRAFTS_ROOT = ROOT / DRAFTS_REL

RULES = [
    "RULE-01",
    "RULE-02",
    "RULE-03",
    "RULE-04",
    "RULE-05",
    "RULE-06",
    "RULE-07",
    "RULE-08",
    "RULE-09",
    "RULE-10",
    "RULE-11",
    "RULE-12",
    "RULE-A",
    "RULE-B",
    "RULE-C",
    "RULE-D",
    "RULE-E",
    "RULE-F",
    "RULE-G",
    "RULE-H",
    "RULE-I",
]
EXPECTED_MECHANICAL = {
    "RULE-05",
    "RULE-06",
    "RULE-12",
    "RULE-B",
    "RULE-D",
    "RULE-G",
    "RULE-I",
}


@dataclass(frozen=True)
class Runner:
    key: str
    model: str
    label: str

    @property
    def drafts(self) -> Path:
        return DRAFTS_ROOT / self.key

    @property
    def original(self) -> Path:
        return ROOT / "docs" / f"bench-0.3.0-{self.key}.md"


RUNNERS = [
    Runner("claude", "claude-opus-4-7", "Claude"),
    Runner("codex", "gpt-5.4", "Codex"),
    Runner("copilot", "gpt-5.4", "Copilot"),
    Runner("gemini", "flash", "Gemini"),
]


def local_engine_command(*args: str) -> list[str]:
    return [sys.executable, "-m", "agent_style.cli", *args]


def discover_scope() -> tuple[set[str], set[str]]:
    probe = next(DRAFTS_ROOT.rglob("draft-1.md"), None)
    if probe is None:
        raise RuntimeError(f"no benchmark drafts found under {DRAFTS_ROOT}")

    proc = subprocess.run(
        local_engine_command(
            "review", "--mechanical-only", "--audit-only", str(probe)
        ),
        cwd=ROOT / "packages" / "pypi",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "local corrected engine scope probe failed:\n"
            f"{proc.stdout}{proc.stderr}"
        )

    payload = json.loads(proc.stdout)

    # The replay is run from `packages/pypi`, and `load_rules()` prefers a
    # project-local `.agent-style/RULES.md` found by walking up from the working
    # directory. One placed at `packages/pypi/`, `packages/`, or the repository
    # root would supply the rule metadata while the identity digest below went on
    # hashing the bundled copy, so the report would name a file that did not
    # score it. The engine already reports which source it chose; refuse any
    # answer but the manifest-covered one.
    if payload.get("rules_source") != "package-bundle":
        raise RuntimeError(
            "replay must use the manifest-covered package-bundle RULES.md; "
            f"resolved {payload.get('rules_source')!r}"
        )

    concrete: set[str] = set()
    skipped: set[str] = set()
    for result in payload["rule_results"]:
        rule = result["rule"]
        if result["detector"] == "mechanical" and result["status"] in {
            "ok",
            "violation",
        }:
            concrete.add(rule)
        if result["status"] == "skipped":
            skipped.add(rule)

    if concrete != EXPECTED_MECHANICAL:
        raise RuntimeError(
            "mechanical scoring scope changed: "
            f"expected {sorted(EXPECTED_MECHANICAL)}, got {sorted(concrete)}"
        )
    no_scored_component = set(RULES) - concrete
    if not no_scored_component <= skipped:
        missing = sorted(no_scored_component - skipped)
        raise RuntimeError(f"rules neither scored nor skipped: {missing}")
    return concrete, no_scored_component


def validate_drafts() -> tuple[int, str]:
    """Check the drafts are present *and* unmodified; return (count, tree hash).

    Counting files is not enough to support the report's claim that it scored
    committed drafts. A local edit, or a baseline/treatment content swap, leaves
    the count at 40 and silently changes every number. The tree hash is written
    into the report so a published run names the exact inputs it scored.
    """
    counts: dict[str, int] = {}
    for runner in RUNNERS:
        count = len(list(runner.drafts.rglob("draft-*.md")))
        counts[runner.key] = count
        if count != 40:
            raise RuntimeError(
                f"{runner.drafts}: expected 40 drafts, found {count}"
            )
    dirty = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain", "--", DRAFTS_REL],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if dirty:
        raise RuntimeError(
            "refusing to publish a re-score of modified drafts; "
            f"`git status --porcelain -- {DRAFTS_REL}` reports:\n{dirty}"
        )
    tree = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", f"HEAD:{DRAFTS_REL}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return sum(counts.values()), tree


def run_replay_pass(work: Path, pass_number: int, bash: str) -> dict[str, dict]:
    cards: dict[str, dict] = {}
    env = os.environ.copy()
    env["PYTHON_BIN"] = Path(sys.executable).as_posix()

    for runner in RUNNERS:
        output = work / f"pass-{pass_number}-{runner.key}.md"
        command = [
            bash,
            RUN_SH.relative_to(ROOT).as_posix(),
            "--runner",
            runner.key,
            "--model",
            runner.model,
            "--drafts",
            runner.drafts.relative_to(ROOT).as_posix(),
            "--output",
            output.as_posix(),
        ]
        proc = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"replay pass {pass_number} failed for {runner.key}:\n"
                f"{proc.stdout}{proc.stderr}"
            )
        cards[runner.key] = parse_scorecard(output)
        print(f"pass {pass_number}: rescored {runner.key}")
    return cards


def numeric_view(cards: dict[str, dict]) -> dict[str, dict]:
    return {
        key: {
            "totals": card["totals"],
            "per_rule": card["per_rule"],
        }
        for key, card in cards.items()
    }


def validate_card_arithmetic(card: dict, source: Path) -> None:
    for field in ("baseline", "treatment"):
        per_rule_total = sum(row[field] for row in card["per_rule"].values())
        if per_rule_total != card["totals"][field]:
            raise RuntimeError(
                f"{source}: {field} total {card['totals'][field]} does not equal "
                f"per-rule sum {per_rule_total}"
            )


def rule_row(card: dict, rule: str) -> dict[str, int]:
    return card["per_rule"].get(
        rule, {"baseline": 0, "treatment": 0, "delta": 0}
    )


SCORER_RELS = tuple(
    sorted(
        [
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "packages" / "pypi" / "agent_style").rglob("*.py")
        ]
        + [
            "packages/pypi/agent_style/data/RULES.md",
            "packages/pypi/agent_style/data/tools.json",
            "scripts/bench/aggregate.py",
            "scripts/bench/rescore.py",
            "scripts/bench/run.sh",
            "scripts/bench/tasks.md",
        ]
    )
)


def engine_identity() -> tuple[str, str]:
    """Return the version and SHA-256 of the complete replay scorer.

    A deterministic replay is only publishable when the artifact says what
    computed it, and the version alone cannot say that: during development the
    five version files still carry the previous number while the scorer already
    behaves like the next release.

    The manifest covers every path the replay actually reads, not just the
    detector module. `primitive.py` decides which rules enter the mechanical
    bucket, `run.sh` tallies the JSON, `aggregate.py` parses the scorecards and
    `tasks.md` selects the drafts, so any of them can move a published number.
    An earlier version of this hashed `detectors_mech.py` alone, and editing
    `primitive.py` left the identity byte-identical.
    """
    version = ""
    init = ROOT / "packages" / "pypi" / "agent_style" / "__init__.py"
    for line in init.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            version = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not version:
        raise RuntimeError(f"{init}: missing or empty __version__ marker")

    return version, manifest_digest(SCORER_RELS)


def manifest_digest(rels: tuple[str, ...]) -> str:
    """Hash an ordered set of repository-relative paths, name and content both.

    Each entry is length-prefixed so that no rename or concatenation of two
    paths can collide with a different set of files.

    Line endings are normalised to LF before hashing, because the digest has to
    identify committed content rather than one checkout of it. `.gitattributes`
    declares `*.py text eol=lf`, so a fresh clone gets LF on every platform,
    while an older working tree can still hold CRLF that `git diff` reports as
    no change at all. Hashing raw bytes made the recorded identity depend on
    which working tree ran the replay, which is the one thing a digest printed
    for external verification may not do. Nothing is lost by normalising: the
    engine applies universal-newline translation on both runtimes, so line
    endings cannot move a score.
    """
    digest = hashlib.sha256()
    for rel in rels:
        name = rel.encode("utf-8")
        data = (ROOT / rel).read_bytes().replace(b"\r\n", b"\n")
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def inputs_identity() -> str:
    """Return the SHA-256 of the replay inputs the scorer does not produce.

    The scorer manifest covers what computes the corrected column, and the
    drafts tree hash covers what it reads. Neither reaches the four published
    scorecards, and every original count, every delta, and the change-in-delta
    column is parsed straight out of them. Editing one silently rewrites the
    comparison the report exists to make while both recorded identities hold
    still, so they get a digest of their own rather than being folded into the
    scorer manifest: they are evidence, not code.
    """
    rels = tuple(sorted(r.original.relative_to(ROOT).as_posix() for r in RUNNERS))
    return manifest_digest(rels)


def render_report(
    original: dict[str, dict],
    corrected: dict[str, dict],
    mechanical: set[str],
    skipped: set[str],
    draft_count: int,
    drafts_tree: str,
    engine_version: str,
    scorer_sha256: str,
    cards_sha256: str,
) -> str:
    lines: list[str] = []
    lines.append("# agent-style bench v0.3.0: corrected-engine re-score")
    lines.append("")
    lines.append(
        f"This report re-scores the {draft_count} committed drafts in "
        f"`{DRAFTS_REL}/` at tree `{drafts_tree}`, verified clean against the "
        "index before scoring. It makes no model calls and generates no "
        "new prose. Original values come from the four published runner "
        f"scorecards, whose SHA-256 as a set is `{cards_sha256}`. Corrected "
        f"values use agent-style v{engine_version}; scoring-source manifest "
        f"SHA-256 `{scorer_sha256}`."
    )
    lines.append("")
    lines.append(
        "The replay uses the original harness and its exact scoring invocation: "
        "`agent-style review --mechanical-only --audit-only`. Delta is treatment "
        "minus baseline. A negative delta means fewer flagged violations in the "
        "treatment drafts. Change in delta is corrected minus original."
    )
    lines.append("")
    lines.append(
        "One-command re-run: `python scripts/bench/rescore.py`. It performs only "
        "local scoring. Add `--verify-repeat` to require two matching replay "
        "passes before the report is written."
    )
    lines.append("")

    mechanical_text = ", ".join(f"`{rule}`" for rule in RULES if rule in mechanical)
    skipped_text = ", ".join(f"`{rule}`" for rule in RULES if rule in skipped)
    lines.append("## Scoring scope")
    lines.append("")
    lines.append(f"Mechanically scored rules: {mechanical_text}.")
    lines.append("")
    lines.append(
        "Rules with no scored component under `--mechanical-only`, each reported "
        f"with `status: skipped`: {skipped_text}. A skipped rule is shown as "
        "`skipped`, not numeric zero. `RULE-05` and `RULE-06` also emit a separate "
        "semantic component with `status: skipped`; their mechanical components "
        "are included in the totals."
    )
    lines.append("")

    lines.append("## Totals")
    lines.append("")
    lines.append(
        "| Runner | Original baseline | Original treatment | Original delta | "
        "Corrected baseline | Corrected treatment | Corrected delta | Change in delta |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    pooled_original = {"baseline": 0, "treatment": 0, "delta": 0}
    pooled_corrected = {"baseline": 0, "treatment": 0, "delta": 0}
    for runner in RUNNERS:
        old = original[runner.key]["totals"]
        new = corrected[runner.key]["totals"]
        for field in pooled_original:
            pooled_original[field] += old[field]
            pooled_corrected[field] += new[field]
        movement = new["delta"] - old["delta"]
        corrected_delta = format_delta(new["delta"])
        if movement:
            corrected_delta = f"**{corrected_delta}**"
        lines.append(
            f"| {runner.label} | {old['baseline']} | {old['treatment']} | "
            f"{format_delta(old['delta'])} | {new['baseline']} | {new['treatment']} | "
            f"{corrected_delta} | {format_delta(movement)} |"
        )
    pooled_movement = pooled_corrected["delta"] - pooled_original["delta"]
    lines.append(
        f"| **Pooled** | **{pooled_original['baseline']}** | "
        f"**{pooled_original['treatment']}** | "
        f"**{format_delta(pooled_original['delta'])}** | "
        f"**{pooled_corrected['baseline']}** | "
        f"**{pooled_corrected['treatment']}** | "
        f"**{format_delta(pooled_corrected['delta'])}** | "
        f"**{format_delta(pooled_movement)}** |"
    )
    lines.append("")

    lines.append("## Rule deltas that moved")
    lines.append("")
    lines.append("| Runner | Rule | Original delta | Corrected delta | Change in delta |")
    lines.append("| --- | --- | ---: | ---: | ---: |")
    movement_rows = 0
    for runner in RUNNERS:
        for rule in RULES:
            if rule not in mechanical:
                continue
            old_delta = rule_row(original[runner.key], rule)["delta"]
            new_delta = rule_row(corrected[runner.key], rule)["delta"]
            movement = new_delta - old_delta
            if movement:
                movement_rows += 1
                lines.append(
                    f"| {runner.label} | {rule} | {format_delta(old_delta)} | "
                    f"**{format_delta(new_delta)}** | **{format_delta(movement)}** |"
                )
    if movement_rows == 0:
        lines.append("| none | none | 0 | 0 | 0 |")
    lines.append("")

    lines.append("## Full per-rule scorecard")
    lines.append("")
    lines.append(
        "`O` is original and `C` is corrected. Bold corrected values changed."
    )
    lines.append("")
    header = ["Rule"]
    for runner in RUNNERS:
        header.extend([f"{runner.label} O", f"{runner.label} C"])
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| --- |" + " ---: | ---: |" * len(RUNNERS))
    for rule in RULES:
        shown_rule = rule
        cells = [shown_rule]
        for runner in RUNNERS:
            if rule in skipped:
                cells.extend(["skipped", "skipped"])
                continue
            old_delta = rule_row(original[runner.key], rule)["delta"]
            new_delta = rule_row(corrected[runner.key], rule)["delta"]
            corrected_cell = format_delta(new_delta)
            if new_delta != old_delta:
                corrected_cell = f"**{corrected_cell}**"
            cells.extend([format_delta(old_delta), corrected_cell])
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    hidden_changes: list[tuple[Runner, str, dict[str, int], dict[str, int]]] = []
    for runner in RUNNERS:
        for rule in RULES:
            if rule not in mechanical:
                continue
            old = rule_row(original[runner.key], rule)
            new = rule_row(corrected[runner.key], rule)
            counts_changed = (
                old["baseline"] != new["baseline"]
                or old["treatment"] != new["treatment"]
            )
            if counts_changed and old["delta"] == new["delta"]:
                hidden_changes.append((runner, rule, old, new))

    lines.append("## Count corrections hidden by unchanged deltas")
    lines.append("")
    if hidden_changes:
        lines.append(
            "These rule deltas stayed fixed only because baseline and treatment "
            "counts moved by the same amount."
        )
        lines.append("")
        lines.append(
            "| Runner | Rule | Original baseline / treatment | "
            "Corrected baseline / treatment | Delta |"
        )
        lines.append("| --- | --- | ---: | ---: | ---: |")
        for runner, rule, old, new in hidden_changes:
            lines.append(
                f"| {runner.label} | {rule} | {old['baseline']} / "
                f"{old['treatment']} | {new['baseline']} / {new['treatment']} | "
                f"{format_delta(new['delta'])} |"
            )
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        f"The pooled delta changes from {format_delta(pooled_original['delta'])} "
        f"to {format_delta(pooled_corrected['delta'])}, a movement of "
        f"{format_delta(pooled_movement)} violations. The rescore changes the "
        "measurement of saved prose only. It does not rerun model generation, "
        "resolve runner instruction-loading caveats, or measure any skipped rule."
    )
    lines.append("")
    lines.append(
        "These are directional benchmark counts, not a claim of statistical "
        "significance or overall writing quality."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "bench-0.3.0-rescored.md",
    )
    parser.add_argument(
        "--verify-repeat",
        action="store_true",
        help="run a second replay pass and require identical numeric results",
    )
    args = parser.parse_args()

    bash = shutil.which("bash")
    if bash is None:
        raise RuntimeError("bash is required to replay scripts/bench/run.sh")

    draft_count, drafts_tree = validate_drafts()
    mechanical, skipped = discover_scope()
    original = {runner.key: parse_scorecard(runner.original) for runner in RUNNERS}
    for runner in RUNNERS:
        validate_card_arithmetic(original[runner.key], runner.original)

    with tempfile.TemporaryDirectory(prefix="agent-style-rescore-") as temp:
        work = Path(temp)
        first = run_replay_pass(work, 1, bash)
        if args.verify_repeat:
            second = run_replay_pass(work, 2, bash)
            if numeric_view(first) != numeric_view(second):
                raise RuntimeError(
                    "two corrected-engine replay passes produced different numbers"
                )
        for runner in RUNNERS:
            validate_card_arithmetic(first[runner.key], runner.drafts)

        engine_version, scorer_sha256 = engine_identity()
        cards_sha256 = inputs_identity()
        report = render_report(
            original, first, mechanical, skipped, draft_count, drafts_tree,
            engine_version, scorer_sha256, cards_sha256,
        )
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        # Not Path.write_text(..., newline=...): that keyword arrived in 3.10
        # and the package declares requires-python >= 3.8, so it would raise
        # TypeError only after the whole replay had already run.
        with output.open("w", encoding="utf-8", newline="\n") as report_file:
            report_file.write(report)

    if args.verify_repeat:
        print(f"two replay passes matched; wrote {output}")
    else:
        print(f"replay complete; wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
