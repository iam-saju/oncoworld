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

A 54-year-old man presents with rapidly enlarging right cervical and mediastinal lymphadenopathy and dysphagia.

Performance status:

- ECOG: 1

Laboratory data:

- Hemoglobin: 12.6 g/dL
- WBC: 8,100/uL
- Platelets: 225,000/uL
- LDH: 740 U/L, elevated

PET-CT:

- FDG-avid right cervical lymphadenopathy
- FDG-avid mediastinal lymphadenopathy
- Bulky mediastinal mass, maximum diameter 12 cm
- No disease below the diaphragm
- No kidney, adrenal, testicular, breast, marrow, or CNS lesions

Pathology:

- Lymph-node biopsy: large B-cell lymphoma with high-grade morphology
- IHC: CD20+, CD10+, BCL6+, MUM1-, BCL2 90%, MYC 80%, Ki-67 approximately 95%
- FISH: MYC rearrangement detected; BCL2 rearrangement detected; BCL6 rearrangement not detected
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
