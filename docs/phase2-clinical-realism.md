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
| regex grader, 11 drifting copies | one shared grader: atomic rubric + optional LLM judge + deterministic safety checks |
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
scripts/build_journey_v2.py       cases_src/<journey> -> harbor_cases/<journey>_v2 (Harbor [[steps]])
```

v1 is frozen (git tag `v1-frozen`): its task folders and `scripts/build_dlbcl_fhir_bundles.py` are untouched; the v2
builder imports FHIR helpers from it.

## Build checks (any failure stops the build)

1. **Leak check**: no `leak_check.forbidden_in_case` term (stage, IPI, regimen names, "prophylaxis", ...) may appear in
   any model-visible file, including base64 FHIR attachments and the instruction.
2. **Pathology consistency**: every structured IHC/FISH value must appear in the pathology report text.
3. **Gold check**: the gold answer must meet every must/should item and no must_not item in regex mode (reward 1.0).

## Grader v2 (`graders/oncoworld_grader/grader_v2.py`)

- Rubric items: `kind` must / should / must_not; `severity` minor / important / dangerous; `points`.
- **A dangerous error fails the case** (reward 0): a missed dangerous `must` or a met dangerous `must_not`.
  Raw points are still reported in review.json.
- **LLM judge** when `ONCOWORLD_JUDGE_API_KEY` and `ONCOWORLD_JUDGE_MODEL` are set (OpenAI-compatible endpoint,
  default OpenRouter). Every "met" verdict must quote the answer verbatim; an unquoted or invented quote is
  downgraded to not met. Regex verdicts are still recorded and disagreements are listed for review.
- **Regex fallback** without a key (`judge="none"` in review.json): coarse. Judge-only items (no regex) score as not met.
- Harbor passes the judge variables via `[verifier.env]` in each task.toml.

## Longitudinal journey (`harbor_cases/dlbcl_0003_journey_v2`)

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

- Regex fallback is a safety net, not a grader of record: it credits keywords anywhere in the answer and cannot
  judge whether a mention is the actual plan. Use the judge for reported numbers.
- Judge agreement with an oncologist has not been measured yet. Target >=90% item-level agreement on ~30 labelled
  answers before trusting judge scores.
- LOINC/SNOMED codes in the v2 builder were chosen from memory of the standard tables and have not been run through a
  terminology server; run a validation pass before external delivery.
- The `oncologist-*-form.pdf` intake forms predate v2; the review sheet in `docs/oncologist-review-v2.md` is the
  current sign-off instrument.
