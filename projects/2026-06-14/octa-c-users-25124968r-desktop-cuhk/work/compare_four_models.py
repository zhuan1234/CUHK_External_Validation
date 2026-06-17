from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


OUTPUT_DIR = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-14\octa-c-users-25124968r-desktop-cuhk\outputs"
)
OCTA_SCORES = OUTPUT_DIR / "octa_3module_module_scores_model_dataset.csv"
CHO_SCORES = OUTPUT_DIR / "cho_module_scores_model_dataset.csv"
OUTPUT_PREFIX = "four_model"

IQR_TOL = 1e-8
RANDOM_SEED = 614
N_SPLITS = 5
N_REPEATS = 100
BOOTSTRAP_N = 2000

OCTA_MODULES = ["CCFA_median", "CT_median", "CVI_median"]
OCTA_NONFLOW_MODULES = ["CT_median", "CVI_median"]
CHO_MODULES = [
    "Density_module_median",
    "Complexity_module_median",
    "Calibre_module_median",
    "Tortuosity_module_median",
    "Branching_Angle_module_median",
]

MODEL_SPECS = {
    "Model 1 Clinical": [],
    "Model 2 Clinical+OCTA": OCTA_MODULES,
    "Model 3 Clinical+Cho": CHO_MODULES,
    "Model 4 Clinical+OCTA+Cho": OCTA_MODULES + CHO_MODULES,
    "Model 5 Clinical+OCTA_nonflow": OCTA_NONFLOW_MODULES,
}

BINARY_ENDPOINTS = {
    "AL >= 26mm": {
        "definition": "AL >= 26 mm",
        "positive_label": "long_axial_length",
        "fn": lambda frame: (frame["AL"] >= 26.00).astype(int),
    },
    "Any myopia": {
        "definition": "SE <= -0.50 D",
        "positive_label": "myopia",
        "fn": lambda frame: (frame["SE"] <= -0.50).astype(int),
    },
    "High myopia": {
        "definition": "SE <= -6.00 D",
        "positive_label": "high_myopia",
        "fn": lambda frame: (frame["SE"] <= -6.00).astype(int),
    },
    "Moderate myopia one-vs-rest": {
        "definition": "-6.00 D < SE <= -0.50 D",
        "positive_label": "moderate_myopia",
        "fn": lambda frame: ((frame["SE"] > -6.00) & (frame["SE"] <= -0.50)).astype(int),
    },
}


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


def sample_z(series: pd.Series) -> tuple[pd.Series, float, float]:
    mean = float(series.mean())
    sd = float(series.std(ddof=1))
    if not math.isfinite(sd) or abs(sd) <= IQR_TOL:
        return pd.Series(0.0, index=series.index), mean, sd
    return (series - mean) / sd, mean, sd


def sorted_levels(series: pd.Series) -> list:
    vals = [v for v in series.dropna().unique().tolist()]
    try:
        return sorted(vals)
    except TypeError:
        return sorted(vals, key=lambda x: str(x))


def load_merged_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    octa = pd.read_csv(OCTA_SCORES)
    cho = pd.read_csv(CHO_SCORES)
    octa["ID"] = octa["ID"].astype(str)
    cho["ID"] = cho["ID"].astype(str)

    clinical = octa[["ID", "Age", "Sex", "AL", "SE"]].copy()
    clinical = clinical.rename(columns={"Age": "Age_canonical", "Sex": "Sex_canonical"})

    sex_check = clinical.merge(cho[["ID", "Sex"]].rename(columns={"Sex": "Sex_cho"}), on="ID", how="inner")
    sex_mismatch = sex_check[
        to_numeric_series(sex_check["Sex_canonical"]) != to_numeric_series(sex_check["Sex_cho"])
    ].copy()

    octa_keep = octa[["ID"] + OCTA_MODULES].copy()
    cho_keep = cho[["ID"] + CHO_MODULES].copy()
    merged = clinical.merge(octa_keep, on="ID", how="inner").merge(cho_keep, on="ID", how="inner")
    for col in ["Age_canonical", "Sex_canonical", "AL", "SE"] + OCTA_MODULES + CHO_MODULES:
        merged[col] = to_numeric_series(merged[col])
    return merged, sex_mismatch


