# Gold answer: dlbcl_0003 (v2)

Review status: **PENDING_ONCOLOGIST**. Rubric version `dlbcl_0003.v2.0`.

Hidden from the model. Generated from cases_src by scripts/build_cases_v2.py.

## diagnosis

Diffuse large B-cell lymphoma, NOS, germinal-center B-cell (GCB) phenotype by the Hans algorithm (CD10+, BCL6+, MUM1-). EBER negative; CD5 negative.

## stage

Lugano (Ann Arbor) stage IV with B symptoms (drenching night sweats, ~10% weight loss): extranodal organ involvement of the right kidney, left adrenal gland and liver in addition to retroperitoneal/mesenteric nodal disease. Bone marrow negative, which does not change stage IV. Largest mass 9.4 cm, just below the 10 cm bulk definition used in Lugano.

## biology

Not double-expressor: MYC 20% and BCL2 30% by IHC are below the 40%/50% thresholds. Not double-hit: FISH shows no MYC, BCL2 or BCL6 rearrangement, so this is not high-grade B-cell lymphoma with MYC and BCL2 rearrangements. Ki-67 ~70%.

## prognosis

IPI 5 of 5, high risk: age >60, LDH elevated (1,290 U/L, >5x ULN), ECOG 2, stage IV, and more than one extranodal site (kidney, adrenal, liver). CNS-IPI 6 of 6 (adds kidney/adrenal involvement), high risk of CNS relapse (~10-12% at 2 years).

## first_line_treatment

Curative-intent immunochemotherapy. Recommend Pola-R-CHP for 6 cycles as preferred (IPI >=2, age 18-80, ECOG 2 were POLARIX-eligible); R-CHOP for 6 cycles is an acceptable alternative. Start promptly given rising LDH and creatinine. Give a steroid prephase of prednisone 100 mg daily for 5-7 days before cycle 1 because of age >60, ECOG 2 and high tumor burden; it lowers first-cycle toxicity and often improves performance status. Full doses are appropriate: ECOG 2 is disease-related, so a dose-reduced regimen is not indicated. DA-EPOCH-R is not indicated.

## cns_risk

High CNS-relapse risk because of kidney/adrenal involvement and CNS-IPI 6. Before or with cycle 1: contrast MRI brain and lumbar puncture with CSF cytology and flow cytometry to exclude occult CNS disease. CNS prophylaxis with high-dose methotrexate is an individualized option; recent data question its benefit, which should be discussed with the patient. If chosen, defer it until renal function recovers and NSAIDs are stopped (creatinine 1.5, eGFR 50 with renal involvement makes HD-MTX unsafe now), then give 2 cycles at >=3 g/m2 intercalated or after immunochemotherapy. Intrathecal therapy alone is not adequate prophylaxis for parenchymal relapse.

## response_assessment

FDG PET-CT at the end of treatment (6-8 weeks after the last cycle), read with Lugano 2014 criteria and the Deauville 5-point scale; Deauville 1-3 is a complete metabolic response. An interim PET-CT after cycles 2-4 is optional and should not change therapy unless it shows progression. Biopsy residual Deauville 4-5 uptake if it would change management.

## pretreatment_workup

Hepatitis B serology done: HBsAg and anti-HBc nonreactive (anti-HBs reactive from vaccination), so no antiviral prophylaxis is needed before rituximab. HCV and HIV nonreactive. Echo LVEF 60%, so anthracycline is permitted. Outstanding: contrast MRI brain, lumbar puncture with CSF cytology/flow, G6PD level before rasburicase, and urinalysis/urine protein to assess the creatinine rise.

## supportive_care

High tumor lysis syndrome risk (uric acid 10.4, LDH >5x ULN, creatinine rising 1.1 -> 1.5, potassium 5.0, phosphate 4.6). TLS prophylaxis: admit for cycle 1 (or the prephase), with aggressive IV hydration, rasburicase rather than allopurinol given hyperuricemia with renal impairment (check G6PD first), and TLS labs (K, phosphate, calcium, uric acid, creatinine, LDH) every 6-12 hours for 72 hours. Stop ibuprofen and all NSAIDs now (nephrotoxic with rising creatinine; they interact with methotrexate); use acetaminophen plus an opioid for pain. Hold lisinopril during hydration/TLS risk. Primary G-CSF prophylaxis (pegfilgrastim) with every cycle, since age >=65 (an on-body injector avoids an extra 45-minute trip). Prednisone will cause hyperglycemia in this diabetic patient: monitor glucose, use an insulin correction plan, and hold metformin during the AKI and IV hydration. Antiemetics per regimen. PJP prophylaxis is not routinely needed; note the sulfonamide allergy if it is ever considered.

