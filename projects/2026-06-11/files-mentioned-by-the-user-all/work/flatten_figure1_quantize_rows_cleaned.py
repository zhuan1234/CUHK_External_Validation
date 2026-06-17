import csv
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
    r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs\figure1_quantize_values_one_row_cleaned.csv"
)


def compact_repeated_label(value):
    text = str(value).strip()
    if ":" in text:
        parts = [part.strip() for part in text.split(":")]
        if len(parts) == 2 and parts[0].casefold() == parts[1].casefold():
            return parts[0]
    return text


def slug(value):
    text = compact_repeated_label(value)
    text = text.replace("μ", "u").replace("µ", "u")
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


def clean_age(value):
    match = re.search(r"\d+", str(value))
    return match.group(0) if match else ""


def clean_gender(value):
    text = str(value).strip().casefold()
    if text == "female":
        return "1"
    if text == "male":
        return "2"
    return str(value).strip()


with SOURCE_CSV.open("r", encoding="gb18030", errors="replace", newline="") as handle:
    source_rows = list(csv.reader(handle))

counts = pd.read_csv(COUNTS_CSV, dtype=str, encoding="utf-8-sig")

output = {}
used_columns = set()

for _, count_row in counts.iterrows():
    target_row = int(count_row["csv_row"])
    header_row = int(count_row["header_row"])
    occurrence = str(count_row["occurrence"])

    row = source_rows[target_row - 1]
    header = source_rows[header_row - 1]

    if not output:
        output["Name"] = row[0]
        output["Gender"] = clean_gender(row[1])
        output["Age"] = clean_age(row[2])
        output["Protocol"] = row[3]

    type_name = slug(row[6])
    layer_name = slug(row[4])
    measure_name = slug(row[5])
    metric_prefix = f"{type_name}_{layer_name}_{measure_name}_block{occurrence}"

    valid_index = 0
    for col_index, value in enumerate(row[7:], start=7):
        if not is_valid_number(value):
            continue
        valid_index += 1
        original_header = slug(header[col_index] if col_index < len(header) else f"col{col_index + 1}")
        column = f"{metric_prefix}_{original_header}_v{valid_index:02d}"
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
        "output_rows": 1,
        "output_columns": len(output),
        "basic_info_columns": 4,
        "value_columns": len(output) - 4,
    }
)
