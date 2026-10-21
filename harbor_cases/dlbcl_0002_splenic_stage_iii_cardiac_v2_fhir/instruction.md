You are the consulting hematologist-oncologist for this patient.

This is a synthetic training case for AI evaluation. It is not clinical decision support.

The chart export is an HL7 FHIR R4 Bundle (mCODE / US Core profiles; SNOMED CT, LOINC and ICD-10-CM codes)
at `/app/case/fhir_bundle.json`. Narrative notes and reports are attached as base64 text in
`DocumentReference.content.attachment` and `DiagnosticReport.presentedForm`.

The patient will be presented at lymphoma tumor board tomorrow. Review the whole record, then write your
assessment and plan the way you would in a consult note. Base management on current standard of care
(NCCN Clinical Practice Guidelines in Oncology: B-Cell Lymphomas). State decisions, not lists of options;
give the key reasons, and say where you are uncertain or what result would change your plan.

Write your answer to:

```text
/app/final_answer.json
```

as one JSON object with these keys (string values, except `missing_information`, which is a list of strings):

- `diagnosis`
- `stage`
- `biology`
- `prognosis`
- `first_line_treatment`
- `cns_risk`
- `response_assessment`
- `pretreatment_workup`
- `supportive_care`
- `fitness_and_goals`
- `missing_information`
