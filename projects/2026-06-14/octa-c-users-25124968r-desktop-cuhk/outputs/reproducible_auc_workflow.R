# Reproducible OCTA + Cho biomarker modelling workflow
# Date: 2026-06-15
#
# Purpose:
#   Start from the prepared OD CSV files, align OCTA and Cho by ID, construct
#   biomarker module scores, and compare 5 logistic prediction models by AUC.
#   Endpoints retained in this script:
#     1) High myopia: SE <= -6.00 D
#     2) Moderate myopia one-vs-rest: -6.00 D < SE <= -0.50 D
#     3) Long axial length: AL >= 26 mm
#
# Input files:
#   1) OCTA OD data: C:/Users/25124968R/Desktop/CUHK/CUHK_OCTA_OD_260614.csv
#   2) Cho/CFP OD data: C:/Users/25124968R/Desktop/CUHK/CUHK_Cho_OD_260614.csv
#   3) Cho variable dictionary: C:/Users/25124968R/Desktop/CUHK/cho_Variables.xlsx
#
# Main analysis set:
#   Common OCTA + Cho IDs after OD selection, n = 137.

# =========================
# 0. Load packages and paths
# =========================

required_packages <- c("readr", "readxl", "dplyr", "purrr", "stringr", "tibble", "pROC")
missing_packages <- required_packages[!vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing_packages) > 0) {
  stop(
    "Please install required R packages first: ",
    paste(missing_packages, collapse = ", ")
  )
}

suppressPackageStartupMessages({
  library(readr)
  library(readxl)
  library(dplyr)
  library(purrr)
  library(stringr)
  library(pROC)
})

set.seed(20260615)

octa_path <- "C:/Users/25124968R/Desktop/CUHK/CUHK_OCTA_OD_260614.csv"
cho_path  <- "C:/Users/25124968R/Desktop/CUHK/CUHK_Cho_OD_260614.csv"
dict_path <- "C:/Users/25124968R/Desktop/CUHK/cho_Variables.xlsx"

out_dir <- "C:/Users/25124968R/Documents/Codex/2026-06-14/octa-c-users-25124968r-desktop-cuhk/outputs"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)


# =========================
# 1. Helper functions
# =========================

# Standardize names for robust column matching.
canon_name <- function(x) {
  x |>
    stringr::str_to_lower() |>
    stringr::str_replace_all("[^a-z0-9]+", "")
}

# Find one column by common candidate names.
find_col <- function(dat, candidates, required = TRUE) {
  nms <- names(dat)
  idx <- match(canon_name(candidates), canon_name(nms), nomatch = 0)
  idx <- idx[idx > 0]
  if (length(idx) > 0) return(nms[idx[1]])
  if (required) {
    stop("Cannot find required column. Candidates: ", paste(candidates, collapse = ", "))
  }
  NA_character_
}

# Convert a vector to numeric while tolerating character-coded values.
to_numeric_safe <- function(x) {
  if (is.numeric(x)) return(x)
  readr::parse_number(as.character(x), locale = readr::locale(grouping_mark = ","))
}

# Row-wise median with all-missing rows kept as NA.
row_median_na <- function(dat) {
  mat <- as.matrix(dat)
  apply(mat, 1, function(z) {
    if (all(is.na(z))) return(NA_real_)
    median(z, na.rm = TRUE)
  })
}

# Median imputation for one numeric vector.
median_impute <- function(x) {
  x <- to_numeric_safe(x)
  med <- median(x, na.rm = TRUE)
  if (is.na(med)) return(x)
  x[is.na(x)] <- med
  x
}

# Z-score scaling for one numeric vector.
z_score <- function(x) {
  x <- to_numeric_safe(x)
  s <- stats::sd(x, na.rm = TRUE)
  m <- mean(x, na.rm = TRUE)
  if (is.na(s) || s == 0) return(rep(NA_real_, length(x)))
  as.numeric((x - m) / s)
}

