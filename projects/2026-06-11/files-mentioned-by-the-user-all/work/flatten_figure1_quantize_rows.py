import csv
import os
import re
from pathlib import Path

import pandas as pd


SOURCE_CSV = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs\CUHK_OCT_OD_Quantize_tables\00535_d20051384_zi qi zeng_OD_2026-04-25_10-05-00Angio 26x21 1536x1280 R2_55.071__2026-05-05_19-31-29.csv"
)
COUNTS_CSV = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs\figure1_row_data_counts.csv"
)
OUTPUT_CSV = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs\figure1_quantize_values_one_row.csv"
)


def slug(value):
    text = str(value).strip()
    text = re.sub(r"[^0-9A-Za-z]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "value"


def is_valid_number(value):
    text = str(value).strip()
    if text in {"", "-"}:
        return False
    try:
        float(text)
        return True
    except ValueError:
        return False


with SOURCE_CSV.open("r", encoding="gb18030", errors="replace", newline="") as handle:
    source_rows = list(csv.reader(handle))

counts = pd.read_csv(COUNTS_CSV, dtype=str, encoding="utf-8-sig")
target_rows = [int(x) for x in counts["csv_row"].tolist()]

output = {}
used_columns = set()

for target_row in target_rows:
    row = source_rows[target_row - 1]
    if not output:
        output["Name"] = row[0]
        output["Gender"] = row[1]
        output["Age"] = row[2]
        output["Protocol"] = row[3]

    layer = row[4]
    measure = row[5]
    type_name = row[6]
    occurrence = counts.loc[counts["csv_row"].astype(int).eq(target_row), "occurrence"].iloc[0]

    metric_prefix = (
        f"{slug(type_name)}_{slug(layer)}_{slug(measure)}_block{occurrence}"
    )

    valid_index = 0
    for value in row[7:]:
        if not is_valid_number(value):
            continue
        valid_index += 1
        column = f"{metric_prefix}_v{valid_index:02d}"
        if column in used_columns:
            raise ValueError(f"Duplicate output column generated: {column}")
        used_columns.add(column)
        output[column] = value

OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(output.keys()))
    writer.writeheader()
    writer.writerow(output)

print(
    {
        "output": str(OUTPUT_CSV),
        "source_rows_used": len(target_rows),
        "output_rows": 1,
        "output_columns": len(output),
        "basic_info_columns": 4,
        "value_columns": len(output) - 4,
    }
)
