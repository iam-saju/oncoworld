#!/usr/bin/env python3
"""Generate the Phase 2 PDF reports into reports/.

Usage: <python with reportlab> scripts/make_reports.py

  reports/cases/<case>_v2_case_pack.pdf      one per v2 case: model-visible chart, task, reference answer, rubric,
                                              review questions (CONFIDENTIAL: contains the answer key)
  reports/cases/dlbcl_0003_journey_v2_case_pack.pdf
  reports/oncoworld_phase2_final_analysis.pdf the final analysis (assessment, what changed, results, per-case review)

All numbers are recomputed when the script runs: grader results come from grader_v2 on the self-test answers, and the
oracle results are read from jobs/. Only the per-case narrative analysis (CASE_NOTES) is written by hand.
Needs reportlab (not a repo dependency): python3 -m venv .venv && .venv/bin/pip install reportlab
"""
from __future__ import annotations

import datetime
import json
import sys
import tomllib
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "graders" / "oncoworld_grader"))
from build_cases_v2 import INSTRUCTION, WHERE, render_narrative  # noqa: E402
from grader_v2 import score  # noqa: E402

OUT = ROOT / "reports"
TODAY = datetime.date.today().isoformat()
CASES = ["dlbcl_0001", "dlbcl_0002", "dlbcl_0003", "dlbcl_0004", "dlbcl_0005"]

# ---------------------------------------------------------------- fonts and styles
pdfmetrics.registerFont(TTFont("Body", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"))
pdfmetrics.registerFont(TTFont("BodyBold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Mono", "/System/Library/Fonts/Menlo.ttc", subfontIndex=0))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="BodyBold", italic="Body", boldItalic="BodyBold")

INK, MUTED, ACCENT, DANGER, LINE, SOFT = (colors.HexColor(c) for c in
                                          ("#1d2733", "#5b6573", "#1f5f8b", "#b3261e", "#d5dbe3", "#f2f5f8"))
base = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("title", parent=base["Title"], fontName="BodyBold", fontSize=22, leading=27, textColor=INK, alignment=0),
    "subtitle": ParagraphStyle("subtitle", fontName="Body", fontSize=11.5, leading=15, textColor=MUTED),
    "h1": ParagraphStyle("h1", fontName="BodyBold", fontSize=15, leading=19, textColor=ACCENT, spaceBefore=14, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="BodyBold", fontSize=11.5, leading=15, textColor=INK, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="Body", fontSize=9.5, leading=13.2, textColor=INK, spaceAfter=5),
    "small": ParagraphStyle("small", fontName="Body", fontSize=8, leading=10.5, textColor=MUTED),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=8, leading=10.2, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="BodyBold", fontSize=8, leading=10.2, textColor=INK),
    "bullet": ParagraphStyle("bullet", fontName="Body", fontSize=9.5, leading=13, textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=2),
    "mono": ParagraphStyle("mono", fontName="Mono", fontSize=6.9, leading=8.6, textColor=INK),
    "banner": ParagraphStyle("banner", fontName="BodyBold", fontSize=9, leading=12, textColor=colors.white, alignment=TA_CENTER),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def E(text):
    return escape(str(text))


def bullets(items, style="bullet"):
    return [Paragraph(t, S[style], bulletText="•") for t in items]


def table(rows, widths, header=True, zebra=True, font_rows=None):
    data = [[c if not isinstance(c, str) else Paragraph(c, S["cellb" if header and i == 0 else "cell"]) for c in r]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), SOFT))
    if zebra:
        for i in range(2 if header else 1, len(rows), 2):
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fafbfc")))
    t.setStyle(TableStyle(style))
    return t


def banner(text, color=DANGER):
    t = Table([[Paragraph(text, S["banner"])]], colWidths=[174 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), color), ("TOPPADDING", (0, 0), (-1, -1), 5),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def mono_block(text, width=108):
    lines = []
    for ln in text.rstrip().splitlines():
        while len(ln) > width:
            cut = ln.rfind(" ", 0, width)
            cut = cut if cut > 40 else width
            lines.append(ln[:cut])
            ln = "    " + ln[cut:].lstrip()
        lines.append(ln)
    return Preformatted("\n".join(lines), S["mono"])


