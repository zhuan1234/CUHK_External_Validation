from __future__ import annotations

import json
import math
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - optional plotting only
    Image = ImageDraw = ImageFont = None


INPUT_CSV = Path(r"C:\Users\25124968R\Desktop\CUHK\CUHK_OCTA_OD_260614.csv")
OUTPUT_DIR = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-14\octa-c-users-25124968r-desktop-cuhk\outputs"
)

MISSING_RATE_THRESHOLD = 0.90
IQR_TOL = 1e-8
RANDOM_SEED = 614
N_SPLITS = 5
N_REPEATS = 50


MODULES = OrderedDict(
    [
        (
            "CCFA",
            {
                "label": "Choriocapillaris Flow Area",
                "aliases": ["Choriocapillaris_Flow_Area"],
                "score": "CCFA_median",
            },
        ),
        (
            "CFA",
            {
                "label": "Choroid Flow Area",
                "aliases": ["Choroid_Flow_Area"],
                "score": "CFA_median",
            },
        ),
        (
            "CT",
            {
                "label": "Choroid Thickness",
                "aliases": ["Choroid_Thickness", "Choroidal_Thickness"],
                "score": "CT_median",
            },
        ),
        (
            "CVI",
            {
                "label": "CVI",
                "aliases": ["CVI", "Choroidal_Vascularity_Index"],
                "score": "CVI_median",
            },
        ),
    ]
)

