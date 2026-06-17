# OCTA 3-module data modeling report

Input file: `C:\Users\25124968R\Desktop\CUHK\CUHK_OCTA_OD_260614.csv`
Rows: 137, columns: 260

## Methods notes
- QC was applied to OCTA grid columns only: remove `missing_rate > 90%`, then remove near-zero variation columns with `IQR <= 1e-8`.
- Module scores are row-wise medians across retained grid columns. Missing module summaries were median-imputed before z-scoring.
- Revised biomarker module set for Step 5, Step 6, and Step 8: `CCFA`, `CT`, and `CVI`. `CFA` was excluded from the final module set because it was highly collinear with `CCFA` in the first run.
- `scale()` was implemented as `(x - mean) / sample_sd`, matching R's default sample standard deviation behavior.
- Outcomes (`AL`, `SE`) were not imputed. Prediction models used `Age + Sex` as baseline and `Age + Sex + three OCTA z-scores` as the full model.
- ICC and Bland-Altman are strict agreement tools only when two variables are intended to measure the same construct on compatible scales. Since the retained 3 modules have different raw units/constructs, Step 6 ICC and Bland-Altman are reported as exploratory z-score agreement checks.

## QC summary
| module | module_label               | input_grid_columns | removed_missing_rate_gt_90pct | removed_low_iqr | retained_columns | median_missing_rate | max_missing_rate | min_iqr | median_iqr |
| ------ | -------------------------- | ------------------ | ----------------------------- | --------------- | ---------------- | ------------------- | ---------------- | ------- | ---------- |
| CCFA   | Choriocapillaris Flow Area | 63                 | 0                             | 0               | 63               | 0.0000              | 0.0000           | 0.0004  | 1.0464     |
| CFA    | Choroid Flow Area          | 63                 | 0                             | 3               | 60               | 0.0000              | 0.0000           | 0.0000  | 1.3347     |
| CT     | Choroid Thickness          | 63                 | 0                             | 0               | 63               | 0.0000              | 0.0073           | 33.1233 | 72.6237    |
| CVI    | CVI                        | 63                 | 0                             | 4               | 59               | 0.0000              | 0.0073           | 0.0000  | 0.0949     |

## Imputation and scaling
| variable    | missing_before_imputation | imputation_method              | imputation_value |
| ----------- | ------------------------- | ------------------------------ | ---------------- |
| CCFA_median | 0                         | median                         | 6.0591           |
| CT_median   | 0                         | median                         | 197.9555         |
| CVI_median  | 0                         | median                         | 0.4103           |
| Age_model   | 0                         | median                         | 12.0000          |
| Sex_model   | 0                         | mode for categorical covariate | 1.0000           |

| variable    | z_variable    | mean     | sample_sd |
| ----------- | ------------- | -------- | --------- |
| CCFA_median | CCFA_median_z | 5.8195   | 0.9519    |
| CT_median   | CT_median_z   | 199.7357 | 43.0249   |
| CVI_median  | CVI_median_z  | 0.4023   | 0.0619    |
| Age_model   | Age_z         | 12.8759  | 7.3549    |

## Module correlation matrix
| module                     | Choriocapillaris Flow Area | Choroid Thickness | CVI    |
| -------------------------- | -------------------------- | ----------------- | ------ |
| Choriocapillaris Flow Area | 1.0000                     | 0.4960            | 0.6671 |
| Choroid Thickness          | 0.4960                     | 1.0000            | 0.5496 |
| CVI                        | 0.6671                     | 0.5496            | 1.0000 |

## Biological validation
Pairwise z-score validation among retained modules:
| comparison                                      | scale   | n   | pearson_r | pearson_p | icc_2_1_absolute_agreement | bias_mean_difference | sd_difference | loa_lower_95 | loa_upper_95 | proportional_bias_slope | proportional_bias_p |
| ----------------------------------------------- | ------- | --- | --------- | --------- | -------------------------- | -------------------- | ------------- | ------------ | ------------ | ----------------------- | ------------------- |
| Choriocapillaris Flow Area vs Choroid Thickness | z-score | 137 | 0.4960    | 0.0000    | 0.4978                     | -0.0000              | 1.0040        | -1.9678      | 1.9678       | -0.0000                 | 1.0000              |
| Choriocapillaris Flow Area vs CVI               | z-score | 137 | 0.6671    | 0.0000    | 0.6687                     | 0.0000               | 0.8160        | -1.5993      | 1.5993       | 0.0000                  | 1.0000              |
| Choroid Thickness vs CVI                        | z-score | 137 | 0.5496    | 0.0000    | 0.5514                     | 0.0000               | 0.9491        | -1.8602      | 1.8602       | 0.0000                  | 1.0000              |

