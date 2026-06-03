"""
02 rtt monthly cleaning pipeline

Converted from the project notebook for the NHS e-RS Booking Gap Analysis GitHub portfolio project.
Upload this file inside the src/ folder.
"""


# 02 RTT Monthly Cleaning Pipeline
# 
# Code copied from the original uploaded notebook and separated into logical steps.


# 1. Set paths and find RTT files


# ------------------------------------------------------------------------
import pandas as pd
import numpy as np
import re
from pathlib import Path

base = Path("/Users/pradeepthikurapati/Library/Mobile Documents/com~apple~CloudDocs/e-rs data capstone")
cleaned = base / "cleaned_nhs_dashboard"
cleaned.mkdir(exist_ok=True)

rtt_folders = sorted([
    p for p in base.iterdir()
    if p.is_dir() and p.name.lower().startswith("incomplete commissioner rtt")
])

rtt_files = []

for folder in rtt_folders:
    files = sorted([
        f for f in folder.rglob("*")
        if f.suffix.lower() in [".xlsx", ".xls", ".csv"]
        and not f.name.startswith("~$")
    ])
    rtt_files.extend(files)

print("RTT folders found:", len(rtt_folders))
print("RTT files found:", len(rtt_files))

# 2. Define helper functions for month parsing, column cleaning and Excel engine


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
    c = c.replace(">", "")
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

# 3. Select RTT sheet and header row


# ------------------------------------------------------------------------
def pick_rtt_sheet(path):
    engine = excel_engine(path)
    xl = pd.ExcelFile(path, engine=engine)
    sheets = xl.sheet_names
    month_start = parse_month_from_filename(path)
    
    # Pre-ICB structure: Commissioner sheet
    commissioner_exact = [s for s in sheets if s.strip().lower() == "commissioner"]
    if commissioner_exact:
        return commissioner_exact[0]
    
    # Post-July 2022 structure: Sub-ICB sheet
    sub_icb_exact = [s for s in sheets if s.strip().lower() == "sub-icb"]
    if sub_icb_exact:
        return sub_icb_exact[0]
    
    # Fallback: Sub-ICB without DTA
    sub_icb_non_dta = [
        s for s in sheets
        if "sub" in s.lower() and "icb" in s.lower() and "dta" not in s.lower()
    ]
    if sub_icb_non_dta:
        return sub_icb_non_dta[0]
    
    # Last fallback: ICB sheet
    icb_exact = [s for s in sheets if s.strip().lower() == "icb"]
    if icb_exact:
        return icb_exact[0]
    
    raise ValueError(f"No Commissioner/Sub-ICB/ICB sheet found. Sheets: {sheets}")

# 4. Read and combine RTT files


# ------------------------------------------------------------------------
def read_rtt_file(path):
    month_start = parse_month_from_filename(path)
    
    if path.suffix.lower() in [".xls", ".xlsx"]:
        engine = excel_engine(path)
        sheet = pick_rtt_sheet(path)
        raw = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str, engine=engine)
    else:
        raw = pd.read_csv(path, header=None, dtype=str, low_memory=False)
        sheet = "csv"
    
    header_row = find_header_row(raw)
    
    cols = raw.iloc[header_row].tolist()
    df = raw.iloc[header_row + 1:].copy()
    df.columns = make_unique(cols)
    
    df = df.dropna(how="all")
    df["month_start"] = month_start
    df["source_file"] = path.name
    df["source_sheet"] = sheet
    
    return df

all_rtt = []
failed = []

for file in rtt_files:
    try:
        df = read_rtt_file(file)
        all_rtt.append(df)
    except Exception as e:
        failed.append((file.name, str(e)))

print("Files successfully read:", len(all_rtt))
print("Failed files:", len(failed))

if failed:
    print("\nFailed files:")
    for name, error in failed[:50]:
        print(name, "=>", error)

if len(all_rtt) == 0:
    raise ValueError("No RTT files were read.")

rtt_raw = pd.concat(all_rtt, ignore_index=True)

print("\nRaw RTT combined shape:", rtt_raw.shape)
print("\nColumns detected:")
print(rtt_raw.columns.tolist())
print("\nSheets used:")
print(rtt_raw["source_sheet"].value_counts())

# 5. Coalesce RTT columns and create working fields


# ------------------------------------------------------------------------
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

rtt = rtt_raw.copy()

print("Available columns:")
print(rtt.columns.tolist())

rtt_clean = pd.DataFrame()

rtt_clean["month_start"] = pd.to_datetime(rtt["month_start"], errors="coerce")

rtt_clean["commissioner_code"] = coalesce_columns(rtt, [
    "ccg_code",
    "sub_icb_location_code",
    "sub_icb_location_ods_code",
    "sub_icb_code",
    "sub_icb_location_short_code",
    "sub_icb_location",
    "organisation_code",
    "org_code",
    "icb_code"
]).astype(str).str.strip().str.upper()

rtt_clean["commissioner_name"] = coalesce_columns(rtt, [
    "ccg_name",
    "sub_icb_location_name",
    "sub_icb_name",
    "sub_icb_location",
    "organisation_name",
    "org_name",
    "icb_name"
]).astype(str).str.strip()

rtt_clean["treatment_function_code"] = coalesce_columns(rtt, [
    "treatment_function_code",
    "function_code"
]).astype(str).str.strip()

rtt_clean["treatment_function"] = coalesce_columns(rtt, [
    "treatment_function",
    "function"
]).astype(str).str.strip()

rtt_clean["incomplete_pathways_total"] = pd.to_numeric(
    numeric_clean(coalesce_columns(rtt, [
        "total_number_of_incomplete_pathways",
        "total_incomplete_pathways",
        "incomplete_pathways_total"
    ])),
    errors="coerce"
).fillna(0)

