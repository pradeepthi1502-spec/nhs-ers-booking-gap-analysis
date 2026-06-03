"""
04 cwt cleaning pipeline

Converted from the project notebook for the NHS e-RS Booking Gap Analysis GitHub portfolio project.
Upload this file inside the src/ folder.
"""


# 04 Cancer Waiting Times Cleaning Pipeline
# 
# Code copied from the original uploaded notebook. The final corrected organisation-key approach is used.


# 1. Set paths and find CWT files


# ------------------------------------------------------------------------
import pandas as pd
import numpy as np
import re
from pathlib import Path

base = Path("/Users/pradeepthikurapati/Library/Mobile Documents/com~apple~CloudDocs/e-rs data capstone")
cleaned = base / "cleaned_nhs_dashboard"
cleaned.mkdir(exist_ok=True)

cwt_files = sorted([
    f for f in base.glob("CWT-CRS*.xlsx")
    if "ICB-Sub-Location" in f.name
    and not f.name.startswith("~$")
])

print("CWT files found:", len(cwt_files))
for f in cwt_files:
    print("-", f.name)

# 2. Define helper functions


# ------------------------------------------------------------------------
def clean_col(c):
    c = str(c).strip().lower()
    c = c.replace("%", "pct")
    c = c.replace("-", "_")
    c = c.replace("/", "_")
    c = re.sub(r"[^a-z0-9]+", "_", c)
    return c.strip("_")

def numeric_clean(s):
    return (
        s.astype(str)
         .str.replace(",", "", regex=False)
         .str.replace("%", "", regex=False)
         .str.strip()
         .replace(["nan", "None", "-", "", "*", "x", "suppressed", "NA", "N/A"], np.nan)
    )

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

def parse_month_from_year_month(year_value, month_value):
    year = pd.to_numeric(year_value, errors="coerce")
    
    if pd.isna(year):
        return pd.NaT
    
    year = int(year)
    m = str(month_value).strip().lower()
    
    if m.isdigit():
        month = int(m)
    else:
        month = month_map.get(m[:3], np.nan)
    
    if pd.isna(month):
        return pd.NaT
    
    return pd.Timestamp(year, int(month), 1)

def split_org_code_name(x):
    """
    Handles values like:
    '00C NHS DARLINGTON CCG'
    '00C - NHS DARLINGTON CCG'
    'NHS BIRMINGHAM AND SOLIHULL ICB - 15E'
    If no clear code exists, keeps the full text as name.
    """
    if pd.isna(x):
        return pd.Series([np.nan, np.nan])
    
    s = str(x).strip()
    
    # Code at start, e.g. 00C NHS SOMETHING or 15E - NHS SOMETHING
    m_start = re.match(r"^([A-Z0-9]{2,5})\s*[-:]*\s*(.+)$", s)
    if m_start:
        possible_code = m_start.group(1)
        possible_name = m_start.group(2).strip()
        
        # Avoid treating NHS as a code
        if possible_code.upper() != "NHS":
            return pd.Series([possible_code.upper(), possible_name])
    
    # Code at end, e.g. NHS SOMETHING - 00C
    m_end = re.match(r"^(.+?)\s*[-:]\s*([A-Z0-9]{2,5})$", s)
    if m_end:
        return pd.Series([m_end.group(2).upper(), m_end.group(1).strip()])
    
    return pd.Series([s, s])

# 3. Read and combine CWT files


# ------------------------------------------------------------------------
all_cwt = []
failed_cwt = []

for file in cwt_files:
    try:
        df = pd.read_excel(
            file,
            sheet_name="CWT CRS ICB SubLocation Extract",
            header=0,
            dtype=str,
            engine="openpyxl"
        )
        
        df.columns = [clean_col(c) for c in df.columns]
        df["source_file"] = file.name
        
        all_cwt.append(df)
        
    except Exception as e:
        failed_cwt.append((file.name, repr(e)))

print("CWT files successfully read:", len(all_cwt))
print("CWT failed files:", len(failed_cwt))

if failed_cwt:
    print("\nFailed files:")
    for name, error in failed_cwt:
        print(name, "=>", error)

if len(all_cwt) == 0:
    raise ValueError("No CWT files were read.")

