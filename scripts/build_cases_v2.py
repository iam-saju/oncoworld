#!/usr/bin/env python3
"""Build OncoWorld v2 Harbor tasks from cases_src/<case>/.

Usage: python3 scripts/build_cases_v2.py [case_id ...]      (run from the repo root; default: every case)

One source per patient, two renderings:
  cases_src/<case>/case.toml      MODEL-VISIBLE facts and chart documents
  cases_src/<case>/gold.json      HIDDEN reference answer
  cases_src/<case>/rubric_v2.toml HIDDEN atomic rubric (graders/oncoworld_grader/grader_v2.py)
  cases_src/<case>/selftest/      HIDDEN grader self-test answers (answers/) and probe sentences (probes.json)

produce harbor_cases/<case>_<slug>_v2_fhir/ (the benchmark: only FHIR tasks are run) and
harbor_cases_narrative/<case>_<slug>_v2_narrative/ (diagnostic only). The narrative chart (chart/*.txt) and the FHIR bundle
are generated from the same case.toml, so values, reference ranges and flags cannot disagree between formats.

Checks that fail the build:
  - a rubric leak_check term appears in any model-visible file
  - a structured pathology value is missing from the pathology report text
  - the gold answer does not meet every must/should item, or trips a must_not item, under the regex rules
v1 tasks and scripts/build_dlbcl_fhir_bundles.py are frozen and untouched; FHIR helpers are imported from there.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import sys
import tomllib
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "graders" / "oncoworld_grader"))
from build_dlbcl_fhir_bundles import (  # noqa: E402
    BASE, DET, DIAGNOSES, FISH_CODES, HTEST, ICD10, IHC_CODES, LOINC, MC, NEG, NOT_DET, OBS_CAT, POS, SCT, USC,
    V2_0074, cc, qty, ref,
)
from grader_v2 import score  # noqa: E402

GRADER_DIR = ROOT / "graders" / "oncoworld_grader"
INTERP = "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"

# key: (LOINC, LOINC long name, short label, unit, UCUM, low, high). low/high may be {"male": .., "female": ..}.
# Qualitative tests have unit None and are reported as Reactive / Nonreactive.
LABS = {
    "hb": ("718-7", "Hemoglobin [Mass/volume] in Blood", "Hemoglobin", "g/dL", "g/dL", {"male": 13.5, "female": 12.0}, {"male": 17.5, "female": 15.5}),
    "mcv": ("787-2", "MCV [Entitic volume] by Automated count", "MCV", "fL", "fL", 80, 100),
    "wbc": ("6690-2", "Leukocytes [#/volume] in Blood by Automated count", "WBC", "x10^3/uL", "10*3/uL", 4.0, 11.0),
    "anc": ("751-8", "Neutrophils [#/volume] in Blood by Automated count", "Absolute neutrophils", "x10^3/uL", "10*3/uL", 1.8, 7.7),
    "alc": ("731-0", "Lymphocytes [#/volume] in Blood by Automated count", "Absolute lymphocytes", "x10^3/uL", "10*3/uL", 1.0, 4.8),
    "plt": ("777-3", "Platelets [#/volume] in Blood by Automated count", "Platelets", "x10^3/uL", "10*3/uL", 150, 400),
    "na": ("2951-2", "Sodium [Moles/volume] in Serum or Plasma", "Sodium", "mmol/L", "mmol/L", 135, 145),
    "k": ("2823-3", "Potassium [Moles/volume] in Serum or Plasma", "Potassium", "mmol/L", "mmol/L", 3.5, 5.1),
    "cl": ("2075-0", "Chloride [Moles/volume] in Serum or Plasma", "Chloride", "mmol/L", "mmol/L", 98, 107),
    "co2": ("2028-9", "Carbon dioxide, total [Moles/volume] in Serum or Plasma", "CO2, total", "mmol/L", "mmol/L", 22, 29),
    "bun": ("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma", "BUN", "mg/dL", "mg/dL", 7, 20),
    "creatinine": ("2160-0", "Creatinine [Mass/volume] in Serum or Plasma", "Creatinine", "mg/dL", "mg/dL", {"male": 0.7, "female": 0.5}, {"male": 1.3, "female": 1.1}),
    "egfr": ("98979-8", "Glomerular filtration rate/1.73 sq M.predicted [Volume Rate/Area] in Serum, Plasma or Blood by Creatinine-based formula (CKD-EPI 2021)",
             "eGFR (CKD-EPI 2021)", "mL/min/1.73m2", "mL/min/{1.73_m2}", 60, None),
    "glucose": ("2345-7", "Glucose [Mass/volume] in Serum or Plasma", "Glucose", "mg/dL", "mg/dL", 70, 99),
    "ca": ("17861-6", "Calcium [Mass/volume] in Serum or Plasma", "Calcium", "mg/dL", "mg/dL", 8.6, 10.3),
    "albumin": ("1751-7", "Albumin [Mass/volume] in Serum or Plasma", "Albumin", "g/dL", "g/dL", 3.5, 5.0),
    "protein": ("2885-2", "Protein [Mass/volume] in Serum or Plasma", "Total protein", "g/dL", "g/dL", 6.0, 8.3),
    "ast": ("1920-8", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma", "AST", "U/L", "U/L", 10, 40),
    "alt": ("1742-6", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma", "ALT", "U/L", "U/L", 7, 56),
    "alp": ("6768-6", "Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma", "Alkaline phosphatase", "U/L", "U/L", 40, 129),
    "tbili": ("1975-2", "Bilirubin.total [Mass/volume] in Serum or Plasma", "Bilirubin, total", "mg/dL", "mg/dL", 0.2, 1.2),
    "urate": ("3084-1", "Urate [Mass/volume] in Serum or Plasma", "Uric acid", "mg/dL", "mg/dL", 3.4, 7.0),
    "phos": ("2777-1", "Phosphate [Mass/volume] in Serum or Plasma", "Phosphorus", "mg/dL", "mg/dL", 2.5, 4.5),
    "ldh": ("14804-9", "Lactate dehydrogenase [Enzymatic activity/volume] in Serum or Plasma by Lactate to pyruvate reaction", "LDH", "U/L", "U/L", 135, 225),
    "b2m": ("1952-1", "Beta-2-Microglobulin [Mass/volume] in Serum or Plasma", "Beta-2 microglobulin", "mg/L", "mg/L", 0.8, 2.2),
    "hba1c": ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood", "Hemoglobin A1c", "%", "%", 4.0, 5.6),
    "hbsag": ("5196-1", "Hepatitis B virus surface Ag [Presence] in Serum or Plasma by Immunoassay", "Hepatitis B surface antigen", None, None, None, None),
    "anti_hbc": ("16933-4", "Hepatitis B virus core Ab [Presence] in Serum", "Hepatitis B core antibody, total", None, None, None, None),
    "anti_hbs": ("22322-2", "Hepatitis B virus surface Ab [Presence] in Serum", "Hepatitis B surface antibody", None, None, None, None),
    "hcv_ab": ("13955-0", "Hepatitis C virus Ab [Presence] in Serum or Plasma by Immunoassay", "Hepatitis C antibody", None, None, None, None),
    "hiv_agab": ("56888-1", "HIV 1+2 Ab+HIV1 p24 Ag [Presence] in Serum or Plasma by Immunoassay", "HIV-1/2 Ag/Ab screen", None, None, None, None),
    "hcg_urine": ("2106-3", "Choriogonadotropin (pregnancy test) [Presence] in Urine", "Urine hCG (pregnancy test)", None, None, None, None),
    "hbv_dna": ("29615-2", "Hepatitis B virus DNA [#/volume] (viral load) in Serum or Plasma by NAA with probe detection", "HBV DNA, quantitative", "IU/mL", "[IU]/mL", None, None),
    # used by the longitudinal journey (post-CAR-T admission labs)
    "crp": ("1988-5", "C reactive protein [Mass/volume] in Serum or Plasma", "C-reactive protein", "mg/L", "mg/L", None, 5),
    "ferritin": ("2276-4", "Ferritin [Mass/volume] in Serum or Plasma", "Ferritin", "ng/mL", "ng/mL", 30, 400),
    "inr": ("6301-6", "INR in Platelet poor plasma by Coagulation assay", "INR", "INR", "{INR}", 0.8, 1.2),
    "fibrinogen": ("3255-7", "Fibrinogen [Mass/volume] in Platelet poor plasma by Coagulation assay", "Fibrinogen", "mg/dL", "mg/dL", 200, 400),
    "lactate": ("2524-7", "Lactate [Moles/volume] in Serum or Plasma", "Lactate", "mmol/L", "mmol/L", 0.5, 2.0),
}
QUAL = {"Reactive": (SCT, "11214006", "Reactive"), "Nonreactive": (SCT, "131194007", "Non-Reactive"),
        "Positive": POS, "Negative": NEG, "Not detected": NOT_DET, "Detected": DET}

DOC_TYPES = {  # kind: (FHIR resource, code, file label)
    "referral_note": ("DocumentReference", (LOINC, "57133-1", "Referral note"), "referral"),
    "consult_note": ("DocumentReference", (LOINC, "11488-4", "Consult note"), "consult"),
    "progress_note": ("DocumentReference", (LOINC, "11506-3", "Progress note"), "progress_note"),
    "pet_ct_report": ("DiagnosticReport", (LOINC, "81554-8", "PET+CT Guidance for localization of tumor of Skull base to mid-thigh-- W 18F-FDG IV"), "pet_ct"),
    "ct_report": ("DiagnosticReport", None, "ct"),
    "mri_report": ("DiagnosticReport", None, "mri"),
    "echo_report": ("DiagnosticReport", None, "echocardiogram"),
    "pathology_report": ("DiagnosticReport", (LOINC, "60568-3", "Pathology synoptic report"), "pathology"),
    "marrow_report": ("DiagnosticReport", (LOINC, "33721-2", "Bone marrow Pathology biopsy report"), "bone_marrow"),
    "csf_report": ("DiagnosticReport", None, "csf"),
    # longitudinal journey documents
    "interval_history": ("DocumentReference", (LOINC, "34133-9", "Summary of episode note"), "interval_history"),
    "admission_note": ("DocumentReference", (LOINC, "34117-2", "History and physical note"), "admission_note"),
    "ngs_report": ("DiagnosticReport", (LOINC, "51969-4", "Genetic analysis report"), "ngs"),
}


# ---------------------------------------------------------------- shared rendering helpers
def rng(v, gender):
    return v.get(gender) if isinstance(v, dict) else v


def lab_flag(key, value, gender):
    _, _, _, unit, _, low, high = LABS[key]
    if unit is None or not isinstance(value, (int, float)):
        return ""
    low, high = rng(low, gender), rng(high, gender)
    if low is not None and value < low:
        return "L"
    if high is not None and value > high:
        return "H"
    return ""


def ref_text(key, gender):
    _, _, _, unit, _, low, high = LABS[key]
    if unit is None:
        return "Nonreactive" if key not in ("hcg_urine",) else "Negative"
    low, high = rng(low, gender), rng(high, gender)
    if low is not None and high is not None:
        return f"{low}-{high}"
    if low is not None:
        return f">={low}"
    if high is not None:
        return f"<={high}"
    return ""


def fmt(v):
    if isinstance(v, float) and v.is_integer() and v >= 100:
        v = int(v)
    if isinstance(v, int) and v >= 1000:
        return f"{v:,}"
    return str(v)


def age_on(birth: str, date: str) -> int:
    by, bm, bd = map(int, birth.split("-"))
    y, m, d = map(int, date.split("-"))
    return y - by - ((m, d) < (bm, bd))


# ---------------------------------------------------------------- narrative chart
def render_narrative(case: dict) -> dict[str, str]:
    pt, gender = case["patient"], case["patient"]["gender"]
    files: dict[str, str] = {}
    age = age_on(pt["birth_date"], case["meta"]["record_date"])
    face = [f"PATIENT SUMMARY (EHR export {case['meta']['record_date']})", "",
            f"Name: {pt['given']} {pt['family']} (synthetic)    MRN: {pt['mrn']}",
            f"DOB: {pt['birth_date']} ({age} y)    Sex: {gender}", "",
            "PROBLEM LIST"]
    face += [f"- {c['display']} (since {c['onset']})" + (f". {c['note']}" if c.get("note") else "") for c in case.get("conditions", [])]
    face += ["", "ACTIVE MEDICATIONS"] + [f"- {m['text']}" for m in case.get("medications", [])] or ["- none"]
    face += ["", "ALLERGIES"] + ([f"- {a['substance']}: {a['reaction']}" for a in case.get("allergies", [])] or ["- No known drug allergies"])
    face += ["", "This is a synthetic training case for AI evaluation. It is not clinical decision support."]
    files["00_patient_summary.txt"] = "\n".join(face) + "\n"

    timeline = []
    for doc in case.get("documents", []):
        body = [doc["title"].upper(), f"Date: {doc['date']}    Author: {doc['author']}"]
        if doc.get("amended"):
            body.append(f"Status: amended {doc['amended']}")
        timeline.append((doc["date"], DOC_TYPES[doc["kind"]][2], "\n".join(body) + "\n\n" + doc["text"].strip() + "\n"))
    for panel in case.get("labs", []):
        rows = [f"LABORATORY RESULTS: {panel['panel']}", f"Collected: {panel['date']}    Synthetic Clinical Laboratory", "",
                f"{'Test':34s}{'Result':>12s}  {'Flag':4s}  {'Units':16s}Reference"]
        for it in panel["items"]:
            key, v = it["key"], it["value"]
            unit = LABS[key][3] or ""
            rows.append(f"{LABS[key][2]:34s}{fmt(v):>12s}  {lab_flag(key, v, gender):4s}  {unit:16s}{ref_text(key, gender)}")
        timeline.append((panel["date"], "labs", "\n".join(rows) + "\n"))
    timeline.sort(key=lambda t: t[0])
    for i, (date, label, text) in enumerate(timeline, 1):
        files[f"{i:02d}_{date}_{label}.txt"] = text
    return files


# ---------------------------------------------------------------- FHIR bundle
def render_fhir(case: dict) -> dict:
    meta, pt, gender = case["meta"], case["patient"], case["patient"]["gender"]
    p = meta["case_id"].replace("_", "-") + "-v2"
    PT, CANCER = f"Patient/{p}-patient", f"Condition/{p}-primary-cancer"
    PATH_LAB, CLIN_LAB, IMAGING = (f"Organization/{p}-{x}" for x in ("pathology-lab", "clinical-lab", "imaging"))
    ONC = f"Practitioner/{p}-hematologist"
    SPEC = f"Specimen/{p}-biopsy-specimen"
    resources: list[dict] = []

    def add(res, summary):
        res["text"] = {"status": "generated", "div": f'<div xmlns="http://www.w3.org/1999/xhtml"><p>{escape(summary)}</p></div>'}
        resources.append(res)

    add({"resourceType": "Patient", "id": f"{p}-patient", "meta": {"profile": [MC + "mcode-cancer-patient"], "security": [HTEST]},
         "extension": [{"url": USC + "us-core-birthsex", "valueCode": "F" if gender == "female" else "M"}],
         "identifier": [{"use": "usual", "type": cc(("http://terminology.hl7.org/CodeSystem/v2-0203", "MR", "Medical record number")),
                         "system": BASE + "/sid/mrn", "value": pt["mrn"]}],
         "name": [{"use": "official", "family": pt["family"], "given": [pt["given"]]}], "gender": gender, "birthDate": pt["birth_date"]},
        f"Synthetic patient {pt['given']} {pt['family']}, {gender}, born {pt['birth_date']}. Test data, not a real person.")

    for i, c in enumerate(case.get("conditions", []), 1):
        res = {"resourceType": "Condition", "id": f"{p}-condition-{i}", "meta": {"profile": [USC + "us-core-condition-problems-health-concerns"]},
               "clinicalStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active")),
               "verificationStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "Confirmed")),
               "category": [cc(("http://terminology.hl7.org/CodeSystem/condition-category", "problem-list-item", "Problem List Item"))],
               "code": cc((SCT, c["code"], c["display"])), "subject": ref(PT), "onsetDateTime": str(c["onset"])}
        if c.get("note"):
            res["note"] = [{"text": c["note"]}]
        add(res, f"Problem: {c['display']} (since {c['onset']}).")
    for i, m in enumerate(case.get("medications", []), 1):
        add({"resourceType": "MedicationStatement", "id": f"{p}-med-{i}", "status": "active",
             "medicationCodeableConcept": {"text": m["text"].split(",")[0]}, "subject": ref(PT),
             "dosage": [{"text": m["text"]}]}, f"Medication: {m['text']}.")
    for i, a in enumerate(case.get("allergies", []), 1):
        add({"resourceType": "AllergyIntolerance", "id": f"{p}-allergy-{i}", "meta": {"profile": [USC + "us-core-allergyintolerance"]},
             "clinicalStatus": cc(("http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "active", "Active")),
             "code": {"text": a["substance"]}, "patient": ref(PT), "reaction": [{"manifestation": [{"text": a["reaction"]}]}]},
            f"Allergy: {a['substance']} ({a['reaction']}).")

    e = case["ecog"]
    add({"resourceType": "Observation", "id": f"{p}-ecog", "meta": {"profile": [MC + "mcode-ecog-performance-status"]},
         "status": "final", "category": [cc((OBS_CAT, "survey", "Survey"))], "code": cc((LOINC, "89247-1", "ECOG Performance Status score")),
         "subject": ref(PT), "effectiveDateTime": e["date"], "performer": [ref(ONC)], "valueInteger": e["value"]},
        f"ECOG performance status {e['value']}.")

    for j, panel in enumerate(case.get("labs", []), 1):
        result_refs = []
        for it in panel["items"]:
            key, v = it["key"], it["value"]
            code, long, short, unit, ucum, low, high = LABS[key]
            rid = f"{p}-lab-{j}-{key.replace('_', '-')}"
            res = {"resourceType": "Observation", "id": rid, "meta": {"profile": [USC + "us-core-observation-lab"]},
                   "status": "final", "category": [cc((OBS_CAT, "laboratory", "Laboratory"))], "code": cc((LOINC, code, long)),
                   "subject": ref(PT), "effectiveDateTime": panel["date"] + "T08:00:00Z", "performer": [ref(CLIN_LAB)]}
            if unit is None:
                res["valueCodeableConcept"] = cc(QUAL[v], text=v)
            else:
                res["valueQuantity"] = qty(v, unit, ucum)
                rr = {}
                if rng(low, gender) is not None:
                    rr["low"] = qty(rng(low, gender), unit, ucum)
                if rng(high, gender) is not None:
                    rr["high"] = qty(rng(high, gender), unit, ucum)
                if rr:
                    res["referenceRange"] = [rr]
                flag = lab_flag(key, v, gender) or "N"
                res["interpretation"] = [cc((INTERP, flag, {"H": "High", "L": "Low", "N": "Normal"}[flag]))]
            add(res, f"{short}: {fmt(v)}{' ' + unit if unit else ''}" + (f" ({lab_flag(key, v, gender)})" if lab_flag(key, v, gender) else "") + f", {panel['date']}.")
            result_refs.append(ref("Observation/" + rid))
        add({"resourceType": "DiagnosticReport", "id": f"{p}-labpanel-{j}", "meta": {"profile": [USC + "us-core-diagnosticreport-lab"]},
             "status": "final", "category": [cc((V2_0074, "LAB", "Laboratory"))], "code": {"text": panel["panel"]},
             "subject": ref(PT), "effectiveDateTime": panel["date"] + "T08:00:00Z", "issued": panel["date"] + "T14:00:00Z",
             "performer": [ref(CLIN_LAB)], "result": result_refs}, f"{panel['panel']}, {panel['date']}.")

    path = case.get("pathology")
    path_results = []
    if path:
        proc_code, proc_disp, spec_code, spec_disp, site_code, site_disp = path["biopsy"]
        add({"resourceType": "Procedure", "id": f"{p}-biopsy", "meta": {"profile": [USC + "us-core-procedure"]}, "status": "completed",
             "code": cc((SCT, proc_code, proc_disp), text=path["specimen_label"]), "subject": ref(PT),
             "performedDateTime": path["collected"], "bodySite": [cc((SCT, site_code, site_disp))]}, f"{path['specimen_label']}, {path['collected']}.")
        add({"resourceType": "Specimen", "id": f"{p}-biopsy-specimen", "meta": {"profile": [MC + "mcode-human-specimen"]}, "status": "available",
             "type": cc(("http://terminology.hl7.org/CodeSystem/v2-0487", "TISS", "Tissue"), (SCT, spec_code, spec_disp)), "subject": ref(PT),
             "collection": {"collectedDateTime": path["collected"], "bodySite": cc((SCT, site_code, site_disp))}}, f"{path['specimen_label']} specimen.")
        dx_code, dx_icd, morph, dx_text = DIAGNOSES[path["diagnosis"]]
        add({"resourceType": "Condition", "id": f"{p}-primary-cancer", "meta": {"profile": [MC + "mcode-primary-cancer-condition"]},
             "extension": [{"url": MC + "mcode-histology-morphology-behavior", "valueCodeableConcept": cc(morph)}],
             "clinicalStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active")),
             "verificationStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "Confirmed")),
             "category": [cc(("http://terminology.hl7.org/CodeSystem/condition-category", "problem-list-item", "Problem List Item"))],
             "code": cc(dx_code, dx_icd, text=dx_text), "subject": ref(PT), "recordedDate": path["ihc_date"],
             "evidence": [{"detail": [ref(f"DiagnosticReport/{p}-doc-pathology")]}]}, f"Primary cancer: {dx_text}.")
        TMT, REL = MC + "mcode-tumor-marker-test", [{"url": MC + "mcode-related-condition", "valueReference": ref(CANCER)}]
        for marker, (kind, code) in IHC_CODES.items():
            v = path["ihc"][marker]
            rid = f"{p}-ihc-{marker.lower()}"
            value = {"valueCodeableConcept": cc(POS if v else NEG)} if kind == "presence" else {"valueQuantity": qty(v, "%", "%")}
            add({"resourceType": "Observation", "id": rid, "meta": {"profile": [TMT]}, "extension": REL, "status": "final",
                 "category": [cc((OBS_CAT, "laboratory", "Laboratory"))], "code": cc(code), "subject": ref(PT),
                 "effectiveDateTime": path["ihc_date"], "performer": [ref(PATH_LAB)], **value, "specimen": ref(SPEC)},
                f"IHC {marker}: " + (("positive" if v else "negative") if kind == "presence" else f"{v}%") + ".")
            path_results.append(ref("Observation/" + rid))
        for gene, code in FISH_CODES.items():
            v = path["fish"][gene]
            rid = f"{p}-fish-{gene.lower()}"
            add({"resourceType": "Observation", "id": rid, "meta": {"profile": [TMT]}, "extension": REL, "status": "final",
                 "category": [cc((OBS_CAT, "laboratory", "Laboratory"))], "code": cc(code), "subject": ref(PT),
                 "effectiveDateTime": path["fish_date"], "issued": path["fish_date"] + "T15:00:00Z", "performer": [ref(PATH_LAB)],
                 "valueCodeableConcept": cc(DET if v else NOT_DET), "specimen": ref(SPEC)},
                f"FISH {gene} rearrangement: {'detected' if v else 'not detected'}.")
            path_results.append(ref("Observation/" + rid))

    for doc in case.get("documents", []):
        rtype, code, label = DOC_TYPES[doc["kind"]]
        attachment = {"contentType": "text/plain; charset=utf-8", "title": doc["title"],
                      "data": base64.b64encode(doc["text"].strip().encode()).decode(), "creation": doc["date"]}
        code_cc = cc(code, text=doc["title"]) if code else {"text": doc["title"]}
        if rtype == "DocumentReference":
            add({"resourceType": "DocumentReference", "id": f"{p}-doc-{doc['id']}", "meta": {"profile": [USC + "us-core-documentreference"]},
                 "status": "current", "docStatus": "final", "type": code_cc,
                 "category": [cc(("http://hl7.org/fhir/us/core/CodeSystem/us-core-documentreference-category", "clinical-note", "Clinical Note"))],
                 "subject": ref(PT), "date": doc["date"] + "T17:00:00Z", "author": [{"display": doc["author"]}],
                 "content": [{"attachment": attachment}]}, f"{doc['title']}, {doc['date']} (text attached).")
        else:
            performer = PATH_LAB if doc["kind"] in ("pathology_report", "marrow_report", "csf_report") else IMAGING
            category = cc((V2_0074, "SP", "Surgical Pathology")) if performer == PATH_LAB else cc((LOINC, "LP29684-5", "Radiology"))
            res = {"resourceType": "DiagnosticReport", "id": f"{p}-doc-{doc['id']}", "meta": {"profile": [USC + "us-core-diagnosticreport-note"]},
                   "status": "amended" if doc.get("amended") else "final", "category": [category], "code": code_cc,
                   "subject": ref(PT), "effectiveDateTime": doc["date"], "issued": (doc.get("amended") or doc["date"]) + "T16:00:00Z",
                   "performer": [ref(performer)], "presentedForm": [attachment]}
            if doc["kind"] == "pathology_report" and path_results:
                res["result"], res["specimen"] = path_results, [ref(SPEC)]
            add(res, f"{doc['title']}, {doc['date']} (full report attached).")

    for oid, name in [("pathology-lab", "Synthetic Hematopathology Laboratory"), ("clinical-lab", "Synthetic Clinical Laboratory"),
                      ("imaging", "Synthetic Imaging Department")]:
        add({"resourceType": "Organization", "id": f"{p}-{oid}", "active": True, "name": name}, f"{name} (synthetic).")
    add({"resourceType": "Practitioner", "id": f"{p}-hematologist", "active": True,
         "name": [{"family": "Hematologist", "given": ["Synthetic"], "prefix": ["Dr."]}]}, "Treating hematologist-oncologist (synthetic).")
    return {"resourceType": "Bundle", "id": p, "meta": {"profile": [MC + "mcode-patient-bundle"], "security": [HTEST]},
            "identifier": {"system": BASE + "/sid/bundle", "value": p}, "type": "collection",
            "timestamp": meta["record_date"] + "T18:00:00Z",
            "entry": [{"fullUrl": f"{BASE}/{r['resourceType']}/{r['id']}", "resource": r} for r in resources]}


# ---------------------------------------------------------------- task files
INSTRUCTION = """You are the consulting hematologist-oncologist for this patient.

