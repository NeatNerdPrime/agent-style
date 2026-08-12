# SPDX-License-Identifier: MIT
"""Mechanical detectors: regex / word-list rules. Deterministic by construction.

Rules covered (see ``skills/style-review/references/rule-detectors.md``):
  RULE-B  em/en-dash casual use (excludes numeric ranges and paired names)
  RULE-D  overused sentence-initial transition openers from the six-item rule list
  RULE-G  heading title-case per RULE-G's own convention (lowercase articles,
          short prepositions, coordinating conjunctions; capitalize everything else)
  RULE-I  contractions in formal prose
  RULE-05 dying metaphors / clichés (regex against a small cliché list derived
          from Orwell 1946 and the rule's BAD examples)
  RULE-06 avoidable jargon (regex against a 54-entry list: the 45-word banned
          AI-tell list adjacent to RULE-06 plus 9 forms of 3 RULE-06 callouts)
  RULE-12 sentence length > 30 words

Plus a single "banned AI-tell list" detector which is covered under RULE-06's
mechanical pass (the banned list IS the jargon surface we check against).

Each detector takes a parsed Rule record, the file text, and the file path, and
returns a RuleResult with zero or more Violation entries.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from typing import Callable

from agent_style.review.loader import Rule
from agent_style.review.primitive import RuleResult, Violation


# ---------- Rule dispatch ---------------------------------------------------


def run(rule: Rule, text: str, file_path: str) -> RuleResult:
    """Dispatch to the detector for ``rule.id``; return the RuleResult."""
    func = _DISPATCH.get(rule.id)
    if func is None:
        return RuleResult(
            rule=rule.id,
            severity=rule.severity,
            detector="mechanical",
            status="skipped",
            count=0,
            note=f"no mechanical detector registered for {rule.id}",
        )
    violations = func(text)
    status = "violation" if violations else "ok"
    return RuleResult(
        rule=rule.id,
        severity=rule.severity,
        detector="mechanical",
        status=status,
        count=len(violations),
        violations=violations,
    )


# ---------- Helpers ---------------------------------------------------------


def _excerpt(line_text: str, span: tuple[int, int], width: int = 120) -> str:
    """Return up to ``width`` chars of the line around the match span."""
    start = max(0, span[0] - 20)
    end = min(len(line_text), start + width)
    out = line_text[start:end].strip()
    if start > 0:
        out = "…" + out
    if end < len(line_text):
        out = out + "…"
    return out


_LINE_BREAK_RE = re.compile(r"\r\n|[\n\r]")


def _line_spans(text: str) -> list[tuple[int, int]]:
    """Return the (start, end) offset of each line, aligned 1:1 with splitlines().

    ``str.splitlines`` recognises CR, LF and CRLF. Any offset arithmetic that
    locates a match inside ``text`` has to recognise the same three, or a CRLF
    pair costs one character and a bare CR costs a whole line break, shifting
    every line and column reported after it.
    """
    spans: list[tuple[int, int]] = []
    pos = 0
    for match in _LINE_BREAK_RE.finditer(text):
        spans.append((pos, match.start()))
        pos = match.end()
    if pos < len(text):
        spans.append((pos, len(text)))
    return spans


def _iter_lines(text: str):
    """Yield (line_no, col_start, line_text) for each line (1-indexed)."""
    for i, (start, end) in enumerate(_line_spans(text), start=1):
        yield i, start, text[start:end]


def _inside_code_fence(lines: list[str], target_idx: int) -> bool:
    """True if ``target_idx`` (0-based line index) is inside a fenced code block."""
    fence_open = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence_open = not fence_open
        if i == target_idx:
            return fence_open
    return False


def _inside_inline_code(line: str, col: int) -> bool:
    """True if the column offset is inside a `backtick` span on that line."""
    ticks = 0
    for i, ch in enumerate(line):
        if ch == "`":
            ticks += 1
        if i == col:
            break
    return (ticks % 2) == 1


# ---------- RULE-B em/en-dash casual use ------------------------------------


# En-dash used as numeric range: preceding digit and following digit.
_NUMERIC_EN_DASH = re.compile(r"(?<=\d)[\u2013](?=\d)")

# Letter-only tokens immediately before and after a candidate paired-name dash.
_LETTER_TOKEN_END = re.compile(r"[^\W\d_]+$")
_LETTER_TOKEN_START = re.compile(r"^[^\W\d_]+")

# Any em-dash or en-dash we want to flag (we subtract allowed en-dashes).
_ANY_DASH = re.compile(r"[\u2014\u2013]")


def _is_paired_name_en_dash(line: str, col: int) -> bool:
    """Return whether ``col`` joins two capitalized name tokens with an en dash."""
    if line[col] != "\u2013":
        return False
    left = _LETTER_TOKEN_END.search(line[:col])
    right = _LETTER_TOKEN_START.match(line[col + 1 :])
    return bool(left and right and left.group()[0].isupper() and right.group()[0].isupper())


def _rule_b(text: str) -> list[Violation]:
    """Flag em or en dashes used as casual sentence punctuation.

    Excludes:
      - en-dashes in numeric ranges (e.g. 2022–2026)
      - en-dashes in paired names (e.g. Cauchy–Schwarz)
      - anything inside code fences or inline backtick spans
    """
    lines_all = text.splitlines()
    out: list[Violation] = []
    for line_no, _col0, line in _iter_lines(text):
        if _inside_code_fence(lines_all, line_no - 1):
            continue
        # Build allow-list: positions of legitimate joining en-dashes on this line.
        allowed = {m.start() for m in _NUMERIC_EN_DASH.finditer(line)}
        for m in _ANY_DASH.finditer(line):
            if m.start() in allowed or _is_paired_name_en_dash(line, m.start()):
                continue
            if _inside_inline_code(line, m.start()):
                continue
            out.append(
                Violation(
                    rule="RULE-B",
                    line=line_no,
                    column=m.start() + 1,
                    excerpt=_excerpt(line, (m.start(), m.end())),
                    detail=f"{'em' if m.group() == '\u2014' else 'en'}-dash as casual punctuation",
                )
            )
    return out


# ---------- RULE-D transition openers ---------------------------------------


_TRANSITION_OPENERS = (
    "Additionally",
    "Furthermore",
    "Moreover",
    "In addition",
    "What's more",
    "Notably",
)
_TRANSITION_SENTENCE_RE = re.compile(
    r"(?:^|[.!?](?:[\"')\]]*)[ \t]+)(?:[\"'(]*)(?P<opener>"
    + "|".join(re.escape(t) for t in sorted(_TRANSITION_OPENERS, key=len, reverse=True))
    + r")(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)
_TRANSITION_ALLOWANCE_PER_PARAGRAPH = 1
# Markdown constructs that open a new block even without a blank line before
# them: an ATX heading, a table row, a thematic break, and each list item.
_BLOCK_BOUNDARY_RE = re.compile(
    r"^(?:#{1,6}[ \t]|\||(?:-{3,}|\*{3,}|_{3,})[ \t]*$|(?:[*+-]|\d+\.)[ \t])"
)


def _rule_d(text: str) -> list[Violation]:
    """Flag transition openers after the first one in each paragraph."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    paragraph_matches: list[tuple[int, int, str, str]] = []

    def flush_paragraph() -> None:
        total = len(paragraph_matches)
        excess_matches = paragraph_matches[_TRANSITION_ALLOWANCE_PER_PARAGRAPH:]
        for line_no, col, line, opener in excess_matches:
            out.append(
                Violation(
                    rule="RULE-D",
                    line=line_no,
                    column=col,
                    excerpt=_excerpt(line, (col - 1, col - 1 + len(opener))),
                    detail=(
                        f"overused transition opener '{opener}' "
                        f"({total} in paragraph; first is allowed)"
                    ),
                )
            )
        paragraph_matches.clear()

    for line_no, _col0, line in _iter_lines(text):
        if not line.strip():
            flush_paragraph()
            continue
        if (
            line.lstrip().startswith(("```", "~~~"))
            or _inside_code_fence(lines_all, line_no - 1)
        ):
            flush_paragraph()
            continue
        stripped = line.lstrip()
        prefix_len = len(line) - len(stripped)
        # Test the boundary on the text inside any blockquote, not on the raw
        # line: `> ## Heading` and `> - item` open new blocks just as their
        # unquoted forms do, and matching before the `>` is stripped misses them.
        unquoted = re.sub(r"^>+\s*", "", stripped)
        if _BLOCK_BOUNDARY_RE.match(unquoted):
            # A heading, table row, thematic break or new list item starts a new
            # block. Without this the one-transition allowance leaks across the
            # boundary, so `Additionally, first.` under one heading makes
            # `Moreover, second.` under the next read as the paragraph's second
            # opener.
            flush_paragraph()
        after_markup = re.sub(r"^(>+\s*|[*-]\s+)+", "", stripped)
        if not after_markup.strip():
            # A markup-only line (a bare ">" inside a blockquote, or a lone
            # bullet marker) separates paragraphs just as a blank line does.
            flush_paragraph()
            continue
        content_offset = prefix_len + len(stripped) - len(after_markup)
        for match in _TRANSITION_SENTENCE_RE.finditer(after_markup):
            opener = match.group("opener")
            col = content_offset + match.start("opener") + 1
            if not _inside_inline_code(line, col - 1):
                paragraph_matches.append((line_no, col, line, opener))
    flush_paragraph()
    return out


