// SPDX-License-Identifier: MIT
'use strict';
/**
 * Fixture-driven tests for the Node review primitive. Mirror of the Python
 * tests in packages/pypi/tests/test_review_fixtures.py. Loads the same
 * fixture-prose/*.md + <name>.expected.json pairs and asserts per-rule counts
 * match byte-for-byte with the Python detectors.
 *
 * Uses node --test (stdlib; zero new runtime dependencies).
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const { audit } = require('../lib/review');
const { CLASSIFICATION } = require('../lib/review/primitive');

const FIXTURES_DIR = path.resolve(
  __dirname,
  '..',
  'data',
  'skills',
  'style-review',
  'references',
  'fixture-prose'
);

function listFixtures() {
  if (!fs.existsSync(FIXTURES_DIR)) return [];
  return fs
    .readdirSync(FIXTURES_DIR)
    .filter((f) => f.endsWith('.md'))
    .map((md) => ({
      name: md,
      md: path.join(FIXTURES_DIR, md),
      expected: path.join(FIXTURES_DIR, md.replace(/\.md$/, '.expected.json')),
    }))
    .filter((x) => fs.existsSync(x.expected))
    .sort((a, b) => a.name.localeCompare(b.name));
}

// Per-fixture count checks.
for (const fx of listFixtures()) {
  test(`audit matches expected for ${fx.name}`, () => {
    const expected = JSON.parse(fs.readFileSync(fx.expected, 'utf8'));
    const result = audit(fx.md, { mechanicalOnly: false, skillHost: false });

    assert.equal(
      result.totalViolations,
      expected.total_violations,
      `${fx.name}: expected ${expected.total_violations} total, got ${result.totalViolations}`
    );

    // Aggregate counts across buckets per rule id.
    const actualCounts = {};
    for (const rr of result.ruleResults) {
      if (rr.count > 0) actualCounts[rr.rule] = (actualCounts[rr.rule] || 0) + rr.count;
    }
    const expectedCounts = expected.per_rule_count || {};
    assert.deepEqual(
      sortObj(actualCounts),
      sortObj(expectedCounts),
      `${fx.name}: per-rule count mismatch`
    );

    // Semantic / deferred-structural rules must all be skipped.
    const skippedIds = new Set(
      result.ruleResults.filter((rr) => rr.status === 'skipped').map((rr) => rr.rule)
    );
    for (const rid of expected.expected_skipped_rules || []) {
      assert.ok(
        skippedIds.has(rid),
        `${fx.name}: expected rule ${rid} to be skipped but it was not`
      );
    }
  });
}

// Explicit regression guards matching the Python test file.
test('clean-control has zero violations', () => {
  const fx = path.join(FIXTURES_DIR, 'clean-control.md');
  if (!fs.existsSync(fx)) return;
  const result = audit(fx, { mechanicalOnly: false, skillHost: false });
  const triggered = result.ruleResults
    .filter((rr) => rr.status === 'violation')
    .map((rr) => [rr.rule, rr.detector, rr.count]);
  assert.deepEqual(triggered, [], `clean-control produced violations: ${JSON.stringify(triggered)}`);
});

test('messy-real-world: fenced `leverages` is not flagged as RULE-06', () => {
  const fx = path.join(FIXTURES_DIR, 'messy-real-world.md');
  if (!fs.existsSync(fx)) return;
  const result = audit(fx, { mechanicalOnly: false, skillHost: false });
  for (const rr of result.ruleResults) {
    if (rr.rule === 'RULE-06') {
      assert.equal(rr.count, 0, 'RULE-06 fired on fenced-code fixture');
    }
  }
});

test('audit (no skill host) skips all semantic rules', () => {
  const fx = path.join(FIXTURES_DIR, 'mixed.md');
  if (!fs.existsSync(fx)) return;
  const result = audit(fx, { mechanicalOnly: false, skillHost: false });
  const leaks = result.ruleResults.filter(
    (rr) => rr.detector === 'semantic' && rr.status === 'violation'
  );
  assert.equal(leaks.length, 0, 'semantic detectors should be skipped without skill host');
});

test('--mechanical-only excludes structural and semantic', () => {
  const fx = path.join(FIXTURES_DIR, 'mixed.md');
  if (!fs.existsSync(fx)) return;
  const result = audit(fx, { mechanicalOnly: true, skillHost: false });
  const leaks = result.ruleResults.filter(
    (rr) => rr.detector !== 'mechanical' && rr.status === 'violation'
  );
  assert.equal(
    leaks.length,
    0,
    `mechanical-only leaked non-mechanical violations: ${leaks.map((l) => l.rule).join(', ')}`
  );
});

test('RULE-07 classification includes structural and semantic', () => {
  assert.deepEqual(
    [...CLASSIFICATION['RULE-07']].sort(),
    ['semantic', 'structural']
  );
});

function sortObj(obj) {
  return Object.fromEntries(Object.entries(obj).sort(([a], [b]) => a.localeCompare(b)));
}

// ---------------------------------------------------------------------------
// Exact-object boundary tests. Mirror of the Python cases in
// packages/pypi/tests/test_review_fixtures.py.
//
// The fixture tests above assert per-rule counts only, so a false positive and
// a false negative for the same rule cancel out and the suite still passes. The
// cases below build their own input and assert the complete violation location,
// which is what makes them a regression oracle rather than a tally.
// ---------------------------------------------------------------------------

const os = require('os');
const { lineSpans } = require('../lib/review/detectors_mech');

let caseSeq = 0;

// Audit `text` through the public file path; return complete violations.
// Comparing whole objects rather than [line, column] is the point: RULE-A's
// `detail` string is part of the canonical JSON, so a change to it is a
// behavior change that a coordinate-only assertion would not catch.
function auditText(text, rule) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'agent-style-case-'));
  const target = path.join(dir, `case-${caseSeq++}.md`);
  fs.writeFileSync(target, Buffer.from(text, 'utf8'));
  const result = audit(target, { skillHost: false });
  return result.ruleResults
    .filter((rr) => rr.rule === rule)
    .flatMap((rr) => (rr.violations || []).map((v) => ({
      line: v.line, column: v.column, excerpt: v.excerpt, detail: v.detail,
    })));
}

// Coordinate-only view of auditText, for the many-case tables.
function auditTextAt(text, rule) {
  return auditText(text, rule).map((v) => [v.line, v.column]);
}

for (const [label, newline] of [['lf', '\n'], ['crlf', '\r\n'], ['cr', '\r']]) {
  test(`RULE-05 locates a cliche under ${label} line endings`, () => {
    const text = `prefix${newline}paradigm shift${newline}tail${newline}`;
    assert.deepEqual(
      auditText(text, 'RULE-05'),
      [{ line: 2, column: 1, excerpt: 'paradigm shift', detail: "cliché phrase 'paradigm shift'" }],
      `RULE-05 mislocated the cliche under ${label} line endings`
    );
  });

  // Go through the detector, not just its helper. `audit` normalises line
  // endings on read, so a direct-text caller is the only path that exercises
  // RULE-05's own offset arithmetic; asserting on lineSpans alone would still
  // pass if RULE-05 stopped consuming it.
  test(`RULE-05 handles ${label} line endings in direct text`, () => {
    const { run: runMech } = require('../lib/review/detectors_mech');
    const result = runMech(
      { id: 'RULE-05', severity: 'medium' },
      `prefix${newline}paradigm shift`,
      'memory.md'
    );
    assert.deepEqual(
      result.violations.map((v) => [v.line, v.column, v.detail]),
      [[2, 1, "cliché phrase 'paradigm shift'"]]
    );
  });
}

test('line spans handle mixed line endings in direct text', () => {
  for (const newline of ['\n', '\r\n', '\r']) {
    assert.deepEqual(
      lineSpans(`prefix${newline}paradigm shift`),
      [[0, 6], [6 + newline.length, 6 + newline.length + 14]],
      `line spans wrong for ${JSON.stringify(newline)}`
    );
  }
});

// RULE-A's directive names checklist steps as a genuine list. Shortness is not
// evidence, and neither is a repeated opening word; both describe these lists
// as much as they describe fragmented prose.
for (const [label, body] of [
  ['imperative checklist', '1. Stop the service.\n2. Rotate the credentials.\n3. Restart the workers.\n'],
  ['repeated-opener checklist', '1. Run the migration.\n2. Run the tests.\n3. Run the service.\n'],
  ['preposition-led enumeration', '- For Linux, use apt.\n- For macOS, use brew.\n- For Windows, use winget.\n'],
  ['uniform per enumeration', '- Per minute limits\n- Per user limits\n- Per region limits\n'],
  ['short independent labels', '- Linux\n- macOS\n- Windows\n'],
]) {
  test(`RULE-A leaves a genuine enumeration alone: ${label}`, () => {
    assert.deepEqual(auditText(`Heading:\n\n${body}`, 'RULE-A'), []);
  });
}

// Each of RULE-A's own BAD shapes must fire, at the first item's line.
for (const [label, body] of [
  ['connective shards', '- Training a contrastive embedder\n- Because this improves recall\n- Which matters downstream\n'],
  ['emphasis-wrapped connective', '- Training an embedder\n- **Because** this improves recall\n- **Which** matters\n'],
  ['leading and', '- A misconfigured load balancer rule\n- An outdated auth-v1 service\n- And insufficient alerting\n'],
  ['mixed per fragments', '- Free tier\n- 100 requests\n- Per minute\n- Per user\n'],
  ['repeated subject and copula', '- It is fast\n- It is accurate\n- It is easy to use\n'],
  ['numbered causal chain', '1. Because retrieval is hard\n2. Therefore we add reranking\n3. And this improves recall\n'],
]) {
  test(`RULE-A flags prose shredded into bullets: ${label}`, () => {
    assert.deepEqual(auditTextAt(`Heading:\n\n${body}`, 'RULE-A'), [[3, 1]]);
  });
}

test('RULE-A strong signal survives a long item', () => {
  const body =
    '- Training a contrastive embedder on a very large corpus of documents\n' +
    '- Because this improves recall\n' +
    '- Which matters downstream\n';
  assert.deepEqual(auditTextAt(`Heading:\n\n${body}`, 'RULE-A'), [[3, 1]]);
});

// ---------------------------------------------------------------------------
// List-container and block-boundary cases. Mirror of the Python block.
//
// These were verified in a local matrix before they were committed, which is
// exactly the gap this block closes: an uncommitted matrix cannot stop the next
// edit from regressing them.
// ---------------------------------------------------------------------------

// A marker and an opening word are not evidence about list structure.
for (const [label, body] of [
  ['nested children not flattened into parent', '- Rate limits:\n  - Per minute\n  - Per user\n'],
  ['only one item is not a Per fragment', '- Global\n- Per user\n- Per project\n'],
  ['bare one-word connective labels', '- And\n- But\n- Or\n'],
]) {
  test(`RULE-A leaves a genuine list container alone: ${label}`, () => {
    assert.deepEqual(auditText(`Heading:\n\n${body}`, 'RULE-A'), []);
  });
}

// Breaking out of the group at the first deeper line turned this three-item
// parent list into groups of one and two, so its connective shards stopped
// being visible at all.
test('RULE-A parent list survives a nested block', () => {
  const body =
    '- Training a contrastive embedder\n' +
    '  - Local negatives\n' +
    '  - Hard negatives\n' +
    '- Because this improves recall\n' +
    '- Which matters downstream\n';
  assert.deepEqual(auditTextAt(`Heading:\n\n${body}`, 'RULE-A'), [[3, 1]]);
});

// Raw character length calls one space and one tab the same depth.
test('RULE-A treats one tab as deeper than one space', () => {
  const body =
    ' - Parent item\n' +
    '\t- Because nested reason\n' +
    '\t- Which nested consequence\n';
  assert.deepEqual(auditText(`Heading:\n\n${body}`, 'RULE-A'), []);
});

// Both land on column 4, so these are siblings and the shards are visible.
// Raw character length calls them depths 4 and 1, losing the positive.
test('RULE-A treats four spaces and one tab as the same depth', () => {
  const body =
    '    - Training a contrastive embedder\n' +
    '\t- Because this improves recall\n' +
    '\t- Which matters downstream\n';
  assert.deepEqual(auditTextAt(`Heading:\n\n${body}`, 'RULE-A'), [[3, 1]]);
});

// The one-transition allowance is per block, not per blank-line run.
for (const [label, body, expected] of [
  ['heading separates two prose blocks', 'Additionally, first.\n## Section\nMoreover, second.\n', []],
  ['adjacent list items are separate blocks', '- Additionally, first.\n- Moreover, second.\n', []],
  ['blockquoted heading separates blocks', '> Additionally, first.\n> ## Section\n> Moreover, second.\n', []],
  ['blockquoted list items are separate blocks', '> - Additionally, first.\n> - Moreover, second.\n', []],
  [
    'two openers in one real paragraph still fire',
    'The first passed. Additionally, the second passed. Furthermore, the third passed.\n',
    [[1, 52]],
  ],
]) {
  test(`RULE-D uses Markdown block boundaries: ${label}`, () => {
    assert.deepEqual(auditTextAt(body, 'RULE-D'), expected);
  });
}

// Two 20-word sentences are two sentences however the second one opens. The
// splitter required a capital, quote, `(` or `[`; prose opens sentences with an
// inline code span or with emphasis constantly, and none of those characters was
// in the class, so each pair scored as one 40-word violation that was not there.
// The capital case is the control: it always passed.
const TWENTY_A =
  'Alpha beta gamma delta epsilon zeta eta theta iota kappa ' +
  'lambda mu nu xi omicron pi rho sigma tau upsilon.';
const TWENTY_TAIL =
  'two three four five six seven eight nine ten ' +
  'eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty.';
const TWENTY_CAPITAL = `One ${TWENTY_TAIL}`;
for (const [label, second, expected] of [
  ['capital opener', TWENTY_CAPITAL, []],
  ['inline-code opener', `\`code\` ${TWENTY_TAIL}`, []],
  ['emphasis opener', `*Emphasized* ${TWENTY_TAIL}`, []],
  ['underscore opener', `_Emphasized_ ${TWENTY_TAIL}`, []],
]) {
  test(`RULE-12 splits a sentence whatever markup opens it: ${label}`, () => {
    assert.deepEqual(auditTextAt(`${TWENTY_A} ${second}`, 'RULE-12'), expected);
  });
}

// Markup after the final punctuation must not hide the boundary either. A
// sentence ending `.**` puts the closing delimiter between the period and the
// whitespace, so a lookbehind anchored on the punctuation never saw it, and
// every bolded CHANGELOG entry read as one sentence through the next one. Each
// case puts the punctuation INSIDE the delimiter, which is the broken shape; a
// period after a closing delimiter always split, so that proves nothing.
const TWENTY_LEAD = TWENTY_A.split(' ').slice(0, -1).join(' ').replace(/\.$/, '');
for (const closer of ['**', '__', '*', '_', '`']) {
  test(`RULE-12 splits when markup closes the first sentence: ${closer}`, () => {
    const text = `${closer}Strong ${TWENTY_LEAD}.${closer} Then ${TWENTY_CAPITAL}`;
    assert.deepEqual(auditTextAt(text, 'RULE-12'), []);
  });
}

// The looser split must not stop the rule from firing on a real violation.
test('RULE-12 still flags a genuinely long sentence', () => {
  const text = `${Array(35).fill('word').join(' ')}.`;
  assert.deepEqual(
    auditText(text, 'RULE-12').map((v) => v.detail),
    ['sentence length 35 words (>30)'],
  );
});

// An abbreviation before a formatted value is not a sentence boundary. Every
// markup opener lives in the guarded branch; putting them in the unguarded one
// looks equivalent and silently suppresses real violations after `e.g.` and
// friends. The matrix is what proves it: a guard applied to only one delimiter
// looks correct until another is tried. `etc.` is deliberately unguarded and so
// is absent, because at a sentence end it is a real boundary.
for (const [abbreviation, lead] of [
  ['e.g.', 'The command supports several output formats, e.g.'],
  ['vs.', 'The evaluation compares our primary system vs.'],
  ['Fig.', 'The evaluation trend appears in Fig.'],
  ['cf.', 'The report compares the alternate protocol, cf.'],
]) {
  for (const value of ['`json`', '*json*', '_json_', '**json**']) {
    test(`RULE-12 does not split ${abbreviation} before ${value}`, () => {
      const text =
        `${lead} ${value}, when automated consumers need stable fields for ` +
        'parsing, validation, archival, comparison, monitoring, and downstream ' +
        'reporting across multiple independent services during every nightly ' +
        'scheduled production run.';
      const words = (text.match(/\b[\w'-]+\b/g) || []).length;
      assert.ok(words > 30, 'fixture must exceed the threshold to be meaningful');
      assert.deepEqual(
        auditText(text, 'RULE-12').map((v) => v.detail),
        [`sentence length ${words} words (>30)`],
      );
    });
  }
}
