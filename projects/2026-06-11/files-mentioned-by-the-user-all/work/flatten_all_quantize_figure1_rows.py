import csv
import re
from pathlib import Path

import pandas as pd


BASE = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs"
)
QUANTIZE_DIR = BASE / "CUHK_OCT_OD_Quantize_tables"
COUNTS_CSV = BASE / "figure1_row_data_counts.csv"
MANIFEST_CSV = QUANTIZE_DIR / "manifest.csv"
OUTPUT_CSV = BASE / "CUHK_OCT_OD_Quantize_figure1_values_all_rows.csv"


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
    if text in {"female", "f", "2"}:
        return "1" if text == "female" else ("1" if text == "f" else "2")
    if text in {"male", "m", "1"}:
        return "2" if text == "male" else ("2" if text == "m" else "1")
    return str(value).strip()


def clean_gender_from_subject_sex(value):
    text = str(value).strip().upper()
    if text == "F":
        return "1"
    if text == "M":
        return "2"
    return ""


def parse_subject(subject):
    match = re.match(r"^(.*)_([0-9]{8})_([MF])$", str(subject).strip(), flags=re.I)
    if not match:
        return str(subject).strip(), "", ""
    return match.group(1), match.group(2), match.group(3).upper()


def read_csv_rows(path):
    with Path(path).open("r", encoding="gb18030", errors="replace", newline="") as handle:
        return list(csv.reader(handle))


def nearest_header_row(rows, row_index):
    for idx in range(row_index - 1, -1, -1):
        if rows[idx] and rows[idx][0] == "Name":
            return rows[idx]
    return []


targets_df = pd.read_csv(COUNTS_CSV, dtype=str, encoding="utf-8-sig")
targets = []
for _, item in targets_df.iterrows():
    targets.append(
        {
            "layer": item["Layer"],
            "measure": item["Measure"],
            "type": item["Type"],
            "occurrence": str(item["occurrence"]),
        }
    )


def extract_one_file(path):
    rows = read_csv_rows(path)
    matches = {}
    occurrence_counter = {}
    for row_index, row in enumerate(rows):
        if len(row) < 7:
            continue
        key = (row[4].strip(), row[5].strip(), row[6].strip())
        occurrence_counter[key] = occurrence_counter.get(key, 0) + 1
        occurrence = str(occurrence_counter[key])
        matches[(key[0], key[1], key[2], occurrence)] = (row_index, row)

    output = {}
    missing_targets = []
    for target in targets:
        match_key = (
            target["layer"],
            target["measure"],
            target["type"],
            target["occurrence"],
        )
        if match_key not in matches:
            missing_targets.append("|".join(match_key))
            continue

        row_index, row = matches[match_key]
        header = nearest_header_row(rows, row_index)
        if "Name" not in output:
            output["Name"] = row[0]
            output["Gender"] = clean_gender(row[1])
            output["Age"] = clean_age(row[2])
            output["Protocol"] = row[3]

        metric_prefix = (
            f"{slug(row[6])}_{slug(row[4])}_{slug(row[5])}_block{target['occurrence']}"
        )
        valid_index = 0
        for col_index, value in enumerate(row[7:], start=7):
            if not is_valid_number(value):
                continue
            valid_index += 1
            original_header = slug(
                header[col_index] if col_index < len(header) else f"col{col_index + 1}"
            )
            output[f"{metric_prefix}_{original_header}_v{valid_index:02d}"] = value

    return output, missing_targets


manifest = pd.read_csv(MANIFEST_CSV, dtype=str, encoding="utf-8-sig")
rows_out = []
all_columns = [
    "source_subject",
    "source_file",
    "process_status",
    "missing_target_count",
    "missing_targets",
    "Name",
    "Gender",
    "Age",
    "Protocol",
]

for _, item in manifest.iterrows():
    subject = item["subject"]
    copied_file = item.get("copied_file", "")
    source_path = Path(copied_file) if isinstance(copied_file, str) and copied_file else None
    row_out = {
        "source_subject": subject,
        "source_file": str(source_path) if source_path else "",
        "process_status": "",
        "missing_target_count": "",
        "missing_targets": "",
    }

    if item.get("status") != "copied" or source_path is None or not source_path.exists():
        name, _, sex = parse_subject(subject)
        row_out.update(
            {
                "Name": name,
                "Gender": clean_gender_from_subject_sex(sex),
                "Age": "",
                "Protocol": "",
                "process_status": "missing_source_file",
                "missing_target_count": len(targets),
                "missing_targets": "all",
            }
        )
    else:
        values, missing_targets = extract_one_file(source_path)
        row_out.update(values)
        row_out["process_status"] = "ok" if not missing_targets else "partial_missing_targets"
        row_out["missing_target_count"] = len(missing_targets)
        row_out["missing_targets"] = ";".join(missing_targets)

    for column in row_out:
        if column not in all_columns:
            all_columns.append(column)
    rows_out.append(row_out)

# Ensure metric columns discovered in later files are present in the final header.
for row in rows_out:
    for column in row:
        if column not in all_columns:
            all_columns.append(column)

OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=all_columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows_out)

metric_columns = [
    col
    for col in all_columns
    if col
    not in {
        "source_subject",
        "source_file",
        "process_status",
        "missing_target_count",
        "missing_targets",
        "Name",
        "Gender",
        "Age",
        "Protocol",
    }
]
print(
    {
        "output": str(OUTPUT_CSV),
        "rows": len(rows_out),
        "columns": len(all_columns),
        "metric_columns": len(metric_columns),
        "ok_rows": sum(1 for row in rows_out if row["process_status"] == "ok"),
        "missing_source_rows": sum(
            1 for row in rows_out if row["process_status"] == "missing_source_file"
        ),
        "partial_rows": sum(
            1 for row in rows_out if row["process_status"] == "partial_missing_targets"
        ),
    }
)
