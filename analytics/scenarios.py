"""Build temporal context around canonical Autopilot disengagement events."""

from pathlib import Path

from config import DATABASE_PATH, TELEMETRY_TABLE
from telemetry import get_connection


EVENTS_TABLE = "events"
SCENARIO_TELEMETRY_TABLE = "scenario_telemetry"
SCENARIOS_TABLE = "scenarios"

SCENARIO_PRE_WINDOW_SECONDS = 5.0
SCENARIO_POST_WINDOW_SECONDS = 5.0
SCENARIO_WINDOW_TOLERANCE_SECONDS = 0.1

REQUIRED_EVENT_COLUMNS = {
    "event_id",
    "drive_id",
    "disengagement_timestamp",
    "speed_kph",
    "longitudinal_accel_g",
    "lateral_accel_g",
}

REQUIRED_TELEMETRY_COLUMNS = {
    "drive_id",
    "timestamp",
    "speed_kph",
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
    missing_columns = sorted(required_columns - available_columns)

    if missing_columns:
        raise ValueError(
            f"Table '{table_name}' is missing required columns: "
            + ", ".join(missing_columns)
        )


def _validate_source_tables(
    database_path: Path = DATABASE_PATH,
) -> None:
    """Validate the persisted event and telemetry inputs for scenarios."""

    with get_connection(database_path) as connection:
        _validate_table(
            connection,
            EVENTS_TABLE,
            REQUIRED_EVENT_COLUMNS,
            (
                f"Events table '{EVENTS_TABLE}' does not exist. "
                "Run build_events() before building scenarios."
            ),
        )

        _validate_table(
            connection,
            TELEMETRY_TABLE,
            REQUIRED_TELEMETRY_COLUMNS,
            (
                f"Telemetry table '{TELEMETRY_TABLE}' does not exist. "
                "Run the telemetry pipeline before building scenarios."
            ),
        )


def _create_scenario_telemetry_table(connection) -> None:
    """Create the detailed temporal context table for disengagements."""

    connection.execute(
        f"""
        CREATE TABLE {SCENARIO_TELEMETRY_TABLE} (
            scenario_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            drive_id TEXT NOT NULL,
            disengagement_timestamp TEXT NOT NULL,
            telemetry_timestamp TEXT NOT NULL,
            relative_time_s REAL NOT NULL,
            phase TEXT NOT NULL,
            speed_kph REAL,
            longitudinal_accel_g REAL,
            lateral_accel_g REAL
        )
        """
    )


def _populate_scenario_telemetry_table(connection) -> None:
    """Materialize telemetry from five seconds before to after each event."""

    connection.execute(
        f"""
        INSERT INTO {SCENARIO_TELEMETRY_TABLE} (
            scenario_id,
            event_id,
            drive_id,
            disengagement_timestamp,
            telemetry_timestamp,
            relative_time_s,
            phase,
            speed_kph,
            longitudinal_accel_g,
            lateral_accel_g
        )
        WITH scenario_rows AS (
            SELECT
                e.event_id || '_scenario' AS scenario_id,
                e.event_id,
                e.drive_id,
                e.disengagement_timestamp,
                t.timestamp AS telemetry_timestamp,
                (
                    julianday(t.timestamp)
                    - julianday(e.disengagement_timestamp)
                ) * 86400.0 AS relative_time_s,
                t.speed_kph,
                t.longitudinal_accel_g,
                t.lateral_accel_g
            FROM {EVENTS_TABLE} AS e
            JOIN {TELEMETRY_TABLE} AS t
              ON t.drive_id = e.drive_id
             AND julianday(t.timestamp) >= (
                    julianday(e.disengagement_timestamp)
                    - (? / 86400.0)
                 )
             AND julianday(t.timestamp) <= (
                    julianday(e.disengagement_timestamp)
                    + (? / 86400.0)
                 )
        )
        SELECT
            scenario_id,
            event_id,
            drive_id,
            disengagement_timestamp,
            telemetry_timestamp,
            relative_time_s,
            CASE
                WHEN ABS(relative_time_s) < 0.000001 THEN 'event'
                WHEN relative_time_s < 0 THEN 'pre'
                ELSE 'post'
            END AS phase,
            speed_kph,
            longitudinal_accel_g,
            lateral_accel_g
        FROM scenario_rows
        ORDER BY drive_id, disengagement_timestamp, telemetry_timestamp
        """,
        (
            SCENARIO_PRE_WINDOW_SECONDS,
            SCENARIO_POST_WINDOW_SECONDS,
        ),
    )


def _create_scenarios_table(connection) -> None:
    """Create one summary row per canonical disengagement scenario."""

    connection.execute(
        f"""
        CREATE TABLE {SCENARIOS_TABLE} (
            scenario_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL UNIQUE,
            drive_id TEXT NOT NULL,
            disengagement_timestamp TEXT NOT NULL,
            event_speed_kph REAL,
            event_longitudinal_accel_g REAL,
            event_lateral_accel_g REAL,
            pre_avg_speed_kph REAL,
            pre_avg_longitudinal_accel_g REAL,
            pre_avg_lateral_accel_g REAL,
            post_avg_speed_kph REAL,
            post_avg_longitudinal_accel_g REAL,
            post_avg_lateral_accel_g REAL,
            post_peak_longitudinal_accel_g REAL,
            post_peak_longitudinal_time_s REAL,
            post_peak_lateral_accel_g REAL,
            post_peak_lateral_time_s REAL,
            speed_change_kph REAL,
            pre_window_duration_s REAL NOT NULL,
            post_window_duration_s REAL NOT NULL,
            complete_pre_window INTEGER NOT NULL,
            complete_post_window INTEGER NOT NULL,
            complete_window INTEGER NOT NULL
        )
        """
    )


def _populate_scenarios_table(connection) -> None:
    """Aggregate detailed scenario telemetry into one row per event."""

    connection.execute(
        f"""
        INSERT INTO {SCENARIOS_TABLE} (
            scenario_id,
            event_id,
            drive_id,
            disengagement_timestamp,
            event_speed_kph,
            event_longitudinal_accel_g,
            event_lateral_accel_g,
            pre_avg_speed_kph,
            pre_avg_longitudinal_accel_g,
            pre_avg_lateral_accel_g,
            post_avg_speed_kph,
            post_avg_longitudinal_accel_g,
            post_avg_lateral_accel_g,
            post_peak_longitudinal_accel_g,
            post_peak_longitudinal_time_s,
            post_peak_lateral_accel_g,
            post_peak_lateral_time_s,
            speed_change_kph,
            pre_window_duration_s,
            post_window_duration_s,
            complete_pre_window,
            complete_post_window,
            complete_window
        )
        WITH aggregates AS (
            SELECT
                event_id,
                AVG(
                    CASE
                        WHEN relative_time_s < 0
                        THEN speed_kph
                    END
                ) AS pre_avg_speed_kph,
                AVG(
                    CASE
                        WHEN relative_time_s < 0
                        THEN longitudinal_accel_g
                    END
                ) AS pre_avg_longitudinal_accel_g,
                AVG(
                    CASE
                        WHEN relative_time_s < 0
                        THEN lateral_accel_g
                    END
                ) AS pre_avg_lateral_accel_g,
                AVG(
                    CASE
                        WHEN relative_time_s > 0
                        THEN speed_kph
                    END
                ) AS post_avg_speed_kph,
                AVG(
                    CASE
                        WHEN relative_time_s > 0
                        THEN longitudinal_accel_g
                    END
                ) AS post_avg_longitudinal_accel_g,
                AVG(
                    CASE
                        WHEN relative_time_s > 0
                        THEN lateral_accel_g
                    END
                ) AS post_avg_lateral_accel_g,
                COALESCE(
                    -MIN(
                        CASE
                            WHEN relative_time_s < 0
                            THEN relative_time_s
                        END
                    ),
                    0.0
                ) AS pre_window_duration_s,
                COALESCE(
                    MAX(
                        CASE
                            WHEN relative_time_s > 0
                            THEN relative_time_s
                        END
                    ),
                    0.0
                ) AS post_window_duration_s
            FROM {SCENARIO_TELEMETRY_TABLE}
            GROUP BY event_id
        ),
        longitudinal_ranked AS (
            SELECT
                event_id,
                longitudinal_accel_g,
                relative_time_s,
                ROW_NUMBER() OVER (
                    PARTITION BY event_id
                    ORDER BY
                        ABS(longitudinal_accel_g) DESC,
                        relative_time_s ASC
                ) AS response_rank
            FROM {SCENARIO_TELEMETRY_TABLE}
            WHERE relative_time_s > 0
              AND longitudinal_accel_g IS NOT NULL
        ),
        lateral_ranked AS (
            SELECT
                event_id,
                lateral_accel_g,
                relative_time_s,
                ROW_NUMBER() OVER (
                    PARTITION BY event_id
                    ORDER BY
                        ABS(lateral_accel_g) DESC,
                        relative_time_s ASC
                ) AS response_rank
            FROM {SCENARIO_TELEMETRY_TABLE}
            WHERE relative_time_s > 0
              AND lateral_accel_g IS NOT NULL
        )
        SELECT
            e.event_id || '_scenario' AS scenario_id,
            e.event_id,
            e.drive_id,
            e.disengagement_timestamp,
            e.speed_kph AS event_speed_kph,
            e.longitudinal_accel_g AS event_longitudinal_accel_g,
            e.lateral_accel_g AS event_lateral_accel_g,
            a.pre_avg_speed_kph,
            a.pre_avg_longitudinal_accel_g,
            a.pre_avg_lateral_accel_g,
            a.post_avg_speed_kph,
            a.post_avg_longitudinal_accel_g,
            a.post_avg_lateral_accel_g,
            lr.longitudinal_accel_g
                AS post_peak_longitudinal_accel_g,
            lr.relative_time_s
                AS post_peak_longitudinal_time_s,
            latr.lateral_accel_g
                AS post_peak_lateral_accel_g,
            latr.relative_time_s
                AS post_peak_lateral_time_s,
            CASE
                WHEN a.pre_avg_speed_kph IS NOT NULL
                 AND a.post_avg_speed_kph IS NOT NULL
                THEN (
                    a.post_avg_speed_kph
                    - a.pre_avg_speed_kph
                )
                ELSE NULL
            END AS speed_change_kph,
            COALESCE(
                a.pre_window_duration_s,
                0.0
            ),
            COALESCE(
                a.post_window_duration_s,
                0.0
            ),
            CASE
                WHEN COALESCE(
                    a.pre_window_duration_s,
                    0.0
                ) >= (? - ?)
                THEN 1
                ELSE 0
            END AS complete_pre_window,
            CASE
                WHEN COALESCE(
                    a.post_window_duration_s,
                    0.0
                ) >= (? - ?)
                THEN 1
                ELSE 0
            END AS complete_post_window,
            CASE
                WHEN COALESCE(
                    a.pre_window_duration_s,
                    0.0
                ) >= (? - ?)
                 AND COALESCE(
                    a.post_window_duration_s,
                    0.0
                ) >= (? - ?)
                THEN 1
                ELSE 0
            END AS complete_window
        FROM {EVENTS_TABLE} AS e
        LEFT JOIN aggregates AS a
          ON a.event_id = e.event_id
        LEFT JOIN longitudinal_ranked AS lr
          ON lr.event_id = e.event_id
         AND lr.response_rank = 1
        LEFT JOIN lateral_ranked AS latr
          ON latr.event_id = e.event_id
         AND latr.response_rank = 1
        ORDER BY e.drive_id, e.disengagement_timestamp
        """,
        (
            SCENARIO_PRE_WINDOW_SECONDS,
            SCENARIO_WINDOW_TOLERANCE_SECONDS,
            SCENARIO_POST_WINDOW_SECONDS,
            SCENARIO_WINDOW_TOLERANCE_SECONDS,
            SCENARIO_PRE_WINDOW_SECONDS,
            SCENARIO_WINDOW_TOLERANCE_SECONDS,
            SCENARIO_POST_WINDOW_SECONDS,
            SCENARIO_WINDOW_TOLERANCE_SECONDS,
        ),
    )


def _create_scenario_indexes(connection) -> None:
    """Create indexes for common downstream scenario access patterns."""

    connection.execute(
        f"""
        CREATE INDEX idx_scenario_telemetry_scenario
        ON {SCENARIO_TELEMETRY_TABLE}(scenario_id)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX idx_scenario_telemetry_event
        ON {SCENARIO_TELEMETRY_TABLE}(event_id)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX idx_scenario_telemetry_scenario_time
        ON {SCENARIO_TELEMETRY_TABLE}(
            scenario_id,
            relative_time_s
        )
        """
    )

    connection.execute(
        f"""
        CREATE INDEX idx_scenarios_drive
        ON {SCENARIOS_TABLE}(drive_id)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX idx_scenarios_timestamp
        ON {SCENARIOS_TABLE}(disengagement_timestamp)
        """
    )


def build_scenarios(
    database_path: Path = DATABASE_PATH,
) -> None:
    """
    Build temporal context around every canonical AP disengagement event.

    Each event is expanded to telemetry from five seconds before through
    five seconds after disengagement. Detailed rows are materialized in
    scenario_telemetry, while one summary row per event is materialized in
    scenarios for downstream insights and visualization.

    Existing scenario data is replaced each time this function runs.
    """

    _validate_source_tables(database_path)

    with get_connection(database_path) as connection:
        connection.execute(
            f"DROP TABLE IF EXISTS {SCENARIO_TELEMETRY_TABLE}"
        )

        connection.execute(
            f"DROP TABLE IF EXISTS {SCENARIOS_TABLE}"
        )

        _create_scenario_telemetry_table(connection)
        _populate_scenario_telemetry_table(connection)

        _create_scenarios_table(connection)
        _populate_scenarios_table(connection)

        _create_scenario_indexes(connection)
