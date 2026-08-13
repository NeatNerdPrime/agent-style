<!-- SPDX-License-Identifier: CC-BY-4.0 -->

# Preregistration: does the effect of persistent writing rules decay across model generations?

> **Status: draft, not registered.** Written 2026-08-11. Nothing has been run and no API quota
> has been spent. The maintainer must still settle the open items in section 1 and approve the
> inference budget before this is registered anywhere.

## 1. Status, scope, and registration point

This document specifies the design only. Generation must not begin until item 1 in `PLAN-next3.md` has landed, the corrected scorer and the rule pack have immutable release identifiers, the Sonnet 5 endpoint has been frozen, the two control texts and 100 tasks have been archived with SHA-256 hashes, and this preregistration has a public timestamp. Any change after the first model call is an amendment and must be dated, justified, and separated from the confirmatory analysis.

The literature-gap claim in `PLAN-next3.md` is [UNVERIFIED] as an exhaustive novelty claim in this document. This worker directly verified only the paper needed to motivate the priming control. The experiment can be informative without claiming that no prior professional-writing experiment exists.

The confirmatory scope is narrow: content-specific compliance with seven mechanically detectable rules on a fixed professional-prose benchmark. The experiment does not, by itself, establish overall writing quality, universal instruction following, or a causal effect of model improvement. Blinded human ratings provide secondary evidence for the fourteen rules outside the deterministic endpoint.

## 2. Question and interpretable null

Among named checkpoints from the same model family, does the incremental benefit of the full persistent `agent-style` pack, relative to a token-matched but outcome-irrelevant competing pack, become smaller at the newer checkpoint when models write professional or technical prose?

For checkpoint (g), let (B_g) be the log mechanical-violation-rate advantage of the competing pack over the full pack:

\[
B_g = \log(R_{g,\mathrm{competing}}) - \log(R_{g,\mathrm{full}}),
\]

where (R) is the expected count of violations per 1,000 output words. Positive (B_g) means that the full pack reduces targeted violations. For an ordered within-family transition from old checkpoint (o) to new checkpoint (n), define decay as

\[
D_{o\rightarrow n} = B_o - B_n.
\]

Positive (D) is decay. The primary estimand is the equal-weight mean of the four prespecified within-family transition contrasts. The four possible conclusions are:

1. **Decay:** the two-sided 95% confidence interval for the mean (D) is wholly above zero.
2. **Stability within a practical margin:** the two one-sided 90% equivalence interval is wholly inside \([-\log(1.25), \log(1.25)]\). This margin treats a 25% multiplicative change in the full-versus-competing rate ratio as the smallest practically important shift.
3. **Reversal:** the two-sided 95% confidence interval is wholly below zero, meaning newer checkpoints benefit more.
4. **Imprecise null:** the interval crosses zero and is not inside the equivalence bounds.

All four outcomes will be published. A nonsignificant result will not be described as stability unless it passes the equivalence test.

## 3. Hypotheses

**H1, content-specific compliance.** At each checkpoint, the full pack will produce a lower seven-rule violation rate than the token-matched competing pack, so (B_g>0). The reason is direct: the full pack names the prohibited forms and desired structures that the scorer counts, whereas the competing pack does not.

**H2, generation decay.** The equal-weight mean (D) across the four transitions will be positive. The predicted reason is that a newer checkpoint may already avoid more of the targeted prose patterns without persistent rules, leaving less marginal room for the pack.

**H3, context priming.** The neutral and competing conditions will improve blinded overall-professionalism ratings relative to the bare prompt, but their improvement in target-rule compliance will be smaller than the full pack's. This direction follows the context-priming account in [Zhang et al. (2026), arXiv:2604.11088v2](https://arxiv.org/abs/2604.11088), whose abstract and paper report that random, shuffled, and mismatched-domain rule files matched curated rules on a coding benchmark. That paper used Claude Code with Opus 4.6 on SWE-bench Verified, so it motivates a control rather than establishing what will happen for prose.

**H4, quality transfer.** On the human-rated subsample, the full pack will improve equal-weight compliance with the fourteen nonmechanical rules and will not reduce overall writing quality relative to the competing pack. This is secondary. Mechanical compliance alone cannot support H4.

