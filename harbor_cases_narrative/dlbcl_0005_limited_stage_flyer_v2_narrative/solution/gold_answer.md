# Gold answer: dlbcl_0005 (v2)

Review status: **PENDING_ONCOLOGIST**. Rubric version `dlbcl_0005.v2.0`.

Hidden from the model. Generated from cases_src by scripts/build_cases_v2.py.

## diagnosis

Diffuse large B-cell lymphoma, NOS, germinal-center B-cell (GCB) phenotype by the Hans algorithm (CD10+, BCL6+, MUM1-). EBER negative; CD5 negative; no low-grade (follicular) component.

## stage

Lugano (Ann Arbor) stage IA: a single nodal region (right cervical levels II-III, contiguous), with no B symptoms (denies fevers, night sweats and weight loss). Non-bulky: largest node 3.1 cm, well below the 7.5 cm threshold used in limited-stage trials. No extranodal, splenic or marrow disease on PET-CT. Bone marrow biopsy is not needed because PET-CT shows homogeneous marrow activity without focal uptake.

## biology

Neither double-expressor nor double-hit. MYC 15% and BCL2 30% by IHC are below the 40%/50% thresholds. FISH shows no MYC, BCL2 or BCL6 rearrangement, so this is not high-grade B-cell lymphoma with MYC and BCL2 rearrangements. Ki-67 ~55%.

## prognosis

IPI 0 of 5, low risk: age 45 (<=60), LDH normal (190 U/L), ECOG 0, stage I, no extranodal sites. CNS-IPI 0, low risk. Age 18-60, IPI 0 and maximum diameter <7.5 cm meet the FLYER trial eligibility criteria; expected 3-year progression-free survival is about 95%.

## first_line_treatment

Curative-intent immunochemotherapy. Recommend R-CHOP for 4 cycles followed by 2 additional doses of rituximab, without radiotherapy (FLYER regimen: 4 cycles of R-CHOP plus 2 rituximab was non-inferior to 6 cycles in young patients with IPI 0 and non-bulky disease, with less toxicity). Six cycles of R-CHOP are not needed. Omitting radiotherapy also respects her wish to avoid neck radiation and spares the thyroid and salivary glands, a real concern given her sister's radiation-induced hypothyroidism. Acceptable alternatives: R-CHOP x3 followed by involved-site radiotherapy (ISRT), or a PET-adapted approach after 4 cycles (S1001). Pola-R-CHP is not indicated: POLARIX enrolled IPI 2-5 only. DA-EPOCH-R is not indicated.

## cns_risk

Low CNS-relapse risk: CNS-IPI 0 and no high-risk extranodal sites (kidney, adrenal, testis, breast, uterus). CNS prophylaxis is not indicated, and no MRI brain or lumbar puncture is required without neurological symptoms.

## response_assessment

Interim PET-CT after 4 cycles of R-CHOP, before the two rituximab doses: Deauville 1-3 supports completing the plan without radiotherapy; Deauville 4-5 should prompt biopsy or consolidative ISRT rather than proceeding as planned. End-of-treatment FDG PET-CT 6-8 weeks after the last dose, read with Lugano 2014 criteria and the Deauville 5-point scale; Deauville 1-3 is a complete metabolic response. Routine surveillance imaging is not needed after a complete metabolic response.

## pretreatment_workup

A pregnancy test (serum or urine hCG) is required before cycle 1; none is documented in this premenopausal woman (LMP 2026-08-28, day 21 of her cycle). Hepatitis B serology done: HBsAg and anti-HBc nonreactive (anti-HBs reactive from vaccination), so no antiviral prophylaxis is needed before rituximab. HCV and HIV nonreactive. Echo LVEF 63%, so anthracycline is permitted. Organ function and blood counts normal.

## supportive_care

Stop the combined oral contraceptive (ethinyl estradiol/levonorgestrel) now: estrogen-containing contraception is contraindicated in migraine with aura because of ischemic stroke risk, and it adds venous thromboembolism risk on top of active lymphoma and chemotherapy. She still needs effective non-estrogen contraception throughout treatment and for at least 12 months after: a levonorgestrel or copper IUD is preferred (a levonorgestrel IUD also limits heavy bleeding during thrombocytopenia), or an etonogestrel implant or progestin-only pill; arrange gynecology referral and use condoms until it is in place. Fertility counselling: 4 cycles of R-CHOP carry low gonadotoxicity at age 45 and most women resume menses, but age-related fertility decline matters; offer referral to reproductive medicine before starting since she is undecided about another pregnancy, without delaying treatment. Tumor lysis risk is low (normal LDH, uric acid and renal function); oral hydration, allopurinol optional. Primary G-CSF is not routinely required at age 45 with no risk factors, but reassess after cycle 1. Antiemetics per regimen; avoid codeine (intolerance). Rituximab infusion-reaction precautions.

