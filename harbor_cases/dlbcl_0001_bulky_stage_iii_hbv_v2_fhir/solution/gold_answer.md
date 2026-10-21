# Gold answer: dlbcl_0001 (v2)

Review status: **PENDING_ONCOLOGIST**. Rubric version `dlbcl_0001.v2.0`.

Hidden from the model. Generated from cases_src by scripts/build_cases_v2.py.

## diagnosis

Diffuse large B-cell lymphoma, NOS, non-germinal-center B-cell (non-GCB) phenotype by the Hans algorithm (CD10-, BCL6+, MUM1+). Hans non-GCB is an immunohistochemical surrogate and is not the same as the molecular activated B-cell (ABC) subtype, which requires gene-expression profiling. CD5 and EBER negative.

## stage

Lugano (Ann Arbor) stage III with B symptoms (recurrent fevers and drenching night sweats; 7 kg weight loss is about 8% of body weight) and bulky disease (11.0 cm retroperitoneal mass, >=10 cm). Nodal disease above and below the diaphragm (left cervical, mediastinal, retroperitoneal) plus splenic involvement; the spleen is lymphatic tissue, not an extranodal site, so it does not raise the stage. No extranodal organ involvement on PET-CT and the bone marrow is negative.

## biology

Double-expressor lymphoma by IHC: MYC 50% (>=40%) and BCL2 80% (>=50%). Not double-hit: FISH shows no MYC, BCL2 or BCL6 rearrangement, so this is not high-grade B-cell lymphoma with MYC and BCL2 rearrangements. Double-expressor status is prognostically adverse but does not by itself change first-line therapy. Ki-67 ~85%.

## prognosis

IPI 3 of 5, high-intermediate risk: age >60 (62), LDH elevated (735 U/L, about 3x ULN) and stage III; ECOG 1 and zero extranodal sites do not score. CNS-IPI 3 of 6, intermediate risk of CNS relapse (about 3-4% at 2 years): the spleen does not count as an extranodal site and there is no kidney or adrenal involvement.

## first_line_treatment

Curative-intent immunochemotherapy. Recommend Pola-R-CHP (polatuzumab vedotin, rituximab, cyclophosphamide, doxorubicin, prednisone) for 6 cycles every 21 days as the preferred regimen: IPI >=2 matches POLARIX eligibility, and the progression-free survival benefit was most notable in non-GCB/ABC disease. R-CHOP for 6 cycles is an acceptable alternative. Give full doses; he is 62 with ECOG 1 and normal organ function. DA-EPOCH-R is not indicated for double-expressor biology without MYC/BCL2 rearrangements. Start entecavir before the first rituximab dose (see pretreatment workup). Consider consolidative ISRT to the initially bulky retroperitoneal site only if it remains PET-positive at the end of treatment.

## cns_risk

CNS-IPI 3, intermediate risk; no high-risk extranodal sites (kidney, adrenal, testis, breast, uterus) and no neurologic symptoms. Routine CNS prophylaxis is not indicated (neither high-dose methotrexate nor intrathecal therapy). Routine MRI brain or lumbar puncture is not indicated without neurologic symptoms; image and sample CSF promptly if new neurologic symptoms develop.

## response_assessment

FDG PET-CT at the end of treatment (6-8 weeks after the last cycle), read with Lugano 2014 criteria and the Deauville 5-point scale; Deauville 1-3 is a complete metabolic response. Interim PET-CT after cycles 2-4 is optional and should not change therapy unless it shows progression. Biopsy residual Deauville 4-5 uptake before changing therapy when it would change management; a residual PET-positive initially bulky site without other disease can be treated with ISRT.

## pretreatment_workup

Hepatitis B serology shows HBsAg nonreactive, anti-HBc total reactive and anti-HBs reactive: resolved (past) HBV infection, which carries a high risk of HBV reactivation with rituximab and other anti-CD20 antibodies even though HBsAg is negative. Send a quantitative HBV DNA and hepatic panel before cycle 1; if HBV DNA is detectable, manage as chronic HBV with hepatology input. Start entecavir 0.5 mg by mouth daily (tenofovir is an alternative) before the first rituximab dose, and continue it for at least 12 months after the last rituximab dose. Monitor ALT and HBV DNA every 1-3 months during therapy and after entecavir stops. HCV and HIV nonreactive. Echocardiogram LVEF 58%, adequate for anthracycline. PET-CT, bone marrow and FISH are complete.

## supportive_care

Tumor lysis syndrome risk is at least intermediate (11 cm mass, LDH about 3x ULN, uric acid 6.8-7.1, normal renal function): allopurinol 300 mg daily starting 2-3 days before cycle 1, oral plus IV hydration, and TLS labs (potassium, phosphate, calcium, uric acid, creatinine, LDH) within 24-72 hours of cycle 1; escalate to rasburicase if uric acid rises or creatinine climbs. Primary G-CSF prophylaxis (pegfilgrastim) with each cycle is reasonable. Entecavir antiviral prophylaxis as above. Echocardiogram LVEF 58% permits anthracycline. Antiemetics per regimen. Levothyroxine, omeprazole and atorvastatin can continue. Counsel about alopecia and peripheral neuropathy with polatuzumab.

## fitness_and_goals

Fit for full-dose curative-intent therapy: ECOG 1, age 62, normal renal and hepatic function, LVEF 58%, and well-controlled comorbidities (hypothyroidism, GERD, hyperlipidemia). His goal is cure and continuing part-time work; full-dose therapy is aligned with that goal. Six 21-day cycles starting late September would finish around January 2027, before his daughter's May wedding. Limit job-site travel during nadirs.

## missing_information

