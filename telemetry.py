"""Shared telemetry ingestion, validation, transformation, SQL persistence, and serving utilities."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from config import (
    DATABASE_PATH,
    INGESTION_TABLE,
    SQL_CHUNK_SIZE,
    TELEMETRY_TABLE,
    TESLA_MODEL3_DATA_DIR,
)

# Minimum source fields required to build the canonical analytics dataset.
REQUIRED_COLUMNS = {
    "Time (epoch)",
    "veh_speed (kph)",
    "veh_odometer (km)",
    "gps_latitude (deg)",
    "gps_longitude (deg)",
    "RCM_longitudinalAccel (m/s^2)",
    "RCM_lateralAccel (m/s^2)",
    "veh_steering_angle (deg)",
    "ESP_driverBrakeApply",
    "DAS_autopilotState",
    "BMS_socAvg (per)",
    "# Vehicles",
}

NUMERIC_SOURCE_COLUMNS = [
    "Time (epoch)",
    "Time (abs)",
    "veh_elevation (M)",
    "gps_accuracy (m)",
    "gps_latitude (deg)",
    "gps_longitude (deg)",
    "UI_gpsVehicleHeading (deg)",
    "veh_odometer (km)",
    "veh_speed (kph)",
    "pedal_accel (per)",
    "veh_steering_angle (deg)",
    "veh_steering_speedps (D/S)",
    "RCM_longitudinalAccel (m/s^2)",
    "RCM_lateralAccel (m/s^2)",
    "RCM_verticalAccel (m/s^2)",
    "APP_environmentRainy",
    "APP_environmentSnowy",
    "BMS_packCurrent (A)",
    "BMS_packVoltage (V)",
    "BMS_socAvg (per)",
    "DAS_controlDistance (m)",
    "DAS_setSpeed (kph)",
    "# Vehicles",
]

CANONICAL_COLUMNS = [
    "source_file",
    "drive_id",
    "timestamp",
    "elapsed_seconds",
    "speed_kph",
    "speed_mps",
    "odometer_km",
    "distance_delta_km",
    "latitude",
    "longitude",
    "gps_accuracy_m",
    "heading_deg",
    "elevation_m",
    "longitudinal_accel_mps2",
    "lateral_accel_mps2",
    "vertical_accel_mps2",
    "steering_angle_deg",
    "steering_rate_deg_s",
    "accelerator_pct",
    "brake_applied",
    "autopilot_state",
    "autopilot_state_code",
    "acc_state",
    "aeb_state",
    "road_class",
    "road_class_code",
    "rainy",
    "snowy",
    "battery_soc_pct",
    "battery_pack_current_a",
    "battery_pack_voltage_v",
    "lead_vehicle_distance_m",
    "set_speed_kph",
    "vehicles_detected",
]


@dataclass(frozen=True)
class PipelineResult:
    """Processed telemetry plus data-quality metadata for downstream consumers."""

    data: pd.DataFrame
    files: tuple[str, ...]
    rows_ingested: int
    rows_served: int
    rows_dropped: int
    duplicate_rows_removed: int
    warnings: tuple[str, ...]


def discover_csv_files(
    data_dir: Path = TESLA_MODEL3_DATA_DIR,
) -> list[Path]:
    """Return every CSV file in the configured telemetry directory."""
    if not data_dir.exists():
        return []

    return sorted(
        path
        for path in data_dir.glob("*.csv")
        if path.is_file()
    )


def _split_state(
    series: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """Split source values like 'UNAVAILABLE|1' into readable label and code."""
    text = series.astype("string")
    parts = text.str.rsplit(
        "|",
        n=1,
        expand=True,
    )

    label = parts[0].replace(
        {"": pd.NA}
    )

    code = (
        pd.to_numeric(
            parts[1],
            errors="coerce",
        )
        if parts.shape[1] > 1
        else pd.Series(
            pd.NA,
            index=series.index,
        )
    )

    return label, code


def _truthy_state(
    series: pd.Series,
) -> pd.Series:
    """Convert numeric or enum-like source states into booleans."""
    text = (
        series.astype("string")
        .str.lower()
    )

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    negative = text.str.contains(
        "not_active|not_applying|inactive|off|false",
        regex=True,
        na=False,
    )

    positive = (
        text.str.contains(
            "active|applying|on|true",
            regex=True,
            na=False,
        )
        & ~negative
    )

    return positive | (
        numeric.fillna(0).ne(0)
        & ~negative
    )


def _elapsed_seconds(
    series: pd.Series,
) -> pd.Series:
    """Convert HH:MM:SS elapsed-time strings to seconds."""
    return pd.to_timedelta(
        series,
        errors="coerce",
    ).dt.total_seconds()


def ingest_csv_files(
    files: Iterable[Path],
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Read source CSV files and preserve file lineage on every row."""
    frames: list[pd.DataFrame] = []
    loaded_files: list[str] = []

    for path in files:
        frame = pd.read_csv(
            path,
            low_memory=False,
        )

        frame["source_file"] = path.name
        frame["drive_id"] = path.stem

        frames.append(frame)
        loaded_files.append(
            path.name
        )

    if not frames:
        return (
            pd.DataFrame(),
            tuple(),
        )

    return (
        pd.concat(
            frames,
            ignore_index=True,
            sort=False,
        ),
        tuple(
            loaded_files
        ),
    )