## 4. Models and permitted comparisons

All confirmatory generation uses the NAIRR gateway. Direct cross-family comparisons are descriptive only. Each decay contrast changes the checkpoint while holding the family and serving channel fixed.

| Series | Older checkpoint | Newer checkpoint | Confirmatory transition |
|---|---|---|---|
| Claude Opus | `claude-opus-4.8` (`vertex_ai/claude-opus-4-8`) | `claude-opus-5` (`vertex_ai/claude-opus-5`) | 4.8 to 5 |
| Claude Sonnet | `claude-sonnet-4.5` (`vertex_ai/claude-sonnet-4-5`) | `claude-sonnet-4.6` (`vertex_ai/claude-sonnet-4-6`) | 4.5 to 4.6 |
| Claude Sonnet | `claude-sonnet-4.6` | inventory name `claude-sonnet`, currently mapped to `vertex_ai/claude-sonnet-5` | 4.6 to 5, only after the alias is immutable |
| OpenAI GPT | `gpt-5.4`, Azure deployment version `2026-03-05` | `gpt-5.5`, Azure deployment version `2026-04-24` | 5.4 to 5.5 |

The seven distinct checkpoints therefore produce four transitions. The Sonnet 4.6 observations are reused in both adjacent Sonnet contrasts, and their covariance will be retained in the global contrast. The floating `claude-sonnet` alias is not admissible as currently configured. Before registration, the gateway operator must bind an immutable experiment label to `vertex_ai/claude-sonnet-5`, record the provider model identifier and configuration hash, and update the manifest. If this cannot be done, generation stops before any confirmatory call. There will be no substitution with a floating alias.

The gateway's `gemini` endpoint is excluded because it is Gemini 2.5 Pro and does not supply the required forward within-family generation comparison. Subscription CLIs are excluded because their model labels can float. Bedrock is not part of the confirmatory test because the inventory currently contains one checkpoint per open-weight family, not within-family generation pairs.

## 4a. Amendment, 2026-08-11: an open-weight arm with a cleaner instrument

This section was added after the rest of the design, when an enumeration of AWS Bedrock found
something the design had assumed did not exist. It changes which arm should be confirmatory, and the
maintainer has to settle that before registration.

**What was found.** Bedrock was believed to expose one model per family, which would make it useless
for a generation comparison. A full sweep of `us-east-1` and `us-west-2`, followed by eleven live
`Converse` calls costing under one cent in total, found four credit-eligible families with invokable
generation sets. The relevant one is Meta Llama:

| Step | Invocation ID | Scale |
|---|---|---|
| Llama 3 | `meta.llama3-70b-instruct-v1:0` | 70B |
| Llama 3.1 | `us.meta.llama3-1-70b-instruct-v1:0` | 70B |
| Llama 3.3 | `us.meta.llama3-3-70b-instruct-v1:0` | 70B |

**Why this matters to section 11.** The threat listed there as "checkpoint changes are bundled" is
the largest one this design cannot control on NAIRR: a vendor checkpoint moves training data,
post-training, scale, tokenization and serving together, so an observed decay cannot be attributed
to generation alone. The three Llama steps above hold scale and architecture fixed and move only the
generation. On internal validity, the open-weight series is the better instrument, and it draws on
ARA credit whose documented risk is expiring unused rather than overspend.

**The decision this forces.** Internal validity and external relevance point in opposite directions:

- If the claim is about model generations in general, run the confirmatory analysis on the Llama 70B
  series and treat the NAIRR Claude and GPT pairs as the external-validity arm. This is the stronger
  experiment and the cheaper one.
- If the claim is specifically about the frontier closed models people actually write with, NAIRR
  stays confirmatory despite the bundled-change confound, and Llama becomes a mechanism arm that
  isolates generation from scale.

**A design must follow the question, not the cleanest available data.** The maintainer decides which
question is being asked; nothing else in this document depends on the answer, because both arms use
the same tasks, conditions, controls and outcome measures.

