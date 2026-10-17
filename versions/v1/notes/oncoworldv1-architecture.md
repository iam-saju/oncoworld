# OncoWorldV1 Architecture

OncoWorldV1 is the current Harbor-based oncology evaluation workspace in this repository.

Its purpose is to run AI agents on synthetic oncology cases, collect structured clinical answers, and score those answers with a deterministic verifier.

The current working benchmark is a DLBCL clinical reasoning task with two input variants:

```text
harbor_cases/dlbcl_0001_narrative
harbor_cases/dlbcl_0001_fhir
```

These are not two different patients. They are two formats of the same synthetic DLBCL case:

```text
narrative files
FHIR Bundle
```

## High-Level System

```text
Harbor config
  -> Harbor runner
  -> Docker task sandbox
  -> agent/model reads instruction + /app/case/*
  -> agent writes /app/final_answer.json
  -> verifier runs tests/test.sh
  -> grader.py scores the answer
  -> reward.json + review.json
  -> jobs/<job_id>/ stores results
```

The model does not score itself. The model produces an answer. The verifier scores it.

## Main Components

```text
configs/
harbor_cases/
docs/
jobs/
scripts/
mockups/
results/
```

### `configs/`

This folder contains Harbor job configs.

Current active Gemini configs:

```text
configs/harbor-gemini-real-eval.json
configs/harbor-gemini-3task-eval.json
configs/harbor-gemini-5case-eval.json
```

OpenRouter/OpenCode config files may still exist as older comparison material, but they are not part of the current Gemini-only validation path.

#### Gemini Config

File:

```text
configs/harbor-gemini-real-eval.json
```

Current model route:

```text
agent: gemini-cli
model: google/gemini-3.8-flash
env: GEMINI_API_KEY or GOOGLE_API_KEY
```

The two-task config runs:

```text
harbor_cases/dlbcl_0001_narrative
harbor_cases/dlbcl_0001_fhir
```

The five-case pilot config runs all current DLBCL task variants:

```text
configs/harbor-gemini-5case-eval.json
```

Run command:

```bash
harbor run \
  -c ./configs/harbor-gemini-real-eval.json \
  --ae GEMINI_API_KEY="$GEMINI_API_KEY"
```

Gemini free-tier runs may fail due to `503` high demand, `429` quota limits, or `403 PERMISSION_DENIED` project/key access errors. Harbor may surface those as `NonZeroAgentExitCodeError` or `ApiUsageLimitError`; inspect the trial's `agent/gemini-cli.txt` to confirm the underlying Gemini CLI error. Those failures are infrastructure/API failures, not clinical model failures.

### `harbor_cases/`

This folder contains the actual benchmark tasks.

Current cases:

```text
harbor_cases/dlbcl_0001_narrative
harbor_cases/dlbcl_0001_fhir
```

Each case is self-contained:

```text
task.toml
instruction.md
environment/
solution/
tests/
results/
```

### `docs/`

Human documentation only.

Examples:

```text
docs/harbor-cases-explained.md
docs/harbor-gemini-runbook.md
docs/harbor-task-components.md
docs/breast-pdf-change-summary.md
docs/oncoworldv1-architecture.md
```

Documents in `docs/` must not be copied into model-visible task evidence because they may contain expected answers, rubrics, or design notes.

### `jobs/`

Harbor run outputs.

Every Harbor run creates a job directory:

```text
jobs/<job_id>/
```

Important files:

```text
jobs/<job_id>/result.json
jobs/<job_id>/job.log
jobs/<job_id>/<trial>/result.json
jobs/<job_id>/<trial>/agent/*.txt
jobs/<job_id>/<trial>/verifier/reward.json
jobs/<job_id>/<trial>/verifier/review.json
jobs/<job_id>/<trial>/exception.txt
```

### `scripts/`

Local development helpers.

Current script:

```text
scripts/score_harbor_task.py
```

This is a lightweight local scoring helper. The canonical Harbor flow uses each task's `tests/test.sh`.

### `mockups/`

Prototype UI/design artifacts.

Current file:

```text
mockups/harbor-results-review.html
```

This is not part of the task runtime.

### `results/`

Human-readable sample results and notes.

Current file:

```text
results/dlbcl_sample_runs.md
```

## Task Anatomy

Each task has this structure:

```text
task.toml
instruction.md
environment/
  Dockerfile
  case/
solution/
  final_answer.json
  gold_answer.md
  solve.sh
tests/
  test.sh
  grader.py
  rubric.yaml
results/
  reward.json
  review.json
```

### `task.toml`

Task metadata.

For the DLBCL cases it declares:

```text
id
title
domain = hematology_oncology
subdomain = lymphoma
difficulty = intermediate
patient_type = synthetic
task_type = clinical_reasoning
input_format = narrative or fhir_bundle
expected_output = /app/final_answer.json
max_score = 100
passing_score = 75
```

It also points to:

```text
tests/rubric.yaml
solution/gold_answer.md
tests/test.sh
```

### `instruction.md`

The model-facing prompt.

It tells the model:

```text
read the patient evidence
answer the clinical tasks
write /app/final_answer.json
use the required JSON keys
```

This file is visible to the model.

### `environment/`

The task sandbox.

Current DLBCL Dockerfile pattern:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY case /app/case
RUN mkdir -p /app/outputs /logs/verifier