def doc(path: Path, title: str, footer: str):
    path.parent.mkdir(parents=True, exist_ok=True)

    def on_page(canvas, d):
        canvas.saveState()
        canvas.setFont("Body", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, footer)
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {d.page}")
        canvas.restoreState()

    d = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                          bottomMargin=17 * mm, title=title, author="OncoWorld engineering",
                          subject="Synthetic oncology evaluation case. Not clinical decision support.")
    return d, on_page


# ---------------------------------------------------------------- data
def load_case(cid):
    src = ROOT / "cases_src" / cid
    case = tomllib.loads((src / "case.toml").read_text())
    rubric = tomllib.loads((src / "rubric_v2.toml").read_text())
    gold = json.loads((src / "gold.json").read_text())
    selftests = []
    for f in sorted((src / "selftest" / "answers").glob("*.json")):
        d = json.loads(f.read_text())
        expect = d.pop("_expect")
        r = score(json.dumps(d, ensure_ascii=False, indent=1), rubric)
        selftests.append({"name": f.stem, "reward": r["reward"], "passed": r["passed"], "dangerous": r["dangerous_errors"],
                          "expected_pass": expect["passed"]})
    return {"id": cid, "src": src, "case": case, "rubric": rubric, "gold": gold, "selftests": selftests,
            "task": f"{cid}_{case['meta']['slug']}_v2"}


def v1_task_dirs(cid):
    return sorted(p for p in (ROOT / "harbor_cases_narrative").glob(f"{cid}_*") if "_v2" not in p.name and p.name.endswith("_narrative"))


def oracle_rows(job):
    rows = []
    for tr in sorted((ROOT / "jobs" / job).glob("*/result.json")):
        t = json.loads(tr.read_text())
        if t.get("step_results"):
            rewards = [s["verifier_result"]["rewards"]["reward"] for s in t["step_results"] if s.get("verifier_result")]
            rows.append((t["task_name"], f"{len(rewards)} steps, all {min(rewards):.2f}" if rewards else "no result"))
        else:
            rw = (t.get("verifier_result") or {}).get("rewards", {}).get("reward")
            rows.append((t["task_name"], "error" if rw is None else f"{rw:.2f}"))
    return rows


