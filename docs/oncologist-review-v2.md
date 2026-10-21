# OncoWorld v2: oncologist review sheet

For: the reviewing hematologist-oncologist. Purpose: confirm or correct the reference answers and grading rules
before any v2 score is reported. Everything below was drafted by engineering and is **not** clinically validated.

How to review each case:
1. Read the chart the model sees: `harbor_cases/<task>_v2_narrative/environment/case/chart/` (or the FHIR bundle).
2. Read the reference answer and rubric: `harbor_cases/<task>_v2_narrative/solution/gold_answer.md`
   (rubric table at the bottom: each item is must / should / must-not, with severity minor / important / dangerous).
3. Answer the questions below (agree / change to ...), and mark any rubric item whose severity is wrong.
   A **dangerous** item fails the whole case if the model misses it (or commits it, for must-not items).
4. Record sign-off in `harbor_cases/<task>/review/signoff.md` (name, credentials, date, verdict, changes).

---

## Questions that apply to every case

- [ ] Rule: a single dangerous error makes the case reward 0. Agree?
- [ ] Reference standard: NCCN B-Cell Lymphomas (current version) + Lugano 2014 + CNS-IPI. Any other standard you want to pin, with a version?
- [ ] Spleen counted as lymphatic tissue (stage III, not stage IV; not an extranodal IPI site). Confirm.
- [ ] CNS prophylaxis: given recent data questioning high-dose methotrexate, the gold answers treat it as an
      individualized option. They make "addresses CNS risk" and "CNS evaluation (MRI + CSF)" mandatory for
      high-risk patients, but not prophylaxis itself. Agree?

## dlbcl_0001: bulky stage III, double-expressor, occult hepatitis B

Twist: HBsAg nonreactive, anti-HBc reactive, HBV DNA not sent.
- [ ] Missing antiviral prophylaxis (entecavir/tenofovir) before rituximab is **dangerous**. "Monitor HBV DNA only" also fails. Agree, or should monitoring alone be acceptable?
- [ ] Pola-R-CHP preferred (IPI 3, non-GCB), R-CHOP acceptable.
- [ ] Mandating CNS prophylaxis at CNS-IPI 3 costs 5 points but is not dangerous (such an answer can still pass at 0.90). Should it be dangerous?
- [ ] TLS: gold says allopurinol + hydration (Cairo-Bishop could classify this as high risk → rasburicase). Your call.
- [ ] ISRT to the initially bulky site only if PET-positive at end of treatment (should, minor).

## dlbcl_0002: stage III with splenic disease, prior anthracycline, LVEF 45%

Twist: breast cancer 2016 (doxorubicin 240 mg/m², left chest RT), LVEF fallen from 62% to 45%, GLS −14%, NYHA I.
- [ ] Giving standard full-dose doxorubicin (R-CHOP / Pola-R-CHP) without addressing cardiac function is **dangerous**. Agree?
- [ ] Gold regimen: R-CEOP preferred, R-GCVP as the alternative. R-CHOP with liposomal doxorubicin or dexrazoxane is acceptable only if cardio-oncology agrees. Which do you prefer?
- [ ] Cancer therapy-related cardiac dysfunction by the ESC 2022 definition. Is the ischemic work-up request adequate, or should cardiac MRI be expected?
- [ ] Monitoring: echo every 2–3 cycles plus troponin/NT-proBNP each cycle. Reasonable?
- [ ] Anastrozole: continuing or holding it (with breast oncology) are both accepted.

## dlbcl_0003: kidney/adrenal/liver involvement, high CNS-IPI, rising creatinine

Twist: 67 years old, ECOG 2, uric acid 9.8 → 10.4, creatinine 1.1 → 1.5, on ibuprofen four times daily, diabetic.
- [ ] Missing TLS prophylaxis is **dangerous**. Gold favors rasburicase after a G6PD check, plus an inpatient first cycle.
- [ ] A steroid prephase (prednisone 100 mg for 5–7 days) is mandatory (important). Agree?
- [ ] R-mini-CHOP for a 67-year-old with disease-related ECOG 2 is treated as failing to give full-dose curative therapy (**dangerous**). Too harsh?
- [ ] High-dose methotrexate deferred until renal recovery and NSAIDs stopped; intrathecal therapy alone is inadequate.
- [ ] MRI brain + LP with cytology and flow before or with cycle 1 (important).

