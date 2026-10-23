#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def read_response(path: Path) -> str:
    raw = path.read_text()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    return json.dumps(parsed, ensure_ascii=False)


def has_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)

# --- sentence-scoped negation helpers (added 2026-10-10 after Gemini wording misreads) ---
_SENTENCE_SPLIT = re.compile(r"(?<=[.;!?])\s+|\n+|\"\s*,\s*\"|[\[{]\s*\"|\"\s*[\]}]")
_NEGATION = re.compile(
    r"\b(?:not|non|no|neither|nor|without|absent|absence|excluded?|excludes|exclusion|rul(?:ed|es|ing) out|"
    r"negative(?!\s+fish)|below|lacks?|lacking|does not|do not|is not|are not|isn't|aren't|rather than|instead of|unnecessary|unlikely)\b"
)
_NEGATED_AFTER = re.compile(
    r"\W*(?:[\w/-]+\W+){0,5}?(?:is|are|was|were|has been|have been|remains?|be)\s+"
    r"(?:not|excluded|ruled out|absent|negative|unlikely|unnecessary)\b"          # "double-hit lymphoma is excluded"
    r"|\W*(?:[\w/-]+\W+){0,3}?(?:excluded|ruled out|not (?:present|identified|detected|met))\b"  # "double-hit excluded"
    r"|\s*(?:lymphoma|status|criteria)?\s*[:=-]\s*(?:negative|not detected|absent|no)\b"       # "double_hit: Negative"
    r"|\W*(?:[\w/-]+\W+){0,1}?(?:all\s+|both\s+)?(?:negative|not detected|absent|undetected)\b"  # "rearrangements negative by FISH"
)
# definitional or conditional sentences do not assert anything about this patient
_HEDGE = re.compile(r"\b(?:is defined|are defined|definition|refers to|by definition|criteria for|the term|versus|vs\.?)\b")
DOUBLE_HIT_TERM = r"double[-_ ]hit|triple[-_ ]hit|hgbl[- ]dh"
DOUBLE_EXPRESSOR_TERM = r"double[-_ ]expressor|\bdel\b"
_RECOMMEND = re.compile(r"\b(?:recommend\w*|prefer\w*|indicated|should|first[- ]line|use\b|used|consider\w*|appropriate|"
                        r"favou?red|option|regimen of choice|treat\w* with|standard)\b")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _mentions(text: str, term: str):
    """Yield (sentence, negated) for every sentence mentioning term."""
    for s in sentences(text):
        m = re.search(term, s)
        if not m:
            continue
        clause = re.split(r"\bbut\b|\bhowever\b|;", s[: m.end()])[-1]
        negated = bool(_NEGATION.search(clause)) or bool(_NEGATED_AFTER.match(s[m.end():]))
        yield s, negated


def denies(text: str, term: str) -> bool:
    return any(neg for _, neg in _mentions(text, term))


def affirms(text: str, term: str) -> bool:
    return any(not neg and not _HEDGE.search(s) for s, neg in _mentions(text, term))


def denies_double_hit(text: str) -> bool:
    return denies(text, DOUBLE_HIT_TERM) or has_any(text, [
        r"\bno\b[^.]{0,60}rearrangements?",
        r"rearrangements?[^.]{0,40}(?:not detected|negative|absent|not identified)",
        r"fish[^.]{0,60}(?:negative|no rearrang|not detected|absence of)",
    ])


def affirms_double_hit(text: str) -> bool:
    return affirms(text, DOUBLE_HIT_TERM) or affirms(text, r"myc[^.]{0,60}bcl2[^.]{0,60}rearrangements?")


def denies_double_expressor(text: str) -> bool:
    return denies(text, DOUBLE_EXPRESSOR_TERM) or has_any(text, [
        r"below[^.]{0,60}(?:threshold|cutoff|cut-off)",
        r"(?:does|do) not meet[^.]{0,40}(?:double[-_ ]expressor|threshold|criteria)",
    ])


def recommends_da_epoch(text: str) -> bool:
    """True when some sentence puts DA-EPOCH-R forward without negating it."""
    return any(not neg and _RECOMMEND.search(s) for s, neg in _mentions(text, r"(?:da|dose[- ]adjusted)[- ]?(?:r[- ])?epoch"))


