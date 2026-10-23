#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def read_response(path: Path) -> str:
    raw = path.read_text()
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False)
    except json.JSONDecodeError:
        return raw


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
    return has_any(text, [r"\bstage\s*iv\b", r"\bstage\s*4\b"])


def supports_curative_treatment(text: str) -> bool:
    if has_any(text, [r"curative", r"immunochemotherapy"]):
        return True
    regimen = has_any(text, [r"r[- ]chop", r"pola[- ]r[- ]chp", r"polatuzumab"])
    context = has_any(text, [r"standard", r"first[- ]line", r"standard of care", r"\bx\s*6\b", r"6\s*cycles?"])
    return regimen and context


def asserts_double_expressor_or_hit(text: str) -> bool:
    return affirms(text, DOUBLE_EXPRESSOR_TERM) or affirms_double_hit(text)


CHECKS = {
    "diagnosis_and_COO": [
        ("DLBCL_NOS", 5, [r"\bdlbcl\b", r"diffuse large b[- ]cell lymphoma"]),
        ("GCB_by_Hans", 3, [r"\bgcb\b", r"germinal[- ]center", r"cd10\+"]),
        ("avoids_non_GCB_or_ABC_call", 2, [r"\bnot\b[^.]{0,120}non[- ]gcb", r"gcb", r"\bnot\b[^.]{0,120}abc"]),
    ],
    "staging": [
        ("correct_Lugano_stage_IV", 8, [r"\bstage\s*iv\b", r"\bstage\s*4\b"]),
        ("recognizes_extranodal_kidney_adrenal_liver", 5, [r"kidney|renal", r"adrenal", r"liver|hepatic"]),
        ("notes_bone_marrow_negative_not_required_for_stage_IV", 2, [r"bone marrow.*negative", r"marrow.*negative", r"despite.*marrow"]),
    ],
    "molecular_classification": [
        ("identifies_not_double_expressor", 5, [r"not\s+double[- ]expressor", r"\bnot\b[^.]{0,120}del\b", r"neither.*double[- ]expressor"]),
        ("identifies_not_double_hit", 5, [r"not double[- ]hit", r"\bnot\b[^.]{0,120}double hit", r"fish.*negative"]),
        ("explains_IHC_vs_FISH", 5, [r"ihc", r"fish", r"rearrangements?.*negative"]),
    ],
    "prognosis": [
        ("IPI_high_risk", 6, [r"\bipi\b.*high", r"high.*\bipi\b", r"age.*stage.*ldh.*ecog"]),
        ("CNS_IPI_high_risk", 6, [r"cns[- ]ipi.*high", r"high.*cns[- ]ipi"]),
        ("identifies_multiple_extranodal_sites", 3, [r"multiple extranodal", r"kidney.*adrenal", r"renal.*adrenal"]),
    ],
    "first_line_treatment": [
        ("curative_immunochemotherapy", 7, [r"curative", r"immunochemotherapy", r"first[- ]line.*(r[- ]chop|pola[- ]r[- ]chp|polatuzumab)"]),
        ("recognizes_pola_or_R_CHOP", 5, [r"pola[- ]r[- ]chp", r"polatuzumab", r"r[- ]chop"]),
        ("avoids_unjustified_DA_EPOCH_R", 3, [r"\bnot\b[^.]{0,120}da[- ]epoch", r"da[- ]epoch[- ]r[^.]{0,120}\bnot\b[^.]{0,120}required", r"fish.*negative"]),
    ],
    "CNS_management": [
        ("kidney_adrenal_high_risk", 6, [r"kidney|renal", r"adrenal"]),
        ("prophylaxis_considered", 6, [r"prophylaxis.*consider", r"consider.*prophylaxis", r"high[- ]dose methotrexate", r"intrathecal"]),
        ("renal_function_or_CSF_missing", 3, [r"renal", r"creatinine", r"csf", r"lumbar puncture"]),
    ],
    "response_assessment": [
        ("PET_CT", 4, [r"pet[- ]ct", r"fdg pet"]),
        ("Lugano_Deauville", 6, [r"deauville", r"lugano"]),
        ("end_of_treatment_assessment", 5, END_OF_TREATMENT),
    ],
}


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
            if name == "curative_immunochemotherapy":
                matched = supports_curative_treatment(lowered)
            if name == "identifies_not_double_expressor":
                matched = denies_double_expressor(lowered)
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
    if not asserts_stage_iv(lowered):
        critical_errors.append({"name": "misses_stage_IV_extranodal_disease", "penalty_points": -20})
        penalty -= 20
    if not has_any(lowered, [r"kidney|renal"]) or not has_any(lowered, [r"adrenal"]):
        critical_errors.append({"name": "misses_kidney_adrenal_CNS_risk", "penalty_points": -20})
        penalty -= 20
    if asserts_double_expressor_or_hit(lowered):
        critical_errors.append({"name": "calls_low_expression_case_double_expressor_or_double_hit", "penalty_points": -15})
        penalty -= 15

    final_points = max(0, total + penalty)
    return {"reward": final_points / 100, "score": final_points, "max_score": 100, "passed": final_points >= 75 and not critical_errors, "raw_score": total, "penalty": penalty, "metrics": metrics, "critical_errors": critical_errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = score(read_response(args.response))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_name("review.json").write_text(json.dumps(result, indent=2) + "\n")
    args.output.write_text(json.dumps({
        "reward": result["reward"],
        "clinical_correctness": result["metrics"]["diagnosis_and_COO"]["score"],
        "staging": result["metrics"]["staging"]["score"],
        "molecular_classification": result["metrics"]["molecular_classification"]["score"],
        "prognosis": result["metrics"]["prognosis"]["score"],
        "first_line_treatment": result["metrics"]["first_line_treatment"]["score"],
        "cns_management": result["metrics"]["CNS_management"]["score"],
        "response_assessment": result["metrics"]["response_assessment"]["score"],
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