def design_matrix(
    frame: pd.DataFrame,
    module_cols: list[str],
    params: dict | None = None,
    fit_params: bool = False,
):
    if fit_params:
        params = {}
    assert params is not None

    out = pd.DataFrame(index=frame.index)
    out["Intercept"] = 1.0
    continuous_cols = ["Age_canonical"] + module_cols
    for col in continuous_cols:
        values = to_numeric_series(frame[col])
        if fit_params:
            median = float(values.median(skipna=True))
            filled = values.fillna(median)
            mean = float(filled.mean())
            sd = float(filled.std(ddof=1))
            params[col] = {"median": median, "mean": mean, "sd": sd}
        cfg = params[col]
        filled = values.fillna(cfg["median"])
        out[f"{col}_z"] = 0.0 if abs(cfg["sd"]) <= IQR_TOL else (filled - cfg["mean"]) / cfg["sd"]

    sex = frame["Sex_canonical"].copy()
    if fit_params:
        levels = sorted_levels(sex)
        mode = sex.mode(dropna=True)
        fill = mode.iloc[0] if not mode.empty else (levels[0] if levels else 0)
        params["Sex_canonical"] = {"levels": levels, "fill": fill}
    cfg = params["Sex_canonical"]
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


def make_repeated_folds(n: int) -> list[list[np.ndarray]]:
    rng = np.random.default_rng(RANDOM_SEED)
    repeats = []
    for _ in range(N_REPEATS):
        idx = np.arange(n)
        rng.shuffle(idx)
        repeats.append(np.array_split(idx, N_SPLITS))
    return repeats


