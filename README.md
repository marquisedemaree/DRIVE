# DRIVE
DRIVE - Data Reporting Infrastructure for Vehicle Events<br>
*Data engineering platform for analyzing vehicle telemetry to measure self-driving performance.*

**Date Source:** Tesla Model 3 Autopilot On-road dataset.<br>
**Purpose:** Demonstrate how real vehicle telemetry can be sourced, transformed, analyzed, packaged into useful datasets, and turned into actionable engineering insight.

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
