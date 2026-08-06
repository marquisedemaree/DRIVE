"""Build canonical Autopilot disengagement events from persisted telemetry."""

from pathlib import Path

from config import DATABASE_PATH, TELEMETRY_TABLE
from telemetry import get_connection


EVENTS_TABLE = "events"

REQUIRED_TELEMETRY_COLUMNS = {
    "drive_id",
    "timestamp",
    "drive_state",
    "autopilot_state",
    "speed_kph",
    "longitudinal_accel_g",
    "lateral_accel_g",
}

AP_ACTIVE_STATES = (
    "ACTIVE_NOMINAL",
    "ACTIVE_RESTRICTED",
)

VEHICLE_DRIVE_STATE = "Driving"


def _validate_telemetry_table(
    database_path: Path = DATABASE_PATH,
) -> None:
    """Validate that the telemetry table exists and supports event extraction."""

    with get_connection(database_path) as connection:
        table_exists = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (TELEMETRY_TABLE,),
        ).fetchone()

        if table_exists is None:
            raise ValueError(
                f"Telemetry table '{TELEMETRY_TABLE}' does not exist. "
                "Run the telemetry pipeline before building events."
            )

        table_info = connection.execute(
            f"PRAGMA table_info({TELEMETRY_TABLE})"
        ).fetchall()

    available_columns = {row[1] for row in table_info}

    missing_columns = sorted(
        REQUIRED_TELEMETRY_COLUMNS - available_columns
    )

    if missing_columns:
        raise ValueError(
            "Telemetry table is missing required columns: "
            + ", ".join(missing_columns)
        )


def _create_events_table(connection) -> None:
    """Create an empty canonical events table."""

    connection.execute(
        f"""
        CREATE TABLE {EVENTS_TABLE} (
            event_id TEXT PRIMARY KEY,
            drive_id TEXT NOT NULL,
            disengagement_timestamp TEXT NOT NULL,
            speed_kph REAL,
            longitudinal_accel_g REAL,
            lateral_accel_g REAL
        )
        """
    )


def _populate_events_table(connection) -> None:
    """Detect AP disengagement transitions and insert canonical events."""

    connection.execute(
        f"""
        INSERT INTO {EVENTS_TABLE} (
            event_id,
            drive_id,
            disengagement_timestamp,
            speed_kph,
            longitudinal_accel_g,
            lateral_accel_g
        )
        WITH ordered_telemetry AS (
            SELECT
                drive_id,
                timestamp,
                drive_state,
                autopilot_state,
                speed_kph,
                longitudinal_accel_g,
                lateral_accel_g,
                LAG(autopilot_state) OVER (
                    PARTITION BY drive_id
                    ORDER BY timestamp
                ) AS previous_autopilot_state
            FROM {TELEMETRY_TABLE}
        ),
        disengagements AS (
            SELECT
                drive_id,
                timestamp AS disengagement_timestamp,
                speed_kph,
                longitudinal_accel_g,
                lateral_accel_g
            FROM ordered_telemetry
            WHERE previous_autopilot_state IN (?, ?)
              AND autopilot_state IS NOT NULL
              AND autopilot_state NOT IN (?, ?)
              AND drive_state = ?
        ),
        numbered_events AS (
            SELECT
                drive_id,
                disengagement_timestamp,
                speed_kph,
                longitudinal_accel_g,
                lateral_accel_g,
                ROW_NUMBER() OVER (
                    PARTITION BY drive_id
                    ORDER BY disengagement_timestamp
                ) AS event_sequence
            FROM disengagements
        )
        SELECT
            drive_id
                || '_ap_disengagement_'
                || printf('%03d', event_sequence),
            drive_id,
            disengagement_timestamp,
            speed_kph,
            longitudinal_accel_g,
            lateral_accel_g
        FROM numbered_events
        ORDER BY drive_id, disengagement_timestamp
        """,
        (
            "ACTIVE_NOMINAL",
            "ACTIVE_RESTRICTED",
            "ACTIVE_NOMINAL",
            "ACTIVE_RESTRICTED",
            VEHICLE_DRIVE_STATE,
        ),
    )

def _create_events_indexes(connection) -> None:
    """Create indexes for common downstream event access patterns."""

    connection.execute(
        f"""
        CREATE INDEX idx_events_drive
        ON {EVENTS_TABLE}(drive_id)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX idx_events_timestamp
        ON {EVENTS_TABLE}(disengagement_timestamp)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX idx_events_drive_timestamp
        ON {EVENTS_TABLE}(drive_id, disengagement_timestamp)
        """
    )


def build_events(
    database_path: Path = DATABASE_PATH,
) -> None:
    """
    Build the canonical AP disengagement events table.

    An event is an explicit transition from ACTIVE Autopilot to a known
    non-ACTIVE state while the vehicle is in DRIVE.

    Transition detection is performed entirely in SQLite using LAG().
    The resulting events are materialized in the events table for
    downstream consumers such as metrics, scenarios, and the dashboard.

    Existing event data is replaced each time this function runs.
    """

    _validate_telemetry_table(database_path)

    with get_connection(database_path) as connection:
        connection.execute(
            f"DROP TABLE IF EXISTS {EVENTS_TABLE}"
        )

        _create_events_table(connection)
        _populate_events_table(connection)
        _create_events_indexes(connection)
