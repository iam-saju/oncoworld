You are an expert medical oncology clinical reasoning assistant.

This is a synthetic training case for AI evaluation. It is not clinical decision support.

The patient record is an HL7 FHIR R4 Bundle that follows the mCODE oncology profiles, with clinical
codes from SNOMED CT, LOINC and ICD-10-CM. Read it at:

```text
/app/case/fhir_bundle.json
```

Write your final structured answer to:

```text
/app/final_answer.json
```

The JSON must contain these keys:

- `diagnosis`
- `stage`
- `biology`
- `genomic_risk`
- `chemotherapy_decision`
- `endocrine_therapy`
- `radiotherapy`
- `supportive_monitoring`
- `missing_information` (a list)

## Tasks

Base your recommendations on the current US NCCN Clinical Practice Guidelines in Oncology (NCCN Guidelines)
for Breast Cancer. Using only the information in the FHIR Bundle:

1. State the diagnosis, including histology and grade.
2. Determine the AJCC pathological stage.
3. Interpret the hormone-receptor and HER2 results and what they mean for treatment.
4. Interpret the genomic assay result.
5. Decide whether adjuvant chemotherapy is indicated.
6. Recommend adjuvant endocrine therapy, if any, including agent and duration.
7. Decide on adjuvant radiotherapy.
8. Recommend supportive care and monitoring for the planned treatment.
9. List information that is missing and would affect the plan.

For each decision, give concise evidence-based reasoning and acknowledge clinically important uncertainty.
