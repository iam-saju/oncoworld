# OncoWorld V1 Baseline Notes

Date: 2026-10-09

## Current Milestone

The next milestone is a reproducible baseline whose scores are trusted.

Do not tune visible prompts to improve the score. Keep prompts frozen and use the patched graders to measure the model more accurately.

## Grader Reweight — 2026-10-13

Domain point weights were rebalanced across all 10 DLBCL cases, in both `tests/rubric.yaml` and the hardcoded `CHECKS` dict in `tests/grader.py` (the file that actually computes scores):

- `response_assessment`: 10 -> 15 (previously the lowest-weighted domain in every case)
- `diagnosis_and_COO`: 15 -> 10 (funds the increase above)
- `dlbcl_0001_narrative` / `dlbcl_0001_fhir` only, fixed an outlier so they match the other 4 cases:
  - `first_line_treatment`: 25 -> 15
  - `CNS_management`: 10 -> 15
  - `staging`: 10 -> 15

All 10 DLBCL cases now share the same domain split: `diagnosis_and_COO=10, staging=15, molecular_classification=15, prognosis=15, first_line_treatment=15, CNS_management=15, response_assessment=15` (sums to 100). Treatment, CNS risk, and response assessment are now weighted equally — the project owner wants those three emphasized over the others.

`critical_errors` penalties and `passing_score` (75) are unchanged. No criteria were added, removed, or reworded — only point values moved. Re-verified after the change: every case's `solution/final_answer.json` (gold answer) still scores `1.0`.

**All reward numbers recorded below predate this reweight and are not comparable to any run made after 2026-10-13.** The milestone below must be re-attempted from scratch under the new weights.

## Clinical Staging Rule To Confirm

For DLBCL/Lugano staging:

- The spleen is treated as lymphatic tissue.
- Nodal disease above and below the diaphragm with splenic involvement is stage III.
- Qualifying non-lymphatic extranodal organ involvement can make disease stage IV.
- Prefer wording: `Stage III, bulky disease; B symptoms present`.
- Avoid relying on `IIIB` wording for Lugano-era non-Hodgkin lymphoma reporting.

This rule should be confirmed by the oncology reviewer before the suite is frozen.

## Task Count Reporting

The current run config has 6 tasks but 5 distinct underlying clinical cases:

```text
dlbcl_0001_narrative
dlbcl_0001_fhir
dlbcl_0002_splenic_stage_iii_narrative
dlbcl_0003_renal_adrenal_cns_high_narrative
dlbcl_0004_double_hit_narrative
dlbcl_0005_limited_stage_gcb_narrative
```

`dlbcl_0001_narrative` and `dlbcl_0001_fhir` are two input-format variants of the same synthetic patient.

Report:

- model performance across 6 tasks
- clinical performance across 5 distinct cases
- format comparison for narrative vs FHIR on case 0001

## Existing Measurements

### Harbor Run With Previous Grader

Job:

```text
jobs/2026-10-09__15-50-46
```

Aggregate result:

```text
trials: 6
exceptions: 0
reward: 0.862
clinical_correctness: 0.878
staging: 0.644
molecular_classification: 1.000
prognosis: 0.944
first_line_treatment: 0.682
cns_management: 0.844
response_assessment: 1.000
```

Use this only as the score under the previous grader.

### Local Re-Scoring Of Saved Answers With Patched Grader

Same saved model answers from:

```text
jobs/2026-10-09__15-50-46
```

Local patched-grader average:

```text
reward: 0.822
```

Use this as a re-evaluation of saved answers, not as a new model run.

Main corrected interpretation:

- The spleen-only case `dlbcl_0002` now receives a critical penalty when the model calls it stage IV.
- Treatment wording is less brittle when the model gives a clinically valid R-CHOP or pola-R-CHP strategy.

## Next Clean Baseline Run

Superseded by the 2026-10-13 grader reweight above — none of the runs below used the new point distribution. Run the same six tasks again with:

- unchanged visible prompts
- reweighted graders (2026-10-13)
- same model identifier
- same Harbor config

Command:

```bash
harbor run \
  -c ./configs/harbor-opencode-real-eval.json \
  --ae OPENROUTER_API_KEY="$OPENROUTER_API_KEY"
```

After the run, record:

- job folder
- model identifier
- task list
- per-case reward
- criterion-level failures from each `review.json`
- any exceptions or infrastructure failures

## Attempted Clean Run: Invalid Baseline

Job:

```text
jobs/2026-10-09__16-28-17
```

This run is not a clean clinical baseline because it had infrastructure/API failures:

```text
AgentSetupTimeoutError: 1
ApiRateLimitError: 2
```

The OpenRouter free-tier daily rate limit was reached during `dlbcl_0004` and `dlbcl_0005`, producing missing answers and zero rewards. `dlbcl_0002` also failed during agent setup.

Do not report the aggregate score as model clinical performance.

Partial completed-trial signal:

```text
dlbcl_0001_narrative: 0.94
dlbcl_0001_fhir: 0.87
dlbcl_0003_renal_adrenal_cns_high: 1.00
```

Interpretation:

- The completed trials suggest the patched graders are working.
- The FHIR version of case 0001 still missed the spleen/stage-III rule.
- The kidney/adrenal high-CNS-risk case scored cleanly.
- A valid baseline still requires all six tasks to complete without API/setup exceptions.

Recommended retry:

- wait for OpenRouter free-tier reset, or
- use a funded OpenRouter key/model route, or
- run fewer tasks per job and combine completed results only if the model/config is identical.

## Doctor Review Table

Use this table for the oncology reviewer:

| Case | Model answer | Expected answer | Miss type | Doctor verdict | Action |
| --- | --- | --- | --- | --- | --- |
| dlbcl_0001 narrative |  |  |  |  |  |
| dlbcl_0001 FHIR |  |  |  |  |  |
| dlbcl_0002 spleen stage III |  |  |  |  |  |
| dlbcl_0003 kidney/adrenal CNS high |  |  |  |  |  |
| dlbcl_0004 double-hit |  |  |  |  |  |
| dlbcl_0005 limited-stage GCB |  |  |  |  |  |

## Action Rules

- If the doctor confirms a clinical reference answer, keep the grader strict on that point.
- If the model answer is clinically valid but loses points due to wording, patch the grader.
- If the same clinical miss repeats, add more cases targeting that concept.
- Do not leak expected answers into visible prompts.
