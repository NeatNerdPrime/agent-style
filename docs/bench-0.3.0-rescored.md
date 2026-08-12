# agent-style bench v0.3.0: corrected-engine re-score

This report re-scores the 160 committed drafts in `docs/bench-0.3.0-drafts/` at tree `a405f980e87becefbbc118495a775d2642ec5d31`, verified clean against the index before scoring. It makes no model calls and generates no new prose. Original values come from the four published runner scorecards. Corrected values use the review engine in this clone.

The replay uses the original harness and its exact scoring invocation: `agent-style review --mechanical-only --audit-only`. Delta is treatment minus baseline. A negative delta means fewer flagged violations in the treatment drafts. Change in delta is corrected minus original.

One-command re-run: `python scripts/bench/rescore.py`. It performs only local scoring. Add `--verify-repeat` to require two matching replay passes before the report is written.

## Scoring scope

Mechanically scored rules: `RULE-05`, `RULE-06`, `RULE-12`, `RULE-B`, `RULE-D`, `RULE-G`, `RULE-I`.

Rules with no scored component under `--mechanical-only`, each reported with `status: skipped`: `RULE-01`, `RULE-02`, `RULE-03`, `RULE-04`, `RULE-07`, `RULE-08`, `RULE-09`, `RULE-10`, `RULE-11`, `RULE-A`, `RULE-C`, `RULE-E`, `RULE-F`, `RULE-H`. A skipped rule is shown as `skipped`, not numeric zero. `RULE-05` and `RULE-06` also emit a separate semantic component with `status: skipped`; their mechanical components are included in the totals.

`RULE-A` is provisional because its structural detector is being revised in parallel. It remains skipped in this mechanical replay, so its interim detector behavior cannot affect any total below.

## Totals

| Runner | Original baseline | Original treatment | Original delta | Corrected baseline | Corrected treatment | Corrected delta | Change in delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude | 105 | 58 | -47 | 91 | 48 | **-43** | +4 |
| Codex | 51 | 28 | -23 | 49 | 26 | -23 | 0 |
| Copilot | 61 | 63 | +2 | 59 | 60 | **+1** | -1 |
| Gemini | 79 | 14 | -65 | 73 | 12 | **-61** | +4 |
| **Pooled** | **296** | **163** | **-133** | **272** | **146** | **-126** | **+7** |

## Rule deltas that moved

| Runner | Rule | Original delta | Corrected delta | Change in delta |
| --- | --- | ---: | ---: | ---: |
| Claude | RULE-B | -27 | **-26** | **+1** |
| Claude | RULE-I | -4 | **-1** | **+3** |
| Copilot | RULE-I | +1 | **0** | **-1** |
| Gemini | RULE-05 | -2 | **-3** | **-1** |
| Gemini | RULE-I | -6 | **-1** | **+5** |

## Full per-rule scorecard

`O` is original and `C` is corrected. Bold corrected values changed. The asterisk on `RULE-A` marks its provisional detector.

| Rule | Claude O | Claude C | Codex O | Codex C | Copilot O | Copilot C | Gemini O | Gemini C |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RULE-01 | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-02 | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-03 | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-04 | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-05 | 0 | 0 | 0 | 0 | 0 | 0 | -2 | **-3** |
| RULE-06 | 0 | 0 | 0 | 0 | 0 | 0 | -13 | -13 |
| RULE-07 | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-08 | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-09 | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-10 | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-11 | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-12 | -17 | -17 | -23 | -23 | +2 | +2 | -34 | -34 |
| RULE-A* | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-B | -27 | **-26** | 0 | 0 | 0 | 0 | -8 | -8 |
| RULE-C | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-D | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| RULE-E | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-F | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-G | +1 | +1 | 0 | 0 | -1 | -1 | -2 | -2 |
| RULE-H | skipped | skipped | skipped | skipped | skipped | skipped | skipped | skipped |
| RULE-I | -4 | **-1** | 0 | 0 | +1 | **0** | -6 | **-1** |

## Count corrections hidden by unchanged deltas

These rule deltas stayed fixed only because baseline and treatment counts moved by the same amount.

| Runner | Rule | Original baseline / treatment | Corrected baseline / treatment | Delta |
| --- | --- | ---: | ---: | ---: |
| Codex | RULE-I | 2 / 2 | 0 / 0 | 0 |

## Interpretation

The pooled delta changes from -133 to -126, a movement of +7 violations. The rescore changes the measurement of saved prose only. It does not rerun model generation, resolve runner instruction-loading caveats, or measure any skipped rule.

These are directional benchmark counts, not a claim of statistical significance or overall writing quality.