**Not usable for a generation arm**, confirmed absent from the account rather than assumed: Qwen 2.5,
Gemma 2, and any `gpt-oss` release other than `1:0`. Two further steps change scale and architecture
at once and stay secondary in either design: Llama 3.3 70B to Llama 4 Scout 17B, and Mistral Large
24.07 to Mistral Large 3 at 675B.

## 5. Task set

The benchmark will contain exactly 100 prompts. The ten prompts in `scripts/bench/tasks.md` will be retained byte for byte to connect the new study to the archived benchmark. They comprise four short-form canaries, four academic tasks, and two long-form professional tasks. The earlier set was useful for a sanity check but was only ten tasks with two generations per condition. It is too small and too author-dependent for a generation-decay claim.

An independent researcher who is not an `agent-style` author and will not see condition outcomes will select or author 90 new prompts under the following fixed quotas:

| Stratum | Existing | New | Total | Required composition |
|---|---:|---:|---:|---|
| Short technical prose | 4 | 16 | 20 | Six PR descriptions, four commit or changelog entries, ten design, API, or runbook sections |
| Academic and scientific prose | 4 | 36 | 40 | Ten abstracts, ten methods sections, ten results or experiments sections, ten related-work sections |
| Long-form professional prose | 2 | 38 | 40 | Ten grant sections, ten product or technical descriptions, ten policy or decision memos, ten incident or evaluation reports |

Short tasks will normally request 75 to 180 words; the retained commit-message task keeps its existing length. Academic and long-form tasks will request 250 to 400 words. Every new prompt will name an audience and a concrete communicative purpose so that RULE-01 can be rated. Twenty tasks, distributed across the academic and long-form strata, will require source use and will include a frozen source packet so that RULE-H can be rated without asking raters to infer unverifiable facts. No task may quote, paraphrase, or mention the rule pack, its detector phrases, this hypothesis, or model names.

The selector will receive only these quotas, the output format, and an exclusion checklist. The selector will produce a candidate log, including rejected prompts and reasons. Before generation, the final XML-style task file, source packets, task-stratum map, and the unchanged ten-task subset will be hashed and archived. The 100-task size is chosen for both content breadth and power. It creates 200 observations per checkpoint-condition cell after two generations, while providing 100 task clusters rather than the old ten.

Results will be reported for all 100 tasks, the unchanged ten tasks, and the 90 new tasks. Only the 100-task result is confirmatory. The ten-task result is a continuity analysis, not an independent replication.

## 6. Conditions, randomization, and fixed factors

Each task-checkpoint pair has four conditions:

1. **Bare:** the task prompt only, with no experiment-supplied persistent instruction.
2. **Neutral:** the task plus the exact persistent instruction `Write clear, concise, professional prose.`
3. **Full pack:** the complete repository `RULES.md`, not a hand-selected subset. The currently read candidate is 91,634 characters and 13,439 whitespace-delimited tokens, SHA-256 `B2C1A3E71C41901A1230C1882DC962F7912E6D5BA9FBC4ED46ADE57FCC9F2205`. The final post-item-1 file and release commit must be frozen before registration; a changed hash requires an amendment.
4. **Competing pack:** 21 outcome-irrelevant software-process rules selected by the independent task selector from a source fixed before generation. It will mirror the full pack's heading count, directive plus example structure, character count within 2%, and whitespace-token count within 1%. Two reviewers will independently reject any competing rule that gives prose-style advice or semantically overlaps one of the 21 target rules. The final text, provenance, exclusions, and SHA-256 will be public. Provider-reported prompt-token counts will be reported as a manipulation check, not adjusted after outcomes are seen.

The neutral condition tests whether a generic quality instruction is sufficient. The competing condition is the first-class control for context priming and long-context burden. The full-versus-competing contrast estimates rule content after matching the presence, size, and presentation of a persistent pack. Competing-versus-bare estimates outcome-irrelevant context priming; neutral-versus-bare estimates short generic priming.

For every checkpoint-condition-task cell, obtain two independent generations. The complete manifest is therefore:

\[
100\text{ tasks}\times 4\text{ conditions}\times 2\text{ generations}\times 7\text{ checkpoints}=5,600\text{ successful outputs}.
\]