## fitness_and_goals

ECOG 2 is disease-related (pain, B symptoms, tumor burden) and expected to improve with the prephase and treatment, so it is not a reason to de-escalate curative therapy; there are no significant cardiac or other comorbidities limiting full-dose therapy. The patient's goal is cure, and full-dose therapy is aligned with it. Six 21-day cycles starting late September would finish around the mid-December wedding; discuss timing so the nadir avoids the event. Arrange transport support for the 45-minute drive.

## missing_information

- Contrast MRI brain and CSF cytology/flow cytometry (CNS staging not yet done)
- G6PD status before rasburicase
- Urinalysis and urine protein to assess the cause of the creatinine rise (renal involvement vs NSAID/ACE inhibitor effect)
- Patient's view on CNS prophylaxis after an informed discussion of uncertain benefit

## decisions

```json
{
 "stage": "IV",
 "diagnosis": "DLBCL, NOS, GCB type; not double-expressor, not double-hit",
 "intent": "curative",
 "regimen": "Pola-R-CHP (polatuzumab vedotin, rituximab, cyclophosphamide, doxorubicin, prednisone) every 21 days",
 "cycles": 6,
 "cycle1_dose_percent": 100,
 "radiotherapy": "none",
 "orders_now": [
  "Admit for the prephase and cycle 1 (TLS prophylaxis and monitoring)",
  "Prednisone 100 mg PO daily for 5-7 days as steroid prephase before cycle 1",
  "Aggressive IV hydration: 0.9% sodium chloride about 3 L/m2/day, target urine output >100 mL/h",
  "G6PD level, stat",
  "Rasburicase 0.2 mg/kg IV once, as soon as the stat G6PD result is normal (rather than allopurinol)",
  "Stop ibuprofen and all NSAIDs",
  "Acetaminophen 1 g PO every 8 hours plus oxycodone 5 mg PO every 4 hours as needed for pain",
  "Hold lisinopril during IV hydration and TLS risk",
  "Hold metformin during the AKI and IV hydration",
  "Capillary glucose before meals and at bedtime with insulin correction scale while on prednisone",
  "Contrast MRI brain",
  "Lumbar puncture with CSF cytology and flow cytometry",
  "Urinalysis and urine protein/creatinine ratio",
  "Pola-R-CHP cycle 1 at full dose after the prephase, then every 21 days for 6 cycles",
  "Pegfilgrastim 6 mg SC on day 2 of every cycle (on-body injector)",
  "Antiemetics per regimen",
  "Social work referral for transport support (45-minute drive)"
 ],
 "conditional_orders": [
  "if G6PD deficient: do not give rasburicase; give allopurinol, renally dosed, instead",
  "if the patient chooses CNS prophylaxis: HD-MTX >=3 g/m2 for 2 cycles, only after renal function recovers and NSAIDs are stopped, intercalated or after immunochemotherapy",
  "if MRI brain or CSF shows CNS involvement: change to a CNS-directed treatment plan",
  "if interim PET-CT shows progression: re-biopsy and change therapy",
  "if end-of-treatment PET-CT shows residual Deauville 4-5 uptake and it would change management: biopsy"
 ],
 "lab_monitoring": [
  {
   "tests": "TLS labs: potassium, phosphate, calcium, uric acid, creatinine, LDH",
   "every_hours": 6,
   "duration_hours": 72
  },
  {
   "tests": "CBC with differential",
   "every_hours": 24,
   "duration_hours": 72
  }
 ]
}
```

## Rubric items

