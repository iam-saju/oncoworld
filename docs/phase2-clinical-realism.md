# OncoWorld Phase 2: clinically realistic cases (v2)

Status 2026-10-19: built and oracle-verified. **No clinical content is signed off yet.** Every v2 rubric and gold
answer is `PENDING_ONCOLOGIST`; journey layers 2-5 are `DRAFT_NEEDS_ONCOLOGIST`. Do not report model scores on v2
as clinical performance until an oncologist has signed off (see `docs/oncologist-review-v2.md`).

## Why v2

v1 cases were short bullet lists built around one teaching point each. Real oncology looks different:

| v1 | v2 |
|---|---|
| 4 short text files of pre-interpreted findings ("LDH elevated") | 10-14 dated chart documents: referral, consult H&P, radiology/pathology reports, FISH addenda, progress notes |
| no past history, meds, allergies | problem list, medication list, allergies, social history, distractor comorbidities |
| narrative said "elevated", FHIR had no reference range (formats disagreed) | one source renders both formats; every lab has a reference range and a computed H/L flag |
| "missing information" manufactured by withholding PET findings | gaps are only things genuinely not done (e.g. no MRI/LP, no pregnancy test, no HBV DNA) |
| instructions asked leading questions ("is this double-hit?") | "You are the consulting hematologist; write your assessment and plan for tumor board" |
| no pre-treatment work-up, supportive care or patient goals | graded: HBV, LVEF, TLS, G-CSF, prephase, contraception, fertility, patient goals |
| regex grader, 11 drifting copies | one shared grader: atomic rubric scored by deterministic regex rules that read like an oncologist (optional LLM judge) |
| one snapshot in time | longitudinal journey (5 layers) as a Harbor multi-step task |

Each patient keeps their v1 identity and core teaching point, plus one **decision-changing real-world twist**:

| case | v1 teaching point (kept) | v2 twist | what a correct plan must now do |
|---|---|---|---|
| 0001 | spleen is lymphatic, stage III; DEL is not DH | HBsAg-, **anti-HBc+** | entecavir/tenofovir prophylaxis before rituximab (dangerous if missed) |
| 0002 | spleen-only stage III; IPI 2 | prior **doxorubicin 240 mg/m2** + chest RT; **LVEF 62% -> 45%** | cardio-oncology, cardioprotection, anthracycline-free/modified curative regimen (standard R-CHOP/Pola-R-CHP ignoring the heart is dangerous) |
| 0003 | kidney/adrenal -> high CNS-IPI | age 67, ECOG 2, **uric acid 10.4, creatinine rising, on ibuprofen** | prephase steroid, TLS prophylaxis (dangerous if missed), stop NSAIDs, G-CSF, MRI+CSF, HD-MTX feasibility tied to renal function |
| 0004 | FISH defines double-hit | initial sign-out "DLBCL NOS" and an **R-CHOP plan already in the chart**; FISH addendum later | revise to HGBL-DH, cancel the outdated plan, intensive regimen, CNS evaluation |
| 0005 | limited stage, low risk | **migraine with aura on combined pill**, no pregnancy test, wants to avoid neck RT | FLYER (4 R-CHOP + 2 R), pregnancy test, stop estrogen pill, non-estrogen contraception |

## Layout

```text
cases_src/<case>/case.toml        MODEL-VISIBLE chart source (facts + documents)
cases_src/<case>/gold.json        hidden reference answer (11 keys)
cases_src/<case>/rubric_v2.toml   hidden atomic rubric + leak_check terms
cases_src/<case>/selftest/        hidden adversarial answers (+ judge_cases for offline judge tests)
cases_src/dlbcl_0003_journey/     longitudinal journey source (journey.toml, L2-L5 rubric/gold, selftests)
graders/oncoworld_grader/         grader_v2.py, test.sh, run_selftest.py (copied into every v2 task)
scripts/build_cases_v2.py         cases_src/<case> -> harbor_cases/<case>_<slug>_v2_{narrative,fhir}
scripts/build_journey_v2.py       cases_src/<journey> -> harbor_cases/<journey>_v2_fhir (Harbor [[steps]]) + narrative control
```

