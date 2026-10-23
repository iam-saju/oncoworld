#!/usr/bin/env python3
"""Build the OncoWorld v2 longitudinal journey as one Harbor multi-step task, in two renderings.

Usage: python3 scripts/build_journey_v2.py [journey_id ...]     (default: every cases_src/*/journey.toml)

cases_src/<journey>/journey.toml   layers, questions, model-visible documents and structured FHIR data (see its header)
cases_src/<journey>/L<n>_rubric.toml, L<n>_gold.json   hidden per-layer rubric and reference answer
cases_src/<journey>/selftest/L<n>/*.json               hidden adversarial answers for that layer
cases_src/<journey>/selftest/probes/L<n>.json          oncologist probe sentences for that layer's rules

Output:
  harbor_cases/<journey>_v2_fhir/        the benchmark. Layer 1 is the single-case FHIR bundle (cases_src/<base_case>)
                                         baked into the image at /app/case/fhir_bundle.json; each later visit uploads ONE
                                         FHIR update Bundle to /app/case/fhir_updates/ right before its step (notes and
                                         reports as base64 attachments, plus structured labs, vitals, ECOG, medications,
                                         administrations, procedures and genomic variants).
  harbor_cases_narrative/<journey>_v2/   diagnostic control: the same facts as chart/*.txt files.

The model never sees a future layer: Harbor uploads steps/<step>/workdir/ into /app only when that step starts.
Each step writes its own answer file and is graded by grader_v2 on its own. Harbor averages step rewards;
scripts/summarize_job.py applies the layer weights and the rule that a dangerous error in any layer fails the case.

Checks that fail the build, per layer: every leak_check term of that layer's rubric is searched in everything the model
can see at that step (base chart, every update up to this one with base64 decoded, and the instruction); the gold
answer must score 1.0 under the regex rules.
"""
from __future__ import annotations

import base64
import json
import shutil
import sys
import tomllib
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_cases_v2 import (  # noqa: E402
    DOC_TYPES, DOCKERFILE, GRADER_DIR, INSTRUCTION, INTERP, LABS, WHERE, gold_check, judge_context, lab_flag, leak_check,
    render_fhir, render_narrative, rng, fmt,
)
from build_dlbcl_fhir_bundles import BASE, HTEST, LOINC, OBS_CAT, USC, V2_0074, cc, qty, ref  # noqa: E402

FIRST_VISIT = ("This is the first visit of a longitudinal follow-up: at later visits new records will be added to the\n"
               "chart and you will be asked to update your plan.\n")

LATER_INSTRUCTION = """You are the treating hematologist-oncologist. This is the same patient you assessed earlier, now on
{date}: {heading}.

This is a synthetic training case for AI evaluation. It is not clinical decision support.

{where}

Answer each question with a clear decision, the key reasons, and important uncertainty. Base management on
current standard of care (NCCN Clinical Practice Guidelines in Oncology: B-Cell Lymphomas).

{questions}

Write your answer to:

```text
{answer_file}
```

as one JSON object with string values for the keys {keys}.
"""

LATER_WHERE = {
    "narrative": """The full chart is in `/app/case/chart/`. The earlier files are unchanged. The new documents for this visit
(numbered {first}x) begin with an interval history describing what ACTUALLY happened since the last visit;
take that history as fact even if it differs from what you previously recommended. Your earlier answers are in
`/app/answers/`.""",
    "fhir": """The record is HL7 FHIR R4 (mCODE / US Core profiles; SNOMED CT, LOINC and ICD-10-CM codes). The original export is
`/app/case/fhir_bundle.json`; each later visit adds one update Bundle in `/app/case/fhir_updates/`, numbered in date
order. Earlier files are unchanged. The update for this visit is `/app/case/fhir_updates/{update}`. Narrative notes
and reports are attached as base64 text in `DocumentReference.content.attachment` and
`DiagnosticReport.presentedForm`. The update's first document is an interval history describing what ACTUALLY
happened since the last visit; take that history as fact even if it differs from what you previously recommended.
Your earlier answers are in `/app/answers/`.""",
}

SOLVE = """#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
mkdir -p "$(dirname {answer_file})"
cp "$script_dir/final_answer.json" {answer_file}
"""