Before any call, generate the full call order with PCG64 seed `20260811`. Within each family-task-generation block, permute checkpoint and condition order, then interleave blocks so that no condition is concentrated at one time of day. Conditions receive opaque labels in saved filenames. A custodian who does not analyze outcomes retains the key.

The following are held fixed: task text, role placement, prompt wrapper, endpoint and region within family, decoding parameters, maximum output length, no tools, no retrieval, no conversational history, no prompt caching, and one independent request per output. Use `temperature=0.7`, `top_p=1`, and `max_output_tokens=768`. Use no model-specific prompt edits. If any checkpoint rejects a required common parameter, stop and amend before substantive generation rather than silently use a different setting. Complete the successful calls within a 72-hour window when feasible and retain request IDs, timestamps, exact model-returned identifiers, token usage, finish reasons, and raw responses.

## 7. Outcomes and measurement limits

### Primary outcome

The primary outcome is the total deterministic violation count per 1,000 output words for exactly these seven rules under the corrected, frozen engine: `RULE-05`, `RULE-06`, `RULE-12`, `RULE-B`, `RULE-D`, `RULE-G`, and `RULE-I`. The analysis also reports raw counts and word counts, because a pack may reduce counts partly by shortening prose.

This is seven of the 21 scorecard rules. In the archived original four-runner benchmark, `RULE-12`, `RULE-B`, and `RULE-06` contributed 120 of the pooled 133-violation movement, or 90.2%. Under the corrected re-score, the same three contributed 112 of 119, or 94.1%. Thus, approximately 90% of prior movement came from three of the seven measured rules. Both critical-severity rules, `RULE-01` on reader knowledge and `RULE-H` on citation discipline, are absent from the deterministic endpoint. The primary result must therefore be described as targeted mechanical compliance, not overall prose quality or full-pack compliance.

The engine release, source commit, rule-pack hash, scoring-source manifest hash, and scoring command will be frozen before generation. The manifest hash is the one `scripts/bench/rescore.py` records. It covers every path that can move a score. An earlier version of that tool hashed the mechanical detector alone, which left edits elsewhere invisible. Scoring occurs only after all raw outputs are saved. No threshold, regex, or task will be changed in response to observed outputs.

### Secondary deterministic outcomes

Secondary outcomes are the seven individual rule rates, output length, prompt length compliance, truncation, refusal or nonanswer rate, and the six additional condition contrasts needed to describe generic priming and bare-prompt performance. Per-rule tests use Benjamini-Hochberg false-discovery-rate control at 5% within the seven-rule family.

### Blinded human outcomes

Human review will cover exactly 1,400 outputs: 50 externally selected tasks, stratified as ten short, twenty academic, and twenty long-form professional, crossed with all seven checkpoints and all four conditions. For each cell, the manifest seed selects one of the two generations. Three qualified raters independently rate every selected output, producing 4,200 completed output-level judgments.

Raters see the task, any supplied source packet, and a response whose model and condition identifiers have been removed. They do not see the competing or full instruction text. They score:

1. each of the fourteen rules not in the deterministic primary endpoint as compliant, violated, or not applicable;
2. `RULE-01` and `RULE-H` separately, regardless of the composite;
3. overall professional writing quality on a 1 to 7 anchored scale;
4. task fulfillment and factual support on separate 1 to 7 scales.

The fourteen-rule compliance composite is the equal-weight proportion of applicable rules judged compliant. Critical rules receive separate estimates rather than author-chosen extra weights. Binary rule labels use majority vote. If fewer than two raters mark a rule applicable, or two applicable ratings disagree while the third is not applicable, a fourth blinded adjudicator resolves applicability and compliance. Overall ordinal scores use the median of three. Krippendorff's alpha and rule prevalence will be reported. If alpha is below 0.67 for the composite or either critical rule, no aggregate human claim will be made for that endpoint; raw disagreement and rater-level models will still be published.

The human outcomes are secondary because 50 tasks per checkpoint-condition cell do not have the confirmatory power of the full mechanical sample. They are nevertheless required: without them, the study cannot speak about fourteen rules, either critical rule, or overall quality.

## 8. Sample size and power

