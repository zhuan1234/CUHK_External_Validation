import csv
import os
import re
import shutil
from pathlib import Path


ROOT = Path(r"E:\CUHK_myopia_2605\CUHK_OCT")
OUTPUT_DIR = Path(
    r"C:\Users\25124968R\Documents\Codex\2026-06-11\files-mentioned-by-the-user-all\outputs\CUHK_OCT_OD_Quantize_tables"
)
TABLE_EXTS = {".csv", ".xlsx", ".xls", ".xlsm", ".tsv"}


def timestamp_key(path: Path) -> str:
    text = str(path)
    matches = re.findall(r"OD_(\d{14})", text, flags=re.I)
    if matches:
        return max(matches)
    return ""


def unique_destination(filename: str) -> Path:
    dest = OUTPUT_DIR / filename
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    index = 2
    while True:
        candidate = OUTPUT_DIR / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def table_files_for_subject(subject_dir: Path):
    files = []
    for child in subject_dir.iterdir():
        if not child.is_dir() or "OD" not in child.name.upper():
            continue
        quantize = child / "Quantize"
        if not quantize.is_dir():
            continue
        for file in quantize.iterdir():
            if file.is_file() and file.suffix.lower() in TABLE_EXTS:
                files.append(file)
    return files


OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

manifest_rows = []
missing_rows = []
copied = 0

for subject_dir in sorted([p for p in ROOT.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
    candidates = table_files_for_subject(subject_dir)
    if not candidates:
        missing_rows.append(
            {
                "subject": subject_dir.name,
                "status": "missing_od_quantize_table",
                "candidate_count": 0,
                "source_file": "",
                "copied_file": "",
                "selection_note": "No second-level folder name contained OD with a Quantize table file.",
            }
        )
        continue

    selected = sorted(
        candidates,
        key=lambda p: (timestamp_key(p.parent.parent), p.name.lower()),
        reverse=True,
    )[0]
    dest = unique_destination(selected.name)
    shutil.copy2(selected, dest)
    copied += 1
    manifest_rows.append(
        {
            "subject": subject_dir.name,
            "status": "copied",
            "candidate_count": len(candidates),
            "source_file": str(selected),
            "copied_file": str(dest),
            "selection_note": "latest OD folder selected" if len(candidates) > 1 else "single OD candidate",
        }
    )

manifest_path = OUTPUT_DIR / "manifest.csv"
with manifest_path.open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "subject",
            "status",
            "candidate_count",
            "source_file",
            "copied_file",
            "selection_note",
        ],
    )
    writer.writeheader()
    writer.writerows(manifest_rows)
    writer.writerows(missing_rows)

print(
    {
        "output_dir": str(OUTPUT_DIR),
        "subjects_total": len(manifest_rows) + len(missing_rows),
        "copied_files": copied,
        "missing_subjects": len(missing_rows),
        "multi_candidate_subjects": sum(
            1 for row in manifest_rows if int(row["candidate_count"]) > 1
        ),
        "manifest": str(manifest_path),
        "missing": [row["subject"] for row in missing_rows],
    }
)