AGENT_TIMEOUT_SEC = 1800.0   # per step; a resumed session carries the whole journey's context


def task_toml(meta, layers, fmt_name) -> str:
    weights = ", ".join(f'{L["id"]} = {L["weight"]}' for L in layers)
    task_id = f"{meta['journey_id']}_v2" + ("_fhir" if fmt_name == "fhir" else "")
    out = [f'''schema_version = "1.4"
multi_step_reward_strategy = "mean"

[metadata]
id = "{task_id}"
title = "{meta['title']} ({'FHIR' if fmt_name == 'fhir' else 'narrative'})"
domain = "hematology_oncology"
subdomain = "lymphoma"
difficulty = "{meta.get('difficulty', 'advanced')}"
patient_type = "synthetic"
task_type = "clinical_reasoning_longitudinal"
input_format = "{'fhir_bundle_with_updates' if fmt_name == 'fhir' else 'narrative_chart'}"
oncoworld_version = "v2"
source = "cases_src/{meta['journey_id']}"
review_status = "{meta['review_status']}"
case_rule = "a dangerous error in any layer fails the whole case"
layer_weights = {{ {weights} }}

[agent]
timeout_sec = {AGENT_TIMEOUT_SEC}
''']
    for L in layers:
        out.append(f'''[[steps]]
name = "{L['step']}"

[steps.verifier]
timeout_sec = 300.0

[steps.verifier.env]
RESPONSE_FILE = "{L['answer_file']}"
ONCOWORLD_JUDGE_API_KEY = "${{ONCOWORLD_JUDGE_API_KEY:-}}"
ONCOWORLD_JUDGE_MODEL = "${{ONCOWORLD_JUDGE_MODEL:-}}"
ONCOWORLD_JUDGE_BASE_URL = "${{ONCOWORLD_JUDGE_BASE_URL:-https://openrouter.ai/api/v1}}"
ONCOWORLD_JUDGE_HEADERS = "${{ONCOWORLD_JUDGE_HEADERS:-}}"
ONCOWORLD_GRADER = "${{ONCOWORLD_GRADER:-regex}}"
''')
    return "\n".join(out)


# ---------------------------------------------------------------- FHIR update bundle for one later visit
def doc_date(doc) -> str:
    return doc["name"].split("_")[1]


def doc_title(doc) -> str:
    if doc["kind"] == "progress_note":
        return "Hematology-oncology clinic note"
    return doc["text"].strip().splitlines()[0].strip()


