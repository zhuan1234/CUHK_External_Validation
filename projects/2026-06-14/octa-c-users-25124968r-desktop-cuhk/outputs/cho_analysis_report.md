# Choroidal morphology module modeling report

Input CSV: `C:\Users\25124968R\Desktop\CUHK\CUHK_Cho_OD_260614.csv`
Variable dictionary: `C:\Users\25124968R\Desktop\CUHK\cho_Variables.xlsx`
Rows: 137, columns: 479
Reference OCTA cohort: `C:\Users\25124968R\Desktop\CUHK\CUHK_OCTA_OD_260614.csv`

## Methods notes
- Cho records were aligned to the OCTA patient cohort by `ID` before QC and modeling.
- Selected variables where `Region == Whole` and `Category` is one of Density, Complexity, Calibre, Tortuosity, Branching Angle.
- QC retained variables with `missing_rate <= 90%`, `IQR > 1e-08`, and `valid_n >= max(20, ceil(10% of N)) = 20`.
- Because variables within a Cho category have different units/scales, the primary module score was calculated as: variable-level median imputation -> variable-level z-score -> module-wise row median -> module-level z-score.
- Outcomes (`AL`, `SE`) were not imputed. Prediction models compare `Age + Sex` against `Age + Sex + five Cho module scores`.
- Step 7 biological validation was interpreted as Pearson associations between each Cho module z-score and Age, AL, and SE.

## Cohort Alignment
| cho_rows_before | cho_unique_ids_before | octa_rows | octa_unique_ids | cho_rows_after | cho_unique_ids_after | id_sets_match_after |
| --------------- | --------------------- | --------- | --------------- | -------------- | -------------------- | ------------------- |
| 137             | 137                   | 137       | 137             | 137            | 137                  | 1                   |

## Selected Whole Variables
| Category        | variables | matched_in_csv |
| --------------- | --------- | -------------- |
| Density         | 10        | 10             |
| Complexity      | 11        | 11             |
| Calibre         | 16        | 16             |
| Tortuosity      | 24        | 24             |
| Branching Angle | 14        | 14             |

## QC Summary
| category        | input_variables | matched_variables | removed_missing_rate_gt_90pct | removed_valid_n_lt_threshold | removed_low_iqr | retained_variables | median_missing_rate | max_missing_rate | min_iqr | median_iqr |
| --------------- | --------------- | ----------------- | ----------------------------- | ---------------------------- | --------------- | ------------------ | ------------------- | ---------------- | ------- | ---------- |
| Density         | 10              | 10                | 0                             | 0                            | 0               | 10                 | 0.0000              | 0.0000           | 0.0008  | 1.9869     |
| Complexity      | 11              | 11                | 0                             | 0                            | 0               | 11                 | 0.0000              | 0.0000           | 0.0100  | 27.0000    |
| Calibre         | 16              | 16                | 0                             | 0                            | 0               | 16                 | 0.0000              | 0.0000           | 0.2268  | 2.0115     |
| Tortuosity      | 24              | 24                | 0                             | 0                            | 1               | 23                 | 0.0000              | 0.0000           | 0.0000  | 0.0159     |
| Branching Angle | 14              | 14                | 0                             | 0                            | 0               | 14                 | 0.0000              | 0.0000           | 0.0304  | 2.9870     |

## Imputation And Scaling
| variable                      | category        | missing_before_imputation | imputation_method              | imputation_value |
| ----------------------------- | --------------- | ------------------------- | ------------------------------ | ---------------- |
| Density_module_median         | Density         | 0                         | median                         | -0.1203          |
| Complexity_module_median      | Complexity      | 0                         | median                         | -0.1144          |
| Calibre_module_median         | Calibre         | 0                         | median                         | -0.0887          |
| Tortuosity_module_median      | Tortuosity      | 0                         | median                         | -0.1226          |
| Branching_Angle_module_median | Branching Angle | 0                         | median                         | -0.0415          |
| Age_model                     | covariate       | 0                         | median                         | 12.0000          |
| Sex_model                     | covariate       | 0                         | mode for categorical covariate | 1.0000           |

| variable                      | z_variable               | mean    | sample_sd |
| ----------------------------- | ------------------------ | ------- | --------- |
| Density_module_median         | Density_module_z         | -0.0354 | 0.5658    |
| Complexity_module_median      | Complexity_module_z      | -0.0435 | 0.5899    |
| Calibre_module_median         | Calibre_module_z         | -0.0326 | 0.8072    |
| Tortuosity_module_median      | Tortuosity_module_z      | -0.1027 | 0.3471    |
| Branching_Angle_module_median | Branching_Angle_module_z | -0.0301 | 0.4215    |
| Age_model                     | Age_z                    | 12.8759 | 7.3549    |

