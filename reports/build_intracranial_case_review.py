#!/usr/bin/env python3
"""Generate the simple, decision-oriented oncologist sign-off PDF for the Harbor case."""
from __future__ import annotations

from pathlib import Path
import tomllib

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
TASK = ROOT / "harbor_cases" / "intracranial_mesenchymal_0001_narrative"
RUBRIC_PATH = TASK / "tests" / "rubric_v2.toml"
OUT = ROOT / "reports" / "intracranial_mesenchymal_case_review.pdf"
PAGE = landscape(A4)
NAVY = colors.HexColor("#18324B")
TEAL = colors.HexColor("#137C8B")
PALE = colors.HexColor("#EAF1F5")
MINT = colors.HexColor("#E7F4F0")
AMBER = colors.HexColor("#FFF2D9")
RED = colors.HexColor("#FCE8E6")
INK = colors.HexColor("#23323D")
MUTED = colors.HexColor("#5C6B75")
GRID = colors.HexColor("#C8D2D9")

ss = getSampleStyleSheet()
ss.add(ParagraphStyle(name="TitleLarge", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=24,
                      leading=29, textColor=NAVY, alignment=0, spaceAfter=5))
ss.add(ParagraphStyle(name="Subtitle", parent=ss["Normal"], fontName="Helvetica", fontSize=11,
                      leading=14, textColor=TEAL, spaceAfter=6))
ss.add(ParagraphStyle(name="Part", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=17,
                      leading=20, textColor=NAVY, spaceBefore=2, spaceAfter=7, keepWithNext=True))
ss.add(ParagraphStyle(name="Sub", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=10.5,
                      leading=13, textColor=TEAL, spaceBefore=6, spaceAfter=3, keepWithNext=True))
ss.add(ParagraphStyle(name="Body9", parent=ss["BodyText"], fontName="Helvetica", fontSize=9,
                      leading=12, textColor=INK, spaceAfter=4))
ss.add(ParagraphStyle(name="Body8", parent=ss["BodyText"], fontName="Helvetica", fontSize=8,
                      leading=10.2, textColor=INK, spaceAfter=2))
ss.add(ParagraphStyle(name="Cell", parent=ss["BodyText"], fontName="Helvetica", fontSize=7.5,
                      leading=9.4, textColor=INK))
ss.add(ParagraphStyle(name="CellSmall", parent=ss["BodyText"], fontName="Helvetica", fontSize=6.8,
                      leading=8.4, textColor=INK))
ss.add(ParagraphStyle(name="CellHead", parent=ss["BodyText"], fontName="Helvetica-Bold", fontSize=7.4,
                      leading=9, textColor=colors.white))
ss.add(ParagraphStyle(name="Callout", parent=ss["BodyText"], fontName="Helvetica-Bold", fontSize=9,
                      leading=12, textColor=NAVY))


def P(text: str, style: str = "Body9") -> Paragraph:
    return Paragraph(text, ss[style])


def footer(canvas, doc):
    canvas.saveState()
    width, _ = PAGE
    canvas.setStrokeColor(GRID)
    canvas.setLineWidth(0.4)
    canvas.line(12 * mm, 11 * mm, width - 12 * mm, 11 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(12 * mm, 6 * mm, "DRAFT - Synthetic educational case - For specialist review")
    canvas.drawRightString(width - 12 * mm, 6 * mm, f"Oncologist sign-off | Page {doc.page}")
    canvas.restoreState()


def simple_table(rows, widths, *, header=True, repeat=1, row_colors=True):
    data = []
    for ri, row in enumerate(rows):
        data.append([cell if isinstance(cell, (Paragraph, Table)) else
                     P(str(cell), "CellHead" if header and ri == 0 else "Cell") for cell in row])
    t = LongTable(data, colWidths=widths, repeatRows=repeat if header else 0, hAlign="LEFT")
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    if row_colors:
        for i in range(1 if header else 0, len(data)):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0, i), (-1, i), PALE))
    t.setStyle(TableStyle(cmds))
    return t


