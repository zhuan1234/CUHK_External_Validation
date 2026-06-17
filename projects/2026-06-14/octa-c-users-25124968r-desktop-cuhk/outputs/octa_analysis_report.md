# OCTA data modeling report

Input file: `C:\Users\25124968R\Desktop\CUHK\CUHK_OCTA_OD_260614.csv`
Rows: 140, columns: 260

## Methods notes
- QC was applied to OCTA grid columns only: remove `missing_rate > 90%`, then remove near-zero variation columns with `IQR <= 1e-8`.
- Module scores are row-wise medians across retained grid columns. Missing module summaries were median-imputed before z-scoring.
- `scale()` was implemented as `(x - mean) / sample_sd`, matching R's default sample standard deviation behavior.
- Outcomes (`AL`, `SE`) were not imputed. Prediction models used `Age + Sex` as baseline and `Age + Sex + four OCTA z-scores` as the full model.
- ICC and Bland-Altman are strict agreement tools only when two variables are intended to measure the same construct on compatible scales. Therefore the raw-scale primary agreement check is CCFA vs CFA; all other pairwise agreement checks are exploratory on z-scores.

## QC summary
| module | module_label               | input_grid_columns | removed_missing_rate_gt_90pct | removed_low_iqr | retained_columns | median_missing_rate | max_missing_rate | min_iqr | median_iqr |
| ------ | -------------------------- | ------------------ | ----------------------------- | --------------- | ---------------- | ------------------- | ---------------- | ------- | ---------- |
| CCFA   | Choriocapillaris Flow Area | 63                 | 0                             | 0               | 63               | 0.0000              | 0.0000           | 0.0004  | 0.9998     |
| CFA    | Choroid Flow Area          | 63                 | 0                             | 3               | 60               | 0.0000              | 0.0000           | 0.0000  | 1.2960     |
| CT     | Choroid Thickness          | 63                 | 0                             | 0               | 63               | 0.0000              | 0.0071           | 33.3687 | 70.9916    |
| CVI    | CVI                        | 63                 | 0                             | 4               | 59               | 0.0000              | 0.0071           | 0.0000  | 0.0949     |

## Imputation and scaling
| variable    | missing_before_imputation | imputation_method              | imputation_value |
| ----------- | ------------------------- | ------------------------------ | ---------------- |
| CCFA_median | 0                         | median                         | 6.0493           |
| CFA_median  | 0                         | median                         | 7.1042           |
| CT_median   | 0                         | median                         | 198.1313         |
| CVI_median  | 0                         | median                         | 0.4104           |
| Age_model   | 0                         | median                         | 12.0000          |
| Sex_model   | 0                         | mode for categorical covariate | 2.0000           |

| variable    | z_variable    | mean     | sample_sd |
| ----------- | ------------- | -------- | --------- |
| CCFA_median | CCFA_median_z | 5.8197   | 0.9419    |
| CFA_median  | CFA_median_z  | 6.9031   | 1.4162    |
| CT_median   | CT_median_z   | 200.2003 | 43.1183   |
| CVI_median  | CVI_median_z  | 0.4026   | 0.0614    |
| Age_model   | Age_z         | 12.8357  | 7.2871    |

## Module correlation matrix
| module                     | Choriocapillaris Flow Area | Choroid Flow Area | Choroid Thickness | CVI    |
| -------------------------- | -------------------------- | ----------------- | ----------------- | ------ |
| Choriocapillaris Flow Area | 1.0000                     | 0.9492            | 0.4912            | 0.6654 |
| Choroid Flow Area          | 0.9492                     | 1.0000            | 0.4667            | 0.6196 |
| Choroid Thickness          | 0.4912                     | 0.4667            | 1.0000            | 0.5530 |
| CVI                        | 0.6654                     | 0.6196            | 0.5530            | 1.0000 |

