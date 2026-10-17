#!/usr/bin/env python3
"""Summarize a Harbor job per case and per cancer type.

Harbor's own table averages every metric over all trials in the job, so a job that mixes breast and DLBCL
cases dilutes breast-only metrics (e.g. chemotherapy_decision) by the number of DLBCL trials. This script
reads each trial's verifier/review.json and groups results so nothing is averaged across different rubrics.

Usage: python3 scripts/summarize_job.py [jobs/<job-folder>]   (default: most recent job)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def latest_job(root: Path) -> Path:
    jobs = [p for p in (root / "jobs").iterdir() if (p / "result.json").exists()]
    return max(jobs, key=lambda p: p.stat().st_mtime)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    job = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_job(root)
    job_result = json.loads((job / "result.json").read_text())
    stats = job_result["stats"]

    rows, errored = [], []
    for trial_result in sorted(job.glob("*/result.json")):
        trial = json.loads(trial_result.read_text())
        task = trial["task_name"]
        review_path = trial_result.parent / "verifier" / "review.json"
        if trial.get("exception_info") or not review_path.exists():
            errored.append((task, (trial.get("exception_info") or {}).get("exception_type", "no review.json")))
            continue
        review = json.loads(review_path.read_text())
        rows.append({
            "task": task,
            "group": task.split("_")[0],  # breast / dlbcl
            "format": "fhir" if task.endswith("_fhir") else "narrative",
            "score": review["score"],
            "passed": review["passed"],
            "critical": [c["name"] for c in review.get("critical_errors", [])],
            "missed": [f"{d}.{c}" for d, m in review.get("metrics", {}).items()
                       for c, x in m["criteria"].items() if not x["matched"]],
            "infra": review.get("infra_failure") or "missing_final_answer" in str(review.get("critical_errors")),
            "domains": {d: m["score"] for d, m in review.get("metrics", {}).items()},
        })

    agents = {f"{a.get('name')} / {a.get('model_name', '-')}" for a in json.loads((job / "config.json").read_text()).get("agents", [])}
    print(f"Job: {job.name}   agent: {', '.join(agents)}")
    print(f"Trials: {job_result['n_total_trials']}   errored: {stats['n_errored_trials']}   cost: ${stats.get('cost_usd') or 0:.3f}\n")

    print(f"{'case':46} {'score':>5}  pass  critical errors")
    for r in sorted(rows, key=lambda r: r["task"]):
        flag = "INFRA" if r["infra"] else ("yes" if r["passed"] else "no")
        print(f"{r['task']:46} {r['score']:>5}  {flag:4}  {', '.join(r['critical']) or '-'}")
    for task, why in errored:
        print(f"{task:46} {'-':>5}  ERR   {why}  (not a clinical score; read agent/*.txt)")

    print("\nBy cancer type (each averaged only over its own rubric):")
    groups = defaultdict(list)
    for r in rows:
        if not r["infra"]:
            groups[r["group"]].append(r)
    for g, rs in sorted(groups.items()):
        mean = sum(r["score"] for r in rs) / len(rs)
        print(f"  {g:7} {len(rs)} cases   mean {mean:5.1f}   passed {sum(r['passed'] for r in rs)}/{len(rs)}   "
              f"critical errors {sum(len(r['critical']) for r in rs)}")
        domains = defaultdict(list)
        for r in rs:
            for d, v in r["domains"].items():
                domains[d].append(v)
        for d, vs in sorted(domains.items()):
            print(f"      {d:28} {sum(vs) / len(vs):.2f}  (n={len(vs)})")

    pairs = defaultdict(dict)
    for r in rows:
        if r["group"] == "dlbcl" and not r["infra"]:
            pairs[r["task"].rsplit("_", 1)[0]][r["format"]] = r["score"]
    both = {k: v for k, v in pairs.items() if len(v) == 2}
    if both:
        print("\nNarrative vs FHIR (same patient):")
        for k, v in sorted(both.items()):
            print(f"  {k:40} narrative {v['narrative']:>3}   fhir {v['fhir']:>3}   diff {v['fhir'] - v['narrative']:+d}")

    print("\nMissed criteria (read the answer before calling these model errors):")
    for r in sorted(rows, key=lambda r: r["task"]):
        if r["missed"]:
            print(f"  {r['task']}: {', '.join(r['missed'])}")


if __name__ == "__main__":
    main()
