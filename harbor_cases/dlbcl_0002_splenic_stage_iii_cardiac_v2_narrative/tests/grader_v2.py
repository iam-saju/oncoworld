#!/usr/bin/env python3
"""OncoWorld v2 grader: atomic physician rubric, optional LLM judge, deterministic safety checks.

Stdlib only, so it runs in the python:3.11-slim task image. Source of truth lives in
graders/oncoworld_grader/; scripts/build_cases_v2.py copies it into every v2 task's tests/.

Rubric (tests/rubric_v2.toml), one [[items]] table per criterion:
  id, domain, text      text is the criterion the judge reads, phrased so "met" means the statement is true
  kind                  must | should | must_not
  severity              minor | important | dangerous
  points                must/should: points earned when met; must_not: points deducted when met
  any / all / affirm / recommend / check     regex fallback (see fallback_met)

Scoring:
  earned    = points of met must/should items, minus points of met must_not items
  dangerous = a missed must item or a met must_not item whose severity is "dangerous"
  reward    = earned / total, or 0.0 when any dangerous error fires (a dangerous error fails the case)
  passed    = reward >= passing_score and no dangerous error

Judge: an OpenAI-compatible chat endpoint, used when ONCOWORLD_JUDGE_API_KEY is set. Every "met" verdict must
quote the answer verbatim; a quote that is not in the answer downgrades the verdict to not met. Without a key
the regex fallback decides and the output says judge="none". In judge mode the regex result is still recorded
per item, and disagreements are listed for human review.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tomllib
import urllib.request
from pathlib import Path

# --- sentence-scoped negation helpers, carried over from the v1 graders (patched 2026-10-10) ---
_SENTENCE_SPLIT = re.compile(r"(?<=[.;!?])\s+|\n+|\"\s*,\s*\"|[\[{]\s*\"|\"\s*[\]}]")
_NEGATION = re.compile(
    r"\b(?:not|no|neither|nor|without|absent|absence|excluded?|excludes|exclusion|rul(?:ed|es|ing) out|"
    r"negative(?!\s+fish)|below|lacks?|lacking|does not|do not|is not|are not|isn't|aren't|rather than|instead of|"
    r"unnecessary|unlikely|avoid\w*|defer\w*|withh[eo]ld\w*)\b"
)
_NEGATED_AFTER = re.compile(
    r"\W*(?:[\w/-]+\W+){0,5}?(?:is|are|was|were|has been|have been|remains?|be)\s+"
    r"(?:not|excluded|ruled out|absent|negative|unlikely|unnecessary|inappropriate)\b"
    r"|\W*(?:[\w/-]+\W+){0,3}?(?:excluded|ruled out|not (?:present|identified|detected|met|indicated|recommended))\b"
    r"|\s*(?:lymphoma|status|criteria)?\s*[:=-]\s*(?:negative|not detected|absent|no)\b"
    r"|\W*(?:[\w/-]+\W+){0,1}?(?:all\s+|both\s+)?(?:negative|not detected|absent|undetected)\b"
)
_NON_PREFIX = re.compile(r"\bnon[- ]?$")
_HEDGE = re.compile(r"\b(?:is defined|are defined|definition|refers to|by definition|criteria for|the term|versus|vs\.?)\b")
_RECOMMEND = re.compile(r"\b(?:recommend\w*|prefer\w*|indicated|should|first[- ]line|use\b|used|consider\w*|appropriate|"
                        r"favou?red|option|regimen of choice|treat\w* with|standard|plan\w*|start\w*|proceed\w*|give|offer\w*)\b")

DOUBLE_HIT = r"double[-_ ]hit|triple[-_ ]hit|hgbl[- ]dh|myc and bcl2 rearrangements"
DOUBLE_EXPRESSOR = r"double[-_ ]expressor|\bdel\b"


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _mentions(text: str, term: str):
    """Yield (sentence, negated) for every sentence mentioning term."""
    for s in sentences(text):
        m = re.search(term, s)
        if not m:
            continue
        clause = re.split(r"\bbut\b|\bhowever\b|;", s[: m.end()])[-1]
        # "non-" negates only the word it is attached to: "non-double-hit" yes, "non-bulky ... R-CHOP" no
        negated = (bool(_NEGATION.search(clause)) or bool(_NON_PREFIX.search(s[: m.start()]))
                   or bool(_NEGATED_AFTER.match(s[m.end():])))
        yield s, negated


def affirms(text: str, term: str) -> bool:
    return any(not neg and not _HEDGE.search(s) for s, neg in _mentions(text, term))


def denies(text: str, term: str) -> bool:
    return any(neg for _, neg in _mentions(text, term))


def recommends(text: str, term: str) -> bool:
    """True when some sentence puts the term forward as a plan without negating it."""
    return any(not neg and _RECOMMEND.search(s) for s, neg in _mentions(text, term))


CHECKS = {
    "affirms_double_hit": lambda t: affirms(t, DOUBLE_HIT),
    "affirms_double_expressor": lambda t: affirms(t, DOUBLE_EXPRESSOR),
    "denies_double_hit": lambda t: denies(t, DOUBLE_HIT) or bool(re.search(
        r"rearrangements?[^.]{0,40}(?:not detected|negative|absent|not identified)|fish[^.]{0,60}(?:negative|no rearrang|not detected)", t)),
    "denies_double_expressor": lambda t: denies(t, DOUBLE_EXPRESSOR) or bool(re.search(
        r"below[^.]{0,60}(?:threshold|cutoff|cut-off)|(?:does|do) not meet[^.]{0,40}(?:double[-_ ]expressor|threshold|criteria)", t)),
    "recommends_da_epoch": lambda t: recommends(t, r"(?:da|dose[- ]adjusted)[- ]?(?:r[- ])?epoch"),
}


def fallback_met(item: dict, text: str) -> bool | None:
    """Regex verdict for one item, or None when the item has no fallback (judge-only)."""
    results = []
    if "any" in item:
        results.append(any(re.search(p, text) for p in item["any"]))
    if "all" in item:
        results.append(all(re.search(p, text) for p in item["all"]))
    if "affirm" in item:
        results.append(any(affirms(text, p) for p in item["affirm"]))
    if "recommend" in item:
        results.append(any(recommends(text, p) for p in item["recommend"]))
    if "check" in item:
        results.append(CHECKS[item["check"]](text))
    return all(results) if results else None


# --- LLM judge ---
JUDGE_PROMPT = """You are a board-certified hematologist-oncologist grading a colleague's written assessment and plan
for a synthetic lymphoma case. Grade ONLY what the response actually says; do not infer intent.

