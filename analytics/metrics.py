"""Calculate aggregate metrics for persisted Autopilot disengagement events."""

from dataclasses import dataclass
from pathlib import Path

from config import DATABASE_PATH
from telemetry import get_connection


EVENTS_TABLE = "events"

REQUIRED_EVENT_COLUMNS = {
    "event_id",
    "drive_id",
    "disengagement_timestamp",
    "speed_kph",
    "longitudinal_accel_g",
    "lateral_accel_g",
}


SPEED_LABELS = [
    "< 10",
    "10-20",
    "20-30",
    "30-40",
    "40-50",
    "50-60",
    "60+",
]

LONGITUDINAL_ACCEL_LABELS = [
    "< -0.3",
    "-0.3 to -0.2",
    "-0.2 to -0.1",
    "-0.1 to 0.0",
    "0.0 to 0.1",
    "0.1 to 0.2",
    "0.2 to 0.3",
    "0.3+",
]

LATERAL_ACCEL_LABELS = [
    "0.00-0.10",
    "0.10-0.20",
    "0.20-0.30",
    "0.30-0.40",
    "0.40+",
]


@dataclass(frozen=True)
class MetricsResult:
    """
    Aggregate overview of Autopilot disengagement events.

    summary:
        Aggregate statistics describing the event population.

    speed_distribution:
        Event counts grouped by speed at disengagement.

    longitudinal_accel_distribution:
        Event counts grouped by signed longitudinal acceleration
        at disengagement.

    lateral_accel_distribution:
        Event counts grouped by absolute lateral acceleration
        at disengagement.
    """

    summary: dict[str, int | float]
    speed_distribution: list[dict[str, str | int]]
    longitudinal_accel_distribution: list[dict[str, str | int]]
    lateral_accel_distribution: list[dict[str, str | int]]

    def to_dict(self) -> dict:
        """Return the complete metrics result as a JSON-friendly dictionary."""

        return {
            "summary": self.summary,
            "distributions": {
                "speed": self.speed_distribution,
                "longitudinal_acceleration": (
                    self.longitudinal_accel_distribution
                ),
                "lateral_acceleration": self.lateral_accel_distribution,
            },
        }


def _validate_events_table(
    database_path: Path = DATABASE_PATH,
) -> None:
    """
    Validate that the canonical events table exists and supports metrics.

    metrics.py assumes events.py has already materialized the events table.
    """

    with get_connection(database_path) as connection:
        table_exists = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (EVENTS_TABLE,),
        ).fetchone()

        if table_exists is None:
            raise ValueError(
                f"Events table '{EVENTS_TABLE}' does not exist. "
                "Run build_events() before calculating metrics."
            )

        table_info = connection.execute(
            f"PRAGMA table_info({EVENTS_TABLE})"
        ).fetchall()

    available_columns = {row[1] for row in table_info}

    missing_columns = sorted(
        REQUIRED_EVENT_COLUMNS - available_columns
    )

    if missing_columns:
        raise ValueError(
            "Events table is missing required columns: "
            + ", ".join(missing_columns)
        )


def _calculate_summary(
    connection,
) -> dict[str, int | float]:
    """
    Calculate aggregate statistics across all disengagement events.

    Metrics describe only the conditions recorded at the exact
    disengagement moment. No surrounding telemetry is queried.
    """

    row = connection.execute(
        f"""
        SELECT
            COUNT(*) AS event_count,
            COALESCE(
                AVG(speed_kph),
                0.0
            ) AS average_speed_kph,
            COALESCE(
                AVG(longitudinal_accel_g),
                0.0
            ) AS average_longitudinal_accel_g,
            COALESCE(
                AVG(ABS(lateral_accel_g)),
                0.0
            ) AS average_absolute_lateral_accel_g
        FROM {EVENTS_TABLE}
        """
    ).fetchone()

    return {
        "event_count": int(row[0]),
        "average_speed_kph": round(
            float(row[1]),
            2,
        ),
        "average_longitudinal_accel_g": round(
            float(row[2]),
            4,
        ),
        "average_absolute_lateral_accel_g": round(
            float(row[3]),
            4,
        ),
    }


def _format_distribution(
    rows,
    labels: list[str],
) -> list[dict[str, str | int]]:
    """
    Format distribution query results for dashboard consumption.

    All configured bins are returned, including bins with zero events,
    so dashboard chart categories remain stable between datasets.
    """

    counts = {
        str(row[0]): int(row[1])
        for row in rows
    }

    return [
        {
            "range": label,
            "count": counts.get(label, 0),
        }
        for label in labels
    ]


def _calculate_speed_distribution(
    connection,
) -> list[dict[str, str | int]]:
    """Count disengagement events by speed range."""

    rows = connection.execute(
        f"""
        SELECT
            CASE
                WHEN speed_kph < 10.0
                    THEN '< 10'
                WHEN speed_kph < 20.0
                    THEN '10-20'
                WHEN speed_kph < 30.0
                    THEN '20-30'
                WHEN speed_kph < 40.0
                    THEN '30-40'
                WHEN speed_kph < 50.0
                    THEN '40-50'
                WHEN speed_kph < 60.0
                    THEN '50-60'
                ELSE '60+'
            END AS range,
            COUNT(*) AS event_count
        FROM {EVENTS_TABLE}
        WHERE speed_kph IS NOT NULL
        GROUP BY range
        """
    ).fetchall()

    return _format_distribution(
        rows,
        SPEED_LABELS,
    )


