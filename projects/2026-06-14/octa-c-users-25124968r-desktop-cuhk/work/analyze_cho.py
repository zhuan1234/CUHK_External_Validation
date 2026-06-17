from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - optional plots only
    Image = ImageDraw = ImageFont = None


INPUT_CSV = Path(r"C:\Users\25124968R\Desktop\CUHK\CUHK_Cho_OD_260614.csv")
VARIABLES_XLSX = Path(r"C:\Users\25124968R\Desktop\CUHK\cho_Variables.xlsx")
REFERENCE_OCTA_CSV = Path(r"C:\Users\25124968R\Desktop\CUHK\CUHK_OCTA_OD_260614.csv")
OUTPUT_DIR = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-14\octa-c-users-25124968r-desktop-cuhk\outputs"
)
OUTPUT_PREFIX = "cho"

MISSING_RATE_THRESHOLD = 0.90
IQR_TOL = 1e-8
MIN_VALID_N_ABSOLUTE = 20
MIN_VALID_N_FRACTION = 0.10
RANDOM_SEED = 612
N_SPLITS = 5
N_REPEATS = 50

CATEGORY_ORDER = ["Density", "Complexity", "Calibre", "Tortuosity", "Branching Angle"]


def _betacf(a: float, b: float, x: float) -> float:
    max_iter = 200
    eps = 3e-14
    fpmin = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def regularized_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def student_t_cdf(t: float, df: int | float) -> float:
    if not math.isfinite(t) or df <= 0:
        return np.nan
    x = df / (df + t * t)
    ib = regularized_beta(x, df / 2.0, 0.5)
    return 1.0 - 0.5 * ib if t >= 0 else 0.5 * ib


def student_t_two_sided_p(t: float, df: int | float) -> float:
    if not math.isfinite(t) or df <= 0:
        return np.nan
    return max(0.0, min(1.0, 2.0 * (1.0 - student_t_cdf(abs(t), df))))


def student_t_ppf(p: float, df: int | float) -> float:
    if not 0.0 < p < 1.0 or df <= 0:
        return np.nan
    if p == 0.5:
        return 0.0
    if p < 0.5:
        return -student_t_ppf(1.0 - p, df)
    lo, hi = 0.0, 1.0
    while student_t_cdf(hi, df) < p and hi < 1e6:
        hi *= 2.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if student_t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def f_survival(f_stat: float, df1: int | float, df2: int | float) -> float:
    if not math.isfinite(f_stat) or f_stat < 0 or df1 <= 0 or df2 <= 0:
        return np.nan
    x = (df1 * f_stat) / (df1 * f_stat + df2)
    return max(0.0, min(1.0, 1.0 - regularized_beta(x, df1 / 2.0, df2 / 2.0)))


def to_numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def category_slug(category: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(category)).strip("_")
    return slug or "Module"


def qnorm(series: pd.Series, q: float) -> float:
    return float(series.quantile(q, interpolation="linear"))


def sample_z(series: pd.Series) -> tuple[pd.Series, float, float]:
    mean = float(series.mean())
    sd = float(series.std(ddof=1))
    if not math.isfinite(sd) or abs(sd) <= IQR_TOL:
        return pd.Series(np.nan, index=series.index), mean, sd
    return (series - mean) / sd, mean, sd


def sorted_levels(series: pd.Series) -> list:
    vals = [v for v in series.dropna().unique().tolist()]
    try:
        return sorted(vals)
    except TypeError:
        return sorted(vals, key=lambda x: str(x))


def read_inputs():
    df = pd.read_csv(INPUT_CSV, na_values=["", "NA", "N/A", "NaN", "nan", "NULL", "null"])
    variables = pd.read_excel(VARIABLES_XLSX)
    whole = variables[
        variables["Region"].astype(str).str.strip().str.lower().eq("whole")
        & variables["Category"].notna()
    ].copy()
    whole["Category"] = whole["Category"].astype(str).str.strip()
    whole = whole[whole["Category"].isin(CATEGORY_ORDER)].copy()
    whole["matched_in_csv"] = whole["variable"].isin(df.columns)
    return df, variables, whole


