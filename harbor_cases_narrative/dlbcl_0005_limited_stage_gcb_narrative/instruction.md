You are an expert hematology-oncology clinical reasoning assistant.

This is a synthetic training case for AI evaluation. It is not clinical decision support.

Read the case files in `/app/case/` if they are available. Write your final structured answer to:

```text
/app/final_answer.json
```

The JSON must contain these keys:

- `diagnosis`
- `stage`
- `biology`
- `prognosis`
- `first_line_treatment`
- `cns_risk`
- `response_assessment`
- `missing_information`

## Clinical Case

A 45-year-old woman presents with a painless enlarging right cervical lymph node found on self-exam. She has no fever, night sweats, or weight loss.

Performance status:

- ECOG: 0

Laboratory data:

- Hemoglobin: 13.2 g/dL
- WBC: 5,900/uL
- Platelets: 240,000/uL
- LDH: 190 U/L, within normal range

PET-CT:

- Single FDG-avid right cervical lymph-node region, maximum diameter 3.1 cm
- No mediastinal, abdominal, splenic, marrow, kidney, adrenal, testicular/breast, or CNS lesions

Pathology:

- Excisional lymph-node biopsy: diffuse large B-cell lymphoma
- IHC: CD20+, CD10+, BCL6+, MUM1-, BCL2 30%, MYC 15%, Ki-67 approximately 55%
- FISH: MYC, BCL2, and BCL6 rearrangements negative
- Bone marrow: no lymphoma involvement

## Tasks

Using only the clinical information provided:

1. State the lymphoma diagnosis and relevant biological subtype.
2. Determine the Ann Arbor/Lugano stage.
3. Determine whether this is double-expressor or double-hit lymphoma.
4. Identify the major prognostic score or scores that should be used.
5. Recommend first-line systemic therapy.
6. Assess CNS-relapse risk and whether prophylaxis should be considered. Identify missing data.
7. Recommend a response-assessment strategy.

For each decision, provide concise evidence-based reasoning and explicitly acknowledge clinically important uncertainty.