ACTIVE_MODULE_KEYS = ["CCFA", "CT", "CVI"]
OUTPUT_PREFIX = "octa_3module"


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for incomplete beta, adapted from Numerical Recipes."""
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
    if t >= 0:
        return 1.0 - 0.5 * ib
    return 0.5 * ib


def student_t_two_sided_p(t: float, df: int | float) -> float:
    if not math.isfinite(t) or df <= 0:
        return np.nan
    p = 2.0 * (1.0 - student_t_cdf(abs(t), df))
    return max(0.0, min(1.0, p))


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
    cdf = regularized_beta(x, df1 / 2.0, df2 / 2.0)
    return max(0.0, min(1.0, 1.0 - cdf))


def simple_linregress(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float]:
    n = len(x)
    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))
    ssx = float(np.sum((x - x_mean) ** 2))
    if ssx <= IQR_TOL or n < 3:
        return np.nan, np.nan, np.nan, np.nan
    slope = float(np.sum((x - x_mean) * (y - y_mean)) / ssx)
    intercept = y_mean - slope * x_mean
    resid = y - (intercept + slope * x)
    sigma2 = float(np.sum(resid**2) / (n - 2))
    se_slope = math.sqrt(sigma2 / ssx)
    tval = slope / se_slope if se_slope > 0 else np.nan
    pval = student_t_two_sided_p(tval, n - 2)
    return slope, intercept, se_slope, pval


def to_numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def detect_module_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    module_cols: dict[str, list[str]] = {}
    for key, spec in MODULES.items():
        aliases = spec["aliases"]
        cols = [col for col in df.columns if any(alias in col for alias in aliases)]
        module_cols[key] = cols
    return module_cols


def qnorm(series: pd.Series, q: float) -> float:
    return float(series.quantile(q, interpolation="linear"))


def make_qc_tables(df: pd.DataFrame, module_cols: dict[str, list[str]]):
    qc_records = []
    retained: dict[str, list[str]] = {}
    for module, cols in module_cols.items():
        retained[module] = []
        for col in cols:
            numeric = to_numeric_series(df[col])
            missing_rate = float(numeric.isna().mean())
            if numeric.notna().sum() == 0:
                iqr = np.nan
            else:
                iqr = qnorm(numeric.dropna(), 0.75) - qnorm(numeric.dropna(), 0.25)
            drop_missing = missing_rate > MISSING_RATE_THRESHOLD
            drop_low_iqr = (not pd.isna(iqr)) and abs(iqr) <= IQR_TOL
            reasons = []
            if drop_missing:
                reasons.append(f"missing_rate>{MISSING_RATE_THRESHOLD:.2f}")
            if drop_low_iqr:
                reasons.append(f"IQR<={IQR_TOL:g}")
            if not reasons:
                retained[module].append(col)
            qc_records.append(
                {
                    "module": module,
                    "module_label": MODULES[module]["label"],
                    "column": col,
                    "missing_rate": missing_rate,
                    "iqr": iqr,
                    "drop_missing_rate_gt_90pct": drop_missing,
                    "drop_low_iqr": drop_low_iqr,
                    "retained": not reasons,
                    "drop_reason": "; ".join(reasons),
                }
            )

    qc_columns = pd.DataFrame(qc_records)
    qc_summary = (
        qc_columns.groupby(["module", "module_label"], as_index=False)
        .agg(
            input_grid_columns=("column", "count"),
            removed_missing_rate_gt_90pct=("drop_missing_rate_gt_90pct", "sum"),
            removed_low_iqr=("drop_low_iqr", "sum"),
            retained_columns=("retained", "sum"),
            median_missing_rate=("missing_rate", "median"),
            max_missing_rate=("missing_rate", "max"),
            min_iqr=("iqr", "min"),
            median_iqr=("iqr", "median"),
        )
        .sort_values("module")
    )
    return qc_columns, qc_summary, retained


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
    for module in ACTIVE_MODULE_KEYS:
        cols = retained[module]
        raw_col = f"{MODULES[module]['score']}_raw"
        score_col = MODULES[module]["score"]
        if cols:
            module_values = df[cols].apply(to_numeric_series)
            scores[raw_col] = module_values.median(axis=1, skipna=True)
        else:
            scores[raw_col] = np.nan

        impute_value = float(scores[raw_col].median(skipna=True))
        missing_before = int(scores[raw_col].isna().sum())
        scores[score_col] = scores[raw_col].fillna(impute_value)
        impute_records.append(
            {
                "variable": score_col,
                "source_column": raw_col,
                "missing_before_imputation": missing_before,
                "imputation_method": "median",
                "imputation_value": impute_value,
            }
        )
        z, mean, sd = sample_z(scores[score_col])
        scores[f"{score_col}_z"] = z
        scale_records.append(
            {
                "variable": score_col,
                "z_variable": f"{score_col}_z",
                "scale_method": "R scale style: (x - mean) / sample_sd",
                "mean": mean,
                "sample_sd": sd,
            }
        )

    if "Age" in scores.columns:
        age_impute = float(scores["Age"].median(skipna=True))
        missing_age = int(scores["Age"].isna().sum())
        scores["Age_model"] = scores["Age"].fillna(age_impute)
        scores["Age_z"], age_mean, age_sd = sample_z(scores["Age_model"])
        impute_records.append(
            {
                "variable": "Age_model",
                "source_column": "Age",
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
        sex_levels = sorted_levels(scores["Sex"])
        mode = scores["Sex"].mode(dropna=True)
        sex_impute = mode.iloc[0] if not mode.empty else np.nan
        scores["Sex_model"] = scores["Sex"].fillna(sex_impute)
        impute_records.append(
            {
                "variable": "Sex_model",
                "source_column": "Sex",
                "missing_before_imputation": int(scores["Sex"].isna().sum()),
                "imputation_method": "mode for categorical covariate",
                "imputation_value": sex_impute,
            }
        )
    else:
        sex_levels = []

    return scores, pd.DataFrame(impute_records), pd.DataFrame(scale_records), sex_levels


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
    return n, float(r), float(p)


def correlation_tables(scores: pd.DataFrame):
    z_cols = [f"{MODULES[m]['score']}_z" for m in ACTIVE_MODULE_KEYS]
    labels = [MODULES[m]["label"] for m in ACTIVE_MODULE_KEYS]
    corr = scores[z_cols].corr(method="pearson")
    corr.index = labels
    corr.columns = labels

    pmat = pd.DataFrame(np.nan, index=labels, columns=labels)
    for i, a in enumerate(z_cols):
        for j, b in enumerate(z_cols):
            if i == j:
                pmat.iloc[i, j] = 0.0
            elif i < j:
                _, _, p = pearson_pair(scores[a], scores[b])
                pmat.iloc[i, j] = p
                pmat.iloc[j, i] = p
    return corr, pmat


def icc_2_1(x: pd.Series, y: pd.Series) -> tuple[int, float]:
    data = pd.concat([x, y], axis=1).dropna().to_numpy(dtype=float)
    n, k = data.shape
    if n < 3 or k != 2:
        return n, np.nan
    row_means = data.mean(axis=1)
    col_means = data.mean(axis=0)
    grand = data.mean()
    ss_rows = k * np.sum((row_means - grand) ** 2)
    ss_cols = n * np.sum((col_means - grand) ** 2)
    ss_error = np.sum((data - row_means[:, None] - col_means[None, :] + grand) ** 2)
    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))
    denom = ms_rows + (k - 1) * ms_error + k * (ms_cols - ms_error) / n
    if abs(denom) <= IQR_TOL:
        return n, np.nan
    return n, float((ms_rows - ms_error) / denom)


def bland_altman(x: pd.Series, y: pd.Series) -> dict:
    data = pd.concat([x, y], axis=1).dropna()
    if len(data) < 3:
        return {
            "n": len(data),
            "bias_mean_difference": np.nan,
            "sd_difference": np.nan,
            "loa_lower_95": np.nan,
            "loa_upper_95": np.nan,
            "proportional_bias_slope": np.nan,
            "proportional_bias_p": np.nan,
        }
    xv = data.iloc[:, 0].to_numpy(dtype=float)
    yv = data.iloc[:, 1].to_numpy(dtype=float)
    diff = xv - yv
    avg = (xv + yv) / 2
    bias = float(np.mean(diff))
    sd = float(np.std(diff, ddof=1))
    slope, intercept, se, p = simple_linregress(avg, diff)
    return {
        "n": len(data),
        "bias_mean_difference": bias,
        "sd_difference": sd,
        "loa_lower_95": bias - 1.96 * sd,
        "loa_upper_95": bias + 1.96 * sd,
        "proportional_bias_slope": float(slope),
        "proportional_bias_p": float(p),
    }


def validation_tables(scores: pd.DataFrame):
    rows = []
    modules = list(ACTIVE_MODULE_KEYS)
    for i, m1 in enumerate(modules):
        for m2 in modules[i + 1 :]:
            c1 = f"{MODULES[m1]['score']}_z"
            c2 = f"{MODULES[m2]['score']}_z"
            n, r, p = pearson_pair(scores[c1], scores[c2])
            _, icc = icc_2_1(scores[c1], scores[c2])
            ba = bland_altman(scores[c1], scores[c2])
            rows.append(
                {
                    "comparison": f"{MODULES[m1]['label']} vs {MODULES[m2]['label']}",
                    "scale": "z-score",
                    "n": n,
                    "pearson_r": r,
                    "pearson_p": p,
                    "icc_2_1_absolute_agreement": icc,
                    **{k: v for k, v in ba.items() if k != "n"},
                }
            )

    return pd.DataFrame(rows)


def design_matrix(
    frame: pd.DataFrame,
    include_modules: bool,
    params: dict | None = None,
    fit_params: bool = False,
):
    if fit_params:
        params = {}
    assert params is not None

    out = pd.DataFrame(index=frame.index)
    out["Intercept"] = 1.0

    continuous_cols = ["Age_model"]
    if include_modules:
        continuous_cols += [MODULES[m]["score"] for m in ACTIVE_MODULE_KEYS]

    for col in continuous_cols:
        raw_source = "Age" if col == "Age_model" else f"{col}_raw"
        values = frame[raw_source if raw_source in frame.columns else col].copy()
        values = to_numeric_series(values)
        if fit_params:
            median = float(values.median(skipna=True))
            filled = values.fillna(median)
            mean = float(filled.mean())
            sd = float(filled.std(ddof=1))
            params[col] = {"median": median, "mean": mean, "sd": sd}
        cfg = params[col]
        filled = values.fillna(cfg["median"])
        if not math.isfinite(cfg["sd"]) or abs(cfg["sd"]) <= IQR_TOL:
            out[f"{col}_z"] = 0.0
        else:
            out[f"{col}_z"] = (filled - cfg["mean"]) / cfg["sd"]

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
        if len(levels) <= 1:
            pass
        else:
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
            vif = np.inf
            r2 = np.nan
        else:
            m = fit_ols(pd.Series(y), others)
            r2 = m["r2"]
            vif = np.inf if (1 - r2) <= IQR_TOL else 1 / (1 - r2)
        rows.append({"predictor": col, "r2_against_other_predictors": r2, "vif": vif})
    return pd.DataFrame(rows)


def model_tables(scores: pd.DataFrame):
    coef_rows = []
    perf_rows = []
    vif_rows = []
    for outcome in ["AL", "SE"]:
        data = scores.loc[scores[outcome].notna()].copy()
        x_base, base_params = design_matrix(data, include_modules=False, fit_params=True)
        x_full, full_params = design_matrix(data, include_modules=True, fit_params=True)
        y = data[outcome]
        base = fit_ols(y, x_base)
        full = fit_ols(y, x_full)

        for model_name, model in [("Age+Sex", base), ("Age+Sex+OCTA", full)]:
            for name, beta, se, tval, pval, lo, hi in zip(
                model["columns"],
                model["beta"],
                model["se"],
                model["t"],
                model["p"],
                model["ci_low"],
                model["ci_high"],
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
            f_stat = np.nan
            f_p = np.nan

        base_cv = repeated_cv(scores, outcome, include_modules=False)
        full_cv = repeated_cv(scores, outcome, include_modules=True)
        for model_name, model, cv in [
            ("Age+Sex", base, base_cv),
            ("Age+Sex+OCTA", full, full_cv),
        ]:
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
                    "delta_r2_vs_age_sex": full["r2"] - base["r2"] if model_name == "Age+Sex+OCTA" else np.nan,
                    "partial_f_for_octa_block": f_stat if model_name == "Age+Sex+OCTA" else np.nan,
                    "partial_f_p_for_octa_block": f_p if model_name == "Age+Sex+OCTA" else np.nan,
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
    labels = list(ACTIVE_MODULE_KEYS)
    cell = 92
    left = 145
    top = 105
    width = left + cell * len(labels) + 160
    height = top + cell * len(labels) + 115
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

    draw.text((20, 22), "Pearson correlations among OCTA module z-scores", fill=(17, 24, 39), font=font)
    for i, row_lab in enumerate(labels):
        y = top + i * cell
        draw.text((35, y + cell // 2 - 6), row_lab, fill=(17, 24, 39), font=font)
    for j, col_lab in enumerate(labels):
        x = left + j * cell
        draw.text((x + 28, 75), col_lab, fill=(17, 24, 39), font=font)
    for i in range(corr.shape[0]):
        for j in range(corr.shape[1]):
            x0 = left + j * cell
            y0 = top + i * cell
            val = corr.iloc[i, j]
            draw.rectangle([x0, y0, x0 + cell, y0 + cell], fill=color_for(val), outline=(229, 231, 235))
            text = f"{val:.2f}"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((x0 + (cell - tw) / 2, y0 + (cell - th) / 2), text, fill=(17, 24, 39), font=font)
    legend_x = left + cell * len(labels) + 35
    legend_y = top
    for k in range(cell * len(labels)):
        v = 1.0 - 2.0 * k / max(1, cell * len(labels) - 1)
        draw.line([(legend_x, legend_y + k), (legend_x + 18, legend_y + k)], fill=color_for(v))
    draw.text((legend_x + 26, legend_y), "1", fill=(17, 24, 39), font=font)
    draw.text((legend_x + 26, legend_y + cell * len(labels) // 2 - 6), "0", fill=(17, 24, 39), font=font)
    draw.text((legend_x + 26, legend_y + cell * len(labels) - 12), "-1", fill=(17, 24, 39), font=font)
    img.save(path)


def save_bland_altman(scores: pd.DataFrame, path: Path, m1: str, m2: str):
    if Image is None:
        return
    x = scores[f"{MODULES[m1]['score']}_z"]
    y = scores[f"{MODULES[m2]['score']}_z"]
    data = pd.concat([x, y], axis=1).dropna()
    avg = data.mean(axis=1)
    diff = data.iloc[:, 0] - data.iloc[:, 1]
    bias = diff.mean()
    sd = diff.std(ddof=1)
    lo = bias - 1.96 * sd
    hi = bias + 1.96 * sd
    font = ImageFont.load_default()
    width, height = 900, 620
    left, top, right, bottom = 90, 80, 50, 90
    plot_w = width - left - right
    plot_h = height - top - bottom
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    x_min, x_max = float(avg.min()), float(avg.max())
    y_min = float(min(diff.min(), lo))
    y_max = float(max(diff.max(), hi))
    x_pad = (x_max - x_min) * 0.06 or 1.0
    y_pad = (y_max - y_min) * 0.10 or 1.0
    x_min -= x_pad
    x_max += x_pad
    y_min -= y_pad
    y_max += y_pad

    def px(val: float) -> int:
        return int(left + (val - x_min) / (x_max - x_min) * plot_w)

    def py(val: float) -> int:
        return int(top + (y_max - val) / (y_max - y_min) * plot_h)

    title = f"Bland-Altman z-score: {m1} vs {m2}"
    draw.text((35, 25), title, fill=(17, 24, 39), font=font)
    draw.rectangle([left, top, left + plot_w, top + plot_h], outline=(31, 41, 55), width=1)
    for val, color, label in [
        (bias, (17, 24, 39), f"Bias {bias:.3f}"),
        (lo, (220, 38, 38), f"Lower LoA {lo:.3f}"),
        (hi, (220, 38, 38), f"Upper LoA {hi:.3f}"),
    ]:
        ypix = py(float(val))
        dash = 8 if val != bias else None
        if dash:
            for x0 in range(left, left + plot_w, dash * 2):
                draw.line([(x0, ypix), (min(x0 + dash, left + plot_w), ypix)], fill=color, width=2)
        else:
            draw.line([(left, ypix), (left + plot_w, ypix)], fill=color, width=2)
        draw.text((left + plot_w - 125, ypix - 12), label, fill=color, font=font)

    for xv, yv in zip(avg.to_numpy(dtype=float), diff.to_numpy(dtype=float)):
        cx, cy = px(float(xv)), py(float(yv))
        draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(37, 99, 235), outline=(255, 255, 255))

    for t in np.linspace(x_min, x_max, 5):
        xpix = px(float(t))
        draw.line([(xpix, top + plot_h), (xpix, top + plot_h + 5)], fill=(31, 41, 55))
        draw.text((xpix - 18, top + plot_h + 12), f"{t:.2f}", fill=(31, 41, 55), font=font)
    for t in np.linspace(y_min, y_max, 5):
        ypix = py(float(t))
        draw.line([(left - 5, ypix), (left, ypix)], fill=(31, 41, 55))
        draw.text((20, ypix - 6), f"{t:.2f}", fill=(31, 41, 55), font=font)
    draw.text((left + plot_w // 2 - 105, height - 38), f"Average of {m1} and {m2} z-scores", fill=(17, 24, 39), font=font)
    draw.text((left, 55), f"{m1} z-score - {m2} z-score", fill=(17, 24, 39), font=font)
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
        width = len(header)
        for row in rows:
            width = max(width, len(row[i]))
        widths.append(width)
    header_line = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    sep_line = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers))) + " |" for row in rows]
    return "\n".join([header_line, sep_line] + body)


def write_report(
    df: pd.DataFrame,
    qc_summary: pd.DataFrame,
    impute: pd.DataFrame,
    scale: pd.DataFrame,
    corr: pd.DataFrame,
    pairwise_validation: pd.DataFrame,
    coefs: pd.DataFrame,
    perf: pd.DataFrame,
    vifs: pd.DataFrame,
    warnings: list[str],
):
    report = []
    report.append("# OCTA 3-module data modeling report")
    report.append("")
    report.append(f"Input file: `{INPUT_CSV}`")
    report.append(f"Rows: {df.shape[0]}, columns: {df.shape[1]}")
    report.append("")
    report.append("## Methods notes")
    report.append(
        "- QC was applied to OCTA grid columns only: remove `missing_rate > 90%`, then remove near-zero variation columns with `IQR <= 1e-8`."
    )
    report.append(
        "- Module scores are row-wise medians across retained grid columns. Missing module summaries were median-imputed before z-scoring."
    )
    report.append(
        "- Revised biomarker module set for Step 5, Step 6, and Step 8: `CCFA`, `CT`, and `CVI`. `CFA` was excluded from the final module set because it was highly collinear with `CCFA` in the first run."
    )
    report.append(
        "- `scale()` was implemented as `(x - mean) / sample_sd`, matching R's default sample standard deviation behavior."
    )
    report.append(
        "- Outcomes (`AL`, `SE`) were not imputed. Prediction models used `Age + Sex` as baseline and `Age + Sex + three OCTA z-scores` as the full model."
    )
    report.append(
        "- ICC and Bland-Altman are strict agreement tools only when two variables are intended to measure the same construct on compatible scales. Since the retained 3 modules have different raw units/constructs, Step 6 ICC and Bland-Altman are reported as exploratory z-score agreement checks."
    )
    if warnings:
        report.append("")
        report.append("## Warnings")
        for item in warnings:
            report.append(f"- {item}")
    report.append("")
    report.append("## QC summary")
    report.append(df_to_md(qc_summary))
    report.append("")
    report.append("## Imputation and scaling")
    report.append(df_to_md(impute[["variable", "missing_before_imputation", "imputation_method", "imputation_value"]]))
    report.append("")
    report.append(df_to_md(scale[["variable", "z_variable", "mean", "sample_sd"]]))
    report.append("")
    report.append("## Module correlation matrix")
    report.append(df_to_md(corr.reset_index(names="module")))
    report.append("")
    report.append("## Biological validation")
    report.append("Pairwise z-score validation among retained modules:")
    report.append(df_to_md(pairwise_validation))
    report.append("")
    report.append("## Prediction model performance")
    perf_view = perf.copy()
    report.append(df_to_md(perf_view))
    report.append("")
    report.append("## Full-model coefficients")
    full_coefs = coefs[coefs["model"] == "Age+Sex+OCTA"].copy()
    report.append(df_to_md(full_coefs))
    report.append("")
    report.append("## VIF")
    report.append(df_to_md(vifs))
    report.append("")
    report.append("## Quick interpretation")
    for outcome in ["AL", "SE"]:
        pfull = perf[(perf["outcome"] == outcome) & (perf["model"] == "Age+Sex+OCTA")].iloc[0]
        pbase = perf[(perf["outcome"] == outcome) & (perf["model"] == "Age+Sex")].iloc[0]
        report.append(
            f"- {outcome}: full model R2={pfull['r2']:.3f} vs baseline R2={pbase['r2']:.3f}; "
            f"delta R2={pfull['delta_r2_vs_age_sex']:.3f}; OCTA block partial-F p={fmt_p(pfull['partial_f_p_for_octa_block'])}; "
            f"repeated 5-fold CV R2={pfull['cv_r2_mean']:.3f}."
        )

    (OUTPUT_DIR / f"{OUTPUT_PREFIX}_analysis_report.md").write_text("\n".join(report), encoding="utf-8")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(INPUT_CSV, na_values=["", "NA", "N/A", "NaN", "nan", "NULL", "null"])
    module_cols = detect_module_columns(df)
    warnings = []
    for module, cols in module_cols.items():
        if len(cols) != 63:
            warnings.append(
                f"{MODULES[module]['label']} detected {len(cols)} grid columns; expected 63 from the protocol."
            )

    qc_columns, qc_summary, retained = make_qc_tables(df, module_cols)
    scores, impute, scale, sex_levels = prepare_scores(df, retained)
    corr, pmat = correlation_tables(scores)
    pairwise_validation = validation_tables(scores)
    coefs, perf, vifs = model_tables(scores)

    qc_columns.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_qc_columns.csv", index=False, encoding="utf-8-sig")
    qc_summary.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_qc_summary.csv", index=False, encoding="utf-8-sig")
    impute.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_imputation_summary.csv", index=False, encoding="utf-8-sig")
    scale.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_scaling_summary.csv", index=False, encoding="utf-8-sig")
    corr.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_correlations.csv", encoding="utf-8-sig")
    pmat.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_correlation_pvalues.csv", encoding="utf-8-sig")
    pairwise_validation.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_biological_validation_pairwise_z.csv", index=False, encoding="utf-8-sig")
    coefs.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_model_coefficients.csv", index=False, encoding="utf-8-sig")
    perf.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_model_performance.csv", index=False, encoding="utf-8-sig")
    vifs.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_model_vif.csv", index=False, encoding="utf-8-sig")

    deliver_cols = [c for c in ["ID", "Age", "Sex", "AL", "SE", "Age_model", "Age_z", "Sex_model"] if c in scores]
    for module in ACTIVE_MODULE_KEYS:
        score = MODULES[module]["score"]
        deliver_cols.extend([f"{score}_raw", score, f"{score}_z"])
    scores[deliver_cols].to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_scores_model_dataset.csv", index=False, encoding="utf-8-sig")

    save_correlation_heatmap(corr, OUTPUT_DIR / f"{OUTPUT_PREFIX}_module_correlation_heatmap.png")
    for i, m1 in enumerate(ACTIVE_MODULE_KEYS):
        for m2 in ACTIVE_MODULE_KEYS[i + 1 :]:
            save_bland_altman(scores, OUTPUT_DIR / f"{OUTPUT_PREFIX}_bland_altman_{m1.lower()}_vs_{m2.lower()}_z.png", m1, m2)

    manifest = {
        "input_csv": str(INPUT_CSV),
        "output_dir": str(OUTPUT_DIR),
        "n_rows": int(df.shape[0]),
        "n_columns": int(df.shape[1]),
        "module_column_counts": {m: len(cols) for m, cols in module_cols.items()},
        "module_retained_counts": {m: len(cols) for m, cols in retained.items()},
        "sex_levels_detected": [str(x) for x in sex_levels],
        "active_module_keys": ACTIVE_MODULE_KEYS,
        "excluded_from_final_modules": ["CFA"],
        "outputs": sorted(p.name for p in OUTPUT_DIR.glob(f"{OUTPUT_PREFIX}_*")),
        "warnings": warnings,
    }
    (OUTPUT_DIR / f"{OUTPUT_PREFIX}_run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    write_report(
        df=df,
        qc_summary=qc_summary,
        impute=impute,
        scale=scale,
        corr=corr,
        pairwise_validation=pairwise_validation,
        coefs=coefs,
        perf=perf,
        vifs=vifs,
        warnings=warnings,
    )
    manifest["outputs"] = sorted(p.name for p in OUTPUT_DIR.glob(f"{OUTPUT_PREFIX}_*"))
    (OUTPUT_DIR / f"{OUTPUT_PREFIX}_run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