# Variable-level QC used by both OCTA grid variables and Cho variables.
feature_qc <- function(dat, vars, module, valid_min = 0, missing_cut = 0.90, iqr_tol = 1e-8) {
  vars <- intersect(vars, names(dat))

  purrr::map_dfr(vars, function(v) {
    x <- to_numeric_safe(dat[[v]])
    valid_n <- sum(!is.na(x))
    missing_rate <- mean(is.na(x))
    iqr_value <- if (valid_n >= 2) stats::IQR(x, na.rm = TRUE) else NA_real_

    keep_missing <- missing_rate <= missing_cut
    keep_valid <- valid_n >= valid_min
    keep_iqr <- !is.na(iqr_value) && iqr_value > iqr_tol
    keep <- keep_missing && keep_valid && keep_iqr

    drop_reason <- dplyr::case_when(
      !keep_missing ~ "missing_rate > 90%",
      !keep_valid ~ "valid_n below threshold",
      !keep_iqr ~ "IQR approximately 0",
      TRUE ~ "kept"
    )

    tibble::tibble(
      module = module,
      variable = v,
      valid_n = valid_n,
      missing_rate = missing_rate,
      iqr = iqr_value,
      keep = keep,
      drop_reason = drop_reason
    )
  })
}

# Use stratified folds for repeated cross-validated AUC.
make_stratified_folds <- function(y, k = 5) {
  fold_id <- rep(NA_integer_, length(y))
  for (cls in sort(unique(y))) {
    idx <- which(y == cls)
    idx <- sample(idx)
    fold_id[idx] <- rep(seq_len(k), length.out = length(idx))
  }
  fold_id
}

# Fit logistic regression and return predicted probabilities.
fit_predict_prob <- function(train_dat, test_dat, outcome, predictors) {
  fml <- stats::as.formula(paste(outcome, "~", paste(predictors, collapse = " + ")))
  fit <- stats::glm(fml, data = train_dat, family = stats::binomial())
  as.numeric(stats::predict(fit, newdata = test_dat, type = "response"))
}

# Compute one AUC. Returns NA if only one outcome class is present.
auc_safe <- function(y, pred) {
  ok <- complete.cases(y, pred)
  y <- y[ok]
  pred <- pred[ok]
  if (length(unique(y)) < 2) return(NA_real_)
  roc_obj <- pROC::roc(response = y, predictor = pred, levels = c(0, 1), direction = "<", quiet = TRUE)
  as.numeric(pROC::auc(roc_obj))
}

# Repeated 5-fold CV AUC for one model and one endpoint.
cv_auc <- function(dat, outcome, predictors, k = 5, repeats = 200) {
  model_dat <- dat[, c(outcome, predictors), drop = FALSE]
  model_dat <- model_dat[complete.cases(model_dat), , drop = FALSE]
  y <- model_dat[[outcome]]
  if (length(unique(y)) < 2) return(c(cv_auc_mean = NA_real_, cv_auc_sd = NA_real_, valid_repeats = 0))

  auc_values <- rep(NA_real_, repeats)

  for (r in seq_len(repeats)) {
    fold_id <- make_stratified_folds(y, k = k)
    pred <- rep(NA_real_, nrow(model_dat))

    for (fold in seq_len(k)) {
      train_dat <- model_dat[fold_id != fold, , drop = FALSE]
      test_dat <- model_dat[fold_id == fold, , drop = FALSE]

      if (length(unique(train_dat[[outcome]])) < 2) next
      pred[fold_id == fold] <- fit_predict_prob(train_dat, test_dat, outcome, predictors)
    }

    auc_values[r] <- auc_safe(y, pred)
  }

  c(
    cv_auc_mean = mean(auc_values, na.rm = TRUE),
    cv_auc_sd = stats::sd(auc_values, na.rm = TRUE),
    valid_repeats = sum(!is.na(auc_values))
  )
}

# Apparent/in-sample AUC and fitted probabilities for bootstrap paired differences.
in_sample_prediction <- function(dat, outcome, predictors) {
  model_dat <- dat[, c(outcome, predictors), drop = FALSE]
  model_dat <- model_dat[complete.cases(model_dat), , drop = FALSE]
  pred <- fit_predict_prob(model_dat, model_dat, outcome, predictors)
  list(
    data = model_dat,
    pred = pred,
    auc = auc_safe(model_dat[[outcome]], pred)
  )
}

