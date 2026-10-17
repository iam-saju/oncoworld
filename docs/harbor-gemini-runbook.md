# Harbor Gemini API Runbook

This is the intended workflow for running the OncoWorld Harbor-style DLBCL tasks through the Gemini API path only.

## Architecture

```text
Oncology Harbor task
  -> Harbor
  -> Gemini CLI agent
  -> Gemini model
  -> Docker sandbox
  -> model writes /app/final_answer.json
  -> tests/test.sh
  -> /logs/verifier/reward.json
```

Important: the model being evaluated does not decide its own score. The verifier scores the model output against the physician-approved rubric.

## 1. Prerequisites

Install and verify:

```bash
uv tool install harbor
harbor --help
docker --version
```

Set Gemini credentials outside the repo:

```bash
export GEMINI_API_KEY="..."
```

or, depending on the Gemini CLI route:

```bash
export GOOGLE_API_KEY="..."
```

Do not put API keys in task files or Git.

Before launching Harbor, smoke-test the local pipeline without spending Gemini quota:

```bash
scripts/check_gemini_pipeline.sh
```

Then smoke-test the key and model:

```bash
scripts/check_gemini_access.sh
```

Or run the full local pipeline check plus the live Gemini API preflight:

```bash
scripts/check_gemini_pipeline.sh --live-api gemini-3.8-flash
```

## 2. Current Task Paths

Narrative input:

```text
harbor_cases/dlbcl_0001_narrative
```

FHIR input:

```text
harbor_cases/dlbcl_0001_fhir
```

## 3. Local Verifier Smoke Test

Before real Harbor runs, verify the grader locally:

```bash
harbor_cases/dlbcl_0001_narrative/tests/test.sh
harbor_cases/dlbcl_0001_fhir/tests/test.sh
```

This uses the reference output in `solution/final_answer.json` and writes:

```text
harbor_cases/<case_id>/results/reward.json
```

Expected result for the reference solution:

```json
{
  "reward": 1.0,
  "clinical_correctness": 1.0,
  "staging": 1.0,
  "first_line_treatment": 1.0
}
```

Harbor 0.24 requires all top-level values in `reward.json` to be numeric. Detailed scoring and critical-error details are saved next to it as `review.json`.

## 4. Oracle Run

Run the Harbor oracle first. This checks that the task and verifier are internally consistent.

```bash
harbor run \
  -p ./harbor_cases/dlbcl_0001_narrative \
  -a oracle
```

Repeat for the FHIR variant:

```bash
harbor run \
  -p ./harbor_cases/dlbcl_0001_fhir \
  -a oracle
```

## 5. Gemini Run

The checked-in Gemini eval config runs both current DLBCL variants with `google/gemini-3.8-flash`:

```bash
harbor run \
  -c ./configs/harbor-gemini-real-eval.json \
  --ae GEMINI_API_KEY="$GEMINI_API_KEY"
```

If your Gemini CLI/API setup uses `GOOGLE_API_KEY` instead, pass that variable:

```bash
harbor run \
  -c ./configs/harbor-gemini-real-eval.json \
  --ae GOOGLE_API_KEY="$GOOGLE_API_KEY"
```

To change models, override the model on the command line with `-m google/<model-id>`.

Gemini free-tier keys can hit low request limits, especially because the CLI retries transient 503/high-demand responses. If Harbor reports `NonZeroAgentExitCodeError` or `ApiUsageLimitError`, check the trial's `agent/gemini-cli.txt`; the error there is the real cause. A `429` quota message means the agent failed before producing `/app/final_answer.json`, not that the oncology verifier failed. A `403 PERMISSION_DENIED` message such as `Your project has been denied access` means the API key's Google project is blocked or not allowed to call the Gemini API/model; use a different enabled Gemini API key/project before rerunning Harbor. If quota is tight, run one task at a time:

```bash
harbor run \
  -c ./configs/harbor-gemini-real-eval.json \
  --ae GEMINI_API_KEY="$GEMINI_API_KEY" \
  -p ./harbor_cases/dlbcl_0001_narrative
```

If a particular Gemini model's free-tier quota is exhausted, use another available model explicitly, for example:

```bash
harbor run \
  -c ./configs/harbor-gemini-real-eval.json \
  --ae GEMINI_API_KEY="$GEMINI_API_KEY" \
  -m google/gemini-3.8-flash \
  -p ./harbor_cases/dlbcl_0001_narrative
```

## 6. Full Gemini Pilot Run

After one-task and two-task Gemini runs work, use the five-case Gemini config:

```bash
harbor run \
  -c ./configs/harbor-gemini-5case-eval.json \
  --ae GEMINI_API_KEY="$GEMINI_API_KEY"
```

Use a dated job name if you want a stable label for a pilot run:

```bash
harbor run \
  -c ./configs/harbor-gemini-5case-eval.json \
  --job-name "dlbcl_gemini_pilot_$(date +%Y%m%d_%H%M%S)" \
  --ae GEMINI_API_KEY="$GEMINI_API_KEY"
```

To run only one task while keeping the same Gemini config, override the task list:

```bash
harbor run \
  -c ./configs/harbor-gemini-5case-eval.json \
  --ae GEMINI_API_KEY="$GEMINI_API_KEY" \
  -p ./harbor_cases/dlbcl_0001_narrative
```

If Docker reports `read-only file system` for `/var/lib/desktop-containerd/.../meta.db`, restart Docker Desktop before rerunning. If the same error persists, use Docker Desktop's troubleshooting action to restart/reset the Docker engine state, then rerun Harbor.

## 7. Inspect Results

Look for the Harbor job/trial output directory. You should expect artifacts such as:

```text
agent.log
verifier.log
reward.json
```

Check:

- Did the model create `/app/final_answer.json`?
- Did `tests/test.sh` run?
- Did the verifier produce `/logs/verifier/reward.json`?
- Were any critical errors triggered?
- Does physician review agree with the automated score?

## 8. Five-Case Pilot Pattern

After one task works end to end, repeat the structure:

```text
ONC-001 -> model -> verifier -> reward
ONC-002 -> model -> verifier -> reward
ONC-003 -> model -> verifier -> reward
ONC-004 -> model -> verifier -> reward
ONC-005 -> model -> verifier -> reward
```

Then report aggregate metrics, error categories, and physician-reviewed examples of failures.

## 9. Medical Benchmark Rule

Use synthetic or properly de-identified material only until privacy, contractual, and physician-review arrangements are in place.
