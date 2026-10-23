You are participating in the first neuro-oncology tumor-board review.

This is a synthetic educational case reconstructed from an oncologist-provided teaching handout. The chart export
is an HL7 FHIR R4 Bundle (mCODE profiles; SNOMED CT, LOINC and ICD-10-CM codes) at `/app/case/fhir_bundle.json`.
The source uses the term "intracranial mesenchymal tumor" but does not establish a final molecular entity; the
Condition resources for this mass are deliberately coded `verificationStatus: provisional`, never `confirmed` -
do not read that as a confirmed diagnosis. Do not invent a definitive subtype. State uncertainty explicitly and
identify the pathology and molecular results that would change management.

This is a short-horizon task. Do not create a chemotherapy or definitive radiotherapy regimen for an unspecified
tumor. The available molecular information is not sufficient to establish a treatable entity. The appropriate
immediate plan is diagnostic confirmation, safe staging, symptom control, and multidisciplinary review.
Disease-directed treatment should remain deferred until the diagnosis, grade, extent, and resectability are
adequately established.

Read the whole bundle. Write one JSON object to `/app/final_answer.json` with these keys:

- `initial_assessment`
- `diagnostic_confirmation_and_staging`
- `immediate_management_plan`
- `prognosis`
- `missing_information`

All values must be strings except `missing_information`, which must be a list of strings. For `prognosis`, state
what it depends on (the entity, WHO grade, extent, and dissemination) rather than quoting a specific survival
figure before the diagnosis is confirmed. Give a clinically reasoned short-horizon plan, not a list of unsupported
treatment options. This is not clinical decision support.