def validate_and_clean(
    frame: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    int,
    int,
    list[str],
]:
    """Validate schema, coerce core types, remove unusable rows, and report quality issues."""
    if frame.empty:
        return (
            frame.copy(),
            0,
            0,
            [],
        )

    missing = sorted(
        REQUIRED_COLUMNS
        - set(frame.columns)
    )

    if missing:
        raise ValueError(
            "Telemetry data is missing required columns: "
            + ", ".join(missing)
        )

    cleaned = frame.copy()
    warnings: list[str] = []

    for column in NUMERIC_SOURCE_COLUMNS:
        if column in cleaned.columns:
            cleaned[column] = pd.to_numeric(
                cleaned[column],
                errors="coerce",
            )

    rows_before = len(
        cleaned
    )

    cleaned = cleaned.dropna(
        subset=[
            "Time (epoch)"
        ]
    )

    invalid_timestamp_rows = (
        rows_before
        - len(cleaned)
    )

    if invalid_timestamp_rows:
        warnings.append(
            f"Dropped {invalid_timestamp_rows:,} "
            "rows with invalid timestamps."
        )

    duplicate_subset = [
        "source_file",
        "Time (epoch)",
    ]

    duplicates = int(
        cleaned.duplicated(
            subset=duplicate_subset
        ).sum()
    )

    cleaned = cleaned.drop_duplicates(
        subset=duplicate_subset,
        keep="first",
    )

    if duplicates:
        warnings.append(
            f"Removed {duplicates:,} "
            "duplicate telemetry samples."
        )

    invalid_gps = (
        cleaned[
            "gps_latitude (deg)"
        ].notna()
        & ~cleaned[
            "gps_latitude (deg)"
        ].between(
            -90,
            90,
        )
    ) | (
        cleaned[
            "gps_longitude (deg)"
        ].notna()
        & ~cleaned[
            "gps_longitude (deg)"
        ].between(
            -180,
            180,
        )
    )

    invalid_gps_count = int(
        invalid_gps.sum()
    )

    if invalid_gps_count:
        cleaned.loc[
            invalid_gps,
            [
                "gps_latitude (deg)",
                "gps_longitude (deg)",
            ],
        ] = pd.NA

        warnings.append(
            f"Cleared invalid GPS coordinates in "
            f"{invalid_gps_count:,} rows."
        )

    return (
        cleaned,
        invalid_timestamp_rows,
        duplicates,
        warnings,
    )