# Paired bootstrap difference in AUC: Model A minus Model B.
bootstrap_auc_diff <- function(y, pred_a, pred_b, b = 2000) {
  ok <- complete.cases(y, pred_a, pred_b)
  y <- y[ok]
  pred_a <- pred_a[ok]
  pred_b <- pred_b[ok]
  n <- length(y)

  diff_values <- rep(NA_real_, b)
  for (i in seq_len(b)) {
    idx <- sample(seq_len(n), size = n, replace = TRUE)
    if (length(unique(y[idx])) < 2) next
    diff_values[i] <- auc_safe(y[idx], pred_a[idx]) - auc_safe(y[idx], pred_b[idx])
  }

  diff_values <- diff_values[!is.na(diff_values)]
  p_value <- 2 * min(mean(diff_values <= 0), mean(diff_values >= 0))

  tibble::tibble(
    delta_auc = mean(diff_values),
    ci_low = stats::quantile(diff_values, 0.025, names = FALSE),
    ci_high = stats::quantile(diff_values, 0.975, names = FALSE),
    p_bootstrap = p_value,
    bootstrap_n = length(diff_values)
  )
}


# =========================
# 2. Read prepared OD data and align IDs
# =========================

octa_raw <- readr::read_csv(octa_path, show_col_types = FALSE)
cho_raw <- readr::read_csv(cho_path, show_col_types = FALSE)
cho_dict <- readxl::read_excel(dict_path)

octa_id_col <- find_col(octa_raw, c("ID", "SubjectID", "Subject_ID", "PatientID"))
cho_id_col <- find_col(cho_raw, c("ID", "SubjectID", "Subject_ID", "PatientID"))

octa_raw <- octa_raw |> mutate(ID = as.character(.data[[octa_id_col]]))
cho_raw <- cho_raw |> mutate(ID = as.character(.data[[cho_id_col]]))

if (anyDuplicated(octa_raw$ID) > 0) stop("Duplicated IDs found in OCTA data.")
if (anyDuplicated(cho_raw$ID) > 0) stop("Duplicated IDs found in Cho data.")

common_ids <- intersect(octa_raw$ID, cho_raw$ID)
octa <- octa_raw |> filter(ID %in% common_ids) |> arrange(ID)
cho <- cho_raw |> filter(ID %in% common_ids) |> arrange(ID)

stopifnot(identical(octa$ID, cho$ID))

# Use OCTA as the canonical source for clinical and outcome variables.
age_col <- find_col(octa, c("Age", "age"))
sex_col <- find_col(octa, c("Sex", "sex", "Gender", "gender"))
al_col <- find_col(octa, c("AL", "AxialLength", "Axial_Length", "Axial Length"))
se_col <- find_col(octa, c("SE", "SphericalEquivalent", "Spherical_Equivalent", "Spherical Equivalent"))

clinical <- octa |>
  transmute(
    ID = ID,
    Age = to_numeric_safe(.data[[age_col]]),
    Sex = factor(as.character(.data[[sex_col]])),
    AL = to_numeric_safe(.data[[al_col]]),
    SE = to_numeric_safe(.data[[se_col]])
  )

# Report Sex differences between OCTA and Cho if Cho also contains Sex.
cho_sex_col <- find_col(cho, c("Sex", "sex", "Gender", "gender"), required = FALSE)
if (!is.na(cho_sex_col)) {
  sex_mismatch <- tibble::tibble(
    ID = octa$ID,
    Sex_OCTA = as.character(octa[[sex_col]]),
    Sex_Cho = as.character(cho[[cho_sex_col]])
  ) |>
    filter(!is.na(Sex_OCTA), !is.na(Sex_Cho), Sex_OCTA != Sex_Cho)
} else {
  sex_mismatch <- tibble::tibble(ID = character(), Sex_OCTA = character(), Sex_Cho = character())
}
readr::write_csv(sex_mismatch, file.path(out_dir, "R_repro_sex_mismatch.csv"))