# ---------------------------------------------------------------- hand-written analysis
CASE_NOTES = {
    "dlbcl_0001": {
        "short": "Occult hepatitis B (HBsAg-, anti-HBc+) before rituximab",
        "patient": "62-year-old man, ECOG 1. Cervical, mediastinal and 11 cm retroperitoneal nodes, splenic lesions, B symptoms.",
        "teaching": "Spleen is lymphatic tissue, so this is stage III, not IV. Double-expressor by IHC is not double-hit when FISH is negative.",
        "twist": "Hepatitis B serology: HBsAg nonreactive but anti-HBc reactive (resolved/occult infection). HBV DNA not sent; nothing in the chart comments on it.",
        "decisions": ["Lugano stage III, bulky, B symptoms; IPI 3, CNS-IPI 3", "Pola-R-CHP x6 preferred (R-CHOP x6 acceptable)",
                      "Entecavir or tenofovir before the first rituximab dose, continued at least 12 months after (dangerous if missed)",
                      "No routine CNS prophylaxis; end-of-treatment PET-CT with Lugano/Deauville"],
        "review": ["Mandating CNS prophylaxis at CNS-IPI 3 costs 5 points but is not dangerous; the answer still passes at 0.90.",
                   "TLS: gold gives allopurinol and hydration; Cairo-Bishop could classify this as high risk, which calls for rasburicase.",
                   "HBV monitoring alone, without prophylaxis, is graded dangerous."],
    },
    "dlbcl_0002": {
        "short": "Prior doxorubicin 240 mg/m² + chest RT; LVEF 62% → 45%",
        "patient": "59-year-old woman, ECOG 1. Axillary, mediastinal, mesenteric and para-aortic nodes with splenic nodules; fevers and night sweats.",
        "teaching": "Splenic involvement with nodes on both sides of the diaphragm is stage III, and the spleen is not an extranodal IPI site (IPI 2).",
        "twist": "Breast cancer in 2016 treated with doxorubicin (240 mg/m² cumulative) and left chest radiotherapy. LVEF has fallen from 62% to 45%, GLS -14%, with no heart-failure symptoms.",
        "decisions": ["Cancer therapy-related cardiac dysfunction: do not give standard full-dose doxorubicin (dangerous to ignore)",
                      "Urgent cardio-oncology review; ACE inhibitor/ARB plus beta-blocker",
                      "Curative anthracycline-free regimen: R-CEOP preferred, R-GCVP as alternative; R-CHOP with liposomal doxorubicin or dexrazoxane only with cardio-oncology agreement",
                      "Serial LVEF and troponin/NT-proBNP; end-of-treatment PET-CT"],
        "review": ["Which regimen does the oncologist prefer: R-CEOP, R-GCVP, or cardioprotected R-CHOP?",
                   "Should cardiac MRI or an ischemic work-up be required?",
                   "Anastrozole: continuing it and holding it are both accepted."],
    },
    "dlbcl_0003": {
        "short": "TLS risk: uric acid and creatinine rising, on ibuprofen; no CNS staging",
        "patient": "67-year-old man, ECOG 2, type 2 diabetes. Retroperitoneal/mesenteric mass with kidney, adrenal and liver lesions.",
        "teaching": "Stage IV. IPI 5, CNS-IPI 6: kidney/adrenal involvement means high CNS-relapse risk.",
        "twist": "Uric acid rising (9.8 to 10.4), creatinine rising (1.1 to 1.5), LDH more than 5x ULN, taking ibuprofen four times daily, no CNS staging done.",
        "decisions": ["TLS prophylaxis: hydration, rasburicase after G6PD check, frequent labs, inpatient cycle 1 (dangerous if missed)",
                      "Prednisone prephase, then Pola-R-CHP x6 at full dose; G-CSF; stop NSAIDs",
                      "MRI brain plus CSF cytology and flow cytometry; HD-MTX optional and deferred until renal recovery",
                      "ECOG 2 is caused by the disease, so it is not a reason to reduce doses"],
        "review": ["R-mini-CHOP for this patient is graded as failing to give full-dose curative therapy (dangerous). Is that too harsh?",
                   "Should the steroid prephase be mandatory?"],
    },
    "dlbcl_0004": {
        "short": "Late FISH addendum: double-hit, after an R-CHOP plan was charted",
        "patient": "54-year-old man, ECOG 1. Right cervical nodes and a 12 cm anterior mediastinal mass narrowing the SVC; above the diaphragm only.",
        "teaching": "FISH, not morphology or IHC, defines double-hit lymphoma.",
        "twist": "Pathology was signed out as DLBCL NOS and an R-CHOP plan was documented. A later FISH addendum shows MYC and BCL2 rearrangements; the problem list was never updated.",
        "decisions": ["Revise the diagnosis to HGBL with MYC and BCL2 rearrangements (dangerous if missed)",
                      "Cancel the outdated R-CHOP plan; DA-EPOCH-R x6 or a clinical trial",
                      "Bulky stage II, IPI 1, but double-hit biology dominates the risk",
                      "MRI brain and CSF; CNS prophylaxis considered; mandatory G-CSF; TLS measures; sperm banking"],
        "review": ["R-CHOP alone as the preferred regimen costs points but is not dangerous. Is that right for bulky stage II double-hit disease?",
                   "An extra must-not (dangerous) was added for dismissing CNS risk because of a low CNS-IPI. Keep it?"],
    },
    "dlbcl_0005": {
        "short": "Migraine with aura on estrogen pill; no pregnancy test; avoid neck RT",
        "patient": "45-year-old woman, ECOG 0, teacher. Single right cervical nodal region (3.1 cm), no B symptoms.",
        "teaching": "Limited-stage, low-risk disease, where less treatment is the right answer.",
        "twist": "She has migraine with aura and takes a combined estrogen pill (contraindicated). No pregnancy test is documented. She wants to avoid neck radiotherapy.",
        "decisions": ["Lugano stage IA, IPI 0, CNS-IPI 0; no marrow biopsy needed after PET",
                      "FLYER: R-CHOP x4 plus rituximab x2, no radiotherapy, which also matches her goals",
                      "Pregnancy test before treatment; stop the estrogen pill and switch to non-estrogen contraception",
                      "Six cycles, Pola-R-CHP or DA-EPOCH-R are overtreatment"],
        "review": ["Six cycles of R-CHOP costs 16 points, enough to fail an otherwise good answer (0.74), but it is not dangerous. Agree?",
                   "Missing the pregnancy test and the contraception change together fails the case but is not dangerous. Agree?"],
    },
}