def transform_telemetry(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """Transform source-specific columns into a stable analysis-ready telemetry schema."""
    if frame.empty:
        return pd.DataFrame(
            columns=CANONICAL_COLUMNS
        )

    result = pd.DataFrame(
        index=frame.index
    )

    result["source_file"] = (
        frame["source_file"]
    )

    result["drive_id"] = (
        frame["drive_id"]
    )

    result["timestamp"] = pd.to_datetime(
        frame["Time (epoch)"],
        unit="s",
        utc=True,
        errors="coerce",
    )

    result["elapsed_seconds"] = (
        _elapsed_seconds(
            frame["Time_Elapsed"]
        )
        if "Time_Elapsed" in frame
        else frame.get(
            "Time (abs)"
        )
    )

    result["speed_kph"] = (
        frame["veh_speed (kph)"]
    )

    result["speed_mps"] = (
        result["speed_kph"]
        / 3.6
    )

    result["odometer_km"] = (
        frame["veh_odometer (km)"]
    )

    result["distance_delta_km"] = (
        result
        .groupby(
            "drive_id",
            sort=False,
        )["odometer_km"]
        .diff()
        .clip(
            lower=0
        )
    )

    result["latitude"] = (
        frame[
            "gps_latitude (deg)"
        ]
    )

    result["longitude"] = (
        frame[
            "gps_longitude (deg)"
        ]
    )

    result["gps_accuracy_m"] = (
        frame.get(
            "gps_accuracy (m)"
        )
    )

    result["heading_deg"] = (
        frame.get(
            "UI_gpsVehicleHeading (deg)"
        )
    )

    result["elevation_m"] = (
        frame.get(
            "veh_elevation (M)"
        )
    )

    result["longitudinal_accel_mps2"] = (
        frame[
            "RCM_longitudinalAccel (m/s^2)"
        ]
    )

    result["lateral_accel_mps2"] = (
        frame[
            "RCM_lateralAccel (m/s^2)"
        ]
    )

    result["vertical_accel_mps2"] = (
        frame.get(
            "RCM_verticalAccel (m/s^2)"
        )
    )

    result["steering_angle_deg"] = (
        frame[
            "veh_steering_angle (deg)"
        ]
    )

    result["steering_rate_deg_s"] = (
        frame.get(
            "veh_steering_speedps (D/S)"
        )
    )

    result["accelerator_pct"] = (
        frame.get(
            "pedal_accel (per)"
        )
    )

    result["brake_applied"] = (
        _truthy_state(
            frame[
                "ESP_driverBrakeApply"
            ]
        )
    )

    (
        result["autopilot_state"],
        result["autopilot_state_code"],
    ) = _split_state(
        frame[
            "DAS_autopilotState"
        ]
    )

    if "DAS_accState" in frame:
        (
            result["acc_state"],
            _,
        ) = _split_state(
            frame[
                "DAS_accState"
            ]
        )
    else:
        result[
            "acc_state"
        ] = pd.NA

    if "DAS_aebEvent" in frame:
        (
            result["aeb_state"],
            _,
        ) = _split_state(
            frame[
                "DAS_aebEvent"
            ]
        )
    else:
        result[
            "aeb_state"
        ] = pd.NA

    if "UI_roadClass" in frame:
        (
            result["road_class"],
            result["road_class_code"],
        ) = _split_state(
            frame[
                "UI_roadClass"
            ]
        )
    else:
        result[
            "road_class"
        ] = pd.NA

        result[
            "road_class_code"
        ] = pd.NA

    result["rainy"] = (
        _truthy_state(
            frame[
                "APP_environmentRainy"
            ]
        )
        if "APP_environmentRainy"
        in frame
        else False
    )

    result["snowy"] = (
        _truthy_state(
            frame[
                "APP_environmentSnowy"
            ]
        )
        if "APP_environmentSnowy"
        in frame
        else False
    )

    result["battery_soc_pct"] = (
        frame[
            "BMS_socAvg (per)"
        ]
    )

    result[
        "battery_pack_current_a"
    ] = frame.get(
        "BMS_packCurrent (A)"
    )

    result[
        "battery_pack_voltage_v"
    ] = frame.get(
        "BMS_packVoltage (V)"
    )

    result[
        "lead_vehicle_distance_m"
    ] = frame.get(
        "DAS_controlDistance (m)"
    )

    result["set_speed_kph"] = (
        frame.get(
            "DAS_setSpeed (kph)"
        )
    )

    result["vehicles_detected"] = (
        frame[
            "# Vehicles"
        ]
    )

    return (
        result[
            CANONICAL_COLUMNS
        ]
        .sort_values(
            [
                "timestamp",
                "source_file",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# ---------------------------------------------------------------------------
# SQL persistence and serving
# ---------------------------------------------------------------------------

def get_connection(
    database_path: Path = DATABASE_PATH,
) -> sqlite3.Connection:
    """Open the DRIVE SQLite database."""
    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        database_path
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def initialize_database(
    database_path: Path = DATABASE_PATH,
) -> None:
    """Create SQL metadata tables used by the telemetry pipeline."""
    with get_connection(
        database_path
    ) as connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS
            {INGESTION_TABLE} (
                id INTEGER
                    PRIMARY KEY AUTOINCREMENT,
                files_processed INTEGER
                    NOT NULL,
                rows_ingested INTEGER
                    NOT NULL,
                rows_served INTEGER
                    NOT NULL,
                rows_dropped INTEGER
                    NOT NULL,
                duplicate_rows_removed INTEGER
                    NOT NULL,
                loaded_at TEXT
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def _create_telemetry_indexes(
    connection: sqlite3.Connection,
) -> None:
    """Create indexes for common downstream telemetry queries."""
    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS
        idx_{TELEMETRY_TABLE}_timestamp
        ON {TELEMETRY_TABLE}(timestamp)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS
        idx_{TELEMETRY_TABLE}_drive
        ON {TELEMETRY_TABLE}(drive_id)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS
        idx_{TELEMETRY_TABLE}_autopilot
        ON {TELEMETRY_TABLE}(autopilot_state)
        """
    )


def persist_telemetry(
    data: pd.DataFrame,
    database_path: Path = DATABASE_PATH,
) -> int:
    """Replace the SQL telemetry serving table with the latest canonical dataset."""
    initialize_database(
        database_path
    )

    sql_data = data.copy()

    if "timestamp" in sql_data.columns:
        sql_data["timestamp"] = (
            sql_data["timestamp"]
            .astype("string")
        )

    with get_connection(
        database_path
    ) as connection:
        sql_data.to_sql(
            TELEMETRY_TABLE,
            connection,
            if_exists="replace",
            index=False,
            chunksize=SQL_CHUNK_SIZE,
        )

        _create_telemetry_indexes(
            connection
        )

    return len(sql_data)


def record_ingestion_run(
    result: PipelineResult,
    database_path: Path = DATABASE_PATH,
) -> None:
    """Record pipeline execution metadata for observability and auditing."""
    initialize_database(
        database_path
    )

    with get_connection(
        database_path
    ) as connection:
        connection.execute(
            f"""
            INSERT INTO
            {INGESTION_TABLE} (
                files_processed,
                rows_ingested,
                rows_served,
                rows_dropped,
                duplicate_rows_removed
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                len(
                    result.files
                ),
                result.rows_ingested,
                result.rows_served,
                result.rows_dropped,
                result.duplicate_rows_removed,
            ),
        )


def query_telemetry(
    sql: str,
    params: Iterable[object] | None = None,
    database_path: Path = DATABASE_PATH,
) -> pd.DataFrame:
    """Execute a read-only telemetry SQL query and return a DataFrame."""
    statement = sql.strip()

    if not statement.lower().startswith(
        (
            "select",
            "with",
        )
    ):
        raise ValueError(
            "query_telemetry only accepts "
            "SELECT or WITH queries."
        )

    with get_connection(
        database_path
    ) as connection:
        return pd.read_sql_query(
            statement,
            connection,
            params=tuple(
                params or ()
            ),
        )


def get_telemetry(
    limit: int = 1000,
    drive_id: str | None = None,
    autopilot_state: str | None = None,
    min_speed_kph: float | None = None,
    database_path: Path = DATABASE_PATH,
) -> pd.DataFrame:
    """Retrieve filtered telemetry from the SQL serving layer."""
    if limit <= 0:
        raise ValueError(
            "limit must be greater than zero."
        )

    conditions: list[str] = []
    params: list[object] = []

    if drive_id is not None:
        conditions.append(
            "drive_id = ?"
        )
        params.append(
            drive_id
        )

    if autopilot_state is not None:
        conditions.append(
            "autopilot_state = ?"
        )
        params.append(
            autopilot_state
        )

    if min_speed_kph is not None:
        conditions.append(
            "speed_kph >= ?"
        )
        params.append(
            min_speed_kph
        )

    where_clause = ""

    if conditions:
        where_clause = (
            "WHERE "
            + " AND ".join(
                conditions
            )
        )

    params.append(
        limit
    )

    return query_telemetry(
        f"""
        SELECT *
        FROM {TELEMETRY_TABLE}
        {where_clause}
        ORDER BY timestamp
        LIMIT ?
        """,
        params=params,
        database_path=database_path,
    )


def get_drive_summary(
    database_path: Path = DATABASE_PATH,
) -> pd.DataFrame:
    """Generate per-drive metrics using SQL aggregation."""
    return query_telemetry(
        f"""
        SELECT
            drive_id,
            source_file,
            COUNT(*) AS samples,
            MIN(timestamp) AS start_time,
            MAX(timestamp) AS end_time,
            ROUND(
                SUM(distance_delta_km),
                3
            ) AS distance_km,
            ROUND(
                AVG(speed_kph),
                2
            ) AS average_speed_kph,
            ROUND(
                MAX(speed_kph),
                2
            ) AS max_speed_kph,
            SUM(
                CASE
                    WHEN autopilot_state
                        IS NOT NULL
                    AND autopilot_state
                        != 'UNAVAILABLE'
                    THEN 1
                    ELSE 0
                END
            ) AS autopilot_samples
        FROM {TELEMETRY_TABLE}
        GROUP BY
            drive_id,
            source_file
        ORDER BY start_time
        """,
        database_path=database_path,
    )


def get_ingestion_history(
    database_path: Path = DATABASE_PATH,
) -> pd.DataFrame:
    """Return pipeline execution history from SQL."""
    return query_telemetry(
        f"""
        SELECT *
        FROM {INGESTION_TABLE}
        ORDER BY id DESC
        """,
        database_path=database_path,
    )


# ---------------------------------------------------------------------------
# Existing public pipeline API
# ---------------------------------------------------------------------------

def run_pipeline(
    data_dir: Path = TESLA_MODEL3_DATA_DIR,
) -> PipelineResult:
    """Run the complete Analytics Mode CSV-to-analysis-ready telemetry pipeline."""
    files = discover_csv_files(
        data_dir
    )

    if not files:
        return PipelineResult(
            data=pd.DataFrame(
                columns=CANONICAL_COLUMNS
            ),
            files=tuple(),
            rows_ingested=0,
            rows_served=0,
            rows_dropped=0,
            duplicate_rows_removed=0,
            warnings=(
                f"No CSV files found in "
                f"{data_dir}.",
            ),
        )

    raw, loaded_files = (
        ingest_csv_files(
            files
        )
    )

    (
        cleaned,
        invalid_rows,
        duplicates,
        warnings,
    ) = validate_and_clean(
        raw
    )

    transformed = transform_telemetry(
        cleaned
    )

    result = PipelineResult(
        data=transformed,
        files=loaded_files,
        rows_ingested=len(
            raw
        ),
        rows_served=len(
            transformed
        ),
        rows_dropped=invalid_rows,
        duplicate_rows_removed=duplicates,
        warnings=tuple(
            warnings
        ),
    )

    # Serve the same canonical dataset through SQL for downstream consumers.
    persist_telemetry(
        result.data
    )

    record_ingestion_run(
        result
    )

    return result


def summarize_pipeline(
    result: PipelineResult,
) -> dict:
    """Create JSON-safe pipeline and dataset statistics for dashboards and APIs."""
    data = result.data

    summary = {
        "files_processed": len(
            result.files
        ),
        "file_names": list(
            result.files
        ),
        "rows_ingested": (
            result.rows_ingested
        ),
        "rows_served": (
            result.rows_served
        ),
        "rows_dropped": (
            result.rows_dropped
        ),
        "duplicate_rows_removed": (
            result.duplicate_rows_removed
        ),
        "warnings": list(
            result.warnings
        ),
        "time_start": None,
        "time_end": None,
        "duration_minutes": 0.0,
        "distance_km": 0.0,
        "average_speed_kph": 0.0,
        "max_speed_kph": 0.0,
        "drives": 0,
    }

    if data.empty:
        return summary

    start = data[
        "timestamp"
    ].min()

    end = data[
        "timestamp"
    ].max()

    summary.update(
        {
            "time_start": (
                start.isoformat()
                if pd.notna(
                    start
                )
                else None
            ),
            "time_end": (
                end.isoformat()
                if pd.notna(
                    end
                )
                else None
            ),
            "duration_minutes": (
                round(
                    (
                        end
                        - start
                    ).total_seconds()
                    / 60,
                    2,
                )
                if (
                    pd.notna(
                        start
                    )
                    and pd.notna(
                        end
                    )
                )
                else 0.0
            ),
            "distance_km": round(
                float(
                    data[
                        "distance_delta_km"
                    ].sum(
                        skipna=True
                    )
                ),
                3,
            ),
            "average_speed_kph": round(
                float(
                    data[
                        "speed_kph"
                    ].mean(
                        skipna=True
                    )
                ),
                2,
            ),
            "max_speed_kph": round(
                float(
                    data[
                        "speed_kph"
                    ].max(
                        skipna=True
                    )
                ),
                2,
            ),
            "drives": int(
                data[
                    "drive_id"
                ].nunique()
            ),
        }
    )

    return summary


def sample_records(
    result: PipelineResult,
    limit: int = 100,
) -> list[dict]:
    """Return JSON-safe canonical telemetry rows for downstream visualization."""
    if (
        result.data.empty
        or limit <= 0
    ):
        return []

    sample = (
        result.data
        .head(
            limit
        )
        .copy()
    )

    sample["timestamp"] = (
        sample[
            "timestamp"
        ]
        .dt.strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
    )

    sample = (
        sample
        .astype(
            object
        )
        .where(
            pd.notna(
                sample
            ),
            None,
        )
    )

    return sample.to_dict(
        orient="records"
    )
