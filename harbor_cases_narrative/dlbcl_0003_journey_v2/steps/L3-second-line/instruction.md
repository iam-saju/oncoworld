You are the treating hematologist-oncologist. This is the same patient you assessed earlier, now on
2027-05-12: second-line therapy and a molecular report.

This is a synthetic training case for AI evaluation. It is not clinical decision support.

The full chart is in `/app/case/chart/`. The earlier files are unchanged. The new documents for this visit
(numbered 3x) begin with an interval history describing what ACTUALLY happened since the last visit;
take that history as fact even if it differs from what you previously recommended. Your earlier answers are in
`/app/answers/`.

Answer each question with a clear decision, the key reasons, and important uncertainty. Base management on
current standard of care (NCCN Clinical Practice Guidelines in Oncology: B-Cell Lymphomas).

1. (q1) Which second-line strategy do you recommend, and why?
2. (q2) He feels well and asks whether adding more drugs now would improve his chances. What do you advise for the period before definitive second-line therapy?
3. (q3) How do you interpret the NGS report, and does it change treatment?

Write your answer to:

```text
/app/answers/L3_second_line.json
```

as one JSON object with string values for the keys `q1`, `q2`, `q3`.