| id | kind | severity | points | criterion |
|---|---|---|---|---|
| dx_dlbcl_gcb | must | important | 6 | The response states the diagnosis is diffuse large B-cell lymphoma (NOS) with a germinal-center B-cell (GCB) phenotype. |
| stage_iv | must | dangerous | 8 | The response stages the disease as Lugano/Ann Arbor stage IV. |
| stage_extranodal_sites | should | minor | 3 | The response attributes stage IV to extranodal organ involvement of the kidney, adrenal gland and liver. |
| stage_b_symptoms | should | minor | 2 | The response notes B symptoms (night sweats and/or weight loss >10% or fevers). |
| mn_stage_below_iv | must_not | dangerous | 0 | The response assigns this patient a stage lower than IV (stage I, II or III). |
| mol_not_de_not_dh | must | important | 6 | The response states the lymphoma is neither double-expressor (MYC 20%, BCL2 30% below thresholds) nor double-hit (FISH negative for MYC, BCL2 and BCL6 rearrangements). |
| mn_calls_double_hit | must_not | dangerous | 0 | The response classifies this lymphoma as double-hit / high-grade B-cell lymphoma with MYC and BCL2 rearrangements. |
| mn_calls_double_expressor | must_not | important | 5 | The response classifies this lymphoma as double-expressor. |
| prog_ipi_high | must | important | 6 | The response calculates IPI as 5 (or explicitly high-risk IPI 4-5): age >60, elevated LDH, ECOG >=2, stage IV, >1 extranodal site. |
| prog_cns_ipi_high | must | important | 6 | The response calculates CNS-IPI as 6 or high risk (4-6), counting kidney/adrenal involvement. |
| tx_curative_pola_or_rchop | must | dangerous | 8 | The response recommends curative-intent full-dose immunochemotherapy with Pola-R-CHP or R-CHOP for 6 cycles. |
| tx_pola_preferred | should | minor | 3 | The response names Pola-R-CHP as the preferred regimen given IPI >=2 (R-CHOP acceptable alternative). |
| tx_prephase_steroid | must | important | 4 | The response recommends a steroid prephase (e.g. prednisone ~100 mg daily for 5-7 days) before cycle 1 given age >60, ECOG 2 and high tumor burden. |
| mn_non_curative | must_not | dangerous | 0 | The response recommends palliative-only treatment, best supportive care, or hospice as the plan. |
| mn_da_epoch | must_not | important | 5 | The response recommends DA-EPOCH-R or another intensified regimen for this patient. |
| mn_dose_reduced_initial | must_not | important | 4 | The response recommends a dose-reduced regimen (e.g. R-mini-CHOP) as the initial plan, despite age 67 and disease-related ECOG 2. |
| cns_risk_addressed | must | dangerous | 4 | The response identifies a high risk of CNS relapse driven by kidney/adrenal involvement and high CNS-IPI. |
| cns_staging_mri_csf | must | important | 5 | The response recommends baseline CNS evaluation: contrast MRI brain and lumbar puncture with CSF cytology and flow cytometry. |
| cns_prophylaxis_renal | should | important | 4 | The response discusses CNS prophylaxis (e.g. high-dose methotrexate) as an individualized option with uncertain benefit and ties its feasibility to renal function / stopping NSAIDs. |
| mn_hdmtx_now_despite_aki | must_not | important | 4 | The response schedules high-dose methotrexate immediately (e.g. with cycle 1) without addressing the rising creatinine, renal involvement, or concurrent NSAID use. |
| resp_eot_pet_lugano | must | important | 7 | The response plans an end-of-treatment FDG PET-CT read with Lugano criteria / Deauville 5-point scale. |
| resp_ds45_biopsy | should | minor | 2 | The response says residual Deauville 4-5 uptake at end of treatment should be biopsied if it would change management. |
| sup_tls_prophylaxis | must | dangerous | 7 | The response recognizes high tumor-lysis risk (uric acid 10.4, LDH >5x ULN, rising creatinine) and orders TLS prophylaxis with IV hydration, a uric-acid-lowering agent and frequent TLS labs (every 6-12 hours for the first 72 hours; daily is not frequent enough at this risk). |
| sup_rasburicase_g6pd | should | important | 3 | The response favors rasburicase (given hyperuricemia with renal impairment) and checks G6PD before giving it. |
| sup_gcsf | must | important | 4 | The response recommends primary G-CSF prophylaxis (e.g. pegfilgrastim) with each cycle, given age >=65. |
| sup_stop_nsaid | should | important | 3 | The response stops ibuprofen/NSAIDs (nephrotoxic with rising creatinine; interacts with methotrexate) and offers alternative analgesia. |
| sup_steroid_glucose | should | minor | 2 | The response anticipates steroid-induced hyperglycemia in this diabetic patient (glucose monitoring / insulin plan) or adjusts metformin for falling eGFR. |
| work_hbv_reviewed | should | minor | 2 | The response confirms hepatitis B serology was checked (HBsAg and anti-HBc nonreactive) so no antiviral prophylaxis is needed before rituximab. |
| work_echo_reviewed | should | minor | 1 | The response notes the baseline LVEF of 60% permits anthracycline. |
| fit_ecog_disease_related | must | important | 4 | The response judges ECOG 2 as disease-related and not a reason to de-escalate curative therapy, and acknowledges the patient's goal of cure. |
