You are the treating hematologist-oncologist. This is the same patient you assessed earlier, now on
2027-10-06: recovery and goals of care.

This is a synthetic training case for AI evaluation. It is not clinical decision support.

The full chart is in `/app/case/chart/`. The earlier files are unchanged. The new documents for this visit
(numbered 5x) begin with an interval history describing what ACTUALLY happened since the last visit;
take that history as fact even if it differs from what you previously recommended.

Answer each question with a clear decision, the key reasons, and important uncertainty. Base management on
current standard of care (NCCN Clinical Practice Guidelines in Oncology: B-Cell Lymphomas).

1. (q1) What does his current performance status mean for treatment options?
2. (q2) He declines further anticancer treatment. How do you proceed?
3. (q3) The family is financially drained. How do you address this?

Write your answer to:

```text
/app/answers/L5_goals_of_care.json
```

as one JSON object with string values for the keys `q1`, `q2`, `q3`.
