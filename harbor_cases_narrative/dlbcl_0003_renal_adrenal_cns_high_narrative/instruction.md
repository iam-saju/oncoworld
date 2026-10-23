You are an expert hematology-oncology clinical reasoning assistant.

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

A 67-year-old man presents with abdominal pain, early satiety, night sweats, and weight loss.

Performance status:

- ECOG: 2

Laboratory data:

- Hemoglobin: 9.9 g/dL
- WBC: 9,400/uL
- Platelets: 145,000/uL
- LDH: 1,120 U/L, elevated
- Creatinine: 1.4 mg/dL

PET-CT:

- FDG-avid retroperitoneal and mesenteric lymphadenopathy
- FDG-avid right renal cortical lesion, 3.2 cm
- FDG-avid left adrenal mass, 2.6 cm
- FDG-avid liver lesion, 1.8 cm
- No testicular, breast, or CNS lesions

Pathology:

- Core biopsy of retroperitoneal mass: diffuse large B-cell lymphoma
- IHC: CD20+, CD10+, BCL6+, MUM1-, BCL2 30%, MYC 20%, Ki-67 approximately 70%
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