# =========================
# 3. OCTA QC and module construction
# =========================

# OCTA candidate modules:
#   CCFA = Choriocapillaris Flow Area
#   CFA  = Choroid Flow Area, QC checked but excluded from final models because it is highly correlated with CCFA
#   CT   = Choroid Thickness
#   CVI  = Choroidal Vascularity Index
clinical_cols <- c("ID", age_col, sex_col, al_col, se_col)
octa_feature_names <- setdiff(names(octa), clinical_cols)
octa_feature_text <- stringr::str_to_lower(octa_feature_names)

octa_vars <- list(
  CCFA = octa_feature_names[
    stringr::str_detect(octa_feature_text, "ccfa") |
      (stringr::str_detect(octa_feature_text, "choriocapillaris") &
         stringr::str_detect(octa_feature_text, "flow") &
         stringr::str_detect(octa_feature_text, "area"))
  ],
  CFA = octa_feature_names[
    (
      stringr::str_detect(octa_feature_text, "(^|[^a-z0-9])cfa([^a-z0-9]|$)|^cfa_|_cfa_|_cfa$") |
        (stringr::str_detect(octa_feature_text, "choroid") &
           stringr::str_detect(octa_feature_text, "flow") &
           stringr::str_detect(octa_feature_text, "area"))
    ) &
      !stringr::str_detect(octa_feature_text, "choriocapillaris") &
      !stringr::str_detect(octa_feature_text, "ccfa")
  ],
  CT = octa_feature_names[
    stringr::str_detect(octa_feature_text, "choroid.*thickness|choroidal.*thickness|\\bct\\b|^ct_|_ct_|_ct$")
  ],
  CVI = octa_feature_names[
    stringr::str_detect(octa_feature_text, "cvi|choroid.*vascular|choroidal.*vascular")
  ]
)

octa_qc <- purrr::imap_dfr(octa_vars, ~ feature_qc(octa, .x, module = .y, valid_min = 0))
readr::write_csv(octa_qc, file.path(out_dir, "R_repro_octa_qc_columns.csv"))

octa_qc_summary <- octa_qc |>
  group_by(module) |>
  summarise(
    candidate_n = n(),
    retained_n = sum(keep),
    removed_n = sum(!keep),
    .groups = "drop"
  )
readr::write_csv(octa_qc_summary, file.path(out_dir, "R_repro_octa_qc_summary.csv"))

octa_keep <- split(octa_qc$variable[octa_qc$keep], octa_qc$module[octa_qc$keep])
required_octa_modules <- c("CCFA", "CT", "CVI")
if (!all(required_octa_modules %in% names(octa_keep))) {
  stop("One or more final OCTA modules have no retained variables after QC.")
}

octa_scores <- tibble::tibble(ID = octa$ID)
for (module in required_octa_modules) {
  vars <- octa_keep[[module]]
  raw_score <- row_median_na(as.data.frame(lapply(octa[vars], to_numeric_safe)))
  imputed_score <- median_impute(raw_score)
  octa_scores[[paste0("octa_", module)]] <- z_score(imputed_score)
}

readr::write_csv(octa_scores, file.path(out_dir, "R_repro_octa_module_scores.csv"))


# =========================
# 4. Cho/CFP QC and module construction
# =========================

# Select Region = Whole variables from the dictionary and split by Category.
dict_region_col <- find_col(cho_dict, c("Region"))
dict_category_col <- find_col(cho_dict, c("Category"))

# Pick the dictionary column whose values best match actual Cho CSV column names.
dict_candidate_cols <- setdiff(names(cho_dict), c(dict_region_col, dict_category_col))
match_counts <- purrr::map_int(
  dict_candidate_cols,
  ~ sum(as.character(cho_dict[[.x]]) %in% names(cho), na.rm = TRUE)
)
dict_variable_col <- dict_candidate_cols[which.max(match_counts)]
if (length(dict_variable_col) == 0 || max(match_counts) == 0) {
  dict_variable_col <- find_col(cho_dict, c("Variable", "Variables", "Name", "Metric", "Feature", "Column", "ColumnName"))
}