cwt_raw = pd.concat(all_cwt, ignore_index=True)

print("\nRaw CWT shape:", cwt_raw.shape)
print("\nColumns:")
print(cwt_raw.columns.tolist())

print(cwt_raw.head(10))

# 4. Build CWT working table with corrected organisation key


# ------------------------------------------------------------------------
import pandas as pd
import numpy as np
import re
from pathlib import Path

base = Path("/Users/pradeepthikurapati/Library/Mobile Documents/com~apple~CloudDocs/e-rs data capstone")
cleaned = base / "cleaned_nhs_dashboard"
cleaned.mkdir(exist_ok=True)

def numeric_clean(s):
    return (
        s.astype(str)
         .str.replace(",", "", regex=False)
         .str.replace("%", "", regex=False)
         .str.strip()
         .replace(["nan", "None", "-", "", "*", "x", "suppressed", "NA", "N/A"], np.nan)
    )

def clean_org_key(x):
    """
    Uses full ICB Sub Location text as the stable key.
    This avoids fake keys like 00, 01, 02.
    """
    if pd.isna(x):
        return np.nan
    
    s = str(x).strip()
    s = re.sub(r"\s+", " ", s)
    return s.upper()

def clean_org_name(x):
    if pd.isna(x):
        return np.nan
    
    s = str(x).strip()
    s = re.sub(r"\s+", " ", s)
    return s

cwt = cwt_raw.copy()

fact_cwt_work = pd.DataFrame()

# Period is already clean in your file
fact_cwt_work["month_start"] = (
    pd.to_datetime(cwt["period"], errors="coerce")
      .dt.to_period("M")
      .dt.to_timestamp()
)

# IMPORTANT FIX: do not split ICB Sub Location
fact_cwt_work["icb_sub_location_code"] = cwt["icb_sub_location"].apply(clean_org_key)
fact_cwt_work["icb_sub_location_name"] = cwt["icb_sub_location"].apply(clean_org_name)

fact_cwt_work["cancer_standard"] = cwt["standard"].astype(str).str.strip()
fact_cwt_work["sub_category"] = cwt["sub_category"].astype(str).str.strip()

fact_cwt_work["eligible_patients"] = pd.to_numeric(
    numeric_clean(cwt["total"]),
    errors="coerce"
).fillna(0)

fact_cwt_work["patients_meeting_standard"] = pd.to_numeric(
    numeric_clean(cwt["within_standard"]),
    errors="coerce"
).fillna(0)

fact_cwt_work["breach_count"] = pd.to_numeric(
    numeric_clean(cwt["breaches"]),
    errors="coerce"
).fillna(0)

fact_cwt_work["sub_category"] = (
    fact_cwt_work["sub_category"]
    .replace(["nan", "NAN", "", "None"], np.nan)
    .fillna("Not specified")
)

print("Rows before filtering:", len(fact_cwt_work))
print("Date range:", fact_cwt_work["month_start"].min(), "to", fact_cwt_work["month_start"].max())
print("Months available:", fact_cwt_work["month_start"].nunique())

print("\nOrg keys sample:")
print(fact_cwt_work["icb_sub_location_code"].dropna().head(10).tolist())

print("\nTotals before filtering:")
print("Eligible patients:", fact_cwt_work["eligible_patients"].sum())
print("Patients meeting standard:", fact_cwt_work["patients_meeting_standard"].sum())
print("Breaches:", fact_cwt_work["breach_count"].sum())

# 5. Filter, aggregate, engineer CWT metrics and save clean file


# ------------------------------------------------------------------------
fact_cwt_filtered = fact_cwt_work[
    (fact_cwt_work["month_start"] >= "2023-10-01")
    & (fact_cwt_work["month_start"] <= "2025-09-01")
].copy()

fact_cwt_filtered = fact_cwt_filtered.dropna(subset=["month_start"])

fact_cwt_filtered = fact_cwt_filtered[
    fact_cwt_filtered["icb_sub_location_code"].notna()
    & (fact_cwt_filtered["icb_sub_location_code"].astype(str).str.lower() != "nan")
    & (fact_cwt_filtered["icb_sub_location_code"].astype(str).str.strip() != "")
]

