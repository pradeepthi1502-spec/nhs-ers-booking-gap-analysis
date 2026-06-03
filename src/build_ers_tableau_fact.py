"""
01 ers tableau fact pipeline

Converted from the project notebook for the NHS e-RS Booking Gap Analysis GitHub portfolio project.
Upload this file inside the src/ folder.
"""


# 01 e-RS Tableau Fact Pipeline
# 
# Structured from the original uploaded notebook. Code blocks are copied from the original file.


# ------------------------------------------------------------------------
import pandas as pd
import numpy as np
from pathlib import Path

# 1. Set your Mac iCloud project folder


# ------------------------------------------------------------------------
base = Path("/Users/pradeepthikurapati/Library/Mobile Documents/com~apple~CloudDocs/e-rs data capstone")

print("Base folder exists:", base.exists())
print("Base folder:", base)

# Input files in your iCloud folder
ers_path = base / "ers_processed_monthly_org_specialty.csv"
lookup_path = base / "Sub_ICB_Locations_to_Integrated_Care_Boards_to_NHS_England_(Region)_(2024)_Lookup_in_EN copy.csv"

print("e-RS file exists:", ers_path.exists())
print("Lookup file exists:", lookup_path.exists())

# Output folder
cleaned = base / "cleaned_nhs_dashboard"
cleaned.mkdir(exist_ok=True)

print("Cleaned output folder:", cleaned)

# 2. Load files


# ------------------------------------------------------------------------
ers = pd.read_csv(ers_path, dtype={"org_code": str})
lookup_raw = pd.read_csv(lookup_path, dtype=str)

print("e-RS shape:", ers.shape)
print("Lookup shape:", lookup_raw.shape)

# 3. Clean geography lookup


# ------------------------------------------------------------------------
dim_org = (
    lookup_raw.rename(columns={
        "SICBL24CDH": "org_code",
        "SICBL24CD": "sub_icb_full_code",
        "SICBL24NM": "sub_icb_name",
        "ICB24CD": "icb_code",
        "ICB24CDH": "icb_short_code",
        "ICB24NM": "icb_name",
        "NHSER24CD": "region_code",
        "NHSER24CDH": "region_short_code",
        "NHSER24NM": "region_name",
    })
    [[
        "org_code",
        "sub_icb_full_code",
        "sub_icb_name",
        "icb_code",
        "icb_short_code",
        "icb_name",
        "region_code",
        "region_short_code",
        "region_name"
    ]]
)

for col in dim_org.columns:
    dim_org[col] = dim_org[col].astype(str).str.strip()

dim_org = dim_org.drop_duplicates(subset=["org_code"], keep="first")

# 4. Clean e-RS


# ------------------------------------------------------------------------
ers["month"] = pd.to_datetime(ers["month"], errors="coerce")
ers["month_start"] = ers["month"].values.astype("datetime64[M]")

ers["org_code"] = ers["org_code"].astype(str).str.strip().str.upper()
ers["org_name_raw"] = ers["org_name"].astype(str).str.strip()
ers["specialty"] = ers["specialty"].astype(str).str.strip()

for col in ["referrals", "bookings", "appointment_slot_issues"]:
    ers[col] = pd.to_numeric(ers[col], errors="coerce").fillna(0).astype(int)

# Keep latest org name as fallback for unmapped older codes
latest_org_name = (
    ers.sort_values("month_start")
       .groupby("org_code", as_index=False)
       .tail(1)[["org_code", "org_name_raw"]]
       .drop_duplicates("org_code")
)

# 5. Aggregate to clean Tableau grain


# ------------------------------------------------------------------------
# This removes the July 2022 CCG/ICB duplicate issue.

fact_ers = (
    ers.groupby(["month_start", "org_code", "specialty"], as_index=False)
       .agg(
           referrals=("referrals", "sum"),
           bookings=("bookings", "sum"),
           appointment_slot_issues=("appointment_slot_issues", "sum")
       )
)

# 6. Add date fields


# ------------------------------------------------------------------------
def financial_year(d):
    y = d.year
    if d.month >= 4:
        return f"{y}/{str(y + 1)[-2:]}"
    else:
        return f"{y - 1}/{str(y)[-2:]}"

