#!/usr/bin/env python3
"""Build the FHIR R4 / mCODE bundle for intracranial_mesenchymal_0001 from its narrative chart.

Usage: python3 scripts/build_mesenchymal_fhir_bundle.py   (run from the repo root)

Carries exactly the facts in harbor_cases/intracranial_mesenchymal_0001_narrative/environment/case/*.txt, no more:
the primary and secondary Condition resources are deliberately verificationStatus "provisional", never "confirmed",
because the source biopsy itself is only "suggestive of" the entity - stating a confirmed diagnosis in the chart
would hand the model the exact judgment this case asks it to withhold.

Codes checked 2026-10-23: D43.0/D43.4 (icd10data.com), SNOMED 25064002/422400008/287511004/113091000
(FindACode/SNOMED browsers), LOINC 24587-8/30855-1/89247-1 (FindACode/loinc.org), LA9624-3 (reused from
scripts/build_dlbcl_fhir_bundles.py, same ECOG 2 answer code). No SNOMED concept names "stereotactic biopsy"
specifically; 287511004 "Non-surgical biopsy of brain" is the nearest real code, with the stereotactic detail
carried only in CodeableConcept.text and the procedure's own note - the honest alternative to guessing a code.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

BASE = "http://oncoworld.example/fhir"
SCT, LOINC, UCUM = "http://snomed.info/sct", "http://loinc.org", "http://unitsofmeasure.org"
ICD10 = "http://hl7.org/fhir/sid/icd-10-cm"
MC = "http://hl7.org/fhir/us/mcode/StructureDefinition/"
USC = "http://hl7.org/fhir/us/core/StructureDefinition/"
OBS_CAT = "http://terminology.hl7.org/CodeSystem/observation-category"
V2_0074 = "http://terminology.hl7.org/CodeSystem/v2-0074"
HTEST = {"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "HTEST", "display": "test health data"}
P = "mesench-0001"


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
    BRAIN_MASS = f"Condition/{P}-brain-mass"
    C6_NODULE = f"Condition/{P}-c6-nodule"
    BRAIN_MRI, SPINE_MRI = f"DiagnosticReport/{P}-brain-mri", f"DiagnosticReport/{P}-spine-mri"
    BIOPSY_PATH = f"DiagnosticReport/{P}-biopsy-pathology"
    SPEC = f"Specimen/{P}-biopsy-specimen"
    NEUROPATH, NEUROSURG, IMAGING = (f"Organization/{P}-{x}" for x in ("neuropathology-lab", "neurosurgery", "imaging"))
    ONC = f"Practitioner/{P}-neurooncologist"
    resources: list[dict] = []

    def add(res, summary):
        res["text"] = {"status": "generated",
                       "div": f'<div xmlns="http://www.w3.org/1999/xhtml"><p>{escape(summary)}</p></div>'}
        resources.append(res)

    # ---- patient
    add({"resourceType": "Patient", "id": f"{P}-patient",
         "meta": {"profile": [MC + "mcode-cancer-patient"], "security": [HTEST]},
         "extension": [{"url": USC + "us-core-birthsex", "valueCode": "M"}],
         "identifier": [{"use": "usual", "type": cc(("http://terminology.hl7.org/CodeSystem/v2-0203", "MR", "Medical record number")),
                         "system": BASE + "/sid/mrn", "value": P.upper()}],
         "name": [{"use": "official", "family": "Sample", "given": ["Daniel"]}],
         "gender": "male", "birthDate": "1992-06-01"},
        "Synthetic patient Daniel Sample, male, 34 years old. Test data, not a real person.")

    # ---- presenting symptoms (one week of headache and vomiting)
    for i, (code, display) in enumerate([("25064002", "Headache"), ("422400008", "Vomiting")], 1):
        add({"resourceType": "Condition", "id": f"{P}-symptom-{i}",
             "meta": {"profile": [USC + "us-core-condition-problems-health-concerns"]},
             "clinicalStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active")),
             "verificationStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "Confirmed")),
             "category": [cc(("http://terminology.hl7.org/CodeSystem/condition-category", "problem-list-item", "Problem List Item"))],
             "code": cc((SCT, code, display)), "subject": ref(PT),
             "onsetString": "about 1 week", "recordedDate": "2026-10-16"},
            f"Presenting symptom: {display}, about 1 week.")

    # ---- performance status (reuses the ECOG 2 answer code from build_dlbcl_fhir_bundles.py)
    add({"resourceType": "Observation", "id": f"{P}-ecog", "meta": {"profile": [MC + "mcode-ecog-performance-status"]},
         "status": "final", "category": [cc((OBS_CAT, "survey", "Survey"))],
         "code": cc((LOINC, "89247-1", "ECOG Performance Status score")), "subject": ref(PT),
         "effectiveDateTime": "2026-10-16", "performer": [ref(ONC)], "valueInteger": 2,
         "interpretation": [cc((LOINC, "LA9624-3", "Ambulatory and capable of all selfcare but unable to carry out "
                                "any work activities. Up and about more than 50% of waking hours"))]},
        "ECOG performance status 2.")

    # ---- brain MRI: left frontal mass
    add({"resourceType": "Observation", "id": f"{P}-brain-mass-size", "status": "final",
         "category": [cc((OBS_CAT, "imaging", "Imaging"))], "code": cc((LOINC, "21889-1", "Size Tumor")),
         "subject": ref(PT), "effectiveDateTime": "2026-10-17", "performer": [ref(IMAGING)],
         "method": cc((SCT, "113091000", "Magnetic resonance imaging (procedure)")),
         "bodySite": cc(text="Left frontal lobe"),
         "component": [{"code": cc((LOINC, "33728-7", "Size.maximum dimension in Tumor")), "valueQuantity": qty(4.2, "cm", "cm")},
                       {"code": cc(text="Second dimension"), "valueQuantity": qty(3.5, "cm", "cm")},
                       {"code": cc(text="Third dimension"), "valueQuantity": qty(3.0, "cm", "cm")}]},
        "Left frontal mass, 4.2 x 3.5 x 3.0 cm on MRI.")
    add({"resourceType": "DiagnosticReport", "id": f"{P}-brain-mri", "meta": {"profile": [USC + "us-core-diagnosticreport-note"]},
         "status": "final", "category": [cc((LOINC, "LP29684-5", "Radiology"))],
         "code": cc((LOINC, "24587-8", "MR Brain WO and W contrast IV")), "subject": ref(PT),
         "effectiveDateTime": "2026-10-17", "issued": "2026-10-17T15:00:00Z", "performer": [ref(IMAGING)],
         "result": [ref(f"Observation/{P}-brain-mass-size")],
         "conclusion": "Well-circumscribed, lobulated, extra-axial/cortically based mass centered in the left "
                       "frontal lobe, approximately 4.2 x 3.5 x 3.0 cm."},
        "Brain MRI, 2026-10-17: left frontal extra-axial/cortically based mass.")

    # ---- spine MRI: C6 pial nodule
    add({"resourceType": "Observation", "id": f"{P}-c6-nodule-size", "status": "final",
         "category": [cc((OBS_CAT, "imaging", "Imaging"))], "code": cc((LOINC, "21889-1", "Size Tumor")),
         "subject": ref(PT), "effectiveDateTime": "2026-10-17", "performer": [ref(IMAGING)],
         "method": cc((SCT, "113091000", "Magnetic resonance imaging (procedure)")),
         "bodySite": cc(text="Posterior pial surface of the cervical spinal cord at C6"),
         "component": [{"code": cc((LOINC, "33728-7", "Size.maximum dimension in Tumor")), "valueQuantity": qty(0.5, "cm", "cm")}]},
        "C6 pial nodule, 5 mm on MRI.")
    add({"resourceType": "DiagnosticReport", "id": f"{P}-spine-mri", "meta": {"profile": [USC + "us-core-diagnosticreport-note"]},
         "status": "final", "category": [cc((LOINC, "LP29684-5", "Radiology"))],
         "code": cc((LOINC, "30855-1", "MR Cervical and thoracic and lumbar spine WO and W contrast IV")), "subject": ref(PT),
         "effectiveDateTime": "2026-10-17", "issued": "2026-10-17T15:00:00Z", "performer": [ref(IMAGING)],
         "result": [ref(f"Observation/{P}-c6-nodule-size")],
         "conclusion": "Cervical spinal cord of normal caliber. A discrete lobulated 5 mm nodule along the "
                       "posterior pial surface of the cord at C6, with intense uniform post-contrast enhancement."},
        "Spine MRI, 2026-10-17: C6 pial nodule, 5 mm, intensely enhancing; cord otherwise normal caliber.")

    # ---- stereotactic biopsy: no SNOMED concept names "stereotactic" specifically (see module docstring),
    # so the nearest real code carries the stereotactic/image-guided detail as free text, not as a coding.
    add({"resourceType": "Procedure", "id": f"{P}-biopsy", "meta": {"profile": [USC + "us-core-procedure"]},
         "status": "completed",
         "code": cc((SCT, "287511004", "Non-surgical biopsy of brain"), text="Stereotactic biopsy, left frontal lobe mass"),
         "subject": ref(PT), "performedDateTime": "2026-10-19", "bodySite": [cc(text="Left frontal lobe")],
         "note": [{"text": "Image-guided (stereotactic) needle biopsy of the left frontal mass."}]},
        "Stereotactic biopsy, left frontal lobe mass, 2026-10-19.")
    add({"resourceType": "Specimen", "id": f"{P}-biopsy-specimen", "meta": {"profile": [MC + "mcode-human-specimen"]},
         "status": "available",
         "type": cc(("http://terminology.hl7.org/CodeSystem/v2-0487", "TISS", "Tissue"), text="Stereotactic brain biopsy"),
         "subject": ref(PT), "collection": {"collectedDateTime": "2026-10-19", "bodySite": cc(text="Left frontal lobe")}},
        "Stereotactic brain biopsy specimen.")

    # ---- primary + secondary Condition: deliberately "provisional", per the module docstring
    add({"resourceType": "Condition", "id": f"{P}-brain-mass", "meta": {"profile": [MC + "mcode-primary-cancer-condition"]},
         "clinicalStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active")),
         "verificationStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-ver-status", "provisional", "Provisional")),
         "category": [cc(("http://terminology.hl7.org/CodeSystem/condition-category", "problem-list-item", "Problem List Item"))],
         "code": cc((ICD10, "D43.0", "Neoplasm of uncertain behavior of brain, supratentorial"),
                    text="Intracranial mesenchymal tumor, left frontal lobe - entity and grade not established"),
         "subject": ref(PT), "recordedDate": "2026-10-19", "evidence": [{"detail": [ref(BIOPSY_PATH)]}]},
        "Left frontal mass: provisional, entity not established.")
    add({"resourceType": "Condition", "id": f"{P}-c6-nodule", "meta": {"profile": [MC + "mcode-primary-cancer-condition"]},
         "clinicalStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active")),
         "verificationStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-ver-status", "provisional", "Provisional")),
         "category": [cc(("http://terminology.hl7.org/CodeSystem/condition-category", "problem-list-item", "Problem List Item"))],
         "code": cc((ICD10, "D43.4", "Neoplasm of uncertain behavior of spinal cord"),
                    text="C6 pial nodule, suspicious for spinal drop metastasis - not biopsy-confirmed"),
         "subject": ref(PT), "recordedDate": "2026-10-19", "evidence": [{"detail": [ref(SPINE_MRI)]}]},
        "C6 nodule: provisional, imaging-suspected, not biopsy-confirmed.")

    # ---- pathology report: explicitly non-specific, matching the source handout verbatim
    add({"resourceType": "DiagnosticReport", "id": f"{P}-biopsy-pathology", "meta": {"profile": [USC + "us-core-diagnosticreport-lab"]},
         "status": "final", "category": [cc((V2_0074, "LAB", "Laboratory")), cc((V2_0074, "SP", "Surgical Pathology"))],
         "code": cc((LOINC, "60568-3", "Pathology synoptic report")), "subject": ref(PT),
         "effectiveDateTime": "2026-10-19", "issued": "2026-10-21T16:00:00Z", "performer": [ref(NEUROPATH)],
         "specimen": [ref(SPEC)],
         "conclusion": "Stereotactic biopsy, left frontal lobe mass: suggestive of an intracranial mesenchymal "
                       "tumor with spinal drop metastasis. The final histologic and molecular entity is not "
                       "established on the current material."},
        "Pathology: suggestive of an intracranial mesenchymal tumor with spinal drop metastasis; entity not established.")

    for oid, name in [("neuropathology-lab", "Synthetic Neuropathology Laboratory"),
                      ("neurosurgery", "Synthetic Neurosurgery Department"),
                      ("imaging", "Synthetic Neuroradiology Department")]:
        add({"resourceType": "Organization", "id": f"{P}-{oid}", "active": True, "name": name,
             "type": [cc(("http://terminology.hl7.org/CodeSystem/organization-type", "prov", "Healthcare Provider"))]},
            f"{name} (synthetic).")
    add({"resourceType": "Practitioner", "id": f"{P}-neurooncologist", "active": True,
         "identifier": [{"system": BASE + "/sid/practitioner", "value": f"{P.upper()}-MD"}],
         "name": [{"family": "Neurooncologist", "given": ["Synthetic"], "prefix": ["Dr."]}]},
        "Treating neuro-oncologist (synthetic).")

    return {"resourceType": "Bundle", "id": P, "meta": {"profile": [MC + "mcode-patient-bundle"], "security": [HTEST]},
            "identifier": {"system": BASE + "/sid/bundle", "value": P}, "type": "collection",
            "timestamp": "2026-10-21T16:00:00Z",
            "entry": [{"fullUrl": f"{BASE}/{r['resourceType']}/{r['id']}", "resource": r} for r in resources]}


def main() -> None:
    root = Path(__file__).resolve().parent.parent / "harbor_cases"
    out = root / "intracranial_mesenchymal_0001_fhir" / "environment" / "case" / "fhir_bundle.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    bundle = build()
    out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out.relative_to(root.parent)} ({len(bundle['entry'])} resources)")


if __name__ == "__main__":
    main()