## Prediction model performance
| outcome | model        | n   | r2     | adj_r2 | rmse   | mae    | cv_r2_mean | cv_r2_sd | cv_rmse_mean | cv_rmse_sd | condition_number | delta_r2_vs_age_sex | partial_f_for_octa_block | partial_f_p_for_octa_block |
| ------- | ------------ | --- | ------ | ------ | ------ | ------ | ---------- | -------- | ------------ | ---------- | ---------------- | ------------------- | ------------------------ | -------------------------- |
| AL      | Age+Sex      | 137 | 0.1067 | 0.0934 | 1.2353 | 0.9626 | -0.1994    | 0.0798   | 1.4306       | 0.0481     | 2.6096           | NA                  | NA                       | NA                         |
| AL      | Age+Sex+OCTA | 137 | 0.4097 | 0.3871 | 1.0043 | 0.8038 | 0.2269     | 0.0377   | 1.1489       | 0.0278     | 3.5006           | 0.3029              | 22.4085                  | 0.0000                     |
| SE      | Age+Sex      | 137 | 0.0703 | 0.0564 | 3.1705 | 2.3331 | -0.2889    | 0.1141   | 3.7294       | 0.1670     | 2.6096           | NA                  | NA                       | NA                         |
| SE      | Age+Sex+OCTA | 137 | 0.4663 | 0.4459 | 2.4022 | 1.9104 | 0.2613     | 0.0519   | 2.8244       | 0.0983     | 3.5006           | 0.3960              | 32.3974                  | 0.0000                     |

## Full-model coefficients
| outcome | model        | term          | estimate | std_error | t_value  | p_value | ci_95_low | ci_95_high |
| ------- | ------------ | ------------- | -------- | --------- | -------- | ------- | --------- | ---------- |
| AL      | Age+Sex+OCTA | Intercept     | 25.1433  | 0.1238    | 203.0531 | 0.0000  | 24.8983   | 25.3882    |
| AL      | Age+Sex+OCTA | Age_model_z   | 0.1288   | 0.0947    | 1.3593   | 0.1764  | -0.0586   | 0.3162     |
| AL      | Age+Sex+OCTA | CCFA_median_z | -0.4692  | 0.1233    | -3.8069  | 0.0002  | -0.7130   | -0.2254    |
| AL      | Age+Sex+OCTA | CT_median_z   | -0.4475  | 0.1078    | -4.1507  | 0.0001  | -0.6607   | -0.2342    |
| AL      | Age+Sex+OCTA | CVI_median_z  | 0.0490   | 0.1270    | 0.3857   | 0.7003  | -0.2022   | 0.3002     |
| AL      | Age+Sex+OCTA | Sex_2_vs_1    | -0.4552  | 0.1760    | -2.5862  | 0.0108  | -0.8035   | -0.1070    |
| SE      | Age+Sex+OCTA | Intercept     | -3.3674  | 0.2962    | -11.3689 | 0.0000  | -3.9534   | -2.7815    |
| SE      | Age+Sex+OCTA | Age_model_z   | -0.1719  | 0.2266    | -0.7586  | 0.4495  | -0.6202   | 0.2764     |
| SE      | Age+Sex+OCTA | CCFA_median_z | 1.0746   | 0.2948    | 3.6449   | 0.0004  | 0.4914    | 1.6578     |
| SE      | Age+Sex+OCTA | CT_median_z   | 1.3692   | 0.2579    | 5.3095   | 0.0000  | 0.8590    | 1.8793     |
| SE      | Age+Sex+OCTA | CVI_median_z  | 0.0892   | 0.3037    | 0.2937   | 0.7694  | -0.5116   | 0.6901     |
| SE      | Age+Sex+OCTA | Sex_2_vs_1    | -0.4583  | 0.4211    | -1.0884  | 0.2784  | -1.2913   | 0.3747     |

## VIF
| outcome | predictor     | r2_against_other_predictors | vif    |
| ------- | ------------- | --------------------------- | ------ |
| AL      | Age_model_z   | 0.1359                      | 1.1573 |
| AL      | CCFA_median_z | 0.4895                      | 1.9588 |
| AL      | CT_median_z   | 0.3327                      | 1.4986 |
| AL      | CVI_median_z  | 0.5190                      | 2.0789 |
| AL      | Sex_2_vs_1    | 0.0062                      | 1.0062 |
| SE      | Age_model_z   | 0.1359                      | 1.1573 |
| SE      | CCFA_median_z | 0.4895                      | 1.9588 |
| SE      | CT_median_z   | 0.3327                      | 1.4986 |
| SE      | CVI_median_z  | 0.5190                      | 2.0789 |
| SE      | Sex_2_vs_1    | 0.0062                      | 1.0062 |

## Quick interpretation
- AL: full model R2=0.410 vs baseline R2=0.107; delta R2=0.303; OCTA block partial-F p=<0.001; repeated 5-fold CV R2=0.227.
- SE: full model R2=0.466 vs baseline R2=0.070; delta R2=0.396; OCTA block partial-F p=<0.001; repeated 5-fold CV R2=0.261.