You are participating in the first neuro-oncology tumor-board review.

This is a synthetic educational case reconstructed from an oncologist-provided teaching handout. This is the
first visit of a longitudinal follow-up: at later visits new records will be added to the chart and you will be
asked to update your plan. The source uses the term "intracranial mesenchymal tumor" but does not establish a
final molecular entity. Do not invent a definitive subtype. State uncertainty explicitly and identify the
pathology and molecular results that would change management.

This is a short-horizon task. Do not create a chemotherapy or definitive radiotherapy regimen for an unspecified
tumor. The available molecular information is not sufficient to establish a treatable entity. The appropriate
immediate plan is diagnostic confirmation, safe staging, symptom control, and multidisciplinary review.
Disease-directed treatment should remain deferred until the diagnosis, grade, extent, and resectability are
adequately established.

Read all files under `/app/case/`. Write one JSON object to `/app/answers/L1_initial_assessment.json` with these
keys:

- `initial_assessment`
- `diagnostic_confirmation_and_staging`
- `immediate_management_plan`
- `prognosis`
- `missing_information`

All values must be strings except `missing_information`, which must be a list of strings. For `prognosis`, state
what it depends on (the entity, WHO grade, extent, and dissemination) rather than quoting a specific survival
figure before the diagnosis is confirmed. Give a clinically reasoned short-horizon plan, not a list of unsupported
treatment options. This is not clinical decision support.