# ---------- RULE-G title-case headings --------------------------------------


# Words always lowercase in title case, exactly as enumerated by RULE-G.
_LC_WORDS = frozenset(
    {
        "a", "an", "the", "and", "but", "or", "nor", "of", "in", "on",
        "to", "for", "by", "at", "with",
    }
)

_QUESTION_OPENERS = frozenset(
    {"how", "what", "when", "where", "which", "who", "whom", "whose", "why"}
)
_FINITE_AUXILIARIES = frozenset(
    {
        "am", "are", "is", "was", "were", "do", "does", "did", "have",
        "has", "had", "can", "could", "may", "might", "must", "shall",
        "should", "will", "would",
    }
)
_HEADING_TOKEN_RE = re.compile(
    r"\.?[A-Za-z0-9](?:[A-Za-z0-9'./\\:_-]*[A-Za-z0-9])?"
)
_VERSION_RE = re.compile(
    r"v?\d+(?:\.\d+)+(?:[-+][A-Za-z0-9.-]+)?$", re.IGNORECASE
)
_FILE_NAME_RE = re.compile(r"\.?[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,10}$")
_UPPER_ID_RE = re.compile(r"[A-Z]{2,}-[A-Z0-9]+$")


def _strip_heading_markup(text: str) -> str:
    """Remove heading content whose spelling must be preserved verbatim."""
    text = re.sub(r"(`+)[^`\n]*?\1", "", text)
    text = re.sub(
        r"!?\[[^\]\n]*\](?:\([^\)\n]*\)|\[[^\]\n]*\])?", "", text
    )
    return re.sub(r"<[^>\n]+>", "", text)


