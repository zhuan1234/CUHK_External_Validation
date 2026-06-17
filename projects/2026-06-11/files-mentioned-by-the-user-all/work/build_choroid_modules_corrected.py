import csv
import math
import re
from pathlib import Path

import pandas as pd


BASE = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs"
)
RECORD = BASE / "CUHK_Record_260612_cleaned_with_raw_Cho.csv"
FEATURES = BASE / "choroid_quantize_module_features.csv"
OUTPUT = BASE / "CUHK_Record_260612_choroid_module_ready_corrected.csv"
MAPPING = BASE / "choroid_module_segmentation_mapping_corrected.csv"


def to_numeric(frame, columns):
    return [col for col in columns if col in frame.columns]


def zscore_columns(frame, columns):
    z_cols = []
    for col in to_numeric(frame, columns):
        z_col = f"z_{col}"
        values = pd.to_numeric(frame[col], errors="coerce")
        sd = values.std(ddof=1)
        if not sd or pd.isna(sd):
            frame[z_col] = pd.NA
        else:
            frame[z_col] = (values - values.mean()) / sd
        z_cols.append(z_col)
    return z_cols


def add_module_score(frame, score_col, columns):
    z_cols = zscore_columns(frame, columns)
    if not z_cols:
        frame[score_col] = pd.NA
        return
    frame[score_col] = frame[z_cols].mean(axis=1, skipna=True)
    frame.loc[frame[z_cols].isna().all(axis=1), score_col] = pd.NA


record = pd.read_csv(RECORD, dtype=str, encoding="utf-8-sig")
features = pd.read_csv(FEATURES, dtype=str, encoding="utf-8-sig")

record["record_key"] = (
    record["DOB"].astype(str).str.replace(r"\.0$", "", regex=True)
    + "_"
    + record["Sex"].astype(str)
)

copied_features = features[features["quantize_status"].eq("copied")].copy()
key_counts = copied_features["quantize_key"].value_counts()
unique_features = copied_features[copied_features["quantize_key"].map(key_counts).eq(1)].copy()
duplicate_keys = set(key_counts[key_counts > 1].index)

merged = record.merge(
    unique_features.drop(columns=["DOB", "Sex"], errors="ignore"),
    how="left",
    left_on="record_key",
    right_on="quantize_key",
)
merged["quantize_merge_status"] = "matched_unique"
merged.loc[merged["quantize_key"].isna(), "quantize_merge_status"] = "no_unique_match"
merged.loc[
    merged["record_key"].isin(duplicate_keys), "quantize_merge_status"
] = "duplicate_DOB_Sex_needs_manual_match"

# raw Cho is treated here as choroidal vascular morphology, not retinal.
add_module_score(merged, "cho_raw_density_score_z", ["VAD", "VSD"])
add_module_score(
    merged,
    "cho_raw_regional_density_score_z",
    [
        "VAD_macula",
        "VAD_other",
        "VAD_S",
        "VAD_I",
        "VAD_N",
        "VAD_T",
        "VSD_macula",
        "VSD_other",
        "VSD_S",
        "VSD_I",
        "VSD_N",
        "VSD_T",
    ],
)
add_module_score(
    merged,
    "cho_raw_caliber_width_score_z",
    ["W_mean_mean", "W_max_mean", "W_min_mean", "W_std_mean", "W_range_mean"],
)
add_module_score(
    merged,
    "cho_raw_tortuosity_score_z",
    [
        "Tortuosity_mean",
        "FDtort_mean",
        "curvtort_mean",
        "twistort_mean",
        "LRtort_mean",
        "angtort_mean",
    ],
)
add_module_score(
    merged,
    "cho_raw_branching_tree_score_z",
    ["N_tree", "N_seg", "N_br", "N_bi", "N_termi0", "N_termi1", "br_den", "bi_den"],
)
add_module_score(
    merged,
    "cho_raw_geometry_score_z",
    [
        "AA_mean",
        "AA_e_mean",
        "Arc_mean",
        "CA_mean",
        "BA_mean",
        "BA_e_mean",
        "SA_mean",
        "chord_mean",
        "ang_m_mean",
        "ang_std_mean",
        "ang_range_mean",
    ],
)
add_module_score(
    merged,
    "cho_raw_topology_hierarchy_score_z",
    ["level_mean", "LDR_mean", "Strahler_mean", "BC_mean", "JED_mean"],
)