category_order <- c("Density", "Complexity", "Calibre", "Tortuosity", "Branching Angle")

cho_vars <- cho_dict |>
  mutate(
    Region_clean = stringr::str_squish(as.character(.data[[dict_region_col]])),
    Category_clean = stringr::str_squish(as.character(.data[[dict_category_col]])),
    variable = as.character(.data[[dict_variable_col]])
  ) |>
  filter(
    stringr::str_to_lower(Region_clean) == "whole",
    Category_clean %in% category_order,
    variable %in% names(cho)
  ) |>
  transmute(Category = Category_clean, variable = variable)

cho_valid_min <- max(20, ceiling(0.10 * nrow(cho)))

cho_qc <- purrr::map_dfr(category_order, function(cat) {
  vars <- cho_vars |> filter(Category == cat) |> pull(variable)
  feature_qc(cho, vars, module = cat, valid_min = cho_valid_min)
})
readr::write_csv(cho_qc, file.path(out_dir, "R_repro_cho_qc_variables.csv"))

cho_qc_summary <- cho_qc |>
  group_by(module) |>
  summarise(
    candidate_n = n(),
    retained_n = sum(keep),
    removed_n = sum(!keep),
    .groups = "drop"
  )
readr::write_csv(cho_qc_summary, file.path(out_dir, "R_repro_cho_qc_summary.csv"))

# Cho variables have heterogeneous units:
#   variable-level median imputation -> variable-level z-score -> module median -> module score scale().
cho_keep <- split(cho_qc$variable[cho_qc$keep], cho_qc$module[cho_qc$keep])
if (!all(category_order %in% names(cho_keep))) {
  stop("One or more Cho modules have no retained variables after QC.")
}

cho_z <- tibble::tibble(ID = cho$ID)
for (v in unique(unlist(cho_keep))) {
  x_imp <- median_impute(cho[[v]])
  cho_z[[v]] <- z_score(x_imp)
}

cho_scores <- tibble::tibble(ID = cho$ID)
for (module in category_order) {
  vars <- cho_keep[[module]]
  module_raw <- row_median_na(cho_z[vars])
  module_scaled <- z_score(module_raw)
  score_name <- paste0("cho_", stringr::str_replace_all(module, "[^A-Za-z0-9]+", "_"))
  score_name <- stringr::str_replace(score_name, "_$", "")
  cho_scores[[score_name]] <- module_scaled
}

readr::write_csv(cho_scores, file.path(out_dir, "R_repro_cho_module_scores.csv"))


# =========================
# 5. Final analysis dataset and outcomes
# =========================

analysis_dat <- clinical |>
  inner_join(octa_scores, by = "ID") |>
  inner_join(cho_scores, by = "ID") |>
  filter(!is.na(Age), !is.na(Sex), !is.na(AL), !is.na(SE)) |>
  mutate(
    high_myopia = as.integer(SE <= -6.00),
    moderate_myopia = as.integer(SE > -6.00 & SE <= -0.50),
    long_axial_length = as.integer(AL >= 26.00)
  )

readr::write_csv(analysis_dat, file.path(out_dir, "R_repro_analysis_dataset.csv"))

endpoint_specs <- list(
  "High myopia: SE <= -6.00D" = "high_myopia",
  "Moderate myopia one-vs-rest: -6.00D < SE <= -0.50D" = "moderate_myopia",
  "Long axial length: AL >= 26mm" = "long_axial_length"
)

endpoint_counts <- purrr::imap_dfr(endpoint_specs, function(outcome, endpoint_label) {
  y <- analysis_dat[[outcome]]
  tibble::tibble(
    endpoint = endpoint_label,
    n = length(y),
    event_n = sum(y == 1, na.rm = TRUE),
    non_event_n = sum(y == 0, na.rm = TRUE),
    event_rate = mean(y == 1, na.rm = TRUE)
  )
})
readr::write_csv(endpoint_counts, file.path(out_dir, "R_repro_endpoint_counts.csv"))