## Module Correlations
| module          | Density | Complexity | Calibre | Tortuosity | Branching Angle |
| --------------- | ------- | ---------- | ------- | ---------- | --------------- |
| Density         | 1.0000  | -0.2467    | 0.4073  | -0.0093    | 0.3044          |
| Complexity      | -0.2467 | 1.0000     | -0.4855 | 0.0536     | -0.1228         |
| Calibre         | 0.4073  | -0.4855    | 1.0000  | -0.4325    | 0.2125          |
| Tortuosity      | -0.0093 | 0.0536     | -0.4325 | 1.0000     | -0.0928         |
| Branching Angle | 0.3044  | -0.1228    | 0.2125  | -0.0928    | 1.0000          |

## Biological Validation
| module          | module_score             | target | n_pairwise | pearson_r | pearson_p |
| --------------- | ------------------------ | ------ | ---------- | --------- | --------- |
| Density         | Density_module_z         | Age    | 137        | 0.4902    | 0.0000    |
| Density         | Density_module_z         | AL     | 137        | 0.4422    | 0.0000    |
| Density         | Density_module_z         | SE     | 137        | -0.5411   | 0.0000    |
| Complexity      | Complexity_module_z      | Age    | 137        | -0.0912   | 0.2892    |
| Complexity      | Complexity_module_z      | AL     | 137        | -0.2218   | 0.0092    |
| Complexity      | Complexity_module_z      | SE     | 137        | 0.1899    | 0.0263    |
| Calibre         | Calibre_module_z         | Age    | 137        | 0.1962    | 0.0216    |
| Calibre         | Calibre_module_z         | AL     | 137        | 0.2917    | 0.0005    |
| Calibre         | Calibre_module_z         | SE     | 137        | -0.2705   | 0.0014    |
| Tortuosity      | Tortuosity_module_z      | Age    | 137        | -0.0874   | 0.3096    |
| Tortuosity      | Tortuosity_module_z      | AL     | 137        | -0.0303   | 0.7257    |
| Tortuosity      | Tortuosity_module_z      | SE     | 137        | 0.0824    | 0.3386    |
| Branching Angle | Branching_Angle_module_z | Age    | 137        | 0.1500    | 0.0802    |
| Branching Angle | Branching_Angle_module_z | AL     | 137        | 0.2606    | 0.0021    |
| Branching Angle | Branching_Angle_module_z | SE     | 137        | -0.3309   | 0.0001    |

## Prediction Model Performance
| outcome | model       | n   | r2     | adj_r2 | rmse   | mae    | cv_r2_mean | cv_r2_sd | cv_rmse_mean | cv_rmse_sd | condition_number | delta_r2_vs_age_sex | partial_f_for_cho_block | partial_f_p_for_cho_block |
| ------- | ----------- | --- | ------ | ------ | ------ | ------ | ---------- | -------- | ------------ | ---------- | ---------------- | ------------------- | ----------------------- | ------------------------- |
| AL      | Age+Sex     | 137 | 0.1067 | 0.0934 | 1.2353 | 0.9626 | -0.1840    | 0.1079   | 1.4207       | 0.0664     | 2.6096           | NA                  | NA                      | NA                        |
| AL      | Age+Sex+Cho | 137 | 0.2967 | 0.2586 | 1.0961 | 0.8907 | 0.0357     | 0.0787   | 1.2825       | 0.0521     | 3.4806           | 0.1900              | 6.9698                  | 0.0000                    |
| SE      | Age+Sex     | 137 | 0.0703 | 0.0564 | 3.1705 | 2.3331 | -0.2694    | 0.1531   | 3.6978       | 0.2288     | 2.6096           | NA                  | NA                      | NA                        |
| SE      | Age+Sex+Cho | 137 | 0.3299 | 0.2935 | 2.6918 | 2.0465 | 0.0711     | 0.0829   | 3.1662       | 0.1396     | 3.4806           | 0.2596              | 9.9937                  | 0.0000                    |

