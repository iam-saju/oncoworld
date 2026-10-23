You are the consulting hematologist-oncologist for this patient.

This is a synthetic training case for AI evaluation. It is not clinical decision support.
This is the first visit of a longitudinal follow-up: at later visits new records will be added to the
chart and you will be asked to update your plan.

The chart export is in `/app/case/chart/`: a patient summary followed by dated notes, reports and
laboratory results, numbered in chronological order.

The patient will be presented at lymphoma tumor board tomorrow. Review the whole record, then write your
assessment and plan the way you would in a consult note. Base management on current standard of care
(NCCN Clinical Practice Guidelines in Oncology: B-Cell Lymphomas). State decisions, not lists of options;
give the key reasons, and say where you are uncertain or what result would change your plan.

Write your answer to:

```text
/app/answers/L1_diagnosis.json
```

as one JSON object with these keys (string values, except `missing_information`, which is a list of strings, and
`decisions`, which is an object described below):

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
- `decisions`: your key decisions restated in fixed fields so they can be read without ambiguity. They must agree
  with your note. Fields:
  - `stage`: the anatomic stage you assign, as a Roman numeral only (no letters, suffixes or ranges)
  - `diagnosis`: your final diagnosis in a few words
  - `intent`: one of `curative`, `palliative`, `observation`
  - `regimen`: the first-line systemic regimen you are ordering, written as on the order, or `none`
  - `cycles`: number of cycles of that regimen (integer)
  - `cycle1_dose_percent`: percent of the full standard dose planned for cycle 1 (integer; 100 = full dose)
  - `radiotherapy`: planned radiotherapy in a few words, or `none`
  - `orders_now`: list of everything you order, start, stop or arrange unconditionally, now or before or with
    cycle 1 (drugs with dose and schedule, tests, procedures, consultations, medication changes)
  - `conditional_orders`: list of actions that depend on a future result or event, each written
    "if <condition>: <action>"
  - `lab_monitoring`: list of scheduled laboratory monitoring around the start of treatment, each
    `{"tests": "...", "every_hours": <integer or null>, "duration_hours": <integer or null>}`