def render_update(layer: dict, case: dict, n: int) -> dict:
    """One FHIR R4 collection Bundle with everything new at this visit. References point at resources in the base bundle
    (same Patient, practitioner and laboratories), as an EHR export increment would."""
    gender = case["patient"]["gender"]
    p = case["meta"]["case_id"].replace("_", "-") + "-v2"
    PT, ONC = f"Patient/{p}-patient", f"Practitioner/{p}-hematologist"
    ORG = {k: f"Organization/{p}-{k}" for k in ("clinical-lab", "pathology-lab", "imaging")}
    u = f"{p}-{layer['id'].lower()}"
    F = layer.get("fhir", {})
    resources: list[dict] = []

    def add(res, summary):
        res["text"] = {"status": "generated", "div": f'<div xmlns="http://www.w3.org/1999/xhtml"><p>{escape(summary)}</p></div>'}
        resources.append(res)
        return res

    for o in F.get("organizations", []):
        ORG[o["id"]] = f"Organization/{p}-{o['id']}"
        add({"resourceType": "Organization", "id": f"{p}-{o['id']}", "active": True, "name": o["name"]}, f"{o['name']} (synthetic).")

    # notes and reports: the interval history first, then the rest in date order
    reports: dict[str, dict] = {}
    for doc in sorted(layer["documents"], key=lambda d: (d["kind"] != "interval_history", doc_date(d), d["name"])):
        rtype, code, _ = DOC_TYPES[doc["kind"]]
        date, title = doc_date(doc), doc_title(doc)
        att = {"contentType": "text/plain; charset=utf-8", "title": title,
               "data": base64.b64encode(doc["text"].strip().encode()).decode(), "creation": date}
        code_cc = cc(code, text=title) if code else {"text": title}
        rid = f"{u}-doc-{doc['name'][:2]}"
        dated = title if title.endswith(date) else f"{title}, {date}"
        if rtype == "DocumentReference":
            add({"resourceType": "DocumentReference", "id": rid, "meta": {"profile": [USC + "us-core-documentreference"]},
                 "status": "current", "docStatus": "final", "type": code_cc,
                 "category": [cc(("http://hl7.org/fhir/us/core/CodeSystem/us-core-documentreference-category", "clinical-note", "Clinical Note"))],
                 "subject": ref(PT), "date": f"{date}T{doc.get('time', '17:00')}:00Z", "author": [ref(ONC)],
                 "content": [{"attachment": att}]}, f"{dated} (text attached).")
        else:
            if doc["kind"] == "pathology_report":
                performer, category = ORG["pathology-lab"], cc((V2_0074, "SP", "Surgical Pathology"))
            elif doc["kind"] == "csf_report":
                performer, category = ORG["pathology-lab"], cc((V2_0074, "CP", "Cytopathology"))
            elif doc["kind"] == "ngs_report":
                performer, category = ORG["pathology-lab"], cc((V2_0074, "GE", "Genetics"))
            elif doc["kind"] == "echo_report":
                performer, category = ORG["imaging"], cc((LOINC, "LP29708-2", "Cardiology"))
            else:
                performer, category = ORG["imaging"], cc((LOINC, "LP29684-5", "Radiology"))
            reports[doc["kind"]] = add({
                "resourceType": "DiagnosticReport", "id": rid, "meta": {"profile": [USC + "us-core-diagnosticreport-note"]},
                "status": "final", "category": [category], "code": code_cc, "subject": ref(PT),
                "effectiveDateTime": date, "issued": date + "T16:00:00Z", "performer": [ref(performer)],
                "presentedForm": [att]}, f"{dated} (full report attached).")

    def obs(oid, code, display, category, when, summary, **value):
        return add({"resourceType": "Observation", "id": f"{u}-{oid}", "status": "final",
                    "category": [cc((OBS_CAT, category, category.replace("-", " ").title()))],
                    "code": cc((LOINC, code, display)), "subject": ref(PT), "effectiveDateTime": when, **value}, summary)

    if "ecog" in F:
        e = F["ecog"]
        obs("ecog", "89247-1", "ECOG Performance Status score", "survey", e["date"], f"ECOG performance status {e['value']}.",
            valueInteger=e["value"], performer=[ref(ONC)])
    if "weight" in F:
        w = F["weight"]
        obs("weight", "29463-7", "Body weight", "vital-signs", w["date"], f"Body weight {w['kg']} kg.", valueQuantity=qty(w["kg"], "kg", "kg"))
    if "gcs" in F:
        g = F["gcs"]
        obs("gcs", "9269-2", "Glasgow coma score total", "exam", f"{g['date']}T{g['time']}:00Z", f"Glasgow coma score {g['value']}.",
            valueInteger=g["value"])
    if "vitals" in F:
        v = F["vitals"]
        when = f"{v['date']}T{v['time']}:00Z"
        obs("temp", "8310-5", "Body temperature", "vital-signs", when, f"Temperature {v['temp_c']} C.", valueQuantity=qty(v["temp_c"], "C", "Cel"))
        obs("hr", "8867-4", "Heart rate", "vital-signs", when, f"Heart rate {v['hr']}/min.", valueQuantity=qty(v["hr"], "/min", "/min"))
        obs("bp", "85354-9", "Blood pressure panel with all children optional", "vital-signs", when,
            f"Blood pressure {v['sbp']}/{v['dbp']} mmHg.",
            component=[{"code": cc((LOINC, "8480-6", "Systolic blood pressure")), "valueQuantity": qty(v["sbp"], "mmHg", "mm[Hg]")},
                       {"code": cc((LOINC, "8462-4", "Diastolic blood pressure")), "valueQuantity": qty(v["dbp"], "mmHg", "mm[Hg]")}])
        obs("rr", "9279-1", "Respiratory rate", "vital-signs", when, f"Respiratory rate {v['rr']}/min.", valueQuantity=qty(v["rr"], "/min", "/min"))
        sp = obs("spo2", "2708-6", "Oxygen saturation in Arterial blood", "vital-signs", when,
                 f"SpO2 {v['spo2']}% on room air.", valueQuantity=qty(v["spo2"], "%", "%"))
        sp["code"]["coding"].append({"system": LOINC, "code": "59408-5", "display": "Oxygen saturation in Arterial blood by Pulse oximetry"})
    if "lvef" in F:
        lv = F["lvef"]
        res = obs("lvef", "10230-1", "Left ventricular Ejection fraction", "imaging", lv["date"], f"LVEF {lv['value']}%.",
                  valueQuantity=qty(lv["value"], "%", "%"))
        if "echo_report" in reports:
            reports["echo_report"]["result"] = [ref(f"Observation/{res['id']}")]

    for j, panel in enumerate(F.get("labs", []), 1):
        when = f"{panel['date']}T{panel.get('time', '08:00')}:00Z"
        hh, mm = map(int, panel.get("time", "08:00").split(":"))
        issued = f"{panel['date']}T{min(hh + (1 if 'time' in panel else 6), 23):02d}:{mm:02d}:00Z"
        result_refs = []
        for it in panel["items"]:
            key, val = it["key"], it["value"]
            code, long, short, unit, ucum, low, high = LABS[key]
            rid = f"{u}-lab-{j}-{key.replace('_', '-')}"
            res = {"resourceType": "Observation", "id": rid, "meta": {"profile": [USC + "us-core-observation-lab"]},
                   "status": "final", "category": [cc((OBS_CAT, "laboratory", "Laboratory"))], "code": cc((LOINC, code, long)),
                   "subject": ref(PT), "effectiveDateTime": when, "performer": [ref(ORG["clinical-lab"])],
                   "valueQuantity": qty(val, unit, ucum)}
            rr = {}
            if rng(low, gender) is not None:
                rr["low"] = qty(rng(low, gender), unit, ucum)
            if rng(high, gender) is not None:
                rr["high"] = qty(rng(high, gender), unit, ucum)
            if rr:
                res["referenceRange"] = [rr]
            flag = lab_flag(key, val, gender) or "N"
            res["interpretation"] = [cc((INTERP, flag, {"H": "High", "L": "Low", "N": "Normal"}[flag]))]
            add(res, f"{short}: {fmt(val)} {unit}" + (f" ({flag})" if flag != "N" else "") + f", {panel['date']}.")
            result_refs.append(ref("Observation/" + rid))
        add({"resourceType": "DiagnosticReport", "id": f"{u}-labpanel-{j}", "meta": {"profile": [USC + "us-core-diagnosticreport-lab"]},
             "status": "final", "category": [cc((V2_0074, "LAB", "Laboratory"))], "code": {"text": panel["panel"]},
             "subject": ref(PT), "effectiveDateTime": when, "issued": issued, "performer": [ref(ORG["clinical-lab"])],
             "result": result_refs}, f"{panel['panel']}, {panel['date']}.")

    # genomics: one variant Observation per finding, plus TMB and MSI, all linked from the NGS report
    gen_refs, gen_date = [], F.get("genomics_date", layer["date"])
    for i, v in enumerate(F.get("variants", []), 1):
        comps = [{"code": cc((LOINC, "48018-6", "Gene studied [ID]")),
                  "valueCodeableConcept": cc(("http://www.genenames.org/geneId", v["hgnc"], v["gene"]))},
                 {"code": cc((LOINC, "48019-4", "DNA change type")), "valueCodeableConcept": {"text": v["type"]}}]
        if v["dna"].startswith("c."):
            comps.insert(1, {"code": cc((LOINC, "48004-6", "DNA change (c.HGVS)")), "valueCodeableConcept": {"text": v["dna"]}})
        if v.get("protein"):
            comps.append({"code": cc((LOINC, "48005-3", "Amino acid change (pHGVS)")), "valueCodeableConcept": {"text": v["protein"]}})
        if v.get("vaf") is not None:
            comps.append({"code": cc((LOINC, "81258-6", "Sample variant allelic frequency [NFr]")),
                          "valueQuantity": {"value": round(v["vaf"] / 100, 2), "unit": "relative frequency", "system": "http://unitsofmeasure.org", "code": "1"}})
        res = obs(f"variant-{i}", "69548-6", "Genetic variant assessment", "laboratory", gen_date,
                  f"{v['gene']} {v.get('protein') or v['dna']} ({v['type']})" + (f", VAF {v['vaf']}%." if v.get("vaf") is not None else "."),
                  valueCodeableConcept=cc((LOINC, "LA9633-4", "Present")), component=comps)
        if not v["dna"].startswith("c."):
            res["note"] = [{"text": f"{v['gene']} {v['dna']}"}]
        gen_refs.append(ref(f"Observation/{res['id']}"))
    if "tmb" in F:
        res = obs("tmb", "94076-7", "Mutations/Megabase [# Ratio] in Tumor", "laboratory", gen_date,
                  f"Tumor mutational burden {F['tmb']} mutations/Mb.", valueQuantity={"value": F["tmb"], "unit": "mutations/Mb", "system": "http://unitsofmeasure.org", "code": "1/1000000{Base}"})
        gen_refs.append(ref(f"Observation/{res['id']}"))
    if "msi" in F:
        res = obs("msi", "81695-9", "Microsatellite instability [Interpretation] in Cancer specimen Qualitative", "laboratory", gen_date,
                  f"Microsatellite {F['msi']}.", valueCodeableConcept={"text": f"Microsatellite {F['msi']}"})
        gen_refs.append(ref(f"Observation/{res['id']}"))
    if gen_refs and "ngs_report" in reports:
        reports["ngs_report"]["result"] = gen_refs

    def period(x):
        out = {}
        if x.get("start"):
            out["start"] = x["start"]
        if x.get("end"):
            out["end"] = x["end"]
        return out

    for i, m in enumerate(F.get("medications", []), 1):
        res = {"resourceType": "MedicationStatement", "id": m.get("id") or f"{u}-med-{i}", "status": m["status"],
               "medicationCodeableConcept": {"text": m["text"]}, "subject": ref(PT), "dosage": [{"text": m["text"]}]}
        if m.get("id"):   # a later version of a resource the record already holds
            res["meta"] = {"lastUpdated": layer["date"] + "T12:00:00Z"}
        if period(m):
            res["effectivePeriod"] = period(m)
        if m.get("note"):
            res["note"] = [{"text": m["note"]}]
        add(res, f"Medication ({m['status']}): {m['text']}.")
    for i, a in enumerate(F.get("administrations", []), 1):
        if a.get("start"):   # dated: a real administration record
            res = {"resourceType": "MedicationAdministration", "id": f"{u}-admin-{i}", "status": "completed",
                   "medicationCodeableConcept": {"text": a["text"]}, "subject": ref(PT)}
            res.update({"effectivePeriod": period(a)} if a.get("end") else {"effectiveDateTime": a["start"]})
            if a.get("performer"):
                res["performer"] = [{"actor": ref(ORG[a["performer"]])}]
        else:                # undated history ("before lymphodepletion"): a completed medication statement
            res = {"resourceType": "MedicationStatement", "id": f"{u}-admin-{i}", "status": "completed",
                   "medicationCodeableConcept": {"text": a["text"]}, "subject": ref(PT)}
        if a.get("note") or a.get("when"):
            res["note"] = [{"text": a.get("note") or a["when"]}]
        when = (a["start"] + (f" to {a['end']}" if a.get("end") else "")) if a.get("start") else a["when"]
        add(res, f"Given: {a['text']} ({when}).")
    for i, pr in enumerate(F.get("procedures", []), 1):
        res = {"resourceType": "Procedure", "id": f"{u}-proc-{i}", "meta": {"profile": [USC + "us-core-procedure"]},
               "status": "completed", "code": {"text": pr["text"]}, "subject": ref(PT)}
        res.update({"performedDateTime": pr["date"]} if pr.get("date") else {"performedString": pr["when"]})
        if pr.get("performer"):
            res["performer"] = [{"actor": ref(ORG[pr["performer"]])}]
        add(res, f"Procedure: {pr['text']} ({pr.get('date') or pr.get('when')}).")
    for i, rq in enumerate(F.get("requests", []), 1):
        res = {"resourceType": "MedicationRequest", "id": f"{u}-request-{i}", "status": "active", "intent": "plan",
               "medicationCodeableConcept": {"text": rq["text"]}, "subject": ref(PT), "requester": ref(ONC)}
        if rq.get("note"):
            res["note"] = [{"text": rq["note"]}]
        add(res, f"Planned medication: {rq['text']}.")
    for i, c in enumerate(F.get("conditions", []), 1):
        res = {"resourceType": "Condition", "id": f"{u}-condition-{i}", "meta": {"profile": [USC + "us-core-condition-problems-health-concerns"]},
               "clinicalStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active")),
               "verificationStatus": cc(("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "Confirmed")),
               "category": [cc(("http://terminology.hl7.org/CodeSystem/condition-category", "problem-list-item", "Problem List Item"))],
               "code": {"text": c["text"]}, "subject": ref(PT)}
        if c.get("note"):
            res["note"] = [{"text": c["note"]}]
        add(res, f"Problem: {c['text']}.")

    return {"resourceType": "Bundle", "id": f"{p}-update-{n:02d}", "meta": {"security": [HTEST]},
            "identifier": {"system": BASE + "/sid/bundle", "value": f"{p}-update-{n:02d}"}, "type": "collection",
            "timestamp": f"{layer['date']}T{F.get('export_time', '18:00')}:00Z",
            "entry": [{"fullUrl": f"{BASE}/{r['resourceType']}/{r['id']}", "resource": r} for r in resources]}


def bundle_visible(name: str, bundle: dict) -> dict[str, str]:
    """What the model can read from a bundle: the JSON itself and every base64 attachment decoded."""
    out = {name: json.dumps(bundle, ensure_ascii=False)}
    for e in bundle["entry"]:
        r = e["resource"]
        for att in [c["attachment"] for c in r.get("content", [])] + r.get("presentedForm", []):
            out[f"{name}#{r['id']}"] = base64.b64decode(att["data"]).decode()
    return out


# ---------------------------------------------------------------- build
def write_step_tests(step: Path, rubric_path: Path, gold: dict, extra: Path, probes: Path):
    tests = step / "tests"
    (tests / "selftest" / "answers").mkdir(parents=True)
    shutil.copy(GRADER_DIR / "grader_v2.py", tests / "grader_v2.py")
    shutil.copy(GRADER_DIR / "test.sh", tests / "test.sh")
    shutil.copy(rubric_path, tests / "rubric_v2.toml")
    shutil.copy(GRADER_DIR / "run_selftest.py", tests / "selftest" / "run_selftest.py")
    (tests / "selftest" / "answers" / "01_reference.json").write_text(
        json.dumps(dict(gold, _expect={"passed": True, "dangerous": [], "all_met": True}), indent=2, ensure_ascii=False) + "\n")
    for f in sorted(extra.glob("*.json")) if extra.exists() else []:
        shutil.copy(f, tests / "selftest" / "answers" / f.name)
    if probes.exists():
        shutil.copy(probes, tests / "selftest" / "probes.json")


def build(src: Path):
    j = tomllib.loads((src / "journey.toml").read_text())
    meta, layers = j["meta"], j["layers"]
    base = ROOT / "cases_src" / meta["base_case"]
    case = tomllib.loads((base / "case.toml").read_text())

    for fmt_name in ("fhir", "narrative"):
        if fmt_name == "fhir":
            out = ROOT / "harbor_cases" / f"{meta['journey_id']}_v2_fhir"
            base_bundle = render_fhir(case)
            env_files = {"fhir_bundle.json": json.dumps(base_bundle, indent=2, ensure_ascii=False) + "\n"}
            visible = bundle_visible("fhir_bundle.json", base_bundle)
        else:
            out = ROOT / "harbor_cases_narrative" / f"{meta['journey_id']}_v2"
            env_files = {f"chart/{k}": v for k, v in render_narrative(case).items()}
            visible = dict(env_files)
        if out.exists():
            shutil.rmtree(out)
        for rel, text in env_files.items():
            (out / "environment" / "case" / rel).parent.mkdir(parents=True, exist_ok=True)
            (out / "environment" / "case" / rel).write_text(text)
        (out / "environment" / "Dockerfile").write_text(DOCKERFILE.replace(
            "RUN mkdir -p /app/outputs /logs/verifier", "RUN mkdir -p /app/outputs /app/answers /logs/verifier"))
        (out / "task.toml").write_text(task_toml(meta, layers, fmt_name))
        (out / "README.md").write_text(
            f"# {meta['title']} ({fmt_name})\n\nGenerated by scripts/build_journey_v2.py from cases_src/{meta['journey_id']}. "
            f"Review status: {meta['review_status']}.\n\nCross-layer consistency notes (hidden):\n{meta['consistency_notes']}")

        for n, L in enumerate(layers):
            step = out / "steps" / L["step"]
            step.mkdir(parents=True)
            if L.get("source"):
                rubric_path, gold = base / "rubric_v2.toml", json.loads((base / "gold.json").read_text())
                instruction = (INSTRUCTION.format(where=WHERE[fmt_name])
                               .replace("/app/final_answer.json", L["answer_file"])
                               .replace("It is not clinical decision support.\n", "It is not clinical decision support.\n" + FIRST_VISIT))
                extra, probes = base / "selftest" / "answers", base / "selftest" / "probes.json"
            else:
                rubric_path, gold = src / f"{L['id']}_rubric.toml", json.loads((src / f"{L['id']}_gold.json").read_text())
                keys = [f"q{i}" for i in range(1, len(L["questions"]) + 1)]
                assert sorted(gold) == keys, f"{L['id']} gold keys {sorted(gold)} != {keys}"
                if fmt_name == "fhir":
                    update_name = f"{n:02d}_{L['date']}_update.json"
                    bundle = render_update(L, case, n)
                    p = step / "workdir" / "case" / "fhir_updates" / update_name
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
                    visible |= bundle_visible(f"fhir_updates/{update_name}", bundle)
                    where = LATER_WHERE["fhir"].format(update=update_name)
                else:
                    for doc in L["documents"]:
                        p = step / "workdir" / "case" / "chart" / doc["name"]
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_text(doc["text"].strip() + "\n")
                        visible[f"chart/{doc['name']}"] = doc["text"]
                    where = LATER_WHERE["narrative"].format(first=L["documents"][0]["name"][:1])
                instruction = LATER_INSTRUCTION.format(
                    date=L["date"], heading=L["heading"].lower(), where=where, answer_file=L["answer_file"],
                    questions="\n".join(f"{i}. ({k}) {q}" for i, (k, q) in enumerate(zip(keys, L["questions"]), 1)),
                    keys=", ".join(f"`{k}`" for k in keys))
                extra, probes = src / "selftest" / L["id"], src / "selftest" / "probes" / f"{L['id']}.json"
            rubric = tomllib.loads(rubric_path.read_text())
            # everything the model can see at this step (earlier layers stay on disk), checked against THIS layer's terms
            leak_check(rubric, visible | {"instruction.md": instruction}, f"{out.name}/{L['step']}")
            gold_check(gold, rubric)
            (step / "instruction.md").write_text(instruction)
            (step / "solution").mkdir()
            (step / "solution" / "final_answer.json").write_text(json.dumps(gold, indent=2, ensure_ascii=False) + "\n")
            (step / "solution" / "solve.sh").write_text(SOLVE.format(answer_file=L["answer_file"]))
            (step / "solution" / "solve.sh").chmod(0o755)
            write_step_tests(step, rubric_path, gold, extra, probes)
            ctx = judge_context(base) if L.get("source") else (
                f"Journey stage {L['id']} ({L['date']}), same patient later in the disease course. This visit's records:\n\n"
                + "\n\n".join(d["text"].strip() for d in L["documents"]))
            (step / "tests" / "judge_context.txt").write_text(ctx + "\n")
            print(f"built {out.relative_to(ROOT)}/steps/{L['step']} (weight {L['weight']}%)")


def main():
    wanted = set(sys.argv[1:])
    for src in sorted((ROOT / "cases_src").iterdir()):
        if (src / "journey.toml").exists() and (not wanted or src.name in wanted):
            build(src)


if __name__ == "__main__":
    main()
