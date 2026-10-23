You are the treating hematologist-oncologist. This is the same patient you assessed earlier, now on
2027-07-07: acute deterioration (day +6, inpatient).

This is a synthetic training case for AI evaluation. It is not clinical decision support.

The full chart is in `/app/case/chart/`. The earlier files are unchanged. The new documents for this visit
(numbered 4x) begin with an interval history describing what ACTUALLY happened since the last visit;
take that history as fact even if it differs from what you previously recommended. Your earlier answers are in
`/app/answers/`.

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
