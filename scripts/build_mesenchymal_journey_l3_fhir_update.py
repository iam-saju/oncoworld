#!/usr/bin/env python3
"""Build the L3 FHIR update Bundle for intracranial_mesenchymal_journey_v1 from its narrative chart update.

Usage: python3 scripts/build_mesenchymal_journey_l3_fhir_update.py   (run from the repo root)

Carries exactly the facts in
harbor_cases/intracranial_mesenchymal_journey_v1_narrative/steps/L3-chemo-and-targeted-therapy/workdir/case/chart/01_2027-01-12_update.txt,
no more. Deliberately thin, like the narrative counterpart: this step's actual new facts (temozolomide started
and tolerated; the NGS result itself) are revealed progressively inside instruction.md's own question text, not
in the chart - matching the dlbcl_0003_journey_v2 convention of layering new ground truth within later questions,
not only in the interval-history document. This update only needs to set up q1's premise: the liquid biopsy has
been sent and a treatment decision is needed before the result returns.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

BASE = "http://oncoworld.example/fhir"
SCT, LOINC = "http://snomed.info/sct", "http://loinc.org"
HTEST = {"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "HTEST", "display": "test health data"}
P = "mesench-0001"

INTERVAL_HISTORY = (Path(__file__).resolve().parent.parent / "harbor_cases"
                     / "intracranial_mesenchymal_journey_v1_narrative" / "steps" / "L3-chemo-and-targeted-therapy"
                     / "workdir" / "case" / "chart" / "01_2027-01-12_update.txt").read_text()


def cc(*codings, text=None):
    out = {"coding": [{"system": s, "code": c, "display": d} for s, c, d in codings]}
    if text:
        out["text"] = text
    return out


def ref(r):
    return {"reference": r}


def build() -> dict:
    PT = f"Patient/{P}-patient"
    ONC = f"Practitioner/{P}-neurooncologist"
    resources: list[dict] = []

    def add(res, summary):
        res["text"] = {"status": "generated",
                       "div": f'<div xmlns="http://www.w3.org/1999/xhtml"><p>{escape(summary)}</p></div>'}
        resources.append(res)

    add({"resourceType": "DocumentReference", "id": f"{P}-l3-interval-history",
         "status": "current", "type": cc((LOINC, "34117-2", "History and physical note")),
         "category": [cc(("http://hl7.org/fhir/us/core/CodeSystem/us-core-documentreference-category",
                          "clinical-note", "Clinical Note"))],
         "subject": ref(PT), "date": "2027-01-12T09:00:00Z", "author": [ref(ONC)],
         "description": "Interval history, 2026-12-15 to 2027-01-12",
         "content": [{"attachment": {"contentType": "text/plain",
                                      "data": __import__("base64").b64encode(INTERVAL_HISTORY.encode()).decode()}}]},
        "Interval history, 2026-12-15 to 2027-01-12: liquid biopsy sent, result pending, treatment decision needed now.")

    add({"resourceType": "ServiceRequest", "id": f"{P}-l3-ngs-request", "status": "active", "intent": "order",
         "code": cc((LOINC, "81247-9", "Master HL7 genetic variant reporting panel"),
                    text="Circulating tumor DNA next-generation sequencing, peripheral blood"),
         "subject": ref(PT), "authoredOn": "2026-12-15", "requester": ref(ONC),
         "note": [{"text": "Peripheral blood liquid biopsy for ctDNA NGS; estimated 4-week turnaround. Result "
                           "not yet available as of this visit."}]},
        "ctDNA NGS ordered 2026-12-15 on peripheral blood; result pending.")

    return {"resourceType": "Bundle", "id": f"{P}-l3-update", "meta": {"security": [HTEST]},
            "identifier": {"system": BASE + "/sid/bundle", "value": f"{P}-l3-update"}, "type": "collection",
            "timestamp": "2027-01-12T09:00:00Z",
            "entry": [{"fullUrl": f"{BASE}/{r['resourceType']}/{r['id']}", "resource": r} for r in resources]}


def main() -> None:
    root = Path(__file__).resolve().parent.parent / "harbor_cases"
    out = (root / "intracranial_mesenchymal_journey_v1_fhir" / "steps" / "L3-chemo-and-targeted-therapy" / "workdir"
           / "case" / "fhir_updates" / "01_2027-01-12_update.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    bundle = build()
    out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out.relative_to(root.parent)} ({len(bundle['entry'])} resources)")


if __name__ == "__main__":
    main()
