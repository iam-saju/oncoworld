You are the treating neuro-oncologist. This is the same patient you assessed earlier, now on 2027-01-12.

This is a synthetic educational case reconstructed from an oncologist-provided teaching handout, continued from
earlier visits. It is not clinical decision support.

The record is HL7 FHIR R4 (mCODE profiles; SNOMED CT, LOINC and ICD-10-CM codes). The original export is
`/app/case/fhir_bundle.json`; this visit adds one update Bundle at `/app/case/fhir_updates/01_2027-01-12_update.json`.
Earlier files are unchanged. The update's first document is an interval history describing what ACTUALLY happened
since the last visit; take that history as fact even if it differs from what you previously recommended. Your
earlier answers are in `/app/answers/`.

Answer each question with a clear decision and the key reasons. The final histologic entity is still not
established - do not invent one, and do not treat a molecular finding alone as establishing it.

1. (q1) The liquid biopsy result is not back yet and the family wants to start treatment now rather than wait.
   What chemotherapy options would you consider for this patient?
2. (q2) The patient was started on single-agent oral temozolomide and has tolerated it well for several weeks,
   with no significant toxicity. Would you consider adding a second chemotherapy drug? If so, what, and why?
3. (q3) The liquid biopsy NGS report has now returned, four weeks after the sample was sent. It shows four
   molecular alterations: an FGFR2 fusion, and KRAS, STK11, and CTNNB1 alterations. Will you stop chemotherapy
   and change to targeted therapy, or not? Give your reasons.

Write your answer to:

```text
/app/answers/L3_chemo_and_targeted_therapy.json
```

as one JSON object with string values for the keys `q1`, `q2`, `q3`.
