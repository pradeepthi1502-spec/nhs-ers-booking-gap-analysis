"""
06 rtt dumbbell comparison dataset

Converted from the project notebook for the NHS e-RS Booking Gap Analysis GitHub portfolio project.
Upload this file inside the src/ folder.
"""


# 06 RTT Dumbbell Comparison Dataset
# 
# Structured from the second uploaded notebook. Code blocks are copied from the original file.


# 1. Load RTT clean fact table


# ------------------------------------------------------------------------
import pandas as pd
import numpy as np
from pathlib import Path

base = Path("/Users/pradeepthikurapati/Library/Mobile Documents/com~apple~CloudDocs/e-rs data capstone")
cleaned = base / "cleaned_nhs_dashboard"

rtt_path = cleaned / "fact_rtt_monthly_clean.csv"
rtt = pd.read_csv(rtt_path)

rtt["month_start"] = pd.to_datetime(rtt["month_start"], errors="coerce")

# 2. Clean treatment function names


# ------------------------------------------------------------------------

# Clean treatment function names so "Cardiology" and "Cardiology Service" are treated as one
rtt["treatment_function_clean"] = (
    rtt["treatment_function"]
    .astype(str)
    .str.replace(" Service", "", regex=False)
    .str.strip()
)

# 3. Define baseline and latest comparison windows


# ------------------------------------------------------------------------

# Define comparison windows
baseline = rtt[
    (rtt["month_start"] >= "2019-10-01") &
    (rtt["month_start"] <= "2020-03-01")
].copy()

latest = rtt[
    (rtt["month_start"] >= "2024-04-01") &
    (rtt["month_start"] <= "2025-03-01")
].copy()

# 4. Summarise each period


# ------------------------------------------------------------------------

def summarise_period(df, label, order):
    out = (
        df.groupby("treatment_function_clean", as_index=False)
        .agg(
            incomplete_pathways_total=("incomplete_pathways_total", "sum"),
            within_18_weeks=("within_18_weeks", "sum"),
            over_18_weeks=("over_18_weeks", "sum")
        )
    )
    
    out["pct_within_18_weeks"] = np.where(
        out["incomplete_pathways_total"] > 0,
        out["within_18_weeks"] / out["incomplete_pathways_total"],
        np.nan
    )
    
    out["period_label"] = label
    out["period_order"] = order
    
    return out

baseline_summary = summarise_period(
    baseline,
    "Baseline: Oct 2019-Mar 2020",
    1
)

# 5. Keep treatment functions present in both periods


# ------------------------------------------------------------------------
latest_summary = summarise_period(
    latest,
    "Latest: Apr 2024-Mar 2025",
    2
)

# Keep only treatment functions that exist in both periods
both = (
    baseline_summary[["treatment_function_clean"]]
    .merge(
        latest_summary[["treatment_function_clean"]],
        on="treatment_function_clean",
        how="inner"
    )
)

# 6. Add latest backlog for Tableau sorting


# ------------------------------------------------------------------------

baseline_summary = baseline_summary.merge(both, on="treatment_function_clean", how="inner")
latest_summary = latest_summary.merge(both, on="treatment_function_clean", how="inner")

# Add latest backlog to both rows so Tableau can sort/filter by it
latest_backlog = latest_summary[
    ["treatment_function_clean", "over_18_weeks"]
].rename(columns={"over_18_weeks": "latest_over_18_backlog"})

# 7. Calculate performance change


# ------------------------------------------------------------------------
baseline_summary = baseline_summary.merge(latest_backlog, on="treatment_function_clean", how="left")
latest_summary = latest_summary.merge(latest_backlog, on="treatment_function_clean", how="left")

# Add performance change
change = (
    baseline_summary[["treatment_function_clean", "pct_within_18_weeks"]]
    .rename(columns={"pct_within_18_weeks": "baseline_pct_within_18_weeks"})
    .merge(
        latest_summary[["treatment_function_clean", "pct_within_18_weeks"]]
        .rename(columns={"pct_within_18_weeks": "latest_pct_within_18_weeks"}),
        on="treatment_function_clean",
        how="inner"
    )
)

change["performance_change_pp"] = (
    change["latest_pct_within_18_weeks"] -
    change["baseline_pct_within_18_weeks"]
)

# 8. Combine baseline and latest rows


# ------------------------------------------------------------------------
rtt_dumbbell = pd.concat([baseline_summary, latest_summary], ignore_index=True)

rtt_dumbbell = rtt_dumbbell.merge(
    change[["treatment_function_clean", "baseline_pct_within_18_weeks", "latest_pct_within_18_weeks", "performance_change_pp"]],
    on="treatment_function_clean",
    how="left"
)

# Remove empty/null treatment functions
rtt_dumbbell = rtt_dumbbell[
    rtt_dumbbell["treatment_function_clean"].notna()

# 9. Remove null treatment functions


# ------------------------------------------------------------------------
    & (rtt_dumbbell["treatment_function_clean"].str.lower() != "nan")
    & (rtt_dumbbell["treatment_function_clean"].str.strip() != "")
]

# Save
out_path = cleaned / "fact_rtt_dumbbell_comparison.csv"
rtt_dumbbell.to_csv(out_path, index=False)

# 10. Save RTT dumbbell comparison dataset


# ------------------------------------------------------------------------
print("Saved:", out_path)
print("Rows:", len(rtt_dumbbell))
print("Treatment functions:", rtt_dumbbell["treatment_function_clean"].nunique())

print("\nPeriod counts:")
print(rtt_dumbbell["period_label"].value_counts())

print("\nCheck sample:")
print(rtt_dumbbell.head(20))
