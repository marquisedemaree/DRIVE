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


STANDARD_GRAVITY_MPS2 = 9.80665


# Minimum source fields required for AP disengagement detection
# and pre/post disengagement vehicle-dynamics analysis.
REQUIRED_COLUMNS = {
    "Time (epoch)",
    "veh_state_drive",
    "veh_speed (kph)",
    "RCM_longitudinalAccel (m/s^2)",
    "RCM_lateralAccel (m/s^2)",
    "DAS_autopilotState",
}


# Source fields that must be numeric before transformation.
NUMERIC_SOURCE_COLUMNS = [
    "Time (epoch)",
    "Time (abs)",
    "veh_speed (kph)",
    "RCM_longitudinalAccel (m/s^2)",
    "RCM_lateralAccel (m/s^2)",
]


# Stable internal telemetry contract consumed by downstream DRIVE modules.
#
# The schema is intentionally narrow:
# - identify each drive,
# - establish reliable temporal ordering,
# - determine whether the vehicle is driving,
# - identify Autopilot state transitions,
# - measure vehicle speed,
# - analyze longitudinal and lateral vehicle dynamics.
CANONICAL_COLUMNS = [
    "source_file",
    "drive_id",
    "timestamp",
    "elapsed_seconds",
    "drive_state",
    "drive_state_code",
    "autopilot_state",
    "autopilot_state_code",
    "speed_kph",
    "speed_mps",
    "longitudinal_accel_mps2",
    "longitudinal_accel_g",
    "lateral_accel_mps2",
    "lateral_accel_g",
]


@dataclass(frozen=True)
class PipelineResult:
    """Processed telemetry plus pipeline metadata for downstream consumers."""

    data: pd.DataFrame
    files: tuple[str, ...]
    rows_ingested: int
    rows_served: int
    rows_dropped: int
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
    """
    Split encoded source states into readable labels and numeric codes.

    Example:
        ACTIVE_NOMINAL|3

    Becomes:
        label = ACTIVE_NOMINAL
        code = 3
    """

    text = series.astype("string")
    parts = text.str.rsplit("|", n=1, expand=True)

    label = parts[0].replace({"": pd.NA})

    if parts.shape[1] > 1:
        code = pd.to_numeric(
            parts[1],
            errors="coerce",
        )
    else:
        code = pd.Series(
            pd.NA,
            index=series.index,
            dtype="Float64",
        )

    return label, code


def _elapsed_seconds(
    series: pd.Series,
) -> pd.Series:
    """Convert HH:MM:SS-style elapsed-time values to seconds."""

    return pd.to_timedelta(
        series,
        errors="coerce",
    ).dt.total_seconds()


