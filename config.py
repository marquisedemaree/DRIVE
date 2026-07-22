from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
DATA_DIR = BASE_DIR / "data"
TESLA_MODEL3_DATA_DIR = DATA_DIR / "tesla-model3"

DATABASE_PATH = DATA_DIR / "drive.db"
TELEMETRY_TABLE = "telemetry"
INGESTION_TABLE = "ingestion_runs"
CSV_PATTERN = "*.csv"
SQL_CHUNK_SIZE = 1_000

# Application server settings.
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
APP_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

VALID_MODES = {"analytics", "scale"}

MODE_DESCRIPTIONS = {
    "analytics": (
        "Analyze real Tesla Model 3 Autopilot telemetry, calculate driving "
        "metrics, identify scenarios, and explore derived datasets."
    ),
    "scale": (
        "Simulate fleet-scale telemetry to explore pipeline health, system "
        "reliability, throughput, and adaptive data sampling."
    ),
}

# metrics
EVENTS_TABLE = "driving_events"
DRIVE_METRICS_TABLE = "drive_metrics"
HARD_BRAKING_THRESHOLD_MPS2 = -3.0
RAPID_ACCELERATION_THRESHOLD_MPS2 = 2.5
HIGH_LATERAL_ACCEL_THRESHOLD_MPS2 = 2.5
SHARP_STEERING_RATE_THRESHOLD_DEG_S = 120.0
MIN_EVENT_DURATION_SECONDS = 0.3
EVENT_COOLDOWN_SECONDS = 0.5