## Biological validation
Primary raw-scale validation:
| comparison                                      | scale                               | n   | pearson_r | pearson_p | icc_2_1_absolute_agreement | bias_mean_difference | sd_difference | loa_lower_95 | loa_upper_95 | proportional_bias_slope | proportional_bias_p |
| ----------------------------------------------- | ----------------------------------- | --- | --------- | --------- | -------------------------- | -------------------- | ------------- | ------------ | ------------ | ----------------------- | ------------------- |
| Choriocapillaris Flow Area vs Choroid Flow Area | raw medians, both flow-area modules | 140 | 0.9492    | 0.0000    | 0.6231                     | -1.0834              | 0.6004        | -2.2602      | 0.0935       | -0.4123                 | 0.0000              |

Exploratory pairwise z-score validation:
| comparison                                      | scale   | n   | pearson_r | pearson_p | icc_2_1_absolute_agreement | bias_mean_difference | sd_difference | loa_lower_95 | loa_upper_95 | proportional_bias_slope | proportional_bias_p |
| ----------------------------------------------- | ------- | --- | --------- | --------- | -------------------------- | -------------------- | ------------- | ------------ | ------------ | ----------------------- | ------------------- |
| Choriocapillaris Flow Area vs Choroid Flow Area | z-score | 140 | 0.9492    | 0.0000    | 0.9495                     | -0.0000              | 0.3188        | -0.6249      | 0.6249       | 0.0000                  | 1.0000              |
| Choriocapillaris Flow Area vs Choroid Thickness | z-score | 140 | 0.4912    | 0.0000    | 0.4930                     | -0.0000              | 1.0088        | -1.9772      | 1.9772       | -0.0000                 | 1.0000              |
| Choriocapillaris Flow Area vs CVI               | z-score | 140 | 0.6654    | 0.0000    | 0.6670                     | -0.0000              | 0.8180        | -1.6034      | 1.6034       | 0.0000                  | 1.0000              |
| Choroid Flow Area vs Choroid Thickness          | z-score | 140 | 0.4667    | 0.0000    | 0.4685                     | 0.0000               | 1.0327        | -2.0242      | 2.0242       | -0.0000                 | 1.0000              |
| Choroid Flow Area vs CVI                        | z-score | 140 | 0.6196    | 0.0000    | 0.6213                     | -0.0000              | 0.8723        | -1.7097      | 1.7097       | 0.0000                  | 1.0000              |
| Choroid Thickness vs CVI                        | z-score | 140 | 0.5530    | 0.0000    | 0.5548                     | -0.0000              | 0.9455        | -1.8532      | 1.8532       | 0.0000                  | 1.0000              |

## Prediction model performance
| outcome | model        | n   | r2     | adj_r2 | rmse   | mae    | cv_r2_mean | cv_r2_sd | cv_rmse_mean | cv_rmse_sd | condition_number | delta_r2_vs_age_sex | partial_f_for_octa_block | partial_f_p_for_octa_block |
| ------- | ------------ | --- | ------ | ------ | ------ | ------ | ---------- | -------- | ------------ | ---------- | ---------------- | ------------------- | ------------------------ | -------------------------- |
| AL      | Age+Sex      | 140 | 0.1049 | 0.0918 | 1.2265 | 0.9545 | -0.2054    | 0.1099   | 1.4217       | 0.0661     | 2.6351           | NA                  | NA                       | NA                         |
| AL      | Age+Sex+OCTA | 140 | 0.4116 | 0.3851 | 0.9944 | 0.7856 | 0.1899     | 0.0790   | 1.1655       | 0.0556     | 7.9669           | 0.3067              | 17.3318                  | 0.0000                     |
| SE      | Age+Sex      | 140 | 0.0693 | 0.0557 | 3.1553 | 2.3184 | -0.2986    | 0.1464   | 3.7212       | 0.2127     | 2.6351           | NA                  | NA                       | NA                         |
| SE      | Age+Sex+OCTA | 140 | 0.4701 | 0.4462 | 2.3808 | 1.8931 | 0.2445     | 0.0679   | 2.8400       | 0.1266     | 7.9669           | 0.4008              | 25.1524                  | 0.0000                     |