The existing benchmark used ten tasks, two generations, and two conditions, or 40 calls per runner, and explicitly labeled its numbers directional rather than statistically significant. A real confirmatory claim here uses 800 successful calls per checkpoint: 100 tasks, four conditions, and two generations. Across seven checkpoints this is 5,600 outputs, 140 times the calls in one old 40-call runner and 20 times the per-checkpoint call count.

The smallest effect of confirmatory interest is a standardized full-versus-competing difference-in-differences of 0.40 for one transition. With four cells and (n) observations per cell, the independent-residual approximation is

\[
n = \frac{4(z_{0.975}+z_{0.80})^2}{0.40^2}=196.2.
\]

Rounding to 200 observations per checkpoint-condition cell gives nominal 80% power for a two-sided 5% test of one transition. Two generations across 100 tasks supply those 200 observations. The equal-weight four-transition primary contrast has greater nominal precision, while pair-specific multiplicity-adjusted contrasts have less.

This calculation is intentionally conservative about effect size but cannot estimate task-cluster correlation from the old data because the old benchmark lacks both a competing condition and pinned within-family pairs. Task blocking should remove large task main effects, but residual within-task correlation can reduce power. Therefore, the powered claim is conditional on this fixed 100-task benchmark. Generalization to the universe of professional-writing tasks is supported by task diversity and cluster-robust intervals, not guaranteed by the formula. No universal claim will be made from a null.

The human subsample has 50 outputs per checkpoint-condition cell and is not powered for a 0.40 interaction at every pair. It supports effect-size estimates, construct checks, and critical-rule evidence. It is not a second confirmatory test.

## 9. Analysis plan

All code is written against opaque checkpoint and condition labels, tested on synthetic data, and hashed before the key is released. The analyst is not the rule-pack author. The public analysis proceeds as follows.

1. Validate the manifest, hashes, request identifiers, model-returned identifiers, finish reasons, and output counts without examining condition summaries.
2. Score every valid output once with the frozen engine. Preserve complete per-rule JSON.
3. Fit a log-link Poisson generalized estimating equation to the seven-rule count with `log(words/1000)` as an offset, task as the clustering unit, task stratum as a fixed effect, and checkpoint, condition, and their interaction as fixed effects. Robust sandwich standard errors make the mean model the target even if counts are overdispersed.
4. Derive the four prespecified full-versus-competing within-family decay contrasts from the fitted covariance matrix. Average them with equal weights, retaining the shared Sonnet 4.6 covariance. Test the global contrast two-sided at alpha 0.05 and report its 95% confidence interval and rate-ratio scale.
5. Run the equivalence test with bounds \(\pm\log(1.25)\). This test, not a nonsignificant superiority test, determines whether the result supports practical stability.
6. Report all four transition estimates. Apply Holm correction to the four pair-specific decay tests. These do not replace the global primary test.
7. Estimate full versus competing, competing versus bare, neutral versus bare, and full versus neutral at each checkpoint. These control contrasts are secondary and will be shown with confidence intervals, not selectively described by significance.
8. Repeat the primary specification for each mechanical rule, with 5% false-discovery-rate control, and separately for the unchanged ten-task and new 90-task subsets. Run a raw-count model without the word offset and a fixed-task linear model on `log1p(violations per 1,000 words)` as sensitivity analyses.
9. Analyze human binary compliance with a rater-level logistic mixed model containing condition, checkpoint, their interaction, task stratum, and random intercepts for task and rater. Analyze 1 to 7 ratings with a cumulative-link mixed model. Report the fourteen-rule composite, the two critical rules, and overall quality separately. Apply 5% false-discovery-rate control across the fourteen individual nonmechanical rule tests.

Models are not randomly assigned to checkpoints, so the condition effect within a checkpoint is causal under randomized call order, but the difference between checkpoint effects is a named-version comparison. It must not be phrased as the causal effect of increased intelligence or training scale.

### Ties and failures

Equal mechanical counts and equal human ratings remain in the data and contribute a zero difference. They are never broken at random or credited as a treatment win. Any rank-based sensitivity analysis will report how many exact-zero pairs its standard tie rule omits.

