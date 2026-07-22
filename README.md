# DRIVE
DRIVE - Data Reporting Infrastructure for Vehicle Events<br>
*Data engineering platform for analyzing vehicle telemetry to measure self-driving performance.*

## Usage
Run the full DRIVE pipeline: `python main.py`

**This will:**
- Start the FastAPI backend and serve the React dashboard.
- Process vehicle telemetry for analysis.
- Calculate fleet performance metrics and identify driving events.
- Generate actionable insights from fleet data.
- Identify and evaluate interesting driving scenarios and datasets.
- Launch the interactive dashboard for exploring fleet metrics, events, scenarios, datasets, and insights.

**DRIVE includes two complementary operating modes:**
- Current MVP: Analytics Mode - Uses real Tesla Model 3 Autopilot On-road telemetry to demonstrate ingestion, transformation, metrics, analysis, and visualization.
- Upcoming Addition: Scale Mode — Uses simulated fleet telemetry to demonstrate high-volume pipeline observability, reliability, automated recovery, and adaptive data sampling.

## Features

**1. Fleet Telemetry Pipeline:** Ingests telemetry, validates and transforms it, organizes it into datasets, and serves those datasets to downstream analytics and visualization tools.

### Analytics Mode
**Date Source:** Tesla Model 3 Autopilot On-road dataset.<br>
**Purpose:** Demonstrate how real vehicle telemetry can be sourced, transformed, analyzed, packaged into useful datasets, and turned into actionable engineering insight.

**2. Metrics Engine:** Derives meaningful driving events and performance metrics from telemetry, then surfaces trends, patterns, and notable behaviors that support engineering decisions and deeper investigation.

**3. Fleet Data SDK + Automated Analysis Workflows:** Provides reusable tools that make common fleet-data tasks faster and more consistent, including querying telemetry, calculating metrics, retrieving events, generating analyses, and creating derived datasets.

**4. Scenario Miner + Dataset Evaluation Framework:** Identify and organize interesting driving scenarios, create targeted datasets around specific behaviors or conditions, and evaluate those datasets for coverage, diversity, redundancy, and usefulness so selection criteria can improve over time.

**5. Interactive Fleet Intelligence Dashboard:** An interactive analytical interface that moves from high-level metrics to event categories, individual drives, specific scenarios, and derived datasets so users can understand what changed, where it occurred, and what deserves attention.

### Scale Mode
**Date Source:** Simulated fleet telemetry stream<br>
**Purpose:** Demonstrate how the platform behaves under high-volume fleet conditions that cannot be reproduced with the limited public dataset.

**6. Fleet Pipeline Observability & Automated Recovery:** Continuously monitor pipeline health, surface operational problems, record system behavior, and demonstrate automated responses to failures, load spikes, processing delays, and data-quality issues.

**7. Adaptive Fleet Data Collection & Sampling Controller:** Control which simulated telemetry enters the pipeline when incoming data exceeds processing or storage limits, prioritizing rare, underrepresented, or high-value scenarios while reducing redundant common data.