# ---------------------------------------------------------------- case packs
def case_pack(c):
    meta, case, rubric, gold = c["case"]["meta"], c["case"], c["rubric"], c["gold"]
    notes = CASE_NOTES[c["id"]]
    path = OUT / "cases" / f"{c['task']}_case_pack.pdf"
    d, on_page = doc(path, f"OncoWorld {c['id']} v2 case pack", f"OncoWorld {c['task']} · synthetic case · CONFIDENTIAL answer key · {TODAY}")
    st = [banner("CONFIDENTIAL: contains the reference answer and rubric. Never place this document where a model can read it."),
          Spacer(1, 8), P(f"{E(c['id'])} · v2 case pack", "subtitle"), P(E(meta["title"]), "title"),
          P(f"Difficulty: {E(meta['difficulty'])} · Chart exported {E(meta['record_date'])} · Review status: "
            f"<b>{E(meta['review_status'])}</b> · Harbor tasks: {E(c['task'])}_narrative, {E(c['task'])}_fhir", "small"),
          Spacer(1, 6),
          table([["Item", "Summary"], ["Patient", E(notes["patient"])], ["Core teaching point", E(notes["teaching"])],
                 ["Real-world twist", E(notes["twist"])],
                 ["Key decisions", "<br/>".join("• " + E(x) for x in notes["decisions"])],
                 ["For the oncologist", "<br/>".join("• " + E(x) for x in notes["review"])]], [38 * mm, 136 * mm]),
          P("Synthetic training case for AI evaluation. Not clinical decision support. No real patient data.", "small"),
          PageBreak(), P("A. Task instruction (model-visible)", "h1"),
          mono_block(INSTRUCTION.format(where=WHERE["narrative"])),
          P("B. Patient chart (model-visible, narrative rendering)", "h1"),
          P("The FHIR rendering carries the same facts, generated from the same source file "
            f"(cases_src/{E(c['id'])}/case.toml). Files appear in chronological order, as the model sees them.", "small")]
    for name, text in render_narrative(case).items():
        st += [P(f"chart/{E(name)}", "h2"), mono_block(text)]
    st += [PageBreak(), P("C. Reference answer (hidden from the model)", "h1")]
    for k, v in gold.items():
        body = "<br/>".join("• " + E(x) for x in v) if isinstance(v, list) else E(v)
        st.append(KeepTogether([P(E(k), "h2"), P(body)]))
    items = rubric["items"]
    pos = sum(i["points"] for i in items if i["kind"] != "must_not")
    st += [PageBreak(), P("D. Grading rubric (hidden from the model)", "h1"),
           P(f"Rubric {E(rubric.get('version'))}. Must and should items total {pos} points; pass threshold "
             f"{rubric.get('passing_score')}. A <b>dangerous</b> item fails the case (reward 0) when a must item is missed "
             "or a must-not item is committed. Points for must-not items are deductions.")]
    rows = [["ID", "Kind", "Severity", "Pts", "Criterion (what the judge reads)"]]
    for i in items:
        sev = f'<font color="#b3261e"><b>{E(i["severity"])}</b></font>' if i["severity"] == "dangerous" else E(i["severity"])
        rows.append([E(i["id"]), E(i["kind"]), sev, str(i["points"]), E(i["text"])])
    st.append(table(rows, [36 * mm, 15 * mm, 17 * mm, 9 * mm, 97 * mm]))
    st += [P("E. Grader self-tests (regex mode, recomputed now)", "h1"),
           P("Each adversarial answer must produce its expected verdict. 01_reference is the gold answer.")]
    rows = [["Answer", "Reward", "Passed", "Expected", "Dangerous errors fired"]]
    for t in [{"name": "01_reference", "reward": 1.0, "passed": True, "dangerous": [], "expected_pass": True}] + c["selftests"]:
        rows.append([E(t["name"]), f"{t['reward']:.2f}", "yes" if t["passed"] else "no",
                     "pass" if t["expected_pass"] else "fail", E(", ".join(t["dangerous"]) or "-")])
    st.append(table(rows, [52 * mm, 16 * mm, 15 * mm, 17 * mm, 74 * mm]))
    st += [P("F. Reviewer sign-off", "h1"),
           table([["Reviewer", "Credentials", "Date", "Verdict", "Changes requested"], ["", "", "", "", ""]],
                 [34 * mm, 30 * mm, 22 * mm, 30 * mm, 58 * mm])]
    d.build(st, onFirstPage=on_page, onLaterPages=on_page)
    return path