v1 is frozen (git tag `v1-frozen`): its task folders and `scripts/build_dlbcl_fhir_bundles.py` are untouched; the v2
builder imports FHIR helpers from it.

## Build checks (any failure stops the build)

1. **Leak check**: no `leak_check.forbidden_in_case` term (stage, IPI, regimen names, "prophylaxis", ...) may appear in
   any model-visible file, including base64 FHIR attachments and the instruction.
2. **Pathology consistency**: every structured IHC/FISH value must appear in the pathology report text.
3. **Gold check**: the gold answer must meet every must/should item and no must_not item under the regex rules (reward 1.0).

## Task layout: FHIR only

Only FHIR tasks are run (2026-10-22). `harbor_cases/` holds the FHIR tasks; the narrative renderings of the same patients
and the narrative journey live in `harbor_cases_narrative/` and are run only as a diagnostic control, for
example when a model fails a FHIR task and you need to know whether it misread the FHIR or got the medicine wrong.
`scripts/build_cases_v2.py` writes each format to its folder. The active configs
(`configs/harbor-3model-v2-first5.json` and the other `*-v2-first5.json`) run all five patients' FHIR tasks.

## Grader v2 (`graders/oncoworld_grader/grader_v2.py`)

- Rubric items: `kind` must / should / must_not; `severity` minor / important / dangerous; `points`.
- **A dangerous error fails the case** (reward 0): a missed dangerous `must` or a met dangerous `must_not`.
  Raw points are still reported in review.json.
