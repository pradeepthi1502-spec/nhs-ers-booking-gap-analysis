"""
03 dm01 cleaning pipeline

Converted from the project notebook for the NHS e-RS Booking Gap Analysis GitHub portfolio project.
Upload this file inside the src/ folder.
"""


# 03 DM01 Diagnostic Waiting Times Cleaning Pipeline
# 
# Code copied from the original uploaded notebook and separated into logical steps.


# 1. Set paths and find DM01 files


# ------------------------------------------------------------------------
import pandas as pd
import numpy as np
import re
from pathlib import Path

base = Path("/Users/pradeepthikurapati/Library/Mobile Documents/com~apple~CloudDocs/e-rs data capstone")
cleaned = base / "cleaned_nhs_dashboard"
cleaned.mkdir(exist_ok=True)

dm01_folders = sorted([
    p for p in base.iterdir()
    if p.is_dir()
    and p.name.lower().startswith("monthly diagnostics commissioner")
])

print("DM01 folders found:", len(dm01_folders))

for folder in dm01_folders:
    print("-", folder.name)

dm01_files = []

for folder in dm01_folders:
    files = sorted([
        f for f in folder.rglob("*")
        if f.suffix.lower() in [".xlsx", ".xls", ".csv"]
        and not f.name.startswith("~$")
    ])
    print(folder.name, ":", len(files), "files")
    dm01_files.extend(files)

print("\nTotal DM01 files found:", len(dm01_files))

for f in dm01_files[:15]:
    print(f.name)

# 2. Define helper functions


# ------------------------------------------------------------------------
month_map = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

def parse_month_from_filename(path):
    name = path.stem.lower().replace("_", " ").replace("-", " ")
    
    for m_name, m_num in month_map.items():
        match = re.search(rf"\b{m_name}\s*(\d{{2}}|\d{{4}})\b", name)
        if match:
            y = match.group(1)
            year = int(y) if len(y) == 4 else 2000 + int(y)
            return pd.Timestamp(year, m_num, 1)
    
    return pd.NaT

def clean_col(c):
    c = str(c).strip().lower()
    c = c.replace("%", "pct")
    c = c.replace(">", "over")
    c = c.replace("+", "plus")
    c = c.replace("-", "_")
    c = re.sub(r"[^a-z0-9]+", "_", c)
    return c.strip("_")

def make_unique(cols):
    seen = {}
    output = []
    
    for c in cols:
        c = clean_col(c)
        if c == "" or c == "nan":
            c = "unnamed"
        
        if c not in seen:
            seen[c] = 0
            output.append(c)
        else:
            seen[c] += 1
            output.append(f"{c}_{seen[c]}")
    
    return output

def numeric_clean(s):
    return (
        s.astype(str)
         .str.replace(",", "", regex=False)
         .str.replace("%", "", regex=False)
         .str.strip()
         .replace(["nan", "None", "-", "", "*", "x"], np.nan)
    )

def excel_engine(path):
    return "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"

def coalesce_columns(df, candidates):
    existing = [c for c in candidates if c in df.columns]
    
    if not existing:
        return pd.Series([np.nan] * len(df), index=df.index)
    
    result = df[existing[0]].copy()
    
    for c in existing[1:]:
        result = result.where(
            result.notna()
            & (result.astype(str).str.lower() != "nan")
            & (result.astype(str).str.strip() != ""),
            df[c]
        )
    
    return result

# 3. Select DM01 sheet, find header row, read and combine files


# ------------------------------------------------------------------------
def pick_dm01_sheet(path):
    if path.suffix.lower() not in [".xls", ".xlsx"]:
        return "csv"
    
    engine = excel_engine(path)
    xl = pd.ExcelFile(path, engine=engine)
    sheets = xl.sheet_names
    
    # Prefer commissioner-style sheets
    preferred = [
        s for s in sheets
        if "commissioner" in s.lower()
        and "provider" not in s.lower()
        and "dta" not in s.lower()
    ]
    if preferred:
        return preferred[0]
    
    # Fallback to data sheet
    data_sheets = [
        s for s in sheets
        if any(word in s.lower() for word in ["data", "monthly", "dm01"])
    ]
    if data_sheets:
        return data_sheets[0]
    
    return sheets[0]

