# Grader known issues (not fixed, deliberately)

Things found while red-teaming a case's rubric that turned out to need a change to shared
`graders/oncoworld_grader/grader_v2.py` rather than that case's `rubric_v2.toml`. Left unfixed on purpose: a change
here touches every case, not just the one that found the bug, and this session already learned the hard way
(2026-10-23, see the `score()` comment on the must/must_not structured-conflict branch) that a shared-logic fix
which passes every calibration test can still false-fail a real model on its very first real run. Don't patch
anything below without: (1) a calibration file reproducing the bug, (2) a full-suite recalibration (every
`cases_src/*/selftest` plus this case's), (3) a real model run against the fix before trusting it.

## 1. `_NEGATION` can't tell what a negation word actually scopes over

**Found:** 2026-10-23, red-teaming `intracranial_mesenchymal_0001` (`harbor_cases/*_narrative` and `*_fhir`).
**Where:** `graders/oncoworld_grader/grader_v2.py`, `_NEGATION` (~line 43) and how `recommends()`/`affirms()` use it
via `_mentions()`'s proximity window.
**Affects:** every `recommend`/`affirm` item in every case - this is shared logic, not case-specific.

A negation marker ("not", "no", "avoid", "defer", "withhold", ...) found within the proximity window before a term
is read as negating *that term*, regardless of which word it's actually attached to. A double negative breaks
this: "we should **not wait** any longer and will start chemotherapy this week" and "**not awaiting** further
results, we will start temozolomide now" both mean *start the drug now* - "not" negates "wait"/"awaiting", not
the drug - but `_NEGATION` matches the bare "not" and the drug mention gets wrongly read as negated, so a
dangerous `recommend` item that should fire on these doesn't.

**Reproduced against:** `mn_unsupported_regimen` in `intracranial_mesenchymal_0001`'s rubric, after the 2026-10-23
red-team pass had already fixed that item's own `except`-list word-boundary bug (`\b` around "no") and its missing
legitimate-deferral phrasing. Both fixes are real and correct; this gap is a different, deeper mechanism in the
shared negation detector that those rubric-level fixes can't reach.

**Why not fixed:** needs real scope detection (what word does the negation marker's own clause actually modify),
not another proximity rule - the kind of natural-language judgment call that looks obviously right against
hand-written calibration and can still be wrong on live model phrasing.

**Next step, when someone picks this up:** add calibration files reproducing the exact two sentences above (and
their mirror-image true negatives, e.g. "we will not start chemotherapy" alone, which must keep working) across a
few cases, not just this one; propose a fix; recalibrate the whole suite; run it against a real model before
trusting it.

## 2. `all`/`any` rule matching has no sentence scoping

**Found:** same red-team pass, same case.
**Where:** `graders/oncoworld_grader/grader_v2.py`, `rule_met()`'s `all`/`any` branch - plain `re.search` over the
whole lowered response, with no sentence binding and no negation awareness (unlike `affirm`/`recommend`, which go
through `affirms()`/`recommends()`).
**Affects:** most `must`/`should` items across the whole suite that use `all`/`any` instead of `affirm`/`recommend`
(roughly 13 of `intracranial_mesenchymal_0001`'s 17 items use this mechanism; it's the same code for every case).

Because `all`'s three (or more) conditions just need to each match *somewhere* in the whole document, scattered
unrelated mentions of the right words can satisfy an item regardless of what the actual plan says. Reproduced on
`tx_defer_definitive`: an unrelated sentence like "travel plans should defer until the diagnosis of the trip
itinerary is finalized" anywhere in the note satisfies all three of its `all` conditions.

**Why not fixed:** a sentence-scoped, order-independent rewrite was prototyped (anchoring the match at sentence
start so word order doesn't matter) and found to break `affirms()`'s own negation detection, since anchoring throws
away the "before" text the negation check needs to read "We will **NOT** defer treatment until diagnosis is
confirmed" correctly. No safe fix found with the current primitives.

**Next step:** likely needs either a per-item hand-verified conversion to `affirm`/`recommend` (reviewed
individually, since each item's semantics differ) or a new primitive that does sentence-scoped `all` without
losing the negation check - not a generic find-and-replace across every `all`/`any` item.

## 3. Judge/regex disagreement watchlist (`intracranial_mesenchymal_journey_v1`)

**Found:** 2026-10-24, building `scripts/hybrid_disagreement_report.py` and `scripts/rescore_mesenchymal_trials.py`
for the hardening plan's item 5. Regex became the grader of record in hybrid mode that same day (see the
`score()`/`grade()` history, `graders/oncoworld_grader/grader_v2.py`), so none of these can move a score
anymore - this list exists purely to decide where regex itself is worth tightening next.

The original scope was 5 items spotted live across 3 fresh trials. Running the actual tool against every
hybrid-mode trial on record (10-15 evaluations per item, not 3) found a materially bigger picture - both
`chemo_escalation_rationale`/`monitoring` dropped sharply (75% -> 14%) once item 4b's `applies_if` fix
landed (the judge is still asked about an inapplicable item and can still occasionally disagree, which no
longer costs anything - the residual is an asking-cleanliness question, not a scoring one), but several other
items turned out to disagree far more often than the original spot-check suggested.

**Update, same day, after fixing the two that crossed 50%:** `chemo_escalation_irinotecan` (two real negation
false positives - DeepSeek, Grok-4.7) dropped from 10% to clean. `chemo_options_entity_pragmatic` (57% -> 29%)
and `tgt_atypical_comutation_pattern` (50% -> 29%) both dropped meaningfully after widening against 3 more real
phrasings each, but neither is clean yet - more real models still disagree on each, just fewer.

**Second update, same day, after a 4-model repeat batch (deepseek-go, opencode-haiku-go, mimo-go, glm53flash-go)
plus a corrected re-score of everything on record:** `mol_access_tissue_insufficient` (real MiMo answer:
"archived FFPE tissue"/"paraffin blocks", missing the exact word "archival") and `mol_access_blood_limitation`
(tied for #1, 42%; real DeepSeek-go/Grok-4.7/GPT-6-Luna/GLM-go/OpenCode-Haiku-go answers used the reversed
"sensitivity is lower" word order or a too-narrow 80-char proximity window) both fixed and now clean or
near-clean. `tx_surveillance` (tied for #1, 42% -> 37%): a real GLM-go false positive ("serial neurologic
assessments; urgent imaging if deterioration" - "serial" bound to the wrong noun across a semicolon) fixed by
adding `;` to the proximity stop class; a second real false positive in the same batch (a Haiku answer, "...can
change how follow-up MRI is interpreted" - about steroid effects on imaging artifact, not a surveillance plan)
is **not** fixed - the `;` fix doesn't reach it, and binding "follow-up" to the right antecedent needs real
semantic scope, the same documented limitation as item 2 above. `tgt_raises_tissue_reacquisition`/
`tgt_acknowledges_biopsy_refusal_constraint` (L3 continuity items) separately widened for bare "tumor
tissue"/"resection specimen"/"FFPE" phrasing lacking the words "archival"/"existing" - see the rubric's own
2026-10-24 comments for the full before/after.

**Third update, same day:** `path_stat6_if_sft` and `tx_evidence_caveat` (tied for #1, 37% each) turned out to
share the exact structural bug item 4b already fixed once - both used a whole-document negative-lookahead regex
alternative to vacuously "pass" when SFT/HPC is never named, and the judge (shown only the item's text, not its
rule) can never agree with "met by absence", so it disagreed in 6-7/7 checked real trials, none of which
actually name SFT/HPC. Converted both to `applies_if` against a new 0-point marker (`dx_sft_named`), the same
fix 4b applied to `chemo_escalation_rationale`/`monitoring` - net scoring is identical, but the item is honestly
"excluded" instead of falsely "met", and the judge is no longer asked to agree with an unparseable claim.
**Grepped the whole case for the same hack afterward - no other live instances remain** (`grep -n "(?s)^"` across
all three steps' rubrics turns up only the historical comment describing the already-fixed `chemo_escalation`
items). Current state:

| item | evals | disagree | models | rate |
|---|---|---|---|---|
| `tgt_bbb_penetration_caveat` | 18 | 5 | 4 | 28% | one real miss fixed; residual is over-firing, see note below |
| `tx_surgery_assessment` | 19 | 6 | 4 | 32% |
| `mol_not_sufficient_alone` | 19 | 6 | 6 | 32% | bare doc-wide `all`, item 2's limitation |
| `chemo_options_entity_pragmatic` | 18 | 5 | 4 | 28% |
| `sup_symptoms` | 19 | 5 | 3 | 26% |
| `chemo_escalation_monitoring` | 18 | 4 | 3 | 22% |
| `tgt_atypical_comutation_pattern` | 18 | 4 | 2 | 22% |
| `chemo_escalation_rationale` | 18 | 3 | 3 | 17% |
| `stage_systemic` | 19 | 3 | 2 | 16% |
| `dx_differential_entity` | 19 | 2 | 2 | 11% |
| `mn_override_biopsy_refusal` | 19 | 2 | 2 | 11% |
| `mol_access_tissue_insufficient` | 19 | 1 | 1 | clean (below count threshold) |
| `mol_access_blood_limitation` | 19 | 0 | 0 | clean |
| `tx_evidence_caveat` | - | - | - | clean (applies_if conversion; judge may still occasionally be asked and disagree at zero scoring cost) |
| `path_stat6_if_sft` | - | - | - | clean (applies_if conversion; same residual asking-cleanliness note) |

**`tgt_bbb_penetration_caveat` - read both directions, fixed one, confirmed the other needs a bigger pass:**
read all 6 disagreements. GPT-6-Luna's (regex=False/judge=True) has no textual basis at all (no
penetrat/blood/bbb anywhere in the answer) - a judge hallucination, not a regex gap. MiMo-go's (the other
regex=False/judge=True) was real: "...their limited and variable brain and meningeal penetration" - genuinely
about FGFR inhibitors, missed because the only reversed-order alternative requires "penetration" before
"brain/cns", not after. Fixed with a new fgfr/inhibitor-anchored alternative (2026-10-24). Of the 4
regex=True/judge=False disagreements, 3 (DeepSeek-go, Qwen3.7-Plus x2) are genuinely about chemo-CNS-penetration
(temozolomide, doxorubicin, lomustine) or ctDNA/blood-brain-barrier shedding - unrelated to FGFR inhibitors, so
the judge was right and the regex over-fired; only GLM-go's ("blood-brain-barrier constraints of fgfr
inhibitors") looks like a genuine judge error. **The over-firing is not fixed** - the two pre-existing
alternatives (`blood[- ]brain[- ]barrier` bare, and `penetrat...brain/cns` bare) have no FGFR/inhibitor anchor
at all, and narrowing them risks breaking other real credits that already rely on their current breadth (not
checked here) - that's a separate, careful pass, not a same-day bundle with the addition above.

**`mol_not_sufficient_alone` checked and NOT fixed:** this is item 2's documented, deliberately-unfixed
limitation (bare doc-wide `all`, no sentence scoping) on a different item than item 2's own example - a
sentence-scoped rewrite was already prototyped once and reverted for breaking `affirms()`'s negation check; this
item needs that same unresolved design work, not a quick regex patch.

(Reproduce with `ONCOWORLD_GRADER=hybrid python3 scripts/rescore_mesenchymal_trials.py "jobs/*mesenchymal_journey*"`
- **the env var is not optional**: `score()` only takes the regex-authoritative hybrid branch when
`grader_mode() == "hybrid"`; without it, a passed-in `judge_verdicts` dict still gets used, but via the
plain-`judge` branch instead - the *opposite* of what this script is trying to measure, inflating apparent
"regressions" and disagreement rates alike. Found the hard way re-checking this same table: a first run without
the env var showed misleading drops as large as -0.35 reward on trials that, under the correct hybrid branch,
moved by at most -0.20 and mostly for well-understood reasons (see above). Next items to fix this way:
`tx_evidence_caveat` and `tx_surveillance`, both now tied at 37% - everything below that bar is lower priority
until there's more trial volume to tell signal from noise.)

**Why not fixed yet:** this is a report, not a diagnosis - each item needs the same per-item treatment every
other fix in this file got (read the actual disagreeing answers, confirm which side is actually right, widen
or rebuild only against real evidence). At 4-6 different models disagreeing on the top few, this isn't noise
to wait out; it's the next thing to actually read.

**Next step:** work down this list same as always - read the real answer text behind each flagged disagreement
(not just the regex/judge booleans), confirm whether regex or judge is right, fix the rubric if regex is wrong,
and re-run `rescore_mesenchymal_trials.py` (with `ONCOWORLD_GRADER=hybrid` set) after each fix to confirm the
item's rate actually drops. Re-check this whole list again once a meaningfully larger batch of trials exists -
10-13 evaluations per item is enough to stop treating single disagreements as noise, but still thin for the
clean items at the bottom of the table.
