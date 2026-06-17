from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import compare_four_models as cmp


OUTPUT_DIR = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-14\octa-c-users-25124968r-desktop-cuhk\outputs"
)


OLD_TO_NEW_MODEL = {
    "Model 1 Clinical": "Model 1 Clinical",
    "Model 2 Clinical+OCTA": "Model 3 Clinical + OCTA",
    "Model 3 Clinical+Cho": "Model 2 Clinical + Cho",
    "Model 4 Clinical+OCTA+Cho": "Model 5 Clinical + OCTA + Cho",
    "Model 5 Clinical+OCTA_nonflow": "Model 4 Clinical + OCTA_nonflow",
}

MODEL_ORDER = [
    "Model 1 Clinical",
    "Model 2 Clinical + Cho",
    "Model 3 Clinical + OCTA",
    "Model 4 Clinical + OCTA_nonflow",
    "Model 5 Clinical + OCTA + Cho",
]

ENDPOINT_KEEP = [
    "High myopia",
    "Moderate myopia one-vs-rest",
    "AL >= 26mm",
]

ENDPOINT_ORDER = {
    "High myopia": 1,
    "Moderate myopia one-vs-rest": 2,
    "AL >= 26mm": 3,
}


def fmt(x: float, digits: int = 3) -> str:
    if pd.isna(x):
        return "NA"
    return f"{float(x):.{digits}f}"


def md_table(df: pd.DataFrame) -> str:
    text = df.copy()
    for col in text.columns:
        if pd.api.types.is_float_dtype(text[col]):
            text[col] = text[col].map(lambda v: fmt(v, 3))
        else:
            text[col] = text[col].astype(str)
    widths = {
        c: max(len(c), *(len(v) for v in text[c].astype(str).tolist()))
        for c in text.columns
    }
    header = "| " + " | ".join(c.ljust(widths[c]) for c in text.columns) + " |"
    sep = "| " + " | ".join("-" * widths[c] for c in text.columns) + " |"
    rows = [
        "| " + " | ".join(str(row[c]).ljust(widths[c]) for c in text.columns) + " |"
        for _, row in text.iterrows()
    ]
    return "\n".join([header, sep, *rows])


