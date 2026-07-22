# DRIVE
DRIVE - Data Reporting Infrastructure for Vehicle Events<br>
*Data engineering platform for analyzing vehicle telemetry to measure self-driving performance.*

## Quick Start
These instructions will help you run DRIVE locally for demo and evaluation.

### Prerequisites
- Git
- Python 3.10+

Not sure if you meet these requirements? Follow this guide: https://github.com/marquisedemaree/prerequisites/blob/main/README.md

### Installation
From the command line:

1. Clone the repository: `git clone https://github.com/marquisedemaree/DRIVE.git`

2. Change the directory to DRIVE: `cd DRIVE`

3. Create a Virtual Environment: `python3 -m venv .venv`

4. Activate Virtual Environment:
    - Mac: `source .venv/bin/activate`
    - Windows: `.venv\Scripts\activate` 

5. Install dependencies: `pip install -r requirements.txt`

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
