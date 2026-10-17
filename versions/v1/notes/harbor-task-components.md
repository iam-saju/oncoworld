# Harbor Oncology Task Components

Harbor tasks for OncoWorld should be cancer-case tasks, not legal or business tasks.
Each task should test whether a model can reason from clinical evidence to oncology decisions.

## Minimal Executable Task Folder

```text
case_id/
|-- task.toml
|-- instruction.md
|-- environment/
|   |-- Dockerfile
|   `-- case/
|       `-- clinical files
|-- solution/
|   |-- solve.sh
|   |-- final_answer.json
|   `-- gold_answer.md
`-- tests/
    |-- test.sh
    |-- grader.py
    `-- rubric.yaml
```

## Components

### 1. `task.toml`

Metadata used by the benchmark harness.

It should include:

- `id`
- `title`
- `domain`
- `subdomain`
- `difficulty`
- `patient_type`
- `task_type`
- required inference flags
- verifier, rubric, gold-answer, and expected-output filenames
- maximum score

### 2. `instruction.md`

This is the model input.

It tells the model or agent what to do and where to write the final answer.
For these prototype tasks, the expected output is:

```text
/app/final_answer.json
```

It should not contain the hidden gold answer.

### 3. `environment/`

This creates the sandboxed task world.

For these oncology prototypes:

- `environment/Dockerfile` creates a small Python container.
- `environment/case/` contains the clinical evidence the agent can read.
- The narrative task stores history, labs, imaging, and pathology as text files.
- The FHIR task stores the case as `fhir_bundle.json`.

### 4. `solution/`

This contains the oracle/reference completion.

- `solution/solve.sh` writes a known-good answer to `/app/final_answer.json`.
- `solution/final_answer.json` is the deterministic reference output.
- `solution/gold_answer.md` is the physician-facing reasoning key.

This helps sanity-check that the task is solvable.

### 5. `tests/`

This is the verifier.

- `tests/test.sh` is the verifier entry point.
- `tests/grader.py` reads the model output and writes `reward.json`.
- `tests/rubric.yaml` contains weighted domains and critical-error rules.

The verifier output shape is:

```json
{
  "reward": 1.0,
  "clinical_correctness": 1.0,
  "staging": 1.0,
  "molecular_classification": 1.0
}
```

Harbor 0.24 requires every top-level value in `reward.json` to be numeric. Detailed domain notes, point totals, and critical-error details are written separately to `review.json`.

### 6. `gold_answer.md`

This is hidden from the model.

It contains the expert reference:

- diagnosis
- staging
- molecular classification
- prognostic reasoning
- recommended management
- missing information
- response assessment

### 7. `rubric.yaml`

This is the scoring contract.

It should include:

- total points
- weighted scoring domains
- subcriteria points
- critical error penalties
- passing score

Critical errors are important in medicine. A model can sound fluent but still make a dangerous error, such as treating double-expressor lymphoma as double-hit lymphoma or recommending non-curative treatment for a fit patient.

## Input And Output

### Input To The Model

The model receives `instruction.md` and can inspect files inside `/app/case/`.

For example:

```text
You are an expert hematology-oncology clinical reasoning assistant.

Clinical case...

Tasks:
1. State the diagnosis.
2. Determine Lugano stage.
3. Recommend first-line therapy.
...
```

### Output From The Model

The model should write structured JSON to `/app/final_answer.json`:

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

### Output From The Evaluator

The evaluator compares the model response to `gold_answer.md` and `rubric.yaml`.

Expected evaluator output:

```json
{
  "reward": 0.95,
  "clinical_correctness": 1.0,
  "staging": 0.9,
  "first_line_treatment": 0.8
}
```

## Process

1. Create a synthetic or fully de-identified oncology case.
2. Write the model-visible input in `instruction.md`.
3. Write the hidden expert answer in `gold_answer.md`.
4. Write weighted scoring rules in `rubric.yaml`.
5. Run the oracle/reference solution first.
6. Confirm the verifier passes on the known-good answer.
7. Run a model or agent on `instruction.md` inside the environment.
8. The agent writes `/app/final_answer.json`.
9. Harbor runs `tests/test.sh`.
10. The verifier writes `/logs/verifier/reward.json`.
11. Review any low-score or critical-error outputs with an oncology specialist.

## Harbor/Gemini Workflow

The practical workflow is:

```text
Harbor task
  -> Harbor runner
  -> Gemini CLI agent
  -> Gemini model
  -> Docker sandbox
  -> /app/final_answer.json
  -> tests/test.sh
  -> /logs/verifier/reward.json
```

Gemini does not grade itself. Gemini produces the answer. The verifier grades the answer against the physician-approved rubric.

For a real run, use the official Harbor command shape after Harbor, Docker, Gemini CLI credentials, and the exact Google model ID are confirmed:

```bash
harbor run \
  -p ./harbor_cases/dlbcl_0001_narrative \
  -a oracle
```

Then run the model:

```bash
harbor run \
  -p ./harbor_cases/dlbcl_0001_narrative \
  -a gemini-cli \
  -m google/<confirmed-gemini-model-id>
```

Do not put API keys in `task.toml` or in the repository. Use environment variables such as `GEMINI_API_KEY` or `GOOGLE_API_KEY`, depending on the Gemini CLI integration.

## Current Case Variants

This workspace includes two DLBCL task variants derived from the attached PDFs:

- `harbor_cases/dlbcl_0001_narrative`: prose clinical-case input.
- `harbor_cases/dlbcl_0001_fhir`: structured FHIR Bundle input.

They use the same underlying clinical facts and gold answer. The difference is the model input format.
