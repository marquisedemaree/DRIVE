# DRIVE
## DRIVE - Data Reporting Infrastructure for Vehicle Events

DRIVE is an end-to-end data engineering pipeline that analyzes Tesla Autopilot disengagement events to evaluate self-driving performance. From ingesting raw telemetry to visualizing metrics through a dashboard, the system provides insight into questions such as:
- Under what conditions do Autopilot disengagements occur?
- What are the vehicle dynamics at the moment of disengagement?
- How does Autopilot behave prior to disengagement?
- How does the driver respond after disengagement?

Combining these observations into a temporal analysis provides context for each disengagement event. This allows engineers to identify recurring patterns, investigate notable scenarios, and better understand the relationship between Autopilot behavior and driver intervention. 

**Data Source:** Tesla Model 3 Autopilot On-road: https://livewire.energy.gov/ds/ld-cav-functionality/tesla-model3<br>

## Pipeline Overview
<img width="1458" height="263" alt="Screenshot 2026-07-30 at 12 38 58 PM" src="https://github.com/user-attachments/assets/678b5e46-a169-4cb4-9a60-b0eceb9716f6" />
Pipeline Overview summarizes the ingestion stage and provides visibility into the transformation of raw telemetry into a dataset for analysis. When the pipeline executes, it:
1. Reads CSV files located in 'DRIVE/data/tesla-model3'.
1. Validates required fields and removes malformed records.
1. Produces a SQLite telemetry table for downstream analysis.
1. Records processing statistics for monitoring data quality.

The dashboard reports four metrics:
| Metric | Description |
|--------|-------------|
| **Files Processed** | Number of telemetry CSV files successfully processed during pipeline execution. |
| **Rows Ingested** | Total number of raw telemetry records read from the input files. |
| **Rows Served** | Number of validated telemetry records written to the SQLite database for downstream analysis. |
| **Rows Dropped** | Number of records excluded during validation because they were incomplete, malformed, or otherwise invalid. |

## Usage
Run the full DRIVE pipeline: `python main.py`

**This will:**
- Start the FastAPI backend and serve the React dashboard.
- Process vehicle telemetry for analysis.
- Calculate fleet performance metrics and identify driving events.
- Generate actionable insights from fleet data.
- Identify and evaluate interesting driving scenarios and datasets.
- Launch the interactive dashboard for exploring fleet metrics, events, scenarios, datasets, and insights.

## Features

### 1. Fleet Telemetry Pipeline
Ingests telemetry, validates and transforms it, organizes it into datasets, and serves those datasets to downstream analytics and visualization tools.

### 2. Metrics Engine
Derives meaningful driving events and performance metrics from telemetry, then surfaces trends, patterns, and notable behaviors that support engineering decisions and deeper investigation.

### 3. Fleet Data SDK + Automated Analysis Workflows
Provides reusable tools that make common fleet-data tasks faster and more consistent, including querying telemetry, calculating metrics, retrieving events, generating analyses, and creating derived datasets.

### 4. Scenario Miner + Dataset Evaluation Framework
Identify and organize interesting driving scenarios, create targeted datasets around specific behaviors or conditions, and evaluate those datasets for coverage, diversity, redundancy, and usefulness so selection criteria can improve over time.

### 5. Interactive Fleet Intelligence Dashboard
An interactive analytical interface that moves from high-level metrics to event categories, individual drives, specific scenarios, and derived datasets so users can understand what changed, where it occurred, and what deserves attention.
