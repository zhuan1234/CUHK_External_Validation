import re
import os
from pathlib import Path

import pandas as pd


BASE = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs"
)
TARGETS = [
    BASE / "CUHK_OCT_OD_Quantize_figure1_values_all_rows.csv",
    BASE / "CUHK_OCT_OD_Quantize_figure1_values_all_rows_with_ID.csv",
]


def gender_from_subject(subject):
    match = re.search(r"_([MF])$", str(subject).strip(), flags=re.I)
    if not match:
        return ""
    return "1" if match.group(1).upper() == "M" else "2"


summaries = []
for path in TARGETS:
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    if "source_subject" not in df.columns or "Gender" not in df.columns:
        raise ValueError(f"Missing required columns in {path}")

    old_counts = df["Gender"].fillna("").value_counts(dropna=False).to_dict()
    df["Gender"] = df["source_subject"].map(gender_from_subject)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(temp_path, index=False, encoding="utf-8-sig")
    os.replace(temp_path, path)

    summaries.append(
        {
            "file": str(path),
            "rows": int(len(df)),
            "old_gender_counts": old_counts,
            "new_gender_counts": df["Gender"].fillna("").value_counts(dropna=False).to_dict(),
            "blank_gender": int((df["Gender"].fillna("") == "").sum()),
        }
    )

print(summaries)