def _is_sentence_style_heading(text: str) -> bool:
    """Recognize question-form and conservatively identifiable full sentences."""
    visible = _strip_heading_markup(text).strip()
    if re.search(r"[.?!](?:[\"')\]}*_]+)?$", visible):
        return True
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", visible)
    if not words:
        return False
    lowered = [word.lower() for word in words]
    return lowered[0] in _QUESTION_OPENERS or any(
        word in _FINITE_AUXILIARIES for word in lowered
    )


def _token_cannot_carry_case(token: str) -> bool:
    """Return True for identifiers whose spelling title case must not alter."""
    return (
        token[0].isdigit()
        or bool(_VERSION_RE.fullmatch(token))
        or bool(_UPPER_ID_RE.fullmatch(token))
        or token.startswith(".")
        or "/" in token
        or "\\" in token
        or "_" in token
        or bool(_FILE_NAME_RE.fullmatch(token))
    )


def _rule_g(text: str) -> list[Violation]:
    """Flag Markdown headings that violate RULE-G title case."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    for line_no, _col0, line in _iter_lines(text):
        if _inside_code_fence(lines_all, line_no - 1):
            continue
        m = re.match(r"^\s*(#{1,6})\s+(.*?)(?:\s+#*\s*)?$", line)
        if not m:
            continue
        heading_text = m.group(2).strip()
        if not heading_text:
            continue
        if _is_sentence_style_heading(heading_text):
            continue
        cleaned = _strip_heading_markup(heading_text)
        tokens = [
            token for token in _HEADING_TOKEN_RE.findall(cleaned)
            if any(char.isalpha() for char in token)
        ]
        if not tokens:
            continue
        problem: list[str] = []
        for idx, tok in enumerate(tokens):
            if _token_cannot_carry_case(tok):
                continue
            is_first = (idx == 0)
            is_last = (idx == len(tokens) - 1)
            parts = tok.split("-")
            for part_idx, part in enumerate(parts):
                if not part or _token_cannot_carry_case(part):
                    continue
                part_is_first = is_first and part_idx == 0
                part_is_last = is_last and part_idx == len(parts) - 1
                should_be_lc = (
                    part.lower() in _LC_WORDS
                    and not part_is_first
                    and not part_is_last
                )
                if should_be_lc:
                    valid = part == part.lower()
                else:
                    valid = _is_titlecased(part)
                if not valid:
                    problem.append(tok)
                    break
        if problem:
            out.append(
                Violation(
                    rule="RULE-G",
                    line=line_no,
                    column=1,
                    excerpt=_excerpt(line, (0, len(line))),
                    detail=f"heading not in title case; violating tokens: {', '.join(problem)}",
                )
            )
    return out


def _is_titlecased(word: str) -> bool:
    """Return True if ``word`` begins with an uppercase letter."""
    if not word:
        return True
    # Capitalized: first letter upper, rest may be mixed (acronyms, "RULES.md", etc.)
    return word[0].isupper()


# ---------- RULE-I contractions ---------------------------------------------


# Ambiguous 's and 'd endings require closed host-word lists.
_CONTRACTION_RE = re.compile(
    r"\b(?:(?:it|that|he|she|there|here|what|who|where|when|how|let)'s|"
    r"(?:i|you|he|she|it|we|they|that|who|what|which|why|there|where|how)'d|"
    r"[A-Za-z]+n't|[A-Za-z]+'(?:re|ll|ve|m))\b",
    re.IGNORECASE,
)


def _rule_i(text: str) -> list[Violation]:
    """Flag contractions outside code spans."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    for line_no, _col0, line in _iter_lines(text):
        if _inside_code_fence(lines_all, line_no - 1):
            continue
        for m in _CONTRACTION_RE.finditer(line):
            if _inside_inline_code(line, m.start()):
                continue
            out.append(
                Violation(
                    rule="RULE-I",
                    line=line_no,
                    column=m.start() + 1,
                    excerpt=_excerpt(line, (m.start(), m.end())),
                    detail=f"contraction '{m.group()}'",
                )
            )
    return out


