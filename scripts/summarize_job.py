#!/usr/bin/env python3
"""Summarize a Harbor job per case and per cancer type.

Harbor's own table averages every metric over all trials in the job, so a job that mixes breast and DLBCL
cases dilutes breast-only metrics (e.g. chemotherapy_decision) by the number of DLBCL trials. This script
reads each trial's verifier/review.json and groups results so nothing is averaged across different rubrics.

It understands three review formats:
  v1        tests/grader.py (score / critical_errors / metrics)
  v2        graders/oncoworld_grader/grader_v2.py (reward / dangerous_errors / domains / items)
  journey   v2 multi-step tasks: one v2 review per step under steps/<step>/verifier/. The case score is the
            layer-weighted mean (task.toml [metadata].layer_weights) and a dangerous error in any layer fails the case.
            Harbor's own "mean" averages domain keys across layers with missing keys as 0, so ignore its domain table.

Usage: python3 scripts/summarize_job.py [jobs/<job-folder>]   (default: most recent job)
"""
from __future__ import annotations

import json
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def v2_row(review: dict) -> dict:
    return {
        "score": round(review["reward"] * 100),
        "passed": review["passed"],
        "critical": review.get("dangerous_errors", []),
        "missed": [i["id"] for i in review.get("items", [])
                   if (i["kind"] != "must_not" and not i["met"]) or (i["kind"] == "must_not" and i["met"])],
        "infra": "missing_final_answer" in review.get("dangerous_errors", []),
        "domains": {d: m["score"] for d, m in review.get("domains", {}).items()},
        "judge": review.get("judge", "none"),
    }


def journey_row(trial: dict, trial_dir: Path) -> dict | None:
    task_toml = ROOT / trial["config"]["task"]["path"] / "task.toml"
    weights = tomllib.loads(task_toml.read_text()).get("metadata", {}).get("layer_weights", {}) if task_toml.exists() else {}
    layers, critical, missed, total_w, acc = [], [], [], 0.0, 0.0
    for step in trial.get("step_results") or []:
        name = step["step_name"]
        review_path = trial_dir / "steps" / name / "verifier" / "review.json"
        if not review_path.exists():
            return None
        r = v2_row(json.loads(review_path.read_text()))
        w = float(weights.get(name.split("-")[0], 1))
        total_w, acc = total_w + w, acc + w * r["score"]
        layers.append(f"{name.split('-')[0]}={r['score']}")
        critical += [f"{name.split('-')[0]}:{c}" for c in r["critical"]]
        missed += [f"{name.split('-')[0]}:{m}" for m in r["missed"]]
    score = round(acc / total_w) if total_w else 0
    return {"score": score, "passed": not critical and score >= 75, "critical": critical, "missed": missed,
            "infra": any(c.endswith("missing_final_answer") for c in critical), "domains": {}, "judge": "-",
            "layers": " ".join(layers)}


def latest_job(root: Path) -> Path:
    jobs = [p for p in (root / "jobs").iterdir() if (p / "result.json").exists()]
    return max(jobs, key=lambda p: p.stat().st_mtime)


def main() -> None:
    job = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_job(ROOT)
    job_result = json.loads((job / "result.json").read_text())
    stats = job_result["stats"]

    rows, errored = [], []
    for trial_result in sorted(job.glob("*/result.json")):
        trial = json.loads(trial_result.read_text())
        task = trial["task_name"]
        review_path = trial_result.parent / "verifier" / "review.json"
        version = "journey" if trial.get("step_results") else ("v2" if "_v2" in task else "v1")
        base = {"task": task, "group": f"{task.split('_')[0]}-{version}",
                "format": "fhir" if task.endswith("_fhir") else "narrative"}
        if version == "journey":
            row = journey_row(trial, trial_result.parent)
            if trial.get("exception_info") or row is None:
                errored.append((task, (trial.get("exception_info") or {}).get("exception_type", "missing step review.json")))
                continue
            rows.append(base | row)
            continue
        if trial.get("exception_info") or not review_path.exists():
            errored.append((task, (trial.get("exception_info") or {}).get("exception_type", "no review.json")))
            continue
        review = json.loads(review_path.read_text())
        if version == "v2":
            rows.append(base | v2_row(review))
            continue
        rows.append(base | {
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
        extra = f"   [{r['layers']}]" if r.get("layers") else (f"   judge={r['judge']}" if r.get("judge") not in (None, "-") else "")
        print(f"{r['task']:46} {r['score']:>5}  {flag:4}  {', '.join(r['critical']) or '-'}{extra}")
    for task, why in errored:
        print(f"{task:46} {'-':>5}  ERR   {why}  (not a clinical score; read agent/*.txt)")

    print("\nBy cancer type and rubric version (each averaged only over its own rubric):")
    groups = defaultdict(list)
    for r in rows:
        if not r["infra"]:
            groups[r["group"]].append(r)
    for g, rs in sorted(groups.items()):
        mean = sum(r["score"] for r in rs) / len(rs)
        print(f"  {g:14} {len(rs)} cases   mean {mean:5.1f}   passed {sum(r['passed'] for r in rs)}/{len(rs)}   "
              f"critical errors {sum(len(r['critical']) for r in rs)}")
        domains = defaultdict(list)
        for r in rs:
            for d, v in r["domains"].items():
                domains[d].append(v)
        for d, vs in sorted(domains.items()):
            print(f"      {d:28} {sum(vs) / len(vs):.2f}  (n={len(vs)})")

    pairs = defaultdict(dict)
    for r in rows:
        if r["group"].startswith("dlbcl") and not r["infra"] and not r.get("layers"):
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
