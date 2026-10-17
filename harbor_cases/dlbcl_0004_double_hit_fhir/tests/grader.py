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


def identifies_double_hit(text: str) -> bool:
    return affirms_double_hit(text)


def avoids_rchop_alone(text: str) -> bool:
    """Credit unless some sentence puts R-CHOP forward on its own (no DA-EPOCH-R / trial / intensive in that sentence)."""
    if has_any(text, [r"(?:over|than|instead of|rather than)\s+(?:standard\s+)?r[- ]chop", r"r[- ]chop alone[^.]{0,40}not",
                      r"not[^.]{0,40}r[- ]chop alone", r"r[- ]chop[^.]{0,40}not[^.]{0,20}preferred",
                      r"r[- ]chop[^.]{0,40}(?:inferior|insufficient|inadequate|suboptimal|generally not)"]):
        return True
    return not any(_RECOMMEND.search(sent) and not re.search(r"(?:da|dose[- ]adjusted)[- ]?(?:r[- ])?epoch|clinical trial|intensive", sent)
                   for sent, neg in _mentions(text, r"r[- ]chop") if not neg)


CHECKS = {
    "diagnosis_and_COO": [
        ("high_grade_or_DLBCL", 5, [r"high[- ]grade b[- ]cell", r"\bdlbcl\b", r"large b[- ]cell lymphoma"]),
        ("GCB_by_Hans", 3, [r"\bgcb\b", r"germinal[- ]center", r"cd10\+"]),
        ("identifies_double_hit_entity", 2, [r"double[- ]hit", r"myc.*bcl2.*rearrangements?"]),
    ],
    "staging": [
        ("correct_Lugano_stage_II", 8, [r"\bstage\s*ii\b", r"\bstage\s*2\b"]),
        ("bulky_disease", 4, [r"bulky", r"12\s*cm"]),
        ("no_disease_below_diaphragm_or_marrow", 3, [r"above.*diaphragm", r"no.*below.*diaphragm", r"marrow.*negative"]),
    ],
    "molecular_classification": [
        ("identifies_double_hit", 6, [r"double[- ]hit", r"myc.*bcl2.*rearrangements?.*detected"]),
        ("identifies_double_expressor", 4, [r"double[- ]expressor", r"\bdel\b", r"myc.*80.*bcl2.*90"]),
        ("explains_FISH_rearrangements", 5, [r"fish", r"rearrangements?.*detected", r"myc.*bcl2"]),
    ],
    "prognosis": [
        ("IPI", 5, [r"\bipi\b", r"international prognostic index"]),
        ("CNS_IPI", 4, [r"cns[- ]ipi"]),
        ("recognizes_double_hit_adverse_risk", 6, [r"double[- ]hit.*risk", r"adverse.*double[- ]hit", r"high[- ]risk.*double[- ]hit"]),
    ],
    "first_line_treatment": [
        ("curative_intensive_immunochemotherapy", 6, [r"curative", r"intensive", r"intensif", r"immunochemotherapy", r"(?:da|dose[- ]adjusted)[- ]?(?:r[- ])?epoch", r"r[- ]hyper[- ]?cvad", r"codox"]),
        ("DA_EPOCH_R_or_clinical_trial", 6, [r"da[- ]epoch[- ]r", r"clinical trial"]),
        ("avoids_R_CHOP_alone_as_preferred", 3, [r"r[- ]chop alone[^.]{0,120}\bnot\b", r"\bnot\b[^.]{0,120}r[- ]chop alone", r"r[- ]chop[^.]{0,120}\bnot\b[^.]{0,120}preferred"]),
    ],
    "CNS_management": [
        ("uses_CNS_IPI", 5, [r"cns[- ]ipi"]),
        ("considers_double_hit_CNS_risk", 5, [r"double[- ]hit.*cns", r"cns.*double[- ]hit", r"high[- ]risk.*cns"]),
        ("individualized_prophylaxis", 5, [r"consider.*prophylaxis", r"prophylaxis.*consider", r"individualized", r"not mandated"]),
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
            if name == "identifies_double_hit":
                matched = identifies_double_hit(lowered)
            if name == "avoids_R_CHOP_alone_as_preferred":
                matched = avoids_rchop_alone(lowered)
            earned += points if matched else 0
            detail[name] = {"score": points if matched else 0, "max": points, "matched": matched}
        metrics[domain] = {"score": earned / possible, "points": earned, "max_points": possible, "criteria": detail}
        total += earned

    critical_errors = []
    penalty = 0
    if not identifies_double_hit(lowered):
        critical_errors.append({"name": "misses_double_hit_FISH_positive", "penalty_points": -25})
        penalty -= 25
    if denies_double_hit(lowered) and not affirms_double_hit(lowered):
        critical_errors.append({"name": "treats_as_standard_DEL_only", "penalty_points": -15})
        penalty -= 15
    if not avoids_rchop_alone(lowered):  # sentence-scoped: "phenotype" must not excuse R-CHOP alone
        critical_errors.append({"name": "recommends_R_CHOP_alone_as_preferred", "penalty_points": -15})
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