## Full-model coefficients
| outcome | model        | term          | estimate | std_error | t_value  | p_value | ci_95_low | ci_95_high |
| ------- | ------------ | ------------- | -------- | --------- | -------- | ------- | --------- | ---------- |
| AL      | Age+Sex+OCTA | Intercept     | 25.1352  | 0.1230    | 204.3335 | 0.0000  | 24.8919   | 25.3785    |
| AL      | Age+Sex+OCTA | Age_model_z   | 0.1364   | 0.0932    | 1.4631   | 0.1458  | -0.0480   | 0.3207     |
| AL      | Age+Sex+OCTA | CCFA_median_z | -0.0818  | 0.2924    | -0.2799  | 0.7800  | -0.6601   | 0.4965     |
| AL      | Age+Sex+OCTA | CFA_median_z  | -0.3998  | 0.2758    | -1.4494  | 0.1496  | -0.9453   | 0.1458     |
| AL      | Age+Sex+OCTA | CT_median_z   | -0.4324  | 0.1060    | -4.0776  | 0.0001  | -0.6421   | -0.2227    |
| AL      | Age+Sex+OCTA | CVI_median_z  | 0.0407   | 0.1251    | 0.3257   | 0.7452  | -0.2068   | 0.2882     |
| AL      | Age+Sex+OCTA | Sex_2_vs_1    | -0.4218  | 0.1730    | -2.4382  | 0.0161  | -0.7640   | -0.0796    |
| SE      | Age+Sex+OCTA | Intercept     | -3.3533  | 0.2945    | -11.3857 | 0.0000  | -3.9359   | -2.7708    |
| SE      | Age+Sex+OCTA | Age_model_z   | -0.1704  | 0.2232    | -0.7634  | 0.4465  | -0.6118   | 0.2710     |
| SE      | Age+Sex+OCTA | CCFA_median_z | 1.3514   | 0.7000    | 1.9305   | 0.0557  | -0.0332   | 2.7360     |
| SE      | Age+Sex+OCTA | CFA_median_z  | -0.3124  | 0.6603    | -0.4731  | 0.6369  | -1.6186   | 0.9937     |
| SE      | Age+Sex+OCTA | CT_median_z   | 1.3914   | 0.2539    | 5.4802   | 0.0000  | 0.8892    | 1.8936     |
| SE      | Age+Sex+OCTA | CVI_median_z  | 0.0880   | 0.2996    | 0.2938   | 0.7694  | -0.5046   | 0.6806     |
| SE      | Age+Sex+OCTA | Sex_2_vs_1    | -0.4019  | 0.4142    | -0.9703  | 0.3336  | -1.2212   | 0.4174     |

## VIF
| outcome | predictor     | r2_against_other_predictors | vif     |
| ------- | ------------- | --------------------------- | ------- |
| AL      | Age_model_z   | 0.1381                      | 1.1602  |
| AL      | CCFA_median_z | 0.9124                      | 11.4160 |
| AL      | CFA_median_z  | 0.9016                      | 10.1586 |
| AL      | CT_median_z   | 0.3341                      | 1.5017  |
| AL      | CVI_median_z  | 0.5218                      | 2.0910  |
| AL      | Sex_2_vs_1    | 0.0061                      | 1.0062  |
| SE      | Age_model_z   | 0.1381                      | 1.1602  |
| SE      | CCFA_median_z | 0.9124                      | 11.4160 |
| SE      | CFA_median_z  | 0.9016                      | 10.1586 |
| SE      | CT_median_z   | 0.3341                      | 1.5017  |
| SE      | CVI_median_z  | 0.5218                      | 2.0910  |
| SE      | Sex_2_vs_1    | 0.0061                      | 1.0062  |

## Quick interpretation
- AL: full model R2=0.412 vs baseline R2=0.105; delta R2=0.307; OCTA block partial-F p=<0.001; repeated 5-fold CV R2=0.190.
- SE: full model R2=0.470 vs baseline R2=0.069; delta R2=0.401; OCTA block partial-F p=<0.001; repeated 5-fold CV R2=0.245.