def repeated_cv_predictions(frame: pd.DataFrame, outcome: str, module_cols: list[str], folds) -> tuple[np.ndarray, dict]:
    data = frame.loc[frame[outcome].notna()].copy().reset_index(drop=True)
    y_all = data[outcome].to_numpy(dtype=float)
    n = len(data)
    all_pred = np.empty((len(folds), n))
    all_pred[:] = np.nan
    r2s, rmses, maes = [], [], []
    for r, split in enumerate(folds):
        pred = np.empty(n)
        pred[:] = np.nan
        for test_pos in split:
            train_pos = np.setdiff1d(np.arange(n), test_pos, assume_unique=False)
            train = data.iloc[train_pos]
            test = data.iloc[test_pos]
            x_train, params = design_matrix(train, module_cols=module_cols, fit_params=True)
            x_test, _ = design_matrix(test, module_cols=module_cols, params=params)
            model = fit_ols(train[outcome], x_train)
            pred[test_pos] = x_test.to_numpy(dtype=float) @ model["beta"]
        all_pred[r, :] = pred
        sse = float(np.sum((y_all - pred) ** 2))
        sst = float(np.sum((y_all - np.mean(y_all)) ** 2))
        r2s.append(1 - sse / sst if sst > 0 else np.nan)
        rmses.append(float(np.sqrt(np.mean((y_all - pred) ** 2))))
        maes.append(float(np.mean(np.abs(y_all - pred))))
    return all_pred.mean(axis=0), {
        "cv_r2_mean": float(np.nanmean(r2s)),
        "cv_r2_sd": float(np.nanstd(r2s, ddof=1)),
        "cv_rmse_mean": float(np.nanmean(rmses)),
        "cv_rmse_sd": float(np.nanstd(rmses, ddof=1)),
        "cv_mae_mean": float(np.nanmean(maes)),
        "cv_mae_sd": float(np.nanstd(maes, ddof=1)),
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


def nested_f_test(reduced: dict, full: dict) -> tuple[float, float, int]:
    df_diff = full["k"] - reduced["k"]
    if df_diff <= 0 or full["df_resid"] <= 0:
        return np.nan, np.nan, df_diff
    f_stat = ((reduced["sse"] - full["sse"]) / df_diff) / (full["sse"] / full["df_resid"])
    return float(f_stat), float(f_survival(f_stat, df_diff, full["df_resid"])), df_diff


def auc_roc(y_true: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y_true, dtype=int)
    s = np.asarray(score, dtype=float)
    mask = np.isfinite(s)
    y = y[mask]
    s = s[mask]
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))
    if n_pos == 0 or n_neg == 0:
        return np.nan
    order = np.argsort(s)
    ranks = np.empty(len(s), dtype=float)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i + 1
        while j < len(s) and sorted_s[j] == sorted_s[i]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        ranks[order[i:j]] = avg_rank
        i = j
    sum_pos = float(np.sum(ranks[y == 1]))
    return (sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def sigmoid_stable(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    out = np.empty_like(x)
    pos = x >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    exp_x = np.exp(x[~pos])
    out[~pos] = exp_x / (1.0 + exp_x)
    return np.clip(out, 1e-8, 1 - 1e-8)


def fit_logistic(y: pd.Series | np.ndarray, x: pd.DataFrame, ridge: float = 1e-5) -> dict:
    yv = np.asarray(y, dtype=float)
    xv = x.to_numpy(dtype=float)
    n, k = xv.shape
    beta = np.zeros(k, dtype=float)
    if 0 < yv.mean() < 1:
        beta[0] = math.log(yv.mean() / (1 - yv.mean()))
    penalty = np.eye(k) * ridge
    penalty[0, 0] = 0.0
    converged = False
    for iteration in range(100):
        eta = xv @ beta
        p = sigmoid_stable(eta)
        w = np.clip(p * (1 - p), 1e-6, None)
        grad = xv.T @ (yv - p) - penalty @ beta
        hess = (xv.T * w) @ xv + penalty
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.pinv(hess) @ grad
        beta_new = beta + step
        if float(np.max(np.abs(step))) < 1e-7:
            beta = beta_new
            converged = True
            break
        beta = beta_new
    prob = sigmoid_stable(xv @ beta)
    loglik = float(np.sum(yv * np.log(prob) + (1 - yv) * np.log(1 - prob)))
    return {
        "n": n,
        "k": k,
        "beta": beta,
        "prob": prob,
        "loglik": loglik,
        "auc": auc_roc(yv, prob),
        "brier": float(np.mean((yv - prob) ** 2)),
        "columns": list(x.columns),
        "condition_number": float(np.linalg.cond(xv)),
        "converged": converged,
        "iterations": iteration + 1,
    }


def repeated_cv_probabilities(frame: pd.DataFrame, y: pd.Series, module_cols: list[str], folds) -> tuple[np.ndarray, dict]:
    data = frame.reset_index(drop=True)
    y_all = np.asarray(y, dtype=int)
    n = len(data)
    all_prob = np.empty((len(folds), n))
    all_prob[:] = np.nan
    aucs, briers = [], []
    for r, split in enumerate(folds):
        prob = np.empty(n)
        prob[:] = np.nan
        for test_pos in split:
            train_pos = np.setdiff1d(np.arange(n), test_pos, assume_unique=False)
            train = data.iloc[train_pos]
            test = data.iloc[test_pos]
            y_train = y_all[train_pos]
            if len(np.unique(y_train)) < 2:
                prob[test_pos] = float(np.mean(y_train))
                continue
            x_train, params = design_matrix(train, module_cols=module_cols, fit_params=True)
            x_test, _ = design_matrix(test, module_cols=module_cols, params=params)
            model = fit_logistic(y_train, x_train)
            prob[test_pos] = sigmoid_stable(x_test.to_numpy(dtype=float) @ model["beta"])
        all_prob[r, :] = prob
        aucs.append(auc_roc(y_all, prob))
        briers.append(float(np.mean((y_all - prob) ** 2)))
    mean_prob = np.nanmean(all_prob, axis=0)
    return mean_prob, {
        "cv_auc_mean": float(np.nanmean(aucs)),
        "cv_auc_sd": float(np.nanstd(aucs, ddof=1)),
        "cv_auc_from_mean_probability": auc_roc(y_all, mean_prob),
        "cv_brier_mean": float(np.nanmean(briers)),
        "cv_brier_sd": float(np.nanstd(briers, ddof=1)),
    }


def bootstrap_auc_difference(y: np.ndarray, score_a: np.ndarray, score_b: np.ndarray, rng: np.random.Generator) -> dict:
    y = np.asarray(y, dtype=int)
    score_a = np.asarray(score_a, dtype=float)
    score_b = np.asarray(score_b, dtype=float)
    observed = auc_roc(y, score_a) - auc_roc(y, score_b)
    diffs = []
    n = len(y)
    for _ in range(BOOTSTRAP_N):
        idx = rng.integers(0, n, size=n)
        if len(np.unique(y[idx])) < 2:
            continue
        diffs.append(auc_roc(y[idx], score_a[idx]) - auc_roc(y[idx], score_b[idx]))
    if not diffs:
        return {"delta_auc": observed, "ci_95_low": np.nan, "ci_95_high": np.nan, "bootstrap_p": np.nan}
    arr = np.asarray(diffs)
    p = 2 * min(float(np.mean(arr <= 0)), float(np.mean(arr >= 0)))
    return {
        "delta_auc": observed,
        "ci_95_low": float(np.quantile(arr, 0.025)),
        "ci_95_high": float(np.quantile(arr, 0.975)),
        "bootstrap_p": min(1.0, p),
    }


def df_to_md(df: pd.DataFrame) -> str:
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


def build_tables(frame: pd.DataFrame):
    perf_rows = []
    coef_rows = []
    nested_rows = []
    vif_rows = []
    prediction_rows = []
    folds = make_repeated_folds(len(frame))

    for outcome in ["AL", "SE"]:
        fitted_models = {}
        for model_name, module_cols in MODEL_SPECS.items():
            data = frame.loc[frame[outcome].notna()].copy().reset_index(drop=True)
            x, _ = design_matrix(data, module_cols=module_cols, fit_params=True)
            model = fit_ols(data[outcome], x)
            fitted_models[model_name] = model
            cv_pred, cv = repeated_cv_predictions(data, outcome, module_cols, folds)
            perf_rows.append(
                {
                    "outcome": outcome,
                    "model": model_name,
                    "n": model["n"],
                    "predictor_count_including_intercept": model["k"],
                    "r2": model["r2"],
                    "adj_r2": model["adj_r2"],
                    "rmse": model["rmse"],
                    "mae": model["mae"],
                    **cv,
                    "condition_number": model["condition_number"],
                }
            )
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
            pred_frame = pd.DataFrame(
                {
                    "ID": data["ID"],
                    "outcome": outcome,
                    "model": model_name,
                    "observed": data[outcome],
                    "fitted_in_sample": model["fitted"],
                    "cv_prediction_mean_over_repeats": cv_pred,
                }
            )
            prediction_rows.append(pred_frame)

        comparisons = [
            ("Model 2 vs Model 1", "Model 1 Clinical", "Model 2 Clinical+OCTA"),
            ("Model 3 vs Model 1", "Model 1 Clinical", "Model 3 Clinical+Cho"),
            ("Model 4 vs Model 1", "Model 1 Clinical", "Model 4 Clinical+OCTA+Cho"),
            ("Model 5 vs Model 1", "Model 1 Clinical", "Model 5 Clinical+OCTA_nonflow"),
            ("Model 2 vs Model 5: add OCTA flow beyond nonflow", "Model 5 Clinical+OCTA_nonflow", "Model 2 Clinical+OCTA"),
            ("Model 4 vs Model 2: add Cho beyond OCTA", "Model 2 Clinical+OCTA", "Model 4 Clinical+OCTA+Cho"),
            ("Model 4 vs Model 3: add OCTA beyond Cho", "Model 3 Clinical+Cho", "Model 4 Clinical+OCTA+Cho"),
        ]
        for label, reduced_name, full_name in comparisons:
            reduced = fitted_models[reduced_name]
            full = fitted_models[full_name]
            f_stat, p_value, df_diff = nested_f_test(reduced, full)
            nested_rows.append(
                {
                    "outcome": outcome,
                    "comparison": label,
                    "reduced_model": reduced_name,
                    "full_model": full_name,
                    "df_added": df_diff,
                    "delta_r2": full["r2"] - reduced["r2"],
                    "delta_adj_r2": full["adj_r2"] - reduced["adj_r2"],
                    "partial_f": f_stat,
                    "partial_f_p": p_value,
                }
            )
        x4, _ = design_matrix(frame.loc[frame[outcome].notna()].reset_index(drop=True), MODEL_SPECS["Model 4 Clinical+OCTA+Cho"], fit_params=True)
        vifs = vif_table(x4)
        vifs.insert(0, "outcome", outcome)
        vifs.insert(1, "model", "Model 4 Clinical+OCTA+Cho")
        vif_rows.append(vifs)

    return (
        pd.DataFrame(perf_rows),
        pd.DataFrame(coef_rows),
        pd.DataFrame(nested_rows),
        pd.concat(vif_rows, ignore_index=True),
        pd.concat(prediction_rows, ignore_index=True),
    )


def build_auc_tables(frame: pd.DataFrame):
    folds = make_repeated_folds(len(frame))
    auc_rows = []
    prediction_frames = []
    diff_rows = []
    rng = np.random.default_rng(RANDOM_SEED + 991)

    for endpoint_name, cfg in BINARY_ENDPOINTS.items():
        y = cfg["fn"](frame).astype(int).to_numpy()
        events = int(np.sum(y == 1))
        controls = int(np.sum(y == 0))
        model_prob: dict[str, np.ndarray] = {}
        model_in_sample_prob: dict[str, np.ndarray] = {}
        for model_name, module_cols in MODEL_SPECS.items():
            x, _ = design_matrix(frame, module_cols=module_cols, fit_params=True)
            if events == 0 or controls == 0:
                logistic = {
                    "auc": np.nan,
                    "brier": np.nan,
                    "condition_number": float(np.linalg.cond(x.to_numpy(dtype=float))),
                    "converged": False,
                    "iterations": 0,
                    "prob": np.full(len(frame), np.nan),
                }
                cv = {
                    "cv_auc_mean": np.nan,
                    "cv_auc_sd": np.nan,
                    "cv_auc_from_mean_probability": np.nan,
                    "cv_brier_mean": np.nan,
                    "cv_brier_sd": np.nan,
                }
                cv_prob = np.full(len(frame), np.nan)
            else:
                logistic = fit_logistic(y, x)
                cv_prob, cv = repeated_cv_probabilities(frame, pd.Series(y), module_cols, folds)
            model_prob[model_name] = cv_prob
            model_in_sample_prob[model_name] = logistic["prob"]
            auc_rows.append(
                {
                    "endpoint": endpoint_name,
                    "definition": cfg["definition"],
                    "model": model_name,
                    "n": int(len(frame)),
                    "events": events,
                    "controls": controls,
                    "event_rate": events / len(frame),
                    "in_sample_auc": logistic["auc"],
                    "in_sample_brier": logistic["brier"],
                    **cv,
                    "condition_number": logistic["condition_number"],
                    "logistic_converged": logistic["converged"],
                    "logistic_iterations": logistic["iterations"],
                }
            )
            prediction_frames.append(
                pd.DataFrame(
                    {
                        "ID": frame["ID"],
                        "endpoint": endpoint_name,
                        "definition": cfg["definition"],
                        "event": y,
                        "model": model_name,
                        "in_sample_probability": logistic["prob"],
                        "cv_probability_mean_over_repeats": cv_prob,
                    }
                )
            )

        pairs = [
            ("Model 2 vs Model 1", "Model 2 Clinical+OCTA", "Model 1 Clinical"),
            ("Model 3 vs Model 1", "Model 3 Clinical+Cho", "Model 1 Clinical"),
            ("Model 5 vs Model 1", "Model 5 Clinical+OCTA_nonflow", "Model 1 Clinical"),
            ("Model 3 vs Model 2: Cho minus OCTA", "Model 3 Clinical+Cho", "Model 2 Clinical+OCTA"),
            ("Model 3 vs Model 5: Cho minus OCTA_nonflow", "Model 3 Clinical+Cho", "Model 5 Clinical+OCTA_nonflow"),
            ("Model 2 vs Model 5: OCTA flow contribution", "Model 2 Clinical+OCTA", "Model 5 Clinical+OCTA_nonflow"),
            ("Model 4 vs Model 1", "Model 4 Clinical+OCTA+Cho", "Model 1 Clinical"),
            ("Model 4 vs Model 2: add Cho beyond OCTA", "Model 4 Clinical+OCTA+Cho", "Model 2 Clinical+OCTA"),
            ("Model 4 vs Model 3: add OCTA beyond Cho", "Model 4 Clinical+OCTA+Cho", "Model 3 Clinical+Cho"),
            ("Model 4 vs Model 5: add flow+Cho beyond OCTA_nonflow", "Model 4 Clinical+OCTA+Cho", "Model 5 Clinical+OCTA_nonflow"),
        ]
        for label, model_a, model_b in pairs:
            if events == 0 or controls == 0:
                cv_diff = {"delta_auc": np.nan, "ci_95_low": np.nan, "ci_95_high": np.nan, "bootstrap_p": np.nan}
                ins_diff = {"delta_auc": np.nan, "ci_95_low": np.nan, "ci_95_high": np.nan, "bootstrap_p": np.nan}
            else:
                cv_diff = bootstrap_auc_difference(y, model_prob[model_a], model_prob[model_b], rng)
                ins_diff = bootstrap_auc_difference(y, model_in_sample_prob[model_a], model_in_sample_prob[model_b], rng)
            diff_rows.append(
                {
                    "endpoint": endpoint_name,
                    "definition": cfg["definition"],
                    "comparison": label,
                    "model_a": model_a,
                    "model_b": model_b,
                    "events": events,
                    "controls": controls,
                    "cv_delta_auc_model_a_minus_b": cv_diff["delta_auc"],
                    "cv_delta_auc_ci_95_low": cv_diff["ci_95_low"],
                    "cv_delta_auc_ci_95_high": cv_diff["ci_95_high"],
                    "cv_delta_auc_bootstrap_p": cv_diff["bootstrap_p"],
                    "in_sample_delta_auc_model_a_minus_b": ins_diff["delta_auc"],
                    "in_sample_delta_auc_ci_95_low": ins_diff["ci_95_low"],
                    "in_sample_delta_auc_ci_95_high": ins_diff["ci_95_high"],
                    "in_sample_delta_auc_bootstrap_p": ins_diff["bootstrap_p"],
                }
            )
    return (
        pd.DataFrame(auc_rows),
        pd.DataFrame(diff_rows),
        pd.concat(prediction_frames, ignore_index=True),
    )


def write_report(
    perf: pd.DataFrame,
    nested: pd.DataFrame,
    auc_perf: pd.DataFrame,
    auc_diff: pd.DataFrame,
    sex_mismatch: pd.DataFrame,
    frame: pd.DataFrame,
):
    lines = []
    lines.append("# Four-model comparison report")
    lines.append("")
    lines.append(f"Cohort: n={len(frame)}, IDs merged from OCTA and Cho module score datasets.")
    lines.append("Canonical clinical/outcome columns: `Age`, `Sex`, `AL`, `SE` from OCTA module dataset.")
    lines.append("")
    lines.append("## AUC Endpoints")
    lines.append("- Long axial length: `AL >= 26 mm`.")
    lines.append("- Any myopia: `SE <= -0.50 D`.")
    lines.append("- High myopia: `SE <= -6.00 D`.")
    lines.append("- Moderate myopia one-vs-rest: `-6.00 D < SE <= -0.50 D`.")
    lines.append("AUC comparisons use logistic regression probabilities; interpretation should prioritize repeated 5-fold CV AUC.")
    lines.append("Model 5 was added for fair morphology comparison: `Clinical + OCTA_nonflow`, where OCTA_nonflow = `CT + CVI` and excludes flow-related `CCFA`.")
    lines.append("")
    lines.append("## Sex Mismatch Handling")
    lines.append(f"Sex mismatches between OCTA and Cho tables: {len(sex_mismatch)}. Canonical OCTA Sex was used for all four models.")
    if len(sex_mismatch):
        lines.append(df_to_md(sex_mismatch))
    lines.append("")
    lines.append("## Continuous Outcome Performance")
    lines.append(df_to_md(perf))
    lines.append("")
    lines.append("## Nested Model Tests")
    lines.append(df_to_md(nested))
    lines.append("")
    lines.append("## Logistic AUC Performance")
    lines.append(df_to_md(auc_perf))
    lines.append("")
    lines.append("## Paired AUC Differences")
    lines.append(df_to_md(auc_diff))
    lines.append("")
    lines.append("## Interpretation")
    for outcome in ["AL", "SE"]:
        rows = perf[perf["outcome"] == outcome].set_index("model")
        m2 = rows.loc["Model 2 Clinical+OCTA"]
        m3 = rows.loc["Model 3 Clinical+Cho"]
        m4 = rows.loc["Model 4 Clinical+OCTA+Cho"]
        m5 = rows.loc["Model 5 Clinical+OCTA_nonflow"]
        lines.append(
            f"- {outcome}: Cho model in-sample R2 is {m3['r2']:.3f} vs OCTA {m2['r2']:.3f}; "
            f"CV R2 is {m3['cv_r2_mean']:.3f} vs OCTA {m2['cv_r2_mean']:.3f} and OCTA_nonflow {m5['cv_r2_mean']:.3f}. "
            f"Combined model CV R2 is {m4['cv_r2_mean']:.3f}."
        )
    for endpoint in auc_perf["endpoint"].unique():
        rows = auc_perf[auc_perf["endpoint"] == endpoint].set_index("model")
        m2 = rows.loc["Model 2 Clinical+OCTA"]
        m3 = rows.loc["Model 3 Clinical+Cho"]
        m4 = rows.loc["Model 4 Clinical+OCTA+Cho"]
        m5 = rows.loc["Model 5 Clinical+OCTA_nonflow"]
        lines.append(
            f"- {endpoint}: CV AUC Cho={m3['cv_auc_from_mean_probability']:.3f}, "
            f"OCTA={m2['cv_auc_from_mean_probability']:.3f}, "
            f"OCTA_nonflow={m5['cv_auc_from_mean_probability']:.3f}, combined={m4['cv_auc_from_mean_probability']:.3f}."
        )
    (OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    frame, sex_mismatch = load_merged_data()
    perf, coef, nested, vifs, predictions = build_tables(frame)
    auc_perf, auc_diff, auc_predictions = build_auc_tables(frame)

    perf.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_continuous_performance.csv", index=False, encoding="utf-8-sig")
    coef.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_coefficients.csv", index=False, encoding="utf-8-sig")
    nested.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_nested_model_tests.csv", index=False, encoding="utf-8-sig")
    vifs.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_model4_vif.csv", index=False, encoding="utf-8-sig")
    predictions.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_predictions.csv", index=False, encoding="utf-8-sig")
    auc_perf.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_auc_performance.csv", index=False, encoding="utf-8-sig")
    auc_diff.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_auc_pairwise_differences.csv", index=False, encoding="utf-8-sig")
    auc_predictions.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_auc_predictions.csv", index=False, encoding="utf-8-sig")
    sex_mismatch.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_sex_mismatch_octa_vs_cho.csv", index=False, encoding="utf-8-sig")

    manifest = {
        "n": int(len(frame)),
        "id_unique": int(frame["ID"].nunique()),
        "octa_score_file": str(OCTA_SCORES),
        "cho_score_file": str(CHO_SCORES),
        "canonical_clinical_source": "octa_3module_module_scores_model_dataset.csv",
        "sex_mismatch_count": int(len(sex_mismatch)),
        "model_specs": MODEL_SPECS,
        "auc_status": "computed_for_AL_and_SE_binary_endpoints",
        "binary_endpoints": {k: v["definition"] for k, v in BINARY_ENDPOINTS.items()},
        "outputs": sorted(p.name for p in OUTPUT_DIR.glob(f"{OUTPUT_PREFIX}_*")),
    }
    write_report(perf, nested, auc_perf, auc_diff, sex_mismatch, frame)
    manifest["outputs"] = sorted(p.name for p in OUTPUT_DIR.glob(f"{OUTPUT_PREFIX}_*"))
    (OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
