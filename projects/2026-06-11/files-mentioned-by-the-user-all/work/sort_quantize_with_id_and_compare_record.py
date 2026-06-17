import re
from pathlib import Path

import pandas as pd


BASE = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs"
)
QUANTIZE_INPUT = Path(
    r"C:\Users\25124968R\Desktop\CUHK\CUHK_OCT_OD_Quantize_figure1_values_all_rows_with_ID.csv"
)
RECORD_INPUT = Path(
    r"C:\Users\25124968R\Desktop\CUHK\CUHK_Record_260612_cleaned_with_raw_Cho.csv"
)
QUANTIZE_OUTPUT = BASE / "CUHK_OCT_OD_Quantize_figure1_values_all_rows_with_ID_sorted_DOB.csv"
COMPARE_REPORT = BASE / "CUHK_OCT_OD_Quantize_vs_Record_ID_DOB_report.csv"


def extract_dob_from_subject(subject):
    match = re.match(r"^.*_([0-9]{8})_[MF]$", str(subject).strip(), flags=re.I)
    return match.group(1) if match else ""


def normalize_id(value):
    text = re.sub(r"\.0$", "", str(value or "").strip())
    if not text or text.lower() == "nan":
        return ""
    text = re.sub(r"[RrLl]$", "", text)
    return f"{text}R"


def id_sort_key(value):
    text = str(value or "").strip()
    match = re.match(r"^(\d+)", text)
    if not match:
        return (1, 10**20, text)
    return (0, int(match.group(1)), text)


def clean_dob(value):
    text = re.sub(r"\.0$", "", str(value or "").strip())
    digits = re.sub(r"\D", "", text)
    return digits[:8] if len(digits) >= 8 else ""


quantize = pd.read_csv(QUANTIZE_INPUT, dtype=str, encoding="utf-8-sig")
record = pd.read_csv(RECORD_INPUT, dtype=str, encoding="utf-8-sig")

if "ID" not in quantize.columns or "source_subject" not in quantize.columns:
    raise ValueError("Quantize CSV must contain ID and source_subject columns.")
if "ID" not in record.columns or "DOB" not in record.columns:
    raise ValueError("Record CSV must contain ID and DOB columns.")

quantize["ID"] = quantize["ID"].map(normalize_id)
dob_values = quantize["source_subject"].map(extract_dob_from_subject)

if "DOB" in quantize.columns:
    quantize = quantize.drop(columns=["DOB"])
insert_at = quantize.columns.get_loc("ID") + 1
quantize.insert(insert_at, "DOB", dob_values)

quantize["_sort_key"] = quantize["ID"].map(id_sort_key)
quantize = quantize.sort_values("_sort_key", kind="mergesort").drop(columns=["_sort_key"])

QUANTIZE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
quantize.to_csv(QUANTIZE_OUTPUT, index=False, encoding="utf-8-sig")

q_compare = quantize.copy()
r_compare = record.copy()
q_compare["ID_norm"] = q_compare["ID"].map(normalize_id)
q_compare["DOB_norm"] = q_compare["DOB"].map(clean_dob)
r_compare["ID_norm"] = r_compare["ID"].map(normalize_id)
r_compare["DOB_norm"] = r_compare["DOB"].map(clean_dob)

q_by_id = q_compare.drop_duplicates("ID_norm", keep="first").set_index("ID_norm")
r_by_id = r_compare.drop_duplicates("ID_norm", keep="first").set_index("ID_norm")

report_rows = []

for identifier in sorted(set(q_by_id.index) | set(r_by_id.index), key=id_sort_key):
    if not identifier:
        continue
    in_q = identifier in q_by_id.index
    in_r = identifier in r_by_id.index
    q_dob = q_by_id.at[identifier, "DOB_norm"] if in_q else ""
    r_dob = r_by_id.at[identifier, "DOB_norm"] if in_r else ""
    q_subject = q_by_id.at[identifier, "source_subject"] if in_q and "source_subject" in q_by_id.columns else ""
    q_name = q_by_id.at[identifier, "Name"] if in_q and "Name" in q_by_id.columns else ""

    if in_q and in_r:
        status = "matched" if q_dob == r_dob else "dob_mismatch"
    elif in_q:
        status = "missing_in_record"
    else:
        status = "missing_in_quantize"

    if status != "matched":
        report_rows.append(
            {
                "ID": identifier,
                "status": status,
                "quantize_DOB": q_dob,
                "record_DOB": r_dob,
                "quantize_source_subject": q_subject,
                "quantize_Name": q_name,
            }
        )

report = pd.DataFrame(
    report_rows,
    columns=[
        "ID",
        "status",
        "quantize_DOB",
        "record_DOB",
        "quantize_source_subject",
        "quantize_Name",
    ],
)
report.to_csv(COMPARE_REPORT, index=False, encoding="utf-8-sig")

summary = {
    "quantize_output": str(QUANTIZE_OUTPUT),
    "compare_report": str(COMPARE_REPORT),
    "quantize_rows": int(len(quantize)),
    "record_rows": int(len(record)),
    "quantize_blank_id": int((quantize["ID"].fillna("") == "").sum()),
    "quantize_blank_dob": int((quantize["DOB"].fillna("") == "").sum()),
    "report_rows": int(len(report)),
    "status_counts": report["status"].value_counts(dropna=False).to_dict()
    if not report.empty
    else {},
    "first_ids": quantize["ID"].head(5).tolist(),
    "last_ids": quantize["ID"].tail(5).tolist(),
}
print(summary)
