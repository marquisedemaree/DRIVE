# DRIVE
### Data Reporting Infrastructure for Vehicle Events

DRIVE is an end-to-end data engineering pipeline that analyzes Tesla Autopilot disengagement events for self-driving performance evaluation. From ingesting raw telemetry to visualizing metrics through a dashboard, the system provides insight into questions such as:
- Under what conditions do Autopilot disengagements occur?
- How does Autopilot behave prior to disengagement?
- How does the driver respond after disengagement?

Combining these observations into a temporal analysis provides context for each event and allows engineers to better understand the relationship between Autopilot behavior and driver intervention. 

**Data Source:** Tesla Model 3 Autopilot On-road: https://livewire.energy.gov/ds/ld-cav-functionality/tesla-model3<br>

## Setup

### Prerequisites

- Git
- Docker

### 1. Clone the repository

```bash
git clone https://github.com/marquisedemaree/DRIVE.git
cd DRIVE
```
### 2. Build and start DRIVE

```bash
docker compose up --build
```

Docker will:

- Build the React frontend
- Install Python dependencies
- Execute the analytics pipeline
- Generate the SQLite analytics database
- Start the FastAPI server

### 3. Open the dashboard

Open your browser and navigate to:

```
http://localhost:8000
```

### Stopping DRIVE

```bash
docker compose down
```

## Features

### Pipeline Overview
<img width="1458" height="263" alt="Screenshot 2026-07-30 at 12 38 58 PM" src="https://github.com/user-attachments/assets/678b5e46-a169-4cb4-9a60-b0eceb9716f6"/>

Pipeline Overview summarizes the ingestion stage and provides visibility into the transformation of raw telemetry into a dataset for analysis. The dashboard reports statistics for monitoring data volume and quality.

### Event Overview
<img width="1463" height="699" alt="Screenshot 2026-07-30 at 4 48 35 PM" src="https://github.com/user-attachments/assets/ba0fb833-d516-4392-8ca4-75a032215812"/>

Event Overview summarizes vehicle dynamics at the moment of disengagement. During this stage the system identifies records defined by an Autopilot state transition from 'ON' to 'OFF'. The dashboard reports statistics for detected events.

### Aggregate Scenario Analysis
<img width="1464" height="571" alt="Screenshot 2026-07-30 at 4 49 02 PM" src="https://github.com/user-attachments/assets/705f02fb-09ba-4f5f-ad44-be649a9c5455"/>

Aggregate Scenario Analysis expands each disengagement by extracting five seconds of telemetry from before and after each event. The dashboard visualizes an aggregate of all scenarios to reveal overall trends.

### Critical Insights
<img width="1461" height="369" alt="Screenshot 2026-07-30 at 3 49 28 PM" src="https://github.com/user-attachments/assets/2baf68f5-9ba2-4537-b0aa-664d0ea6b592"/>

Critical Insights applies configurable thresholds to identify the most significant Autopilot disengagements. The overview assesses the frequency of aggressive corrective action.

### Critical Findings Table
<img width="1461" height="419" alt="Screenshot 2026-07-30 at 4 00 00 PM" src="https://github.com/user-attachments/assets/1a732a25-e5e8-42f9-9352-9c17b319c14d"/>

The Critical Findings Table lists every critical scenario identified by the threshold analysis, along with metrics summaries. This sortable table allows for the selection of a single scenario for further analysis in the following section.

### Scenario Drill-Down
<img width="1460" height="777" alt="Screenshot 2026-07-30 at 4 49 46 PM" src="https://github.com/user-attachments/assets/590ad19b-5bcb-47a7-b853-c243d99086e5" />

Scenario Drill-Down provides a detailed view of a single critical scenario selected from the Critical Findings Table. This section reconstructs the full sequence of vehicle dynamics surrounding a single Autopilot disengagement. The dashboard visualizes a telemetry timeline showing the transition from Autopilot to driver intervention.
