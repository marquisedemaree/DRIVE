"""Identify critical post-disengagement scenarios from temporal telemetry."""

from pathlib import Path

from config import DATABASE_PATH, HARD_BRAKING, HARD_TURNING
from telemetry import get_connection


SCENARIOS_TABLE = "scenarios"
SCENARIO_TELEMETRY_TABLE = "scenario_telemetry"
CRITICAL_SCENARIOS_TABLE = "critical_scenarios"


REQUIRED_SCENARIO_COLUMNS = {
    "scenario_id",
    "event_id",
    "drive_id",
    "disengagement_timestamp",
}

REQUIRED_SCENARIO_TELEMETRY_COLUMNS = {
    "scenario_id",
    "event_id",
    "drive_id",
    "disengagement_timestamp",
    "relative_time_s",
    "longitudinal_accel_g",
    "lateral_accel_g",
}


def _validate_table(
    connection,
    table_name: str,
    required_columns: set[str],
    missing_table_message: str,
) -> None:
    """Validate that a source table exists and contains required columns."""

    table_exists = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    if table_exists is None:
        raise ValueError(missing_table_message)

    table_info = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    available_columns = {row[1] for row in table_info}
    missing_columns = sorted(
        required_columns - available_columns
    )

    if missing_columns:
        raise ValueError(
            f"Table '{table_name}' is missing required columns: "
            + ", ".join(missing_columns)
        )


def _validate_source_tables(
    database_path: Path = DATABASE_PATH,
) -> None:
    """Validate persisted scenario inputs for critical scenario detection."""

    with get_connection(database_path) as connection:
        _validate_table(
            connection,
            SCENARIOS_TABLE,
            REQUIRED_SCENARIO_COLUMNS,
            (
                f"Scenarios table '{SCENARIOS_TABLE}' does not exist. "
                "Run build_scenarios() before building critical scenarios."
            ),
        )

        _validate_table(
            connection,
            SCENARIO_TELEMETRY_TABLE,
            REQUIRED_SCENARIO_TELEMETRY_COLUMNS,
            (
                f"Scenario telemetry table "
                f"'{SCENARIO_TELEMETRY_TABLE}' does not exist. "
                "Run build_scenarios() before building critical scenarios."
            ),
        )


def _create_critical_scenarios_table(connection) -> None:
    """Create one classification row per qualifying critical scenario."""

    connection.execute(
        f"""
        CREATE TABLE {CRITICAL_SCENARIOS_TABLE} (
            scenario_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL UNIQUE,
            drive_id TEXT NOT NULL,
            disengagement_timestamp TEXT NOT NULL,
            harsh_braking INTEGER NOT NULL,
            hard_turning INTEGER NOT NULL,
            peak_braking_g REAL,
            peak_lateral_g REAL,
            braking_threshold_crossing_time_s REAL,
            turning_threshold_crossing_time_s REAL
        )
        """
    )