For every criterion below decide whether the statement is TRUE of the response ("met": true) or not.
Some criteria describe errors (e.g. "The response recommends palliative-only care"); for those, "met": true means
the response commits the error. Paraphrase and synonyms count. A passing mention that is contradicted elsewhere
in the response does not count as met for positive criteria, but does count as met for error criteria.

When "met" is true you MUST copy a short verbatim quote (5-40 words) from the response as evidence.
When "met" is false, evidence is "".

Return only JSON: {{"items": [{{"id": "...", "met": true|false, "evidence": "..."}}]}}

CRITERIA:
{criteria}

RESPONSE:
<<<
{response}
>>>"""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\"'`‘’“”]", "", s)).strip().lower()


def call_judge(items: list[dict], response: str) -> dict:
    base = os.environ.get("ONCOWORLD_JUDGE_BASE_URL") or "https://openrouter.ai/api/v1"
    model = os.environ["ONCOWORLD_JUDGE_MODEL"]
    criteria = "\n".join(f"- {it['id']}: {it['text']}" for it in items)
    body = {"model": model, "temperature": 0,
            "messages": [{"role": "user", "content": JUDGE_PROMPT.format(criteria=criteria, response=response)}],
            "response_format": {"type": "json_object"}}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {os.environ['ONCOWORLD_JUDGE_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        content = json.loads(r.read())["choices"][0]["message"]["content"]
    content = re.sub(r"^```(?:json)?|```$", "", content.strip()).strip()
    return {v["id"]: v for v in json.loads(content)["items"]}


def judge_available() -> bool:
    return bool(os.environ.get("ONCOWORLD_JUDGE_API_KEY") and os.environ.get("ONCOWORLD_JUDGE_MODEL"))


# --- scoring ---
def score(response: str, rubric: dict, judge_verdicts: dict | None = None) -> dict:
    """judge_verdicts: {item_id: {"met": bool, "evidence": str}}; None means regex fallback only."""
    lowered = response.lower()
    norm_response = _norm(response)
    items = rubric["items"]
    total = sum(it["points"] for it in items if it["kind"] != "must_not")
    earned = 0
    domains: dict[str, dict] = {}
    dangerous, disagreements, detail = [], [], []

    for it in items:
        fb = fallback_met(it, lowered)
        source = "regex"
        if judge_verdicts is not None and it["id"] in judge_verdicts:
            v = judge_verdicts[it["id"]]
            met = bool(v.get("met"))
            evidence = v.get("evidence", "") or ""
            source = "judge"
            if met and _norm(evidence) not in norm_response:
                met, source = False, "judge_unquoted"   # evidence not found verbatim in the answer
            if fb is not None and fb != met:
                disagreements.append({"id": it["id"], "judge": met, "regex": fb})
        else:
            met, evidence = bool(fb), ""
            if fb is None:
                source = "unscored"   # judge-only item with no judge available; scored as not met
        if it["kind"] == "must_not":
            delta = -it["points"] if met else 0
            fired = met
        else:
            delta = it["points"] if met else 0
            fired = it["kind"] == "must" and not met
        earned += delta
        if fired and it["severity"] == "dangerous":
            dangerous.append(it["id"])
        d = domains.setdefault(it["domain"], {"points": 0, "max_points": 0})
        d["points"] += delta
        if it["kind"] != "must_not":
            d["max_points"] += it["points"]
        detail.append({"id": it["id"], "domain": it["domain"], "kind": it["kind"], "severity": it["severity"],
                       "points": it["points"], "met": met, "delta": delta, "source": source, "regex": fb,
                       "evidence": evidence})

    raw = max(0, earned)
    reward = 0.0 if dangerous else round(raw / total, 4)
    passing = rubric.get("passing_score", 0.75)
    for d in domains.values():
        d["score"] = round(max(0, d["points"]) / d["max_points"], 4) if d["max_points"] else 1.0
    return {"reward": reward, "raw_points": raw, "max_points": total, "passed": reward >= passing and not dangerous,
            "dangerous_errors": dangerous, "judge": "none" if judge_verdicts is None else os.environ.get("ONCOWORLD_JUDGE_MODEL", "injected"),
            "rubric_version": rubric.get("version"), "review_status": rubric.get("review_status"),
            "domains": domains, "items": detail, "judge_regex_disagreements": disagreements}


def read_response(path: Path) -> str:
    raw = path.read_text()
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, indent=1)
    except json.JSONDecodeError:
        return raw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--response", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--rubric", type=Path, default=Path(__file__).with_name("rubric_v2.toml"))
    args = ap.parse_args()
    rubric = tomllib.loads(args.rubric.read_text())
    response = read_response(args.response)
    verdicts, judge_error = None, None
    if judge_available():
        try:
            verdicts = call_judge(rubric["items"], response)
        except Exception as e:  # judge outage must not zero the model: fall back and say so
            judge_error = f"{type(e).__name__}: {e}"
    result = score(response, rubric, verdicts)
    if judge_error:
        result["judge"], result["judge_error"] = "none", judge_error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_name("review.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    compact = {"reward": result["reward"], "passed": float(result["passed"]),
               "dangerous_errors": float(len(result["dangerous_errors"]))}
    compact.update({k: v["score"] for k, v in sorted(result["domains"].items())})
    args.output.write_text(json.dumps(compact, indent=2) + "\n")


if __name__ == "__main__":
    main()