# =========================
# 6. Define the 5 prediction models
# =========================

cho_predictors <- names(cho_scores)[names(cho_scores) != "ID"]
octa_predictors <- c("octa_CCFA", "octa_CT", "octa_CVI")
octa_nonflow_predictors <- c("octa_CT", "octa_CVI")

model_specs <- list(
  "Model 1 Clinical" = c("Age", "Sex"),
  "Model 2 Clinical + Cho" = c("Age", "Sex", cho_predictors),
  "Model 3 Clinical + OCTA" = c("Age", "Sex", octa_predictors),
  "Model 4 Clinical + OCTA_nonflow" = c("Age", "Sex", octa_nonflow_predictors),
  "Model 5 Clinical + OCTA + Cho" = c("Age", "Sex", octa_predictors, cho_predictors)
)


# =========================
# 7. Model performance: repeated 5-fold CV AUC and apparent AUC
# =========================

performance <- purrr::imap_dfr(endpoint_specs, function(outcome, endpoint_label) {
  purrr::imap_dfr(model_specs, function(predictors, model_label) {
    cv <- cv_auc(analysis_dat, outcome, predictors, k = 5, repeats = 200)
    apparent <- in_sample_prediction(analysis_dat, outcome, predictors)

    tibble::tibble(
      endpoint = endpoint_label,
      model = model_label,
      n = nrow(apparent$data),
      event_n = sum(apparent$data[[outcome]] == 1),
      predictor_n = length(predictors),
      apparent_auc = apparent$auc,
      cv_auc_mean = unname(cv["cv_auc_mean"]),
      cv_auc_sd = unname(cv["cv_auc_sd"]),
      valid_cv_repeats = unname(cv["valid_repeats"])
    )
  })
})

readr::write_csv(performance, file.path(out_dir, "R_repro_auc_performance.csv"))


# =========================
# 8. Paired bootstrap AUC differences
# =========================

pair_index <- utils::combn(names(model_specs), 2, simplify = FALSE)

differences <- purrr::imap_dfr(endpoint_specs, function(outcome, endpoint_label) {
  preds <- purrr::imap(model_specs, function(predictors, model_label) {
    in_sample_prediction(analysis_dat, outcome, predictors)
  })

  purrr::map_dfr(pair_index, function(pair) {
    model_a <- pair[[1]]
    model_b <- pair[[2]]

    dat_a <- preds[[model_a]]$data
    dat_b <- preds[[model_b]]$data

    # The analysis set is complete, but this check keeps the bootstrap aligned if
    # future data contain missing clinical covariates.
    common_rows <- intersect(rownames(dat_a), rownames(dat_b))
    y <- analysis_dat[[outcome]][as.integer(common_rows)]
    pred_a <- preds[[model_a]]$pred[match(common_rows, rownames(dat_a))]
    pred_b <- preds[[model_b]]$pred[match(common_rows, rownames(dat_b))]

    boot <- bootstrap_auc_diff(y, pred_a, pred_b, b = 2000)
    boot |>
      mutate(
        endpoint = endpoint_label,
        model_a = model_a,
        model_b = model_b,
        contrast = paste0(model_a, " minus ", model_b),
        .before = 1
      )
  })
})

readr::write_csv(differences, file.path(out_dir, "R_repro_auc_pairwise_differences.csv"))


# =========================
# 9. Compact console summary
# =========================

cat("\nFinal analysis set n =", nrow(analysis_dat), "\n")
cat("Common OCTA + Cho IDs =", length(common_ids), "\n")
cat("Sex mismatches between OCTA and Cho =", nrow(sex_mismatch), "\n\n")

cat("OCTA QC summary:\n")
print(octa_qc_summary)

cat("\nCho QC summary:\n")
print(cho_qc_summary)

cat("\nEndpoint counts:\n")
print(endpoint_counts)

cat("\nAUC performance written to:\n")
cat(file.path(out_dir, "R_repro_auc_performance.csv"), "\n")

cat("\nPaired AUC differences written to:\n")
cat(file.path(out_dir, "R_repro_auc_pairwise_differences.csv"), "\n")
