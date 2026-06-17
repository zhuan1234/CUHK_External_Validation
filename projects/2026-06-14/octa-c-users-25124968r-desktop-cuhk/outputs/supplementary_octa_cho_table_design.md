# Supplementary Table Design

## Supplementary Table 1. Definition of OCTA and Cho/CFP biomarker modules.

| Domain  | Module / biomarker group | Components used for score                                  | Interpretation                         | Used in model(s)          |
| ------- | ------------------------ | ---------------------------------------------------------- | -------------------------------------- | ------------------------- |
| OCTA    | CCFA                     | Median of retained choriocapillaris flow-area grid values  | Flow-related choriocapillaris signal   | Model 3, Model 5          |
| OCTA    | CT                       | Median of retained choroidal thickness grid values         | Structural choroidal thickness         | Model 3, Model 4, Model 5 |
| OCTA    | CVI                      | Median of retained choroidal vascularity index grid values | Relative choroidal vascularity         | Model 3, Model 4, Model 5 |
| Cho/CFP | Density                  | Whole-region GAN-derived vessel-density metrics            | Global choroidal vessel density        | Model 2, Model 5          |
| Cho/CFP | Complexity               | Whole-region GAN-derived complexity metrics                | Branching/structural complexity        | Model 2, Model 5          |
| Cho/CFP | Calibre                  | Whole-region GAN-derived calibre metrics                   | Vessel width/calibre profile           | Model 2, Model 5          |
| Cho/CFP | Tortuosity               | Whole-region GAN-derived tortuosity metrics                | Curvature and vessel path irregularity | Model 2, Model 5          |
| Cho/CFP | Branching Angle          | Whole-region GAN-derived branching-angle metrics           | Angular branching geometry             | Model 2, Model 5          |

Note. CCFA, choriocapillaris flow area; CT, choroidal thickness; CVI, choroidal vascularity index; CFP, color fundus photography.

## Supplementary Table 2. Characteristics of the final OD analytic cohort stratified by refractive status.

| Variables                                | Total (n = 137)      | Non-myopia (n = 22)  | Moderate myopia (n = 91) | High myopia (n = 24) |
| ---------------------------------------- | -------------------- | -------------------- | ------------------------ | -------------------- |
| Age, median (Q1, Q3)                     | 12.0 (10.0, 13.0)    | 13.0 (12.0, 14.0)    | 11.0 (10.0, 13.0)        | 13.0 (10.8, 14.0)    |
| Sex = 1, n (%)                           | 69 (50.4)            | 10 (45.5)            | 47 (51.6)                | 12 (50.0)            |
| Sex = 2, n (%)                           | 68 (49.6)            | 12 (54.5)            | 44 (48.4)                | 12 (50.0)            |
| Axial length, median (Q1, Q3), mm        | 24.91 (23.97, 25.71) | 23.52 (23.11, 23.96) | 24.91 (24.21, 25.49)     | 26.39 (25.82, 26.95) |
| Spherical equivalent, median (Q1, Q3), D | -3.50 (-5.25, -1.00) | 0.25 (0.00, 0.69)    | -3.50 (-4.88, -2.12)     | -6.75 (-8.00, -6.50) |
| AL >= 26 mm, n (%)                       | 25 (18.2)            | 0 (0.0)              | 9 (9.9)                  | 16 (66.7)            |

Note. Sex was kept as the coded variable available in the source files. Moderate and high myopia are mutually exclusive by SE definition.

## Supplementary Table 3. Quality control and module construction summary.

| Source  | Module / category | Candidate n | Retained n | Removed variables                                 | Processing note                                                              |
| ------- | ----------------- | ----------- | ---------- | ------------------------------------------------- | ---------------------------------------------------------------------------- |
| OCTA    | CCFA              | 63          | 63         | missing >90%: 0; low IQR: 0                       | Grid-level QC -> module median -> median imputation if needed -> scale       |
| OCTA    | CFA               | 63          | 60         | missing >90%: 0; low IQR: 3                       | QC checked; excluded from final models because of high correlation with CCFA |
| OCTA    | CT                | 63          | 63         | missing >90%: 0; low IQR: 0                       | Grid-level QC -> module median -> median imputation if needed -> scale       |
| OCTA    | CVI               | 63          | 59         | missing >90%: 0; low IQR: 4                       | Grid-level QC -> module median -> median imputation if needed -> scale       |
| Cho/CFP | Density           | 10          | 10         | missing >90%: 0; valid n<threshold: 0; low IQR: 0 | Variable median imputation -> variable z-score -> module median -> scale     |
| Cho/CFP | Complexity        | 11          | 11         | missing >90%: 0; valid n<threshold: 0; low IQR: 0 | Variable median imputation -> variable z-score -> module median -> scale     |
| Cho/CFP | Calibre           | 16          | 16         | missing >90%: 0; valid n<threshold: 0; low IQR: 0 | Variable median imputation -> variable z-score -> module median -> scale     |
| Cho/CFP | Tortuosity        | 24          | 23         | missing >90%: 0; valid n<threshold: 0; low IQR: 1 | Variable median imputation -> variable z-score -> module median -> scale     |
| Cho/CFP | Branching Angle   | 14          | 14         | missing >90%: 0; valid n<threshold: 0; low IQR: 0 | Variable median imputation -> variable z-score -> module median -> scale     |

