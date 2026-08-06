"""Build aggregate temporal analysis for AP disengagement scenarios."""

from pathlib import Path

from config import DATABASE_PATH
from telemetry import get_connection


SCENARIO_TELEMETRY_TABLE = "scenario_telemetry"
TEMPORAL_ANALYSIS_TABLE = "temporal_analysis"

TIME_BIN_SECONDS = 0.1

REQUIRED_SCENARIO_TELEMETRY_COLUMNS = {
    "scenario_id",
    "relative_time_s",
    "speed_kph",
    "longitudinal_accel_g",
    "lateral_accel_g",
}


def _validate_scenario_telemetry_table(
    database_path: Path = DATABASE_PATH,
) -> None:
    """Validate the scenario telemetry source required for aggregation."""

    with get_connection(database_path) as connection:
        table_exists = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (SCENARIO_TELEMETRY_TABLE,),
        ).fetchone()

        if table_exists is None:
            raise ValueError(
                f"Scenario telemetry table '{SCENARIO_TELEMETRY_TABLE}' "
                "does not exist. Run build_scenarios() before building "
                "aggregate analysis."
            )

        table_info = connection.execute(
            f"PRAGMA table_info({SCENARIO_TELEMETRY_TABLE})"
        ).fetchall()

    available_columns = {row[1] for row in table_info}
    missing_columns = sorted(
        REQUIRED_SCENARIO_TELEMETRY_COLUMNS - available_columns
    )

    if missing_columns:
        raise ValueError(
            f"Table '{SCENARIO_TELEMETRY_TABLE}' is missing required columns: "
            + ", ".join(missing_columns)
        )


def _create_temporal_analysis_table(connection) -> None:
    """Create the aggregate temporal trajectory table."""

    connection.execute(
        f"""
        CREATE TABLE {TEMPORAL_ANALYSIS_TABLE} (
            relative_time_s REAL PRIMARY KEY,
            scenario_count INTEGER NOT NULL,

            min_speed_kph REAL,
            avg_speed_kph REAL,
            max_speed_kph REAL,

            min_longitudinal_accel_g REAL,
            avg_longitudinal_accel_g REAL,
            max_longitudinal_accel_g REAL,

            min_lateral_accel_g REAL,
            avg_lateral_accel_g REAL,
            max_lateral_accel_g REAL
        )
        """
    )


def _populate_temporal_analysis_table(connection) -> None:
    """Aggregate aligned scenario telemetry into min/average/max trajectories."""

    connection.execute(
        f"""
        INSERT INTO {TEMPORAL_ANALYSIS_TABLE} (
            relative_time_s,
            scenario_count,

            min_speed_kph,
            avg_speed_kph,
            max_speed_kph,

            min_longitudinal_accel_g,
            avg_longitudinal_accel_g,
            max_longitudinal_accel_g,

            min_lateral_accel_g,
            avg_lateral_accel_g,
            max_lateral_accel_g
        )
        WITH binned_scenario_samples AS (
            SELECT
                scenario_id,
                ROUND(
                    relative_time_s / ?,
                    0
                ) * ? AS relative_time_s,
                AVG(speed_kph) AS speed_kph,
                AVG(longitudinal_accel_g) AS longitudinal_accel_g,
                AVG(ABS(lateral_accel_g)) AS lateral_accel_g
            FROM {SCENARIO_TELEMETRY_TABLE}
            GROUP BY
                scenario_id,
                ROUND(relative_time_s / ?, 0)
        )
        SELECT
            ROUND(relative_time_s, 6),
            COUNT(DISTINCT scenario_id),

            MIN(speed_kph),
            AVG(speed_kph),
            MAX(speed_kph),

            MIN(longitudinal_accel_g),
            AVG(longitudinal_accel_g),
            MAX(longitudinal_accel_g),

            MIN(lateral_accel_g),
            AVG(lateral_accel_g),
            MAX(lateral_accel_g)
        FROM binned_scenario_samples
        GROUP BY relative_time_s
        ORDER BY relative_time_s
        """,
        (
            TIME_BIN_SECONDS,
            TIME_BIN_SECONDS,
            TIME_BIN_SECONDS,
        ),
    )


def build_aggregate(
    database_path: Path = DATABASE_PATH,
) -> None:
    """
    Build aggregate temporal analysis across AP disengagement scenarios.

    Scenario telemetry is aligned into fixed relative-time bins. Samples are
    first averaged within each scenario and time bin so scenarios with denser
    telemetry do not receive disproportionate weight. The resulting per-
    scenario values are then aggregated across the scenario population to
    produce minimum, average, and maximum trajectories for speed,
    longitudinal acceleration, and absolute lateral acceleration.

    Partial scenarios are preserved. Each temporal point records the number
    of scenarios contributing to that time bin so downstream visualizations
    can expose changing population coverage near the edges of the window.

    Existing temporal analysis data is replaced each time this function runs.
    """

    _validate_scenario_telemetry_table(database_path)

    with get_connection(database_path) as connection:
        connection.execute(
            f"DROP TABLE IF EXISTS {TEMPORAL_ANALYSIS_TABLE}"
        )

        _create_temporal_analysis_table(connection)
        _populate_temporal_analysis_table(connection)
