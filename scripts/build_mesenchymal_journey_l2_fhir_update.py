#!/usr/bin/env python3
"""Build the L2 FHIR update Bundle for intracranial_mesenchymal_journey_v1 from its narrative chart update.

Usage: python3 scripts/build_mesenchymal_journey_l2_fhir_update.py   (run from the repo root)

Carries exactly the facts in
harbor_cases/intracranial_mesenchymal_journey_v1_narrative/steps/L2-molecular-access/workdir/case/chart/01_2026-12-15_update.txt,
no more. References the existing Patient/Practitioner/Organization resources from the base bundle
(scripts/build_mesenchymal_fhir_bundle.py) by id rather than re-declaring them, matching the journey convention
used by scripts/build_journey_v2.py: a later layer's update bundle is an increment, not a restatement.

The entity remains deliberately unresolved: final surgical pathology is coded as a non-specific high-grade
mesenchymal neoplasm (no SNOMED/ICD-O concept exists for "NOS" at this specificity, so the code carries the
closest real class and the free text carries the "NOS"/negative-STAT6 detail, same convention as the base
script).

Codes checked 2026-10-23: SNOMED 1201979001 "Excision of lesion of brain" (FindACode; craniotomy+excision series),
169332007 "External beam radiotherapy" (HL7 mCODE teleradiotherapy value set / VSAC), LOINC 60568-3 and 24587-8
(reused from the base bundle, already checked there), LA9623-5 "ECOG 1" (loinc.org LL529-9 answer list, checked
directly against loinc.org).
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

BASE = "http://oncoworld.example/fhir"
SCT, LOINC, UCUM = "http://snomed.info/sct", "http://loinc.org", "http://unitsofmeasure.org"
OBS_CAT = "http://terminology.hl7.org/CodeSystem/observation-category"
HTEST = {"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "HTEST", "display": "test health data"}
P = "mesench-0001"

INTERVAL_HISTORY = (Path(__file__).resolve().parent.parent / "harbor_cases"
                     / "intracranial_mesenchymal_journey_v1_narrative" / "steps" / "L2-molecular-access"
                     / "workdir" / "case" / "chart" / "01_2026-12-15_update.txt").read_text()


def cc(*codings, text=None):
    out = {"coding": [{"system": s, "code": c, "display": d} for s, c, d in codings]}
    if text:
        out["text"] = text
    return out


def ref(r):
    return {"reference": r}


def qty(value, unit, code):
    return {"value": value, "unit": unit, "system": UCUM, "code": code}


def build() -> dict:
    PT = f"Patient/{P}-patient"
    ONC = f"Practitioner/{P}-neurooncologist"
    NEUROSURG, NEUROPATH, IMAGING = (f"Organization/{P}-{x}" for x in
                                      ("neurosurgery", "neuropathology-lab", "imaging"))
    resources: list[dict] = []

    def add(res, summary):
        res["text"] = {"status": "generated",
                       "div": f'<div xmlns="http://www.w3.org/1999/xhtml"><p>{escape(summary)}</p></div>'}
        resources.append(res)

    # ---- interval history: the first document, ground truth for what actually happened (journey convention)
    add({"resourceType": "DocumentReference", "id": f"{P}-l2-interval-history",
         "status": "current", "type": cc((LOINC, "34117-2", "History and physical note")),
         "category": [cc(("http://hl7.org/fhir/us/core/CodeSystem/us-core-documentreference-category",
                          "clinical-note", "Clinical Note"))],
         "subject": ref(PT), "date": "2026-12-15T09:00:00Z", "author": [ref(ONC)],
         "description": "Interval history, 2026-10-21 to 2026-12-15",
         "content": [{"attachment": {"contentType": "text/plain",
                                      "data": __import__("base64").b64encode(INTERVAL_HISTORY.encode()).decode()}}]},
        "Interval history, 2026-10-21 to 2026-12-15: subtotal resection, postoperative RT, growing residual disease.")

    # ---- craniotomy with subtotal resection, 2026-10-28
    add({"resourceType": "Procedure", "id": f"{P}-l2-resection", "status": "completed",
         "code": cc((SCT, "1201979001", "Excision of lesion of brain"),
                    text="Craniotomy with subtotal resection of left frontal lobe mass"),
         "subject": ref(PT), "performedDateTime": "2026-10-28", "performer": [{"actor": ref(NEUROSURG)}],
         "bodySite": [cc(text="Left frontal lobe")],
         "note": [{"text": "Subtotal resection; posterior margin left in situ adjacent to eloquent cortex."}]},
        "Craniotomy, subtotal resection of the left frontal mass, 2026-10-28.")

    # ---- final surgical pathology, issued 2026-11-04: still non-specific, STAT6 negative (SFT excluded)
    add({"resourceType": "DiagnosticReport", "id": f"{P}-l2-surgical-pathology", "status": "final",
         "category": [cc(("http://terminology.hl7.org/CodeSystem/v2-0074", "SP", "Surgical Pathology"))],
         "code": cc((LOINC, "60568-3", "Pathology synoptic report")), "subject": ref(PT),
         "effectiveDateTime": "2026-10-28", "issued": "2026-11-04T16:00:00Z", "performer": [ref(NEUROPATH)],
         "conclusion": "High-grade spindle cell/mesenchymal neoplasm, NOS. STAT6 immunohistochemistry negative; "
                       "NAB2-STAT6 fusion not detected. No additional actionable alteration identified on the "
                       "available immunohistochemistry and sequencing panel. The specific entity remains "
                       "unresolved."},
        "Surgical pathology (2026-11-04): high-grade spindle cell/mesenchymal neoplasm, NOS; STAT6 negative; "
        "entity still unresolved.")

    # ---- postoperative focal radiotherapy, 2026-10-31 to 2026-12-05
    add({"resourceType": "Procedure", "id": f"{P}-l2-radiotherapy", "status": "completed",
         "code": cc((SCT, "169332007", "External beam radiotherapy")),
         "subject": ref(PT), "performedPeriod": {"start": "2026-10-31", "end": "2026-12-05"},
         "bodySite": [cc(text="Left frontal resection bed")],
         "note": [{"text": "Postoperative focal radiotherapy to the resection bed, 60 Gy in 30 fractions, "
                           "completed 2026-12-05."}]},
        "Postoperative focal radiotherapy to the resection bed, 60 Gy/30 fractions, completed 2026-12-05.")

    # ---- surveillance MRI, 2026-12-12: growth at the primary site, C6 nodule stable
    add({"resourceType": "Observation", "id": f"{P}-l2-residual-growth", "status": "final",
         "category": [cc((OBS_CAT, "imaging", "Imaging"))], "code": cc((LOINC, "21889-1", "Size Tumor")),
         "subject": ref(PT), "effectiveDateTime": "2026-12-12", "performer": [ref(IMAGING)],
         "method": cc((SCT, "113091000", "Magnetic resonance imaging (procedure)")),
         "bodySite": cc(text="Left frontal resection margin"),
         "interpretation": [cc(("http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "H",
                                "Higher than normal (worse)"), text="Interval growth since 2026-10-17 baseline")]},
        "Interval growth of residual enhancing tumor along the left frontal resection margin, 2026-12-12.")
    add({"resourceType": "Observation", "id": f"{P}-l2-c6-nodule-stable", "status": "final",
         "category": [cc((OBS_CAT, "imaging", "Imaging"))], "code": cc((LOINC, "21889-1", "Size Tumor")),
         "subject": ref(PT), "effectiveDateTime": "2026-12-12", "performer": [ref(IMAGING)],
         "method": cc((SCT, "113091000", "Magnetic resonance imaging (procedure)")),
         "bodySite": cc(text="Posterior pial surface of the cervical spinal cord at C6"),
         "component": [{"code": cc((LOINC, "33728-7", "Size.maximum dimension in Tumor")), "valueQuantity": qty(0.5, "cm", "cm")}],
         "interpretation": [cc(("http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "N", "Normal"),
                               text="Unchanged from 2026-10-17 baseline")]},
        "C6 pial nodule stable in size and enhancement, unchanged from prior, 2026-12-12.")
    add({"resourceType": "DiagnosticReport", "id": f"{P}-l2-surveillance-mri", "status": "final",
         "category": [cc((LOINC, "LP29684-5", "Radiology"))],
         "code": cc((LOINC, "24587-8", "MR Brain WO and W contrast IV"), text="Surveillance brain and spine MRI"),
         "subject": ref(PT), "effectiveDateTime": "2026-12-12", "issued": "2026-12-12T18:00:00Z",
         "performer": [ref(IMAGING)],
         "result": [ref(f"Observation/{P}-l2-residual-growth"), ref(f"Observation/{P}-l2-c6-nodule-stable")],
         "conclusion": "Interval growth of residual enhancing tumor along the left frontal resection margin. "
                       "The C6 pial nodule is stable in size and enhancement, unchanged from prior."},
        "Surveillance brain/spine MRI, 2026-12-12: residual disease growth at the primary site; C6 nodule stable.")

    # ---- performance status, 2026-12-15 (still 1)
    add({"resourceType": "Observation", "id": f"{P}-l2-ecog", "status": "final",
         "category": [cc((OBS_CAT, "survey", "Survey"))],
         "code": cc((LOINC, "89247-1", "ECOG Performance Status score")), "subject": ref(PT),
         "effectiveDateTime": "2026-12-15", "performer": [ref(ONC)], "valueInteger": 1,
         "interpretation": [cc((LOINC, "LA9623-5", "Restricted in physically strenuous activity but ambulatory "
                                "and able to carry out light or sedentary work"))]},
        "ECOG performance status 1, 2026-12-15.")

    return {"resourceType": "Bundle", "id": f"{P}-l2-update", "meta": {"security": [HTEST]},
            "identifier": {"system": BASE + "/sid/bundle", "value": f"{P}-l2-update"}, "type": "collection",
            "timestamp": "2026-12-15T09:00:00Z",
            "entry": [{"fullUrl": f"{BASE}/{r['resourceType']}/{r['id']}", "resource": r} for r in resources]}


def main() -> None:
    root = Path(__file__).resolve().parent.parent / "harbor_cases"
    out = (root / "intracranial_mesenchymal_journey_v1_fhir" / "steps" / "L2-molecular-access" / "workdir"
           / "case" / "fhir_updates" / "01_2026-12-15_update.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    bundle = build()
    out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out.relative_to(root.parent)} ({len(bundle['entry'])} resources)")


if __name__ == "__main__":
    main()
