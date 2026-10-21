#!/usr/bin/env python3
"""v2 grader self-test. Run: python3 tests/selftest/run_selftest.py

answers/*.json hold an answer plus an `_expect` block:
  passed      True/False
  dangerous   exact list of dangerous item ids that must fire
  must_met    item ids that must be met
  must_unmet  item ids that must NOT be met
Runs in regex-fallback mode (no judge), so it is deterministic and free.
judge_cases/*.json hold {"answer": ..., "verdicts": ..., "_expect": ...} to test judge aggregation offline.
"""
import json
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from grader_v2 import score  # noqa: E402

rubric = tomllib.loads((HERE.parent / "rubric_v2.toml").read_text())
failures = 0


def check(name, r, expect):
    problems = []
    met = {i["id"] for i in r["items"] if i["met"]}
    if r["passed"] != expect["passed"]:
        problems.append(f"passed={r['passed']} expected {expect['passed']}")
    if "dangerous" in expect and sorted(r["dangerous_errors"]) != sorted(expect["dangerous"]):
        problems.append(f"dangerous={r['dangerous_errors']} expected {expect['dangerous']}")
    problems += [f"should meet {i}" for i in expect.get("must_met", []) if i not in met]
    problems += [f"should NOT meet {i}" for i in expect.get("must_unmet", []) if i in met]
    if expect.get("all_met") is True:
        problems += [f"unmet {i['id']}" for i in r["items"] if i["kind"] != "must_not" and not i["met"]]
    print(f"{'ok  ' if not problems else 'FAIL'} {name:44s} reward={r['reward']:<6} {'; '.join(problems)}")
    return bool(problems)


for f in sorted((HERE / "answers").glob("*.json")):
    doc = json.loads(f.read_text())
    expect = doc.pop("_expect")
    failures += check(f.name, score(json.dumps(doc, ensure_ascii=False, indent=1), rubric), expect)

for f in sorted((HERE / "judge_cases").glob("*.json")) if (HERE / "judge_cases").exists() else []:
    doc = json.loads(f.read_text())
    answer = json.dumps(doc["answer"], ensure_ascii=False, indent=1)
    failures += check(f.name, score(answer, rubric, doc["verdicts"]), doc["_expect"])

print("ALL SELF-TESTS PASSED" if not failures else f"{failures} SELF-TEST(S) FAILED")
sys.exit(1 if failures else 0)
