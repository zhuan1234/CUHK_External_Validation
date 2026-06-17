# Reproducible OCTA + Cho AUC Workflow Results

## Input And Alignment

- OCTA file: `C:/Users/25124968R/Desktop/CUHK/CUHK_OCTA_OD_260614.csv`.
- Cho file: `C:/Users/25124968R/Desktop/CUHK/CUHK_Cho_OD_260614.csv`.
- Cho dictionary: `C:/Users/25124968R/Desktop/CUHK/cho_Variables.xlsx`.
- Final common OD analysis set: n=137, unique IDs=137.
- Sex mismatches between OCTA and Cho after current cleanup: 0.

## QC And Module Construction

- OCTA: grid-level QC -> module median -> median imputation if needed -> module score scale; final modules: CCFA, CT, CVI. CFA was checked but excluded because of high correlation with CCFA.
- Cho/CFP: Whole-region variables from the dictionary -> variable-level QC -> variable-level median imputation -> variable-level z-score -> module median -> module score scale.

OCTA QC summary:

| module | input_grid_columns | retained_columns | removed_missing_rate_gt_90pct | removed_low_iqr |
| ------ | ------------------ | ---------------- | ----------------------------- | --------------- |
| CCFA   | 63                 | 63               | 0                             | 0               |
| CFA    | 63                 | 60               | 0                             | 3               |
| CT     | 63                 | 63               | 0                             | 0               |
| CVI    | 63                 | 59               | 0                             | 4               |

Cho QC summary:

| category        | matched_variables | retained_variables | removed_missing_rate_gt_90pct | removed_valid_n_lt_threshold | removed_low_iqr |
| --------------- | ----------------- | ------------------ | ----------------------------- | ---------------------------- | --------------- |
| Density         | 10                | 10                 | 0                             | 0                            | 0               |
| Complexity      | 11                | 11                 | 0                             | 0                            | 0               |
| Calibre         | 16                | 16                 | 0                             | 0                            | 0               |
| Tortuosity      | 24                | 23                 | 0                             | 0                            | 1               |
| Branching Angle | 14                | 14                 | 0                             | 0                            | 0               |

## Endpoint Counts

| endpoint                    | definition              | n   | events | controls | event_rate |
| --------------------------- | ----------------------- | --- | ------ | -------- | ---------- |
| High myopia                 | SE <= -6.00 D           | 137 | 24     | 113      | 0.175      |
| Moderate myopia one-vs-rest | -6.00 D < SE <= -0.50 D | 137 | 91     | 46       | 0.664      |
| AL >= 26mm                  | AL >= 26 mm             | 137 | 25     | 112      | 0.182      |

## AUC Performance

Primary interpretation should use `cv_auc`; `apparent_auc` is in-sample and more optimistic.

| endpoint                    | model                           | events | controls | apparent_auc | cv_auc | cv_auc_mean | cv_auc_sd |
| --------------------------- | ------------------------------- | ------ | -------- | ------------ | ------ | ----------- | --------- |
| High myopia                 | Model 1 Clinical                | 24     | 113      | 0.635        | 0.487  | 0.505       | 0.050     |
| High myopia                 | Model 2 Clinical + Cho          | 24     | 113      | 0.788        | 0.682  | 0.671       | 0.040     |
| High myopia                 | Model 3 Clinical + OCTA         | 24     | 113      | 0.790        | 0.741  | 0.726       | 0.029     |
| High myopia                 | Model 4 Clinical + OCTA_nonflow | 24     | 113      | 0.700        | 0.620  | 0.619       | 0.035     |
| High myopia                 | Model 5 Clinical + OCTA + Cho   | 24     | 113      | 0.861        | 0.750  | 0.733       | 0.039     |
| Moderate myopia one-vs-rest | Model 1 Clinical                | 91     | 46       | 0.692        | 0.640  | 0.650       | 0.017     |
| Moderate myopia one-vs-rest | Model 2 Clinical + Cho          | 91     | 46       | 0.746        | 0.644  | 0.639       | 0.029     |
| Moderate myopia one-vs-rest | Model 3 Clinical + OCTA         | 91     | 46       | 0.726        | 0.662  | 0.655       | 0.023     |
| Moderate myopia one-vs-rest | Model 4 Clinical + OCTA_nonflow | 91     | 46       | 0.722        | 0.669  | 0.662       | 0.019     |
| Moderate myopia one-vs-rest | Model 5 Clinical + OCTA + Cho   | 91     | 46       | 0.797        | 0.693  | 0.685       | 0.029     |
| AL >= 26mm                  | Model 1 Clinical                | 25     | 112      | 0.741        | 0.684  | 0.669       | 0.030     |
| AL >= 26mm                  | Model 2 Clinical + Cho          | 25     | 112      | 0.745        | 0.668  | 0.652       | 0.030     |
| AL >= 26mm                  | Model 3 Clinical + OCTA         | 25     | 112      | 0.802        | 0.763  | 0.736       | 0.024     |
| AL >= 26mm                  | Model 4 Clinical + OCTA_nonflow | 25     | 112      | 0.766        | 0.736  | 0.714       | 0.024     |
| AL >= 26mm                  | Model 5 Clinical + OCTA + Cho   | 25     | 112      | 0.805        | 0.710  | 0.684       | 0.027     |

