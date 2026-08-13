// SPDX-License-Identifier: MIT
'use strict';
/**
 * Mechanical detectors. Deterministic regex / word-list rules.
 * Mirrors agent_style.review.detectors_mech in the Python package.
 * Must produce byte-identical counts + line numbers + excerpts as Python
 * for --cli-parity to stay at 12/12.
 */

// ---------- Entry point ----------------------------------------------------

function run(rule, text, filePath) {
  const fn = DISPATCH[rule.id];
  if (!fn) {
    return {
      rule: rule.id,
      severity: rule.severity,
      detector: 'mechanical',
      status: 'skipped',
      count: 0,
      note: `no mechanical detector registered for ${rule.id}`,
      violations: [],
    };
  }
  const violations = fn(text);
  return {
    rule: rule.id,
    severity: rule.severity,
    detector: 'mechanical',
    status: violations.length > 0 ? 'violation' : 'ok',
    count: violations.length,
    note: '',
    violations,
  };
}

// ---------- Helpers --------------------------------------------------------

function excerpt(lineText, span, width = 120) {
  const [s, e] = span;
  let start = Math.max(0, s - 20);
  let end = Math.min(lineText.length, start + width);
  let out = lineText.slice(start, end).trim();
  if (start > 0) out = '\u2026' + out;
  if (end < lineText.length) out = out + '\u2026';
  return out;
}

const LINE_BREAK_RE = /\r\n|[\n\r]/g;

// (start, end) offset of each line under the same CR/LF/CRLF model the line
// splitter uses. Advancing by `line.length + 1` instead is one character short
// after every CRLF, which shifts every offset reported past it.
function lineSpans(text) {
  const spans = [];
  let pos = 0;
  LINE_BREAK_RE.lastIndex = 0;
  let m;
  while ((m = LINE_BREAK_RE.exec(text)) !== null) {
    spans.push([pos, m.index]);
    pos = m.index + m[0].length;
  }
  if (pos < text.length) spans.push([pos, text.length]);
  return spans;
}

function* iterLines(text) {
  const spans = lineSpans(text);
  for (let i = 0; i < spans.length; i++) {
    yield [i + 1, spans[i][0], text.slice(spans[i][0], spans[i][1])];
  }
}

function fenceMaskForLineIdx(lines, targetIdx) {
  let fenceOpen = false;
  for (let i = 0; i < lines.length; i++) {
    const stripped = lines[i].replace(/^\s+/, '');
    if (stripped.startsWith('```') || stripped.startsWith('~~~')) {
      fenceOpen = !fenceOpen;
    }
    if (i === targetIdx) return fenceOpen;
  }
  return false;
}

function insideInlineCode(line, col) {
  let ticks = 0;
  for (let i = 0; i < line.length; i++) {
    if (line[i] === '`') ticks++;
    if (i === col) break;
  }
  return ticks % 2 === 1;
}

// ---------- RULE-B em/en-dash ----------------------------------------------

const NUMERIC_EN_DASH = /(?<=\d)\u2013(?=\d)/g;
const LETTER_TOKEN_END = /\p{L}+$/u;
const LETTER_TOKEN_START = /^\p{L}+/u;
const ANY_DASH = /[\u2014\u2013]/g;

function isPairedNameEnDash(line, col) {
  if (line[col] !== '\u2013') return false;
  const left = line.slice(0, col).match(LETTER_TOKEN_END);
  const right = line.slice(col + 1).match(LETTER_TOKEN_START);
  if (!left || !right) return false;
  const leftInitial = Array.from(left[0])[0];
  const rightInitial = Array.from(right[0])[0];
  return leftInitial === leftInitial.toUpperCase()
    && leftInitial !== leftInitial.toLowerCase()
    && rightInitial === rightInitial.toUpperCase()
    && rightInitial !== rightInitial.toLowerCase();
}