CMD ["bash"]
```

This is the model-visible boundary. Only `environment/case` is copied into `/app/case`.

The model does not receive:

```text
solution/
tests/
docs/
rubric.yaml
gold_answer.md
grader.py
```

### `environment/case/`

The patient evidence.

For the narrative DLBCL task:

```text
history.txt
labs.txt
imaging.txt
pathology.txt
```

For the FHIR DLBCL task:

```text
fhir_bundle.json
```

### `solution/`

Hidden reference answer.

Files:

```text
solution/final_answer.json
solution/gold_answer.md
solution/solve.sh
```

Purpose:

```text
define the expert/reference answer
support oracle runs
validate that the verifier can score a known-good answer
```

This is hidden from the model during normal eval.

### `tests/`

Verifier logic.

Files:

```text
tests/test.sh
tests/grader.py
tests/rubric.yaml
```

`test.sh` is the Harbor verifier entrypoint.

`grader.py` reads the model output and writes:

```text
/logs/verifier/reward.json
/logs/verifier/review.json
```

`rubric.yaml` documents the scoring intent.

### `results/`

Local smoke-test output.

These files show that the reference answer scores correctly:

```text
results/reward.json
results/review.json
```

## Current DLBCL Clinical Task

The model must infer:

```text
diagnosis
stage
biology
prognosis
first_line_treatment
cns_risk
response_assessment
missing_information
```

Expected output:

```text
/app/final_answer.json
```

Required JSON keys:

```json
{
  "diagnosis": "...",
  "stage": "...",
  "biology": "...",
  "prognosis": "...",
  "first_line_treatment": "...",
  "cns_risk": "...",
  "response_assessment": "...",
  "missing_information": []
}
```

Gold clinical conclusions:

```text
DLBCL, NOS
non-GCB phenotype by Hans algorithm
Hans non-GCB is not definitive molecular ABC subtype
Lugano/Ann Arbor stage III bulky disease
double-expressor lymphoma by IHC
not double-hit lymphoma because FISH rearrangements are negative
use IPI and CNS-IPI
curative-intent immunochemotherapy
Pola-R-CHP appropriate
R-CHOP acceptable
do not escalate to DA-EPOCH-R solely for double-expressor biology
CNS prophylaxis is not automatic from supplied data
response assessment with FDG PET-CT using Lugano/Deauville
```

## Model-Visible Boundary

The model should see:

```text
instruction.md
/app/case/*
```

The model should not see:

```text
solution/
tests/
docs/
gold answer
rubric
grader
critical-error penalties
breast PDF
```

Current Dockerfiles enforce this by copying only:

```text
environment/case -> /app/case
```

## Verifier Output

Compact score:

```text
verifier/reward.json
```

Detailed score:

```text
verifier/review.json
```

The compact score includes:

```text
reward
clinical_correctness
staging
molecular_classification
prognosis
first_line_treatment
cns_management
response_assessment
```

The detailed review includes criterion-level matches and penalties.

## Job Interpretation

Read a job in this order:

```text
1. jobs/<job_id>/result.json
2. jobs/<job_id>/<trial>/result.json
3. jobs/<job_id>/<trial>/agent/*.txt
4. jobs/<job_id>/<trial>/verifier/reward.json
5. jobs/<job_id>/<trial>/verifier/review.json
6. jobs/<job_id>/<trial>/exception.txt
7. harbor_cases/<case>/solution/gold_answer.md
```

Interpretation rules:

```text
n_errored_trials > 0
  The job had infrastructure/API/agent failures. Do not interpret reward as clinical performance yet.

exception_info != null
  Inspect agent logs and exception.txt.

reward = 0.0 with missing_final_answer
  The model probably failed to produce /app/final_answer.json.

n_errored_trials = 0
  The model produced answers and the verifier scored them.

review.json
  Use this for clinical interpretation. It explains what passed or failed.
```

## Known Runtime Paths

Gemini-only pipeline checks:

```text
scripts/check_gemini_pipeline.sh
scripts/check_gemini_pipeline.sh --live-api gemini-3.8-flash
```

Gemini run configs:

```text
configs/harbor-gemini-real-eval.json
configs/harbor-gemini-5case-eval.json
GEMINI_API_KEY
```

Recent Gemini failures were due to Gemini API quota/project-access errors, not task logic.

## Current Limitations

OncoWorldV1 is functional but still early.

Important limitations:

```text
rule-based regex grader can over-credit or under-credit unusual wording
clinical rubric needs physician review
critical-error penalties need physician validation
aggregate score should not be trusted without reading review.json
Gemini free-tier quota can block runs
breast case is documented but not yet implemented as task folders
```

## Planned Next Components

The breast PDF describes a future case pair:

```text
harbor_cases/breast_0001_narrative
harbor_cases/breast_0001_fhir
```

This is not yet implemented in `harbor_cases/`.

When implemented, it should follow the same architecture:

```text
instruction.md + environment/case/* visible to model
solution/ hidden
tests/ hidden
PDF kept as documentation only
```

## OncoWorldV1 In One Sentence

OncoWorldV1 is a Harbor-based oncology benchmark workspace where synthetic clinical cases are presented to AI agents in controlled Docker sandboxes, model answers are written as structured JSON, and hidden deterministic verifiers score clinical reasoning against gold answers and rubrics.