def find_dm01_header_row(raw):
    for i in range(min(100, len(raw))):
        row_text = " ".join(raw.iloc[i].fillna("").astype(str).str.lower().tolist())
        
        has_org = any(term in row_text for term in [
            "commissioner", "organisation", "org code", "ccg", "sub icb", "icb"
        ])
        
        has_diag = any(term in row_text for term in [
            "diagnostic", "test", "modality"
        ])
        
        has_measure = any(term in row_text for term in [
            "waiting", "activity", "total", "patients"
        ])
        
        if has_org and has_diag and has_measure:
            return i
    
    # fallback
    for i in range(min(100, len(raw))):
        row_text = " ".join(raw.iloc[i].fillna("").astype(str).str.lower().tolist())
        if ("diagnostic" in row_text or "test" in row_text) and ("waiting" in row_text or "activity" in row_text):
            return i
    
    raise ValueError("Could not find DM01 header row")

def read_dm01_file(path):
    month_start = parse_month_from_filename(path)
    
    if path.suffix.lower() in [".xls", ".xlsx"]:
        engine = excel_engine(path)
        sheet = pick_dm01_sheet(path)
        raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str, engine=engine)
    else:
        sheet = "csv"
        raw = pd.read_csv(path, header=None, dtype=str, low_memory=False)
    
    header_row = find_dm01_header_row(raw)
    
    cols = raw.iloc[header_row].tolist()
    df = raw.iloc[header_row + 1:].copy()
    df.columns = make_unique(cols)
    
    df = df.dropna(how="all")
    df["month_start"] = month_start
    df["source_file"] = path.name
    df["source_sheet"] = sheet
    
    return df

all_dm01 = []
failed_dm01 = []

for file in dm01_files:
    try:
        df = read_dm01_file(file)
        all_dm01.append(df)
    except Exception as e:
        failed_dm01.append((file.name, str(e)))

print("DM01 files successfully read:", len(all_dm01))
print("DM01 failed files:", len(failed_dm01))

if failed_dm01:
    print("\nFailed DM01 files:")
    for name, error in failed_dm01[:50]:
        print(name, "=>", error)

if len(all_dm01) == 0:
    raise ValueError("No DM01 files were read. Stop here and inspect file structure.")

dm01_raw = pd.concat(all_dm01, ignore_index=True)

print("\nRaw DM01 combined shape:", dm01_raw.shape)
print("\nColumns detected:")
print(dm01_raw.columns.tolist())
print("\nSheets used:")
print(dm01_raw["source_sheet"].value_counts())

# 4. Standardise DM01 fields and create working metrics


# ------------------------------------------------------------------------
dm01 = dm01_raw.copy()

fact_work = pd.DataFrame()

fact_work["month_start"] = pd.to_datetime(dm01["month_start"], errors="coerce")

fact_work["commissioner_code"] = coalesce_columns(dm01, [
    "ccg_code",
    "sub_icb_location_code",
    "sub_icb_code",
    "icb_code",
    "commissioner_code",
    "organisation_code",
    "org_code",
    "ods_code",
    "regional_team_code"
]).astype(str).str.strip().str.upper()

fact_work["commissioner_name"] = coalesce_columns(dm01, [
    "ccg_name",
    "sub_icb_location_name",
    "sub_icb_name",
    "icb_name",
    "commissioner_name",
    "organisation_name",
    "org_name",
    "regional_team_name"
]).astype(str).str.strip()

fact_work["diagnostic_id"] = coalesce_columns(dm01, [
    "diagnostic_id",
    "diagnostic_code",
    "test_id"
]).astype(str).str.strip()

fact_work["diagnostic_test"] = coalesce_columns(dm01, [
    "diagnostic_test_name",
    "diagnostic_test",
    "test_name",
    "test",
    "diagnostic_modality",
    "modality"
]).astype(str).str.strip()

fact_work["waiting_list_total"] = pd.to_numeric(
    numeric_clean(coalesce_columns(dm01, [
        "total_waiting_list",
        "waiting_list_total",
        "total_waiting",
        "patients_waiting",
        "number_waiting",
        "total_number_waiting"
    ])),
    errors="coerce"
).fillna(0)

