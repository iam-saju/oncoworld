#!/usr/bin/env python3
"""Rule-based verifier for breast_0001 (HR+/HER2- early breast cancer, adjuvant planning).

Writes reward.json (numeric only, Harbor requirement) and review.json (evidence per criterion,
critical errors, and sentences a doctor should read). No LLM is used.

Lessons from the DLBCL graders built in:
- Matching is per sentence with negation awareness, so "not a candidate for trastuzumab" is not
  read as recommending trastuzumab.
- Safety criteria fire on what the model positively recommends, never on what it fails to mention.
- Conditional wording ("would only be considered if...") is neither credited nor penalised; it is
  listed under needs_doctor_review instead.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FIELDS = [
    "diagnosis", "stage", "biology", "genomic_risk", "chemotherapy_decision",
    "endocrine_therapy", "radiotherapy", "supportive_monitoring", "missing_information",
]

NEGATION = re.compile(
    r"\b(no|not|non|without|never|avoid\w*|omit\w*|spar\w*|forgo\w*|unnecessary|ineligible|"
    r"does not|do not|is not|are not|isn't|aren't|don't|doesn't|unlikely|lack\w*|absence|"
    r"rather than|instead of|in place of|nor|negligible|minimal|little|marginal)\b"
)
CONDITIONAL = re.compile(r"\b(if|unless|would|were|only when|in case|should .* change|could be considered)\b")
RECOMMEND = re.compile(
    r"\b(recommend\w*|indicated|should (?:receive|start|begin|get|be given|be offered|undergo)|"
    r"proceed with|administer\w*|start\w*|initiat\w*|offer\w*|give|plan for|plan\b|"
    r"is advised|advis\w*|benefit\w* from|candidate for|preferred|suggest\w*|warrant\w*)\b"
)

CHEMO = re.compile(
    r"\b(chemotherapy|chemo|docetaxel|cyclophosphamide|doxorubicin|epirubicin|paclitaxel|"
    r"anthracycline\w*|taxane\w*|capecitabine|\btc\b|ac[- ]?t|\bcmf\b|dose[- ]dense)\b"
)
HER2_THERAPY = re.compile(
    r"\b(trastuzumab|pertuzumab|herceptin|t[- ]?dm1|t[- ]?dxd|ado[- ]trastuzumab|"
    r"(?:fam[- ])?trastuzumab deruxtecan|enhertu|kadcyla|anti[- ]her2|her2[- ](?:targeted|directed|blockade)|"
    r"neratinib|lapatinib|tucatinib)\b"
)
ENDOCRINE = re.compile(
    r"\b(aromatase inhibitor\w*|\bais?\b|anastrozole|letrozole|exemestane|tamoxifen|"
    r"endocrine therapy|hormonal therapy|hormone therapy|anti[- ]?estrogen\w*|endocrine treatment)\b"
)
RADIATION = re.compile(
    r"\b(radiotherapy|radiation|irradiation|wbrt|whole[- ]breast|apbi|\bpbi\b|partial[- ]breast|"
    r"hypofractionat\w*|\brt\b|xrt)\b"
)


def flatten(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(f"{k}: {flatten(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return " ; ".join(flatten(v) for v in value)
    return str(value)


def sentences(text: str) -> list[str]:
    text = re.sub(r"\b(e\.g|i\.e|vs|approx|dr)\.", lambda m: m.group(1), text, flags=re.I)
    parts = re.split(r"(?<=[.;!?])\s+|\n+|\s+;\s+", text)
    return [p.strip() for p in parts if p.strip()]


def negated(sentence: str, term: re.Pattern) -> bool:
    """True when a negation word sits before the term within the same clause."""
    m = term.search(sentence)
    if not m:
        return False
    before = sentence[: m.start()]
    clause = re.split(r"[,:]\s+(?:but|however|although)\b|\bbut\b|\bhowever\b", before)[-1]
    words = re.findall(r"[\w'-]+", sentence[m.end():])
    after = " ".join(words[:5])
    # a clear negative predicate may follow a parenthetical drug list:
    # "anti-HER2 therapies (e.g. trastuzumab, pertuzumab, ...) are not indicated"
    far = " ".join(words[:15])
    return bool(NEGATION.search(clause)) or bool(NEGATION.search(after)) or bool(
        re.search(r"\b(?:omitted|avoided|spared|unnecessary|no longer)\b", after)) or bool(
        re.search(r"\b(?:is|are)\s+not\s+(?:indicated|recommended|warranted|appropriate|needed|required|beneficial)\b"
                  r"|\bno proven\b|\bnot (?:a )?candidates?\b", far))


class Answer:
    def __init__(self, data: dict):
        self.fields = {k: flatten(data.get(k)).lower() for k in FIELDS}
        self.all = " \n".join(flatten(v) for v in data.values()).lower()
        # Clinical recommendations only; missing_information lists gaps, not decisions.
        self.plan = " \n".join(flatten(v) for k, v in data.items() if k != "missing_information").lower()
        self.missing_fields = [k for k in FIELDS if not self.fields[k].strip()]

    def field_or_all(self, key: str) -> str:
        return self.fields[key] if self.fields[key].strip() else self.all

    def sents(self, key: str | None = None) -> list[str]:
        return sentences(self.plan if key is None else self.field_or_all(key))


def first(pattern: str, text: str) -> str | None:
    for s in sentences(text):
        if re.search(pattern, s):
            return s
    return None


def positive_sentences(sents: list[str], term: re.Pattern) -> tuple[list[str], list[str], list[str]]:
    """Split sentences mentioning term into (positive, negated, conditional)."""
    pos, neg, cond = [], [], []
    for s in sents:
        if not term.search(s):
            continue
        if negated(s, term):
            neg.append(s)
        elif CONDITIONAL.search(s):
            cond.append(s)
        else:
            pos.append(s)
    return pos, neg, cond


def grade(ans: Answer) -> dict:
    crit: dict[str, dict] = {}
    review: list[dict] = []

    def award(domain, name, max_pts, pts, evidence, note=None):
        crit.setdefault(domain, {})[name] = {"score": pts, "max": max_pts, "matched": pts == max_pts,
                                             "evidence": evidence, **({"note": note} if note else {})}

    # ---- Diagnosis and biology (25)
    dx = ans.all
    ev = first(r"invasive ductal|\bidc\b|no special type|\bnst\b|infiltrating duct", dx)
    award("diagnosis_and_biology", "IDC", 5, 5 if ev else 0, ev)

    ev = first(r"\bhr[- ]?(?:positive|\+)|hormone[- ]receptor[- ]positive|\ber[- ]?(?:positive|\+)|"
               r"estrogen receptor[- ]positive|\ber\b[^.]{0,30}\b9\d ?%|luminal", dx)
    award("diagnosis_and_biology", "HR_positive", 5, 5 if ev else 0, ev)

    her2_neg = first(r"her2[- ]?(?:negative|low|-(?:\s|$|,|\.))|her2[^.]{0,40}\b1\+[^.]{0,40}negative|"
                     r"her2[^.]{0,30}\bnegative|not her2[- ]?positive", dx)
    her2_pos_claim = None
    for s in sentences(dx):
        if re.search(r"her2[- ]?(?:positive|\+(?!\s*\())|her2[- ]amplified", s) and not negated(s, re.compile(r"her2")):
            if not re.search(r"not\s+her2[- ]?positive|her2[- ]?positive\s+(?:therapy|disease)\s+is\s+not", s):
                her2_pos_claim = s
    pts = 5 if her2_neg and not her2_pos_claim else 0
    award("diagnosis_and_biology", "HER2_negative", 5, pts, her2_neg or her2_pos_claim,
          "model also describes HER2 as positive" if her2_pos_claim else None)

    stage_txt = ans.field_or_all("stage")
    if re.search(r"\bstage\s*(?:ia|1a)\b|\bstage\s*i\s*a\b|anatomic(?:al)? stage\s*(?:ia|1a)|prognostic stage\s*(?:ia|1a)", stage_txt):
        award("diagnosis_and_biology", "stage_IA", 10, 10, first(r"stage\s*(?:i\s*a|1a|ia)", stage_txt))
    elif re.search(r"\bstage\s*(?:i|1)\b(?!\s*[ab]|i)", stage_txt):
        award("diagnosis_and_biology", "stage_IA", 10, 7, first(r"stage\s*(?:i|1)\b", stage_txt), "stage I without IA substage")
    else:
        award("diagnosis_and_biology", "stage_IA", 10, 0, first(r"stage", stage_txt))

    # ---- Genomic risk (15)
    gr = ans.field_or_all("genomic_risk")
    low = first(r"\blow(?:[- ]genomic)?[- ](?:risk|recurrence)|\blow\b[^.]{0,40}\b(?:risk|recurrence|score)|"
                r"(?:risk|score)[^.]{0,40}\blow\b|rs\s*(?:of\s*)?14[^.]{0,40}(?:≤|<=|<|below)\s*(?:15|16|25|26)", gr)
    high = first(r"\b(?:intermediate|high)[- ](?:genomic[- ])?risk", gr)
    award("genomic_risk", "recognizes_low_risk", 8, 8 if low and not high else 0, low or high,
          "also calls the score intermediate/high" if low and high else None)

    link_txt = gr + " \n" + ans.fields["chemotherapy_decision"]
    link = None
    for s in sentences(link_txt):
        if re.search(r"recurrence score|\brs\b|oncotype|21[- ]gene|genomic|tailorx|score of 14|\b14\b", s) and CHEMO.search(s):
            link = s
            break
    award("genomic_risk", "links_score_to_chemotherapy", 7, 7 if link else 0, link)

    # ---- Chemotherapy decision (20) + critical error
    chemo_pos, chemo_neg, chemo_cond = positive_sentences(ans.sents(), CHEMO)
    chemo_pos = [s for s in chemo_pos if RECOMMEND.search(s)]
    field_pos, field_neg, field_cond = positive_sentences(ans.sents("chemotherapy_decision"), CHEMO)
    not_indicated = field_neg[0] if field_neg else None
    if not not_indicated and re.search(r"endocrine therapy alone|no (?:adjuvant )?chemo", ans.field_or_all("chemotherapy_decision")):
        not_indicated = first(r"endocrine therapy alone|no (?:adjuvant )?chemo", ans.field_or_all("chemotherapy_decision"))
    award("chemotherapy_decision", "chemotherapy_not_indicated", 14, 14 if not_indicated and not chemo_pos else 0,
          not_indicated or (chemo_pos[0] if chemo_pos else None))
    rationale = first(r"node[- ]negative|\bpn0|\bn0\b|0\s*/\s*2|postmenopausal|recurrence score|\brs\b|21[- ]gene|"
                      r"oncotype|tailorx|low (?:genomic )?risk|no (?:significant |meaningful )?(?:chemotherapy )?benefit",
                      ans.field_or_all("chemotherapy_decision"))
    award("chemotherapy_decision", "gives_rationale", 6, 6 if rationale else 0, rationale)

    # ---- Endocrine therapy (20) + critical error
    endo_pos, endo_neg, endo_cond = positive_sentences(ans.sents("endocrine_therapy"), ENDOCRINE)
    award("endocrine_therapy", "recommends_endocrine_therapy", 10, 10 if endo_pos else 0,
          endo_pos[0] if endo_pos else (endo_neg[0] if endo_neg else None))
    agent = first(r"aromatase inhibitor|\bais?\b|anastrozole|letrozole|exemestane|tamoxifen", ans.field_or_all("endocrine_therapy"))
    award("endocrine_therapy", "names_AI_or_tamoxifen", 5, 5 if agent else 0, agent)
    dur = first(r"\b(?:5|five|7|seven|10|ten)[- ]?(?:to[- ]\d+[- ])?(?:years?|yrs?)\b|\b5\s*[-–]\s*10\b|extended", ans.field_or_all("endocrine_therapy"))
    award("endocrine_therapy", "states_duration", 5, 5 if dur else 0, dur)

    # ---- Radiotherapy (10) + critical error
    rt_pos, rt_neg, rt_cond = positive_sentences(ans.sents("radiotherapy"), RADIATION)
    rt_pos_specific = [s for s in rt_pos if re.search(r"whole[- ]breast|wbrt|partial[- ]breast|apbi|\bpbi\b|hypofraction", s)]
    if rt_pos_specific:
        note = "partial-breast irradiation accepted (ASTRO suitable group); confirm with oncologist" \
            if re.search(r"partial|apbi|\bpbi\b", rt_pos_specific[0]) and not re.search(r"whole", rt_pos_specific[0]) else None
        award("radiotherapy", "recommends_breast_RT", 10, 10, rt_pos_specific[0], note)
    elif rt_pos:
        award("radiotherapy", "recommends_breast_RT", 10, 7, rt_pos[0], "radiotherapy recommended without specifying whole/partial breast")
    else:
        award("radiotherapy", "recommends_breast_RT", 10, 0, rt_neg[0] if rt_neg else None)

    # ---- Supportive (5) and missing information (5)
    sup = first(r"dexa|dxa|bone (?:mineral )?density|bone health|calcium|vitamin d|osteopor|bisphosphonate|denosumab",
                ans.field_or_all("supportive_monitoring"))
    award("supportive_monitoring", "bone_health", 5, 5 if sup else 0, sup)
    mi = ans.fields["missing_information"]
    gap = first(r"dexa|dxa|bone (?:mineral )?density|preference|toleran|side[- ]effect|germline|genetic|brca|"
                r"comorbid|adherence|fertility|cardiac|lipid|vitamin d|baseline|menopaus|family history|"
                r"performance|patient (?:goals|values|wishes)|shared decision", mi)
    award("missing_information", "names_relevant_gap", 5, 5 if gap else 0, gap)

    # ---- Critical errors
    critical = []
    if chemo_pos:
        critical.append({"name": "recommends_adjuvant_chemotherapy", "penalty_points": -25, "evidence": chemo_pos[0]})
    her2_pos, _, her2_cond = positive_sentences(ans.sents(), HER2_THERAPY)
    if her2_pos:
        critical.append({"name": "recommends_HER2_targeted_therapy", "penalty_points": -20, "evidence": her2_pos[0]})
    endo_any, _, _ = positive_sentences(ans.sents(), ENDOCRINE)
    if not endo_any:
        critical.append({"name": "omits_endocrine_therapy", "penalty_points": -20, "evidence": None})
    rt_any, rt_any_neg, _ = positive_sentences(ans.sents(), RADIATION)
    if not rt_any:
        critical.append({"name": "omits_adjuvant_radiotherapy", "penalty_points": -10,
                         "evidence": rt_any_neg[0] if rt_any_neg else None})

    for label, items in [("conditional chemotherapy wording", chemo_cond), ("conditional HER2-therapy wording", her2_cond),
                         ("conditional radiotherapy wording", rt_cond), ("conditional endocrine wording", endo_cond)]:
        for s in items:
            review.append({"reason": label, "sentence": s})
    if ans.missing_fields:
        review.append({"reason": "required keys missing or empty", "sentence": ", ".join(ans.missing_fields)})

    raw = sum(c["score"] for d in crit.values() for c in d.values())
    penalty = sum(c["penalty_points"] for c in critical)
    final = max(0, raw + penalty)
    metrics = {d: {"score": sum(c["score"] for c in cs.values()) / sum(c["max"] for c in cs.values()),
                   "points": sum(c["score"] for c in cs.values()), "max_points": sum(c["max"] for c in cs.values()),
                   "criteria": cs} for d, cs in crit.items()}
    return {"reward": final / 100, "score": final, "max_score": 100, "passed": final >= 75 and not critical,
            "raw_score": raw, "penalty": penalty, "infra_failure": False, "invalid_json": False,
            "metrics": metrics, "critical_errors": critical, "needs_doctor_review": review}


def zero_result(**flags) -> dict:
    return {"reward": 0.0, "score": 0, "max_score": 100, "passed": False, "raw_score": 0, "penalty": 0,
            "infra_failure": False, "invalid_json": False, **flags, "metrics": {}, "critical_errors": [],
            "needs_doctor_review": []}


def score_file(path: Path) -> dict:
    if not path.exists():
        return zero_result(infra_failure=True, note="no answer file was produced; this is not a clinical score")
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError("top-level JSON is not an object")
    except (json.JSONDecodeError, ValueError) as exc:
        return zero_result(invalid_json=True, note=f"answer is not a JSON object: {exc}")
    return grade(Answer(data))


REWARD_KEYS = ["diagnosis_and_biology", "genomic_risk", "chemotherapy_decision", "endocrine_therapy",
               "radiotherapy", "supportive_monitoring", "missing_information"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = score_file(args.response)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_name("review.json").write_text(json.dumps(result, indent=2) + "\n")
    reward = {"reward": result["reward"]}
    for key in REWARD_KEYS:
        reward[key] = result["metrics"].get(key, {}).get("score", 0.0)
    args.output.write_text(json.dumps(reward, indent=2) + "\n")


if __name__ == "__main__":
    main()
