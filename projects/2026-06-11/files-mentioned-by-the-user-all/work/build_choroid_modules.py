import csv
import math
import os
import re
from pathlib import Path

import pandas as pd


BASE = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs"
)
MANIFEST = BASE / "CUHK_OCT_OD_Quantize_tables" / "manifest.csv"
RECORD = BASE / "CUHK_Record_260612_cleaned_with_raw_Cho.csv"
QUANTIZE_FEATURES = BASE / "choroid_quantize_module_features.csv"
MODULE_READY = BASE / "CUHK_Record_260612_module_ready.csv"
MODULE_MAP = BASE / "module_segmentation_mapping.csv"

TERMS = [
    ("Choriocapillaris:Choriocapillaris", "Flow Area (mm2)", "cc_flow_area"),
    ("Choroid:Choroid", "Flow Area (mm2)", "choroid_flow_area"),
    ("Choroid:Choroid", "Thickness", "choroid_thickness"),
    ("CSI:CSI", "ChoroidVessel_CSI", "csi"),
    ("CSV:CSV", "ChoroidVessel_CSV", "csv"),
    ("CVI:CVI", "ChoroidVessel_CVI", "cvi"),
    ("CVV:CVV", "ChoroidVessel_CVV", "cvv"),
]
TERM_KEYS = {(layer, measure): short for layer, measure, short in TERMS}


def parse_subject(subject):
    match = re.match(r"^(.*)_([0-9]{8})_([MF])$", str(subject).strip(), flags=re.I)
    if not match:
        return "", "", ""
    return match.group(1), match.group(2), match.group(3).upper()


def read_quantize_rows(path):
    with open(path, "r", encoding="gb18030", errors="replace", newline="") as handle:
        return list(csv.reader(handle))


def as_float(value):
    text = str(value).strip()
    if text in {"", "-"}:
        return math.nan
    try:
        return float(text)
    except ValueError:
        return math.nan


def extract_quantize_features(path):
    rows = read_quantize_rows(path)
    features = {}
    occurrences = {}
    for csv_row, row in enumerate(rows, start=1):
        if len(row) < 7 or row[6].strip() != "GRID3mm*3mm":
            continue
        key = (row[4].strip(), row[5].strip())
        if key not in TERM_KEYS:
            continue
        short = TERM_KEYS[key]
        occurrences[short] = occurrences.get(short, 0) + 1
        suffix = f"{short}_block{occurrences[short]}"
        values = [as_float(value) for value in row[7:]]
        series = pd.Series(values, dtype="float64").dropna()
        features[f"{suffix}_n"] = int(series.shape[0])
        features[f"{suffix}_mean"] = series.mean()
        features[f"{suffix}_median"] = series.median()
        features[f"{suffix}_sd"] = series.std(ddof=1)
        features[f"{suffix}_min"] = series.min()
        features[f"{suffix}_max"] = series.max()
        features[f"{suffix}_source_row"] = csv_row
    return features


def zscore_columns(frame, columns):
    out_cols = []
    for col in columns:
        z_col = f"z_{col}"
        values = pd.to_numeric(frame[col], errors="coerce")
        sd = values.std(ddof=1)
        if not sd or pd.isna(sd):
            frame[z_col] = pd.NA
        else:
            frame[z_col] = (values - values.mean()) / sd
        out_cols.append(z_col)
    return out_cols


def add_module_score(frame, score_col, feature_cols):
    usable = [col for col in feature_cols if col in frame.columns]
    z_cols = zscore_columns(frame, usable)
    frame[score_col] = frame[z_cols].mean(axis=1, skipna=True)
    frame.loc[frame[z_cols].isna().all(axis=1), score_col] = pd.NA


manifest = pd.read_csv(MANIFEST, dtype=str, encoding="utf-8-sig")
feature_rows = []
for _, item in manifest.iterrows():
    name, dob, sex = parse_subject(item["subject"])
    row = {
        "subject": item["subject"],
        "q_name": name,
        "DOB": dob,
        "SexLetter": sex,
        "Sex": {"M": "1", "F": "2"}.get(sex, ""),
        "quantize_status": item["status"],
        "candidate_count": item["candidate_count"],
        "copied_file": item["copied_file"],
        "selection_note": item["selection_note"],
    }
    if item["status"] == "copied" and isinstance(item["copied_file"], str) and item["copied_file"]:
        row.update(extract_quantize_features(item["copied_file"]))
    feature_rows.append(row)

features = pd.DataFrame(feature_rows)
features["quantize_key"] = features["DOB"].astype(str) + "_" + features["Sex"].astype(str)

add_module_score(
    features,
    "choroid_perfusion_area_score_z",
    [
        "cc_flow_area_block1_mean",
        "choroid_flow_area_block1_mean",
        "cc_flow_area_block2_mean",
        "choroid_flow_area_block2_mean",
    ],
)
add_module_score(features, "choroid_thickness_score_z", ["choroid_thickness_block1_mean"])
add_module_score(features, "choroid_vascular_index_score_z", ["csi_block1_mean", "cvi_block1_mean"])
add_module_score(features, "choroid_vascular_volume_score_z", ["csv_block1_mean", "cvv_block1_mean"])