def _populate_critical_scenarios_table(connection) -> None:
    """
    Identify scenarios with post-disengagement threshold crossings.

    Harsh braking:
        longitudinal_accel_g <= -HARD_BRAKING

    Hard turning:
        ABS(lateral_accel_g) >= HARD_TURNING

    Only telemetry strictly after disengagement is considered.
    """

    connection.execute(
        f"""
        INSERT INTO {CRITICAL_SCENARIOS_TABLE} (
            scenario_id,
            event_id,
            drive_id,
            disengagement_timestamp,
            harsh_braking,
            hard_turning,
            peak_braking_g,
            peak_lateral_g,
            braking_threshold_crossing_time_s,
            turning_threshold_crossing_time_s
        )
        WITH post_telemetry AS (
            SELECT
                scenario_id,
                relative_time_s,
                longitudinal_accel_g,
                lateral_accel_g
            FROM {SCENARIO_TELEMETRY_TABLE}
            WHERE relative_time_s > 0
        ),

        threshold_summary AS (
            SELECT
                scenario_id,

                MAX(
                    CASE
                        WHEN longitudinal_accel_g <= ?
                        THEN 1
                        ELSE 0
                    END
                ) AS harsh_braking,

                MAX(
                    CASE
                        WHEN ABS(lateral_accel_g) >= ?
                        THEN 1
                        ELSE 0
                    END
                ) AS hard_turning,

                MIN(
                    CASE
                        WHEN longitudinal_accel_g <= ?
                        THEN relative_time_s
                    END
                ) AS braking_threshold_crossing_time_s,

                MIN(
                    CASE
                        WHEN ABS(lateral_accel_g) >= ?
                        THEN relative_time_s
                    END
                ) AS turning_threshold_crossing_time_s

            FROM post_telemetry
            GROUP BY scenario_id
        ),

        braking_ranked AS (
            SELECT
                scenario_id,
                longitudinal_accel_g,
                ROW_NUMBER() OVER (
                    PARTITION BY scenario_id
                    ORDER BY
                        longitudinal_accel_g ASC,
                        relative_time_s ASC
                ) AS response_rank
            FROM post_telemetry
            WHERE longitudinal_accel_g IS NOT NULL
        ),

        lateral_ranked AS (
            SELECT
                scenario_id,
                lateral_accel_g,
                ROW_NUMBER() OVER (
                    PARTITION BY scenario_id
                    ORDER BY
                        ABS(lateral_accel_g) DESC,
                        relative_time_s ASC
                ) AS response_rank
            FROM post_telemetry
            WHERE lateral_accel_g IS NOT NULL
        )

        SELECT
            s.scenario_id,
            s.event_id,
            s.drive_id,
            s.disengagement_timestamp,
            ts.harsh_braking,
            ts.hard_turning,
            br.longitudinal_accel_g AS peak_braking_g,
            lr.lateral_accel_g AS peak_lateral_g,
            ts.braking_threshold_crossing_time_s,
            ts.turning_threshold_crossing_time_s

        FROM {SCENARIOS_TABLE} AS s

        JOIN threshold_summary AS ts
          ON ts.scenario_id = s.scenario_id

        LEFT JOIN braking_ranked AS br
          ON br.scenario_id = s.scenario_id
         AND br.response_rank = 1

        LEFT JOIN lateral_ranked AS lr
          ON lr.scenario_id = s.scenario_id
         AND lr.response_rank = 1

        WHERE ts.harsh_braking = 1
           OR ts.hard_turning = 1

        ORDER BY
            s.drive_id,
            s.disengagement_timestamp
        """,
        (
            -HARD_BRAKING,
            HARD_TURNING,
            -HARD_BRAKING,
            HARD_TURNING,
        ),
    )


def _create_critical_scenarios_indexes(connection) -> None:
    """Create indexes for common downstream critical scenario queries."""

    connection.execute(
        f"""
        CREATE INDEX idx_critical_scenarios_drive
        ON {CRITICAL_SCENARIOS_TABLE}(drive_id)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX idx_critical_scenarios_timestamp
        ON {CRITICAL_SCENARIOS_TABLE}(disengagement_timestamp)
        """
    )


def build_critical_scenarios(
    database_path: Path = DATABASE_PATH,
) -> None:
    """
    Build the critical scenarios dataset.

    A scenario is critical when available telemetry strictly after the
    Autopilot disengagement crosses at least one configured threshold:

    - Harsh braking:
      longitudinal acceleration <= -HARD_BRAKING

    - Hard turning:
      absolute lateral acceleration >= HARD_TURNING

    Any qualifying observation within the post-disengagement scenario
    window makes the entire scenario critical.

    One row is materialized per qualifying scenario. Multiple threshold
    crossings do not create duplicate scenario records, and a scenario
    may be classified as both harsh braking and hard turning.

    The first crossing time for each threshold and the strongest observed
    post-disengagement braking and lateral responses are retained for
    downstream aggregate analysis and scenario drill-down.

    Existing critical scenario data is replaced each time this function
    runs.
    """

    _validate_source_tables(database_path)

    with get_connection(database_path) as connection:
        connection.execute(
            f"DROP TABLE IF EXISTS {CRITICAL_SCENARIOS_TABLE}"
        )

        _create_critical_scenarios_table(connection)
        _populate_critical_scenarios_table(connection)
        _create_critical_scenarios_indexes(connection)
