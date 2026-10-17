You are an expert hematology-oncology clinical reasoning assistant.

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
- `prognosis`
- `first_line_treatment`
- `cns_risk`
- `response_assessment`
- `missing_information`

## Tasks

Using only the information in the FHIR Bundle:

1. State the lymphoma diagnosis and relevant biological subtype.
2. Determine the Ann Arbor/Lugano stage.
3. Determine whether this is double-expressor or double-hit lymphoma.
4. Identify the major prognostic score or scores that should be used.
5. Recommend first-line systemic therapy.
6. Assess CNS-relapse risk and whether prophylaxis should be considered. Identify missing data.
7. Recommend a response-assessment strategy.

For each decision, provide concise evidence-based reasoning and explicitly acknowledge clinically important uncertainty.