#!/usr/bin/env python3
"""v2 grader self-test. Run: python3 tests/selftest/run_selftest.py [--judge]

answers/*.json      an answer plus an `_expect` block, graded by the regex rules (the grader of record): gold
                    reference, hand-written bad answers, paraphrases, and real model answers with known verdicts.
                    Deterministic, offline and free; every rule change must keep these passing.
probes.json         oncologist-written single sentences per high-stakes rule, labelled fire / does not fire.
judge_cases/*.json  {"answer": ..., "verdicts": ..., "_expect": ...}: fixed judge verdicts, testing how the optional
                    judge mode aggregates (points, dangerous errors, verbatim-quote check).
--judge             additionally grade answers/ with the live optional judge (ONCOWORLD_JUDGE_*).

_expect fields:
  passed      True/False (optional)
  dangerous   exact list of dangerous item ids that must fire
  must_met    item ids that must be met
  must_unmet  item ids that must NOT be met
  all_met     every must/should item met
  _label      optional provenance of the expectation (e.g. who classified a real model answer)
"""
import json
import os
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from grader_v2 import grade, judge_available, score  # noqa: E402

rubric = tomllib.loads((HERE.parent / "rubric_v2.toml").read_text())
failures = 0


def check(name, r, expect):
    problems = []
    met = {i["id"] for i in r["items"] if i["met"]}
    if "passed" in expect and r["passed"] != expect["passed"]:
        problems.append(f"passed={r['passed']} expected {expect['passed']}")
    if "dangerous" in expect and sorted(r["dangerous_errors"]) != sorted(expect["dangerous"]):
        problems.append(f"dangerous={r['dangerous_errors']} expected {expect['dangerous']}")
    problems += [f"should meet {i}" for i in expect.get("must_met", []) if i not in met]
    problems += [f"should NOT meet {i}" for i in expect.get("must_unmet", []) if i in met]
    if expect.get("all_met") is True:
        problems += [f"unmet {i['id']}" for i in r["items"] if i["kind"] != "must_not" and not i["met"]]
    print(f"{'ok  ' if not problems else 'FAIL'} {name:44s} reward={r['reward']:<6} {'; '.join(problems)}", flush=True)
    return bool(problems)


answers = []
for f in sorted((HERE / "answers").glob("*.json")):
    doc = json.loads(f.read_text())
    expect = doc.pop("_expect")
    answers.append((f.name, json.dumps(doc, ensure_ascii=False, indent=1), expect))
    failures += check(f.name, score(answers[-1][1], rubric), expect)

# probes.json: single oncologist-written sentences per high-stakes rule, labelled fire / does not fire
probes_path = HERE / "probes.json"
if probes_path.exists():
    from grader_v2 import read_response_text, rule_met  # noqa: E402
    items = {i["id"]: i for i in rubric["items"]}
    probes = json.loads(probes_path.read_text())
    bad = []
    for p in probes:
        text = read_response_text(json.dumps({p["field"]: p["text"]}, ensure_ascii=False)).lower()
        if bool(rule_met(items[p["item"]], text)) != bool(p["fire"]) and not p.get("known_limitation"):
            bad.append(p)
    for p in bad:
        kind = "false alarm" if not p["fire"] else "miss"
        print(f"FAIL probe {kind:11} {p['item']:32} {p['text'][:110]}")
    print(f"{'ok  ' if not bad else 'FAIL'} probes.json: {len(probes) - len(bad)}/{len(probes)} sentences graded as labelled")
    failures += bool(bad)

for f in sorted((HERE / "judge_cases").glob("*.json")) if (HERE / "judge_cases").exists() else []:
    doc = json.loads(f.read_text())
    answer = json.dumps(doc["answer"], ensure_ascii=False, indent=1)
    failures += check(f.name, score(answer, rubric, doc["verdicts"]), doc["_expect"])

if "--judge" in sys.argv:
    os.environ["ONCOWORLD_GRADER"] = "judge"
    if not judge_available():
        sys.exit("--judge needs ONCOWORLD_JUDGE_API_KEY and ONCOWORLD_JUDGE_MODEL")
    for name, answer, expect in answers:
        failures += check(f"[judge] {name}", grade(answer, rubric), expect)

print("ALL SELF-TESTS PASSED" if not failures else f"{failures} SELF-TEST(S) FAILED")
sys.exit(1 if failures else 0)