- **Regex rules are the grader of record** (fast, free, deterministic; ~0.2 s for a 15-trial job). They read the way a
  senior oncologist reads a consult note: a term only counts when it is asserted. Negations ("not double-hit",
  "excluding double-hit lymphoma"), hedged denials ("reduces the concern for double-hit"), hypotheticals ("if FISH were
  ever positive", "stage IV would only apply if"), indication statements ("reserve DA-EPOCH-R for double-hit"), and
  definitions or lists of criteria do not assert it. A regimen only counts as recommended when the sentence puts it
  forward as the plan, not when it is the comparator in an outcomes statement ("inferior outcomes after R-CHOP").
  These rules were rebuilt on 2026-10-22 after the older version zeroed 7 of 10 failing trials in
  `jobs/3model_v2_first5_r2` by misreading exactly those phrasings.
- **Every rule change is gated** by the calibration answers (`answers/*.json`: gold, hand-written bad answers, and real
  model answers with verdicts classified from their text) and by per-item oncologist probe sentences
  (`selftest/probes.json`, 577 sentences written and independently re-labelled by senior heme-onc agents).
  `python3 scripts/check_rules.py` is the gate (calibration must stay 100%); `tests/selftest/run_selftest.py` runs the
  same checks inside each task; `scripts/probe_rules.py` tests one sentence against one rule;
  `scripts/rescore_job.py jobs/<job>` re-grades saved answers in seconds after a change.
- **Generalisation benchmark**: `selftest/heldout_probes.json` (370 sentences by agents who never saw the rules or the
  tuning probes) is reported by check_rules.py but never gates. 2026-10-22: 345/370 (93%); this figure is partly
  contaminated because some shared-rule fixes were made after seeing held-out failures. Measure future changes with a
  fresh held-out set.
- **Open clinical calls for the oncologist**: dlbcl_0003 `sup_tls_prophylaxis` now requires labs every few hours
  (high-risk TLS); answers that monitor daily or twice weekly fail it, and it is a dangerous item. Stage items reject
  hedged ranges ("stage III-IV") as not committing to a stage.
- **Optional LLM judge**: `ONCOWORLD_GRADER=judge` plus `ONCOWORLD_JUDGE_API_KEY` / `ONCOWORLD_JUDGE_MODEL`. Every
  "met" verdict must quote the answer verbatim; regex verdicts are still recorded and disagreements listed; if the
  judge fails, the regex verdicts stand. `scripts/calibrate_judge.py` measures a judge against the calibration set.
- Harbor passes the grader variables via `[verifier.env]` in each task.toml.
- **Oncologist report**: `scripts/build_report.py jobs/<run> [jobs/<run2> ...]` (also run by `scripts/run_timed.sh`) writes
  `reports/<run>.html`: plain-language results per model, coverage grids, charts, every unsafe finding quoted from the
  note, and agree/disagree controls; runs given together are shown as repeated attempts. Plain-language criterion
  labels and patient summaries live in `cases_src/<case>/review_labels.json` (never shown to the model).

## Longitudinal journey (`harbor_cases/dlbcl_0003_journey_v2_fhir`)

FHIR rendering (2026-10-22): layer 1 is the single-case FHIR bundle at `/app/case/fhir_bundle.json`; each later visit uploads
one FHIR R4 update Bundle to `/app/case/fhir_updates/0N_<date>_update.json` at step start: the visit's notes and reports
(base64 attachments, interval history first) plus structured labs with reference ranges, vitals, ECOG, weight, GCS, LVEF,
medication statements and administrations, procedures and genomic variants. Structured data only restates facts already in
that layer's notes. The build leak-checks each layer's `[leak_check]` terms against everything visible at that step.
Real-model run: `configs/harbor-3model-v2-journey-fhir.json` (`resume_trajectory: true`, so each agent keeps its own session
from visit to visit; 1800 s agent timeout per step). Oracle: `configs/harbor-oracle-journey-fhir.json`.
Per-layer results: `python3 scripts/summarize_job.py jobs/<job>` (the HTML report covers single-visit trials only).

One Harbor multi-step task, five steps; each later layer's documents are uploaded via `steps/<L>/workdir` only when
that step starts, and each begins with an interval history of what actually happened.

| layer | weight | situation | key dangerous errors |
|---|---|---|---|
| L1 diagnosis | 20 | the v2 0003 chart | as in the single case |
| L2 after first line | 15 | EOT PET Deauville 4, non-diagnostic biopsy, refusal of re-biopsy | calling it complete response |
| L3 second line | 20 | progression 3.5 months after Pola-R-CHP; NGS (EZH2 Y646F) | no CAR-T; palliative-only |
| L4 acute admission | 30 | day +6 after axi-cel: confusion, fever, hypotension, ANC 0.2 | no steroids for ICANS; no empiric antibiotics |
| L5 goals of care | 15 | progression after CAR-T, ECOG 3, declines treatment, financial toxicity | abandoning the patient |

`scripts/summarize_job.py` applies the layer weights and fails the case if any layer has a dangerous error
(Harbor's own "mean" table averages domain keys across layers with missing keys as 0, so ignore it).

## Commands

```bash
python3 scripts/build_cases_v2.py            # all v2 cases (or: build_cases_v2.py dlbcl_0003)
python3 scripts/build_journey_v2.py
for t in harbor_cases/*_v2_*/ ; do python3 $t/tests/selftest/run_selftest.py | tail -1; done
for s in harbor_cases/*_journey_v2/steps/*/ ; do python3 $s/tests/selftest/run_selftest.py | tail -1; done

harbor run -y -c configs/harbor-oracle-v2-all.json         # oracle: every v2 task and journey step = 1.0
harbor run -y -c configs/harbor-oracle-v1-all.json         # v1 sanity under current weights

# Funded baseline (v1 vs v2 side by side, 3 attempts each). Needs a paid key; free tiers caused most v1 errors.
export OPENROUTER_API_KEY=...                              # agent
export ONCOWORLD_JUDGE_API_KEY=... ONCOWORLD_JUDGE_MODEL=... # judge (pin the model id and record it)
harbor run -y -c configs/harbor-baseline-v1-v2-paid.json
python3 scripts/summarize_job.py jobs/<job>
```

## Known limits

- Judge agreement with an oncologist has not been measured yet. Target >=90% item-level agreement on ~30 labelled
  answers before trusting judge scores.
- LOINC/SNOMED codes in the v2 builder were chosen from memory of the standard tables and have not been run through a
  terminology server; run a validation pass before external delivery.
- The `oncologist-*-form.pdf` intake forms predate v2; the review sheet in `docs/oncologist-review-v2.md` is the
  current sign-off instrument.