function ruleB(text) {
  const linesAll = text.split(/\r\n|[\n\r]/);
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    // Allow-list: positions of legitimate joining en-dashes.
    const allowed = new Set();
    let m;
    const numRe = new RegExp(NUMERIC_EN_DASH.source, 'g');
    while ((m = numRe.exec(line)) !== null) allowed.add(m.index);
    const anyRe = new RegExp(ANY_DASH.source, 'g');
    while ((m = anyRe.exec(line)) !== null) {
      if (allowed.has(m.index) || isPairedNameEnDash(line, m.index)) continue;
      if (insideInlineCode(line, m.index)) continue;
      const isEm = m[0] === '\u2014';
      out.push({
        rule: 'RULE-B',
        line: lineNo,
        column: m.index + 1,
        excerpt: excerpt(line, [m.index, m.index + 1]),
        detail: `${isEm ? 'em' : 'en'}-dash as casual punctuation`,
      });
    }
  }
  return out;
}

// ---------- RULE-D transition openers --------------------------------------

const TRANSITION_OPENERS = [
  'Additionally', 'Furthermore', 'Moreover', 'In addition', "What's more", 'Notably',
];
const TRANSITION_SENTENCE_RE = new RegExp(
  '(?:^|[.!?](?:["\')\\]]*)[ \\t]+)(?:["\'(]*)(?<opener>' +
    [...TRANSITION_OPENERS].sort((a, b) => b.length - a.length)
      .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') +
    ')(?![A-Za-z0-9_-])',
  'gi'
);
const TRANSITION_ALLOWANCE_PER_PARAGRAPH = 1;
// Markdown constructs that open a new block even without a blank line before
// them: an ATX heading, a table row, a thematic break, and each list item.
const BLOCK_BOUNDARY_RE = /^(?:#{1,6}[ \t]|\||(?:-{3,}|\*{3,}|_{3,})[ \t]*$|(?:[*+-]|\d+\.)[ \t])/;

function ruleD(text) {
  const linesAll = text.split(/\r\n|[\n\r]/);
  const out = [];
  const paragraphMatches = [];
  function flushParagraph() {
    const total = paragraphMatches.length;
    for (const match of paragraphMatches.slice(TRANSITION_ALLOWANCE_PER_PARAGRAPH)) {
      const { lineNo, col, line, opener } = match;
      out.push({
        rule: 'RULE-D',
        line: lineNo,
        column: col,
        excerpt: excerpt(line, [col - 1, col - 1 + opener.length]),
        detail: `overused transition opener '${opener}' (${total} in paragraph; first is allowed)`,
      });
    }
    paragraphMatches.length = 0;
  }
  for (const [lineNo, , line] of iterLines(text)) {
    if (!line.trim()) {
      flushParagraph();
      continue;
    }
    if (/^\s*(?:```|~~~)/.test(line) || fenceMaskForLineIdx(linesAll, lineNo - 1)) {
      flushParagraph();
      continue;
    }
    const stripped = line.replace(/^\s+/, '');
    const prefixLen = line.length - stripped.length;
    // Test the boundary on the text inside any blockquote, not on the raw
    // line: `> ## Heading` and `> - item` open new blocks just as their
    // unquoted forms do, and matching before the `>` is stripped misses them.
    const unquoted = stripped.replace(/^>+\s*/, '');
    if (BLOCK_BOUNDARY_RE.test(unquoted)) {
      // A heading, table row, thematic break or new list item starts a new
      // block. Without this the one-transition allowance leaks across the
      // boundary, so `Additionally, first.` under one heading makes
      // `Moreover, second.` under the next read as the paragraph's second
      // opener.
      flushParagraph();
    }
    const afterMarkup = stripped.replace(/^(>+\s*|[*-]\s+)+/, '');
    if (!afterMarkup.trim()) {
      // A markup-only line (a bare ">" inside a blockquote, or a lone bullet
      // marker) separates paragraphs just as a blank line does.
      flushParagraph();
      continue;
    }
    const contentOffset = prefixLen + stripped.length - afterMarkup.length;
    const re = new RegExp(TRANSITION_SENTENCE_RE.source, 'gi');
    let match;
    while ((match = re.exec(afterMarkup)) !== null) {
      const opener = match.groups.opener;
      const openerOffset = match.index + match[0].lastIndexOf(opener);
      const col = contentOffset + openerOffset + 1;
      if (!insideInlineCode(line, col - 1)) {
        paragraphMatches.push({ lineNo, col, line, opener });
      }
    }
  }
  flushParagraph();
  return out;
}

// ---------- RULE-G title-case headings -------------------------------------

const LC_WORDS = new Set([
  'a','an','the','and','but','or','nor','of','in','on',
  'to','for','by','at','with',
]);

const QUESTION_OPENERS = new Set([
  'how','what','when','where','which','who','whom','whose','why',
]);
const FINITE_AUXILIARIES = new Set([
  'am','are','is','was','were','do','does','did','have','has','had','can',
  'could','may','might','must','shall','should','will','would',
]);
const HEADING_TOKEN_RE = /\.?[A-Za-z0-9](?:[A-Za-z0-9'./\\:_-]*[A-Za-z0-9])?/g;
const VERSION_RE = /^v?\d+(?:\.\d+)+(?:[-+][A-Za-z0-9.-]+)?$/i;
const FILE_NAME_RE = /^\.?[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,10}$/;
const UPPER_ID_RE = /^[A-Z]{2,}-[A-Z0-9]+$/;

function stripHeadingMarkup(text) {
  return text
    .replace(/(`+)[^`\n]*?\1/g, '')
    .replace(/!?\[[^\]\n]*\](?:\([^\)\n]*\)|\[[^\]\n]*\])?/g, '')
    .replace(/<[^>\n]+>/g, '');
}

function isSentenceStyleHeading(text) {
  const visible = stripHeadingMarkup(text).trim();
  if (/[.?!](?:["')\]}*_]+)?$/.test(visible)) return true;
  const words = visible.match(/[A-Za-z]+(?:'[A-Za-z]+)?/g) || [];
  if (words.length === 0) return false;
  const lowered = words.map((word) => word.toLowerCase());
  return QUESTION_OPENERS.has(lowered[0]) || lowered.some((word) => FINITE_AUXILIARIES.has(word));
}

function tokenCannotCarryCase(token) {
  return token[0] >= '0' && token[0] <= '9'
    || VERSION_RE.test(token)
    || UPPER_ID_RE.test(token)
    || token.startsWith('.')
    || token.includes('/')
    || token.includes('\\')
    || token.includes('_')
    || FILE_NAME_RE.test(token);
}

function ruleG(text) {
  const linesAll = text.split(/\r\n|[\n\r]/);
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    const m = line.match(/^\s*(#{1,6})\s+(.*?)(?:\s+#*\s*)?$/);
    if (!m) continue;
    const headingText = m[2].trim();
    if (!headingText) continue;
    if (isSentenceStyleHeading(headingText)) continue;
    const cleaned = stripHeadingMarkup(headingText);
    const tokens = (cleaned.match(HEADING_TOKEN_RE) || [])
      .filter((token) => /[A-Za-z]/.test(token));
    if (tokens.length === 0) continue;
    const problem = [];
    for (let idx = 0; idx < tokens.length; idx++) {
      const tok = tokens[idx];
      if (tokenCannotCarryCase(tok)) continue;
      const isFirst = idx === 0;
      const isLast = idx === tokens.length - 1;
      const parts = tok.split('-');
      for (let partIdx = 0; partIdx < parts.length; partIdx++) {
        const part = parts[partIdx];
        if (!part || tokenCannotCarryCase(part)) continue;
        const partIsFirst = isFirst && partIdx === 0;
        const partIsLast = isLast && partIdx === parts.length - 1;
        const shouldBeLc = LC_WORDS.has(part.toLowerCase()) && !partIsFirst && !partIsLast;
        const valid = shouldBeLc ? part === part.toLowerCase() : isTitlecased(part);
        if (!valid) {
          problem.push(tok);
          break;
        }
      }
    }
    if (problem.length > 0) {
      out.push({
        rule: 'RULE-G',
        line: lineNo,
        column: 1,
        excerpt: excerpt(line, [0, line.length]),
        detail: `heading not in title case; violating tokens: ${problem.join(', ')}`,
      });
    }
  }
  return out;
}

function isTitlecased(word) {
  if (!word) return true;
  return /[A-Z]/.test(word[0]);
}

// ---------- RULE-I contractions --------------------------------------------

// Ambiguous 's and 'd endings require closed host-word lists.
const CONTRACTION_RE = /\b(?:(?:it|that|he|she|there|here|what|who|where|when|how|let)'s|(?:i|you|he|she|it|we|they|that|who|what|which|why|there|where|how)'d|[A-Za-z]+n't|[A-Za-z]+'(?:re|ll|ve|m))\b/gi;

function ruleI(text) {
  const linesAll = text.split(/\r\n|[\n\r]/);
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    let m;
    const re = new RegExp(CONTRACTION_RE.source, 'gi');
    while ((m = re.exec(line)) !== null) {
      if (insideInlineCode(line, m.index)) continue;
      out.push({
        rule: 'RULE-I',
        line: lineNo,
        column: m.index + 1,
        excerpt: excerpt(line, [m.index, m.index + m[0].length]),
        detail: `contraction '${m[0]}'`,
      });
    }
  }
  return out;
}

// ---------- RULE-12 sentence length > 30 -----------------------------------

function rule12(text) {
  const linesAll = text.split(/\r\n|[\n\r]/);
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    const stripped = line.trim();
    if (!stripped || stripped.startsWith('#') || stripped.startsWith('|')) continue;
    // Two alternatives, mirroring _SENTENCE_SPLIT_RE in the Python engine.
    // First: the original conservative split on punct + space + Capital or
    // open-quote. Second: an inline-code opener, because technical prose
    // routinely starts a sentence with a code span, and without it two ordinary
    // sentences were counted as one over-long sentence.
    //
    // The code-span branch is guarded against the abbreviations that routinely
    // precede a code span: dotted initialisms (`e.g.`, `i.e.`) and the one-token
    // forms `vs.`, `cf.` and `Fig.`. Unguarded, any of them reads as a sentence
    // end and silently suppresses a genuine violation, trading a visible false
    // positive for an invisible false negative. `etc.` is deliberately absent:
    // mid-sentence it takes a comma, and at a sentence end it is a real boundary
    // a guard would wrongly merge.
    //
    // Both branches also handle Markdown emphasis on either side of the
    // boundary. The optional closing run absorbs markup after the punctuation,
    // because a sentence ending `.**` puts that markup between the period and
    // the whitespace. That run sits outside the lookbehind to stay identical to
    // the Python engine, which cannot express it inside one (`re` rejects a
    // variable-width lookbehind).
    //
    // Every markup opener lives in the SECOND branch so it inherits the
    // abbreviation guards. In the first branch they would bypass every guard,
    // and `e.g. *json*` would silently suppress a real violation.
    const sentences = stripped.split(
      /(?<=[.!?])(?:\*\*|__|\*|_|`)?\s+(?=[A-Z"'(\[])|(?<!\b(?:[A-Za-z]\.){2})(?<!\b(?:[Vv][Ss]|[Cc][Ff])\.)(?<!\b[Ff][Ii][Gg]\.)(?<=[.!?])(?:\*\*|__|\*|_|`)?\s+(?=[`*_])/,
    );
    for (const sentence of sentences) {
      const words = sentence.match(/\b[\w'-]+\b/g) || [];
      if (words.length > 30) {
        out.push({
          rule: 'RULE-12',
          line: lineNo,
          column: 1,
          excerpt: excerpt(sentence, [0, sentence.length]),
          detail: `sentence length ${words.length} words (>30)`,
        });
      }
    }
  }
  return out;
}

// ---------- RULE-05 clichés ------------------------------------------------

const CLICHE_PHRASES = [
  'ring the changes', 'take up the cudgels', 'toe the line', 'ride roughshod over',
  'stand shoulder to shoulder with', 'play into the hands of', 'no axe to grind',
  'grist to the mill', 'fishing in troubled waters', 'at the end of the day',
  'think outside the box', 'level playing field', 'low-hanging fruit',
  'paradigm shift', 'moving the needle', 'push the envelope', 'circle back',
  'deep dive', 'cutting-edge', 'state of the art', 'state-of-the-art',
  'paves the way', 'pave the way', 'a novel', 'novel approach', 'novel framework',
  'novel method', 'novel optimization', 'advance the state of the art',
  'game-changer', 'game changer', 'significant step forward', 'paradigm-shifting',
  'best-in-class', 'world-class', 'next-generation', 'next generation',
];

function rule05(text) {
  const linesAll = text.split(/\r\n|[\n\r]/);
  const spans = lineSpans(text);
  const starts = spans.map((s) => s[0]);
  const out = [];
  for (const phrase of CLICHE_PHRASES) {
    const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`(?<![A-Za-z0-9_])${escaped}(?![A-Za-z0-9_])`, 'gi');
    let match;
    while ((match = re.exec(text)) !== null) {
      const idx = match.index;
      // Locate the match against the same CR/LF/CRLF line model that produced
      // linesAll. Searching for "\n" alone puts a match that follows a bare CR
      // on the previous line and gives it that line's column.
      let lineNo = 1;
      for (let lo = 0, hi = starts.length; lo < hi; ) {
        const mid = (lo + hi) >> 1;
        if (starts[mid] <= idx) { lineNo = mid + 1; lo = mid + 1; } else hi = mid;
      }
      const [lineStart, lineEnd] = spans[lineNo - 1];
      const col = idx - lineStart + 1;
      if (!fenceMaskForLineIdx(linesAll, lineNo - 1)) {
        const lineText = text.slice(lineStart, lineEnd);
        if (!insideInlineCode(lineText, col - 1)) {
          out.push({
            rule: 'RULE-05',
            line: lineNo,
            column: col,
            excerpt: excerpt(lineText, [col - 1, col - 1 + phrase.length]),
            detail: `cliché phrase '${phrase}'`,
          });
        }
      }
    }
  }
  return out;
}

// ---------- RULE-06 jargon / banned AI-tell list ---------------------------

// This 54-entry list combines the 45-word banned AI-tell list with 9 forms of
// 3 RULE-06 BAD-example callouts.
const JARGON_WORDS = [
  // 45-word banned AI-tell list
  'encompass','burgeoning','pivotal','realm','keen','adept','endeavor',
  'uphold','imperative','profound','ponder','cultivate','hone','delve',
  'embrace','pave','embark','monumental','scrutinize','vast','versatile',
  'paramount','foster','necessitates','provenance','multifaceted','nuance',
  'obliterate','articulate','acquire','underpin','underscore','harmonize',
  'garner','undermine','gauge','facet','bolster','groundbreaking',
  'game-changing','reimagine','turnkey','intricate','trailblazing',
  'unprecedented',
  // 9 forms of 3 RULE-06 BAD-example callouts
  'leverages','leveraging','leverage',
  'utilize','utilizes','utilizing',
  'facilitate','facilitates','facilitating',
];
const JARGON_RE = new RegExp(
  '\\b(?:' +
    [...new Set(JARGON_WORDS)].sort((a, b) => b.length - a.length)
      .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') +
    ')\\b',
  'gi'
);

function rule06(text) {
  const linesAll = text.split(/\r\n|[\n\r]/);
  const out = [];
  for (const [lineNo, , line] of iterLines(text)) {
    if (fenceMaskForLineIdx(linesAll, lineNo - 1)) continue;
    let m;
    const re = new RegExp(JARGON_RE.source, 'gi');
    while ((m = re.exec(line)) !== null) {
      if (insideInlineCode(line, m.index)) continue;
      out.push({
        rule: 'RULE-06',
        line: lineNo,
        column: m.index + 1,
        excerpt: excerpt(line, [m.index, m.index + m[0].length]),
        detail: `jargon / AI-tell '${m[0]}'`,
      });
    }
  }
  return out;
}

// ---------- Dispatch -------------------------------------------------------

const DISPATCH = {
  'RULE-B': ruleB,
  'RULE-D': ruleD,
  'RULE-G': ruleG,
  'RULE-I': ruleI,
  'RULE-12': rule12,
  'RULE-05': rule05,
  'RULE-06': rule06,
};

// lineSpans is exported for the boundary tests: it is the detector's own
// CR/LF/CRLF line model, and `audit` normalises on read, so a direct-text
// caller is the only path that exercises it.
module.exports = { run, lineSpans };
