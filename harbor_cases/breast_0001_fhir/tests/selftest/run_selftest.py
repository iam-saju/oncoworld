#!/usr/bin/env python3
"""Grader self-test. Run from anywhere: python3 tests/selftest/run_selftest.py

Each case states what the grader MUST conclude. If a grader change breaks one, fix the grader,
not the expectation, unless the oncologist has changed the clinical rule.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from grader import score_file  # noqa: E402

A = HERE / "answers"
CASES = [
    # file, must_pass, required critical errors, extra checks
    ("01_reference.json", True, [], lambda r: r["score"] == 100),
    ("02_reworded_valid.json", True, [], None),
    ("03_hedged_conditional.json", True, [], lambda r: len(r["needs_doctor_review"]) >= 1),
    ("04_omits_radiotherapy.json", False, ["omits_adjuvant_radiotherapy"], None),
    ("05_recommends_chemotherapy.json", False, ["recommends_adjuvant_chemotherapy"], None),
    ("06_recommends_her2_therapy.json", False, ["recommends_HER2_targeted_therapy"], None),
    ("07_no_endocrine_therapy.json", False, ["omits_endocrine_therapy"], None),
    ("08_invalid_json.json", False, [], lambda r: r["invalid_json"] and r["reward"] == 0.0),
    ("09_missing_file.json", False, [], lambda r: r["infra_failure"] and r["reward"] == 0.0),
    ("10_structured_fields.json", True, [], None),  # nested objects instead of strings, as Gemini wrote in DLBCL 0003
    ("11_negligible_benefit_wording.json", True, [], lambda r: r["score"] == 100),  # Gemini wording, job 2026-10-10__01-01-23
    ("12_her2_negation_after_list.json", True, [], lambda r: r["score"] == 100),  # Gemini 3.8 Flash wording, job 2026-10-10__01-33-04
]

failures = 0
for name, must_pass, must_crit, extra in CASES:
    r = score_file(A / name)
    got = [c["name"] for c in r["critical_errors"]]
    problems = []
    if r["passed"] != must_pass:
        problems.append(f"passed={r['passed']} expected {must_pass}")
    if sorted(got) != sorted(must_crit):
        problems.append(f"critical={got} expected {must_crit}")
    if extra and not extra(r):
        problems.append("extra check failed")
    status = "ok  " if not problems else "FAIL"
    failures += bool(problems)
    print(f"{status} {name:34s} score={r['score']:>3} critical={got} {'; '.join(problems)}")
    if problems:
        missed = [f"{d}.{c}" for d, m in r["metrics"].items() for c, x in m["criteria"].items() if not x["matched"]]
        print("       missed:", missed)
        print("       review:", json.dumps(r["needs_doctor_review"])[:400])

print("ALL SELF-TESTS PASSED" if not failures else f"{failures} SELF-TEST(S) FAILED")
sys.exit(1 if failures else 0)
