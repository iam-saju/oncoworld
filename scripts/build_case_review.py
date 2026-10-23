#!/usr/bin/env python3
"""Build the oncologist sign-off page for ONE case: patient, reference plan, checklist by clinical area, open
questions and borderline real examples, each with agree/change controls.

Usage: python3 scripts/build_case_review.py dlbcl_0003 [--out reports/review_dlbcl_0003.html] [--fragment]

Reads cases_src/<case>/{case.toml, gold.json, rubric_v2.toml, review_labels.json, review_questions.json} and the
grading truth set (cases_src/truth_set) for how real model answers fared on each item. --fragment writes page content
only (for publishing as a claude.ai Artifact); verdicts are then saved to the artifact's shared store.
"""
import argparse
import html
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_cases_v2 import LABS, age_on, fmt, lab_flag, ref_text  # noqa: E402
from build_report import DOMAINS, MODELS  # noqa: E402

FIELD = {"diagnosis": "Diagnosis", "stage": "Stage", "biology": "Biology", "prognosis": "Prognosis",
         "first_line_treatment": "First-line treatment", "cns_risk": "CNS risk", "response_assessment": "Response assessment",
         "pretreatment_workup": "Pre-treatment work-up", "supportive_care": "Supportive care",
         "fitness_and_goals": "Fitness and goals", "missing_information": "Missing information"}


def patient_facts(case: dict) -> dict:
    pt, g = case["patient"], case["patient"]["gender"]
    rd = case["meta"]["record_date"]
    age = age_on(pt["birth_date"], rd)
    latest = {}
    for panel in sorted(case.get("labs", []), key=lambda p: p["date"]):
        for it in panel["items"]:
            latest[it["key"]] = (it["value"], panel["date"])
    abnormal = [{"test": LABS[k][2], "value": f"{fmt(v)} {LABS[k][3] or ''}".strip(), "ref": ref_text(k, g),
                 "flag": lab_flag(k, v, g), "date": d} for k, (v, d) in latest.items() if lab_flag(k, v, g)]
    path = case.get("pathology", {})
    return {
        "who": f"{pt['given']} {pt['family']} (synthetic), {age}-year-old {g}, ECOG {case['ecog']['value']}",
        "problems": [c["display"] for c in case.get("conditions", [])],
        "medications": [m["text"] for m in case.get("medications", [])],
        "allergies": [f"{a['substance']}: {a['reaction']}" for a in case.get("allergies", [])] or ["None known"],
        "abnormal_labs": abnormal,
        "pathology": ([f"IHC {k}: " + (("positive" if v else "negative") if isinstance(v, bool) else f"{v}%") for k, v in path.get("ihc", {}).items()]
                      + [f"FISH {k}: {'rearranged' if v else 'no rearrangement'}" for k, v in path.get("fish", {}).items()]),
        "documents": [{"title": d["title"], "date": d["date"], "text": d["text"].strip()} for d in case.get("documents", [])],
    }


def truth_evidence(case_id: str, rubric_items: dict) -> tuple[dict, list]:
    """Per item: how often real answers met it; plus borderline examples worth an oncologist's verdict."""
    ts = ROOT / "cases_src" / "truth_set"
    rate, examples = {}, []
    sonnet = ts / "judge_cache" / "claude-sonnet-5-5"
    sys.path.insert(0, str(ROOT / "graders" / "oncoworld_grader"))
    import grader_v2 as G
    for pf in sorted((ts / "packets").glob("*.json")):
        p = json.loads(pf.read_text())
        if not p["rubric"].endswith(f"{case_id}/rubric_v2.toml"):
            continue
        lf = ts / "labels" / pf.name
        if not lf.exists():
            continue
        labels = json.loads(lf.read_text())["labels"]
        text = G.read_response_text(json.dumps(p["answer"], ensure_ascii=False)).lower()
        judge = json.loads((sonnet / pf.name).read_text()) if (sonnet / pf.name).exists() else {}
        model = MODELS.get(p["model"], (p["model"],))[0]
        for iid, t in labels.items():
            if iid not in rubric_items:
                continue
            r = rate.setdefault(iid, [0, 0])
            r[1] += 1
            r[0] += bool(t["met"])
            it = rubric_items[iid]
            rx = G.rule_met(it, text)
            jv = judge.get(iid, {}).get("met")
            disputed = (rx is not None and bool(rx) != bool(t["met"])) or (jv is not None and jv != bool(t["met"]))
            if it["severity"] != "minor" and (disputed or t.get("confidence") in ("low", "medium")) and t.get("quote"):
                examples.append({"key": f"{pf.stem}#{iid}", "item": iid, "model": model, "quote": t["quote"],
                                 "ai_verdict": bool(t["met"]), "ai_note": t.get("note", ""),
                                 "rules": None if rx is None else bool(rx), "judge": jv,
                                 "severity": it["severity"], "kind": it["kind"]})
    # one or two per item, unsafe-error items first, at most 12
    order = {"dangerous": 0, "important": 1}
    examples.sort(key=lambda e: (order.get(e["severity"], 2), e["item"]))
    picked, per = [], {}
    for e in examples:
        if per.get(e["item"], 0) < 2 and len(picked) < 12:
            picked.append(e)
            per[e["item"]] = per.get(e["item"], 0) + 1
    return rate, picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--fragment", action="store_true")
    args = ap.parse_args()
    d = ROOT / "cases_src" / args.case
    case = tomllib.loads((d / "case.toml").read_text())
    rubric = tomllib.loads((d / "rubric_v2.toml").read_text())
    labels = json.loads((d / "review_labels.json").read_text()) if (d / "review_labels.json").exists() else {}
    lab_by = {i["id"]: i for i in labels.get("items", [])}
    questions = json.loads((d / "review_questions.json").read_text())["questions"] if (d / "review_questions.json").exists() else []
    by_id = {i["id"]: i for i in rubric["items"]}
    rate, examples = truth_evidence(args.case, by_id)
    items = [{"id": i["id"], "domain": i["domain"], "kind": i["kind"], "severity": i["severity"], "points": i["points"],
              "label": lab_by.get(i["id"], {}).get("label") or i["text"], "why": lab_by.get(i["id"], {}).get("why", ""),
              "criterion": i["text"], "met": rate.get(i["id"], [0, 0])[0], "n": rate.get(i["id"], [0, 0])[1]}
             for i in rubric["items"]]
    for e in examples:
        e["label"] = lab_by.get(e["item"], {}).get("label") or by_id[e["item"]]["text"]
    gold = json.loads((d / "gold.json").read_text())
    data = {"case": args.case, "card": labels.get("case_card", {}), "facts": patient_facts(case),
            "plan": [{"field": FIELD.get(k, k), "text": v} for k, v in gold.items()],
            "domains": [{"key": k, "label": v} for k, v in DOMAINS], "items": items, "questions": questions,
            "examples": examples, "rubric_version": rubric.get("version"), "review_status": rubric.get("review_status"),
            "pass_mark": round(rubric.get("passing_score", 0.75) * 100)}
    title = f"Case review: {labels.get('case_card', {}).get('title', args.case)}"
    page = (Path(__file__).with_name("case_review_template.html").read_text()
            .replace("__TITLE__", html.escape(title)).replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")))
    if not args.fragment:
        page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>' + page + "</body></html>")
    out = args.out or ROOT / "reports" / f"review_{args.case}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    print(f"wrote {out} ({len(items)} checklist items, {len(questions)} questions, {len(examples)} examples)")


if __name__ == "__main__":
    main()
