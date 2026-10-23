#!/usr/bin/env python3
"""Re-score saved mesenchymal journey trials with the current grader_v2.py + rubric, without re-calling the
live judge API. Per the hardening plan's item 5.5: items 2/3/4/4b/5 changed scoring in ways that should only
ever raise L3 (alt_group's ceiling fix, applies_if removing the vacuous free-points bug, regex-authoritative
hybrid no longer letting a wrong judge call cost points) - this reports the corrected numbers against every
trial already on record, and recomputes disagreements against the new regex/rubric using each trial's
already-saved judge verdict (its "evidence"/"judge_met" fields are a faithful record of what the judge said
at the time; only the regex/rubric side has changed since, so there is nothing to re-ask the judge about).

Usage: python3 scripts/rescore_mesenchymal_trials.py <job_dir_glob> [<job_dir_glob> ...]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "graders" / "oncoworld_grader"))
sys.path.insert(0, str(ROOT / "scripts"))
import grader_v2 as G  # noqa: E402
from hybrid_disagreement_report import flag  # noqa: E402

RUBRIC_CACHE: dict[Path, dict] = {}


def _rubric_for_step(case_path: str, step: str) -> dict | None:
    rp = ROOT / case_path / "steps" / step / "tests" / "rubric_v2.toml"
    if rp not in RUBRIC_CACHE:
        if not rp.exists():
            return None
        RUBRIC_CACHE[rp] = tomllib.loads(rp.read_text())
    return RUBRIC_CACHE[rp]


def _judge_verdicts(old_items: list[dict]) -> dict | None:
    verdicts = {it["id"]: {"met": it["judge_met"], "evidence": it.get("evidence", "")}
                for it in old_items if it.get("judge_met") is not None}
    return verdicts or None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_globs", nargs="+")
    args = ap.parse_args()

    rows = []
    for g in args.job_globs:
        for review_path in sorted(Path(p) for p in glob.glob(f"{g}/**/verifier/review.json", recursive=True)):
            step_dir = review_path.parent.parent
            step = step_dir.name
            answer_path = review_path.with_name("final_answer.json")
            cfg_path = next((p / "config.json" for p in review_path.parents if (p / "config.json").exists()), None)
            if not answer_path.exists() or cfg_path is None:
                continue
            old = json.loads(review_path.read_text())
            cfg = json.loads(cfg_path.read_text())
            # the nearest config.json walking up from review.json is the trial-level one (singular task/agent,
            # resolved for this one trial) - not the job-level config this session more often works with
            # (plural tasks/agents, the original multi-task file); shapes differ, so read the singular form.
            case_path = cfg.get("task", {}).get("path", "")
            rubric = _rubric_for_step(case_path, step)
            if rubric is None:
                continue
            model = cfg.get("agent", {}).get("model_name", "unknown")
            response = answer_path.read_text()
            verdicts = _judge_verdicts(old.get("items", [])) if old.get("grader") in ("judge", "hybrid") else None
            new = G.score(response, rubric, verdicts)
            rows.append({
                "job": review_path.parts[review_path.parts.index("jobs") + 1] if "jobs" in review_path.parts else "?",
                "model": model, "step": step,
                "old_reward": old.get("reward"), "new_reward": new["reward"],
                "old_disagreements": len(old.get("judge_regex_disagreements", [])),
                "new_disagreements": len(new["judge_regex_disagreements"]),
                "new_disagreement_ids": {d["id"] for d in new["judge_regex_disagreements"]},
                "new_items": new["items"],
            })

    if not rows:
        print("No matching trials found.", file=sys.stderr)
        return

    width_job = max(len(r["job"]) for r in rows)
    width_model = max(len(r["model"]) for r in rows)
    print(f"{'job':<{width_job}}  {'model':<{width_model}}  {'step':<30}  old_reward  new_reward  delta  "
          f"old_dis  new_dis")
    for r in sorted(rows, key=lambda r: (r["job"], r["step"])):
        delta = (r["new_reward"] or 0) - (r["old_reward"] or 0)
        print(f"{r['job']:<{width_job}}  {r['model']:<{width_model}}  {r['step']:<30}  "
              f"{r['old_reward']:.4f}      {r['new_reward']:.4f}      {delta:+.4f}  "
              f"{r['old_disagreements']:>7}  {r['new_disagreements']:>7}")

    deltas = [(r["new_reward"] or 0) - (r["old_reward"] or 0) for r in rows]
    print()
    print(f"{len(rows)} trials rescored. reward delta: min={min(deltas):+.4f} max={max(deltas):+.4f} "
          f"mean={sum(deltas)/len(deltas):+.4f}")
    worse = [r for r in rows if (r["new_reward"] or 0) < (r["old_reward"] or 0)]
    if worse:
        print(f"{len(worse)} trial(s) scored lower - not necessarily a bug (a newly-added item correctly "
              f"catching an answer written before it existed, or an unrelated earlier-today regex fix/revert "
              f"this trial predates, both score lower correctly) but worth a quick look, not an assumption:")
        for r in worse:
            print(f"  {r['job']} / {r['step']}: {r['old_reward']:.4f} -> {r['new_reward']:.4f}")

    # corrected per-item disagreement report, reusing the exact flag rule from hybrid_disagreement_report.py,
    # computed fresh against the current grader+rubric rather than read from each trial's stale review.json.
    stats: dict[str, dict] = {}
    for r in rows:
        if r["old_disagreements"] == 0 and r["new_disagreements"] == 0 and not r["new_items"]:
            continue
        for it in r["new_items"]:
            iid = it["id"]
            if it.get("judge_met") is None:
                continue  # no judge verdict for this item on this trial - nothing to compare
            s = stats.setdefault(iid, {"evaluations": 0, "disagreements": 0, "models": set()})
            s["evaluations"] += 1
            if iid in r["new_disagreement_ids"]:
                s["disagreements"] += 1
                s["models"].add(r["model"])
    if stats:
        print()
        print("corrected per-item disagreement report (recomputed against current grader+rubric):")
        items_rows = sorted(stats.items(), key=lambda kv: (-kv[1]["disagreements"], kv[0]))
        w = max(len(iid) for iid, _ in items_rows)
        print(f"  {'item':<{w}}  evals  disagree  models  status")
        for iid, s in items_rows:
            print(f"  {iid:<{w}}  {s['evaluations']:>5}  {s['disagreements']:>8}  "
                  f"{len(s['models']):>6}  {flag(s)}")


if __name__ == "__main__":
    main()