Note. Both data sources removed variables with missing rate >90% and near-zero IQR. Cho/CFP additionally required valid n >= 20 or >=10% of total n.

## Supplementary Table 4. Binary outcomes and prediction model specifications.

| Section | Name                            | Definition / predictors                      | Event count |
| ------- | ------------------------------- | -------------------------------------------- | ----------- |
| Outcome | High myopia                     | SE <= -6.00 D                                | 24/137      |
| Outcome | Moderate myopia                 | -6.00 D < SE <= -0.50 D                      | 91/137      |
| Outcome | Long axial length               | AL >= 26 mm                                  | 25/137      |
| Model   | Model 1 Clinical                | Age + Sex                                    |             |
| Model   | Model 2 Clinical + Cho          | Age + Sex + 5 Cho/CFP modules                |             |
| Model   | Model 3 Clinical + OCTA         | Age + Sex + CCFA + CT + CVI                  |             |
| Model   | Model 4 Clinical + OCTA_nonflow | Age + Sex + CT + CVI                         |             |
| Model   | Model 5 Clinical + OCTA + Cho   | Age + Sex + OCTA modules + 5 Cho/CFP modules |             |

Note. All models used the final aligned OD analysis set (n=137). Age, Sex, AL and SE were taken from the OCTA file as the canonical clinical/outcome source.

## Supplementary Table 5. Cross-validated AUC performance of the five prediction models.

| Endpoint                                | Events / N | Clinical | + Cho | + OCTA | + OCTA_nonflow | + OCTA + Cho |
| --------------------------------------- | ---------- | -------- | ----- | ------ | -------------- | ------------ |
| High myopia (SE <= -6.00D)              | 24/137     | 0.487    | 0.682 | 0.741  | 0.620          | 0.750        |
| Moderate myopia (-6.00D < SE <= -0.50D) | 91/137     | 0.640    | 0.644 | 0.662  | 0.669          | 0.693        |
| Long axial length (AL >= 26mm)          | 25/137     | 0.684    | 0.668 | 0.763  | 0.736          | 0.710        |

Note. Values are repeated 5-fold cross-validated AUCs. In-sample AUCs were not prioritized for interpretation because they are more optimistic.

## Supplementary Table 6. Key pairwise differences in cross-validated AUC.

| Endpoint                                | Comparison             | Delta CV AUC | 95% CI          | p     | Interpretation                    |
| --------------------------------------- | ---------------------- | ------------ | --------------- | ----- | --------------------------------- |
| High myopia (SE <= -6.00D)              | Cho vs OCTA            | -0.059       | -0.222 to 0.090 | 0.469 | NS; comparable within this sample |
| High myopia (SE <= -6.00D)              | Cho vs OCTA_nonflow    | 0.062        | -0.078 to 0.200 | 0.387 | NS; comparable within this sample |
| High myopia (SE <= -6.00D)              | OCTA flow contribution | 0.121        | 0.025 to 0.225  | 0.017 | Significant                       |
| High myopia (SE <= -6.00D)              | Add Cho beyond OCTA    | 0.009        | -0.100 to 0.114 | 0.886 | NS                                |
| Moderate myopia (-6.00D < SE <= -0.50D) | Cho vs OCTA            | -0.018       | -0.116 to 0.081 | 0.734 | NS; comparable within this sample |
| Moderate myopia (-6.00D < SE <= -0.50D) | Cho vs OCTA_nonflow    | -0.025       | -0.110 to 0.076 | 0.634 | NS; comparable within this sample |
| Moderate myopia (-6.00D < SE <= -0.50D) | OCTA flow contribution | -0.007       | -0.031 to 0.017 | 0.635 | NS                                |
| Moderate myopia (-6.00D < SE <= -0.50D) | Add Cho beyond OCTA    | 0.031        | -0.039 to 0.103 | 0.416 | NS                                |
| Long axial length (AL >= 26mm)          | Cho vs OCTA            | -0.095       | -0.212 to 0.019 | 0.114 | NS; comparable within this sample |
| Long axial length (AL >= 26mm)          | Cho vs OCTA_nonflow    | -0.068       | -0.180 to 0.047 | 0.263 | NS; comparable within this sample |
| Long axial length (AL >= 26mm)          | OCTA flow contribution | 0.027        | -0.035 to 0.088 | 0.383 | NS                                |
| Long axial length (AL >= 26mm)          | Add Cho beyond OCTA    | -0.053       | -0.121 to 0.007 | 0.092 | NS                                |

Note. Delta CV AUC equals the first model minus the second model. Confidence intervals and p values were estimated using paired bootstrap on repeated-CV probabilities.
