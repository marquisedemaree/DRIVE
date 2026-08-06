"""Compose persisted Analytics Mode results for the dashboard."""

import math
from pathlib import Path
from typing import Any

import pandas as pd

from analytics.insights import (
    get_critical_findings,
    get_insights_summary,
    get_scenario_insight,
)
from analytics.metrics import calculate_metrics
from config import DATABASE_PATH, INGESTION_TABLE
from telemetry import get_connection


EVENTS_TABLE = "events"
TEMPORAL_ANALYSIS_TABLE = "temporal_analysis"


def _json_safe(value: Any) -> Any:
    """Recursively normalize values for FastAPI JSON responses."""

    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _json_safe(item)
            for item in value
        ]

    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass

    return str(value)


def _table_exists(
    connection,
    table_name: str,
) -> bool:
    """Return whether a SQLite table exists."""

    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


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


def _get_pipeline_summary(
    database_path: Path = DATABASE_PATH,
) -> dict:
    """
    Return processing statistics from the latest persisted ingestion run.

    The dashboard reads persisted metadata rather than rerunning telemetry
    ingestion on each request.
    """

    with get_connection(database_path) as connection:
        if not _table_exists(
            connection,
            INGESTION_TABLE,
        ):
            raise ValueError(
                f"Ingestion history table '{INGESTION_TABLE}' "
                "does not exist. Run the telemetry pipeline first."
            )

        cursor = connection.execute(
            f"""
            SELECT
                files_processed,
                rows_ingested,
                rows_served,
                rows_dropped
            FROM {INGESTION_TABLE}
            ORDER BY id DESC
            LIMIT 1
            """
        )

        rows = _rows_to_dicts(cursor)

    if not rows:
        raise ValueError(
            f"Ingestion history table '{INGESTION_TABLE}' "
            "is empty. Run the telemetry pipeline first."
        )

    return rows[0]

'''
def _get_event_overview(
    database_path: Path = DATABASE_PATH,
) -> dict:
    """Return aggregate AP disengagement metrics and distributions."""

    with get_connection(database_path) as connection:
        if not _table_exists(
            connection,
            EVENTS_TABLE,
        ):
            raise ValueError(
                f"Events table '{EVENTS_TABLE}' does not exist. "
                "Run build_events() first."
            )

        events = pd.read_sql_query(
            f"""
            SELECT
                event_id,
                drive_id,
                disengagement_timestamp,
                speed_kph,
                longitudinal_accel_g,
                lateral_accel_g
            FROM {EVENTS_TABLE}
            ORDER BY
                drive_id,
                disengagement_timestamp
            """,
            connection,
        )

    return calculate_metrics(events).to_dict()
'''
def _get_event_overview(
    database_path: Path = DATABASE_PATH,
) -> dict:
    """Return event-level metrics for the dashboard."""

    return calculate_metrics(
        database_path=database_path,
    ).to_dict()

def _get_aggregate_analysis(
    database_path: Path = DATABASE_PATH,
) -> dict:
    """Return persisted aggregate temporal trajectories."""

    with get_connection(database_path) as connection:
        if not _table_exists(
            connection,
            TEMPORAL_ANALYSIS_TABLE,
        ):
            raise ValueError(
                f"Aggregate table '{TEMPORAL_ANALYSIS_TABLE}' "
                "does not exist. Run build_aggregate() first."
            )

        cursor = connection.execute(
            f"""
            SELECT
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
            FROM {TEMPORAL_ANALYSIS_TABLE}
            ORDER BY relative_time_s
            """
        )

        temporal = _rows_to_dicts(cursor)

    return {
        "disengagement_time_s": 0.0,
        "temporal": temporal,
    }


def _get_critical_analysis(
    database_path: Path = DATABASE_PATH,
) -> dict:
    """Return critical-finding overview and sortable findings."""

    summary = get_insights_summary(
        database_path=database_path,
    )

    findings = get_critical_findings(
        database_path=database_path,
    )

    return {
        "summary": summary,
        "findings": findings,
    }


def get_dashboard_data(
    database_path: Path = DATABASE_PATH,
) -> dict:
    """
    Return the complete Analytics Mode dashboard overview.

    This function is read-only. It does not rerun telemetry ingestion or
    rebuild analytical datasets. The full analysis pipeline should be run
    before the dashboard is requested.

    Includes:
        - latest pipeline processing statistics,
        - AP disengagement event metrics and distributions,
        - aggregate scenario trajectories,
        - critical-finding summary,
        - sortable critical findings.

    Detailed selected-scenario telemetry is intentionally excluded and is
    retrieved separately through get_scenario_data().
    """

    response = {
        "mode": "analytics",
        "title": "Fleet Analytics",
        "status": "Analytics ready.",
        "pipeline": _get_pipeline_summary(
            database_path,
        ),
        "events": _get_event_overview(
            database_path,
        ),
        "aggregate": _get_aggregate_analysis(
            database_path,
        ),
        "critical_analysis": _get_critical_analysis(
            database_path,
        ),
        "sections": [
            "Pipeline Overview",
            "Event Overview",
            "Aggregate Scenario Analysis",
            "Critical Findings",
            "Scenario Drill-Down",
        ],
    }

    return _json_safe(response)


def get_scenario_data(
    scenario_id: str,
    database_path: Path = DATABASE_PATH,
) -> dict:
    """
    Return one selected critical scenario for dashboard drill-down.

    The response contains:
        - finding and event metadata,
        - plot-ready threshold values,
        - ordered scenario telemetry from the existing scenario_telemetry table.
    """

    if not scenario_id:
        raise ValueError(
            "scenario_id must be a non-empty string."
        )

    result = get_scenario_insight(
        scenario_id=scenario_id,
        database_path=database_path,
    )

    return _json_safe(result)