This is a synthetic training case for AI evaluation. It is not clinical decision support.

{where}

The patient will be presented at lymphoma tumor board tomorrow. Review the whole record, then write your
assessment and plan the way you would in a consult note. Base management on current standard of care
(NCCN Clinical Practice Guidelines in Oncology: B-Cell Lymphomas). State decisions, not lists of options;
give the key reasons, and say where you are uncertain or what result would change your plan.

Write your answer to:

```text
/app/final_answer.json
```

as one JSON object with these keys (string values, except `missing_information`, which is a list of strings, and
`decisions`, which is an object described below):

- `diagnosis`
- `stage`
- `biology`
- `prognosis`
- `first_line_treatment`
- `cns_risk`
- `response_assessment`
- `pretreatment_workup`
- `supportive_care`
- `fitness_and_goals`
- `missing_information`
- `decisions`: your key decisions restated in fixed fields so they can be read without ambiguity. They must agree
  with your note. Fields:
  - `stage`: the anatomic stage you assign, as a Roman numeral only (no letters, suffixes or ranges)
  - `diagnosis`: your final diagnosis in a few words
  - `intent`: one of `curative`, `palliative`, `observation`
  - `regimen`: the first-line systemic regimen you are ordering, written as on the order, or `none`
  - `cycles`: number of cycles of that regimen (integer)
  - `cycle1_dose_percent`: percent of the full standard dose planned for cycle 1 (integer; 100 = full dose)
  - `radiotherapy`: planned radiotherapy in a few words, or `none`
  - `orders_now`: list of everything you order, start, stop or arrange unconditionally, now or before or with
    cycle 1 (drugs with dose and schedule, tests, procedures, consultations, medication changes)
  - `conditional_orders`: list of actions that depend on a future result or event, each written
    "if <condition>: <action>"
  - `lab_monitoring`: list of scheduled laboratory monitoring around the start of treatment, each
    `{{"tests": "...", "every_hours": <integer or null>, "duration_hours": <integer or null>}}`
