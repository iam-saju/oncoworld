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

A 62-year-old man presents with rapidly progressive cervical and abdominal lymphadenopathy, fever, night sweats, and 7-kg weight loss over 3 months.

Performance status:

- ECOG: 1

Laboratory data:

- Hemoglobin: 10.8 g/dL
- WBC: 7,800/uL
- Platelets: 210,000/uL
- LDH: 680 U/L, elevated

PET-CT:

- FDG-avid cervical nodes
- Mediastinal lymphadenopathy
- Bulky retroperitoneal lymphadenopathy, maximum diameter 11 cm
- FDG-avid splenic lesions
- No CNS lesions

Pathology:

- Lymph-node biopsy: diffuse large B-cell lymphoma
- IHC: CD20+, CD10-, BCL6+, MUM1+, BCL2 80%, MYC 50%, Ki-67 approximately 85%
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
