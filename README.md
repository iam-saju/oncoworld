# oncoworld

Harbor-based evaluation harness for oncology clinical reasoning tasks (DLBCL and breast cancer cases), built on synthetic FHIR R4 / mCODE patient bundles.

## Layout

- `harbor_cases/` — benchmark task definitions (instructions, FHIR bundles, graders, solutions, scoring)
  - v1 (frozen, tag `v1-frozen`): `dlbcl_000X_*_{narrative,fhir}`, `breast_0001_fhir`
  - v2 (generated, do not hand-edit): `dlbcl_000X_*_v2_{narrative,fhir}` and the multi-step `dlbcl_0003_journey_v2`
- `cases_src/` — v2 single source per patient (model-visible `case.toml`; hidden gold, rubric, self-tests)
- `graders/oncoworld_grader/` — shared v2 grader (atomic rubric + optional LLM judge + safety checks)
- `configs/` — eval run configs for different agents/models (Gemini, OpenCode/OpenRouter)
- `scripts/` — bundle builders (`build_cases_v2.py`, `build_journey_v2.py`), pipeline checks, job summary (`summarize_job.py`)
- `docs/` — runbooks and case-intake reference docs
- `versions/` — architecture notes and diagrams per iteration
- `results/`, `mockups/` — sample run summaries and a results-review UI mockup

Local eval run output lives under `jobs/` and is not tracked in this repo.

Phase 2 (clinically realistic v2 cases): see `docs/phase2-clinical-realism.md`. Clinical sign-off: `docs/oncologist-review-v2.md`.
