# oncoworld

Harbor-based evaluation harness for oncology clinical reasoning tasks (DLBCL and breast cancer cases), built on synthetic FHIR R4 / mCODE patient bundles.

## Layout

- `harbor_cases/` — benchmark task definitions (instructions, FHIR bundles, graders, solutions, scoring)
- `configs/` — eval run configs for different agents/models (Gemini, OpenCode/OpenRouter)
- `scripts/` — bundle builders, pipeline checks, job scoring/summary helpers
- `docs/` — runbooks and case-intake reference docs
- `versions/` — architecture notes and diagrams per iteration
- `results/`, `mockups/` — sample run summaries and a results-review UI mockup

Local eval run output lives under `jobs/` and is not tracked in this repo.
