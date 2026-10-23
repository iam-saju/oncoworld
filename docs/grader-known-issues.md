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
hybrid-mode trial on record (10-13 evaluations per item, not 3) found a materially bigger picture - both
`chemo_escalation_rationale`/`monitoring` dropped sharply (75% -> 10-20%) once item 4b's `applies_if` fix
landed (the judge is still asked about an inapplicable item and can still occasionally disagree, which no
longer costs anything - the residual is an asking-cleanliness question, not a scoring one), but several other
items turned out to disagree far more often than the original spot-check suggested:

| item | evals | disagree | models | rate |
|---|---|---|---|---|
| `mol_access_blood_limitation` | 11 | 6 | 5 | 55% |
| `chemo_options_entity_pragmatic` | 10 | 5 | 4 | 50% |
| `tgt_atypical_comutation_pattern` | 10 | 5 | 4 | 50% |
| `mol_access_tissue_insufficient` | 11 | 3 | 3 | 27% |
| `mol_not_sufficient_alone` | 11 | 3 | 3 | 27% |
| `tx_evidence_caveat` | 11 | 3 | 3 | 27% |
| `tx_surgery_assessment` | 11 | 3 | 3 | 27% |
| `tx_surveillance` | 11 | 3 | 3 | 27% |
| `chemo_escalation_rationale` | 10 | 2 | 2 | 20% |
| `path_stat6_if_sft` | 11 | 2 | 2 | 18% |
| `sup_symptoms` | 11 | 2 | 2 | 18% |
| `tgt_bbb_penetration_caveat` | 10 | 2 | 2 | 20% |
| `chemo_escalation_irinotecan` | 10 | 1 | 1 | 10% |
| `chemo_escalation_monitoring` | 10 | 1 | 1 | 10% |
| `tgt_molecular_not_sufficient_alone` | 10 | 1 | 1 | 10% |

(Reproduce with `python3 scripts/rescore_mesenchymal_trials.py "jobs/*mesenchymal_journey*"` - the corrected
per-item section at the end of its output. `chemo_options_entity_pragmatic` and `tgt_atypical_comutation_pattern`
were already each widened against real misses earlier the same day - this list is the first time either has
been quantified rather than fixed one real miss at a time, and both are clearly still an open gap, not a
closed one.)

**Why not fixed yet:** this is a report, not a diagnosis - each item needs the same per-item treatment every
other fix in this file got (read the actual disagreeing answers, confirm which side is actually right, widen
or rebuild only against real evidence). At 4-5 different models disagreeing on the top three, this isn't noise
to wait out; it's the next thing to actually read.

**Next step:** work down this list same as always - read the real answer text behind each flagged disagreement
(not just the regex/judge booleans), confirm whether regex or judge is right, fix the rubric if regex is wrong,
and re-run `rescore_mesenchymal_trials.py` after each fix to confirm the item's rate actually drops. Re-check
this whole list again once a meaningfully larger batch of trials exists - 10-13 evaluations per item is enough
to stop treating single disagreements as noise, but still thin for the clean items at the bottom of the table.
