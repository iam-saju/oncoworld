# Grader patch notes, 2026-10-10

All ten DLBCL graders (five narrative/FHIR pairs) and the breast grader were patched after reading the saved
Gemini 3.5 Flash Lite answers next to their `review.json`. Prompts, gold answers and rubric weights are unchanged.

## What was wrong

| Bug | Effect | Fix |
|---|---|---|
| "non-double-hit", "not **a** double-hit", "ruling out double-hit" not recognised | correct answers lost 5 pts and, on 0003, a −15 critical error | sentence-scoped negation helper shared by all graders |
| `double-hit.*negative` scanned the whole answer | on 0004 a later "bone marrow negative" cancelled a correct "double-hit" (−25) | negation must sit in the same sentence as the term |
| "avoid DA-EPOCH-R" / "avoid stage IV" only credited explicit wording | answers that simply did not recommend DA-EPOCH-R lost 3-4 pts | credit unless the regimen is actually put forward |
| end-of-treatment PET only matched "end of treatment" | "end of systemic therapy", "after completion of therapy" lost 3 pts | wider phrase list |
| breast: "negligible benefit from chemotherapy" read as recommending chemotherapy | −25 critical error on a correct answer | "negligible/minimal/little" added as negators |
| safe patterns like `not.*r-chop` scanned the whole answer with an unbounded `not` | the "not" inside "phe**not**ype" in the diagnosis field excused a dangerous "R-CHOP is preferred" on 0004; 0001's DA-EPOCH-R critical could never fire | `not` is word-bounded and must sit in the same sentence; the R-CHOP critical uses the sentence-scoped helper |

Critical errors are judged per sentence: a sentence that asserts double-hit (or double-expressor on the
low-expression cases) without negating it fires the penalty even if another sentence denies it. Definitional
sentences ("double-hit is defined as...", "versus") are not treated as assertions. Answers reach the grader as
JSON text, so field boundaries (`"...", "key": "..."`) also end a sentence; without that, a "not" in one field
leaked into the next field's sentence and silently excused an assertion.

## Re-scored saved answers (same model outputs, old grader → patched grader)

| Job | Task | Old | New | False critical removed |
|---|---|---|---|---|
| 2026-10-09__22-08-35 | dlbcl_0001_narrative | 78 | 90 | |
| 2026-10-09__22-08-35 | dlbcl_0002 narrative | 79 | 90 | |
| 2026-10-09__22-08-35 | dlbcl_0003 narrative | 98 | 98 | |
| 2026-10-09__22-20-20 | dlbcl_0001_fhir (old free-text bundle) | 67 | 76 | |
| 2026-10-09__22-20-20 | dlbcl_0001_narrative | 75 | 90 | |
| 2026-10-09__22-20-20 | dlbcl_0002 narrative | 71 | 85 | |
| 2026-10-09__22-20-20 | dlbcl_0003 narrative | 93 | 98 | |
| 2026-10-09__22-20-20 | dlbcl_0004 narrative | 94 | 97 | |
| 2026-10-09__22-20-20 | dlbcl_0005 narrative | 87 | 95 | |
| 2026-10-10__01-01-23 | breast_0001_fhir | 61 | 100 | recommends_adjuvant_chemotherapy |
| 2026-10-10__01-01-23 | dlbcl_0002 fhir | 94 | 90 | (two criteria were over-credited before, see below) |
| 2026-10-10__01-01-23 | dlbcl_0003 fhir | 72 | 100 | calls_low_expression_case_double_expressor_or_double_hit |
| 2026-10-10__01-01-23 | dlbcl_0004 fhir | 60 | 100 | misses_double_hit_FISH_positive |

Points still lost after the patch are real model behaviour, for the oncologist to classify:

- `dlbcl_0001` (both formats, every run): stages the case **IV** by counting splenic lesions as extranodal; gold is III. Needs the spleen rule confirmed.
- `dlbcl_0001`, `dlbcl_0002`: calls Hans non-GCB "ABC subtype" as if it were the molecular subtype.
- `dlbcl_0002` (both formats): counts the spleen as an extranodal IPI site. The FHIR run had been credited for this by a stray "not" (from "not otherwise specified") bridging two fields; the bounded patterns now catch it, so that score goes down from 94 to 90, correctly.
- `dlbcl_0001_fhir` (old bundle): no CNS-IPI, vague prophylaxis advice. Not comparable with the new coded bundle.
- `dlbcl_0005`: does not name CNS-IPI.
- A critical for "CNS prophylaxis is mandatory" (wording with the noun first) was added to 0001 and 0005; the old patterns only matched "mandatory ... CNS prophylaxis".

## Self-tests

Every DLBCL case now has `tests/selftest/run_selftest.py` with the reference answer, the real Gemini answers above
(with the criteria they must and must not earn), and two dangerous answers that must trigger their critical error.
Run all of them:

```bash
for c in harbor_cases/*/; do python3 $c/tests/selftest/run_selftest.py | tail -1; done
```

## Configs

`harbor-gemini-fhir-eval.json` was split so Harbor's summary table is not averaged across two different rubrics:

- `configs/harbor-gemini-breast-eval.json` (breast_0001_fhir)
- `configs/harbor-gemini-dlbcl-fhir-eval.json` (five DLBCL FHIR cases)

All Gemini configs now use `google/gemini-3.8-flash`. Earlier runs used `gemini-3.5-flash-lite`; do not mix them in one comparison.

## Follow-up: Gemini 3.8 Flash FHIR run (job 2026-10-10__01-33-04)

- breast_0001_fhir: graded 80 with a −20 `recommends_HER2_targeted_therapy`, but the answer said "Anti-HER2 targeted
  therapies (e.g, trastuzumab, pertuzumab, antibody-drug conjugates) are not indicated". The negation sat after the
  drug list, beyond the 5-word look-ahead. The breast grader now also accepts a clear negative predicate
  ("are not indicated", "no proven") up to 15 words after the drug name. Re-scored: **100**. Self-test 12 holds the sentence.
- dlbcl_0001_fhir: 90; real misses are stage IV for splenic disease and Hans non-GCB called "ABC".
- dlbcl_0002–0005_fhir: no answer. Gemini free tier allows 20 requests/day for gemini-3.8-flash (HTTP 429).
  Retry with `configs/harbor-gemini-fhir-retry.json` after the quota resets.