def align_to_octa_cohort(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    info = {
        "reference_octa_csv": str(REFERENCE_OCTA_CSV),
        "cho_rows_before_alignment": int(len(df)),
        "cho_unique_ids_before_alignment": int(df["ID"].astype(str).nunique()) if "ID" in df.columns else None,
        "octa_rows": None,
        "octa_unique_ids": None,
        "cho_ids_not_in_octa": [],
        "octa_ids_not_in_cho": [],
        "cho_rows_after_alignment": int(len(df)),
        "cho_unique_ids_after_alignment": int(df["ID"].astype(str).nunique()) if "ID" in df.columns else None,
        "cohort_id_sets_match_after_alignment": None,
    }
    if "ID" not in df.columns or not REFERENCE_OCTA_CSV.exists():
        return df, info

    octa_ids_frame = pd.read_csv(REFERENCE_OCTA_CSV, usecols=["ID"])
    cho_ids = set(df["ID"].astype(str))
    octa_ids = set(octa_ids_frame["ID"].astype(str))
    info["octa_rows"] = int(len(octa_ids_frame))
    info["octa_unique_ids"] = int(len(octa_ids))
    info["cho_ids_not_in_octa"] = sorted(cho_ids - octa_ids)
    info["octa_ids_not_in_cho"] = sorted(octa_ids - cho_ids)

    common_ids = cho_ids & octa_ids
    aligned = df[df["ID"].astype(str).isin(common_ids)].copy()
    info["cho_rows_after_alignment"] = int(len(aligned))
    info["cho_unique_ids_after_alignment"] = int(aligned["ID"].astype(str).nunique())
    aligned_ids = set(aligned["ID"].astype(str))
    info["cohort_id_sets_match_after_alignment"] = aligned_ids == octa_ids
    return aligned, info


def qc_variables(df: pd.DataFrame, whole: pd.DataFrame):
    n_total = len(df)
    min_valid_n = max(MIN_VALID_N_ABSOLUTE, int(math.ceil(n_total * MIN_VALID_N_FRACTION)))
    rows = []
    retained: dict[str, list[str]] = {category: [] for category in CATEGORY_ORDER}
    for _, item in whole.iterrows():
        variable = item["variable"]
        category = item["Category"]
        if variable not in df.columns:
            rows.append(
                {
                    "variable": variable,
                    "label": item.get("Label", ""),
                    "category": category,
                    "matched_in_csv": False,
                    "valid_n": 0,
                    "missing_rate": 1.0,
                    "iqr": np.nan,
                    "retained": False,
                    "drop_reason": "not_found_in_csv",
                }
            )
            continue
        numeric = to_numeric_series(df[variable])
        valid_n = int(numeric.notna().sum())
        missing_rate = float(numeric.isna().mean())
        iqr = np.nan if valid_n == 0 else qnorm(numeric.dropna(), 0.75) - qnorm(numeric.dropna(), 0.25)
        reasons = []
        if missing_rate > MISSING_RATE_THRESHOLD:
            reasons.append(f"missing_rate>{MISSING_RATE_THRESHOLD:.2f}")
        if valid_n < min_valid_n:
            reasons.append(f"valid_n<{min_valid_n}")
        if (not pd.isna(iqr)) and abs(iqr) <= IQR_TOL:
            reasons.append(f"IQR<={IQR_TOL:g}")
        retained_flag = not reasons
        if retained_flag:
            retained[category].append(variable)
        rows.append(
            {
                "variable": variable,
                "label": item.get("Label", ""),
                "category": category,
                "matched_in_csv": True,
                "valid_n": valid_n,
                "missing_rate": missing_rate,
                "iqr": iqr,
                "retained": retained_flag,
                "drop_reason": "; ".join(reasons),
            }
        )
    qc = pd.DataFrame(rows)
    summary = (
        qc.groupby("category", as_index=False)
        .agg(
            input_variables=("variable", "count"),
            matched_variables=("matched_in_csv", "sum"),
            removed_missing_rate_gt_90pct=("drop_reason", lambda s: sum("missing_rate>" in str(x) for x in s)),
            removed_valid_n_lt_threshold=("drop_reason", lambda s: sum("valid_n<" in str(x) for x in s)),
            removed_low_iqr=("drop_reason", lambda s: sum("IQR<=" in str(x) for x in s)),
            retained_variables=("retained", "sum"),
            median_missing_rate=("missing_rate", "median"),
            max_missing_rate=("missing_rate", "max"),
            min_iqr=("iqr", "min"),
            median_iqr=("iqr", "median"),
        )
        .sort_values("category", key=lambda x: x.map({c: i for i, c in enumerate(CATEGORY_ORDER)}))
    )
    return qc, summary, retained, min_valid_n


def prepare_scores(df: pd.DataFrame, retained: dict[str, list[str]]):
    outcome_se_col = "Post SE" if "Post SE" in df.columns else "SE"
    base_cols = [c for c in ["ID", "Age", "Sex", "AL", outcome_se_col] if c in df.columns]
    scores = df[base_cols].copy()
    if outcome_se_col in scores.columns and outcome_se_col != "SE":
        scores = scores.rename(columns={outcome_se_col: "SE"})
    for col in ["Age", "Sex", "AL", "SE"]:
        if col in scores.columns:
            scores[col] = to_numeric_series(scores[col])

    impute_records = []
    scale_records = []
    feature_scale_records = []
    for category in CATEGORY_ORDER:
        slug = category_slug(category)
        cols = retained[category]
        z_cols = []
        raw_cols = []
        for variable in cols:
            numeric = to_numeric_series(df[variable])
            filled = numeric.fillna(float(numeric.median(skipna=True)))
            z, mean, sd = sample_z(filled)
            z_col = f"__{slug}__{variable}__z"
            scores[z_col] = z
            z_cols.append(z_col)
            raw_cols.append(variable)
            feature_scale_records.append(
                {
                    "category": category,
                    "variable": variable,
                    "missing_before_feature_imputation": int(numeric.isna().sum()),
                    "feature_imputation_value": float(numeric.median(skipna=True)),
                    "feature_mean_after_imputation": mean,
                    "feature_sample_sd_after_imputation": sd,
                }
            )

        raw_median_col = f"{slug}_raw_median"
        module_col = f"{slug}_module_median"
        module_z_col = f"{slug}_module_z"
        if raw_cols:
            raw_values = df[raw_cols].apply(to_numeric_series)
            scores[raw_median_col] = raw_values.median(axis=1, skipna=True)
        else:
            scores[raw_median_col] = np.nan
        if z_cols:
            scores[module_col] = scores[z_cols].median(axis=1, skipna=True)
        else:
            scores[module_col] = np.nan

        impute_value = float(scores[module_col].median(skipna=True))
        missing_before = int(scores[module_col].isna().sum())
        scores[module_col] = scores[module_col].fillna(impute_value)
        module_z, mean, sd = sample_z(scores[module_col])
        scores[module_z_col] = module_z
        impute_records.append(
            {
                "variable": module_col,
                "category": category,
                "missing_before_imputation": missing_before,
                "imputation_method": "median",
                "imputation_value": impute_value,
            }
        )
        scale_records.append(
            {
                "variable": module_col,
                "z_variable": module_z_col,
                "scale_method": "R scale style: (x - mean) / sample_sd",
                "mean": mean,
                "sample_sd": sd,
            }
        )
        scores = scores.drop(columns=z_cols)

    if "Age" in scores.columns:
        age_impute = float(scores["Age"].median(skipna=True))
        missing_age = int(scores["Age"].isna().sum())
        scores["Age_model"] = scores["Age"].fillna(age_impute)
        scores["Age_z"], age_mean, age_sd = sample_z(scores["Age_model"])
        impute_records.append(
            {
                "variable": "Age_model",
                "category": "covariate",
                "missing_before_imputation": missing_age,
                "imputation_method": "median",
                "imputation_value": age_impute,
            }
        )
        scale_records.append(
            {
                "variable": "Age_model",
                "z_variable": "Age_z",
                "scale_method": "R scale style: (x - mean) / sample_sd",
                "mean": age_mean,
                "sample_sd": age_sd,
            }
        )

    if "Sex" in scores.columns:
        mode = scores["Sex"].mode(dropna=True)
        sex_impute = mode.iloc[0] if not mode.empty else np.nan
        scores["Sex_model"] = scores["Sex"].fillna(sex_impute)
        impute_records.append(
            {
                "variable": "Sex_model",
                "category": "covariate",
                "missing_before_imputation": int(scores["Sex"].isna().sum()),
                "imputation_method": "mode for categorical covariate",
                "imputation_value": sex_impute,
            }
        )

    return (
        scores,
        pd.DataFrame(impute_records),
        pd.DataFrame(scale_records),
        pd.DataFrame(feature_scale_records),
    )


def pearson_pair(x: pd.Series, y: pd.Series) -> tuple[int, float, float]:
    data = pd.concat([x, y], axis=1).dropna()
    n = len(data)
    if n < 3 or data.iloc[:, 0].nunique() <= 1 or data.iloc[:, 1].nunique() <= 1:
        return n, np.nan, np.nan
    r = float(np.corrcoef(data.iloc[:, 0].to_numpy(dtype=float), data.iloc[:, 1].to_numpy(dtype=float))[0, 1])
    if abs(r) >= 1:
        p = 0.0
    else:
        tval = r * math.sqrt((n - 2) / (1 - r * r))
        p = student_t_two_sided_p(tval, n - 2)
    return n, r, p


def module_z_col(category: str) -> str:
    return f"{category_slug(category)}_module_z"


def module_score_col(category: str) -> str:
    return f"{category_slug(category)}_module_median"


def correlation_tables(scores: pd.DataFrame):
    z_cols = [module_z_col(category) for category in CATEGORY_ORDER]
    corr = scores[z_cols].corr(method="pearson")
    corr.index = CATEGORY_ORDER
    corr.columns = CATEGORY_ORDER
    pmat = pd.DataFrame(np.nan, index=CATEGORY_ORDER, columns=CATEGORY_ORDER)
    for i, a in enumerate(z_cols):
        for j, b in enumerate(z_cols):
            if i == j:
                pmat.iloc[i, j] = 0.0
            elif i < j:
                _, _, p = pearson_pair(scores[a], scores[b])
                pmat.iloc[i, j] = p
                pmat.iloc[j, i] = p
    return corr, pmat


def biological_validation(scores: pd.DataFrame):
    targets = [target for target in ["Age", "AL", "SE"] if target in scores.columns]
    rows = []
    for category in CATEGORY_ORDER:
        z_col = module_z_col(category)
        for target in targets:
            n, r, p = pearson_pair(scores[z_col], scores[target])
            rows.append(
                {
                    "module": category,
                    "module_score": z_col,
                    "target": target,
                    "n_pairwise": n,
                    "pearson_r": r,
                    "pearson_p": p,
                }
            )
    return pd.DataFrame(rows)


def design_matrix(frame: pd.DataFrame, include_modules: bool, params: dict | None = None, fit_params: bool = False):
    if fit_params:
        params = {}
    assert params is not None
    out = pd.DataFrame(index=frame.index)
    out["Intercept"] = 1.0
    continuous_cols = ["Age_model"]
    if include_modules:
        continuous_cols += [module_score_col(category) for category in CATEGORY_ORDER]
    for col in continuous_cols:
        source = "Age" if col == "Age_model" else col
        values = to_numeric_series(frame[source])
        if fit_params:
            median = float(values.median(skipna=True))
            filled = values.fillna(median)
            mean = float(filled.mean())
            sd = float(filled.std(ddof=1))
            params[col] = {"median": median, "mean": mean, "sd": sd}
        cfg = params[col]
        filled = values.fillna(cfg["median"])
        out[f"{col}_z"] = 0.0 if abs(cfg["sd"]) <= IQR_TOL else (filled - cfg["mean"]) / cfg["sd"]
    if "Sex" in frame.columns:
        sex = frame["Sex"].copy()
        if fit_params:
            levels = sorted_levels(sex)
            mode = sex.mode(dropna=True)
            sex_fill = mode.iloc[0] if not mode.empty else (levels[0] if levels else 0)
            params["Sex"] = {"levels": levels, "fill": sex_fill}
        cfg = params["Sex"]
        sex = sex.fillna(cfg["fill"])
        levels = cfg["levels"]
        if len(levels) > 1:
            ref = levels[0]
            for lev in levels[1:]:
                out[f"Sex_{lev}_vs_{ref}"] = (sex == lev).astype(float)
    return out, params


def fit_ols(y: pd.Series, x: pd.DataFrame) -> dict:
    yv = y.to_numpy(dtype=float)
    xv = x.to_numpy(dtype=float)
    n, k = xv.shape
    beta = np.linalg.pinv(xv) @ yv
    fitted = xv @ beta
    resid = yv - fitted
    sse = float(np.sum(resid**2))
    sst = float(np.sum((yv - np.mean(yv)) ** 2))
    df_resid = n - k
    sigma2 = sse / df_resid if df_resid > 0 else np.nan
    xtx_inv = np.linalg.pinv(xv.T @ xv)
    se = np.sqrt(np.maximum(np.diag(xtx_inv) * sigma2, 0))
    tvals = beta / se
    pvals = np.array([student_t_two_sided_p(float(t), df_resid) for t in tvals])
    tcrit = student_t_ppf(0.975, df_resid)
    ci_low = beta - tcrit * se
    ci_high = beta + tcrit * se
    r2 = 1 - sse / sst if sst > 0 else np.nan
    adj_r2 = 1 - (1 - r2) * (n - 1) / df_resid if df_resid > 0 else np.nan
    return {
        "n": n,
        "k": k,
        "df_resid": df_resid,
        "beta": beta,
        "se": se,
        "t": tvals,
        "p": pvals,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "fitted": fitted,
        "resid": resid,
        "sse": sse,
        "sst": sst,
        "r2": float(r2),
        "adj_r2": float(adj_r2),
        "rmse": float(np.sqrt(np.mean(resid**2))),
        "mae": float(np.mean(np.abs(resid))),
        "condition_number": float(np.linalg.cond(xv)),
        "columns": list(x.columns),
    }


def make_folds(n: int, rng: np.random.Generator, splits: int) -> list[np.ndarray]:
    idx = np.arange(n)
    rng.shuffle(idx)
    return np.array_split(idx, splits)


def repeated_cv(frame: pd.DataFrame, outcome: str, include_modules: bool) -> dict:
    data = frame.loc[frame[outcome].notna()].copy()
    y_all = data[outcome].to_numpy(dtype=float)
    n = len(data)
    if n < N_SPLITS:
        return {"cv_r2_mean": np.nan, "cv_r2_sd": np.nan, "cv_rmse_mean": np.nan, "cv_rmse_sd": np.nan}
    rng = np.random.default_rng(RANDOM_SEED)
    r2s, rmses = [], []
    for _ in range(N_REPEATS):
        folds = make_folds(n, rng, N_SPLITS)
        pred = np.empty(n)
        pred[:] = np.nan
        for test_pos in folds:
            train_pos = np.setdiff1d(np.arange(n), test_pos, assume_unique=False)
            train = data.iloc[train_pos]
            test = data.iloc[test_pos]
            x_train, params = design_matrix(train, include_modules=include_modules, fit_params=True)
            x_test, _ = design_matrix(test, include_modules=include_modules, params=params)
            model = fit_ols(train[outcome], x_train)
            pred[test_pos] = x_test.to_numpy(dtype=float) @ model["beta"]
        sse = float(np.sum((y_all - pred) ** 2))
        sst = float(np.sum((y_all - np.mean(y_all)) ** 2))
        r2s.append(1 - sse / sst if sst > 0 else np.nan)
        rmses.append(float(np.sqrt(np.mean((y_all - pred) ** 2))))
    return {
        "cv_r2_mean": float(np.nanmean(r2s)),
        "cv_r2_sd": float(np.nanstd(r2s, ddof=1)),
        "cv_rmse_mean": float(np.nanmean(rmses)),
        "cv_rmse_sd": float(np.nanstd(rmses, ddof=1)),
    }


def vif_table(x: pd.DataFrame) -> pd.DataFrame:
    rows = []
    predictors = [c for c in x.columns if c != "Intercept"]
    for col in predictors:
        y = x[col].to_numpy(dtype=float)
        others = x[[c for c in x.columns if c not in ["Intercept", col]]].copy()
        others.insert(0, "Intercept", 1.0)
        if np.std(y, ddof=1) <= IQR_TOL:
            r2, vif = np.nan, np.inf
        else:
            model = fit_ols(pd.Series(y), others)
            r2 = model["r2"]
            vif = np.inf if (1 - r2) <= IQR_TOL else 1 / (1 - r2)
        rows.append({"predictor": col, "r2_against_other_predictors": r2, "vif": vif})
    return pd.DataFrame(rows)


def model_tables(scores: pd.DataFrame):
    coef_rows = []
    perf_rows = []
    vif_rows = []
    for outcome in ["AL", "SE"]:
        data = scores.loc[scores[outcome].notna()].copy()
        x_base, _ = design_matrix(data, include_modules=False, fit_params=True)
        x_full, _ = design_matrix(data, include_modules=True, fit_params=True)
        y = data[outcome]
        base = fit_ols(y, x_base)
        full = fit_ols(y, x_full)
        for model_name, model in [("Age+Sex", base), ("Age+Sex+Cho", full)]:
            for name, beta, se, tval, pval, lo, hi in zip(
                model["columns"], model["beta"], model["se"], model["t"], model["p"], model["ci_low"], model["ci_high"]
            ):
                coef_rows.append(
                    {
                        "outcome": outcome,
                        "model": model_name,
                        "term": name,
                        "estimate": float(beta),
                        "std_error": float(se),
                        "t_value": float(tval),
                        "p_value": float(pval),
                        "ci_95_low": float(lo),
                        "ci_95_high": float(hi),
                    }
                )

        df_diff = full["k"] - base["k"]
        if df_diff > 0 and full["df_resid"] > 0:
            f_stat = ((base["sse"] - full["sse"]) / df_diff) / (full["sse"] / full["df_resid"])
            f_p = float(f_survival(f_stat, df_diff, full["df_resid"]))
        else:
            f_stat, f_p = np.nan, np.nan
        base_cv = repeated_cv(scores, outcome, include_modules=False)
        full_cv = repeated_cv(scores, outcome, include_modules=True)
        for model_name, model, cv in [("Age+Sex", base, base_cv), ("Age+Sex+Cho", full, full_cv)]:
            perf_rows.append(
                {
                    "outcome": outcome,
                    "model": model_name,
                    "n": model["n"],
                    "r2": model["r2"],
                    "adj_r2": model["adj_r2"],
                    "rmse": model["rmse"],
                    "mae": model["mae"],
                    "cv_r2_mean": cv["cv_r2_mean"],
                    "cv_r2_sd": cv["cv_r2_sd"],
                    "cv_rmse_mean": cv["cv_rmse_mean"],
                    "cv_rmse_sd": cv["cv_rmse_sd"],
                    "condition_number": model["condition_number"],
                    "delta_r2_vs_age_sex": full["r2"] - base["r2"] if model_name == "Age+Sex+Cho" else np.nan,
                    "partial_f_for_cho_block": f_stat if model_name == "Age+Sex+Cho" else np.nan,
                    "partial_f_p_for_cho_block": f_p if model_name == "Age+Sex+Cho" else np.nan,
                }
            )
        vifs = vif_table(x_full)
        vifs.insert(0, "outcome", outcome)
        vif_rows.append(vifs)
    return pd.DataFrame(coef_rows), pd.DataFrame(perf_rows), pd.concat(vif_rows, ignore_index=True)


def save_correlation_heatmap(corr: pd.DataFrame, path: Path):
    if Image is None:
        return
    font = ImageFont.load_default()
    labels = list(corr.columns)
    cell = 86
    left = 165
    top = 105
    width = left + cell * len(labels) + 150
    height = top + cell * len(labels) + 100
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    def color_for(value: float) -> tuple[int, int, int]:
        v = max(-1.0, min(1.0, float(value)))
        if v < 0:
            t = v + 1.0
            c1 = np.array([37, 99, 235])
            c2 = np.array([255, 255, 255])
        else:
            t = v
            c1 = np.array([255, 255, 255])
            c2 = np.array([220, 38, 38])
        rgb = (c1 * (1 - t) + c2 * t).astype(int)
        return tuple(int(x) for x in rgb)

    draw.text((20, 22), "Pearson correlations among Cho module z-scores", fill=(17, 24, 39), font=font)
    for i, row_lab in enumerate(labels):
        y = top + i * cell
        draw.text((22, y + cell // 2 - 6), row_lab, fill=(17, 24, 39), font=font)
    for j, col_lab in enumerate(labels):
        x = left + j * cell
        short = col_lab.replace("Branching Angle", "BranchAng")
        draw.text((x + 10, 75), short, fill=(17, 24, 39), font=font)
    for i in range(corr.shape[0]):
        for j in range(corr.shape[1]):
            x0 = left + j * cell
            y0 = top + i * cell
            val = corr.iloc[i, j]
            draw.rectangle([x0, y0, x0 + cell, y0 + cell], fill=color_for(val), outline=(229, 231, 235))
            text = f"{val:.2f}"
            bbox = draw.textbbox((0, 0), text, font=font)
            draw.text((x0 + (cell - (bbox[2] - bbox[0])) / 2, y0 + (cell - (bbox[3] - bbox[1])) / 2), text, fill=(17, 24, 39), font=font)
    legend_x = left + cell * len(labels) + 35
    for k in range(cell * len(labels)):
        v = 1.0 - 2.0 * k / max(1, cell * len(labels) - 1)
        draw.line([(legend_x, top + k), (legend_x + 18, top + k)], fill=color_for(v))
    draw.text((legend_x + 26, top), "1", fill=(17, 24, 39), font=font)
    draw.text((legend_x + 26, top + cell * len(labels) // 2 - 6), "0", fill=(17, 24, 39), font=font)
    draw.text((legend_x + 26, top + cell * len(labels) - 12), "-1", fill=(17, 24, 39), font=font)
    img.save(path)


def fmt_p(p: float) -> str:
    if pd.isna(p):
        return "NA"
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"


def df_to_md(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    df = df.copy()

    def cell_text(value) -> str:
        if pd.isna(value):
            return "NA"
        if isinstance(value, (float, np.floating)):
            if math.isinf(float(value)):
                return "Inf" if value > 0 else "-Inf"
            return f"{float(value):.4f}"
        if isinstance(value, (int, np.integer)):
            return str(int(value))
        return str(value)

    headers = [str(c) for c in df.columns]
    rows = [[cell_text(v) for v in row] for row in df.to_numpy(dtype=object)]
    widths = []
    for i, header in enumerate(headers):
        widths.append(max([len(header)] + [len(row[i]) for row in rows]))
    header_line = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    sep_line = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows]
    return "\n".join([header_line, sep_line] + body)


def write_report(
    df: pd.DataFrame,
    whole: pd.DataFrame,
    cohort_info: dict,
    qc_summary: pd.DataFrame,
    min_valid_n: int,
    impute: pd.DataFrame,
    scale: pd.DataFrame,
    corr: pd.DataFrame,
    bio: pd.DataFrame,
    coefs: pd.DataFrame,
    perf: pd.DataFrame,
    vifs: pd.DataFrame,
    warnings: list[str],
):
    report = []
    report.append("# Choroidal morphology module modeling report")
    report.append("")
    report.append(f"Input CSV: `{INPUT_CSV}`")
    report.append(f"Variable dictionary: `{VARIABLES_XLSX}`")
    report.append(f"Rows: {df.shape[0]}, columns: {df.shape[1]}")
    report.append(f"Reference OCTA cohort: `{REFERENCE_OCTA_CSV}`")
    report.append("")
    report.append("## Methods notes")
    report.append("- Cho records were aligned to the OCTA patient cohort by `ID` before QC and modeling.")
    report.append("- Selected variables where `Region == Whole` and `Category` is one of Density, Complexity, Calibre, Tortuosity, Branching Angle.")
    report.append(
        f"- QC retained variables with `missing_rate <= 90%`, `IQR > {IQR_TOL:g}`, and `valid_n >= max(20, ceil(10% of N)) = {min_valid_n}`."
    )
    report.append(
        "- Because variables within a Cho category have different units/scales, the primary module score was calculated as: variable-level median imputation -> variable-level z-score -> module-wise row median -> module-level z-score."
    )
    report.append("- Outcomes (`AL`, `SE`) were not imputed. Prediction models compare `Age + Sex` against `Age + Sex + five Cho module scores`.")
    report.append("- Step 7 biological validation was interpreted as Pearson associations between each Cho module z-score and Age, AL, and SE.")
    if warnings:
        report.append("")
        report.append("## Warnings")
        for item in warnings:
            report.append(f"- {item}")
    report.append("")
    report.append("## Cohort Alignment")
    report.append(
        df_to_md(
            pd.DataFrame(
                [
                    {
                        "cho_rows_before": cohort_info.get("cho_rows_before_alignment"),
                        "cho_unique_ids_before": cohort_info.get("cho_unique_ids_before_alignment"),
                        "octa_rows": cohort_info.get("octa_rows"),
                        "octa_unique_ids": cohort_info.get("octa_unique_ids"),
                        "cho_rows_after": cohort_info.get("cho_rows_after_alignment"),
                        "cho_unique_ids_after": cohort_info.get("cho_unique_ids_after_alignment"),
                        "id_sets_match_after": cohort_info.get("cohort_id_sets_match_after_alignment"),
                    }
                ]
            )
        )
    )
    if cohort_info.get("cho_ids_not_in_octa") or cohort_info.get("octa_ids_not_in_cho"):
        report.append("")
        report.append(f"Cho IDs excluded because absent in OCTA: `{', '.join(cohort_info.get('cho_ids_not_in_octa', [])) or 'none'}`")
        report.append(f"OCTA IDs absent in Cho: `{', '.join(cohort_info.get('octa_ids_not_in_cho', [])) or 'none'}`")
    report.append("")
    report.append("## Selected Whole Variables")
    selected_counts = (
        whole.groupby("Category", as_index=False)
        .agg(variables=("variable", "count"), matched_in_csv=("matched_in_csv", "sum"))
        .sort_values("Category", key=lambda x: x.map({c: i for i, c in enumerate(CATEGORY_ORDER)}))
    )
    report.append(df_to_md(selected_counts))
    report.append("")
    report.append("## QC Summary")
    report.append(df_to_md(qc_summary))
    report.append("")
    report.append("## Imputation And Scaling")
    report.append(df_to_md(impute[["variable", "category", "missing_before_imputation", "imputation_method", "imputation_value"]]))
    report.append("")
    report.append(df_to_md(scale[["variable", "z_variable", "mean", "sample_sd"]]))
    report.append("")
    report.append("## Module Correlations")
    report.append(df_to_md(corr.reset_index(names="module")))
    report.append("")
    report.append("## Biological Validation")
    report.append(df_to_md(bio))
    report.append("")
    report.append("## Prediction Model Performance")
    report.append(df_to_md(perf))
    report.append("")
    report.append("## Full-Model Coefficients")
    report.append(df_to_md(coefs[coefs["model"] == "Age+Sex+Cho"]))
    report.append("")
    report.append("## VIF")
    report.append(df_to_md(vifs))
    report.append("")
    report.append("## Quick Interpretation")
    for outcome in ["AL", "SE"]:
        pfull = perf[(perf["outcome"] == outcome) & (perf["model"] == "Age+Sex+Cho")].iloc[0]
        pbase = perf[(perf["outcome"] == outcome) & (perf["model"] == "Age+Sex")].iloc[0]
        report.append(
            f"- {outcome}: full model R2={pfull['r2']:.3f} vs baseline R2={pbase['r2']:.3f}; "
            f"delta R2={pfull['delta_r2_vs_age_sex']:.3f}; Cho block partial-F p={fmt_p(pfull['partial_f_p_for_cho_block'])}; "
            f"repeated 5-fold CV R2={pfull['cv_r2_mean']:.3f}."
        )
    (OUTPUT_DIR / f"{OUTPUT_PREFIX}_analysis_report.md").write_text("\n".join(report), encoding="utf-8")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df, variables, whole = read_inputs()
    df, cohort_info = align_to_octa_cohort(df)
    warnings = []
    if cohort_info.get("cho_ids_not_in_octa"):
        warnings.append(
            f"Excluded {len(cohort_info['cho_ids_not_in_octa'])} Cho IDs absent from OCTA: "
            + ", ".join(cohort_info["cho_ids_not_in_octa"])
        )
    if cohort_info.get("octa_ids_not_in_cho"):
        warnings.append(
            f"OCTA contains {len(cohort_info['octa_ids_not_in_cho'])} IDs absent from Cho: "
            + ", ".join(cohort_info["octa_ids_not_in_cho"])
        )
    if whole.empty:
        warnings.append("No Whole-region variables with recognized categories were found.")
    unmatched = whole.loc[~whole["matched_in_csv"], "variable"].tolist()
    if unmatched:
        warnings.append(f"{len(unmatched)} selected variables were not found in the CSV.")

    qc, qc_summary, retained, min_valid_n = qc_variables(df, whole)
    missing_categories = [category for category, cols in retained.items() if len(cols) == 0]
    if missing_categories:
        warnings.append(f"No retained variables after QC for categories: {', '.join(missing_categories)}.")

    scores, impute, scale, feature_scale = prepare_scores(df, retained)
    corr, pmat = correlation_tables(scores)
    bio = biological_validation(scores)
    coefs, perf, vifs = model_tables(scores)

    qc.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_qc_variables.csv", index=False, encoding="utf-8-sig")
    qc_summary.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_qc_summary.csv", index=False, encoding="utf-8-sig")
    whole.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_whole_variable_dictionary_selected.csv", index=False, encoding="utf-8-sig")
    feature_scale.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_scaling_summary.csv", index=False, encoding="utf-8-sig")
    impute.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_imputation_summary.csv", index=False, encoding="utf-8-sig")
    scale.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_scaling_summary.csv", index=False, encoding="utf-8-sig")
    corr.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_correlations.csv", encoding="utf-8-sig")
    pmat.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_correlation_pvalues.csv", encoding="utf-8-sig")
    bio.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_biological_validation_pearson.csv", index=False, encoding="utf-8-sig")
    coefs.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_model_coefficients.csv", index=False, encoding="utf-8-sig")
    perf.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_model_performance.csv", index=False, encoding="utf-8-sig")
    vifs.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_model_vif.csv", index=False, encoding="utf-8-sig")

    score_cols = [c for c in ["ID", "Age", "Sex", "AL", "SE", "Age_model", "Age_z", "Sex_model"] if c in scores]
    for category in CATEGORY_ORDER:
        slug = category_slug(category)
        score_cols.extend([f"{slug}_raw_median", module_score_col(category), module_z_col(category)])
    scores[score_cols].to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_scores_model_dataset.csv", index=False, encoding="utf-8-sig")

    save_correlation_heatmap(corr, OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_correlation_heatmap.png")

    write_report(
        df=df,
        whole=whole,
        cohort_info=cohort_info,
        qc_summary=qc_summary,
        min_valid_n=min_valid_n,
        impute=impute,
        scale=scale,
        corr=corr,
        bio=bio,
        coefs=coefs,
        perf=perf,
        vifs=vifs,
        warnings=warnings,
    )

    manifest = {
        "input_csv": str(INPUT_CSV),
        "variables_xlsx": str(VARIABLES_XLSX),
        "output_dir": str(OUTPUT_DIR),
        "n_rows": int(df.shape[0]),
        "n_columns": int(df.shape[1]),
        "selected_whole_variables": int(len(whole)),
        "category_order": CATEGORY_ORDER,
        "selected_by_category": whole["Category"].value_counts().reindex(CATEGORY_ORDER).fillna(0).astype(int).to_dict(),
        "retained_by_category": {category: len(cols) for category, cols in retained.items()},
        "min_valid_n_threshold": min_valid_n,
        "cohort_alignment": cohort_info,
        "outputs": sorted(p.name for p in OUTPUT_DIR.glob(f"{OUTPUT_PREFIX}_*")),
        "warnings": warnings,
    }
    (OUTPUT_DIR / f"{OUTPUT_PREFIX}_run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
