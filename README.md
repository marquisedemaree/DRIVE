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
<img width="1463" height="699" alt="Screenshot 2026-07-30 at 4 48 35 PM" src="https://github.com/user-attachments/assets/ba0fb833-d516-4392-8ca4-75a032215812"/>

Event Overview summarizes vehicle dynamics at the moment of disengagement. During this stage the system identifies records defined by an Autopilot state transition from 'ON' to 'OFF'.

The dashboard reports statistics for detected events:
| Metric | Description |
|--------|-------------|
| **Number of Events** | Total number of Autopilot disengagement events detected in the telemetry dataset. |
| **Average Speed (km/h)** | Mean vehicle speed at the moment of Autopilot disengagement across all detected events. |
| **Average Longitudinal Acceleration (g)** | Braking/acceleration at the moment of disengagement. |
| **Average Lateral Acceleration (g)** | Turning at the moment of disengagement. |

## Aggregate Scenario Analysis
<img width="1464" height="571" alt="Screenshot 2026-07-30 at 4 49 02 PM" src="https://github.com/user-attachments/assets/705f02fb-09ba-4f5f-ad44-be649a9c5455"/>

Aggregate Scenario Analysis expands each disengagement by extracting five seconds of telemetry from before and after each event. The dashboard visualizes an aggregate of all scenarios to reveal overall trends.

## Critical Insights
<img width="1461" height="369" alt="Screenshot 2026-07-30 at 3 49 28 PM" src="https://github.com/user-attachments/assets/2baf68f5-9ba2-4537-b0aa-664d0ea6b592"/>

Critical Insights applies configurable thresholds to identify the most significant Autopilot disengagements.

The overview assesses the frequency of aggressive corrective action:
| Metric | Description |
|--------|-------------|
| **Harsh Braking Threshold** | Longitudinal acceleration threshold used to identify harsh braking events. |
| **Hard Turning Threshold** | Lateral acceleration threshold used to identify hard turning events. |
| **Critical Findings** | Total number of scenarios that exceeded one or more thresholds. |
| **Scenarios with Hard Braking** | Percentage of analyzed scenarios containing at least one harsh braking event after disengagement. |
| **Scenarios with Hard Turning** | Percentage of analyzed scenarios containing at least one hard turning event after disengagement. |

## Critical Findings Table
<img width="1461" height="419" alt="Screenshot 2026-07-30 at 4 00 00 PM" src="https://github.com/user-attachments/assets/1a732a25-e5e8-42f9-9352-9c17b319c14d"/>

The Critical Findings Table lists every critical scenario identified by the threshold analysis, along with metrics summaries. 

This sortable table allows for the selection of a single scenario for further analysis in the following section:
| Column | Description |
|--------|-------------|
| **Scenario ID** | Unique identifier for each driving scenario. |
| **Drive ID** | Identifier of the source drive containing the disengagement event. |
| **Disengagement Timestamp** | Timestamp at which Autopilot disengaged. |
| **Speed (km/h)** | Vehicle speed at the moment of disengagement. |
| **Finding Type** | Classification of the critical event (Harsh Braking, Hard Turning, or both). |
| **Peak Braking (g)** | Maximum longitudinal braking recorded after disengagement. |
| **Peak Lateral Acceleration (g)** | Maximum lateral acceleration recorded after disengagement. |

## Scenario Drill-Down
<img width="1460" height="777" alt="Screenshot 2026-07-30 at 4 49 46 PM" src="https://github.com/user-attachments/assets/590ad19b-5bcb-47a7-b853-c243d99086e5" />

Scenario Drill-Down provides a detailed view of a single critical scenario selected from the Critical Findings Table. Metadata is provided for the scenario and includes classification, disengagement timestamp, and peak vehicle dynamics.

This section reconstructs the full sequence of vehicle dynamics surrounding a single Autopilot disengagement. The dashboard visualizes a full telemetry timeline showing the transition from Autopilot to driver intervention.

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