fact_ers["financial_year"] = fact_ers["month_start"].apply(financial_year)
fact_ers["year"] = fact_ers["month_start"].dt.year
fact_ers["month_number"] = fact_ers["month_start"].dt.month
fact_ers["month_name"] = fact_ers["month_start"].dt.strftime("%b")
fact_ers["quarter"] = fact_ers["month_start"].dt.to_period("Q").astype(str)

# 7. Add geography


# ------------------------------------------------------------------------
fact_ers = fact_ers.merge(dim_org, on="org_code", how="left")
fact_ers = fact_ers.merge(latest_org_name, on="org_code", how="left")

fact_ers["mapping_status"] = np.where(
    fact_ers["icb_name"].notna(),
    "Mapped to 2024 Sub-ICB lookup",
    np.where(
        fact_ers["org_name_raw"].str.contains("UNKNOWN", case=False, na=False),
        "Unknown org code",
        "Unmapped legacy/hub org code"
    )
)

fact_ers["display_org_name"] = fact_ers["sub_icb_name"].fillna(fact_ers["org_name_raw"])

# 8. Create KPIs


# ------------------------------------------------------------------------
fact_ers["demand_to_booking_gap"] = fact_ers["referrals"] - fact_ers["bookings"]

# Positive gap is useful for risk scoring because negative gaps should not reduce clarity
fact_ers["positive_demand_gap"] = fact_ers["demand_to_booking_gap"].clip(lower=0)

fact_ers["booking_absorption_rate"] = np.where(
    fact_ers["referrals"] > 0,
    fact_ers["bookings"] / fact_ers["referrals"],
    np.nan
)

fact_ers["absorption_weakness"] = np.where(
    fact_ers["referrals"] > 0,
    (1 - fact_ers["booking_absorption_rate"]).clip(lower=0),
    np.nan
)

fact_ers["asi_rate_per_10000"] = np.where(
    fact_ers["referrals"] > 0,
    fact_ers["appointment_slot_issues"] / fact_ers["referrals"] * 10000,
    np.nan
)

fact_ers["bottleneck_severity_index"] = (
    fact_ers["asi_rate_per_10000"].fillna(0) * np.log1p(fact_ers["referrals"])
)

# 9. Capacity escalation priority score


# ------------------------------------------------------------------------
fact_ers["asi_rate_rank"] = fact_ers["asi_rate_per_10000"].fillna(0).rank(pct=True)
fact_ers["demand_gap_rank"] = fact_ers["positive_demand_gap"].fillna(0).rank(pct=True)
fact_ers["weak_absorption_rank"] = fact_ers["absorption_weakness"].fillna(0).rank(pct=True)

fact_ers["capacity_escalation_priority_score"] = (
    0.40 * fact_ers["asi_rate_rank"]
    + 0.30 * fact_ers["demand_gap_rank"]
    + 0.30 * fact_ers["weak_absorption_rank"]
)

fact_ers["risk_tier"] = pd.cut(
    fact_ers["capacity_escalation_priority_score"],
    bins=[-0.01, 0.50, 0.75, 0.90, 1.01],
    labels=["Monitor", "Review", "High Risk", "Escalate"]
)

# 10. Reorder useful columns


# ------------------------------------------------------------------------
final_cols = [
    "month_start",
    "financial_year",
    "year",
    "quarter",
    "month_number",
    "month_name",
    "org_code",
    "display_org_name",
    "mapping_status",
    "sub_icb_full_code",
    "sub_icb_name",
    "icb_code",
    "icb_short_code",
    "icb_name",
    "region_code",
    "region_short_code",
    "region_name",
    "specialty",
    "referrals",
    "bookings",
    "appointment_slot_issues",
    "demand_to_booking_gap",
    "positive_demand_gap",
    "booking_absorption_rate",
    "absorption_weakness",
    "asi_rate_per_10000",
    "bottleneck_severity_index",
    "capacity_escalation_priority_score",
    "risk_tier"
]

fact_ers = fact_ers[final_cols]

# 11. Save clean files


# ------------------------------------------------------------------------
fact_path = cleaned / "fact_ers_monthly_clean.csv"
dim_path = cleaned / "dim_org_lookup_clean.csv"

fact_ers.to_csv(fact_path, index=False)
dim_org.to_csv(dim_path, index=False)

print("\nSaved clean files:")
print(fact_path)
print(dim_path)