rtt_clean["within_18_weeks"] = pd.to_numeric(
    numeric_clean(coalesce_columns(rtt, [
        "total_within_18_weeks",
        "within_18_weeks",
        "total_number_within_18_weeks"
    ])),
    errors="coerce"
).fillna(0)

rtt_clean["over_18_weeks"] = (
    rtt_clean["incomplete_pathways_total"] - rtt_clean["within_18_weeks"]
).clip(lower=0)

# 6. Filter, aggregate, engineer RTT metrics and save clean file


# ------------------------------------------------------------------------
rtt_clean = rtt_clean.dropna(subset=["month_start"])

rtt_clean = rtt_clean[
    rtt_clean["commissioner_code"].notna()
    & (rtt_clean["commissioner_code"].str.lower() != "nan")
    & (rtt_clean["commissioner_code"].str.strip() != "")
]

rtt_clean = rtt_clean[
    ~(
        (rtt_clean["commissioner_name"].str.upper().str.strip() == "NHS ENGLAND")
        | (rtt_clean["commissioner_name"].str.upper().str.strip() == "ENGLAND")
        | (rtt_clean["commissioner_name"].str.upper().str.strip() == "TOTAL")
        | (rtt_clean["treatment_function"].str.upper().str.strip() == "TOTAL")
    )
]

rtt_clean = rtt_clean[
    rtt_clean["incomplete_pathways_total"] > 0
]

fact_rtt = (
    rtt_clean
    .groupby(
        [
            "month_start",
            "commissioner_code",
            "commissioner_name",
            "treatment_function_code",
            "treatment_function"
        ],
        as_index=False
    )
    .agg(
        incomplete_pathways_total=("incomplete_pathways_total", "sum"),
        within_18_weeks=("within_18_weeks", "sum"),
        over_18_weeks=("over_18_weeks", "sum")
    )
)

fact_rtt["pct_within_18_weeks"] = np.where(
    fact_rtt["incomplete_pathways_total"] > 0,
    fact_rtt["within_18_weeks"] / fact_rtt["incomplete_pathways_total"],
    np.nan
)

fact_rtt["pct_over_18_weeks"] = np.where(
    fact_rtt["incomplete_pathways_total"] > 0,
    fact_rtt["over_18_weeks"] / fact_rtt["incomplete_pathways_total"],
    np.nan
)

fact_rtt["rtt_18_week_gap"] = fact_rtt["over_18_weeks"]

def financial_year(d):
    y = d.year
    return f"{y}/{str(y + 1)[-2:]}" if d.month >= 4 else f"{y - 1}/{str(y)[-2:]}"

fact_rtt["financial_year"] = fact_rtt["month_start"].apply(financial_year)
fact_rtt["year"] = fact_rtt["month_start"].dt.year
fact_rtt["month_number"] = fact_rtt["month_start"].dt.month
fact_rtt["month_name"] = fact_rtt["month_start"].dt.strftime("%b")
fact_rtt["quarter"] = fact_rtt["month_start"].dt.to_period("Q").astype(str)

fact_rtt = fact_rtt[
    [
        "month_start",
        "financial_year",
        "year",
        "quarter",
        "month_number",
        "month_name",
        "commissioner_code",
        "commissioner_name",
        "treatment_function_code",
        "treatment_function",
        "incomplete_pathways_total",
        "within_18_weeks",
        "over_18_weeks",
        "pct_within_18_weeks",
        "pct_over_18_weeks",
        "rtt_18_week_gap"
    ]
]

rtt_out_path = cleaned / "fact_rtt_monthly_clean.csv"
fact_rtt.to_csv(rtt_out_path, index=False)

print("Saved RTT clean file:")
print(rtt_out_path)
print("Rows:", len(fact_rtt))

# 7. Validate RTT output


# ------------------------------------------------------------------------
fact_rtt = pd.read_csv(cleaned / "fact_rtt_monthly_clean.csv")
fact_rtt["month_start"] = pd.to_datetime(fact_rtt["month_start"])

print("--- RTT FACT TABLE CHECK ---")
print("Rows:", len(fact_rtt))
print("Columns:", len(fact_rtt.columns))

print("\nDuplicate month + commissioner_code + treatment_function rows:")
print(fact_rtt.duplicated(["month_start", "commissioner_code", "treatment_function"]).sum())

print("\nDate range:")
print(fact_rtt["month_start"].min().date(), "to", fact_rtt["month_start"].max().date())

print("\nNumber of months:")
print(fact_rtt["month_start"].nunique())

expected_months = pd.date_range("2019-10-01", "2025-09-01", freq="MS")
actual_months = pd.to_datetime(fact_rtt["month_start"].drop_duplicates()).sort_values()
missing_months = sorted(set(expected_months) - set(actual_months))

print("\nExpected months:", len(expected_months))
print("Actual months:", len(actual_months))
print("Missing months:", missing_months)

print("\nMissing values in key fields:")
print(fact_rtt[
    [
        "month_start",
        "commissioner_code",
        "treatment_function",
        "incomplete_pathways_total",
        "within_18_weeks",
        "over_18_weeks"
    ]
].isna().sum())

print("\nTotals:")
print("Incomplete pathways:", fact_rtt["incomplete_pathways_total"].sum())
print("Within 18 weeks:", fact_rtt["within_18_weeks"].sum())
print("Over 18 weeks:", fact_rtt["over_18_weeks"].sum())

print("\nOverall pct within 18 weeks:")
print(fact_rtt["within_18_weeks"].sum() / fact_rtt["incomplete_pathways_total"].sum())

print("\nFiles in cleaned folder:")
for file in cleaned.glob("*"):
    print(file.name)