def _calculate_longitudinal_accel_distribution(
    connection,
) -> list[dict[str, str | int]]:
    """
    Count disengagement events by longitudinal acceleration range.

    Signed acceleration is preserved because negative and positive
    longitudinal acceleration represent different vehicle behavior.
    """

    rows = connection.execute(
        f"""
        SELECT
            CASE
                WHEN longitudinal_accel_g < -0.30
                    THEN '< -0.3'
                WHEN longitudinal_accel_g < -0.20
                    THEN '-0.3 to -0.2'
                WHEN longitudinal_accel_g < -0.10
                    THEN '-0.2 to -0.1'
                WHEN longitudinal_accel_g < 0.00
                    THEN '-0.1 to 0.0'
                WHEN longitudinal_accel_g < 0.10
                    THEN '0.0 to 0.1'
                WHEN longitudinal_accel_g < 0.20
                    THEN '0.1 to 0.2'
                WHEN longitudinal_accel_g < 0.30
                    THEN '0.2 to 0.3'
                ELSE '0.3+'
            END AS range,
            COUNT(*) AS event_count
        FROM {EVENTS_TABLE}
        WHERE longitudinal_accel_g IS NOT NULL
        GROUP BY range
        """
    ).fetchall()

    return _format_distribution(
        rows,
        LONGITUDINAL_ACCEL_LABELS,
    )


def _calculate_lateral_accel_distribution(
    connection,
) -> list[dict[str, str | int]]:
    """
    Count disengagement events by absolute lateral acceleration range.

    Magnitude is used because the overview measures lateral loading
    rather than left-versus-right direction.
    """

    rows = connection.execute(
        f"""
        SELECT
            CASE
                WHEN ABS(lateral_accel_g) < 0.10
                    THEN '0.00-0.10'
                WHEN ABS(lateral_accel_g) < 0.20
                    THEN '0.10-0.20'
                WHEN ABS(lateral_accel_g) < 0.30
                    THEN '0.20-0.30'
                WHEN ABS(lateral_accel_g) < 0.40
                    THEN '0.30-0.40'
                ELSE '0.40+'
            END AS range,
            COUNT(*) AS event_count
        FROM {EVENTS_TABLE}
        WHERE lateral_accel_g IS NOT NULL
        GROUP BY range
        """
    ).fetchall()

    return _format_distribution(
        rows,
        LATERAL_ACCEL_LABELS,
    )


def calculate_summary_metrics(
    database_path: Path = DATABASE_PATH,
) -> dict[str, int | float]:
    """Calculate aggregate statistics for all disengagement events."""

    _validate_events_table(database_path)

    with get_connection(database_path) as connection:
        return _calculate_summary(connection)


def calculate_speed_distribution(
    database_path: Path = DATABASE_PATH,
) -> list[dict[str, str | int]]:
    """Calculate the disengagement speed distribution."""

    _validate_events_table(database_path)

    with get_connection(database_path) as connection:
        return _calculate_speed_distribution(connection)


def calculate_longitudinal_accel_distribution(
    database_path: Path = DATABASE_PATH,
) -> list[dict[str, str | int]]:
    """Calculate the disengagement longitudinal acceleration distribution."""

    _validate_events_table(database_path)

    with get_connection(database_path) as connection:
        return _calculate_longitudinal_accel_distribution(
            connection
        )


def calculate_lateral_accel_distribution(
    database_path: Path = DATABASE_PATH,
) -> list[dict[str, str | int]]:
    """Calculate the disengagement lateral acceleration distribution."""

    _validate_events_table(database_path)

    with get_connection(database_path) as connection:
        return _calculate_lateral_accel_distribution(
            connection
        )


def calculate_metrics(
    database_path: Path = DATABASE_PATH,
) -> MetricsResult:
    """
    Calculate the complete AP disengagement metrics overview.

    This is the primary entry point for metrics.py.

    All calculations operate directly on the persisted SQLite events
    table. Summary statistics and distribution counts are calculated in
    SQL and returned as a JSON-friendly MetricsResult for downstream
    consumers such as the dashboard.
    """

    _validate_events_table(database_path)

    with get_connection(database_path) as connection:
        summary = _calculate_summary(connection)

        speed_distribution = (
            _calculate_speed_distribution(connection)
        )

        longitudinal_accel_distribution = (
            _calculate_longitudinal_accel_distribution(
                connection
            )
        )

        lateral_accel_distribution = (
            _calculate_lateral_accel_distribution(
                connection
            )
        )

    return MetricsResult(
        summary=summary,
        speed_distribution=speed_distribution,
        longitudinal_accel_distribution=(
            longitudinal_accel_distribution
        ),
        lateral_accel_distribution=(
            lateral_accel_distribution
        ),
    )
