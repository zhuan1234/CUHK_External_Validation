import json
import os
import re

import pandas as pd


INPUT_XLSX = r"C:\Users\25124968R\Desktop\CUHK\CUHK_Record_260612_cleaned.xlsx"
RAW_CSV = r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs\all_raw_Cho_sorted.csv"
OUTPUT_CSV = r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs\CUHK_Record_260612_cleaned_with_raw_Cho.csv"


def make_unique_headers(headers):
    used = {}
    out = []
    for idx, header in enumerate(headers, start=1):
        name = "" if pd.isna(header) else str(header).strip()
        if not name:
            name = f"blank_{idx}"
        if name in used:
            used[name] += 1
            name = f"{name}_{used[name]}"
        else:
            used[name] = 1
        out.append(name)
    return out


def append_r(value):
    if pd.isna(value) or str(value).strip() == "":
        return ""
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    if re.fullmatch(r"\d+[Rr]", text):
        return text[:-1] + "R"
    if re.fullmatch(r"\d+[Ll]", text):
        return text[:-1] + "R"
    return f"{text}R"


def map_sex(value):
    if pd.isna(value) or str(value).strip() == "":
        return ""
    text = str(value).strip().upper()
    if text == "M":
        return 1
    if text == "F":
        return 2
    return value


def split_post_ar(value):
    if pd.isna(value):
        return value, ""
    text = str(value)
    match = re.search(r"\(\s*SE\s*([+-]?\d+(?:\.\d+)?)\s*\)", text, flags=re.I)
    post_se = match.group(1) if match else ""
    cleaned = re.sub(r"\s*\([^)]*\)", "", text).strip()
    return cleaned, post_se


excel_raw = pd.read_excel(INPUT_XLSX, sheet_name=0, header=None, dtype=object)
headers = make_unique_headers(excel_raw.iloc[1].tolist())
data = excel_raw.iloc[2:].copy()
data.columns = headers

# Drop only completely empty unnamed trailing columns from the source workbook.
empty_unnamed = [
    col for col in data.columns if col.startswith("blank_") and data[col].isna().all()
]
if empty_unnamed:
    data = data.drop(columns=empty_unnamed)

required = ["ID", "Sex", "Post AR", "Post SE"]
missing = [col for col in required if col not in data.columns]
if missing:
    raise ValueError(f"Missing required columns: {missing}")

data["ID"] = data["ID"].map(append_r)
data["Sex"] = data["Sex"].map(map_sex)

post_ar_clean = []
post_se_values = []
for value in data["Post AR"]:
    cleaned, post_se = split_post_ar(value)
    post_ar_clean.append(cleaned)
    post_se_values.append(post_se)
data["Post AR"] = post_ar_clean
data["Post SE"] = post_se_values

raw = pd.read_csv(RAW_CSV, dtype=object, encoding="utf-8-sig")
raw["imid"] = raw["imid"].astype(str).str.strip()

merged = data.merge(raw, how="left", left_on="ID", right_on="imid", suffixes=("", "_raw"))

os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
merged.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

matched = int(merged["imid"].notna().sum()) if "imid" in merged.columns else 0
unmatched_rows = merged.loc[merged["imid"].isna(), "ID"].head(20).tolist()

summary = {
    "output": OUTPUT_CSV,
    "source_rows": int(len(data)),
    "source_columns_after_cleanup": int(len(data.columns)),
    "raw_columns_appended": int(len(raw.columns)),
    "output_rows": int(len(merged)),
    "output_columns": int(len(merged.columns)),
    "matched_imid": matched,
    "unmatched_imid": int(len(merged) - matched),
    "unmatched_id_samples": unmatched_rows,
    "post_se_filled": int(pd.Series(post_se_values).replace("", pd.NA).notna().sum()),
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
