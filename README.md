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