## Full-Model Coefficients
| outcome | model       | term                            | estimate | std_error | t_value  | p_value | ci_95_low | ci_95_high |
| ------- | ----------- | ------------------------------- | -------- | --------- | -------- | ------- | --------- | ---------- |
| AL      | Age+Sex+Cho | Intercept                       | 25.2430  | 0.1374    | 183.7032 | 0.0000  | 24.9711   | 25.5149    |
| AL      | Age+Sex+Cho | Age_model_z                     | 0.0898   | 0.1121    | 0.8010   | 0.4246  | -0.1320   | 0.3115     |
| AL      | Age+Sex+Cho | Density_module_median_z         | 0.4255   | 0.1262    | 3.3708   | 0.0010  | 0.1757    | 0.6752     |
| AL      | Age+Sex+Cho | Complexity_module_median_z      | -0.1222  | 0.1133    | -1.0782  | 0.2830  | -0.3465   | 0.1021     |
| AL      | Age+Sex+Cho | Calibre_module_median_z         | 0.1277   | 0.1360    | 0.9386   | 0.3497  | -0.1415   | 0.3968     |
| AL      | Age+Sex+Cho | Tortuosity_module_median_z      | 0.0398   | 0.1126    | 0.3536   | 0.7242  | -0.1830   | 0.2627     |
| AL      | Age+Sex+Cho | Branching_Angle_module_median_z | 0.2150   | 0.1033    | 2.0806   | 0.0395  | 0.0105    | 0.4194     |
| AL      | Age+Sex+Cho | Sex_2_vs_1                      | -0.6562  | 0.1971    | -3.3299  | 0.0011  | -1.0461   | -0.2663    |
| SE      | Age+Sex+Cho | Intercept                       | -3.6481  | 0.3374    | -10.8110 | 0.0000  | -4.3157   | -2.9804    |
| SE      | Age+Sex+Cho | Age_model_z                     | 0.0693   | 0.2752    | 0.2519   | 0.8016  | -0.4752   | 0.6138     |
| SE      | Age+Sex+Cho | Density_module_median_z         | -1.6265  | 0.3100    | -5.2473  | 0.0000  | -2.2397   | -1.0132    |
| SE      | Age+Sex+Cho | Complexity_module_median_z      | 0.1841   | 0.2783    | 0.6614   | 0.5095  | -0.3666   | 0.7348     |
| SE      | Age+Sex+Cho | Calibre_module_median_z         | 0.0653   | 0.3341    | 0.1955   | 0.8453  | -0.5956   | 0.7262     |
| SE      | Age+Sex+Cho | Tortuosity_module_median_z      | 0.2291   | 0.2766    | 0.8280   | 0.4092  | -0.3183   | 0.7764     |
| SE      | Age+Sex+Cho | Branching_Angle_module_median_z | -0.5863  | 0.2537    | -2.3107  | 0.0224  | -1.0883   | -0.0843    |
| SE      | Age+Sex+Cho | Sex_2_vs_1                      | 0.1071   | 0.4839    | 0.2214   | 0.8252  | -0.8504   | 1.0646     |

## VIF
| outcome | predictor                       | r2_against_other_predictors | vif    |
| ------- | ------------------------------- | --------------------------- | ------ |
| AL      | Age_model_z                     | 0.2529                      | 1.3384 |
| AL      | Density_module_median_z         | 0.4111                      | 1.6981 |
| AL      | Complexity_module_median_z      | 0.2697                      | 1.3693 |
| AL      | Calibre_module_median_z         | 0.4930                      | 1.9723 |
| AL      | Tortuosity_module_median_z      | 0.2606                      | 1.3525 |
| AL      | Branching_Angle_module_median_z | 0.1212                      | 1.1379 |
| AL      | Sex_2_vs_1                      | 0.0407                      | 1.0424 |
| SE      | Age_model_z                     | 0.2529                      | 1.3384 |
| SE      | Density_module_median_z         | 0.4111                      | 1.6981 |
| SE      | Complexity_module_median_z      | 0.2697                      | 1.3693 |
| SE      | Calibre_module_median_z         | 0.4930                      | 1.9723 |
| SE      | Tortuosity_module_median_z      | 0.2606                      | 1.3525 |
| SE      | Branching_Angle_module_median_z | 0.1212                      | 1.1379 |
| SE      | Sex_2_vs_1                      | 0.0407                      | 1.0424 |

## Quick Interpretation
- AL: full model R2=0.297 vs baseline R2=0.107; delta R2=0.190; Cho block partial-F p=<0.001; repeated 5-fold CV R2=0.036.
- SE: full model R2=0.330 vs baseline R2=0.070; delta R2=0.260; Cho block partial-F p=<0.001; repeated 5-fold CV R2=0.071.