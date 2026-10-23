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
        # judge-less runs: kept out of every average (not a clinical zero); re-grade with scripts/rescore_job.py
        "unscored": review.get("status") == "unscored",
        "reason": review.get("reason", ""),
        "domains": {d: m["score"] for d, m in review.get("domains", {}).items()},
        "judge": review.get("judge", "none"),
        "review": review.get("needs_review", []) or [f"{x}(structured vs prose)" for x in review.get("structured_conflicts", [])],
    }


INFRA_MARKERS = ('"statusCode":402', '"statusCode":429', '"statusCode":500', '"statusCode":502', '"statusCode":503',
                 "Insufficient account funds", "Endpoint is unavailable", '"result":"API Error')


def step_infra(step_dir: Path) -> str | None:
    """A provider/API failure recorded in that step's agent log (not a clinical result)."""
    for log in ("opencode.txt", "claude-code.txt"):
        f = step_dir / "agent" / log
        if f.exists():
            text = f.read_text(errors="replace")
            hit = next((m for m in INFRA_MARKERS if m in text), None)
            if hit:
                return "HTTP " + hit.split(":")[1] if hit.startswith('"statusCode"') else hit.strip('"')
    return None


def journey_row(trial: dict, trial_dir: Path) -> dict | None:
    """Layer-weighted journey score. Every layer in task.toml counts: a layer the model answered badly, timed out on or
    never wrote is 0 and stays in the averages; only a layer lost to a provider/API failure marks the row INFRA."""
    task_dir = ROOT / trial["config"]["task"]["path"]
    if not task_dir.exists():   # narrative tasks moved to harbor_cases_narrative/ on 2026-10-22
        task_dir = ROOT / "harbor_cases_narrative" / task_dir.name
    task_toml = task_dir / "task.toml"
    cfg = tomllib.loads(task_toml.read_text()) if task_toml.exists() else {}
    weights = cfg.get("metadata", {}).get("layer_weights", {})
    expected = [s["name"] for s in cfg.get("steps", [])]
    results = {s["step_name"]: s for s in trial.get("step_results") or []}
    names = expected or list(results)
    layers, critical, missed, notes, total_w, acc, infra, review = [], [], [], [], 0.0, 0.0, False, []
    for name in names:
        lid, w = name.split("-")[0], float(weights.get(name.split("-")[0], 1))
        step = results.get(name)
        sdir = trial_dir / "steps" / name
        exc = ((step or {}).get("exception_info") or {}).get("exception_type")
        rescored = sdir / "verifier" / "rescored_review.json"
        review_path = rescored if rescored.exists() else sdir / "verifier" / "review.json"
        problem = step_infra(sdir) if step else None
        if step is None:
            score, tag = 0, "not run"
            notes.append(f"{lid} not run")
        elif review_path.exists():
            r = v2_row(json.loads(review_path.read_text()))
            score, tag = r["score"], ("*" if rescored.exists() else "")
            critical += [f"{lid}:{c}" for c in r["critical"] if c != "missing_final_answer"]
            review += [f"{lid}:{x}" for x in r["review"]]
            missed += [f"{lid}:{m}" for m in r["missed"]]
            if "missing_final_answer" in r["critical"]:
                tag = "no answer"
                critical.append(f"{lid}:missing_final_answer")
        else:
            score, tag = 0, "no review"
        if exc:
            tag = (tag + " " if tag else "") + exc
        if problem:
            infra, tag = True, (tag + " " if tag else "") + f"INFRA {problem}"
        total_w, acc = total_w + w, acc + w * score
        layers.append(f"{lid}={score}" + (f"({tag.strip()})" if tag.strip() and tag != "*" else ("*" if tag == "*" else "")))
    score = round(acc / total_w) if total_w else 0
    return {"score": score, "passed": not critical and score >= 75 and not notes, "critical": critical, "missed": missed,
            "infra": infra, "domains": {}, "judge": "-", "layers": " ".join(layers), "review": review}


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
        # scripts/rescore_job.py writes rescored_review.json with the current grader; prefer it when present
        rescored = trial_result.parent / "verifier" / "rescored_review.json"
        review_path = rescored if rescored.exists() else trial_result.parent / "verifier" / "review.json"
        version = "journey" if trial.get("step_results") else ("v2" if "_v2" in task else "v1")
        agent = (trial.get("config") or {}).get("agent") or {}
        model = agent.get("model_name") or agent.get("name") or "?"   # the oracle agent has no model name
        model = model.split("/")[-1]
        base = {"task": task, "model": model, "group": f"{task.split('_')[0]}-{version}  {model}",
                "format": "fhir" if task.endswith("_fhir") else "narrative", "rescored": rescored.exists()}
        if version == "journey":
            row = journey_row(trial, trial_result.parent)
            if trial.get("exception_info") and not trial.get("step_results"):
                errored.append((task, model, trial["exception_info"].get("exception_type", "error")))
                continue
            rows.append(base | row)
            continue
        if trial.get("exception_info") or not review_path.exists():
            errored.append((task, model, (trial.get("exception_info") or {}).get("exception_type", "no review.json")))
            continue
        review = json.loads(review_path.read_text())
        # the v2 grader's review.json always has a top-level "reward"; detect the shape from the data itself
        # rather than trusting "_v2" in the task name, since a hand-built case (e.g. a one-off teaching case)
        # may use the v2 grader without following that naming convention.
        if "reward" in review:
            base["group"] = f"{task.split('_')[0]}-v2  {model}"
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

    if any(r.get("rescored") for r in rows):
        print("(* = re-scored with the current grader by scripts/rescore_job.py)\n")
    print(f"{'case':46} {'model':26} {'score':>5}  pass  critical errors")
    for r in sorted(rows, key=lambda r: (r["task"], r["model"])):
        flag = "INFRA" if r["infra"] else "UNSC" if r.get("unscored") else ("yes" if r["passed"] else "no")
        extra = f"   [{r['layers']}]" if r.get("layers") else (f"   judge={r['judge']}" if r.get("judge") not in (None, "-", "none") else "")
        star = "*" if r.get("rescored") else " "
        if r.get("unscored"):
            print(f"{r['task']:46} {r['model']:26} {'-':>5}{star} {flag:4}  {r['reason']}")
            continue
        rv = f"   REVIEW {len(r['review'])}: {', '.join(r['review'][:6])}" if r.get("review") else ""
        print(f"{r['task']:46} {r['model']:26} {r['score']:>5}{star} {flag:4}  {', '.join(r['critical']) or '-'}{extra}{rv}")
    for task, model, why in errored:
        print(f"{task:46} {model:26} {'-':>5}  ERR   {why}  (not a clinical score; read agent/*.txt)")

    print("\nBy cancer type and rubric version (each averaged only over its own rubric):")
    groups = defaultdict(list)
    for r in rows:
        if not r["infra"] and not r.get("unscored"):
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
        if r["group"].startswith("dlbcl") and not r["infra"] and not r.get("unscored") and not r.get("layers"):
            pairs[(r["task"].rsplit("_", 1)[0], r["model"])][r["format"]] = r["score"]
    both = {k: v for k, v in pairs.items() if len(v) == 2}
    if both:
        print("\nNarrative vs FHIR (same patient):")
        for (k, model), v in sorted(both.items()):
            print(f"  {k:40} {model:26} narrative {v['narrative']:>3}   fhir {v['fhir']:>3}   diff {v['fhir'] - v['narrative']:+d}")

    print("\nMissed criteria (read the answer before calling these model errors):")
    for r in sorted(rows, key=lambda r: (r["task"], r["model"])):
        if r["missed"]:
            print(f"  {r['task']} [{r['model']}]: {', '.join(r['missed'])}")


if __name__ == "__main__":
    main()