fact_cwt_filtered = fact_cwt_filtered[
    fact_cwt_filtered["eligible_patients"] > 0
]

# Correct final grain
fact_cwt = (
    fact_cwt_filtered
    .groupby(
        [
            "month_start",
            "icb_sub_location_code",
            "icb_sub_location_name",
            "cancer_standard",
            "sub_category"
        ],
        as_index=False
    )
    .agg(
        eligible_patients=("eligible_patients", "sum"),
        patients_meeting_standard=("patients_meeting_standard", "sum"),
        breach_count=("breach_count", "sum")
    )
)

fact_cwt["performance_pct"] = np.where(
    fact_cwt["eligible_patients"] > 0,
    fact_cwt["patients_meeting_standard"] / fact_cwt["eligible_patients"],
    np.nan
)

def financial_year(d):
    y = d.year
    return f"{y}/{str(y + 1)[-2:]}" if d.month >= 4 else f"{y - 1}/{str(y)[-2:]}"

fact_cwt["financial_year"] = fact_cwt["month_start"].apply(financial_year)
fact_cwt["year"] = fact_cwt["month_start"].dt.year
fact_cwt["month_number"] = fact_cwt["month_start"].dt.month
fact_cwt["month_name"] = fact_cwt["month_start"].dt.strftime("%b")
fact_cwt["quarter"] = fact_cwt["month_start"].dt.to_period("Q").astype(str)

fact_cwt = fact_cwt[
    [
        "month_start",
        "financial_year",
        "year",
        "quarter",
        "month_number",
        "month_name",
        "icb_sub_location_code",
        "icb_sub_location_name",
        "cancer_standard",
        "sub_category",
        "eligible_patients",
        "patients_meeting_standard",
        "breach_count",
        "performance_pct"
    ]
]

cwt_out_path = cleaned / "fact_cwt_monthly_clean.csv"
fact_cwt.to_csv(cwt_out_path, index=False)

print("Saved fixed CWT clean file:")
print(cwt_out_path)
print("Rows:", len(fact_cwt))

# 6. Validate CWT output


# ------------------------------------------------------------------------
fact_cwt = pd.read_csv(cleaned / "fact_cwt_monthly_clean.csv")
fact_cwt["month_start"] = pd.to_datetime(fact_cwt["month_start"], errors="coerce")

print("--- CWT FACT TABLE CHECK ---")
print("Rows:", len(fact_cwt))
print("Columns:", len(fact_cwt.columns))

print("\nDuplicate month + org + standard + sub-category rows:")
print(fact_cwt.duplicated([
    "month_start",
    "icb_sub_location_code",
    "cancer_standard",
    "sub_category"
]).sum())

print("\nDate range:")
print(fact_cwt["month_start"].min().date(), "to", fact_cwt["month_start"].max().date())

print("\nNumber of months:")
print(fact_cwt["month_start"].nunique())

expected_months = pd.date_range("2023-10-01", "2025-09-01", freq="MS")
actual_months = pd.to_datetime(fact_cwt["month_start"].drop_duplicates()).sort_values()
missing_months = sorted(set(expected_months) - set(actual_months))

print("\nExpected months:", len(expected_months))
print("Actual months:", len(actual_months))
print("Missing months:", missing_months)

print("\nMissing values in key fields:")
print(fact_cwt[
    [
        "month_start",
        "icb_sub_location_code",
        "cancer_standard",
        "eligible_patients",
        "patients_meeting_standard",
        "performance_pct"
    ]
].isna().sum())

eligible_total = fact_cwt["eligible_patients"].sum()
met_total = fact_cwt["patients_meeting_standard"].sum()

print("\nTotals:")
print("Eligible patients:", eligible_total)
print("Patients meeting standard:", met_total)
print("Breaches:", fact_cwt["breach_count"].sum())

if eligible_total > 0:
    print("\nOverall cancer performance:")
    print(met_total / eligible_total)

print("\nCancer standards found:")
print(fact_cwt["cancer_standard"].value_counts())

print("\nRows per month:")
print(fact_cwt.groupby("month_start").size())

print("\nFiles in cleaned folder:")
for file in cleaned.glob("*"):
    print(file.name)
