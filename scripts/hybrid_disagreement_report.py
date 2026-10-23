#!/usr/bin/env python3
"""Aggregate judge/regex disagreements across saved hybrid-mode trials into a per-item report.

Usage: python3 scripts/hybrid_disagreement_report.py <job_dir_glob> [<job_dir_glob> ...]
Example: python3 scripts/hybrid_disagreement_report.py "jobs/*mesenchymal_journey*hybrid*"

For each item that appeared in at least one trial's review.json, reports how many trials evaluated it, how
many disagreed, which models those disagreements came from, and a flag.

Flag rule (small-N safe, per the hardening plan's item 5): at today's trial volumes a flat disagreement-RATE
threshold flags almost everything (1 of 3 trials is already 33%), so below 10 evaluations an item is flagged
by raw count instead - 2 or more disagreeing trials across 2 or more different models (a single model
disagreeing twice is not enough; that's one model's blind spot, not evidence the rubric is wrong for everyone).
At 10+ evaluations, switches to a 10% disagreement-rate threshold. Below 10 evaluations and not count-flagged,
reported as "insufficient data" - never silently counted as clean.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

COUNT_THRESHOLD_TRIALS = 2
COUNT_THRESHOLD_MODELS = 2
RATE_THRESHOLD_EVALUATIONS = 10
RATE_THRESHOLD = 0.10


def _model_name(review_path: Path) -> str:
    """Walk up from a review.json to the job's own config.json and read agents[0].model_name."""
    for parent in review_path.parents:
        cfg = parent / "config.json"
        if cfg.exists():
            try:
                agents = json.loads(cfg.read_text()).get("agents", [])
                if agents:
                    return agents[0].get("model_name", "unknown")
            except (json.JSONDecodeError, OSError):
                pass
    return "unknown"


def collect(job_globs: list[str]) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    seen_trials = 0
    for g in job_globs:
        for review_path in sorted(Path(p) for p in glob.glob(f"{g}/**/verifier/review.json", recursive=True)):
            try:
                r = json.loads(review_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if r.get("grader") != "hybrid":
                continue  # a regex-only or judge-only trial has no disagreement signal to aggregate
            seen_trials += 1
            model = _model_name(review_path)
            disagreed_ids = {d["id"] for d in r.get("judge_regex_disagreements", [])}
            for it in r.get("items", []):
                iid = it["id"]
                s = stats.setdefault(iid, {"evaluations": 0, "disagreements": 0, "models": set()})
                s["evaluations"] += 1
                if iid in disagreed_ids:
                    s["disagreements"] += 1
                    s["models"].add(model)
    if seen_trials == 0:
        print("No hybrid-mode review.json files found under the given path(s).", file=sys.stderr)
    return stats


def flag(s: dict) -> str:
    if s["evaluations"] >= RATE_THRESHOLD_EVALUATIONS:
        rate = s["disagreements"] / s["evaluations"]
        return f"FLAG (rate {rate:.0%} >= {RATE_THRESHOLD:.0%})" if rate >= RATE_THRESHOLD else "clean"
    if s["disagreements"] >= COUNT_THRESHOLD_TRIALS and len(s["models"]) >= COUNT_THRESHOLD_MODELS:
        return f"FLAG ({s['disagreements']} trials, {len(s['models'])} models)"
    if s["disagreements"] > 0:
        return "insufficient data (seen, below count/rate threshold)"
    return "insufficient data (never disagreed, but n < 10)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_globs", nargs="+")
    args = ap.parse_args()
    stats = collect(args.job_globs)
    if not stats:
        return
    rows = sorted(stats.items(), key=lambda kv: (-kv[1]["disagreements"], kv[0]))
    width = max(len(iid) for iid, _ in rows)
    print(f"{'item':<{width}}  evals  disagree  models  status")
    for iid, s in rows:
        print(f"{iid:<{width}}  {s['evaluations']:>5}  {s['disagreements']:>8}  "
              f"{len(s['models']):>6}  {flag(s)}")


if __name__ == "__main__":
    main()