# ---------- RULE-12 sentence length > 30 words ------------------------------


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'\(\[])")


def _rule_12(text: str) -> list[Violation]:
    """Flag sentences longer than 30 words."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    for line_no, _col0, line in _iter_lines(text):
        if _inside_code_fence(lines_all, line_no - 1):
            continue
        # Skip headings and list markup lines.
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|"):
            continue
        # Split into sentences and count words per sentence.
        for sentence in _SENTENCE_SPLIT_RE.split(stripped):
            words = re.findall(r"\b[\w'-]+\b", sentence)
            if len(words) > 30:
                out.append(
                    Violation(
                        rule="RULE-12",
                        line=line_no,
                        column=1,
                        excerpt=_excerpt(sentence, (0, len(sentence))),
                        detail=f"sentence length {len(words)} words (>30)",
                    )
                )
    return out


# ---------- RULE-05 dying metaphors / clichés -------------------------------
# Small, conservative cliché list drawn from Orwell 1946 and the RULE-05 BAD
# examples in RULES.md. Kept short to keep false-positive rate low; the
# semantic pass catches novel clichés.

_CLICHE_PHRASES = [
    "ring the changes",
    "take up the cudgels",
    "toe the line",
    "ride roughshod over",
    "stand shoulder to shoulder with",
    "play into the hands of",
    "no axe to grind",
    "grist to the mill",
    "fishing in troubled waters",
    "at the end of the day",
    "think outside the box",
    "level playing field",
    "low-hanging fruit",
    "paradigm shift",
    "moving the needle",
    "push the envelope",
    "circle back",
    "deep dive",
    "cutting-edge",
    "state of the art",
    "state-of-the-art",
    "paves the way",
    "pave the way",
    "a novel",
    "novel approach",
    "novel framework",
    "novel method",
    "novel optimization",
    "advance the state of the art",
    "game-changer",
    "game changer",
    "significant step forward",
    "paradigm-shifting",
    "best-in-class",
    "world-class",
    "next-generation",
    "next generation",
]
_CLICHE_PATTERNS = tuple(
    (
        phrase,
        re.compile(
            r"(?<![A-Za-z0-9_])" + re.escape(phrase) + r"(?![A-Za-z0-9_])",
            re.IGNORECASE,
        ),
    )
    for phrase in _CLICHE_PHRASES
)


def _rule_05(text: str) -> list[Violation]:
    """Flag cliché phrases (small conservative list)."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    spans = _line_spans(text)
    starts = [start for start, _ in spans]
    for phrase, pattern in _CLICHE_PATTERNS:
        for match in pattern.finditer(text):
            idx = match.start()
            # Locate the match against the same CR/LF/CRLF line model that
            # produced ``lines_all``. Counting only "\n" here would put a match
            # after a bare CR on the wrong line, and disagree with the fence
            # mask indexed just below.
            line_no = bisect.bisect_right(starts, idx)
            line_start, line_end = spans[line_no - 1]
            col = idx - line_start + 1
            if not _inside_code_fence(lines_all, line_no - 1):
                line_text = text[line_start:line_end]
                if not _inside_inline_code(line_text, col - 1):
                    out.append(
                        Violation(
                            rule="RULE-05",
                            line=line_no,
                            column=col,
                            excerpt=_excerpt(line_text, (col - 1, col - 1 + len(phrase))),
                            detail=f"cliché phrase '{phrase}'",
                        )
                    )
    return out