def journey_pack():
    src = ROOT / "cases_src" / "dlbcl_0003_journey"
    j = tomllib.loads((src / "journey.toml").read_text())
    path = OUT / "cases" / "dlbcl_0003_journey_v2_case_pack.pdf"
    d, on_page = doc(path, "OncoWorld dlbcl_0003 journey case pack", f"OncoWorld dlbcl_0003_journey_v2 · synthetic case · CONFIDENTIAL answer key · {TODAY}")
    st = [banner("CONFIDENTIAL: contains reference answers and rubrics. Layers 2-5 are DRAFTS awaiting oncologist review."),
          Spacer(1, 8), P("dlbcl_0003_journey · v2 longitudinal case pack", "subtitle"), P(E(j["meta"]["title"]), "title"),
          P("One Harbor multi-step task. The model sees one layer at a time. Each new layer's documents are uploaded only "
            "when that step starts, and each opens with what actually happened, so an early mistake does not spoil later "
            "layers. Each layer is scored on its own; a dangerous error in any layer fails the case.")]
    rows = [["Layer", "Date", "Weight", "Situation"]]
    for L in j["layers"]:
        rows.append([E(L["id"]), E(L["date"]), f"{L['weight']}%", E(L.get("heading", "Diagnosis and tumor-board plan (the v2 dlbcl_0003 chart)"))])
    st += [table(rows, [16 * mm, 24 * mm, 16 * mm, 118 * mm]), P("Cross-layer consistency checks", "h2"),
           *bullets([E(x.lstrip("- ")) for x in j["meta"]["consistency_notes"].strip().splitlines()])]
    st += [P("Layer 1 uses the dlbcl_0003 v2 chart, reference answer and rubric; see that case pack.", "small")]
    for L in j["layers"][1:]:
        rubric = tomllib.loads((src / f"{L['id']}_rubric.toml").read_text())
        gold = json.loads((src / f"{L['id']}_gold.json").read_text())
        st += [PageBreak(), P(f"{E(L['id'])} · {E(L['heading'])} ({E(L['date'])}, weight {L['weight']}%)", "h1"),
               P("New documents (model-visible)", "h2")]
        for doc_ in L["documents"]:
            st += [P(f"chart/{E(doc_['name'])}", "small"), mono_block(doc_["text"].strip())]
        st += [P("Questions", "h2"), *bullets([f"<b>q{i}</b> {E(q)}" for i, q in enumerate(L["questions"], 1)]),
               P("Reference answer (hidden)", "h2")]
        st += [P(f"<b>{E(k)}</b> {E(v)}") for k, v in gold.items()]
        rows = [["ID", "Kind", "Severity", "Pts", "Criterion"]]
        for i in rubric["items"]:
            sev = f'<font color="#b3261e"><b>{E(i["severity"])}</b></font>' if i["severity"] == "dangerous" else E(i["severity"])
            rows.append([E(i["id"]), E(i["kind"]), sev, str(i["points"]), E(i["text"])])
        st += [P("Rubric (hidden)", "h2"), table(rows, [36 * mm, 15 * mm, 17 * mm, 9 * mm, 97 * mm])]
    d.build(st, onFirstPage=on_page, onLaterPages=on_page)
    return path