fact_work["waiting_6_plus_weeks"] = pd.to_numeric(
    numeric_clean(coalesce_columns(dm01, [
        "number_waiting_6plus_weeks",
        "number_waiting_6_weeks",
        "number_waiting_6_plus_weeks",
        "patients_waiting_6_weeks_or_more",
        "waiting_6_plus_weeks",
        "over_6_weeks"
    ])),
    errors="coerce"
).fillna(0)

fact_work["waiting_13_plus_weeks"] = pd.to_numeric(
    numeric_clean(coalesce_columns(dm01, [
        "number_waiting_13plus_weeks",
        "number_waiting_13_weeks",
        "number_waiting_13_plus_weeks",
        "waiting_13_plus_weeks",
        "over_13_weeks"
    ])),
    errors="coerce"
).fillna(0)

fact_work["planned_activity"] = pd.to_numeric(
    numeric_clean(coalesce_columns(dm01, [
        "planned_tests_procedures",
        "planned_tests",
        "planned_activity"
    ])),
    errors="coerce"
).fillna(0)

fact_work["unscheduled_activity"] = pd.to_numeric(
    numeric_clean(coalesce_columns(dm01, [
        "unscheduled_tests_procedures",
        "unscheduled_tests",
        "unscheduled_activity"
    ])),
    errors="coerce"
).fillna(0)

fact_work["waiting_list_activity"] = pd.to_numeric(
    numeric_clean(coalesce_columns(dm01, [
        "waiting_list_tests_procedures_excluding_planned",
        "waiting_list_tests_procedures",
        "waiting_list_activity"
    ])),
    errors="coerce"
).fillna(0)

fact_work["activity"] = (
    fact_work["planned_activity"]
    + fact_work["unscheduled_activity"]
    + fact_work["waiting_list_activity"]
)

print("Rows before filtering:", len(fact_work))
print("Date range:", fact_work["month_start"].min(), "to", fact_work["month_start"].max())
print("Months available:", fact_work["month_start"].nunique())

print("\nBlank commissioner codes:")
print((fact_work["commissioner_code"].str.lower() == "nan").sum())

print("\nBlank diagnostic tests:")
print((fact_work["diagnostic_test"].str.lower() == "nan").sum())

print("\nTotals before filtering:")
print("Waiting list total:", fact_work["waiting_list_total"].sum())
print("Waiting 6+ weeks:", fact_work["waiting_6_plus_weeks"].sum())
print("Waiting 13+ weeks:", fact_work["waiting_13_plus_weeks"].sum())
print("Activity:", fact_work["activity"].sum())

print(fact_work.head(20))

# 5. Filter, aggregate, engineer DM01 metrics and save clean file


# ------------------------------------------------------------------------
fact_work = fact_work.dropna(subset=["month_start"])

fact_work = fact_work[
    fact_work["commissioner_code"].notna()
    & (fact_work["commissioner_code"].str.lower() != "nan")
    & (fact_work["commissioner_code"].str.strip() != "")
]

fact_work = fact_work[
    fact_work["diagnostic_test"].notna()
    & (fact_work["diagnostic_test"].str.lower() != "nan")
    & (fact_work["diagnostic_test"].str.strip() != "")
]

fact_work = fact_work[
    ~(
        (fact_work["commissioner_name"].str.upper().str.strip() == "ENGLAND")
        | (fact_work["commissioner_name"].str.upper().str.strip() == "NHS ENGLAND")
        | (fact_work["commissioner_name"].str.upper().str.strip() == "TOTAL")
        | (fact_work["diagnostic_test"].str.upper().str.strip() == "TOTAL")
    )
]

fact_work = fact_work[
    (fact_work["waiting_list_total"] > 0)
    | (fact_work["waiting_6_plus_weeks"] > 0)
    | (fact_work["activity"] > 0)
]

fact_dm01 = (
    fact_work
    .groupby(
        [
            "month_start",
            "commissioner_code",
            "commissioner_name",
            "diagnostic_id",
            "diagnostic_test"
        ],
        as_index=False
    )
    .agg(
        waiting_list_total=("waiting_list_total", "sum"),
        waiting_6_plus_weeks=("waiting_6_plus_weeks", "sum"),
        waiting_13_plus_weeks=("waiting_13_plus_weeks", "sum"),
        planned_activity=("planned_activity", "sum"),
        unscheduled_activity=("unscheduled_activity", "sum"),
        waiting_list_activity=("waiting_list_activity", "sum"),
        activity=("activity", "sum")
    )
)