# ---------- RULE-06 avoidable jargon ----------------------------------------
# This 54-entry list combines the 45-word banned AI-tell list from
# .agent-config AGENTS.md Writing Defaults with 9 forms of 3 RULE-06
# BAD-example callouts. It is both the RULE-06 jargon surface and the
# "banned AI-tell list" detector.

_JARGON_WORDS = [
    # 45-word banned AI-tell list
    "encompass", "burgeoning", "pivotal", "realm", "keen", "adept", "endeavor",
    "uphold", "imperative", "profound", "ponder", "cultivate", "hone", "delve",
    "embrace", "pave", "embark", "monumental", "scrutinize", "vast", "versatile",
    "paramount", "foster", "necessitates", "provenance", "multifaceted", "nuance",
    "obliterate", "articulate", "acquire", "underpin", "underscore", "harmonize",
    "garner", "undermine", "gauge", "facet", "bolster", "groundbreaking",
    "game-changing", "reimagine", "turnkey", "intricate", "trailblazing",
    "unprecedented",
    # 9 forms of 3 jargon terms called out in RULE-06 BAD examples
    "leverages", "leveraging", "leverage",
    "utilize", "utilizes", "utilizing",
    "facilitate", "facilitates", "facilitating",
]

_JARGON_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in sorted(set(_JARGON_WORDS), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _rule_06(text: str) -> list[Violation]:
    """Flag the 54 avoidable-jargon and AI-tell entries."""
    out: list[Violation] = []
    lines_all = text.splitlines()
    for line_no, _col0, line in _iter_lines(text):
        if _inside_code_fence(lines_all, line_no - 1):
            continue
        for m in _JARGON_RE.finditer(line):
            if _inside_inline_code(line, m.start()):
                continue
            out.append(
                Violation(
                    rule="RULE-06",
                    line=line_no,
                    column=m.start() + 1,
                    excerpt=_excerpt(line, m.span()),
                    detail=f"jargon / AI-tell '{m.group()}'",
                )
            )
    return out


# ---------- Dispatch table --------------------------------------------------


_DISPATCH: dict[str, Callable[[str], list[Violation]]] = {
    "RULE-B": _rule_b,
    "RULE-D": _rule_d,
    "RULE-G": _rule_g,
    "RULE-I": _rule_i,
    "RULE-12": _rule_12,
    "RULE-05": _rule_05,
    "RULE-06": _rule_06,
}