END_OF_TREATMENT = [
    r"end[- ]of[- ](?:treatment|therapy)", r"end of (?:systemic |all )?(?:therapy|treatment)", r"\beot\b",
    r"after (?:completion|completing)[^.]{0,40}(?:therapy|treatment|cycles)",
    r"completion of (?:all |planned |systemic |the )?(?:therapy|treatment|chemo)",
    r"post[- ]treatment", r"final (?:pet|response)", r"(?:after|following)[^.]{0,20}(?:6|six|all)[^.]{0,10}cycles",
]


def asserts_stage_iv(text: str) -> bool:
    if has_any(text, [r"not\s+(?:lugano\s+|ann arbor\s+)?stage\s*iv", r"not\s+stage\s*4"]):
        return False
    return has_any(text, [r"\bstage\s*iv\b", r"\bstage\s*4\b", r"\blugano\b[^.]{0,80}\bstage\s*iv\b", r"\bann arbor\b[^.]{0,80}\bstage\s*iv\b"])


def asserts_double_hit(text: str) -> bool:
    return affirms_double_hit(text)


def supports_curative_immunochemotherapy(text: str) -> bool:
    if has_any(text, [r"curative", r"immunochemotherapy"]):
        return True
    curative_regimen = has_any(text, [r"pola[- ]r[- ]chp", r"polatuzumab", r"r[- ]chop", r"da[- ]epoch[- ]r"])
    treatment_context = has_any(text, [r"first[- ]line", r"standard", r"systemic", r"6\s*cycles?", r"\bx\s*6\b"])
    return curative_regimen and treatment_context


CHECKS = {
    "diagnosis_and_COO": [
        ("DLBCL_NOS", 5, [r"\bdlbcl\b", r"diffuse large b[- ]cell lymphoma"]),
        ("non_GCB_by_Hans", 3, [r"non[- ]gcb.*hans", r"hans.*non[- ]gcb"]),
        ("avoids_equating_Hans_with_definitive_ABC", 2, [r"\bnot\b[^.]{0,120}definitive.*abc", r"\bnot\b[^.]{0,120}synonymous.*abc", r"\bnot\b[^.]{0,120}molecular abc"]),
    ],
    "staging": [
        ("correct_Lugano_stage_III", 10, [r"\bstage\s*iii\b(?!\s*/\s*iv)", r"\blugano\b[^.]{0,80}\bstage\s*iii\b", r"\bann arbor\b[^.]{0,80}\bstage\s*iii\b"]),
        ("correct_staging_reasoning", 5, [r"above and below.*diaphragm", r"splenic", r"bone marrow.*negative"]),
    ],
    "molecular_classification": [
        ("identifies_double_expressor", 5, [r"double[- ]expressor", r"\bdel\b"]),
        ("identifies_not_double_hit", 5, [r"not double[- ]hit", r"\bnot\b[^.]{0,120}double hit", r"double[- ]hit.*negative", r"double[- ]hit.*excluded", r"excluded.*double[- ]hit", r"excludes.*double[- ]hit", r"ruled out.*double[- ]hit"]),
        ("explains_IHC_vs_FISH", 5, [r"fish", r"rearrangements?.*negative", r"ihc"]),
    ],
    "prognosis": [
        ("IPI", 8, [r"\bipi\b", r"international prognostic index"]),
        ("CNS_IPI", 4, [r"cns[- ]ipi"]),
        ("identifies_missing_variables", 3, [r"missing", r"additional", r"kidney", r"adrenal", r"extranodal"]),
    ],
    "first_line_treatment": [
        ("curative_immunochemotherapy", 7, [r"curative", r"immunochemotherapy"]),
        ("recognizes_pola_R_CHP", 4, [r"pola[- ]r[- ]chp", r"polatuzumab"]),
        ("accepts_R_CHOP_alternative", 2, [r"r[- ]chop"]),
        ("avoids_unjustified_DA_EPOCH_R", 2, [r"\bnot\b[^.]{0,120}da[- ]epoch", r"not routinely.*da[- ]epoch", r"da[- ]epoch[- ]r[^.]{0,120}\bnot\b[^.]{0,120}solely"]),
    ],
    "CNS_management": [
        ("uses_CNS_IPI", 6, [r"cns[- ]ipi"]),
        ("identifies_high_risk_sites", 5, [r"kidney", r"adrenal", r"testicular", r"breast", r"high[- ]risk"]),
        ("no_automatic_prophylaxis_for_DEL", 4, ['not automatic', 'not automatically', 'not.*automatically indicated', 'does not mandate', 'not mandated', 'not (?:routinely |generally |typically )?(?:indicated|recommended|required|warranted|needed)', 'generally not', 'routine.*not recommended']),
    ],
    "response_assessment": [
        ("PET_CT", 4, [r"pet[- ]ct", r"fdg pet"]),
        ("Lugano_Deauville", 6, [r"deauville", r"lugano"]),
        ("end_of_treatment_assessment", 5, END_OF_TREATMENT),
    ],
}