## fitness_and_goals

Fit: ECOG 0 with no limiting comorbidity, so curative-intent therapy is appropriate with a high cure probability. Her goals are cure, continuing to work as a teacher with minimal time off, and avoiding neck radiation; the 4 x R-CHOP + 2 x rituximab plan without radiotherapy matches all three, and schedules can place infusions late in the week so she can keep teaching. Shared decision-making about the radiotherapy-containing alternative documented.

## missing_information

- Pregnancy test (serum or urine hCG) before cycle 1
- Agreed non-estrogen contraception plan for treatment and the following 12 months
- Patient's fertility preference after counselling (reproductive medicine referral if wanted)

## decisions

```json
{
 "stage": "I",
 "diagnosis": "DLBCL NOS, GCB type (Hans); not double-expressor, not double-hit",
 "intent": "curative",
 "regimen": "R-CHOP-21 x 4 cycles, then rituximab 375 mg/m2 x 2 doses (FLYER)",
 "cycles": 4,
 "cycle1_dose_percent": 100,
 "radiotherapy": "none (consolidative ISRT only if interim PET Deauville 4-5)",
 "orders_now": [
  "Serum or urine hCG pregnancy test before cycle 1",
  "Stop combined oral contraceptive (ethinyl estradiol/levonorgestrel) now",
  "Gynecology referral to place a levonorgestrel or copper IUD (alternatives: etonogestrel implant or progestin-only pill); condoms until it is in place",
  "Reproductive medicine referral for fertility counselling before cycle 1, offered without delaying treatment",
  "R-CHOP-21 x 4: rituximab 375 mg/m2 IV, cyclophosphamide 750 mg/m2 IV, doxorubicin 50 mg/m2 IV, vincristine 1.4 mg/m2 IV (max 2 mg) on day 1; prednisone 100 mg PO days 1-5; every 21 days",
  "Rituximab 375 mg/m2 IV every 21 days x 2 doses after cycle 4",
  "Oral hydration with cycle 1 (low tumor lysis risk; allopurinol optional)",
  "Antiemetics per regimen; avoid codeine (intolerance)",
  "Rituximab infusion-reaction premedication (acetaminophen, diphenhydramine)"
 ],
 "conditional_orders": [
  "if interim PET-CT after cycle 4 is Deauville 4-5: biopsy or consolidative ISRT instead of proceeding as planned",
  "if febrile neutropenia or a treatment delay after cycle 1: add G-CSF to subsequent cycles",
  "if pregnancy test positive: hold chemotherapy and discuss with obstetrics before starting"
 ],
 "lab_monitoring": [
  {
   "tests": "CBC with differential, CMP, LDH, uric acid",
   "every_hours": 504,
   "duration_hours": null
  }
 ]
}
```

## Rubric items

