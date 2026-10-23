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