# ---------------------------------------------------------------- final analysis
def final_report(cases):
    path = OUT / "oncoworld_phase2_final_analysis.pdf"
    d, on_page = doc(path, "OncoWorld Phase 2 final analysis", f"OncoWorld · Phase 2 final analysis · {TODAY}")
    v1_rows, n_suites, n_answers, n_ok = [], 0, 0, 0
    for c in cases:
        v1 = next((t for t in c["selftests"] if t["name"] == "v1_gold_answer"), None)
        v1_rows.append([E(c["id"]), E(CASE_NOTES[c["id"]]["short"]),
                        f"{v1['reward']:.2f}" if v1 else "-", E(", ".join(v1["dangerous"]) or "none (fails on points)") if v1 else "-"])
        n_answers += len(c["selftests"]) + 1
        n_ok += 1 + sum(t["passed"] == t["expected_pass"] for t in c["selftests"])
    n_suites = len(list(ROOT.glob("harbor_cases*/*_v2_*/tests/selftest"))) + len(list((ROOT / "harbor_cases_narrative").glob("*_journey_v2/steps/*/tests/selftest")))
    o1, o2 = oracle_rows("v1_oracle_reweighted_2026-10-19"), oracle_rows("v2_oracle_all_2026-10-19")

    st = [P("OncoWorld · Harbor oncology evaluation harness", "subtitle"), P("Phase 2 final analysis: clinically realistic cases", "title"),
          P(f"{TODAY} · Prepared by engineering · Status: built and oracle-verified; <b>clinical content awaiting oncologist sign-off</b>", "small"),
          Spacer(1, 8), banner("No v2 score should be reported as clinical performance until an oncologist signs off the reference answers.", ACCENT),
          P("1. Summary", "h1"),
          P("OncoWorld v1 had a sound harness: Docker sandboxes, a hidden verifier, and narrative and FHIR versions of each case. "
            "But its cases were short, pre-interpreted bullet lists, each built around a single teaching point, and its regex "
            "graders scored wording more than reasoning. Phase 2 rebuilds the same five DLBCL patients as realistic charts and adds a "
            "five-layer longitudinal journey. Grading now uses atomic rubric items with severities, so a single dangerous error "
            "fails the case."),
          *bullets([
              "<b>Realism:</b> 10-14 dated documents per case (referral, consult, radiology, pathology with FISH addendum, labs with "
              "reference ranges, medications, distractor comorbidities). Narrative and FHIR versions are generated from one source and cannot disagree.",
              "<b>Decision-changing twists</b> taken from real practice: occult hepatitis B, anthracycline cardiotoxicity, tumour-lysis risk "
              "with rising creatinine and NSAID use, a double-hit FISH addendum that arrives after a plan already exists, and a "
              "contraindicated contraceptive.",
              "<b>The v1 reference answers fail the v2 bar.</b> Graded against the v2 rubrics, three score 0.00 because they miss a dangerous "
              "item (HBV prophylaxis, cardiac function, TLS prophylaxis), and the other two score 0.47 and 0.43. That gap is what the new cases test.",
              f"<b>Verified:</b> {n_suites} self-test suites pass ({n_ok}/{n_answers} case-level verdicts as expected). Harbor oracle runs: "
              f"v1 {sum(r[1] == '1.00' for r in o1)}/{len(o1)} and v2 {sum(r[1].startswith(('1.00', '5 steps')) for r in o2)}/{len(o2)} "
              "trials at full score (v2 includes the 5-step journey).",
              "<b>Not yet done:</b> oncologist sign-off, a funded-model baseline, and measuring how well the LLM judge agrees with the oncologist.",
          ]),
          P("2. Assessment of v1 (the starting point)", "h1"), P("Workflow in use", "h2"),
          *bullets(["Write a short bullet-point case (history, labs, imaging, pathology).",
                    "Generate a matching FHIR R4/mCODE bundle from a hard-coded Python dictionary.",
                    "Write a gold answer, a rubric and a regex grader per case (11 copies, 6 different versions).",
                    "Run oracle, then Gemini CLI / OpenCode models, mostly on free tiers.",
                    "Read review.json, patch regexes when correct wording was marked wrong, and add the answer to the self-tests."]),
          P("What blocked trust", "h2"),
          table([["Problem", "Effect"],
                 ["No valid baseline under the 2026-10-13 weights; many runs failed on 429/503 errors and setup timeouts", "No model score could be reported"],
                 ["No physician sign-off; the spleen staging rule was still marked 'to confirm'", "Gold answers were engineering opinion"],
                 ["Regex graders patched 6 times and still brittle to paraphrase and negation", "Scores partly measured wording"],
                 ["11 copy-pasted graders", "Fixes did not propagate between cases"]], [100 * mm, 74 * mm]),
          P("Where v1 departed from real practice", "h2"),
          *bullets(["No past history, medications, allergies or reference ranges; findings arrived pre-interpreted ('LDH elevated').",
                    "The narrative and FHIR versions disagreed: the narrative said 'elevated' while the FHIR bundle omitted the range on purpose.",
                    "'Missing information' was manufactured by withholding PET findings a real report would state.",
                    "Leading questions named the concept being tested ('double-expressor or double-hit?').",
                    "No pre-treatment work-up, supportive care or patient goals, though these drive real treatment decisions.",
                    "Gold gaps: no FLYER for limited stage (0005); no WHO-HAEM5 name accepted (0004); an IPI wording slip (0001); no prephase, TLS or methotrexate-feasibility content (0003).",
                    "A single snapshot in time, while real oncology unfolds over months."]),
          PageBreak(), P("3. What Phase 2 changed", "h1"),
          table([["Area", "v1", "v2"],
                 ["Chart", "4 short text files", "10-14 dated documents with reference ranges, computed H/L flags, past history, meds, allergies, distractors"],
                 ["Formats", "Hand-built separately; disagreed", "One source (cases_src/&lt;case&gt;/case.toml) generates both narrative and FHIR"],
                 ["Prompt", "Leading per-concept questions", "'Consulting hematologist: write the tumor-board assessment and plan'"],
                 ["Answer keys", "8 keys", "11 keys, adding pretreatment_workup, supportive_care, fitness_and_goals"],
                 ["Grading", "Regex per case, points minus penalties", "Atomic must / should / must-not items with minor / important / dangerous severity; a dangerous error means reward 0"],
                 ["Judge", "None", "Optional LLM judge that must quote the answer verbatim (invented quotes are rejected); regex fallback"],
                 ["Safety checks", "None", "Build fails on answer leakage into the chart, pathology inconsistency, or a gold answer below 1.0"],
                 ["Time", "One snapshot", "5-layer journey as a native Harbor multi-step task"]], [24 * mm, 50 * mm, 100 * mm]),
          P("4. Results", "h1"), P("v1 reference answers graded against the v2 rubrics", "h2"),
          P("Same patient, same core facts, but the v2 chart adds the real-world twist. A clinically complete plan must now handle it."),
          table([["Case", "v2 twist", "v1 gold reward", "Dangerous errors"]] + v1_rows, [22 * mm, 70 * mm, 22 * mm, 60 * mm]),
          P("Harbor oracle runs (Docker, 2026-10-19)", "h2"),
          table([["v1 task (current weights)", "Reward"]] + [[E(a), b] for a, b in o1], [140 * mm, 34 * mm]),
          Spacer(1, 6),
          table([["v2 task", "Reward"]] + [[E(a), b] for a, b in o2], [140 * mm, 34 * mm]),
          P("Oracle runs prove the pipeline (build → sandbox → answer file → verifier → reward) and that each gold answer scores "
            "full marks. They say nothing about model ability.", "small"),
          PageBreak(), P("5. Case-by-case analysis", "h1")]
    for c in cases:
        n = CASE_NOTES[c["id"]]
        items = c["rubric"]["items"]
        st += [KeepTogether([P(f"{E(c['id'])} · {E(c['case']['meta']['title'])}", "h2"),
               table([["Patient", E(n["patient"])], ["Teaching point", E(n["teaching"])], ["Twist", E(n["twist"])],
                      ["Key decisions", "<br/>".join("• " + E(x) for x in n["decisions"])],
                      ["Dangerous items", E(", ".join(i["id"] for i in items if i["severity"] == "dangerous"))],
                      ["Open questions", "<br/>".join("• " + E(x) for x in n["review"])]], [30 * mm, 144 * mm], header=False)]),
               Spacer(1, 4)]
    st += [P("6. Longitudinal journey (dlbcl_0003)", "h1"),
           table([["Layer", "Weight", "Situation", "Dangerous errors"],
                  ["L1", "20%", "Diagnosis: the v2 0003 chart", "As in the single case (TLS, stage, CNS risk, curative therapy)"],
                  ["L2", "15%", "End-of-treatment PET Deauville 4; biopsy non-diagnostic; patient declines a repeat biopsy", "Calling it a complete response"],
                  ["L3", "20%", "Progression 3.5 months after Pola-R-CHP; NGS shows EZH2 Y646F", "No second-line CAR-T; palliative-only care"],
                  ["L4", "30%", "Day +6 after axi-cel: confusion, fever, hypotension, ANC 0.2", "No steroids for ICANS; no empiric antibiotics"],
                  ["L5", "15%", "Progression after CAR-T, ECOG 3, declines treatment, financial toxicity", "Abandoning the patient"]],
                 [14 * mm, 15 * mm, 85 * mm, 60 * mm]),
           P("Layers 2-5 are drafts. The L4 differential must include CNS relapse, carried over from the CNS-IPI of 6 at diagnosis.", "small"),
           P("7. Grader design and known limits", "h1"),
           *bullets(["The regex fallback is a safety net, not the grade of record: it credits keywords anywhere in the answer. Use the judge for any reported number.",
                     "The judge's agreement with an oncologist has not been measured. Target at least 90% item-level agreement on about 30 labelled answers.",
                     "A negation bug (the 'non-' in 'non-bulky' hid a recommendation) was found during the build, fixed, and every case retested.",
                     "Harbor's own multi-step 'mean' averages domain keys with missing values counted as 0. Use scripts/summarize_job.py for weighted journey scores.",
                     "LOINC/SNOMED codes in the v2 builder have not been checked against a terminology server."]),
           P("8. Next steps", "h1"),
           table([["#", "Action", "Owner", "Unblocks"],
                  ["1", "Oncologist reviews the 5 case packs and the journey pack (docs/oncologist-review-v2.md)", "Oncologist", "Any reported v2 score"],
                  ["2", "Funded agent key plus a pinned judge model; run configs/harbor-baseline-v1-v2-paid.json (3 attempts each)", "Engineering", "First trustworthy baseline; v1 vs v2 and narrative vs FHIR"],
                  ["3", "Judge calibration against about 30 oncologist-labelled answers", "Engineering + oncologist", "Trust in judge scores"],
                  ["4", "Oncologist completes journey layers 2-5 on the longitudinal form", "Oncologist", "Journey scores"],
                  ["5", "Terminology validation of FHIR codes", "Engineering", "External delivery"],
                  ["6", "Scale to about 20 patients using the cases_src template; second tumour type", "Engineering + oncologist", "Pilot package"]],
                 [8 * mm, 92 * mm, 32 * mm, 42 * mm]),
           P("9. Where things are", "h1"),
           table([["Path", "Contents"],
                  ["reports/cases/", "One confidential case pack PDF per v2 case, plus the journey"],
                  ["cases_src/", "Single source per patient: case.toml (visible), gold.json, rubric_v2.toml, selftest/ (hidden)"],
                  ["graders/oncoworld_grader/", "Shared v2 grader, test.sh, self-test runner"],
                  ["scripts/build_cases_v2.py, build_journey_v2.py", "Generate the Harbor tasks; enforce the leak, consistency and gold checks"],
                  ["scripts/summarize_job.py", "Per-case, per-version and journey-weighted summaries of a Harbor job"],
                  ["docs/phase2-clinical-realism.md", "Engineering documentation and commands"],
                  ["docs/oncologist-review-v2.md", "Sign-off questionnaire"]], [62 * mm, 112 * mm]),
           Spacer(1, 8), P("Synthetic cases for AI evaluation only. Not clinical decision support. No real patient data.", "small")]
    d.build(st, onFirstPage=on_page, onLaterPages=on_page)
    return path


def main():
    cases = [load_case(c) for c in CASES]
    out = [case_pack(c) for c in cases] + [journey_pack(), final_report(cases)]
    for p in out:
        print(f"wrote {p.relative_to(ROOT)} ({p.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