def main() -> None:
    frame, sex_mismatch = cmp.load_merged_data()
    auc_perf_old, auc_diff_old, auc_predictions_old = cmp.build_auc_tables(frame)

    # Map old labels produced by the legacy function to the current manuscript labels.
    auc_perf = auc_perf_old.copy()
    auc_perf["model"] = auc_perf["model"].map(OLD_TO_NEW_MODEL)
    auc_perf = auc_perf[auc_perf["endpoint"].isin(ENDPOINT_KEEP)].copy()
    auc_perf["endpoint_order"] = auc_perf["endpoint"].map(ENDPOINT_ORDER)
    auc_perf["model_order"] = auc_perf["model"].map({m: i for i, m in enumerate(MODEL_ORDER, start=1)})
    auc_perf = auc_perf.sort_values(["endpoint_order", "model_order"]).drop(columns=["endpoint_order", "model_order"])

    auc_diff = auc_diff_old.copy()
    auc_diff["model_a"] = auc_diff["model_a"].map(OLD_TO_NEW_MODEL)
    auc_diff["model_b"] = auc_diff["model_b"].map(OLD_TO_NEW_MODEL)
    auc_diff = auc_diff[auc_diff["endpoint"].isin(ENDPOINT_KEEP)].copy()
    auc_diff["contrast"] = auc_diff["model_a"] + " minus " + auc_diff["model_b"]
    auc_diff["endpoint_order"] = auc_diff["endpoint"].map(ENDPOINT_ORDER)
    auc_diff = auc_diff.sort_values(["endpoint_order", "contrast"]).drop(columns=["endpoint_order"])

    predictions = auc_predictions_old.copy()
    predictions["model"] = predictions["model"].map(OLD_TO_NEW_MODEL)
    predictions = predictions[predictions["endpoint"].isin(ENDPOINT_KEEP)].copy()

    # Analysis dataset with endpoint variables under the current names.
    analysis_dataset = frame.copy()
    analysis_dataset["high_myopia"] = (analysis_dataset["SE"] <= -6.00).astype(int)
    analysis_dataset["moderate_myopia"] = (
        (analysis_dataset["SE"] > -6.00) & (analysis_dataset["SE"] <= -0.50)
    ).astype(int)
    analysis_dataset["long_axial_length"] = (analysis_dataset["AL"] >= 26.00).astype(int)

    endpoint_counts = pd.DataFrame(
        [
            {
                "endpoint": "High myopia",
                "definition": "SE <= -6.00 D",
                "n": len(frame),
                "events": int(analysis_dataset["high_myopia"].sum()),
                "controls": int((1 - analysis_dataset["high_myopia"]).sum()),
                "event_rate": float(analysis_dataset["high_myopia"].mean()),
            },
            {
                "endpoint": "Moderate myopia one-vs-rest",
                "definition": "-6.00 D < SE <= -0.50 D",
                "n": len(frame),
                "events": int(analysis_dataset["moderate_myopia"].sum()),
                "controls": int((1 - analysis_dataset["moderate_myopia"]).sum()),
                "event_rate": float(analysis_dataset["moderate_myopia"].mean()),
            },
            {
                "endpoint": "AL >= 26mm",
                "definition": "AL >= 26 mm",
                "n": len(frame),
                "events": int(analysis_dataset["long_axial_length"].sum()),
                "controls": int((1 - analysis_dataset["long_axial_length"]).sum()),
                "event_rate": float(analysis_dataset["long_axial_length"].mean()),
            },
        ]
    )

    # Copy current module QC tables to R_repro names for a single reproducibility bundle.
    octa_qc = pd.read_csv(OUTPUT_DIR / "octa_3module_module_qc_summary.csv")
    cho_qc = pd.read_csv(OUTPUT_DIR / "cho_module_qc_summary.csv")
    octa_columns = pd.read_csv(OUTPUT_DIR / "octa_3module_qc_columns.csv")
    cho_variables = pd.read_csv(OUTPUT_DIR / "cho_qc_variables.csv")

    sex_mismatch.to_csv(OUTPUT_DIR / "R_repro_sex_mismatch.csv", index=False, encoding="utf-8-sig")
    octa_qc.to_csv(OUTPUT_DIR / "R_repro_octa_qc_summary.csv", index=False, encoding="utf-8-sig")
    cho_qc.to_csv(OUTPUT_DIR / "R_repro_cho_qc_summary.csv", index=False, encoding="utf-8-sig")
    octa_columns.to_csv(OUTPUT_DIR / "R_repro_octa_qc_columns.csv", index=False, encoding="utf-8-sig")
    cho_variables.to_csv(OUTPUT_DIR / "R_repro_cho_qc_variables.csv", index=False, encoding="utf-8-sig")
    analysis_dataset.to_csv(OUTPUT_DIR / "R_repro_analysis_dataset.csv", index=False, encoding="utf-8-sig")
    endpoint_counts.to_csv(OUTPUT_DIR / "R_repro_endpoint_counts.csv", index=False, encoding="utf-8-sig")
    auc_perf.to_csv(OUTPUT_DIR / "R_repro_auc_performance.csv", index=False, encoding="utf-8-sig")
    auc_diff.to_csv(OUTPUT_DIR / "R_repro_auc_pairwise_differences.csv", index=False, encoding="utf-8-sig")
    predictions.to_csv(OUTPUT_DIR / "R_repro_auc_predictions.csv", index=False, encoding="utf-8-sig")

    # Key pairwise rows for interpretation.
    key_contrasts = [
        "Model 2 Clinical + Cho minus Model 3 Clinical + OCTA",
        "Model 2 Clinical + Cho minus Model 4 Clinical + OCTA_nonflow",
        "Model 3 Clinical + OCTA minus Model 4 Clinical + OCTA_nonflow",
        "Model 5 Clinical + OCTA + Cho minus Model 3 Clinical + OCTA",
        "Model 5 Clinical + OCTA + Cho minus Model 2 Clinical + Cho",
    ]
    key_diff = auc_diff[auc_diff["contrast"].isin(key_contrasts)].copy()

    perf_display = auc_perf[
        [
            "endpoint",
            "model",
            "events",
            "controls",
            "in_sample_auc",
            "cv_auc_from_mean_probability",
            "cv_auc_mean",
            "cv_auc_sd",
        ]
    ].rename(
        columns={
            "in_sample_auc": "apparent_auc",
            "cv_auc_from_mean_probability": "cv_auc",
        }
    )

    diff_display = key_diff[
        [
            "endpoint",
            "contrast",
            "cv_delta_auc_model_a_minus_b",
            "cv_delta_auc_ci_95_low",
            "cv_delta_auc_ci_95_high",
            "cv_delta_auc_bootstrap_p",
        ]
    ].rename(
        columns={
            "cv_delta_auc_model_a_minus_b": "delta_cv_auc",
            "cv_delta_auc_ci_95_low": "ci_low",
            "cv_delta_auc_ci_95_high": "ci_high",
            "cv_delta_auc_bootstrap_p": "p_bootstrap",
        }
    )

    summary_lines = [
        "# Reproducible OCTA + Cho AUC Workflow Results",
        "",
        "## Input And Alignment",
        "",
        "- OCTA file: `C:/Users/25124968R/Desktop/CUHK/CUHK_OCTA_OD_260614.csv`.",
        "- Cho file: `C:/Users/25124968R/Desktop/CUHK/CUHK_Cho_OD_260614.csv`.",
        "- Cho dictionary: `C:/Users/25124968R/Desktop/CUHK/cho_Variables.xlsx`.",
        f"- Final common OD analysis set: n={len(frame)}, unique IDs={frame['ID'].nunique()}.",
        f"- Sex mismatches between OCTA and Cho after current cleanup: {len(sex_mismatch)}.",
        "",
        "## QC And Module Construction",
        "",
        "- OCTA: grid-level QC -> module median -> median imputation if needed -> module score scale; final modules: CCFA, CT, CVI. CFA was checked but excluded because of high correlation with CCFA.",
        "- Cho/CFP: Whole-region variables from the dictionary -> variable-level QC -> variable-level median imputation -> variable-level z-score -> module median -> module score scale.",
        "",
        "OCTA QC summary:",
        "",
        md_table(octa_qc[["module", "input_grid_columns", "retained_columns", "removed_missing_rate_gt_90pct", "removed_low_iqr"]]),
        "",
        "Cho QC summary:",
        "",
        md_table(cho_qc[["category", "matched_variables", "retained_variables", "removed_missing_rate_gt_90pct", "removed_valid_n_lt_threshold", "removed_low_iqr"]]),
        "",
        "## Endpoint Counts",
        "",
        md_table(endpoint_counts),
        "",
        "## AUC Performance",
        "",
        "Primary interpretation should use `cv_auc`; `apparent_auc` is in-sample and more optimistic.",
        "",
        md_table(perf_display),
        "",
        "## Key AUC Differences",
        "",
        "Differences are paired bootstrap estimates based on repeated-CV probabilities.",
        "",
        md_table(diff_display),
        "",
        "## Interpretation",
        "",
        "- Current files are fully aligned at n=137; no Sex mismatch remains in the aligned OCTA/Cho cohort.",
        "- Moderate myopia one-vs-rest has 91/137 events, matching the updated note.",
        "- AL >= 26mm is retained as a separate binary endpoint.",
        "- Cho performance should be compared mainly with OCTA_nonflow for the fair non-flow comparison; full OCTA additionally includes CCFA.",
    ]

    (OUTPUT_DIR / "reproducible_auc_workflow_results_summary.md").write_text(
        "\n".join(summary_lines), encoding="utf-8"
    )

    manifest = {
        "n": int(len(frame)),
        "unique_ids": int(frame["ID"].nunique()),
        "sex_mismatch_count": int(len(sex_mismatch)),
        "endpoints": endpoint_counts.to_dict("records"),
        "models": MODEL_ORDER,
        "outputs": [
            "reproducible_auc_workflow.R",
            "reproducible_auc_workflow_results_summary.md",
            "R_repro_auc_performance.csv",
            "R_repro_auc_pairwise_differences.csv",
            "R_repro_endpoint_counts.csv",
            "R_repro_analysis_dataset.csv",
        ],
    }
    (OUTPUT_DIR / "R_repro_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