fact_dm01["pct_waiting_6_plus_weeks"] = np.where(
    fact_dm01["waiting_list_total"] > 0,
    fact_dm01["waiting_6_plus_weeks"] / fact_dm01["waiting_list_total"],
    np.nan
)

fact_dm01["pct_waiting_13_plus_weeks"] = np.where(
    fact_dm01["waiting_list_total"] > 0,
    fact_dm01["waiting_13_plus_weeks"] / fact_dm01["waiting_list_total"],
    np.nan
)

def financial_year(d):
    y = d.year
    return f"{y}/{str(y + 1)[-2:]}" if d.month >= 4 else f"{y - 1}/{str(y)[-2:]}"

fact_dm01["financial_year"] = fact_dm01["month_start"].apply(financial_year)
fact_dm01["year"] = fact_dm01["month_start"].dt.year
fact_dm01["month_number"] = fact_dm01["month_start"].dt.month
fact_dm01["month_name"] = fact_dm01["month_start"].dt.strftime("%b")
fact_dm01["quarter"] = fact_dm01["month_start"].dt.to_period("Q").astype(str)

fact_dm01 = fact_dm01[
    [
        "month_start",
        "financial_year",
        "year",
        "quarter",
        "month_number",
        "month_name",
        "commissioner_code",
        "commissioner_name",
        "diagnostic_id",
        "diagnostic_test",
        "waiting_list_total",
        "waiting_6_plus_weeks",
        "waiting_13_plus_weeks",
        "pct_waiting_6_plus_weeks",
        "pct_waiting_13_plus_weeks",
        "planned_activity",
        "unscheduled_activity",
        "waiting_list_activity",
        "activity"
    ]
]

dm01_out_path = cleaned / "fact_dm01_monthly_clean.csv"
fact_dm01.to_csv(dm01_out_path, index=False)

print("Saved DM01 clean file:")
print(dm01_out_path)
print("Rows:", len(fact_dm01))

# 6. Validate DM01 output


# ------------------------------------------------------------------------
fact_dm01 = pd.read_csv(cleaned / "fact_dm01_monthly_clean.csv")
fact_dm01["month_start"] = pd.to_datetime(fact_dm01["month_start"])

print("--- DM01 FACT TABLE CHECK ---")
print("Rows:", len(fact_dm01))
print("Columns:", len(fact_dm01.columns))

print("\nDuplicate month + commissioner_code + diagnostic_test rows:")
print(fact_dm01.duplicated(["month_start", "commissioner_code", "diagnostic_test"]).sum())

print("\nDate range:")
print(fact_dm01["month_start"].min().date(), "to", fact_dm01["month_start"].max().date())

print("\nNumber of months:")
print(fact_dm01["month_start"].nunique())

expected_months = pd.date_range("2019-10-01", "2025-09-01", freq="MS")
actual_months = pd.to_datetime(fact_dm01["month_start"].drop_duplicates()).sort_values()
missing_months = sorted(set(expected_months) - set(actual_months))

print("\nExpected months:", len(expected_months))
print("Actual months:", len(actual_months))
print("Missing months:", missing_months)

print("\nMissing values in key fields:")
print(fact_dm01[
    [
        "month_start",
        "commissioner_code",
        "diagnostic_test",
        "waiting_list_total",
        "waiting_6_plus_weeks",
        "activity"
    ]
].isna().sum())

print("\nTotals:")
print("Waiting list total:", fact_dm01["waiting_list_total"].sum())
print("Waiting 6+ weeks:", fact_dm01["waiting_6_plus_weeks"].sum())
print("Waiting 13+ weeks:", fact_dm01["waiting_13_plus_weeks"].sum())
print("Activity:", fact_dm01["activity"].sum())

print("\nOverall pct waiting 6+ weeks:")
print(fact_dm01["waiting_6_plus_weeks"].sum() / fact_dm01["waiting_list_total"].sum())

print("\nRows per month, last 10:")
print(fact_dm01.groupby("month_start").size().tail(10))

print("\nFiles in cleaned folder:")
for file in cleaned.glob("*"):
    print(file.name)
