import csv
import json
import re
from pathlib import Path

import pandas as pd


BASE = Path(r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs")
RECORD = BASE / "CUHK_Record_260612_cleaned_with_raw_Cho.csv"
FIGURE = BASE / "figure1_row_data_counts.csv"
SUMMARY_OUT = BASE / "vascular_module_segmentation_summary.csv"
MAP_OUT = BASE / "raw_Cho_variable_module_map.csv"


def classify_raw_cho_column(col: str):
    if col in {
        "Number",
        "ID",
        "DOB",
        "Sex",
        "Age",
        "Study",
        "Study ID",
        "Post AR",
        "Post SE",
        "AL",
        "imid",
        "Quality",
        "Field",
        "FDt",
        "magf",
        "disc_diameter",
        "disc_angle",
        "ovality_index",
        "macula_source",
        "df_dist",
        "df_angle",
        "6mm_pix",
    }:
        return None

    if re.match(r"^V[AS]D($|_)", col):
        return "Retinal vessel density/perfusion"
    if re.match(r"^(W_|W$)", col) or re.match(r"^W_(std|max|mean|range|min|termi)", col):
        return "Retinal caliber/width"
    if any(token in col for token in ["Tortuosity", "tort", "curvtort", "twistort", "LRtort", "inflectort", "ang_std", "ang_range", "angtort"]):
        return "Retinal tortuosity/angular complexity"
    if re.match(r"^(N_tree|N_seg|N_br|N_bi|N_termi|br_den|bi_den|Strahler|level|LDR)", col):
        return "Retinal branching/topology"
    if re.match(r"^(AA|AA_e|Arc|CA|JED|AR|BA|BA_e|SA|BC|chord|ang_m)", col):
        return "Retinal branching geometry"
    return "Other retinal/raw feature"


record_cols = list(pd.read_csv(RECORD, nrows=0, encoding="utf-8-sig").columns)
raw_map = []
for col in record_cols:
    module = classify_raw_cho_column(col)
    if module:
        raw_map.append({"source": "CUHK_Record_260612_cleaned_with_raw_Cho.csv", "variable": col, "module": module})

with MAP_OUT.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["source", "variable", "module"])
    writer.writeheader()
    writer.writerows(raw_map)

raw_counts = pd.DataFrame(raw_map).groupby("module")["variable"].agg(["count", lambda s: "; ".join(list(s)[:8])]).reset_index()
raw_counts.columns = ["module", "n_variables", "examples"]

figure = pd.read_csv(FIGURE, dtype=object, encoding="utf-8-sig")
figure_modules = []
for _, row in figure.iterrows():
    layer = row["Layer"]
    measure = row["Measure"]
    if "Choriocapillaris" in layer:
        module = "Choriocapillaris perfusion"
    elif layer == "Choroid:Choroid" and measure == "Flow Area (mm2)":
        module = "Choroid perfusion"
    elif layer == "Choroid:Choroid" and measure == "Thickness":
        module = "Choroid structure/thickness"
    elif layer in {"CSI:CSI", "CVI:CVI"}:
        module = "Choroid vascular index/ratio"
    elif layer in {"CSV:CSV", "CVV:CVV"}:
        module = "Choroid vascular volume"
    else:
        module = "Other choroid/quantize feature"
    figure_modules.append(module)
figure = figure.assign(module=figure_modules)
fig_counts = figure.groupby("module").agg(
    n_rows=("Layer", "count"),
    valid_numeric_data=("valid_numeric_data", lambda s: int(pd.to_numeric(s).sum())),
    examples=("Layer", lambda s: "; ".join(list(s)[:4])),
).reset_index()

summary_rows = []
for _, row in raw_counts.iterrows():
    summary_rows.append(
        {
            "source": "raw_Cho merged table",
            "module": row["module"],
            "n_variables_or_rows": int(row["n_variables"]),
            "valid_grid_values": "",
            "examples": row["examples"],
            "recommended_score": "Z-score each variable, align direction, average within module. Consider regional scores separately for macula/other/S/I/T/N.",
        }
    )
for _, row in fig_counts.iterrows():
    summary_rows.append(
        {
            "source": "Quantize figure1 GRID3mm*3mm",
            "module": row["module"],
            "n_variables_or_rows": int(row["n_rows"]),
            "valid_grid_values": int(row["valid_numeric_data"]),
            "examples": row["examples"],
            "recommended_score": "Per row summarize 63 grid values by mean/median plus optional central/peripheral zones; z-score row summaries and average within module.",
        }
    )

with SUMMARY_OUT.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "source",
            "module",
            "n_variables_or_rows",
            "valid_grid_values",
            "examples",
            "recommended_score",
        ],
    )
    writer.writeheader()
    writer.writerows(summary_rows)

print(
    json.dumps(
        {
            "summary_out": str(SUMMARY_OUT),
            "map_out": str(MAP_OUT),
            "raw_modules": raw_counts.to_dict(orient="records"),
            "figure_modules": fig_counts.to_dict(orient="records"),
        },
        ensure_ascii=False,
        indent=2,
    )
)
