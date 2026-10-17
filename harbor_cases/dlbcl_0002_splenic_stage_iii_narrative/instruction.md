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

A 59-year-old woman presents with fatigue, intermittent fevers, and enlarging left axillary and abdominal lymph nodes.

Performance status:

- ECOG: 1

Laboratory data:

- Hemoglobin: 11.4 g/dL
- WBC: 6,900/uL
- Platelets: 178,000/uL
- LDH: 510 U/L, elevated

PET-CT:

- FDG-avid left axillary and mediastinal lymphadenopathy
- FDG-avid mesenteric and para-aortic lymphadenopathy
- FDG-avid splenic nodules
- Largest nodal mass: 7.5 cm
- No kidney, adrenal, testicular, breast, bone, liver, lung, marrow, or CNS lesions

Pathology:

- Excisional lymph-node biopsy: diffuse large B-cell lymphoma
- IHC: CD20+, CD10-, BCL6+, MUM1+, BCL2 70%, MYC 45%, Ki-67 approximately 80%
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