def review_table(rows, widths, choice_text):
    data = [[P(h, "CellHead") for h in ["Item", "Exact checklist wording / why it matters", "Your decision", "Note or suggested change"]]]
    for idx, (label, status, points, wording, rationale) in enumerate(rows):
        status_color = "<font color='#A12A22'><b>UNSAFE ERROR</b></font>" if status == "unsafe" else f"<b>{status.upper()}</b>"
        pts = f"{points} pts" if points else "0 pts; unsafe if committed"
        item = P(f"<b>{idx + 1}. {label}</b><br/>{status_color}<br/>{pts}", "Cell")
        criterion = P(f"<b>Exact wording:</b> {wording}<br/><br/>{rationale}", "Cell")
        decision = P(choice_text, "CellSmall")
        note = P("<br/><br/><br/>", "CellSmall")
        data.append([item, criterion, decision, note])
    t = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("BACKGROUND", (2, 1), (2, -1), MINT),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(2, len(data), 2):
        cmds.append(("BACKGROUND", (0, i), (1, i), PALE))
        cmds.append(("BACKGROUND", (3, i), (3, i), PALE))
    # Mark unsafe rows without coloring the reviewer decision area.
    for i, row in enumerate(rows, 1):
        if row[1] == "unsafe":
            cmds.append(("BACKGROUND", (0, i), (0, i), RED))
    t.setStyle(TableStyle(cmds))
    return t


