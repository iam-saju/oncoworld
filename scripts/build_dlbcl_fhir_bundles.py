#!/usr/bin/env python3
"""Build FHIR R4 / mCODE STU4 bundles for the DLBCL narrative cases 0001-0005.

Usage: python3 scripts/build_dlbcl_fhir_bundles.py   (run from the repo root)

Each bundle carries exactly the facts in that case's environment/case/*.txt files, no more:
- no stage, IPI, double-hit label or treatment (those are graded);
- LDH has no reference range, because "LDH upper limit of normal" is graded missing information;
- diagnosis ICD-10-CM codes use "unspecified site", so the code does not reveal extranodal spread.

Codes were checked against tx.fhir.org. IHC percentages for MYC, BCL2 and MUM1 have no LOINC code,
so they use a labelled local code system, the way labs report unmapped tests.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

BASE = "http://oncoworld.example/fhir"
LOCAL = BASE + "/CodeSystem/lab-local"
SCT, LOINC, UCUM = "http://snomed.info/sct", "http://loinc.org", "http://unitsofmeasure.org"
ICD10 = "http://hl7.org/fhir/sid/icd-10-cm"
MC = "http://hl7.org/fhir/us/mcode/StructureDefinition/"
USC = "http://hl7.org/fhir/us/core/StructureDefinition/"
OBS_CAT = "http://terminology.hl7.org/CodeSystem/observation-category"
V2_0074 = "http://terminology.hl7.org/CodeSystem/v2-0074"
HTEST = {"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "HTEST", "display": "test health data"}

POS, NEG = (SCT, "10828004", "Positive"), (SCT, "260385009", "Negative")
DET, NOT_DET = (SCT, "260373001", "Detected"), (SCT, "260415000", "Not detected")

CASES = {
    "dlbcl_0001": {
        "patient": ("Male", "male", "1964-05-11", "Sample", "Thomas"),
        "ecog": 1,
        "symptoms": [("30746006", "Lymphadenopathy", "Rapidly progressive cervical and abdominal lymphadenopathy."),
                     ("386661006", "Fever", None), ("42984000", "Night sweats", None),
                     ("262285001", "Weight decreased", "7-kg weight loss over 3 months.")],
        "labs": {"hb": 10.8, "wbc": 7.8, "plt": 210, "ldh": 680},
        "pet": ["FDG-avid cervical nodes.",
                "Mediastinal lymphadenopathy.",
                "Bulky retroperitoneal lymphadenopathy, maximum diameter 11 cm.",
                "FDG-avid splenic lesions.",
                "No CNS lesions."],
        "largest_mass_cm": 11,
        "biopsy": ("Lymph-node biopsy", "21911005", "Biopsy of lymph node", "309079007", "Lymph node biopsy specimen",
                   "59441001", "Structure of lymph node"),
        "diagnosis": "dlbcl", "path_text": "Diffuse large B-cell lymphoma.",
        "ihc": {"CD20": True, "CD10": False, "BCL6": True, "MUM1": True, "BCL2": 80, "MYC": 50, "KI67": 85},
        "fish": {"MYC": False, "BCL2": False, "BCL6": False},
    },
    "dlbcl_0002_splenic_stage_iii": {
        "patient": ("Female", "female", "1967-03-08", "Sample", "Grace"),
        "ecog": 1,
        "symptoms": [("84229001", "Fatigue", None),
                     ("386661006", "Fever", "Intermittent fevers."),
                     ("30746006", "Lymphadenopathy", "Enlarging left axillary and abdominal lymph nodes.")],
        "labs": {"hb": 11.4, "wbc": 6.9, "plt": 178, "ldh": 510},
        "pet": ["FDG-avid left axillary and mediastinal lymphadenopathy.",
                "FDG-avid mesenteric and para-aortic lymphadenopathy.",
                "FDG-avid splenic nodules.",
                "Largest nodal mass: 7.5 cm.",
                "No kidney, adrenal, testicular, breast, bone, liver, lung, marrow, or CNS lesions."],
        "largest_mass_cm": 7.5,
        "biopsy": ("Lymph-node biopsy", "21911005", "Biopsy of lymph node", "309079007", "Lymph node biopsy specimen",
                   "59441001", "Structure of lymph node"),
        "diagnosis": "dlbcl", "path_text": "Diffuse large B-cell lymphoma.",
        "ihc": {"CD20": True, "CD10": False, "BCL6": True, "MUM1": True, "BCL2": 70, "MYC": 45, "KI67": 80},
        "fish": {"MYC": False, "BCL2": False, "BCL6": False},
    },
    "dlbcl_0003_renal_adrenal_cns_high": {
        "patient": ("Male", "male", "1959-06-21", "Sample", "Robert"),
        "ecog": 2,
        "symptoms": [("21522001", "Abdominal pain", None), ("442076002", "Early satiety", None),
                     ("42984000", "Night sweats", None), ("262285001", "Weight decreased", None)],
        "labs": {"hb": 9.9, "wbc": 9.4, "plt": 145, "ldh": 1120, "creatinine": 1.4},
        "pet": ["FDG-avid retroperitoneal and mesenteric lymphadenopathy.",
                "FDG-avid right renal cortical lesion, 3.2 cm.",
                "FDG-avid left adrenal mass, 2.6 cm.",
                "FDG-avid liver lesion, 1.8 cm.",
                "No testicular, breast, or CNS lesions."],
        "largest_mass_cm": None,
        "biopsy": ("Core biopsy of retroperitoneal mass", "9911007", "Core needle biopsy", "119376003", "Tissue specimen",
                   "82849001", "Retroperitoneal compartment structure"),
        "diagnosis": "dlbcl", "path_text": "Diffuse large B-cell lymphoma.",
        "ihc": {"CD20": True, "CD10": True, "BCL6": True, "MUM1": False, "BCL2": 30, "MYC": 20, "KI67": 70},
        "fish": {"MYC": False, "BCL2": False, "BCL6": False},
    },
    "dlbcl_0004_double_hit": {
        "patient": ("Male", "male", "1972-01-30", "Sample", "Daniel"),
        "ecog": 1,
        "symptoms": [("30746006", "Lymphadenopathy", "Rapidly enlarging right cervical and mediastinal lymphadenopathy."),
                     ("40739000", "Dysphagia", None)],
        "labs": {"hb": 12.6, "wbc": 8.1, "plt": 225, "ldh": 740},
        "pet": ["FDG-avid right cervical lymphadenopathy.",
                "FDG-avid mediastinal lymphadenopathy.",
                "Bulky mediastinal mass, maximum diameter 12 cm.",
                "No disease below the diaphragm.",
                "No kidney, adrenal, testicular, breast, marrow, or CNS lesions."],
        "largest_mass_cm": 12,
        "biopsy": ("Lymph-node biopsy", "21911005", "Biopsy of lymph node", "309079007", "Lymph node biopsy specimen",
                   "59441001", "Structure of lymph node"),
        "diagnosis": "lbcl_high_grade", "path_text": "Large B-cell lymphoma with high-grade morphology.",
        "ihc": {"CD20": True, "CD10": True, "BCL6": True, "MUM1": False, "BCL2": 90, "MYC": 80, "KI67": 95},
        "fish": {"MYC": True, "BCL2": True, "BCL6": False},
    },
    "dlbcl_0005_limited_stage_gcb": {
        "patient": ("Female", "female", "1981-02-19", "Sample", "Laura"),
        "ecog": 0,
        "symptoms": [("30746006", "Lymphadenopathy", "Painless enlarging right cervical lymph node found on self-exam."),
                     # documented absence of B symptoms: FHIR records this as a refuted Condition
                     ("386661006", "Fever", "No fever.", "refuted"),
                     ("42984000", "Night sweats", "No night sweats.", "refuted"),
                     ("262285001", "Weight decreased", "No weight loss.", "refuted")],
        "labs": {"hb": 13.2, "wbc": 5.9, "plt": 240, "ldh": 190},
        "ldh_interpretation": "N",
        "pet": ["Single FDG-avid right cervical lymph-node region, maximum diameter 3.1 cm.",
                "No mediastinal, abdominal, splenic, marrow, kidney, adrenal, testicular/breast, or CNS lesions."],
        "largest_mass_cm": 3.1,
        "biopsy": ("Lymph-node biopsy", "21911005", "Biopsy of lymph node", "309079007", "Lymph node biopsy specimen",
                   "59441001", "Structure of lymph node"),
        "diagnosis": "dlbcl", "path_text": "Diffuse large B-cell lymphoma.",
        "ihc": {"CD20": True, "CD10": True, "BCL6": True, "MUM1": False, "BCL2": 30, "MYC": 15, "KI67": 55},
        "fish": {"MYC": False, "BCL2": False, "BCL6": False},
    },
}

DIAGNOSES = {
    # Condition.code, ICD-10-CM, morphology extension. Case 0004 deliberately stays at "B-cell lymphoma":
    # its pathology names only high-grade morphology; the double-hit diagnosis must come from FISH.
    "dlbcl": ((SCT, "109969005", "Diffuse large B-cell lymphoma"),
              (ICD10, "C83.30", "Diffuse large B-cell lymphoma, unspecified site"),
              (SCT, "1172695008", "Diffuse large B cell malignant lymphoma (morphologic abnormality)"),
              "Diffuse large B-cell lymphoma"),
    "lbcl_high_grade": ((SCT, "109979007", "B-cell lymphoma (disorder)"),
                        (ICD10, "C85.10", "Unspecified B-cell lymphoma, unspecified site"),
                        (SCT, "314925008", "High grade B-cell lymphoma morphology (morphologic abnormality)"),
                        "Large B-cell lymphoma with high-grade morphology"),
}

IHC_CODES = {
    "CD20": ("presence", (LOINC, "10438-0", "CD20 Ag [Presence] in Tissue by Immune stain")),
    "CD10": ("presence", (LOINC, "40551-4", "CD10 Ag [Presence] in Tissue by Immune stain")),
    "BCL6": ("presence", (LOINC, "47009-6", "BCL6 Ag [Presence] in Tissue by Immune stain")),
    "MUM1": ("presence", (LOCAL, "MUM1-IHC", "MUM1/IRF4 Ag [Presence] in Tissue by Immune stain")),
    "BCL2": ("percent", (LOCAL, "BCL2-IHC-PCT", "BCL2 Ag positive tumor cells/cells in Tissue by Immune stain")),
    "MYC": ("percent", (LOCAL, "MYC-IHC-PCT", "c-MYC Ag positive tumor cells/cells in Tissue by Immune stain")),
    "KI67": ("percent", (LOINC, "29593-1", "Cells.Ki-67 nuclear Ag/cells in Tissue by Immune stain")),
}
FISH_CODES = {
    "MYC": (LOINC, "78215-1", "MYC gene rearrangements [Presence] in Blood or Tissue by FISH"),
    "BCL2": (LOINC, "78218-5", "BCL2 gene rearrangements [Presence] in Blood or Tissue by FISH"),
    "BCL6": (LOINC, "78203-7", "BCL6 gene rearrangements [Presence] in Blood or Tissue by FISH"),
}


def cc(*codings, text=None):
    out = {"coding": [{"system": s, "code": c, "display": d} for s, c, d in codings]}
    if text:
        out["text"] = text
    return out


def ref(r):
    return {"reference": r}


def qty(value, unit, code):
    return {"value": value, "unit": unit, "system": UCUM, "code": code}


def build(key: str, case: dict) -> dict:
    p = f"dlbcl-{key.split('_')[1]}"
    PT = f"Patient/{p}-patient"
    CANCER = f"Condition/{p}-primary-cancer"
    SPEC, BM_SPEC = f"Specimen/{p}-biopsy-specimen", f"Specimen/{p}-marrow-specimen"
    PATH_LAB, CLIN_LAB, IMAGING = (f"Organization/{p}-{x}" for x in ("pathology-lab", "clinical-lab", "imaging"))
    ONC = f"Practitioner/{p}-hematologist"
    resources: list[dict] = []

    def add(res, summary):
        res["text"] = {"status": "generated",
                       "div": f'<div xmlns="http://www.w3.org/1999/xhtml"><p>{escape(summary)}</p></div>'}
        resources.append(res)

    sex_word, gender, birth, family, given = case["patient"]
    add({"resourceType": "Patient", "id": f"{p}-patient",
         "meta": {"profile": [MC + "mcode-cancer-patient"], "security": [HTEST]},
         "extension": [{"url": USC + "us-core-birthsex", "valueCode": "F" if gender == "female" else "M"}],
         "identifier": [{"use": "usual", "type": cc(("http://terminology.hl7.org/CodeSystem/v2-0203", "MR", "Medical record number")),
                         "system": BASE + "/sid/mrn", "value": p.upper()}],
         "name": [{"use": "official", "family": family, "given": [given]}],
         "gender": gender, "birthDate": birth},
        f"Synthetic patient {given} {family}, {gender}, born {birth}. Test data, not a real person.")

    for i, (code, display, note, *flag) in enumerate(case["symptoms"], 1):
        refuted = flag == ["refuted"]
        res = {"resourceType": "Condition", "id": f"{p}-symptom-{i}",
               "meta": {"profile": [USC + "us-core-condition-problems-health-concerns"]},
               "verificationStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-ver-status",
                                         *(("refuted", "Refuted") if refuted else ("confirmed", "Confirmed")))),
               "category": [cc(("http://terminology.hl7.org/CodeSystem/condition-category", "problem-list-item", "Problem List Item"))],
               "code": cc((SCT, code, display)), "subject": ref(PT), "recordedDate": "2026-09-02"}
        if not refuted:  # clinicalStatus must be absent when verificationStatus is refuted (FHIR con-5)
            res["clinicalStatus"] = cc(("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active"))
        if note:
            res["note"] = [{"text": note}]
        add(res, f"Symptom documented as absent: {display}." if refuted
            else f"Presenting symptom: {display}." + (f" {note}" if note else ""))

    add({"resourceType": "Observation", "id": f"{p}-ecog", "meta": {"profile": [MC + "mcode-ecog-performance-status"]},
         "status": "final", "category": [cc((OBS_CAT, "survey", "Survey"))],
         "code": cc((LOINC, "89247-1", "ECOG Performance Status score")), "subject": ref(PT),
         "effectiveDateTime": "2026-09-02", "performer": [ref(ONC)], "valueInteger": case["ecog"],
         "interpretation": [cc({0: (LOINC, "LA9622-7", "Fully active, able to carry on all pre-disease performance without restriction"),
                                1: (LOINC, "LA9623-5", "Restricted in physically strenuous activity but ambulatory and able to carry out work of a light or sedentary nature, e.g., light house work, office work"),
                                2: (LOINC, "LA9624-3", "Ambulatory and capable of all selfcare but unable to carry out any work activities. Up and about more than 50% of waking hours")}[case["ecog"]])]},
        f"ECOG performance status {case['ecog']}.")

    # ---- labs
    lab_defs = [("hb", "718-7", "Hemoglobin [Mass/volume] in Blood", "g/dL", "g/dL", "cbc"),
                ("wbc", "6690-2", "Leukocytes [#/volume] in Blood by Automated count", "10*3/uL", "10*3/uL", "cbc"),
                ("plt", "777-3", "Platelets [#/volume] in Blood by Automated count", "10*3/uL", "10*3/uL", "cbc"),
                ("ldh", "14804-9", "Lactate dehydrogenase [Enzymatic activity/volume] in Serum or Plasma by Lactate to pyruvate reaction", "U/L", "U/L", "chem"),
                ("creatinine", "2160-0", "Creatinine [Mass/volume] in Serum or Plasma", "mg/dL", "mg/dL", "chem")]
    panels = {"cbc": [], "chem": []}
    for k, code, disp, unit, ucode, panel in lab_defs:
        if k not in case["labs"]:
            continue
        rid = f"{p}-lab-{k}"
        res = {"resourceType": "Observation", "id": rid, "meta": {"profile": [USC + "us-core-observation-lab"]},
               "status": "final", "category": [cc((OBS_CAT, "laboratory", "Laboratory"))],
               "code": cc((LOINC, code, disp)), "subject": ref(PT), "effectiveDateTime": "2026-09-03T08:00:00Z",
               "performer": [ref(CLIN_LAB)], "valueQuantity": qty(case["labs"][k], unit, ucode)}
        flag = case.get("ldh_interpretation", "H")
        if k == "ldh":  # narrative says "elevated" (or "within normal range") and gives no reference range
            res["interpretation"] = [cc(("http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                                         flag, {"H": "High", "N": "Normal"}[flag]))]
        add(res, f"{disp.split(' [')[0]}: {case['labs'][k]} {unit}"
            + ({"H": " (high).", "N": " (normal)."}[flag] if k == "ldh" else "."))
        panels[panel].append(ref("Observation/" + rid))
    for panel, code, disp in [("cbc", "58410-2", "CBC panel - Blood by Automated count"),
                              ("chem", "24323-8", "Comprehensive metabolic 2000 panel - Serum or Plasma")]:
        if panels[panel]:
            add({"resourceType": "DiagnosticReport", "id": f"{p}-{panel}", "meta": {"profile": [USC + "us-core-diagnosticreport-lab"]},
                 "status": "final", "category": [cc((V2_0074, "LAB", "Laboratory"))], "code": cc((LOINC, code, disp)),
                 "subject": ref(PT), "effectiveDateTime": "2026-09-03T08:00:00Z", "issued": "2026-09-03T12:00:00Z",
                 "performer": [ref(CLIN_LAB)], "result": panels[panel]}, f"{disp}, 2026-09-03.")

    # ---- imaging
    pet_results = []
    if case["largest_mass_cm"]:
        # Plain Observation: mcode-tumor-size needs a tumor BodyStructure or specimen, and this is an imaging measurement.
        add({"resourceType": "Observation", "id": f"{p}-largest-mass",
             "status": "final", "category": [cc((OBS_CAT, "imaging", "Imaging"))], "code": cc((LOINC, "21889-1", "Size Tumor")),
             "subject": ref(PT), "effectiveDateTime": "2026-09-05", "performer": [ref(IMAGING)],
             "method": cc((SCT, "82918005", "Positron emission tomography (procedure)")),
             "component": [{"code": cc((LOINC, "33728-7", "Size.maximum dimension in Tumor")),
                            "valueQuantity": qty(case["largest_mass_cm"], "cm", "cm")}]},
            f"Largest nodal mass on PET-CT: {case['largest_mass_cm']} cm.")
        pet_results.append(ref(f"Observation/{p}-largest-mass"))
    pet = {"resourceType": "DiagnosticReport", "id": f"{p}-pet-ct", "meta": {"profile": [USC + "us-core-diagnosticreport-note"]},
           "status": "final", "category": [cc((LOINC, "LP29684-5", "Radiology"))],
           "code": cc((LOINC, "81554-8", "PET+CT Guidance for localization of tumor of Skull base to mid-thigh-- W 18F-FDG IV")),
           "subject": ref(PT), "effectiveDateTime": "2026-09-05", "issued": "2026-09-05T16:00:00Z", "performer": [ref(IMAGING)],
           "conclusion": " ".join(case["pet"])}
    if pet_results:
        pet["result"] = pet_results
    add(pet, "FDG PET-CT 2026-09-05: " + " ".join(case["pet"]))

    # ---- biopsy, specimens
    label, proc_code, proc_disp, spec_code, spec_disp, site_code, site_disp = case["biopsy"]
    add({"resourceType": "Procedure", "id": f"{p}-biopsy", "meta": {"profile": [USC + "us-core-procedure"]},
         "status": "completed", "code": cc((SCT, proc_code, proc_disp), text=label), "subject": ref(PT),
         "performedDateTime": "2026-09-08", "bodySite": [cc((SCT, site_code, site_disp))]}, f"{label}, 2026-09-08.")
    add({"resourceType": "Procedure", "id": f"{p}-marrow-biopsy", "meta": {"profile": [USC + "us-core-procedure"]},
         "status": "completed", "code": cc((SCT, "56241004", "Bone marrow biopsy, needle or trocar")), "subject": ref(PT),
         "performedDateTime": "2026-09-10"}, "Bone marrow biopsy, 2026-09-10.")
    TISS = ("http://terminology.hl7.org/CodeSystem/v2-0487", "TISS", "Tissue")
    add({"resourceType": "Specimen", "id": f"{p}-biopsy-specimen", "meta": {"profile": [MC + "mcode-human-specimen"]},
         "status": "available", "type": cc(TISS, (SCT, spec_code, spec_disp)), "subject": ref(PT),
         "collection": {"collectedDateTime": "2026-09-08", "bodySite": cc((SCT, site_code, site_disp))}}, f"{label} specimen.")
    add({"resourceType": "Specimen", "id": f"{p}-marrow-specimen", "meta": {"profile": [MC + "mcode-human-specimen"]},
         "status": "available", "type": cc(("http://terminology.hl7.org/CodeSystem/v2-0487", "BON", "Bone"),
                                           (SCT, "119359002", "Bone marrow specimen")),
         "subject": ref(PT), "collection": {"collectedDateTime": "2026-09-10"}}, "Bone marrow specimen.")

    # ---- primary cancer condition (diagnosis as reported by pathology, nothing more)
    dx_code, dx_icd, morph, dx_text = DIAGNOSES[case["diagnosis"]]
    add({"resourceType": "Condition", "id": f"{p}-primary-cancer", "meta": {"profile": [MC + "mcode-primary-cancer-condition"]},
         "extension": [{"url": MC + "mcode-histology-morphology-behavior", "valueCodeableConcept": cc(morph)}],
         "clinicalStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active")),
         "verificationStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "Confirmed")),
         "category": [cc(("http://terminology.hl7.org/CodeSystem/condition-category", "problem-list-item", "Problem List Item"))],
         "code": cc(dx_code, dx_icd, text=dx_text), "subject": ref(PT), "recordedDate": "2026-09-12",
         "evidence": [{"detail": [ref(f"DiagnosticReport/{p}-lymphoma-pathology")]}]},
        f"Primary cancer: {dx_text}.")

    # ---- IHC and FISH
    path_results = []
    TMT = MC + "mcode-tumor-marker-test"
    REL = [{"url": MC + "mcode-related-condition", "valueReference": ref(CANCER)}]
    summary_bits = []
    for marker, (kind, code) in IHC_CODES.items():
        v = case["ihc"][marker]
        rid = f"{p}-ihc-{marker.lower()}"
        value = ({"valueCodeableConcept": cc(POS if v else NEG)} if kind == "presence"
                 else {"valueQuantity": qty(v, "%", "%")})
        add({"resourceType": "Observation", "id": rid, "meta": {"profile": [TMT]}, "extension": REL, "status": "final",
             "category": [cc((OBS_CAT, "laboratory", "Laboratory"))], "code": cc(code), "subject": ref(PT),
             "effectiveDateTime": "2026-09-12", "performer": [ref(PATH_LAB)], **value, "specimen": ref(SPEC)},
            f"IHC {marker}: " + (("positive" if v else "negative") if kind == "presence" else f"{v}%") + ".")
        path_results.append(ref("Observation/" + rid))
        name = "Ki-67" if marker == "KI67" else marker
        summary_bits.append(f"{name}{'+' if v is True else '-' if v is False else ' ' + str(v) + '%'}")
    fish_bits = []
    for gene, code in FISH_CODES.items():
        v = case["fish"][gene]
        rid = f"{p}-fish-{gene.lower()}"
        add({"resourceType": "Observation", "id": rid, "meta": {"profile": [TMT]}, "extension": REL, "status": "final",
             "category": [cc((OBS_CAT, "laboratory", "Laboratory"))], "code": cc(code), "subject": ref(PT),
             "effectiveDateTime": "2026-09-12", "performer": [ref(PATH_LAB)],
             "valueCodeableConcept": cc(DET if v else NOT_DET), "specimen": ref(SPEC)},
            f"FISH {gene} rearrangement: {'detected' if v else 'not detected'}.")
        path_results.append(ref("Observation/" + rid))
        fish_bits.append(f"{gene} rearrangement {'detected' if v else 'not detected'}")

    add({"resourceType": "DiagnosticReport", "id": f"{p}-lymphoma-pathology", "meta": {"profile": [USC + "us-core-diagnosticreport-lab"]},
         "status": "final", "category": [cc((V2_0074, "LAB", "Laboratory")), cc((V2_0074, "SP", "Surgical Pathology"))],
         "code": cc((LOINC, "60568-3", "Pathology synoptic report")), "subject": ref(PT),
         "effectiveDateTime": "2026-09-12", "issued": "2026-09-12T17:00:00Z", "performer": [ref(PATH_LAB)],
         "specimen": [ref(SPEC)], "result": path_results,
         "conclusion": f"{label}: {case['path_text']} IHC: {', '.join(summary_bits)}. FISH: {'; '.join(fish_bits)}.",
         "conclusionCode": [cc(dx_code)]},
        f"{label}: {case['path_text']}")
    add({"resourceType": "DiagnosticReport", "id": f"{p}-marrow-pathology", "meta": {"profile": [USC + "us-core-diagnosticreport-lab"]},
         "status": "final", "category": [cc((V2_0074, "LAB", "Laboratory")), cc((V2_0074, "SP", "Surgical Pathology"))],
         "code": cc((LOINC, "33721-2", "Bone marrow Pathology biopsy report")), "subject": ref(PT),
         "effectiveDateTime": "2026-09-10", "issued": "2026-09-13T12:00:00Z", "performer": [ref(PATH_LAB)],
         "specimen": [ref(BM_SPEC)], "conclusion": "Bone marrow: no lymphoma involvement."},
        "Bone marrow biopsy: no lymphoma involvement.")

    for oid, name in [("pathology-lab", "Synthetic Hematopathology Laboratory"),
                      ("clinical-lab", "Synthetic Clinical Laboratory"), ("imaging", "Synthetic Nuclear Medicine Department")]:
        add({"resourceType": "Organization", "id": f"{p}-{oid}", "active": True, "name": name,
             "type": [cc(("http://terminology.hl7.org/CodeSystem/organization-type", "prov", "Healthcare Provider"))]},
            f"{name} (synthetic).")
    add({"resourceType": "Practitioner", "id": f"{p}-hematologist", "active": True,
         "identifier": [{"system": BASE + "/sid/practitioner", "value": f"{p.upper()}-MD"}],
         "name": [{"family": "Hematologist", "given": ["Synthetic"], "prefix": ["Dr."]}]},
        "Treating hematologist-oncologist (synthetic).")

    return {"resourceType": "Bundle", "id": p, "meta": {"profile": [MC + "mcode-patient-bundle"], "security": [HTEST]},
            "identifier": {"system": BASE + "/sid/bundle", "value": p}, "type": "collection",
            "timestamp": "2026-09-15T12:00:00Z",
            "entry": [{"fullUrl": f"{BASE}/{r['resourceType']}/{r['id']}", "resource": r} for r in resources]}


def main() -> None:
    root = Path(__file__).resolve().parent.parent / "harbor_cases"
    for key, case in CASES.items():
        out = root / f"{key}_fhir" / "environment" / "case" / "fhir_bundle.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        bundle = build(key, case)
        out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {out.relative_to(root.parent)} ({len(bundle['entry'])} resources)")


if __name__ == "__main__":
    main()