An HTTP, gateway, timeout, or provider error with no substantive output receives one retry with the identical payload and a logged request ID. A second transport failure is missing, with no imputation in the main model. A refusal, empty answer, or nonresponsive answer is a model outcome, not a transport retry; it enters the completion-rate outcome. It is excluded from the word-rate endpoint because zero words would create a false zero-violation success. The sensitivity analysis assigns such outcomes the 99th percentile of the valid violation-rate distribution in the same task stratum, computed while labels remain masked. Truncated outputs remain in the primary analysis and are flagged.

If more than 1% of planned outputs remain missing overall after retry, any checkpoint-condition cell has more than five missing outputs, or the maximum minus minimum condition-specific missing rate exceeds two percentage points, the confirmatory result is declared technically inconclusive. Raw data and failure patterns are still published.

## 10. Stopping rule and falsification

There is no outcome-based optional stopping and no interim condition comparison. Generation ends after 5,600 valid outputs or when a technical stop is triggered. At most 280 transport retries are permitted, for a hard ceiling of 5,880 attempted requests. Monitoring may inspect only errors, model identifiers, token usage, finish reasons, and budget, not violation scores or human ratings.

Stop before or during generation if any of the following occurs: the Sonnet alias is not immutable; a returned model identifier differs from the manifest; a common decoding parameter is rejected; a checkpoint becomes unavailable; the scorer, task file, full pack, competing pack, or wrapper hash changes; the post-retry missingness threshold is crossed; or projected gateway inference exceeds $550. Do not replace a model, task, or condition. Resume only under a dated preregistration amendment. The human phase stops after 4,200 accepted judgments, with replacements allowed only for prespecified attention-check or completion failures.

H2 fails to receive support if the global mean (D) is not positive. It is statistically falsified in the predicted direction if the 95% confidence interval lies wholly at or below zero. H1 is falsified if the full pack does not outperform the token-matched competing pack on the targeted mechanical endpoint, particularly if competing and full packs have equivalent effects. If random or irrelevant context matches the full pack on both mechanical and human compliance, the content-specific interpretation is rejected even if both beat the bare prompt. If mechanical compliance improves but human quality or either critical rule worsens, the claim is restricted to mechanical token-pattern control and the broader quality hypothesis is rejected.

## 11. Threats to validity and their controls

**Context priming is the leading threat.** Zhang et al. found content-independent gains from random, shuffled, mismatched-domain, and unconverted-format coding rule files. The neutral and token-matched competing arms are therefore mandatory. Full versus bare alone is not an admissible estimate of rule-content value.

**Checkpoint changes are bundled.** Within-family comparison removes vendor and broad family differences, but every checkpoint can change training data, post-training, system prompts, tokenization, safety behavior, and serving code. The study estimates version-specific differences in rule effects, not why they changed.

**Sonnet alias drift threatens reproducibility.** A floating alias can turn a generation comparison into an undocumented moving target. An immutable mapping and returned-identifier check are hard preconditions.

**The measurement instrument is narrow.** The deterministic engine scores seven of 21 rules, prior movement is concentrated in three regex-heavy rules, and both critical rules are absent. The human subsample and explicit claim language address but do not eliminate this limitation. The human result is smaller and less precise.

**The pack may teach the detector.** Several directives mention exact surface forms counted by the engine, so a lower mechanical score can be literal compliance without better prose. Blinded overall-quality ratings, the fourteen-rule human composite, and separate critical-rule ratings test whether improvement extends beyond those strings.

**Length can masquerade as compliance.** Shorter outputs naturally contain fewer violations. The primary offset, raw-count sensitivity, word-count reporting, and task-fulfillment ratings expose this path, but rates do not capture information omitted to achieve brevity.

**The competing pack is an imperfect control.** Irrelevant software-process instructions may distract a writing model, while a random style pack might accidentally overlap target rules. Token and structure matching, independent semantic screening, public provenance, and both short-neutral and bare arms make this limitation inspectable.

**Task contamination and authorship can favor the pack.** The retained ten prompts are public and were authored within the project. They are only 10% of the confirmatory set and are reported separately. An external selector supplies the other 90 before seeing outcomes. Even so, the benchmark covers specified English professional genres, not all writing.

