#!/usr/bin/env python3
"""Tiny local runner for the DLBCL Harbor task drafts.

This is not a replacement for physician review or a production Harbor harness.
It lets you see the instruction -> agent output -> verifier -> reward loop locally.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def has_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


CHECKS = {
    "diagnosis_and_COO": [
        ("DLBCL_NOS", 7, [r"\bdlbcl\b", r"diffuse large b[- ]cell lymphoma"]),
        ("non_GCB_by_Hans", 5, [r"non[- ]gcb.*hans", r"hans.*non[- ]gcb"]),
        ("avoids_equating_Hans_with_definitive_ABC", 3, [r"not.*definitive.*abc", r"not.*synonymous.*abc", r"does not.*abc"]),
    ],
    "staging": [
        ("correct_Lugano_stage_III", 7, [r"stage iii", r"lugano.*iii", r"ann arbor.*iii"]),
        ("correct_staging_reasoning", 3, [r"above and below.*diaphragm", r"splenic", r"bone marrow.*negative"]),
    ],
    "molecular_classification": [
        ("identifies_double_expressor", 5, [r"double[- ]expressor", r"\bdel\b"]),
        ("identifies_not_double_hit", 5, [r"not double[- ]hit", r"not.*double hit", r"double[- ]hit.*negative"]),
        ("explains_IHC_vs_FISH", 5, [r"fish", r"rearrangements?.*negative", r"ihc"]),
    ],
    "prognosis": [
        ("IPI", 8, [r"\bipi\b", r"international prognostic index"]),
        ("CNS_IPI", 4, [r"cns[- ]ipi"]),
        ("identifies_missing_variables", 3, [r"missing", r"additional", r"kidney", r"adrenal", r"extranodal"]),
    ],
    "first_line_treatment": [
        ("curative_immunochemotherapy", 12, [r"curative", r"immunochemotherapy"]),
        ("recognizes_pola_R_CHP", 6, [r"pola[- ]r[- ]chp", r"polatuzumab"]),
        ("accepts_R_CHOP_alternative", 3, [r"r[- ]chop"]),
        (
            "avoids_unjustified_DA_EPOCH_R",
            4,
            [
                r"not.*da[- ]epoch",
                r"does not.*da[- ]epoch",
                r"not routinely.*da[- ]epoch",
                r"da[- ]epoch[- ]r.*not routinely",
                r"da[- ]epoch[- ]r.*not.*solely",
            ],
        ),
    ],
    "CNS_management": [
        ("uses_CNS_IPI", 4, [r"cns[- ]ipi"]),
        ("identifies_high_risk_sites", 3, [r"kidney", r"adrenal", r"testicular", r"breast", r"high[- ]risk"]),
        ("no_automatic_prophylaxis_for_DEL", 3, [r"not automatic", r"not automatically", r"should not be automatic"]),
    ],
    "response_assessment": [
        ("PET_CT", 3, [r"pet[- ]ct", r"fdg pet"]),
        ("Lugano_Deauville", 4, [r"deauville", r"lugano"]),
        ("end_of_treatment_assessment", 3, [r"end[- ]of[- ]treatment", r"end of treatment", r"\beot\b"]),
    ],
}

CRITICAL_ERRORS = [
    ("double_expressor_called_double_hit_despite_negative_FISH", -20, [r"is double[- ]hit", r"double[- ]hit lymphoma"], [r"not double[- ]hit", r"not.*double hit"]),
    ("unjustified_non_curative_treatment", -25, [r"palliative only", r"supportive care only"], []),
    ("mandates_CNS_prophylaxis_without_risk_assessment", -10, [r"must.*cns prophylaxis", r"definitely.*cns prophylaxis", r"mandatory.*cns prophylaxis"], [r"cns[- ]ipi", r"risk"]),
    (
        "DA_EPOCH_R_escalation_solely_for_DEL",
        -10,
        [r"da[- ]epoch[- ]r.*because.*double[- ]expressor", r"da[- ]epoch[- ]r.*solely"],
        [r"not.*da[- ]epoch", r"da[- ]epoch[- ]r.*not", r"not routinely.*da[- ]epoch"],
    ),
]


def score_response(response: str) -> dict:
    text = response.lower()
    domains: dict[str, dict] = {}
    total = 0

    for domain, checks in CHECKS.items():
        earned = 0
        details = []
        possible = sum(points for _, points, _ in checks)
        for name, points, patterns in checks:
            ok = has_any(text, patterns)
            if ok:
                earned += points
            details.append({"criterion": name, "points": points if ok else 0, "max": points, "matched": ok})
        domains[domain] = {"score": earned, "max": possible, "criteria": details}
        total += earned

    critical_errors = []
    penalty = 0
    for name, points, bad_patterns, safe_patterns in CRITICAL_ERRORS:
        bad = has_any(text, bad_patterns)
        safe = has_any(text, safe_patterns) if safe_patterns else False
        if bad and not safe:
            critical_errors.append({"name": name, "penalty": points})
            penalty += points

    final_score = max(0, total + penalty)
    return {
        "raw_score": total,
        "penalty": penalty,
        "final_score": final_score,
        "max_score": 100,
        "passed": final_score >= 75 and not critical_errors,
        "domain_scores": domains,
        "critical_errors": critical_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--response", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    response_path = args.response or args.case_dir / "solution" / "final_answer.json"
    result = score_response(response_path.read_text())
    reward = {
        "reward": result["final_score"] / result["max_score"],
        "score": result["final_score"],
        "max_score": result["max_score"],
        "passed": result["passed"],
        "raw_score": result["raw_score"],
        "penalty": result["penalty"],
        "metrics": result["domain_scores"],
        "critical_errors": result["critical_errors"],
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(reward, indent=2) + "\n")
        print(args.output)
        return
    print(json.dumps(reward, indent=2))


if __name__ == "__main__":
    main()