CRITICAL_ERRORS = [
    ("double_expressor_called_double_hit_despite_negative_FISH", -20, [r"is double[- ]hit", r"double[- ]hit lymphoma"], [r"not double[- ]hit", r"\bnot\b[^.]{0,120}double hit"]),
    ("unjustified_non_curative_treatment", -25, [r"palliative only", r"supportive care only"], []),
    ("mandates_CNS_prophylaxis_without_risk_assessment", -10, [r"must[^.]{0,120}cns prophylaxis", r"mandatory[^.]{0,120}cns prophylaxis", r"cns prophylaxis[^.]{0,40}(?:is |are |remains )?(?:required|mandatory|mandated|obligatory|must)"], [r"cns[- ]ipi", r"risk"]),
    ("DA_EPOCH_R_escalation_solely_for_DEL", -10, [r"da[- ]epoch[- ]r[^.]{0,120}because[^.]{0,120}double[- ]expressor", r"da[- ]epoch[- ]r.*solely"], [r"\bnot\b[^.]{0,120}da[- ]epoch", r"da[- ]epoch[- ]r[^.]{0,120}\bnot\b"]),
]


def score(text: str) -> dict:
    lowered = text.lower()
    total = 0
    metrics = {}
    for domain, checks in CHECKS.items():
        earned = 0
        detail = {}
        possible = sum(points for _, points, _ in checks)
        for name, points, patterns in checks:
            matched = has_any(lowered, patterns)
            if name == "correct_Lugano_stage_III" and asserts_stage_iv(lowered):
                matched = False
            if name == "curative_immunochemotherapy":
                matched = supports_curative_immunochemotherapy(lowered)
            if name == "identifies_not_double_hit":
                matched = denies_double_hit(lowered)
            if name == "avoids_unjustified_DA_EPOCH_R":
                matched = not recommends_da_epoch(lowered)
            earned += points if matched else 0
            detail[name] = {"score": points if matched else 0, "max": points, "matched": matched}
        metrics[domain] = {"score": earned / possible, "points": earned, "max_points": possible, "criteria": detail}
        total += earned

    critical_errors = []
    penalty = 0
    for name, points, bad_patterns, safe_patterns in CRITICAL_ERRORS:
        bad = asserts_double_hit(lowered) if name == "double_expressor_called_double_hit_despite_negative_FISH" else has_any(lowered, bad_patterns)
        safe = has_any(lowered, safe_patterns) if safe_patterns else False
        if bad and not safe:
            critical_errors.append({"name": name, "penalty_points": points})
            penalty += points

    final_points = max(0, total + penalty)
    return {
        "reward": final_points / 100,
        "score": final_points,
        "max_score": 100,
        "passed": final_points >= 75 and not critical_errors,
        "raw_score": total,
        "penalty": penalty,
        "metrics": metrics,
        "critical_errors": critical_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = score(read_response(args.response))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    review_path = args.output.with_name("review.json")
    review_path.write_text(json.dumps(result, indent=2) + "\n")
    args.output.write_text(
        json.dumps(
            {
                "reward": result["reward"],
                "clinical_correctness": result["metrics"]["diagnosis_and_COO"]["score"],
                "staging": result["metrics"]["staging"]["score"],
                "molecular_classification": result["metrics"]["molecular_classification"]["score"],
                "prognosis": result["metrics"]["prognosis"]["score"],
                "first_line_treatment": result["metrics"]["first_line_treatment"]["score"],
                "cns_management": result["metrics"]["CNS_management"]["score"],
                "response_assessment": result["metrics"]["response_assessment"]["score"],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
