"""Build final critical-scenario analysis and drill-down data."""

from pathlib import Path

from config import DATABASE_PATH, HARD_BRAKING, HARD_TURNING
from telemetry import get_connection


SCENARIOS_TABLE = "scenarios"
SCENARIO_TELEMETRY_TABLE = "scenario_telemetry"
CRITICAL_SCENARIOS_TABLE = "critical_scenarios"

INSIGHTS_SUMMARY_TABLE = "insights_summary"
CRITICAL_FINDINGS_TABLE = "critical_findings"


REQUIRED_SCENARIO_COLUMNS = {
    "scenario_id",
    "event_id",
    "drive_id",
    "disengagement_timestamp",
    "event_speed_kph",
}

REQUIRED_SCENARIO_TELEMETRY_COLUMNS = {
    "scenario_id",
    "relative_time_s",
    "speed_kph",
    "longitudinal_accel_g",
    "lateral_accel_g",
}

REQUIRED_CRITICAL_SCENARIO_COLUMNS = {
    "scenario_id",
    "event_id",
    "drive_id",
    "disengagement_timestamp",
    "harsh_braking",
    "hard_turning",
    "peak_braking_g",
    "peak_lateral_g",
    "braking_threshold_crossing_time_s",
    "turning_threshold_crossing_time_s",
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
    """Validate persisted inputs required for final insights analysis."""

    with get_connection(database_path) as connection:
        _validate_table(
            connection,
            SCENARIOS_TABLE,
            REQUIRED_SCENARIO_COLUMNS,
            (
                f"Scenarios table '{SCENARIOS_TABLE}' does not exist. "
                "Run build_scenarios() before building insights."
            ),
        )

        _validate_table(
            connection,
            SCENARIO_TELEMETRY_TABLE,
            REQUIRED_SCENARIO_TELEMETRY_COLUMNS,
            (
                f"Scenario telemetry table "
                f"'{SCENARIO_TELEMETRY_TABLE}' does not exist. "
                "Run build_scenarios() before building insights."
            ),
        )

        _validate_table(
            connection,
            CRITICAL_SCENARIOS_TABLE,
            REQUIRED_CRITICAL_SCENARIO_COLUMNS,
            (
                f"Critical scenarios table "
                f"'{CRITICAL_SCENARIOS_TABLE}' does not exist. "
                "Run build_critical_scenarios() before building insights."
            ),
        )


def _create_insights_summary_table(connection) -> None:
    """Create the one-row final-analysis overview table."""

    connection.execute(
        f"""
        CREATE TABLE {INSIGHTS_SUMMARY_TABLE} (
            summary_id INTEGER PRIMARY KEY CHECK (summary_id = 1),
            total_scenarios INTEGER NOT NULL,
            critical_findings INTEGER NOT NULL,
            harsh_braking_scenarios INTEGER NOT NULL,
            hard_turning_scenarios INTEGER NOT NULL,
            harsh_braking_pct REAL NOT NULL,
            hard_turning_pct REAL NOT NULL,
            hard_braking_threshold_g REAL NOT NULL,
            hard_turning_threshold_g REAL NOT NULL
        )
        """
    )


def _populate_insights_summary_table(connection) -> None:
    """Calculate overview counts, percentages, and configured thresholds."""

    connection.execute(
        f"""
        INSERT INTO {INSIGHTS_SUMMARY_TABLE} (
            summary_id,
            total_scenarios,
            critical_findings,
            harsh_braking_scenarios,
            hard_turning_scenarios,
            harsh_braking_pct,
            hard_turning_pct,
            hard_braking_threshold_g,
            hard_turning_threshold_g
        )
        WITH scenario_counts AS (
            SELECT
                COUNT(*) AS total_scenarios
            FROM {SCENARIOS_TABLE}
        ),
        critical_counts AS (
            SELECT
                COUNT(*) AS critical_findings,
                COALESCE(SUM(harsh_braking), 0)
                    AS harsh_braking_scenarios,
                COALESCE(SUM(hard_turning), 0)
                    AS hard_turning_scenarios
            FROM {CRITICAL_SCENARIOS_TABLE}
        )
        SELECT
            1,
            sc.total_scenarios,
            cc.critical_findings,
            cc.harsh_braking_scenarios,
            cc.hard_turning_scenarios,
            CASE
                WHEN sc.total_scenarios = 0 THEN 0.0
                ELSE (
                    100.0
                    * cc.harsh_braking_scenarios
                    / sc.total_scenarios
                )
            END,
            CASE
                WHEN sc.total_scenarios = 0 THEN 0.0
                ELSE (
                    100.0
                    * cc.hard_turning_scenarios
                    / sc.total_scenarios
                )
            END,
            ?,
            ?
        FROM scenario_counts AS sc
        CROSS JOIN critical_counts AS cc
        """,
        (
            HARD_BRAKING,
            HARD_TURNING,
        ),
    )


def _create_critical_findings_table(connection) -> None:
    """Create one presentation-ready row per critical scenario."""

    connection.execute(
        f"""
        CREATE TABLE {CRITICAL_FINDINGS_TABLE} (
            scenario_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL UNIQUE,
            drive_id TEXT NOT NULL,
            disengagement_timestamp TEXT NOT NULL,
            speed_kph REAL,
            harsh_braking INTEGER NOT NULL,
            hard_turning INTEGER NOT NULL,
            finding_type TEXT NOT NULL,
            peak_braking_g REAL,
            peak_lateral_g REAL,
            braking_threshold_crossing_time_s REAL,
            turning_threshold_crossing_time_s REAL
        )
        """
    )


def _populate_critical_findings_table(connection) -> None:
    """Join critical classifications with scenario-level display context."""

    connection.execute(
        f"""
        INSERT INTO {CRITICAL_FINDINGS_TABLE} (
            scenario_id,
            event_id,
            drive_id,
            disengagement_timestamp,
            speed_kph,
            harsh_braking,
            hard_turning,
            finding_type,
            peak_braking_g,
            peak_lateral_g,
            braking_threshold_crossing_time_s,
            turning_threshold_crossing_time_s
        )
        SELECT
            c.scenario_id,
            c.event_id,
            c.drive_id,
            c.disengagement_timestamp,
            s.event_speed_kph,
            c.harsh_braking,
            c.hard_turning,
            CASE
                WHEN c.harsh_braking = 1
                 AND c.hard_turning = 1
                THEN 'Harsh Braking + Hard Turning'
                WHEN c.harsh_braking = 1
                THEN 'Harsh Braking'
                WHEN c.hard_turning = 1
                THEN 'Hard Turning'
            END AS finding_type,
            c.peak_braking_g,
            c.peak_lateral_g,
            c.braking_threshold_crossing_time_s,
            c.turning_threshold_crossing_time_s
        FROM {CRITICAL_SCENARIOS_TABLE} AS c
        JOIN {SCENARIOS_TABLE} AS s
          ON s.scenario_id = c.scenario_id
        ORDER BY
            c.drive_id,
            c.disengagement_timestamp
        """
    )


def _create_insights_indexes(connection) -> None:
    """Create indexes for common critical-findings access patterns."""

    connection.execute(
        f"""
        CREATE INDEX idx_critical_findings_drive
        ON {CRITICAL_FINDINGS_TABLE}(drive_id)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX idx_critical_findings_timestamp
        ON {CRITICAL_FINDINGS_TABLE}(disengagement_timestamp)
        """
    )

    connection.execute(
        f"""
        CREATE INDEX idx_critical_findings_type
        ON {CRITICAL_FINDINGS_TABLE}(finding_type)
        """
    )


def _rows_to_dicts(cursor) -> list[dict]:
    """Convert SQLite cursor results to dictionaries."""

    columns = [
        description[0]
        for description in cursor.description
    ]

    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


def build_insights(
    database_path: Path = DATABASE_PATH,
) -> None:
    """
    Build final analysis datasets for critical AP disengagement scenarios.

    Creates:

    insights_summary:
        One overview row containing scenario counts, critical finding counts,
        prevalence percentages, and configured critical thresholds.

    critical_findings:
        One presentation-ready row per critical scenario containing the
        classification, disengagement speed, peak responses, and first
        threshold-crossing times.

    Detailed temporal telemetry is not duplicated. Scenario drill-downs read
    directly from the existing scenario_telemetry table.

    Existing insight datasets are replaced each time this function runs.
    """

    _validate_source_tables(database_path)

    with get_connection(database_path) as connection:
        connection.execute(
            f"DROP TABLE IF EXISTS {CRITICAL_FINDINGS_TABLE}"
        )

        connection.execute(
            f"DROP TABLE IF EXISTS {INSIGHTS_SUMMARY_TABLE}"
        )

        _create_insights_summary_table(connection)
        _populate_insights_summary_table(connection)

        _create_critical_findings_table(connection)
        _populate_critical_findings_table(connection)

        _create_insights_indexes(connection)


def get_insights_summary(
    database_path: Path = DATABASE_PATH,
) -> dict:
    """Return the persisted final-analysis overview."""

    with get_connection(database_path) as connection:
        _validate_table(
            connection,
            INSIGHTS_SUMMARY_TABLE,
            {
                "total_scenarios",
                "critical_findings",
                "harsh_braking_scenarios",
                "hard_turning_scenarios",
                "harsh_braking_pct",
                "hard_turning_pct",
                "hard_braking_threshold_g",
                "hard_turning_threshold_g",
            },
            (
                f"Insights summary table "
                f"'{INSIGHTS_SUMMARY_TABLE}' does not exist. "
                "Run build_insights() first."
            ),
        )

        cursor = connection.execute(
            f"""
            SELECT
                total_scenarios,
                critical_findings,
                harsh_braking_scenarios,
                hard_turning_scenarios,
                harsh_braking_pct,
                hard_turning_pct,
                hard_braking_threshold_g,
                hard_turning_threshold_g
            FROM {INSIGHTS_SUMMARY_TABLE}
            WHERE summary_id = 1
            """
        )

        rows = _rows_to_dicts(cursor)

    if not rows:
        raise ValueError(
            f"Insights summary table "
            f"'{INSIGHTS_SUMMARY_TABLE}' is empty. "
            "Run build_insights() again."
        )

    return rows[0]


def get_critical_findings(
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """Return all critical findings for the sortable dashboard table."""

    with get_connection(database_path) as connection:
        _validate_table(
            connection,
            CRITICAL_FINDINGS_TABLE,
            {
                "scenario_id",
                "event_id",
                "drive_id",
                "disengagement_timestamp",
                "speed_kph",
                "harsh_braking",
                "hard_turning",
                "finding_type",
                "peak_braking_g",
                "peak_lateral_g",
                "braking_threshold_crossing_time_s",
                "turning_threshold_crossing_time_s",
            },
            (
                f"Critical findings table "
                f"'{CRITICAL_FINDINGS_TABLE}' does not exist. "
                "Run build_insights() first."
            ),
        )

        cursor = connection.execute(
            f"""
            SELECT
                scenario_id,
                event_id,
                drive_id,
                disengagement_timestamp,
                speed_kph,
                harsh_braking,
                hard_turning,
                finding_type,
                peak_braking_g,
                peak_lateral_g,
                braking_threshold_crossing_time_s,
                turning_threshold_crossing_time_s
            FROM {CRITICAL_FINDINGS_TABLE}
            ORDER BY
                drive_id,
                disengagement_timestamp
            """
        )

        return _rows_to_dicts(cursor)


def get_scenario_insight(
    scenario_id: str,
    database_path: Path = DATABASE_PATH,
) -> dict:
    """
    Return one critical finding and its telemetry for dashboard drill-down.

    Threshold values are returned in plot-ready form:

    hard_braking_g:
        Negative longitudinal threshold because harsh braking is defined as
        longitudinal acceleration less than or equal to -HARD_BRAKING.

    hard_turning_positive_g / hard_turning_negative_g:
        Positive and negative lateral threshold lines because hard turning is
        defined using absolute lateral acceleration.

    disengagement_time_s:
        Always 0.0 and intended for the shared vertical disengagement marker
        on all scenario plots.
    """

    if not scenario_id:
        raise ValueError(
            "scenario_id must be a non-empty string."
        )

    with get_connection(database_path) as connection:
        _validate_table(
            connection,
            CRITICAL_FINDINGS_TABLE,
            {
                "scenario_id",
                "event_id",
                "drive_id",
                "disengagement_timestamp",
                "speed_kph",
                "harsh_braking",
                "hard_turning",
                "finding_type",
                "peak_braking_g",
                "peak_lateral_g",
                "braking_threshold_crossing_time_s",
                "turning_threshold_crossing_time_s",
            },
            (
                f"Critical findings table "
                f"'{CRITICAL_FINDINGS_TABLE}' does not exist. "
                "Run build_insights() first."
            ),
        )

        _validate_table(
            connection,
            SCENARIO_TELEMETRY_TABLE,
            REQUIRED_SCENARIO_TELEMETRY_COLUMNS,
            (
                f"Scenario telemetry table "
                f"'{SCENARIO_TELEMETRY_TABLE}' does not exist. "
                "Run build_scenarios() before requesting drill-down data."
            ),
        )

        finding_cursor = connection.execute(
            f"""
            SELECT
                scenario_id,
                event_id,
                drive_id,
                disengagement_timestamp,
                speed_kph,
                harsh_braking,
                hard_turning,
                finding_type,
                peak_braking_g,
                peak_lateral_g,
                braking_threshold_crossing_time_s,
                turning_threshold_crossing_time_s
            FROM {CRITICAL_FINDINGS_TABLE}
            WHERE scenario_id = ?
            """,
            (scenario_id,),
        )

        finding_rows = _rows_to_dicts(
            finding_cursor
        )

        if not finding_rows:
            raise ValueError(
                f"Critical scenario "
                f"'{scenario_id}' was not found."
            )

        telemetry_cursor = connection.execute(
            f"""
            SELECT
                relative_time_s,
                speed_kph,
                longitudinal_accel_g,
                lateral_accel_g
            FROM {SCENARIO_TELEMETRY_TABLE}
            WHERE scenario_id = ?
            ORDER BY relative_time_s
            """,
            (scenario_id,),
        )

        telemetry = _rows_to_dicts(
            telemetry_cursor
        )

    return {
        "scenario": finding_rows[0],
        "thresholds": {
            "hard_braking_g": -HARD_BRAKING,
            "hard_turning_positive_g": HARD_TURNING,
            "hard_turning_negative_g": -HARD_TURNING,
            "disengagement_time_s": 0.0,
        },
        "telemetry": telemetry,
    }
