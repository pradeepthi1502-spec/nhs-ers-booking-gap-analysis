"""
05 date dimension and validation checks

Converted from the project notebook for the NHS e-RS Booking Gap Analysis GitHub portfolio project.
Upload this file inside the src/ folder.
"""


# 05 Shared Date Dimension and Output Checks
# 
# Code copied from the original uploaded notebook.


# 1. Check expected cleaned files exist


# ------------------------------------------------------------------------
from pathlib import Path
import pandas as pd

base = Path("/Users/pradeepthikurapati/Library/Mobile Documents/com~apple~CloudDocs/e-rs data capstone")
cleaned = base / "cleaned_nhs_dashboard"

expected_files = [
    "fact_ers_monthly_clean.csv",
    "fact_rtt_monthly_clean.csv",
    "fact_dm01_monthly_clean.csv",
    "fact_cwt_monthly_clean.csv",
    "dim_org_lookup_clean.csv",
    "dim_date.csv"
]

print("Files currently in cleaned folder:")
for file in cleaned.glob("*"):
    print("-", file.name)

print("\nExpected file check:")
for file in expected_files:
    path = cleaned / file
    print(file, "=>", path.exists())

# 2. Create shared date dimension


# ------------------------------------------------------------------------
import pandas as pd
from pathlib import Path

base = Path("/Users/pradeepthikurapati/Library/Mobile Documents/com~apple~CloudDocs/e-rs data capstone")
cleaned = base / "cleaned_nhs_dashboard"

def financial_year(d):
    y = d.year
    return f"{y}/{str(y + 1)[-2:]}" if d.month >= 4 else f"{y - 1}/{str(y)[-2:]}"

dim_date = pd.DataFrame({
    "month_start": pd.date_range("2019-10-01", "2025-09-01", freq="MS")
})

dim_date["year"] = dim_date["month_start"].dt.year
dim_date["month_number"] = dim_date["month_start"].dt.month
dim_date["month_name"] = dim_date["month_start"].dt.strftime("%b")
dim_date["quarter"] = dim_date["month_start"].dt.to_period("Q").astype(str)
dim_date["financial_year"] = dim_date["month_start"].apply(financial_year)

dim_date.to_csv(cleaned / "dim_date.csv", index=False)

print("Saved dim_date.csv")

# 3. Validate all cleaned fact tables


# ------------------------------------------------------------------------
import pandas as pd
from pathlib import Path

base = Path("/Users/pradeepthikurapati/Library/Mobile Documents/com~apple~CloudDocs/e-rs data capstone")
cleaned = base / "cleaned_nhs_dashboard"

checks = {
    "e-RS": {
        "file": "fact_ers_monthly_clean.csv",
        "key": ["month_start", "org_code", "specialty"],
        "expected_start": "2019-10-01",
        "expected_end": "2025-09-01"
    },
    "RTT": {
        "file": "fact_rtt_monthly_clean.csv",
        "key": ["month_start", "commissioner_code", "treatment_function"],
        "expected_start": "2019-10-01",
        "expected_end": "2025-09-01"
    },
    "DM01": {
        "file": "fact_dm01_monthly_clean.csv",
        "key": ["month_start", "commissioner_code", "diagnostic_test"],
        "expected_start": "2019-10-01",
        "expected_end": "2025-09-01"
    },
    "CWT": {
        "file": "fact_cwt_monthly_clean.csv",
        "key": ["month_start", "icb_sub_location_code", "cancer_standard", "sub_category"],
        "expected_start": "2023-10-01",
        "expected_end": "2025-09-01"
    }
}

for name, cfg in checks.items():
    path = cleaned / cfg["file"]
    
    print("\n" + "="*60)
    print(name)
    print("="*60)
    
    if not path.exists():
        print("MISSING FILE:", cfg["file"])
        continue
    
    df = pd.read_csv(path)
    df["month_start"] = pd.to_datetime(df["month_start"], errors="coerce")
    
    expected_months = pd.date_range(cfg["expected_start"], cfg["expected_end"], freq="MS")
    actual_months = pd.to_datetime(df["month_start"].dropna().drop_duplicates()).sort_values()
    missing_months = sorted(set(expected_months) - set(actual_months))
    
    print("Rows:", len(df))
    print("Date range:", df["month_start"].min(), "to", df["month_start"].max())
    print("Actual months:", df["month_start"].nunique())
    print("Expected months:", len(expected_months))
    print("Missing months:", missing_months)
    print("Duplicate key rows:", df.duplicated(cfg["key"]).sum())
    print("Missing key values:")
    print(df[cfg["key"]].isna().sum())