# Quantize modules from GRID3mm*3mm.
add_module_score(
    merged,
    "cho_quantize_perfusion_area_score_z",
    [
        "cc_flow_area_block1_mean",
        "choroid_flow_area_block1_mean",
        "cc_flow_area_block2_mean",
        "choroid_flow_area_block2_mean",
    ],
)
add_module_score(merged, "cho_quantize_thickness_score_z", ["choroid_thickness_block1_mean"])
add_module_score(merged, "cho_quantize_vascular_index_score_z", ["csi_block1_mean", "cvi_block1_mean"])
add_module_score(merged, "cho_quantize_vascular_volume_score_z", ["csv_block1_mean", "cvv_block1_mean"])

raw_score_cols = [
    "cho_raw_density_score_z",
    "cho_raw_regional_density_score_z",
    "cho_raw_caliber_width_score_z",
    "cho_raw_tortuosity_score_z",
    "cho_raw_branching_tree_score_z",
    "cho_raw_geometry_score_z",
    "cho_raw_topology_hierarchy_score_z",
]
quantize_score_cols = [
    "cho_quantize_perfusion_area_score_z",
    "cho_quantize_thickness_score_z",
    "cho_quantize_vascular_index_score_z",
    "cho_quantize_vascular_volume_score_z",
]
merged["cho_raw_composite_score_z"] = merged[raw_score_cols].apply(
    pd.to_numeric, errors="coerce"
).mean(axis=1, skipna=True)
merged["cho_quantize_composite_score_z"] = merged[quantize_score_cols].apply(
    pd.to_numeric, errors="coerce"
).mean(axis=1, skipna=True)
both_source_scores = merged[
    ["cho_raw_composite_score_z", "cho_quantize_composite_score_z"]
].apply(pd.to_numeric, errors="coerce")
merged["cho_overall_composite_score_z"] = both_source_scores.mean(axis=1, skipna=False)

merged.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