## Key AUC Differences

Differences are paired bootstrap estimates based on repeated-CV probabilities.

| endpoint                    | contrast                                                      | delta_cv_auc | ci_low | ci_high | p_bootstrap |
| --------------------------- | ------------------------------------------------------------- | ------------ | ------ | ------- | ----------- |
| High myopia                 | Model 2 Clinical + Cho minus Model 3 Clinical + OCTA          | -0.059       | -0.222 | 0.090   | 0.469       |
| High myopia                 | Model 2 Clinical + Cho minus Model 4 Clinical + OCTA_nonflow  | 0.062        | -0.078 | 0.200   | 0.387       |
| High myopia                 | Model 3 Clinical + OCTA minus Model 4 Clinical + OCTA_nonflow | 0.121        | 0.025  | 0.225   | 0.017       |
| High myopia                 | Model 5 Clinical + OCTA + Cho minus Model 2 Clinical + Cho    | 0.068        | -0.028 | 0.169   | 0.161       |
| High myopia                 | Model 5 Clinical + OCTA + Cho minus Model 3 Clinical + OCTA   | 0.009        | -0.100 | 0.114   | 0.886       |
| Moderate myopia one-vs-rest | Model 2 Clinical + Cho minus Model 3 Clinical + OCTA          | -0.018       | -0.116 | 0.081   | 0.734       |
| Moderate myopia one-vs-rest | Model 2 Clinical + Cho minus Model 4 Clinical + OCTA_nonflow  | -0.025       | -0.110 | 0.076   | 0.634       |
| Moderate myopia one-vs-rest | Model 3 Clinical + OCTA minus Model 4 Clinical + OCTA_nonflow | -0.007       | -0.031 | 0.017   | 0.635       |
| Moderate myopia one-vs-rest | Model 5 Clinical + OCTA + Cho minus Model 2 Clinical + Cho    | 0.049        | -0.023 | 0.117   | 0.174       |
| Moderate myopia one-vs-rest | Model 5 Clinical + OCTA + Cho minus Model 3 Clinical + OCTA   | 0.031        | -0.039 | 0.103   | 0.416       |
| AL >= 26mm                  | Model 2 Clinical + Cho minus Model 3 Clinical + OCTA          | -0.095       | -0.212 | 0.019   | 0.114       |
| AL >= 26mm                  | Model 2 Clinical + Cho minus Model 4 Clinical + OCTA_nonflow  | -0.068       | -0.180 | 0.047   | 0.263       |
| AL >= 26mm                  | Model 3 Clinical + OCTA minus Model 4 Clinical + OCTA_nonflow | 0.027        | -0.035 | 0.088   | 0.383       |
| AL >= 26mm                  | Model 5 Clinical + OCTA + Cho minus Model 2 Clinical + Cho    | 0.041        | -0.056 | 0.143   | 0.377       |
| AL >= 26mm                  | Model 5 Clinical + OCTA + Cho minus Model 3 Clinical + OCTA   | -0.053       | -0.121 | 0.007   | 0.092       |

## Interpretation

- Current files are fully aligned at n=137; no Sex mismatch remains in the aligned OCTA/Cho cohort.
- Moderate myopia one-vs-rest has 91/137 events, matching the updated note.
- AL >= 26mm is retained as a separate binary endpoint.
- Cho performance should be compared mainly with OCTA_nonflow for the fair non-flow comparison; full OCTA additionally includes CCFA.