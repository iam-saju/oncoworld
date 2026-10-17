# breast_0001 gold answer (hidden from the model)

Status: draft v0.2 from Harbor_Oncology_Case_Breast_0001.pdf. Not physician-reviewed.
Guideline set: US NCCN Guidelines for Breast Cancer (decided by project owner, 2026-10-10). Record the exact
NCCN version at physician sign-off.

Radiotherapy: required for this patient (decided by project owner, 2026-10-10). Under NCCN, omitting breast
radiotherapy after lumpectomy is an option only for selected patients aged 70 or older with small, node-negative,
ER-positive tumors on endocrine therapy; at 58 it is not appropriate, so omission stays a critical error.

| Domain | Gold answer |
|---|---|
| Diagnosis | Invasive ductal carcinoma, no special type (NST), Nottingham grade 2, 1.8 cm, margins negative (4 mm), no LVI. |
| Stage | pT1c pN0(sn) cM0, AJCC 8th edition. Anatomic stage IA; pathological prognostic stage IA. |
| Biology | HR-positive (ER 95% strong, PR 80%), HER2-negative. HER2 IHC 1+ is HER2-negative (HER2-low); no anti-HER2 therapy. |
| Genomic risk | 21-gene Recurrence Score 14 = low risk. |
| Chemotherapy | Not indicated: node-negative, postmenopausal, RS 14. Trap: grade 2 and Ki-67 15% may tempt toward chemotherapy. |
| Endocrine | Aromatase inhibitor for 5 years; extended therapy up to 10 years may be considered; tamoxifen acceptable alternative. |
| Radiotherapy | Whole-breast radiotherapy after lumpectomy. Partial-breast irradiation also accepted (see rubric deviations). |
| Supportive | Baseline DEXA, calcium/vitamin D, bone-health monitoring on an aromatase inhibitor. |
| Missing information | Baseline DEXA result; patient preferences; expected tolerance of endocrine therapy. |

## Expected stage as mCODE resources

If the answer were written back to the chart, the stage would be an mCODE TNM Stage Group:

| Element | Code |
|---|---|
| Observation.code | SNOMED 399588009 Pathologic TNM stage grouping |
| Observation.method | SNOMED 897275008 AJCC Cancer Staging Manual, 8th edition |
| Observation.value | SNOMED 1222724007 IA (AJCC) |
| pT member | SNOMED 384625004 pT category = 1229846008 pT1c (AJCC) |
| pN member | SNOMED 371494008 pN category = 1229947003 pN0 (AJCC); (sn) suffix noted in text |
| M member | SNOMED 399387003 cM category = 1229901006 cM0 (AJCC) |

The FHIR input deliberately contains no stage, risk category or treatment plan: those are what is graded.