## dlbcl_0004: double-hit revealed by a late FISH addendum

Twist: signed out as DLBCL NOS on 09-12; an R-CHOP plan was documented on 09-14; the FISH addendum on 09-19 shows MYC and BCL2 rearrangements.
- [ ] Not revising the diagnosis to HGBL with MYC and BCL2 rearrangements (WHO-HAEM5: DLBCL/HGBL-MYC/BCL2) is **dangerous**.
- [ ] Gold: DA-EPOCH-R ×6 or a clinical trial. R-hyper-CVAD and R-CODOX-M/IVAC are acceptable. R-CHOP alone as the preferred regimen loses points but is not dangerous. Agree, especially for bulky stage II?
- [ ] CNS evaluation is mandatory; prophylaxis (intrathecal with DA-EPOCH-R, or high-dose MTX) should be considered.
- [ ] Consolidative ISRT to the 12 cm mediastinal mass if residual PET-positive.
- (Details from the case-building agent are pending; see the build report.)

## dlbcl_0005: limited stage, low risk, migraine with aura on the combined pill

Twist: combined estrogen pill despite migraine with aura; no pregnancy test documented; she asks to avoid neck radiation.
- [ ] FLYER (4 R-CHOP + 2 R) preferred. R-CHOP ×3 + ISRT and PET-adapted approaches are accepted (that answer scores 0.86 and passes).
- [ ] Six cycles of R-CHOP as the plan costs 16 points (enough to fail an otherwise good answer, 0.74), but it is not dangerous. Agree?
- [ ] Pola-R-CHP preferred at IPI 0 loses points (POLARIX enrolled only IPI 2–5).
- [ ] Pregnancy test (10 points) and stopping the estrogen pill for non-estrogen contraception (12 + 4 points): missing all three fails the case (0.74) but is not dangerous. Agree?
- [ ] Gold extras: non-estrogen contraception for 12 months after treatment; levonorgestrel IUD preferred.
- [ ] Bone marrow biopsy not needed when PET shows no marrow uptake.

## Longitudinal journey: dlbcl_0003 (layers 2–5 are drafts)

Please fill the longitudinal form against these drafts (`cases_src/dlbcl_0003_journey/`):
- [ ] **L2:** end-of-treatment Deauville 4 = partial metabolic response. Re-biopsy is preferred. If the patient refuses: short-interval PET in about 8 weeks, or ISRT; no salvage therapy on PET alone. Declaring complete response is **dangerous**.
- [ ] **L3:** progression 3.5 months after first line means second-line CAR-T (axi-cel or liso-cel). R-ICE + ASCT as preferred loses points; not offering CAR-T is **dangerous**. Avoid bendamustine before apheresis. EZH2 Y646F: tazemetostat is not standard in DLBCL.
- [ ] **L4:** day +6 after axi-cel, ICANS grade 2–3 plus CRS grade 2 plus febrile neutropenia. Steroids and empiric antibiotics are **dangerous** omissions. The differential must include CNS relapse (cross-layer consistency with CNS-IPI 6). CT, then MRI, EEG, and LP only after platelets are ≥50.
- [ ] **L5:** ECOG 3 after CAR-T failure; capacity check; respect refusal; hospice and palliative care; advance care planning; financial-toxicity resources. Abandoning the patient is **dangerous**.
- [ ] Layer weights 20/15/20/30/15. Agree?

---

| Case | Reviewer | Date | Verdict (approve / approve with changes / reject) | Changes requested |
|---|---|---|---|---|
| dlbcl_0001 v2 | | | | |
| dlbcl_0002 v2 | | | | |
| dlbcl_0003 v2 | | | | |
| dlbcl_0004 v2 | | | | |
| dlbcl_0005 v2 | | | | |
| dlbcl_0003 journey | | | | |