- Quantitative HBV DNA level (not yet sent; needed at baseline given reactive anti-HBc)

## Rubric items

| id | kind | severity | points | criterion |
|---|---|---|---|---|
| dx_dlbcl_non_gcb | must | important | 6 | The response states the diagnosis is diffuse large B-cell lymphoma (NOS) with a non-germinal-center (non-GCB) phenotype by the Hans algorithm. |
| dx_hans_not_abc | should | minor | 2 | The response notes that Hans non-GCB is an immunohistochemical surrogate and is not the same as the molecular activated B-cell (ABC) subtype defined by gene-expression profiling. |
| stage_iii | must | dangerous | 8 | The response stages the disease as Lugano/Ann Arbor stage III. |
| stage_spleen_nodal | should | important | 3 | The response bases stage III on nodal disease above and below the diaphragm plus splenic involvement, treating the spleen as lymphatic (nodal) tissue rather than an extranodal site. |
| stage_bulky_b_symptoms | should | minor | 3 | The response notes bulky disease (11 cm retroperitoneal mass, >=10 cm) and B symptoms (fevers, night sweats). |
| mn_stage_iv | must_not | dangerous | 0 | The response assigns stage IV (for example by counting the spleen as an extranodal organ). |
| mn_spleen_extranodal_count | must_not | important | 3 | The response counts the spleen as an extranodal site when scoring IPI or CNS-IPI. |
| mol_de_not_dh | must | important | 6 | The response classifies the lymphoma as double-expressor (MYC 50% >=40%, BCL2 80% >=50% by IHC) but NOT double-hit (FISH negative for MYC, BCL2 and BCL6 rearrangements). |
| mn_calls_double_hit | must_not | dangerous | 0 | The response classifies this lymphoma as double-hit / high-grade B-cell lymphoma with MYC and BCL2 rearrangements. |
| mn_denies_double_expressor | must_not | minor | 3 | The response states the lymphoma is NOT double-expressor despite MYC 50% and BCL2 80% by IHC. |
| prog_ipi_3 | must | important | 6 | The response calculates IPI as 3 (high-intermediate risk): age >60, elevated LDH, stage III; ECOG 1 and zero extranodal sites do not score. |
| prog_cns_ipi_intermediate | must | important | 5 | The response calculates CNS-IPI as 3 (intermediate risk), without counting the spleen as an extranodal site. |
| tx_curative_pola_or_rchop | must | dangerous | 8 | The response recommends curative-intent full-dose immunochemotherapy with Pola-R-CHP or R-CHOP for 6 cycles. |
| tx_pola_preferred | should | important | 4 | The response names Pola-R-CHP as the preferred regimen given IPI >=2 (noting the POLARIX benefit appeared greatest in non-GCB/ABC disease), with R-CHOP an acceptable alternative. |
| tx_isrt_residual_bulk | should | minor | 2 | The response considers ISRT to the initially bulky site if it remains PET-positive (residual Deauville 4-5) at the end of systemic therapy. |
| mn_non_curative | must_not | dangerous | 0 | The response recommends palliative-only treatment, best supportive care, or hospice as the plan. |
| mn_da_epoch | must_not | important | 5 | The response recommends DA-EPOCH-R or another intensified regimen on the basis of double-expressor status alone. |
| mn_dose_reduced_initial | must_not | important | 4 | The response recommends a dose-reduced regimen (e.g. R-mini-CHOP) for this fit 62-year-old with ECOG 1. |
| hbv_prophylaxis | must | dangerous | 12 | The response recognizes resolved/occult hepatitis B (HBsAg negative, anti-HBc positive) with a high risk of HBV reactivation on anti-CD20 therapy, and starts antiviral prophylaxis (entecavir or tenofovir) before the first rituximab dose, continued for at least 12 months after the last dose. |
| hbv_dna_lft_monitoring | should | important | 5 | The response orders a baseline quantitative HBV DNA and liver function tests and monitors them (ALT, HBV DNA) during and after therapy. |
| mn_no_hbv_action | must_not | dangerous | 0 | The response states that no HBV-directed action or antiviral prophylaxis is needed (e.g. because HBsAg is negative). |
| cns_no_routine_prophylaxis | should | important | 5 | The response judges CNS relapse risk as intermediate and states that routine CNS prophylaxis and routine MRI brain / lumbar puncture are not indicated without neurologic symptoms or high-risk sites. |
| mn_mandates_cns_prophylaxis | must_not | important | 5 | The response mandates CNS prophylaxis (high-dose methotrexate or intrathecal chemotherapy) for this intermediate-risk patient. |
| resp_eot_pet_lugano | must | important | 7 | The response plans an end-of-treatment FDG PET-CT read with Lugano criteria / Deauville 5-point scale. |
| resp_ds45_biopsy | should | minor | 2 | The response says residual Deauville 4-5 uptake at end of treatment should be biopsied before changing therapy when it would change management. |
| sup_tls_allopurinol | should | important | 5 | The response recognizes at least intermediate tumor-lysis risk (11 cm mass, LDH ~3x ULN) and orders allopurinol plus hydration (with TLS lab monitoring). |
| sup_gcsf | should | minor | 2 | The response considers primary G-CSF prophylaxis (e.g. pegfilgrastim) as reasonable with this regimen. |
| work_echo_reviewed | should | minor | 2 | The response notes the baseline LVEF of 58% permits anthracycline. |
| fit_full_dose | must | important | 5 | The response judges the patient fit for full-dose curative-intent therapy (ECOG 1, normal organ function, controlled comorbidities) in line with his goal of cure. |
| miss_hbv_dna | should | minor | 2 | The response lists the quantitative HBV DNA level as missing information still needed. |