"""
WHERE = {
    "narrative": "The chart export is in `/app/case/chart/`: a patient summary followed by dated notes, reports and\nlaboratory results, numbered in chronological order.",
    "fhir": "The chart export is an HL7 FHIR R4 Bundle (mCODE / US Core profiles; SNOMED CT, LOINC and ICD-10-CM codes)\nat `/app/case/fhir_bundle.json`. Narrative notes and reports are attached as base64 text in\n`DocumentReference.content.attachment` and `DiagnosticReport.presentedForm`.",
}
# Agent tooling is baked in ahead of `COPY case` so every v2 task image shares these cached layers. Harbor's
# installed agents skip their per-trial apt-get when curl/node/npm/stdbuf/ps are already on PATH, and their nvm,
# `npm i -g opencode-ai` and Claude Code bootstrap steps become quick re-checks instead of fresh downloads
# (that per-trial install was hitting the 360 s agent setup timeout with 4 trials in parallel).
DOCKERFILE = """FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates procps \\
    && rm -rf /var/lib/apt/lists/*
ENV NVM_DIR=/root/.nvm
RUN curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash \\
    && . "$NVM_DIR/nvm.sh" && nvm install 22 && nvm alias default 22 \\
    && npm i -g opencode-ai \\
    && ln -sf "$(dirname "$(nvm which 22)")"/node /usr/local/bin/node \\
    && ln -sf "$(dirname "$(nvm which 22)")"/npm /usr/local/bin/npm \\
    && ln -sf "$(dirname "$(nvm which 22)")"/opencode /usr/local/bin/opencode
RUN curl -fsSL https://downloads.claude.ai/claude-code-releases/bootstrap.sh | bash

WORKDIR /app
COPY case /app/case
RUN mkdir -p /app/outputs /logs/verifier

CMD ["bash"]
"""
SOLVE = "#!/usr/bin/env bash\nset -euo pipefail\n\nscript_dir=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\ncp \"$script_dir/final_answer.json\" /app/final_answer.json\n"


def task_toml(case, fmt_name, task_id):
    m = case["meta"]
    return f'''id = "{task_id}"
title = "{m['title']} ({'FHIR' if fmt_name == 'fhir' else 'narrative'})"
domain = "hematology_oncology"
subdomain = "lymphoma"
difficulty = "{m['difficulty']}"
patient_type = "synthetic"
task_type = "clinical_reasoning"
oncoworld_version = "v2"
source_case = "cases_src/{m['case_id']}"
review_status = "{m['review_status']}"
input_format = "{'fhir_bundle' if fmt_name == 'fhir' else 'narrative_chart'}"

[evaluation]
rubric_file = "tests/rubric_v2.toml"
gold_file = "solution/gold_answer.md"
verifier = "tests/test.sh"
expected_output = "/app/final_answer.json"
passing_score = 0.75

[verifier]
timeout_sec = 300.0

[verifier.env]
# Optional LLM judge, used only when ONCOWORLD_GRADER=judge; the regex rules are the grader of record.
ONCOWORLD_JUDGE_API_KEY = "${{ONCOWORLD_JUDGE_API_KEY:-}}"
ONCOWORLD_JUDGE_MODEL = "${{ONCOWORLD_JUDGE_MODEL:-}}"
ONCOWORLD_JUDGE_BASE_URL = "${{ONCOWORLD_JUDGE_BASE_URL:-https://openrouter.ai/api/v1}}"
ONCOWORLD_JUDGE_HEADERS = "${{ONCOWORLD_JUDGE_HEADERS:-}}"
ONCOWORLD_GRADER = "${{ONCOWORLD_GRADER:-regex}}"
'''


def judge_context(case_dir: Path) -> str:
    """Patient summary for the LLM judge (hidden; tests/ only): the plain-language case card."""
    p = case_dir / "review_labels.json"
    card = json.loads(p.read_text()).get("case_card", {}) if p.exists() else {}
    return (f"{card.get('patient', '')}\nWhat this case tests: " + " | ".join(card.get("tests", []))).strip() + "\n"


def gold_md(case, gold, rubric):
    lines = [f"# Gold answer: {case['meta']['case_id']} (v2)", "",
             f"Review status: **{rubric.get('review_status')}**. Rubric version `{rubric.get('version')}`.", "",
             "Hidden from the model. Generated from cases_src by scripts/build_cases_v2.py.", ""]
    for k, v in gold.items():
        if isinstance(v, dict):
            body = ["```json", json.dumps(v, ensure_ascii=False, indent=1), "```"]
        elif isinstance(v, list):
            body = [f"- {x}" for x in v]
        else:
            body = [v]
        lines += [f"## {k}", ""] + body + [""]
    lines += ["## Rubric items", "", "| id | kind | severity | points | criterion |", "|---|---|---|---|---|"]
    lines += [f"| {i['id']} | {i['kind']} | {i['severity']} | {i['points']} | {i['text']} |" for i in rubric["items"]]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- checks
def leak_check(rubric, visible: dict[str, str], where: str):
    hits = []
    for term in rubric.get("leak_check", {}).get("forbidden_in_case", []):
        pat = re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])")
        hits += [f"{where}/{name}: '{term}'" for name, text in visible.items() if pat.search(text.lower())]
    if hits:
        raise SystemExit("LEAK CHECK FAILED:\n  " + "\n  ".join(hits))


def pathology_consistency(case):
    path = case.get("pathology")
    if not path:
        return
    text = next(d["text"] for d in case["documents"] if d["kind"] == "pathology_report").lower()
    problems = []
    for marker, v in path["ihc"].items():
        if isinstance(v, bool):
            continue
        if not re.search(rf"{marker.lower().replace('ki67', 'ki-67')}[^\n]*\b{v}%", text):
            problems.append(f"IHC {marker} {v}% not in pathology text")
    for gene, v in path["fish"].items():
        line = next((ln for ln in text.splitlines() if ln.strip().startswith(gene.lower()) and "rearrangement" in ln), "")
        if bool(v) != ("rearrangement detected" in line and "no rearrangement" not in line):
            problems.append(f"FISH {gene}={v} disagrees with pathology text line: {line.strip()!r}")
    if problems:
        raise SystemExit("PATHOLOGY CONSISTENCY FAILED:\n  " + "\n  ".join(problems))


def gold_check(gold, rubric):
    r = score(json.dumps(gold, ensure_ascii=False, indent=1), rubric)
    bad = [i["id"] for i in r["items"] if (i["kind"] == "must_not") == i["met"] and i.get("regex") is not None]
    if bad or r["reward"] != 1.0:
        raise SystemExit(f"GOLD CHECK FAILED: reward={r['reward']} items={bad} dangerous={r['dangerous_errors']}")


# ---------------------------------------------------------------- main
def build(case_dir: Path):
    case = tomllib.loads((case_dir / "case.toml").read_text())
    rubric = tomllib.loads((case_dir / "rubric_v2.toml").read_text())
    gold = json.loads((case_dir / "gold.json").read_text())
    pathology_consistency(case)
    gold_check(gold, rubric)
    m = case["meta"]
    renderings = {"narrative": {f"chart/{k}": v for k, v in render_narrative(case).items()},
                  "fhir": {"fhir_bundle.json": json.dumps(render_fhir(case), indent=2, ensure_ascii=False) + "\n"}}
    for fmt_name, visible in renderings.items():
        task_id = f"{m['case_id']}_{m['slug']}_v2_{fmt_name}"
        decoded = dict(visible)
        if fmt_name == "fhir":  # check the base64 attachments too
            bundle = json.loads(visible["fhir_bundle.json"])
            for e in bundle["entry"]:
                for att in [c["attachment"] for c in e["resource"].get("content", [])] + e["resource"].get("presentedForm", []):
                    decoded[f"{e['resource']['id']}.txt"] = base64.b64decode(att["data"]).decode()
        instruction = INSTRUCTION.format(where=WHERE[fmt_name])
        leak_check(rubric, decoded | {"instruction.md": instruction}, task_id)

        # FHIR tasks are the benchmark; narrative renderings live apart and are only run as a diagnostic control
        out = ROOT / ("harbor_cases" if fmt_name == "fhir" else "harbor_cases_narrative") / task_id
        if out.exists():
            shutil.rmtree(out)
        for rel, text in visible.items():
            (out / "environment" / "case" / rel).parent.mkdir(parents=True, exist_ok=True)
            (out / "environment" / "case" / rel).write_text(text)
        (out / "environment" / "Dockerfile").write_text(DOCKERFILE)
        (out / "instruction.md").write_text(instruction)
        (out / "task.toml").write_text(task_toml(case, fmt_name, task_id))
        (out / "solution").mkdir()
        (out / "solution" / "final_answer.json").write_text(json.dumps(gold, indent=2, ensure_ascii=False) + "\n")
        (out / "solution" / "gold_answer.md").write_text(gold_md(case, gold, rubric))
        (out / "solution" / "solve.sh").write_text(SOLVE)
        (out / "solution" / "solve.sh").chmod(0o755)
        tests = out / "tests"
        (tests / "selftest" / "answers").mkdir(parents=True)
        shutil.copy(GRADER_DIR / "grader_v2.py", tests / "grader_v2.py")
        shutil.copy(GRADER_DIR / "test.sh", tests / "test.sh")
        shutil.copy(case_dir / "rubric_v2.toml", tests / "rubric_v2.toml")
        shutil.copy(GRADER_DIR / "run_selftest.py", tests / "selftest" / "run_selftest.py")
        ref_answer = dict(gold, _expect={"passed": True, "dangerous": [], "all_met": True})
        (tests / "selftest" / "answers" / "01_reference.json").write_text(json.dumps(ref_answer, indent=2, ensure_ascii=False) + "\n")
        for sub in ("answers", "judge_cases"):
            src = case_dir / "selftest" / sub
            if src.exists():
                (tests / "selftest" / sub).mkdir(exist_ok=True)
                for f in src.glob("*.json"):
                    shutil.copy(f, tests / "selftest" / sub / f.name)
        (tests / "judge_context.txt").write_text(judge_context(case_dir))
        if (case_dir / "selftest" / "probes.json").exists():   # oncologist probe sentences per high-stakes rule
            shutil.copy(case_dir / "selftest" / "probes.json", tests / "selftest" / "probes.json")
        print(f"built {out.relative_to(ROOT)} ({len(visible)} visible file(s))")


def main():
    wanted = set(sys.argv[1:])
    for case_dir in sorted((ROOT / "cases_src").iterdir()):
        if (case_dir / "case.toml").exists() and (not wanted or case_dir.name in wanted):
            build(case_dir)


if __name__ == "__main__":
    main()
