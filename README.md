# nhs-ers-booking-gap-analysis
End-to-end NHS e-Referral Service analytics project using Python and Tableau to analyse referral demand, booking absorption, appointment slot pressure and bottleneck archetypes across regions and specialties.
Data belongs to the original public data providers. This repository uses publicly available NHS and ONS data sources for educational and portfolio purposes.
Raw NHS files are not stored in this repository due to volume and file size. Source links are provided in docs/data_sources.md. Processed analysis-ready datasets are included for reproducibility.

# NHS e-RS Booking Gap Analysis

## Project Overview

This project analyses NHS e-Referral Service open data to examine where referral demand does not fully convert into booked appointments. The analysis focuses on booking absorption, appointment slot pressure, demand-to-booking gaps, regional bottlenecks, specialty-level pressure and bottleneck archetypes.

The final Tableau story identifies a hidden access-pressure signal before patients appear in downstream waiting-list measures: referral demand entering e-RS is not always absorbed into booked appointments.

## Key Question

Where is NHS referral demand not converting into booked appointments, and which regions, specialties and bottleneck types should be prioritised for intervention?

## Key Findings

1. Referral demand is not evenly absorbed into bookings across time, region and specialty.
2. A small number of local service combinations account for a disproportionate share of unabsorbed demand.
3. Orthopaedics, 2WW and selected high-volume specialties appear repeatedly among the largest contributors to the demand-to-booking gap.
4. Regional averages hide local access risk, especially where low booking absorption combines with high appointment-slot pressure.
5. Different bottleneck archetypes require different operational responses rather than one generic capacity fix.

## Dashboard Story

The Tableau dashboard is organised into three story pages:

### Page 1: The hidden gap before the waiting list
Shows the national demand-to-booking gap and booking absorption trend.

### Page 2: Where the booking gap concentrates
Shows concentration of unabsorbed demand by local service combinations and specialties.

### Page 3: Where intervention should be escalated first
Shows capacity escalation priorities, bottleneck archetypes and regional hotspot patterns.

## Tools Used

- Python
- pandas
- NumPy
- Tableau Public
- Jupyter Notebook
- NHS Open Data
- ONS Geography Lookup

## Repository Structure

```text
data/
notebooks/
src/
tableau/
docs/
assets/
