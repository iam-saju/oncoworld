# Breast PDF Change Summary

Source PDF:

```text
/Users/itsmesaju/Downloads/Harbor_Oncology_Case_Breast_0001.pdf
```

## Main Conclusion

The PDF is not model input. It is a benchmark design/specification document for a new breast-cancer Harbor task package.

It contains:

```text
patient chart
expected output schema
hidden gold answer
scoring rubric
critical-error penalties
run order
physician review checklist
open clinical questions
```

Because it includes the gold answer and scoring rules, it must not be copied into `/app/case/` or shown to the model during an eval.

## What Changed Compared With The Current DLBCL Cases

The current workspace has two DLBCL cases:

```text
harbor_cases/dlbcl_0001_narrative
harbor_cases/dlbcl_0001_fhir
```

The PDF proposes adding a new breast-cancer case pair:

```text
harbor_cases/breast_0001_narrative
harbor_cases/breast_0001_fhir
```

This is not a replacement for the DLBCL cases. It is a new oncology benchmark case.

## New Clinical Topic

The new case is:

```text
Early-stage hormone-receptor-positive / HER2-negative invasive ductal carcinoma
```

Core patient facts:

```text
58-year-old postmenopausal woman
screening-detected right breast mass
ECOG 0
lumpectomy and sentinel node biopsy completed
invasive ductal carcinoma NST
tumor size 1.8 cm
grade 2
no lymphovascular invasion
margins negative, 4 mm
sentinel nodes 0/2
ER 95% strong
PR 80%
HER2 IHC 1+, interpreted as HER2-negative
Ki-67 15%
21-gene recurrence score 14
DEXA not yet performed
```

## New Model-Visible Inputs

For the narrative version, the model should see only:

```text
instruction.md
environment/case/history.txt
environment/case/labs.txt
environment/case/imaging.txt
environment/case/pathology.txt
```

For the FHIR version, the model should see only:

```text
instruction.md
environment/case/fhir_bundle.json
```

The model should not see:

```text
solution/
tests/
gold_answer.md
rubric.yaml
grader.py
selftest answers
the PDF itself
```

## New Output Schema

The breast case uses a different JSON schema from the DLBCL case.

The model must write:

```text
/app/final_answer.json
```

with these keys:

```json
{
  "diagnosis": "...",
  "stage": "...",
  "biology": "...",
  "genomic_risk": "...",
  "chemotherapy_decision": "...",
  "endocrine_therapy": "...",
  "radiotherapy": "...",
  "supportive_monitoring": "...",
  "missing_information": ["..."]
}
```

This means the breast task cannot reuse the DLBCL answer schema unchanged.

## Hidden Gold Answer

The expected clinical conclusions are:

```text
Diagnosis:
Invasive ductal carcinoma NST, grade 2, 1.8 cm, margins negative.

Stage:
pT1c pN0(sn) M0.
Anatomic stage IA.
Pathological prognostic stage IA.

Biology:
HR-positive, HER2-negative.
HER2 IHC 1+ is HER2-negative / HER2-low.
Do not recommend anti-HER2 therapy.

Genomic risk:
21-gene recurrence score 14 = low risk.

Chemotherapy:
Adjuvant chemotherapy is not indicated.

Endocrine therapy:
Aromatase inhibitor for 5 years is appropriate.
Extended therapy up to 10 years may be considered.
Tamoxifen is an acceptable alternative.

Radiotherapy:
Whole-breast radiotherapy after lumpectomy.

Supportive monitoring:
Baseline DEXA.
Calcium/vitamin D.
Bone-health monitoring while on aromatase inhibitor.
```

## New Scoring Rubric

The PDF defines a 100-point draft rubric:

```text
Diagnosis and biology: 25
Genomic risk: 15
Chemotherapy decision: 20
Endocrine therapy: 20
Radiotherapy: 10
Supportive monitoring: 5
Missing information: 5
```

Critical penalties:

```text
Recommends adjuvant chemotherapy: -25
Recommends HER2-targeted therapy by treating IHC 1+ as positive: -20
Omits endocrine therapy: -20
Omits adjuvant radiotherapy: -10
```

Pass rule:

```text
score >= 75 and no critical error
```

## What Must Change In The Repository

To implement this PDF as Harbor tasks, add two new case folders:

```text
harbor_cases/breast_0001_narrative/
harbor_cases/breast_0001_fhir/
```

Each should follow the existing Harbor layout:

```text
task.toml
instruction.md
environment/
solution/
tests/
```

Changes needed:

```text
1. Create breast-specific instruction.md.
2. Create model-visible breast chart files under environment/case/.
3. Create breast-specific solution/final_answer.json.
4. Create breast-specific solution/gold_answer.md.
5. Create breast-specific rubric.yaml.
6. Create or adapt grader.py for the breast schema and scoring rules.
7. Add self-tests if using the PDF's proposed selftest pattern.
8. Add configs if you want a Harbor run config for breast evals.
9. Verify the model cannot access solution/ or tests/.
10. Have oncologists review the case, rubric, penalties, and guideline version before submission.
```

## What Should Not Change

Do not replace the existing DLBCL cases.

Do not put the PDF into model-visible evidence.

Do not expose:

```text
gold answer
rubric
critical-error penalties
grader implementation
selftest answers
```

to the model.

## Important Caveat

The PDF itself says:

```text
Draft v0.1.
Not physician-reviewed.
Every clinical statement, gold answer, scoring weight, and critical-error penalty must be checked before submission.
```

So this should be treated as a draft task specification, not as a finalized benchmark.

## Practical Next Step

The next engineering step is to create:

```text
harbor_cases/breast_0001_narrative
harbor_cases/breast_0001_fhir
```

using the existing DLBCL folder pattern, but with the breast-specific schema, gold answer, and grader.
