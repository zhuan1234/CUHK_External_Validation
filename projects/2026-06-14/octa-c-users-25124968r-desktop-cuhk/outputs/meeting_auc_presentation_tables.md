# Meeting-ready AUC Tables

Primary metric: repeated 5-fold cross-validated AUC (cv_auc_from_mean_probability).

## Table 1. Model Performance Overview

| Endpoint                                | Events / N | M1 Clinical | M2 + Cho | M3 + OCTA | M4 + OCTA_nonflow | M5 + OCTA + Cho | Meeting message       |
| --------------------------------------- | ---------- | ----------- | -------- | --------- | ----------------- | --------------- | --------------------- |
| High myopia (SE <= -6.00D)              | 24/137     | 0.487       | 0.682    | 0.741     | 0.62              | 0.75            | Best: M5 + OCTA + Cho |
| Moderate myopia (-6.00D < SE <= -0.50D) | 91/137     | 0.64        | 0.644    | 0.662     | 0.669             | 0.693           | Best: M5 + OCTA + Cho |
| Long axial length (AL >= 26mm)          | 25/137     | 0.684       | 0.668    | 0.763     | 0.736             | 0.71            | Best: M3 + OCTA       |

## Table 2. Key Pairwise AUC Differences

Delta CV AUC = first model minus second model; NS = not statistically significant.

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

## Presentation Take-home

- High myopia: Cho AUC is below full OCTA but above OCTA_nonflow by point estimate; Cho vs OCTA and Cho vs OCTA_nonflow are both not statistically significant.
- Moderate myopia: Cho, OCTA, and OCTA_nonflow show similar CV AUCs; pairwise differences are not statistically significant.
- AL >= 26mm: Cho has lower point-estimate AUC than OCTA/OCTA_nonflow, but differences are not statistically significant in this cohort.
- Combined OCTA + Cho is numerically best for High and Moderate myopia, but adding Cho beyond OCTA is not statistically significant in these displayed endpoints.