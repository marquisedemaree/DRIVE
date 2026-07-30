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
<img width="1458" height="263" alt="Screenshot 2026-07-30 at 12 38 58 PM" src="https://github.com/user-attachments/assets/678b5e46-a169-4cb4-9a60-b0eceb9716f6"/>

Pipeline Overview summarizes the ingestion stage and provides visibility into the transformation of raw telemetry into a dataset for analysis. When the pipeline executes, it will:
- Read CSV files located in 'DRIVE/data/tesla-model3'.
- Validate required fields and remove malformed records.
- Produce a SQLite telemetry table for downstream analysis.
- Record processing statistics for monitoring data quality.

The dashboard reports four metrics:
| Metric | Description |
|--------|-------------|
| **Files Processed** | Number of telemetry CSV files successfully processed. |
| **Rows Ingested** | Total number of raw telemetry records read from the input files. |
| **Rows Served** | Number of validated telemetry records written to the SQLite database. |
| **Rows Dropped** | Number of invalid records excluded during validation. |

## Event Overview
<img width="1460" height="699" alt="Screenshot 2026-07-30 at 1 11 51 PM" src="https://github.com/user-attachments/assets/4db7a349-c1bf-4360-979c-9478f7d46d37"/>

Event Overview summarizes vehicle dynamics at the moment of disengagement. During this stage the system identifies records defined by an Autopilot state transition from 'ON' to 'OFF'.

The dashboard reports statistics for detected events:
| Metric | Description |
|--------|-------------|
| **Number of Events** | Total number of Autopilot disengagement events detected in the telemetry dataset. |
| **Average Speed (km/h)** | Mean vehicle speed at the moment of Autopilot disengagement across all detected events. |
| **Average Longitudinal Acceleration (g)** | Mean longitudinal acceleration at the moment of disengagement, indicating average braking or acceleration behavior. |
| **Average Lateral Acceleration (g)** | Mean lateral acceleration at the moment of disengagement, indicating average turning behavior. |
| **Speed Distribution** | Histogram showing the distribution of vehicle speeds at the moment of disengagement. |
| **Longitudinal Acceleration Distribution** | Histogram showing the distribution of longitudinal acceleration values at disengagement, highlighting braking and acceleration trends. |
| **Lateral Acceleration Distribution** | Histogram showing the distribution of lateral acceleration values at disengagement, illustrating the range of turning conditions during disengagement events. |

## Aggregate Scenario Analysis
<img width="1461" height="576" alt="Screenshot 2026-07-30 at 1 50 00 PM" src="https://github.com/user-attachments/assets/87f53c77-b48a-4974-bf30-abe3fd8f64d0"/>

Aggregate Scenario Analysis expands each disengagement by extracting five seconds of telemetry from before and after each event.

The dashboard visualizes an aggregate of all scenarios to reveal overall trends:
| Visualization | Description |
|--------------|-------------|
| **Vehicle Speed** | Line chart showing the minimum, average, and maximum vehicle speed across all scenarios relative to the moment of Autopilot disengagement. |
| **Longitudinal Acceleration** | Line chart showing the minimum, average, and maximum longitudinal acceleration before and after disengagement, highlighting braking and acceleration behavior. |
| **Lateral Acceleration** | Line chart showing the minimum, average, and maximum lateral acceleration throughout the scenario window, illustrating steering behavior before and after disengagement. |
| **Disengagement Marker** | Vertical reference line at **0 seconds** indicating the exact moment Autopilot disengaged, providing a common alignment point for all aggregated scenarios. |




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
