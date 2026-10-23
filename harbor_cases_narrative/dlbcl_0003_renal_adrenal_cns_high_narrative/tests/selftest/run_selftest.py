#!/usr/bin/env python3
"""Grader self-test. Run from anywhere: python3 tests/selftest/run_selftest.py

answers/*.json each hold an answer plus an `_expect` block:
  passed            True/False
  critical          exact list of critical-error names
  must_match        criteria "domain.name" that must earn credit
  must_miss         criteria that must NOT earn credit (real model errors the grader has to keep catching)
  score (optional)  exact score
The answers starting 'gemini_' are real model outputs saved from Harbor jobs; the expectations on them were
set by reading the answer, so a grader change that flips one needs a reason, not a new expectation.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from grader import score  # noqa: E402

failures = 0
for f in sorted((HERE / "answers").glob("*.json")):
    doc = json.loads(f.read_text())
    expect = doc.pop("_expect")
    r = score(json.dumps(doc, ensure_ascii=False))
    got_crit = sorted(c["name"] for c in r["critical_errors"])
    matched = {f"{d}.{c}" for d, m in r["metrics"].items() for c, x in m["criteria"].items() if x["matched"]}
    problems = []
    if r["passed"] != expect["passed"]:
        problems.append(f"passed={r['passed']} expected {expect['passed']}")
    if got_crit != sorted(expect.get("critical", [])):
        problems.append(f"critical={got_crit} expected {expect.get('critical', [])}")
    for c in expect.get("must_match", []):
        if c not in matched:
            problems.append(f"should credit {c}")
    for c in expect.get("must_miss", []):
        if c in matched:
            problems.append(f"should NOT credit {c}")
    if "score" in expect and r["score"] != expect["score"]:
        problems.append(f"score={r['score']} expected {expect['score']}")
    failures += bool(problems)
    print(f"{'ok  ' if not problems else 'FAIL'} {f.name:48s} score={r['score']:>3} {'; '.join(problems)}")

print("ALL SELF-TESTS PASSED" if not failures else f"{failures} SELF-TEST(S) FAILED")
sys.exit(1 if failures else 0)