def ingest_csv_files(
    files: Iterable[Path],
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """
    Read telemetry CSV files and preserve source lineage.

    Each source file is treated as one drive and receives:
    - source_file: original filename
    - drive_id: filename stem
    """

    frames = []
    loaded_files = []

    for path in files:
        frame = pd.read_csv(
            path,
            low_memory=False,
        )

        frame["source_file"] = path.name
        frame["drive_id"] = path.stem

        frames.append(frame)
        loaded_files.append(path.name)

    if not frames:
        return pd.DataFrame(), tuple()

    combined = pd.concat(
        frames,
        ignore_index=True,
        sort=False,
    )

    return combined, tuple(loaded_files)


def validate_and_clean(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Validate the required telemetry schema and clean unusable samples.

    Critical schema problems raise an error.

    Recoverable row-level problems are cleaned and reported through
    pipeline warnings.
    """

    if frame.empty:
        return frame.copy(), []

    missing = sorted(
        REQUIRED_COLUMNS - set(frame.columns)
    )

    if missing:
        raise ValueError(
            "Telemetry data is missing required columns: "
            + ", ".join(missing)
        )

    cleaned = frame.copy()
    warnings = []

    # Coerce analytical numeric signals into consistent numeric types.
    for column in NUMERIC_SOURCE_COLUMNS:
        if column in cleaned.columns:
            cleaned[column] = pd.to_numeric(
                cleaned[column],
                errors="coerce",
            )

    # Timestamp validity is mandatory because AP transition detection
    # depends on reliable chronological ordering.
    rows_before_timestamp_cleaning = len(cleaned)

    cleaned = cleaned.dropna(
        subset=["Time (epoch)"]
    )

    invalid_timestamp_rows = (
        rows_before_timestamp_cleaning - len(cleaned)
    )

    if invalid_timestamp_rows:
        warnings.append(
            f"Dropped {invalid_timestamp_rows:,} rows "
            "with invalid timestamps."
        )

    # Duplicate timestamps within the same source drive could create
    # ambiguous or false AP state transitions.
    duplicate_subset = [
        "source_file",
        "Time (epoch)",
    ]

    duplicate_rows = int(
        cleaned.duplicated(
            subset=duplicate_subset
        ).sum()
    )

    cleaned = cleaned.drop_duplicates(
        subset=duplicate_subset,
        keep="first",
    )

    if duplicate_rows:
        warnings.append(
            f"Removed {duplicate_rows:,} duplicate telemetry samples."
        )

    return cleaned, warnings


def transform_telemetry(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Transform Tesla-specific telemetry into DRIVE's canonical schema.

    The resulting dataset supports:

    1. AP active -> inactive transition detection.
    2. Detection only while the vehicle is in a valid driving state.
    3. Reliable chronological analysis within each drive.
    4. Pre/post disengagement comparison of longitudinal and
       lateral vehicle dynamics.
    """

    if frame.empty:
        return pd.DataFrame(
            columns=CANONICAL_COLUMNS
        )

    result = pd.DataFrame(
        index=frame.index
    )

    # ------------------------------------------------------------------
    # Identity and lineage
    # ------------------------------------------------------------------

    result["source_file"] = frame["source_file"]
    result["drive_id"] = frame["drive_id"]

    # ------------------------------------------------------------------
    # Temporal ordering
    # ------------------------------------------------------------------

    result["timestamp"] = pd.to_datetime(
        frame["Time (epoch)"],
        unit="s",
        utc=True,
        errors="coerce",
    )

    if "Time_Elapsed" in frame.columns:
        result["elapsed_seconds"] = _elapsed_seconds(
            frame["Time_Elapsed"]
        )
    elif "Time (abs)" in frame.columns:
        result["elapsed_seconds"] = frame["Time (abs)"]
    else:
        result["elapsed_seconds"] = pd.NA

    # ------------------------------------------------------------------
    # Vehicle driving state
    # ------------------------------------------------------------------

    (
        result["drive_state"],
        result["drive_state_code"],
    ) = _split_state(
        frame["veh_state_drive"]
    )

    # ------------------------------------------------------------------
    # Autopilot state
    # ------------------------------------------------------------------

    (
        result["autopilot_state"],
        result["autopilot_state_code"],
    ) = _split_state(
        frame["DAS_autopilotState"]
    )

    # ------------------------------------------------------------------
    # Vehicle speed
    # ------------------------------------------------------------------

    result["speed_kph"] = frame[
        "veh_speed (kph)"
    ]

    result["speed_mps"] = (
        result["speed_kph"] / 3.6
    )

    # ------------------------------------------------------------------
    # Vehicle dynamics
    #
    # Preserve acceleration in the source SI unit and derive equivalent
    # g-force values for scenario-level interpretation.
    # ------------------------------------------------------------------

    result["longitudinal_accel_mps2"] = frame[
        "RCM_longitudinalAccel (m/s^2)"
    ]

    result["longitudinal_accel_g"] = (
        result["longitudinal_accel_mps2"]
        / STANDARD_GRAVITY_MPS2
    )

    result["lateral_accel_mps2"] = frame[
        "RCM_lateralAccel (m/s^2)"
    ]

    result["lateral_accel_g"] = (
        result["lateral_accel_mps2"]
        / STANDARD_GRAVITY_MPS2
    )

    # Strict per-drive ordering is required for downstream transition
    # detection using operations such as groupby().shift().
    #
    # Sorting by drive_id prevents the final sample of one drive from
    # ever being compared with the first sample of another drive.
    result = (
        result[CANONICAL_COLUMNS]
        .sort_values(
            [
                "drive_id",
                "timestamp",
            ],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    return result


def get_connection(
    database_path: Path = DATABASE_PATH,
) -> sqlite3.Connection:
    """Open the DRIVE SQLite database."""

    database_path = Path(database_path)

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

    with get_connection(database_path) as connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {INGESTION_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                files_processed INTEGER NOT NULL,
                rows_ingested INTEGER NOT NULL,
                rows_served INTEGER NOT NULL,
                rows_dropped INTEGER NOT NULL,
                loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def _create_telemetry_indexes(
    connection: sqlite3.Connection,
) -> None:
    """
    Create indexes for common AP disengagement analysis queries.
    """

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
        idx_{TELEMETRY_TABLE}_drive_timestamp
        ON {TELEMETRY_TABLE}(drive_id, timestamp)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS
        idx_{TELEMETRY_TABLE}_autopilot
        ON {TELEMETRY_TABLE}(autopilot_state)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS
        idx_{TELEMETRY_TABLE}_drive_state
        ON {TELEMETRY_TABLE}(drive_state)
        """
    )


def persist_telemetry(
    data: pd.DataFrame,
    database_path: Path = DATABASE_PATH,
) -> int:
    """
    Replace the SQL telemetry table with the latest canonical dataset.
    """

    initialize_database(
        database_path
    )

    sql_data = data.copy()

    if "timestamp" in sql_data.columns:
        sql_data["timestamp"] = (
            sql_data["timestamp"]
            .astype("string")
        )

    with get_connection(database_path) as connection:
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
    """
    Record pipeline execution metadata for observability and auditing.
    """

    initialize_database(
        database_path
    )

    with get_connection(database_path) as connection:
        connection.execute(
            f"""
            INSERT INTO {INGESTION_TABLE} (
                files_processed,
                rows_ingested,
                rows_served,
                rows_dropped
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                len(result.files),
                result.rows_ingested,
                result.rows_served,
                result.rows_dropped,
            ),
        )


def query_telemetry(
    sql: str,
    params: Iterable[object] | None = None,
    database_path: Path = DATABASE_PATH,
) -> pd.DataFrame:
    """
    Execute a read-only telemetry SQL query and return a DataFrame.
    """

    statement = sql.strip()

    if not statement.lower().startswith(
        ("select", "with")
    ):
        raise ValueError(
            "query_telemetry only accepts "
            "SELECT or WITH queries."
        )

    with get_connection(database_path) as connection:
        return pd.read_sql_query(
            statement,
            connection,
            params=tuple(params or ()),
        )


def get_telemetry(
    limit: int = 1000,
    drive_id: str | None = None,
    autopilot_state: str | None = None,
    min_speed_kph: float | None = None,
    database_path: Path = DATABASE_PATH,
) -> pd.DataFrame:
    """
    Retrieve filtered canonical telemetry from the SQL serving layer.
    """

    if limit <= 0:
        raise ValueError(
            "limit must be greater than zero."
        )

    conditions = []
    params = []

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

    if conditions:
        where_clause = (
            "WHERE "
            + " AND ".join(conditions)
        )
    else:
        where_clause = ""

    params.append(limit)

    return query_telemetry(
        f"""
        SELECT *
        FROM {TELEMETRY_TABLE}
        {where_clause}
        ORDER BY drive_id, timestamp
        LIMIT ?
        """,
        params=params,
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


def run_pipeline(
    data_dir: Path = TESLA_MODEL3_DATA_DIR,
) -> PipelineResult:
    """
    Run the complete CSV-to-canonical telemetry pipeline.

    Pipeline:
        discover
        -> ingest
        -> validate
        -> clean
        -> transform
        -> order
        -> persist
        -> record ingestion metadata
    """

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
            warnings=(
                f"No CSV files found in {data_dir}.",
            ),
        )

    raw, loaded_files = ingest_csv_files(
        files
    )

    cleaned, warnings = validate_and_clean(
        raw
    )

    transformed = transform_telemetry(
        cleaned
    )

    rows_ingested = len(raw)
    rows_served = len(transformed)
    rows_dropped = (
        rows_ingested - rows_served
    )

    result = PipelineResult(
        data=transformed,
        files=loaded_files,
        rows_ingested=rows_ingested,
        rows_served=rows_served,
        rows_dropped=rows_dropped,
        warnings=tuple(warnings),
    )

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
    """
    Create a summary of telemetry pipeline processing.

    Only pipeline processing statistics are included here.
    Telemetry-derived values and analytical metrics belong in
    downstream analytics modules.
    """

    return {
        "files_processed": len(result.files),
        "rows_ingested": result.rows_ingested,
        "rows_served": result.rows_served,
        "rows_dropped": result.rows_dropped,
    }


def sample_records(
    result: PipelineResult,
    limit: int = 100,
) -> list[dict]:
    """
    Return JSON-safe canonical telemetry rows for visualization/API use.
    """

    if (
        result.data.empty
        or limit <= 0
    ):
        return []

    sample = (
        result.data
        .head(limit)
        .copy()
    )

    sample["timestamp"] = (
        sample["timestamp"]
        .dt.strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
    )

    sample = (
        sample
        .astype(object)
        .where(
            pd.notna(sample),
            None,
        )
    )

    return sample.to_dict(
        orient="records"
    )