mapping_rows = [
    {
        "module_family": "Covariates",
        "module": "Demographic and ocular covariates",
        "source": "CUHK record",
        "variables": "DOB, Sex, Age, Post SE, AL, Study, Study ID",
        "score_column": "",
        "note": "For adjustment/stratification; not included in choroid composite by default.",
    },
    {
        "module_family": "raw Cho choroid",
        "module": "Choroidal vascular density",
        "source": "raw Cho",
        "variables": "VAD, VSD",
        "score_column": "cho_raw_density_score_z",
        "note": "Global choroidal vascular density/perfusion indicators.",
    },
    {
        "module_family": "raw Cho choroid",
        "module": "Regional choroidal vascular density",
        "source": "raw Cho",
        "variables": "VAD/VSD macula, other, S, I, N, T",
        "score_column": "cho_raw_regional_density_score_z",
        "note": "Regional density distribution across macula/other/quadrants.",
    },
    {
        "module_family": "raw Cho choroid",
        "module": "Choroidal vessel caliber/width",
        "source": "raw Cho",
        "variables": "W_mean, W_max, W_min, W_std, W_range",
        "score_column": "cho_raw_caliber_width_score_z",
        "note": "Width/caliber distribution of choroidal vessels.",
    },
    {
        "module_family": "raw Cho choroid",
        "module": "Choroidal vessel tortuosity",
        "source": "raw Cho",
        "variables": "Tortuosity, FDtort, curvtort, twistort, LRtort, angtort",
        "score_column": "cho_raw_tortuosity_score_z",
        "note": "Curvature and tortuosity morphology.",
    },
    {
        "module_family": "raw Cho choroid",
        "module": "Choroidal branching/tree complexity",
        "source": "raw Cho",
        "variables": "N_tree, N_seg, N_br, N_bi, N_termi0/1, br_den, bi_den",
        "score_column": "cho_raw_branching_tree_score_z",
        "note": "Vascular tree size, branches, bifurcations, terminals.",
    },
    {
        "module_family": "raw Cho choroid",
        "module": "Choroidal geometric architecture",
        "source": "raw Cho",
        "variables": "AA, AA_e, Arc, CA, BA, BA_e, SA, chord, angular metrics",
        "score_column": "cho_raw_geometry_score_z",
        "note": "Angular, arc, chord, and geometric descriptors.",
    },
    {
        "module_family": "raw Cho choroid",
        "module": "Choroidal topology/hierarchy",
        "source": "raw Cho",
        "variables": "level, LDR, Strahler, BC, JED",
        "score_column": "cho_raw_topology_hierarchy_score_z",
        "note": "Hierarchical/topological vascular descriptors.",
    },
    {
        "module_family": "Quantize choroid GRID3mm*3mm",
        "module": "Choroid/choriocapillaris perfusion area",
        "source": "Quantize",
        "variables": "Choriocapillaris Flow Area block1/block2; Choroid Flow Area block1/block2",
        "score_column": "cho_quantize_perfusion_area_score_z",
        "note": "63 valid grid values per indicator row summarized before scoring.",
    },
    {
        "module_family": "Quantize choroid GRID3mm*3mm",
        "module": "Choroid thickness",
        "source": "Quantize",
        "variables": "Choroid Thickness",
        "score_column": "cho_quantize_thickness_score_z",
        "note": "Structural thickness module.",
    },
    {
        "module_family": "Quantize choroid GRID3mm*3mm",
        "module": "Choroid vascular index",
        "source": "Quantize",
        "variables": "CSI, CVI",
        "score_column": "cho_quantize_vascular_index_score_z",
        "note": "Dimensionless choroidal vascular indices.",
    },
    {
        "module_family": "Quantize choroid GRID3mm*3mm",
        "module": "Choroid vascular volume",
        "source": "Quantize",
        "variables": "CSV, CVV",
        "score_column": "cho_quantize_vascular_volume_score_z",
        "note": "Volume-type choroidal vascular metrics.",
    },
    {
        "module_family": "Composite",
        "module": "raw Cho choroid composite",
        "source": "raw Cho",
        "variables": "All raw Cho choroid module scores",
        "score_column": "cho_raw_composite_score_z",
        "note": "Mean of raw Cho choroid module z-scores.",
    },
    {
        "module_family": "Composite",
        "module": "Quantize choroid composite",
        "source": "Quantize",
        "variables": "All Quantize choroid module scores",
        "score_column": "cho_quantize_composite_score_z",
        "note": "Mean of Quantize choroid module z-scores.",
    },
    {
        "module_family": "Composite",
        "module": "Overall choroid composite",
        "source": "raw Cho + Quantize",
        "variables": "raw Cho composite + Quantize composite",
        "score_column": "cho_overall_composite_score_z",
        "note": "Balanced average of the two source-level composites; available only where source modules exist.",
    },
]
pd.DataFrame(mapping_rows).to_csv(MAPPING, index=False, encoding="utf-8-sig")

score_cols = [c for c in merged.columns if c.startswith("cho_") and c.endswith("_score_z")]
summary = {
    "output": str(OUTPUT),
    "mapping": str(MAPPING),
    "rows": int(len(merged)),
    "score_columns": score_cols,
    "score_nonnull_counts": {
        c: int(pd.to_numeric(merged[c], errors="coerce").notna().sum()) for c in score_cols
    },
    "merge_status": merged["quantize_merge_status"].value_counts(dropna=False).to_dict(),
}
print(summary)