| id | kind | severity | points | criterion |
|---|---|---|---|---|
| dx_dlbcl_gcb | must | important | 5 | The response states the diagnosis is diffuse large B-cell lymphoma (NOS) with a germinal-center B-cell (GCB) phenotype by the Hans algorithm. |
| stage_i | must | important | 7 | The response stages the disease as Lugano/Ann Arbor stage I (stage IA acceptable): a single nodal region (right cervical levels II-III). |
| stage_nonbulky_no_b | should | minor | 2 | The response notes the disease is non-bulky (largest node 3.1 cm, below 7.5 cm) and that there are no B symptoms. |
| stage_pet_no_marrow_biopsy | should | minor | 2 | The response notes that bone marrow biopsy is unnecessary because PET-CT shows no marrow uptake. |
| mn_overstaged | must_not | dangerous | 0 | The response overstages the disease as stage III or IV / advanced stage. |
| mol_not_de_not_dh | must | important | 5 | The response states the lymphoma is neither double-expressor (MYC 15%, BCL2 30% below thresholds) nor double-hit (FISH negative for MYC, BCL2 and BCL6 rearrangements). |
| mn_calls_double_hit | must_not | dangerous | 0 | The response classifies this lymphoma as double-hit / high-grade B-cell lymphoma with MYC and BCL2 rearrangements. |
| mn_calls_double_expressor | must_not | important | 5 | The response classifies this lymphoma as double-expressor. |
| prog_ipi_low | must | important | 6 | The response calculates IPI as 0 (low risk): age <=60, normal LDH, ECOG 0, stage I, no extranodal sites. |
| prog_cns_ipi_low | should | minor | 2 | The response calculates CNS-IPI as 0 / low risk. |
| tx_curative_rchop | must | dangerous | 6 | The response recommends curative-intent rituximab-containing immunochemotherapy (R-CHOP-based) for this patient. |
| tx_flyer_4rchop_2r | must | important | 10 | The response recommends, as the preferred plan, 4 cycles of R-CHOP followed by 2 additional doses of rituximab without radiotherapy (FLYER regimen; age 18-60, IPI 0, non-bulky <7.5 cm). A 4-cycle PET-adapted R-CHOP approach is also accepted. |
| tx_no_rt_goals | should | important | 4 | The response notes that the chosen plan omits neck radiotherapy, which aligns with her wish to avoid radiation (thyroid and salivary late effects, sister's radiation-induced hypothyroidism). |
| tx_alternatives | should | minor | 2 | The response names R-CHOP x3 followed by involved-site radiotherapy, or a PET-adapted 4-cycle approach (S1001), as an acceptable alternative. |
| mn_six_cycles | must_not | important | 16 | The response recommends 6 cycles of R-CHOP (or of Pola-R-CHP) as the preferred plan for this IPI-0, non-bulky stage I disease (overtreatment). |
| mn_pola_preferred | must_not | important | 8 | The response recommends Pola-R-CHP as the preferred regimen (POLARIX enrolled IPI 2-5 only; not indicated at IPI 0). |
| mn_da_epoch | must_not | important | 5 | The response recommends DA-EPOCH-R or another intensified regimen for this patient. |
| mn_observation_or_rt_alone | must_not | dangerous | 0 | The response recommends observation / no systemic treatment, or radiotherapy alone, as the plan. |
| cns_low_no_prophylaxis | should | important | 4 | The response judges CNS-relapse risk as low and states that CNS prophylaxis and CNS staging (MRI brain / lumbar puncture) are not indicated. |
| mn_mandates_cns_prophylaxis | must_not | important | 4 | The response recommends CNS prophylaxis (intrathecal chemotherapy or high-dose methotrexate) for this patient. |
| resp_eot_pet_lugano | must | important | 6 | The response plans an end-of-treatment FDG PET-CT read with Lugano criteria / Deauville 5-point scale. |
| resp_interim_pet | should | minor | 2 | The response plans an interim PET-CT after cycle 4 (before the rituximab-only doses) and says a positive scan (Deauville 4-5) would prompt additional therapy (e.g. RT or biopsy) rather than proceeding as planned. |
| work_pregnancy_test | must | important | 10 | The response requires a pregnancy test (serum or urine hCG) before starting chemotherapy, noting that none is documented in this premenopausal woman. |
| work_hbv_reviewed | should | minor | 2 | The response confirms hepatitis B serology was checked (HBsAg and anti-HBc nonreactive) so no antiviral prophylaxis is needed before rituximab. |
| work_echo_reviewed | should | minor | 1 | The response notes the baseline LVEF of 63% permits anthracycline. |
| sup_stop_coc_switch | must | important | 12 | The response stops the combined estrogen-containing oral contraceptive and switches to effective non-estrogen contraception (e.g. copper or levonorgestrel IUD, implant, progestin-only method) for the duration of treatment. |
| sup_coc_reason | should | important | 4 | The response gives the reason: estrogen-containing contraception is contraindicated in migraine with aura (ischemic stroke risk) and adds venous thromboembolism risk during chemotherapy/active cancer. |
| sup_fertility_counselling | should | minor | 3 | The response offers fertility / ovarian-function counselling (abbreviated R-CHOP has low gonadotoxicity; referral to reproductive medicine offered since she is undecided about further pregnancy). |
| fit_goals | must | important | 5 | The response judges her fit (ECOG 0, no limiting comorbidity) for curative-intent therapy with a high cure probability, and addresses her goals of continuing to work and avoiding neck radiation. |