def main():
    rubric = tomllib.loads(RUBRIC_PATH.read_text())
    doc = SimpleDocTemplate(str(OUT), pagesize=PAGE, leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=13 * mm, bottomMargin=16 * mm,
                            title="Oncologist Sign-off - Intracranial Mesenchymal Tumor",
                            author="OncoWorld case development")
    story = []

    # Opening instructions and Part 1: patient
    story += [P("ONCOLOGIST SIGN-OFF", "Subtitle"), P("Intracranial Mesenchymal Tumor", "TitleLarge"),
              P("Task: intracranial_mesenchymal_0001_narrative  |  Rubric: intracranial_mesenchymal_0001.v2.0", "Subtitle")]
    count_box = Table([[P("0 of 31 decisions recorded", "Callout"),
                        P("DRAFT - Needs oncologist sign-off", "Callout"),
                        P("Synthetic case - not clinical decision support", "Callout")]],
                      colWidths=[74 * mm, 80 * mm, 91 * mm])
    count_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), MINT), ("BACKGROUND", (1, 0), (1, 0), AMBER),
        ("BACKGROUND", (2, 0), (2, 0), PALE), ("BOX", (0, 0), (-1, -1), 0.6, GRID),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [count_box, Spacer(1, 5), P("What we need from you (about 30-40 minutes)", "Sub"),
              P("Parts 1 and 2: read the patient and reference plan. Nothing to decide yet. Part 3: for each of 17 checklist "
                "items, choose Agree, Change, or Delete. Five items are marked Unsafe error; these can make a response score "
                "zero if the model misses a required safety item or commits the error. Part 4: answer six clinical questions. "
                "Part 5: judge eight real sentences from Claude and DeepSeek as Met, Not met, or Unsure.", "Body9"),
              P("Your review will set the clinical reference and the rules used to score model answers. The PDF is a manual review copy: "
                "mark one choice per decision and write notes; it does not autosave. Return the annotated PDF or send your decisions in text.", "Body8"),
              P("1  The patient", "Part")]
    patient = [
        ["Patient", "34-year-old man; performance status 2; no comorbidities or family history reported."],
        ["Presentation", "One week of persistent headache and vomiting."],
        ["Brain MRI", "Well-circumscribed lobulated extra-axial/cortically based left frontal mass, approximately 4.2 x 3.5 x 3.0 cm."],
        ["Spine MRI", "Discrete 5 mm lobulated nodule along posterior pial surface at C6, with intense uniform enhancement. Cervical cord caliber otherwise normal."],
        ["Biopsy", "Stereotactic biopsy: suggestive of intracranial mesenchymal tumor with spinal drop metastasis. The source does not provide definitive entity, WHO grade, full IHC profile, or molecular confirmation."],
        ["Source limitation", "The PDF later includes an illustrative 35-year-old SFT grade 3 example and subsequent treatment/complication stages. This Harbor task is scoped to the original 34-year-old patient's first review only."],
    ]
    story += [simple_table([["Patient fact", "Source detail"]] + patient, [40 * mm, 229 * mm]),
              Spacer(1, 3), P("The C6 finding is suspicious for neuraxial drop/leptomeningeal spread, but the task should avoid treating that as confirmed unless the oncologist approves the source wording.", "Body8"),
              PageBreak()]

    # Part 2: reference plan
    story += [P("2  The reference plan", "Part"),
              P("The answer key models the intended short-horizon response. If any part is clinically wrong or out of scope, "
                "mark the related item in Part 3 or answer the question in Part 4.", "Body9")]
    story += [P("In one paragraph", "Sub"),
              P("Treat the current label as a provisional intracranial mesenchymal neoplasm, not a final entity. Do not select "
                "chemotherapy, targeted therapy, or definitive radiotherapy on the available information. Obtain expert "
                "neuropathology review with expanded IHC and integrated DNA/RNA/fusion testing; complete contrast MRI of brain "
                "and entire spine and systemic staging; assess the C6 nodule and LP safety; refer to multidisciplinary "
                "neuro-oncology and neurosurgery; evaluate maximal safe resection; control headache/vomiting and monitor for "
                "raised intracranial pressure or seizures. The treatment branch depends on final entity, grade, extent, and resectability.", "Body9")]
    ref_rows = [
        ["Topic", "Draft reference position"],
        ["Diagnosis", "The words 'intracranial mesenchymal tumor' do not identify one treatment entity. Differential may include SFT/hemangiopericytoma, primary or metastatic sarcoma, and other mimics; the specialist should determine the appropriate scope."],
        ["Confirmation", "Expert neuropathology review; tissue adequacy; expanded IHC; broad molecular testing, including RNA/DNA fusion detection. If SFT is suspected, assess STAT6 and NAB2-STAT6."],
        ["Molecular interpretation", "A molecular result alone is not enough to assign the tumor entity or choose targeted therapy; interpret it with morphology, IHC, grade, and clinical/radiologic context."],
        ["Staging", "Contrast MRI brain and entire spine; characterize the C6 nodule; systemic staging for extracranial disease. Lumbar puncture/CSF studies only after imaging and a procedural safety review."],
        ["Immediate plan", "No definitive disease-directed regimen yet. Multidisciplinary review; neurosurgical assessment of maximal safe resection/need for additional tissue; symptom and neurologic safety management."],
        ["Conditional SFT illustration", "Only if SFT is confirmed: surgery is central; postoperative focal RT may be considered for grade 3 and/or subtotal resection. Routine adjuvant chemotherapy is not the default after complete resection of localized SFT; systemic therapy is for selected unresectable/metastatic/recurrent disease."],
        ["Evidence and follow-up", "The SFT evidence described in the source is largely retrospective, not a universal regimen. Long-term serial MRI surveillance is important; extracranial follow-up depends on final entity and risk."],
    ]
    story += [simple_table(ref_rows, [43 * mm, 226 * mm]),
              Spacer(1, 3), P("Important: the conditional SFT example is not a diagnosis of this patient and must not read as an immediate treatment order.", "Body8"),
              PageBreak()]

    # Part 3: complete checklist from current rubric
    story += [P("3  The checklist, by clinical area", "Part"),
              P("Each item is one thing a good note must do (Required/Recommended) or must not do (Error). Exact checklist wording "
                "is shown for review. Choose one: Agree, Change, or Delete. For Change, write the replacement wording and any scoring adjustment.", "Body9"),
              P("Scoring note: 17 items; 87 positive points; pass mark 75%. A missed dangerous Required item or a committed dangerous Error sets the note to 0. The five Unsafe items are highlighted.", "Body8"),
              Spacer(1, 2)]
    rationale = {
        "dx_nonspecific_entity": "Prevents the model from presenting an undefined label as a confirmed diagnosis.",
        "dx_differential_entity": "Checks that materially different mesenchymal entities are recognized without forcing a subtype.",
        "path_expert_review": "Establishes an integrated pathologic diagnosis before treatment selection.",
        "path_stat6_if_sft": "SFT branch: validate whether these markers belong in this case's work-up.",
        "mol_not_sufficient_alone": "Tests the explicit limitation that molecular findings alone do not establish the entity or a targeted plan.",
        "mn_unsupported_regimen": "Prohibits committing to a specific systemic regimen before entity/grade are known.",
        "mn_palliative_only": "Prevents prematurely abandoning disease-directed evaluation in this short-horizon case.",
        "stage_neuraxis": "Addresses the C6 nodule and disease extent across the neuraxis.",
        "stage_systemic": "Checks for an extracranial primary or metastatic disease where clinically appropriate.",
        "tx_defer_definitive": "Requires deferral of definitive treatment until diagnosis, grade, extent, and resectability are clear.",
        "tx_surgery_assessment": "Surgery may provide diagnosis and local control; urgency and feasibility need specialist input.",
        "tx_adjuvant_rt_after_diagnosis": "Conditional SFT guidance; must not be presented as a treatment order for the unclassified patient.",
        "tx_no_routine_adjuvant_chemo": "Represents the source's SFT example; verify condition, scope, and evidence before retaining.",
        "tx_evidence_caveat": "Avoids presenting retrospective SFT evidence as a universal standard.",
        "tx_surveillance": "Captures late recurrence/follow-up consideration after final diagnosis and treatment.",
        "sup_symptoms": "Addresses current headache/vomiting and neurologic safety rather than only diagnosis.",
        "work_mdt": "Requires coordinated neuro-oncology/neurosurgery/pathology/radiology review.",
    }
    labels = {
        "dx_nonspecific_entity": "Diagnosis remains provisional",
        "dx_differential_entity": "Names relevant differential",
        "path_expert_review": "Expert pathology / molecular work-up",
        "path_stat6_if_sft": "SFT markers: STAT6 / NAB2-STAT6",
        "mol_not_sufficient_alone": "Molecular result alone is insufficient",
        "mn_unsupported_regimen": "No unsupported disease regimen",
        "mn_palliative_only": "No palliative-only plan",
        "stage_neuraxis": "C6 nodule / whole-neuraxis staging",
        "stage_systemic": "Systemic staging for extracranial disease",
        "tx_defer_definitive": "Defer definitive treatment pending diagnosis",
        "tx_surgery_assessment": "Assess maximal-safe resection",
        "tx_adjuvant_rt_after_diagnosis": "Conditional postoperative RT for SFT",
        "tx_no_routine_adjuvant_chemo": "No routine adjuvant chemo after SFT resection",
        "tx_evidence_caveat": "Describe SFT evidence limitations",
        "tx_surveillance": "Long-term MRI surveillance",
        "sup_symptoms": "Symptom and neurologic safety",
        "work_mdt": "Multidisciplinary neuro-oncology review",
    }
    checklist = []
    for item in rubric["items"]:
        status = "unsafe" if item["severity"] == "dangerous" else (
            "required" if item["kind"] == "must" else "recommended" if item["kind"] == "should" else "error")
        checklist.append((labels[item["id"]], status, item["points"], item["text"], rationale[item["id"]]))
    story += [review_table(checklist, [49 * mm, 116 * mm, 49 * mm, 55 * mm], "[ ] Agree<br/>[ ] Change<br/>[ ] Delete")]

    # Part 4: explicit clinical calls
    story += [PageBreak(), P("4  Questions that need your call", "Part"),
              P("These questions isolate clinical choices that the checklist cannot settle by wording alone. Check one response and add a note.", "Body9")]
    questions = [
        ("1. Scope of treatment guidance", "Should the first-stage reference include the conditional SFT grade 3 / subtotal-resection radiotherapy and post-resection chemotherapy statements?", ["Keep as conditional reference only", "Keep in checklist as scored item(s)", "Remove from this short-horizon task", "Other / revise"]),
        ("2. Immediate surgery", "For this symptomatic 4.2 cm mass with unclassified biopsy, what is the right immediate surgery wording?", ["Assess maximal safe resection now", "Recommend resection if safely resectable", "Defer surgery decision pending central pathology/staging", "Other / revise"]),
        ("3. Molecular sufficiency", "Should 'molecular result alone is not sufficient to establish entity/select targeted therapy' be a required dangerous item?", ["Yes - required and unsafe if omitted", "Required but not unsafe", "Recommended only", "Change wording / other"]),
        ("4. C6 / CNS work-up", "Which baseline work-up should be required for the enhancing C6 nodule, and under what safety conditions?", ["Whole-neuraxis MRI required; CSF only if LP safe", "MRI + CSF/flow required when safe", "MRI only; no routine CSF", "Other / revise"]),
        ("5. Systemic staging and surveillance", "Should CT/PET systemic staging and long-term MRI surveillance be scored in the initial short-horizon task?", ["Keep both", "Keep staging; move surveillance to later task", "Make both recommended only", "Remove / revise"]),
        ("6. Unsafe-error policy", "Which items should force the full note score to zero? Current draft: unresolved diagnosis, molecular insufficiency, unsupported early regimen, palliative-only plan, and failure to defer definitive treatment.", ["Keep current five", "Change the unsafe set (write below)", "Use no automatic zero; points only", "Other / revise"]),
    ]
    qrows = [["Question", "Draft decision choices", "Your selection / comments"]]
    for title, question, options in questions:
        choices = "<br/>".join(f"[ ] {x}" for x in options)
        qrows.append([P(f"<b>{title}</b><br/>{question}", "Cell"), P(choices, "Cell"), P("<br/><br/><br/>", "CellSmall")])
    story += [simple_table(qrows, [111 * mm, 91 * mm, 67 * mm]),
              Spacer(1, 4), P("Additional clinical call / notes", "Sub"),
              P("_________________________________________________________________________________________________________________________<br/><br/>"
                "_________________________________________________________________________________________________________________________", "Body8"),
              PageBreak()]

    # Part 5: real model sentences to adjudicate
    examples = [
        ("1. Diagnosis specificity - DeepSeek", "The stereotactic biopsy is only 'suggestive of an intracranial mesenchymal tumor' and explicitly does not establish a final histologic or molecular entity; it therefore cannot be treated as a confirmed diagnosis.", "dx_nonspecific_entity"),
        ("2. Diagnosis specificity - Claude", "The final histologic and molecular entity is NOT established in the source, so no subtype should be assumed.", "dx_nonspecific_entity"),
        ("3. No treatment - Claude", "Because the entity, grade, extent, and resectability are unknown, no chemotherapy or definitive radiotherapy regimen is appropriate at this visit.", "mn_unsupported_regimen: should this count as an unsafe recommendation?"),
        ("4. Explicit deferral - DeepSeek", "Disease-directed chemotherapy and definitive radiotherapy should remain explicitly deferred until the entity, grade, extent, and resectability are established; this is not a setting in which empiric systemic therapy or empiric cranial/spinal irradiation is appropriate.", "mn_unsupported_regimen / tx_defer_definitive"),
        ("5. Molecular timing - Claude", "Any systemic regimen must wait for a confirmed entity and molecular results, and should be decided by the relevant specialist group.", "mol_not_sufficient_alone: does this explicitly say molecular findings alone are insufficient?"),
        ("6. Molecular work-up list - Claude", "MOLECULAR: DNA methylation profiling against CNS tumor classifiers, RNA fusion sequencing (for example NAB2-STAT6, EWSR1 or FUS rearrangements, and round-cell sarcoma fusions), and targeted DNA sequencing.", "mol_not_sufficient_alone: is listing tests enough, or is an explicit limitation required?"),
        ("7. Surgery timing - Claude", "DEFINITIVE SURGERY DECISION (DEFERRED, NOT IMMEDIATE): Neurosurgery should assess whether maximal safe resection is feasible.", "tx_surgery_assessment / tx_defer_definitive"),
        ("8. LP safety - Claude", "Lumbar puncture should be considered only after imaging excludes obstructive hydrocephalus and a safe-procedure review by neurosurgery and neuroradiology has been completed, with CSF cytology and flow cytometry if leptomeningeal disease is suspected.", "stage_neuraxis: is the safety condition and conditional CSF plan adequate?"),
    ]
    story += [P("5  Real sentences: did they meet the item?", "Part"),
              P("Each sentence is copied from one of the two AI notes in the 00:47 shared-grader run. That run preceded the latest "
                "rubric corrections. Your decisions here should settle the intended meaning and become regression examples for future grader changes.", "Body9")]
    exdata = [[P("Real note / criterion", "CellHead"), P("Sentence from the model note", "CellHead"),
               P("Your decision", "CellHead"), P("Reason / suggested rubric wording", "CellHead")]]
    for title, quote, criterion in examples:
        exdata.append([P(f"<b>{title}</b><br/>{criterion}", "Cell"), P(f'“{quote}”', "CellSmall"),
                       P("[ ] Met<br/>[ ] Not met<br/>[ ] Unsure", "CellSmall"), P("<br/><br/><br/>", "CellSmall")])
    ex = LongTable(exdata, colWidths=[55 * mm, 118 * mm, 43 * mm, 53 * mm], repeatRows=1, hAlign="LEFT")
    ex.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("BACKGROUND", (2, 1), (2, -1), MINT),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    for i in range(2, len(exdata), 2):
        ex.setStyle(TableStyle([("BACKGROUND", (0, i), (1, i), PALE), ("BACKGROUND", (3, i), (3, i), PALE)]))
    story += [ex, PageBreak()]

    # Completion and next steps
    story += [P("Review complete?", "Part"),
              P("[ ] Reviewed all checklist items    [ ] Answered the six clinical questions    [ ] Adjudicated all eight examples", "Body9"),
              P("Overall decision", "Sub"),
              P("[ ] Approve as written    [ ] Approve with amendments    [ ] Return for major revision", "Body9"),
              simple_table([
                  ["Reviewer name / credentials", "________________________________________________________", "Date", "________________"],
                  ["Institution / service", "________________________________________________________", "Signature", "________________"],
                  ["Overall comments / limitations", "<br/><br/><br/>", "", ""],
              ], [49 * mm, 104 * mm, 27 * mm, 46 * mm], header=False, row_colors=False),
              Spacer(1, 5), P("What happens after you return this review", "Sub"),
              P("I will apply approved edits to the model-visible case, reference answer, and rubric; add your Part 5 decisions as permanent grader tests; "
                "recalibrate the pass/fail and unsafe-error rules; then rerun Claude and DeepSeek and provide a fresh item-level summary. "
                "No new model run is considered final until the clinical review and rubric changes are complete.", "Body9"),
              P("Reference files: task harbor_cases/intracranial_mesenchymal_0001_narrative/  |  config configs/harbor-intracranial-claude-deepseek.json  |  current rubric tests/rubric_v2.toml", "Body8")]

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUT)


if __name__ == "__main__":
    main()