**Rater masking can leak.** Distinctive prose may reveal a model or pack. Raters receive no labels or instructions, assignment is randomized, and analyses include rater effects, but perfect masking cannot be guaranteed. Raters will be asked after rating to guess condition; guess accuracy is reported as a masking check.

**API nondeterminism limits exact replay.** Pinned names and fixed payloads do not guarantee bitwise output reproducibility. The design archives raw outputs, request metadata, two samples per cell, and version identifiers. A comparable rerun estimates the same design, not the same strings.

**Multiplicity can generate stories.** One global decay contrast is primary. Pair, rule, genre, human, and control-arm results are explicitly secondary with Holm or false-discovery-rate adjustment. No family-specific result can replace a failed global hypothesis after unblinding.

## 12. Cost and credit fit

The cost calculation assumes at most 24,000 input tokens for each full or competing request, at most 500 input tokens for each bare or neutral request, and the 768-token output cap. This gives 9.8 million input tokens and 0.6144 million output tokens per checkpoint. Actual provider-reported usage and billed cost will be published.

| Channel | Planned role | Successful calls | Dollar estimate or cap | Credit fit |
|---|---|---:|---:|---|
| NAIRR gateway, Vertex AI Claude | Five Claude checkpoints | 4,000 | $258.83 at the Sonnet 5 promotional rate, or $273.21 after it ends | CloudBank credit, approximately $10,000 total |
| NAIRR gateway, Azure OpenAI GPT | Two GPT checkpoints | 1,600 | $102.65 | Same CloudBank-funded gateway program |
| **NAIRR total** | Confirmatory experiment | **5,600** | **$361.47 through 2026-08-31, or $375.85 afterward; hard stop $550 including retry and token-estimation error** | At most 5.5% of an approximately $10,000 credit, plus a few dollars for an already-running `e2-small` VM |
| AWS Bedrock | Gated open-weight follow-on | 0 in the confirmatory experiment | $0 now | No valid within-family pairs currently exist |
| Human rating | Secondary construct validation | 4,200 judgments, not API calls | $5,040 to $10,080 labor at $1.20 to $2.40 per judgment; platform and administration overhead excluded | Not covered by model-inference credit |

The Claude rates used in the estimate are $5.50 input and $27.50 output per million tokens for Opus 4.8 and Opus 5; $3.30 and $16.50 for Sonnet 4.5 and 4.6; and $2.20 and $11.00 for Sonnet 5 through August 31, 2026, rising to $3.30 and $16.50 afterward. These were checked on the [official Google Cloud pricing page](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing). GPT-5.4 uses $2.50 input and $15 output per million tokens, checked against [OpenAI's official GPT-5.4 model page](https://developers.openai.com/api/docs/models/gpt-5.4) and Microsoft's launch material. GPT-5.5 uses $5 input and $30 output per million tokens, checked against the [official Microsoft Foundry announcement](https://azure.microsoft.com/en-us/blog/openais-gpt-5-5-in-microsoft-foundry-frontier-intelligence-on-an-enterprise-ready-platform/). The public Azure price table renders placeholders for these rows, so the registration archive should also save the dated launch pages and the account's effective SKU prices.

The current Bedrock inventory lists exactly one confirmed credit-eligible identifier in each of seven families: `amazon.nova-micro-v1:0`, `us.meta.llama3-3-70b-instruct-v1:0`, `mistral.mistral-small-2402-v1:0`, `qwen.qwen3-32b-v1:0`, `us.deepseek.r1-v1:0`, `openai.gpt-oss-20b-1:0`, and `google.gemma-3-12b-it`. They cannot form within-family generation pairs. Running the same 800-call protocol on all seven would be 5,600 calls and would test cross-family breadth, not decay. `PLAN-next3.md` estimates that breadth arm below $50 [UNVERIFIED at current model-specific `us-east-1` rates]. It would fit easily within the recorded remaining ARA balance of $9,943.38, but it must be registered as a separate transfer study. The [official AWS Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/) must be snapshotted and the effective regional rates frozen before that follow-on begins.

No semantic model judge is budgeted. Using the same or a related model family as judge would introduce another generation-dependent measurement channel. The blinded human subsample is the chosen remedy for the deterministic engine's missing coverage.
