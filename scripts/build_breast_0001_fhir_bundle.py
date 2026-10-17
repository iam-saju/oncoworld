#!/usr/bin/env python3
"""Build the breast_0001 FHIR R4 / mCODE STU4 patient bundle (model-visible chart only).

Usage: python3 scripts/build_breast_0001_fhir_bundle.py harbor_cases/breast_0001_fhir/environment/case/fhir_bundle.json

Every code below was checked against tx.fhir.org before use. The bundle carries chart facts
only: no stage, no risk category, no treatment plan, because those are what the model is graded on.
"""
import json
import sys
from html import escape

BASE = "http://oncoworld.example/fhir"
SCT, LOINC, UCUM = "http://snomed.info/sct", "http://loinc.org", "http://unitsofmeasure.org"
ICD10, ICDO3 = "http://hl7.org/fhir/sid/icd-10-cm", "http://terminology.hl7.org/CodeSystem/icd-o-3"
MC = "http://hl7.org/fhir/us/mcode/StructureDefinition/"
USC = "http://hl7.org/fhir/us/core/StructureDefinition/"
OBS_CAT = "http://terminology.hl7.org/CodeSystem/observation-category"
HTEST = {"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "HTEST", "display": "test health data"}

PT = "Patient/breast-0001-patient"
CANCER = "Condition/breast-0001-primary-cancer"
LUMP_SPEC = "Specimen/breast-0001-lumpectomy-specimen"
SLN_SPEC = "Specimen/breast-0001-sentinel-node-specimen"
PATH_LAB = "Organization/breast-0001-pathology-lab"
CLIN_LAB = "Organization/breast-0001-clinical-lab"
GENOMIC_LAB = "Organization/breast-0001-genomic-lab"
ONCOLOGIST = "Practitioner/breast-0001-oncologist"


def cc(system, code, display, text=None):
    c = {"coding": [{"system": system, "code": code, "display": display}]}
    if text:
        c["text"] = text
    return c


def cc2(codings, text=None):
    c = {"coding": [{"system": s, "code": k, "display": d} for s, k, d in codings]}
    if text:
        c["text"] = text
    return c


def ref(r, display=None):
    out = {"reference": r}
    if display:
        out["display"] = display
    return out


def qty(value, unit, code):
    return {"value": value, "unit": unit, "system": UCUM, "code": code}


def narrative(summary):
    return {"status": "generated", "div": f'<div xmlns="http://www.w3.org/1999/xhtml"><p>{escape(summary)}</p></div>'}


RIGHT = {"url": MC + "mcode-laterality-qualifier", "valueCodeableConcept": cc(SCT, "24028007", "Right (qualifier value)")}
LAB_CAT = [cc(OBS_CAT, "laboratory", "Laboratory")]

resources = []


def add(res, summary):
    res["text"] = narrative(summary)
    resources.append(res)


# ---------------------------------------------------------------- patient + history
add({
    "resourceType": "Patient", "id": "breast-0001-patient",
    "meta": {"profile": [MC + "mcode-cancer-patient"], "security": [HTEST]},
    "extension": [{"url": USC + "us-core-birthsex", "valueCode": "F"}],
    "identifier": [{"use": "usual",
                    "type": cc("http://terminology.hl7.org/CodeSystem/v2-0203", "MR", "Medical record number"),
                    "system": BASE + "/sid/mrn", "value": "ONC-BR-0001"}],
    "name": [{"use": "official", "family": "Sample", "given": ["Meera"]}],
    "gender": "female", "birthDate": "1968-04-17",
}, "Synthetic patient Meera Sample, female, born 1968-04-17 (58 years old). Test data, not a real person.")

add({
    "resourceType": "Condition", "id": "breast-0001-postmenopausal",
    "meta": {"profile": [USC + "us-core-condition-problems-health-concerns"]},
    "clinicalStatus": cc("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active"),
    "verificationStatus": cc("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "Confirmed"),
    "category": [cc("http://terminology.hl7.org/CodeSystem/condition-category", "problem-list-item", "Problem List Item")],
    "code": cc(SCT, "76498008", "Postmenopausal state"),
    "subject": ref(PT), "onsetAge": {"value": 52, "unit": "years", "system": UCUM, "code": "a"},
    "recordedDate": "2026-10-01",
    "note": [{"text": "Last menstrual period at age 52. Never used hormone replacement therapy."}],
}, "Postmenopausal; last menstrual period at age 52; no hormone replacement therapy.")

add({
    "resourceType": "List", "id": "breast-0001-family-history", "status": "current", "mode": "snapshot",
    "title": "Family history", "code": cc(LOINC, "10157-6", "History of family member diseases note"),
    "subject": ref(PT), "date": "2026-10-01",
    "emptyReason": cc("http://terminology.hl7.org/CodeSystem/list-empty-reason", "nilknown", "Nil Known"),
    "note": [{"text": "No known family history of breast, ovarian or other cancer."}],
}, "Family history: none known.")

add({
    "resourceType": "List", "id": "breast-0001-medications", "status": "current", "mode": "snapshot",
    "title": "Medication history", "code": cc(LOINC, "10160-0", "History of Medication use Narrative"),
    "subject": ref(PT), "date": "2026-10-01",
    "emptyReason": cc("http://terminology.hl7.org/CodeSystem/list-empty-reason", "nilknown", "Nil Known"),
    "note": [{"text": "No regular medications. No prior or current hormone replacement therapy. Adjuvant cancer treatment has not started."}],
}, "Medications: none. No HRT. Adjuvant treatment not started.")

add({
    "resourceType": "List", "id": "breast-0001-problem-list", "status": "current", "mode": "snapshot",
    "title": "Problem list", "code": cc(LOINC, "11450-4", "Problem list - Reported"),
    "subject": ref(PT), "date": "2026-10-01",
    "entry": [{"item": ref(CANCER)}, {"item": ref("Condition/breast-0001-postmenopausal")}],
    "note": [{"text": "No other medical comorbidities. No prior chest or breast radiation."}],
}, "Problem list: right breast cancer, postmenopausal state. No comorbidities. No prior chest radiation.")

add({
    "resourceType": "Observation", "id": "breast-0001-ecog",
    "meta": {"profile": [MC + "mcode-ecog-performance-status"]}, "status": "final",
    "category": [cc(OBS_CAT, "survey", "Survey")],
    "code": cc(LOINC, "89247-1", "ECOG Performance Status score"),
    "subject": ref(PT), "effectiveDateTime": "2026-10-01", "performer": [ref(ONCOLOGIST)], "valueInteger": 0,
    "interpretation": [cc(LOINC, "LA9622-7", "Fully active, able to carry on all pre-disease performance without restriction")],
}, "ECOG performance status 0 on 2026-10-01.")

# ---------------------------------------------------------------- diagnosis
add({
    "resourceType": "Condition", "id": "breast-0001-primary-cancer",
    "meta": {"profile": [MC + "mcode-primary-cancer-condition"]},
    "extension": [{"url": MC + "mcode-histology-morphology-behavior",
                   "valueCodeableConcept": cc(SCT, "82711006", "Infiltrating duct carcinoma (morphologic abnormality)")}],
    "clinicalStatus": cc("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active"),
    "verificationStatus": cc("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "Confirmed"),
    "category": [cc("http://terminology.hl7.org/CodeSystem/condition-category", "problem-list-item", "Problem List Item")],
    "code": cc2([(SCT, "1306491000", "Primary infiltrating duct carcinoma of upper outer quadrant of right breast"),
                 (ICD10, "C50.411", "Malignant neoplasm of upper-outer quadrant of right female breast")]),
    "bodySite": [dict(cc(SCT, "110496004", "Upper outer quadrant of right breast"), extension=[RIGHT])],
    "subject": ref(PT), "onsetDateTime": "2026-07-14", "recordedDate": "2026-08-25",
    "evidence": [{"detail": [ref("DiagnosticReport/breast-0001-surgical-pathology")]}],
}, "Primary invasive ductal carcinoma, right breast, upper outer quadrant. Screening-detected 2026-07-14.")

# ---------------------------------------------------------------- imaging
RAD_CAT = cc(LOINC, "LP29684-5", "Radiology")
add({
    "resourceType": "DiagnosticReport", "id": "breast-0001-screening-mammogram",
    "meta": {"profile": [USC + "us-core-diagnosticreport-note"]}, "status": "final",
    "category": [RAD_CAT], "code": cc(LOINC, "24606-6", "MG Breast Screening"),
    "subject": ref(PT), "effectiveDateTime": "2026-07-14", "issued": "2026-07-14T16:00:00Z",
    "conclusion": "Right breast: 1.8 cm irregular spiculated mass in the upper outer quadrant. Left breast: negative.",
}, "Screening mammogram 2026-07-14: 1.8 cm irregular spiculated mass, right upper outer quadrant. Left breast negative.")

add({
    "resourceType": "DiagnosticReport", "id": "breast-0001-breast-ultrasound",
    "meta": {"profile": [USC + "us-core-diagnosticreport-note"]}, "status": "final",
    "category": [RAD_CAT], "code": cc(LOINC, "26216-2", "US Breast - right"),
    "subject": ref(PT), "effectiveDateTime": "2026-07-21", "issued": "2026-07-21T15:00:00Z",
    "conclusion": "Right breast upper outer quadrant: 1.8 cm irregular spiculated hypoechoic mass corresponding to the mammographic finding. Right axilla: no suspicious lymph nodes. No systemic staging imaging has been performed.",
}, "Right breast and axillary ultrasound 2026-07-21: 1.8 cm mass; no suspicious axillary nodes. No systemic staging imaging.")

# ---------------------------------------------------------------- surgery + specimens
SURG = MC + "mcode-cancer-related-surgical-procedure"
CURATIVE = {"url": MC + "mcode-procedure-intent", "valueCodeableConcept": cc(SCT, "373808002", "Curative - procedure intent")}
add({
    "resourceType": "Procedure", "id": "breast-0001-lumpectomy", "meta": {"profile": [SURG]},
    "extension": [CURATIVE], "status": "completed",
    "code": cc(SCT, "392021009", "Lumpectomy of breast"), "subject": ref(PT),
    "performedDateTime": "2026-08-20", "reasonReference": [ref(CANCER)],
    "bodySite": [dict(cc(SCT, "73056007", "Right breast structure"), extension=[RIGHT])],
}, "Right breast lumpectomy, 2026-08-20.")
add({
    "resourceType": "Procedure", "id": "breast-0001-sentinel-node-biopsy", "meta": {"profile": [SURG]},
    "extension": [CURATIVE], "status": "completed",
    "code": cc(SCT, "1179695007", "Excisional biopsy of axillary sentinel lymph node"), "subject": ref(PT),
    "performedDateTime": "2026-08-20", "reasonReference": [ref(CANCER)],
    "bodySite": [dict(cc(SCT, "68171009", "Axillary lymph node structure"), extension=[RIGHT])],
}, "Right axillary sentinel lymph node biopsy, 2026-08-20.")
add({
    "resourceType": "Procedure", "id": "breast-0001-dexa-not-done",
    "meta": {"profile": [USC + "us-core-procedure"]}, "status": "not-done",
    "statusReason": {"text": "Not yet performed"},
    "code": cc(SCT, "241686001", "Dual energy X-ray absorptiometry"), "subject": ref(PT),
    "performedDateTime": "2026-10-01",
}, "Bone density (DEXA) scan: not yet performed.")

TISS = ("http://terminology.hl7.org/CodeSystem/v2-0487", "TISS", "Tissue")
add({
    "resourceType": "Specimen", "id": "breast-0001-lumpectomy-specimen",
    "meta": {"profile": [MC + "mcode-human-specimen"]}, "status": "available",
    "type": cc2([TISS, (SCT, "309546004", "Lumpectomy breast specimen")]),
    "subject": ref(PT),
    "collection": {"collectedDateTime": "2026-08-20",
                   "bodySite": dict(cc(SCT, "73056007", "Right breast structure"), extension=[RIGHT])},
}, "Right breast lumpectomy specimen.")
add({
    "resourceType": "Specimen", "id": "breast-0001-sentinel-node-specimen",
    "meta": {"profile": [MC + "mcode-human-specimen"]}, "status": "available",
    "type": cc2([TISS, (SCT, "441709004", "Specimen from sentinel lymph node")]),
    "subject": ref(PT),
    "collection": {"collectedDateTime": "2026-08-20",
                   "bodySite": dict(cc(SCT, "68171009", "Axillary lymph node structure"), extension=[RIGHT])},
}, "Right axillary sentinel lymph nodes (2 nodes).")

# ---------------------------------------------------------------- pathology observations
LAB = USC + "us-core-observation-lab"
TMT = MC + "mcode-tumor-marker-test"
REL = [{"url": MC + "mcode-related-condition", "valueReference": ref(CANCER)}]
PATH_DATE = "2026-08-25"
path_ids = []


def path_obs(rid, summary, profile, code, value, specimen=LUMP_SPEC, **extra):
    res = {"resourceType": "Observation", "id": rid, "meta": {"profile": [profile]}, "status": "final",
           "category": LAB_CAT, "code": code, "subject": ref(PT), "effectiveDateTime": PATH_DATE,
           "performer": [ref(PATH_LAB)],
           **value, "specimen": ref(specimen), **extra}
    if profile in (TMT, MC + "mcode-histologic-grade"):
        res = {**res, "extension": REL}
    add(res, summary)
    path_ids.append("Observation/" + rid)


add({
    "resourceType": "Observation", "id": "breast-0001-tumor-size",
    "meta": {"profile": [MC + "mcode-tumor-size"]}, "status": "final", "category": LAB_CAT,
    "code": cc(LOINC, "21889-1", "Size Tumor"), "subject": ref(PT), "effectiveDateTime": PATH_DATE,
    "performer": [ref(PATH_LAB)],
    "method": cc(SCT, "104157003", "Light microscopy (procedure)"), "specimen": ref(LUMP_SPEC),
    "component": [{"code": cc(LOINC, "33728-7", "Size.maximum dimension in Tumor"),
                   "valueQuantity": qty(1.8, "cm", "cm")}],
}, "Invasive tumor size 1.8 cm (greatest dimension).")
path_ids.append("Observation/breast-0001-tumor-size")

path_obs("breast-0001-histologic-grade", "Nottingham histologic grade 2 (intermediate).", MC + "mcode-histologic-grade",
         cc("http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl", "C18000", "Histologic Grade"),
         {"valueCodeableConcept": cc2([(SCT, "1286893008", "Intermediate histologic grade (qualifier value)"),
                                       (LOINC, "LA27824-4", "Nottingham grade 2")])},
         method=cc(SCT, "449205006", "Nottingham histologic grading system", "Nottingham combined histologic grade (Elston-Ellis modification)"))
path_obs("breast-0001-lvi", "Lymphovascular invasion not identified.", LAB,
         cc(LOINC, "59544-7", "Lymph-vascular invasion Cancer specimen"),
         {"valueCodeableConcept": cc(LOINC, "LA13327-4", "Lymph-vascular Invasion Not Present (absent)/Not Identified")})
path_obs("breast-0001-margin", "All margins negative for invasive carcinoma; closest margin 4 mm.", LAB,
         cc(LOINC, "33737-8", "Distance of tumor from closest margin"),
         {"valueQuantity": qty(4, "mm", "mm")},
         note=[{"text": "All margins negative for invasive carcinoma."}])
path_obs("breast-0001-sln-examined", "Sentinel lymph nodes examined: 2.", LAB,
         cc(LOINC, "85347-3", "Sentinel lymph nodes examined [#] in Cancer specimen by Light microscopy"),
         {"valueInteger": 2}, specimen=SLN_SPEC)
path_obs("breast-0001-sln-positive", "Sentinel lymph nodes with metastasis: 0.", LAB,
         cc(LOINC, "92832-5", "Sentinel lymph nodes with metastasis [#] in Cancer specimen"),
         {"valueInteger": 0}, specimen=SLN_SPEC)

POS, NEG = cc(SCT, "10828004", "Positive"), cc(SCT, "260385009", "Negative")
path_obs("breast-0001-er", "Estrogen receptor positive: 95% of tumor cells, strong intensity.", TMT,
         cc(LOINC, "85337-4", "Estrogen receptor Ag [Presence] in Breast cancer specimen by Immune stain"),
         {"valueCodeableConcept": POS},
         component=[{"code": cc(LOINC, "85329-1", "Cells.estrogen receptor/cells in Breast cancer specimen by Immune stain"),
                     "valueQuantity": qty(95, "%", "%")},
                    {"code": cc(LOINC, "85310-1", "Estrogen receptor fluorescence intensity [Type] in Breast cancer specimen by Immune stain"),
                     "valueCodeableConcept": {"text": "Strong"}}])
path_obs("breast-0001-pr", "Progesterone receptor positive: 80% of tumor cells.", TMT,
         cc(LOINC, "85339-0", "Progesterone receptor Ag [Presence] in Breast cancer specimen by Immune stain"),
         {"valueCodeableConcept": POS},
         component=[{"code": cc(LOINC, "85325-9", "Cells.progesterone receptor/cells in Breast cancer specimen by Immune stain"),
                     "valueQuantity": qty(80, "%", "%")}])
path_obs("breast-0001-her2-ihc", "HER2 by immunohistochemistry: score 1+, reported as negative.", TMT,
         cc(LOINC, "85319-2", "HER2 Ag [Presence] in Breast cancer specimen by Immune stain"),
         {"valueCodeableConcept": dict(NEG, text="Negative (IHC score 1+)")})
path_obs("breast-0001-ki67", "Ki-67 proliferation index 15%.", TMT,
         cc(LOINC, "85330-9", "Cells.Ki-67 nuclear Ag/cells in Breast cancer specimen by Immune stain"),
         {"valueQuantity": qty(15, "%", "%")})

add({
    "resourceType": "DiagnosticReport", "id": "breast-0001-surgical-pathology",
    "meta": {"profile": [USC + "us-core-diagnosticreport-lab"]}, "status": "final",
    "category": [cc("http://terminology.hl7.org/CodeSystem/v2-0074", "LAB", "Laboratory"),
                 cc("http://terminology.hl7.org/CodeSystem/v2-0074", "SP", "Surgical Pathology")],
    "code": cc(LOINC, "60568-3", "Pathology synoptic report"), "performer": [ref(PATH_LAB)],
    "subject": ref(PT), "effectiveDateTime": PATH_DATE, "issued": "2026-08-25T17:00:00Z",
    "specimen": [ref(LUMP_SPEC), ref(SLN_SPEC)],
    "result": [ref(r) for r in path_ids],
    "conclusion": ("A. Right breast, lumpectomy: invasive ductal carcinoma, no special type (NST), Nottingham grade 2, "
                   "1.8 cm. No lymphovascular invasion. Margins negative for invasive carcinoma; closest margin 4 mm. "
                   "ER positive (95%, strong). PR positive (80%). HER2 negative (IHC 1+). Ki-67 15%. "
                   "B. Right axillary sentinel lymph nodes: 0 of 2 lymph nodes involved by carcinoma."),
    "conclusionCode": [cc(SCT, "1306491000", "Primary infiltrating duct carcinoma of upper outer quadrant of right breast")],
}, "Surgical pathology 2026-08-25: IDC NST, grade 2, 1.8 cm, LVI absent, margins negative (4 mm), ER 95%, PR 80%, HER2 IHC 1+ negative, Ki-67 15%, sentinel nodes 0/2.")

# ---------------------------------------------------------------- genomic assay
add({
    "resourceType": "Observation", "id": "breast-0001-recurrence-score",
    "meta": {"profile": [LAB]}, "status": "final", "category": LAB_CAT,
    "code": {"coding": [{"system": BASE + "/CodeSystem/lab-local", "code": "RS21",
                         "display": "21-gene Breast Recurrence Score"}],
             "text": "21-gene Breast Recurrence Score (Oncotype DX)"},
    "subject": ref(PT), "effectiveDateTime": "2026-09-15", "performer": [ref(GENOMIC_LAB)],
    "valueInteger": 14,
    "specimen": ref(LUMP_SPEC),
}, "21-gene Recurrence Score: 14.")
add({
    "resourceType": "DiagnosticReport", "id": "breast-0001-genomic-assay",
    "meta": {"profile": [USC + "us-core-diagnosticreport-lab"]}, "status": "final",
    "category": [cc("http://terminology.hl7.org/CodeSystem/v2-0074", "LAB", "Laboratory")],
    "code": cc(LOINC, "104119-3", "Breast Cancer recurrence risk multigene analysis in Tissue by Molecular genetics method"),
    "subject": ref(PT), "effectiveDateTime": "2026-09-15", "issued": "2026-09-22T12:00:00Z",
    "specimen": [ref(LUMP_SPEC)], "result": [ref("Observation/breast-0001-recurrence-score")],
    "conclusion": "21-gene Breast Recurrence Score result: 14.",
}, "21-gene recurrence score assay 2026-09-15: Recurrence Score 14.")

# ---------------------------------------------------------------- labs
labs = [
    ("hemoglobin", "718-7", "Hemoglobin [Mass/volume] in Blood", 13.1, "g/dL", "g/dL", (12.0, 15.5)),
    ("wbc", "6690-2", "Leukocytes [#/volume] in Blood by Automated count", 6.4, "10*3/uL", "10*3/uL", (4.0, 11.0)),
    ("platelets", "777-3", "Platelets [#/volume] in Blood by Automated count", 245, "10*3/uL", "10*3/uL", (150, 400)),
    ("creatinine", "2160-0", "Creatinine [Mass/volume] in Serum or Plasma", 0.8, "mg/dL", "mg/dL", (0.5, 1.1)),
    ("ast", "1920-8", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma", 24, "U/L", "U/L", (10, 40)),
    ("alt", "1742-6", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma", 21, "U/L", "U/L", (7, 35)),
    ("alp", "6768-6", "Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma", 82, "U/L", "U/L", (40, 130)),
    ("calcium", "17861-6", "Calcium [Mass/volume] in Serum or Plasma", 9.4, "mg/dL", "mg/dL", (8.6, 10.3)),
]
lab_refs = {"cbc": [], "cmp": []}
for key, code, disp, val, unit, ucode, (lo, hi) in labs:
    rid = f"breast-0001-lab-{key}"
    add({
        "resourceType": "Observation", "id": rid, "meta": {"profile": [LAB]}, "status": "final",
        "category": LAB_CAT, "code": cc(LOINC, code, disp), "subject": ref(PT),
        "effectiveDateTime": "2026-10-01T08:30:00Z", "performer": [ref(CLIN_LAB)], "valueQuantity": qty(val, unit, ucode),
        "interpretation": [cc("http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "N", "Normal")],
        "referenceRange": [{"low": qty(lo, unit, ucode), "high": qty(hi, unit, ucode)}],
    }, f"{disp.split(' [')[0]}: {val} {unit} (reference {lo}-{hi}).")
    lab_refs["cbc" if key in ("hemoglobin", "wbc", "platelets") else "cmp"].append(ref("Observation/" + rid))

for key, code, disp in [("cbc", "58410-2", "CBC panel - Blood by Automated count"),
                        ("cmp", "24323-8", "Comprehensive metabolic 2000 panel - Serum or Plasma")]:
    add({
        "resourceType": "DiagnosticReport", "id": f"breast-0001-{key}",
        "meta": {"profile": [USC + "us-core-diagnosticreport-lab"]}, "status": "final",
        "category": [cc("http://terminology.hl7.org/CodeSystem/v2-0074", "LAB", "Laboratory")],
        "code": cc(LOINC, code, disp), "subject": ref(PT),
        "effectiveDateTime": "2026-10-01T08:30:00Z", "issued": "2026-10-01T11:00:00Z",
        "result": lab_refs[key],
    }, f"{disp} on 2026-10-01: all results within reference range.")

for oid, name in [("pathology-lab", "Synthetic Surgical Pathology Laboratory"),
                  ("clinical-lab", "Synthetic Clinical Chemistry and Hematology Laboratory"),
                  ("genomic-lab", "Synthetic Reference Genomic Laboratory")]:
    add({"resourceType": "Organization", "id": f"breast-0001-{oid}", "active": True, "name": name,
         "type": [cc("http://terminology.hl7.org/CodeSystem/organization-type", "prov", "Healthcare Provider")]},
        f"{name} (synthetic).")
add({"resourceType": "Practitioner", "id": "breast-0001-oncologist", "active": True,
     "identifier": [{"system": BASE + "/sid/practitioner", "value": "ONC-MD-0001"}],
     "name": [{"family": "Oncologist", "given": ["Synthetic"], "prefix": ["Dr."]}]},
    "Treating medical oncologist (synthetic).")

bundle = {
    "resourceType": "Bundle", "id": "breast-0001",
    "meta": {"profile": [MC + "mcode-patient-bundle"], "security": [HTEST]},
    "identifier": {"system": BASE + "/sid/bundle", "value": "breast-0001"},
    "type": "collection", "timestamp": "2026-10-01T12:00:00Z",
    "entry": [{"fullUrl": f"{BASE}/{r['resourceType']}/{r['id']}", "resource": r} for r in resources],
}
json.dump(bundle, open(sys.argv[1], "w"), indent=2, ensure_ascii=False)
print(f"wrote {sys.argv[1]} with {len(resources)} resources")