features.to_csv(QUANTIZE_FEATURES, index=False, encoding="utf-8-sig")

record = pd.read_csv(RECORD, dtype=str, encoding="utf-8-sig")
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
    unique_features.drop(columns=["DOB", "Sex"]),
    how="left",
    left_on="record_key",
    right_on="quantize_key",
)
merged["quantize_merge_status"] = "matched_unique"
merged.loc[merged["quantize_key"].isna(), "quantize_merge_status"] = "no_unique_match"
merged.loc[merged["record_key"].isin(duplicate_keys), "quantize_merge_status"] = "duplicate_DOB_Sex_needs_manual_match"

add_module_score(merged, "retinal_density_score_z", ["VAD", "VSD"])
add_module_score(
    merged,
    "retinal_morphology_width_score_z",
    ["W_mean_mean", "W_max_mean", "W_min_mean", "W_std_mean", "W_range_mean"],
)
add_module_score(
    merged,
    "retinal_morphology_tortuosity_score_z",
    ["Tortuosity_mean", "FDtort_mean", "curvtort_mean", "twistort_mean", "LRtort_mean", "angtort_mean"],
)
add_module_score(merged, "retinal_branching_score_z", ["N_tree", "N_seg", "N_br", "N_bi", "N_termi0", "N_termi1"])

merged.to_csv(MODULE_READY, index=False, encoding="utf-8-sig")

mapping_rows = [
    {
        "module": "Demographic and ocular covariates",
        "source": "CUHK record",
        "variables": "DOB, Sex, Age, Post SE, AL, Study, Study ID",
        "role": "Adjustment/covariates; not part of pathology module score by default.",
        "score_column": "",
    },
    {
        "module": "Retinal vessel density",
        "source": "raw Cho",
        "variables": "VAD, VSD and regional VAD/VSD columns",
        "role": "Retinal vascular density/perfusion module; related but not choroidal.",
        "score_column": "retinal_density_score_z",
    },
    {
        "module": "Retinal morphology - width",
        "source": "raw Cho",
        "variables": "W_mean, W_max, W_min, W_std, W_range families",
        "role": "Retinal vessel caliber/width module.",
        "score_column": "retinal_morphology_width_score_z",
    },
    {
        "module": "Retinal morphology - tortuosity",
        "source": "raw Cho",
        "variables": "Tortuosity, FDtort, curvtort, twistort, LRtort, angtort families",
        "role": "Retinal vessel tortuosity module.",
        "score_column": "retinal_morphology_tortuosity_score_z",
    },
    {
        "module": "Retinal branching complexity",
        "source": "raw Cho",
        "variables": "N_tree, N_seg, N_br, N_bi, N_termi0, N_termi1 and branching-related families",
        "role": "Retinal vascular tree/branching module.",
        "score_column": "retinal_branching_score_z",
    },
    {
        "module": "Choroid perfusion area",
        "source": "Quantize GRID3mm*3mm",
        "variables": "Choriocapillaris Flow Area block1/block2; Choroid Flow Area block1/block2",
        "role": "Direct choroidal/choriocapillaris flow-area module; 63 valid grid values per row.",
        "score_column": "choroid_perfusion_area_score_z",
    },
    {
        "module": "Choroid thickness",
        "source": "Quantize GRID3mm*3mm",
        "variables": "Choroid Thickness",
        "role": "Structural choroid module; unit differs from flow and volume.",
        "score_column": "choroid_thickness_score_z",
    },
    {
        "module": "Choroid vascular index",
        "source": "Quantize GRID3mm*3mm",
        "variables": "CSI, CVI",
        "role": "Dimensionless choroid vascular ratio/index module.",
        "score_column": "choroid_vascular_index_score_z",
    },
    {
        "module": "Choroid vascular volume",
        "source": "Quantize GRID3mm*3mm",
        "variables": "CSV, CVV",
        "role": "Choroid vessel/space volume module.",
        "score_column": "choroid_vascular_volume_score_z",
    },
]
pd.DataFrame(mapping_rows).to_csv(MODULE_MAP, index=False, encoding="utf-8-sig")

summary = {
    "quantize_features": str(QUANTIZE_FEATURES),
    "module_ready": str(MODULE_READY),
    "module_mapping": str(MODULE_MAP),
    "record_rows": int(len(record)),
    "quantize_rows": int(len(features)),
    "copied_quantize_rows": int(features["quantize_status"].eq("copied").sum()),
    "matched_unique": int(merged["quantize_merge_status"].eq("matched_unique").sum()),
    "duplicate_needs_manual": int(merged["quantize_merge_status"].eq("duplicate_DOB_Sex_needs_manual_match").sum()),
    "no_unique_match": int(merged["quantize_merge_status"].eq("no_unique_match").sum()),
}
print(summary)
