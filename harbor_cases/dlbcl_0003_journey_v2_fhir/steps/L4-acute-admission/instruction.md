You are the treating hematologist-oncologist. This is the same patient you assessed earlier, now on
2027-07-07: acute deterioration (day +6, inpatient).

This is a synthetic training case for AI evaluation. It is not clinical decision support.

The record is HL7 FHIR R4 (mCODE / US Core profiles; SNOMED CT, LOINC and ICD-10-CM codes). The original export is
`/app/case/fhir_bundle.json`; each later visit adds one update Bundle in `/app/case/fhir_updates/`, numbered in date
order. Earlier files are unchanged. The update for this visit is `/app/case/fhir_updates/03_2027-07-07_update.json`. Narrative notes
and reports are attached as base64 text in `DocumentReference.content.attachment` and
`DiagnosticReport.presentedForm`. The update's first document is an interval history describing what ACTUALLY
happened since the last visit; take that history as fact even if it differs from what you previously recommended.
Your earlier answers are in `/app/answers/`.

Answer each question with a clear decision, the key reasons, and important uncertainty. Base management on
current standard of care (NCCN Clinical Practice Guidelines in Oncology: B-Cell Lymphomas).

1. (q1) What do you consider first (immediate priorities)?
2. (q2) What are your differential diagnoses?
3. (q3) How do you investigate?

Write your answer to:

```text
/app/answers/L4_acute_admission.json
```

as one JSON object with string values for the keys `q1`, `q2`, `q3`.
