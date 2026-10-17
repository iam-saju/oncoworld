# Harbor Cases Explained

This workspace contains two Harbor-style oncology evaluation tasks under:

```text
harbor_cases/
```

They are not two separate patients. They are two representations of the same synthetic DLBCL case:

```text
dlbcl_0001_narrative
dlbcl_0001_fhir
```

Together, they test whether a model can reason about the same lymphoma case when the input is given as ordinary clinical prose versus structured FHIR data.

## What You Gave The Model

The clinical case is a synthetic hematology-oncology case about diffuse large B-cell lymphoma.

Core facts:

```text
Patient:
62-year-old man

Presentation:
Rapid cervical and abdominal lymphadenopathy
Fever, night sweats, weight loss
ECOG 1

Labs:
Hemoglobin 10.8 g/dL
WBC 7,800/uL
Platelets 210,000/uL
LDH 680 U/L, elevated

Imaging:
FDG-avid cervical nodes
Mediastinal lymphadenopathy
Bulky retroperitoneal lymphadenopathy, 11 cm
FDG-avid splenic lesions
No CNS lesions

Pathology:
Diffuse large B-cell lymphoma
CD20+
CD10-
BCL6+
MUM1+
BCL2 80%
MYC 50%
Ki-67 about 85%

FISH:
MYC rearrangement negative
BCL2 rearrangement negative
BCL6 rearrangement negative

Bone marrow:
No lymphoma involvement
```

The model must turn those facts into a structured clinical answer.

## What The Task Asks The Model To Produce

Each case asks the agent to write:

```text
/app/final_answer.json
```

The expected JSON keys are:

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

So the model is being evaluated on clinical reasoning, not free-form chat.

## Case 1: Narrative Variant

Path:

```text
harbor_cases/dlbcl_0001_narrative
```

This task gives the case as text files:

```text
environment/case/history.txt
environment/case/labs.txt
environment/case/imaging.txt
environment/case/pathology.txt
```

It represents a realistic chart-like input format. The model must read separate clinical notes and combine them into one decision.

This variant tests:

```text
Can the model read prose clinical evidence?
Can it combine history, labs, imaging, and pathology?
Can it produce a structured lymphoma management answer?
```

## Case 2: FHIR Variant

Path:

```text
harbor_cases/dlbcl_0001_fhir
```

This task gives the same case as a structured FHIR Bundle:

```text
environment/case/fhir_bundle.json
```

It represents a more machine-readable clinical data format.

This variant tests:

```text
Can the model extract clinical facts from structured FHIR-style JSON?
Can it reason from coded resources and diagnostic reports?
Does its clinical answer stay consistent with the narrative version?
```

## What The Correct Answer Represents

The gold answer expects these main conclusions:

```text
Diagnosis:
Diffuse large B-cell lymphoma, NOS

Cell-of-origin:
non-GCB phenotype by Hans algorithm
Do not treat Hans non-GCB as definitive molecular ABC subtype

Stage:
Lugano/Ann Arbor stage III bulky disease

Biology:
Double-expressor lymphoma by IHC
Not double-hit lymphoma, because FISH rearrangements are negative

Prognosis:
Use IPI and CNS-IPI
IPI is about 3 from supplied facts
CNS-IPI needs anatomic risk review

First-line treatment:
Curative-intent immunochemotherapy
Pola-R-CHP is appropriate
R-CHOP is acceptable
Do not escalate to DA-EPOCH-R solely because of double-expressor biology

CNS risk:
CNS prophylaxis is not automatic from the supplied data
Assess kidney/adrenal, testicular, breast, extranodal count, and other high-risk sites

Response assessment:
FDG PET-CT using Lugano/Deauville criteria
End-of-treatment PET is key
Biopsy residual PET-positive disease if it would change management
```

## What Each Folder/File Means

Each Harbor case follows this pattern:

```text
task.toml
instruction.md
environment/
solution/
tests/
results/
```

### `task.toml`

This is the task metadata.

It declares:

```text
case id
title
domain
input format
required reasoning dimensions
verifier path
expected output path
max score
passing score
```

Example concepts:

```text
domain = hematology_oncology
subdomain = lymphoma
task_type = clinical_reasoning
expected_output = /app/final_answer.json
passing_score = 75
```

### `instruction.md`

This is what the model sees.

It tells the model:

```text
Read the case files.
Answer the clinical questions.
Write /app/final_answer.json.
Use the required JSON keys.
```

### `environment/`

This is the sandboxed clinical world.

It contains:

```text
Dockerfile
case/
```

The `case/` folder contains the model-visible patient evidence.

### `solution/`

This is the hidden reference answer.

It contains:

```text
final_answer.json
gold_answer.md
solve.sh
```

This is used to check that the task and verifier are internally consistent.

The model should not rely on this during evaluation.

### `tests/`

This is the verifier.

It contains:

```text
test.sh
grader.py
rubric.yaml
```

`test.sh` is the entrypoint Harbor runs after the model finishes.

`grader.py` reads `/app/final_answer.json` and writes scores.

`rubric.yaml` describes the intended scoring categories.

### `results/`

This stores local smoke-test outputs from running the verifier against the reference answer.

These files are useful for development, but they are not the main Harbor job outputs.

## What A Harbor Run Does

When you run Harbor, the flow is:

```text
Harbor config
  -> chooses an agent/model
  -> starts the task sandbox
  -> gives the model instruction.md and /app/case/*
  -> model writes /app/final_answer.json
  -> tests/test.sh runs
  -> grader.py scores the answer
  -> reward.json and review.json are produced
```

The key output files for a run are under:

```text
jobs/<job_id>/
```

## What The Cases Represent

These cases represent a miniature medical benchmark.

They are designed to measure whether a model can:

```text
1. Extract clinical facts
2. Diagnose DLBCL
3. Stage lymphoma correctly
4. Distinguish double-expressor from double-hit lymphoma
5. Choose relevant prognostic scores
6. Recommend appropriate first-line therapy
7. Assess CNS relapse risk
8. Recommend response assessment
9. Identify missing information
```

The two variants also measure input-format robustness:

```text
Same patient, same expected reasoning,
but different input format.
```

That means you can compare:

```text
Does the model do better on prose?
Does it do better on FHIR?
Does it make the same mistakes in both?
```

## Important Interpretation Note

A score is only meaningful if the agent successfully produced:

```text
/app/final_answer.json
```

If the job failed because of API quota, model access, Docker, or CLI errors, then a `0.0` score usually means:

```text
No valid answer was produced.
```

It does not necessarily mean:

```text
The model made a clinically wrong answer.
```

Always inspect:

```text
jobs/<job_id>/<trial>/agent/*.txt
jobs/<job_id>/<trial>/verifier/review.json
jobs/<job_id>/<trial>/exception.txt
```

before drawing clinical conclusions.
