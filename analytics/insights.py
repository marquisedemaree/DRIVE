"""Automated analysis workflows for DRIVE Analytics Mode.

This module turns persisted fleet metrics and driving events into reusable,
higher-level findings. Data access stays in FleetDataSDK and metric/event
semantics stay in analytics.metrics; this module focuses on interpretation,
comparison, prioritization, and report generation.
"""


from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from analytics.sdk import FleetDataSDK
from config import DATABASE_PATH


EVENT_RATE_COLUMNS = (
    "hard_braking_per_100_km",
    "rapid_acceleration_per_100_km",
    "sharp_steering_per_100_km",
    "high_lateral_accel_per_100_km",
    "events_per_100_km",
)

DEFAULT_NOTABILITY_METRICS = (
    "events_per_100_km",
    "hard_braking_per_100_km",
    "rapid_acceleration_per_100_km",
    "sharp_steering_per_100_km",
    "high_lateral_accel_per_100_km",
    "max_speed_kph",
)

LOW_IS_NOTABLE_METRICS = {
    "autopilot_active_pct",
}


@dataclass(frozen=True)
class Insight:
    """One structured analytical finding."""

    name: str
    summary: str
    value: Any = None
    severity: str = "info"
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """Return a JSON-friendly dictionary representation."""
        return asdict(self)


@dataclass(frozen=True)
class AnalysisReport:
    """Structured result returned by automated analysis workflows."""

    title: str
    scope: str
    summary: dict[str, Any]
    insights: tuple[
        Insight,
        ...,
    ] = ()
    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """Return a JSON-friendly dictionary representation."""
        result = asdict(
            self
        )

        result[
            "insights"
        ] = [
            insight.to_dict()
            for insight
            in self.insights
        ]

        return result


def _records(
    frame: pd.DataFrame,
) -> list[
    dict[str, Any]
]:
    """Convert a DataFrame to records while normalizing missing values."""
    if frame.empty:
        return []

    clean = (
        frame
        .astype(object)
        .where(
            pd.notna(frame),
            None,
        )
    )

    return clean.to_dict(
        orient="records"
    )


def _numeric(
    value: Any,
) -> float | None:
    """Return a finite float when a value is numeric."""
    try:
        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    return (
        number
        if np.isfinite(
            number
        )
        else None
    )


def _format_number(
    value: Any,
    digits: int = 2,
) -> str:
    """Format a numeric value for generated insight text."""
    number = _numeric(
        value
    )

    if number is None:
        return "N/A"

    return (
        f"{number:.{digits}f}"
    )


def summarize_metrics(
    metrics:
        pd.DataFrame
        | dict[str, Any],
) -> dict[str, Any]:
    """Create a compact metric summary from one drive or aggregate metrics."""
    if isinstance(
        metrics,
        pd.DataFrame,
    ):
        if metrics.empty:
            return {}

        if len(metrics) != 1:
            raise ValueError(
                "summarize_metrics expects "
                "exactly one metric row."
            )

        row = (
            metrics
            .iloc[0]
            .to_dict()
        )

    else:
        row = dict(
            metrics
        )

    preferred = (
        "drive_id",
        "drives",
        "duration_s",
        "distance_km",
        "average_speed_kph",
        "max_speed_kph",
        "autopilot_active_time_s",
        "autopilot_active_distance_km",
        "autopilot_active_pct",
        "hard_braking_count",
        "hard_braking_per_100_km",
        "rapid_acceleration_count",
        "rapid_acceleration_per_100_km",
        "sharp_steering_count",
        "sharp_steering_per_100_km",
        "high_lateral_accel_count",
        "high_lateral_accel_per_100_km",
        "total_events",
        "events_per_100_km",
    )

    return {
        key: row[key]
        for key
        in preferred
        if key in row
    }


def summarize_events(
    events: pd.DataFrame,
) -> dict[str, Any]:
    """Summarize event counts, severity, and timing."""
    if events.empty:
        return {
            "total_events": 0,
            "event_counts": {},
            "max_severity_score":
                0.0,
            "most_common_event_type":
                None,
            "highest_severity_event":
                None,
        }

    counts = (
        events[
            "event_type"
        ]
        .value_counts()
        .to_dict()
        if "event_type"
        in events
        else {}
    )

    if (
        "severity_score"
        in events.columns
    ):
        severity = (
            pd.to_numeric(
                events[
                    "severity_score"
                ],
                errors="coerce",
            )
        )
    else:
        severity = (
            pd.Series(
                np.nan,
                index=events.index,
                dtype=float,
            )
        )

    highest = None

    if severity.notna().any():
        highest_index = (
            severity.idxmax()
        )

        highest = _records(
            events.loc[
                [
                    highest_index
                ]
            ]
        )[0]

    return {
        "total_events":
            int(
                len(events)
            ),

        "event_counts": {
            str(key):
                int(value)
            for (
                key,
                value,
            )
            in counts.items()
        },

        "max_severity_score": (
            float(
                severity.max()
            )
            if severity
            .notna()
            .any()
            else 0.0
        ),

        "most_common_event_type": (
            str(
                next(
                    iter(
                        counts
                    )
                )
            )
            if counts
            else None
        ),

        "highest_severity_event":
            highest,
    }


def compare_metrics(
    left:
        pd.Series
        | dict[str, Any],
    right:
        pd.Series
        | dict[str, Any],
    metric_names:
        Sequence[str]
        | None = None,
) -> pd.DataFrame:
    """Compare numeric metrics and calculate absolute and percentage differences.

    Percentage difference is measured from left to right:
    (right - left) / abs(left) * 100.

    When the left value is zero, percentage difference is undefined
    and returned as NaN.
    """
    left_values = dict(
        left
    )

    right_values = dict(
        right
    )

    if metric_names is None:
        shared = (
            left_values.keys()
            & right_values.keys()
        )

        metric_names = [
            key
            for key
            in shared
            if (
                _numeric(
                    left_values[
                        key
                    ]
                )
                is not None
                and
                _numeric(
                    right_values[
                        key
                    ]
                )
                is not None
            )
        ]

    rows: list[
        dict[str, Any]
    ] = []

    for metric in metric_names:
        if (
            metric
            not in left_values
            or metric
            not in right_values
        ):
            continue

        left_number = _numeric(
            left_values[
                metric
            ]
        )

        right_number = _numeric(
            right_values[
                metric
            ]
        )

        if (
            left_number is None
            or
            right_number is None
        ):
            continue

        difference = (
            right_number
            - left_number
        )

        pct_difference = (
            np.nan
            if left_number == 0
            else (
                difference
                / abs(
                    left_number
                )
            )
            * 100.0
        )

        rows.append(
            {
                "metric":
                    metric,

                "left_value":
                    left_number,

                "right_value":
                    right_number,

                "difference":
                    difference,

                "pct_difference":
                    pct_difference,
            }
        )

    return pd.DataFrame(
        rows,
        columns=(
            "metric",
            "left_value",
            "right_value",
            "difference",
            "pct_difference",
        ),
    )


def analyze_trends(
    metrics: pd.DataFrame,
    metric_names:
        Sequence[str]
        | None = None,
    order_by:
        str = "start_time",
) -> pd.DataFrame:
    """Describe first-to-last changes for drive-level metrics.

    This is intentionally lightweight descriptive trend analysis rather
    than forecasting.
    """
    columns = (
        "metric",
        "first_value",
        "last_value",
        "absolute_change",
        "change_pct",
        "direction",
    )

    if (
        metrics.empty
        or len(metrics) < 2
    ):
        return pd.DataFrame(
            columns=columns
        )

    frame = metrics.copy()

    if (
        order_by
        in frame.columns
    ):
        frame[
            order_by
        ] = pd.to_datetime(
            frame[
                order_by
            ],
            errors="coerce",
            utc=True,
        )

        frame = (
            frame.sort_values(
                order_by,
                kind="stable",
            )
        )

    if metric_names is None:
        metric_names = [
            column
            for column
            in frame.columns
            if (
                column
                != "drive_id"
                and
                pd.api.types
                .is_numeric_dtype(
                    frame[
                        column
                    ]
                )
            )
        ]

    rows = []

    for metric in metric_names:
        if (
            metric
            not in frame.columns
        ):
            continue

        values = (
            pd.to_numeric(
                frame[
                    metric
                ],
                errors="coerce",
            )
            .dropna()
        )

        if len(values) < 2:
            continue

        first = float(
            values.iloc[0]
        )

        last = float(
            values.iloc[-1]
        )

        change = (
            last - first
        )

        change_pct = (
            np.nan
            if first == 0
            else (
                change
                / abs(first)
            )
            * 100.0
        )

        tolerance = (
            max(
                abs(first),
                abs(last),
                1.0,
            )
            * 1e-9
        )

        if (
            abs(change)
            <= tolerance
        ):
            direction = (
                "stable"
            )

        elif change > 0:
            direction = (
                "increasing"
            )

        else:
            direction = (
                "decreasing"
            )

        rows.append(
            {
                "metric":
                    metric,

                "first_value":
                    first,

                "last_value":
                    last,

                "absolute_change":
                    change,

                "change_pct":
                    change_pct,

                "direction":
                    direction,
            }
        )

    return pd.DataFrame(
        rows,
        columns=columns,
    )


def find_notable_metrics(
    metrics: pd.DataFrame,
    drive_id: str,
    metric_names:
        Sequence[str] = (
            DEFAULT_NOTABILITY_METRICS
        ),
    percentile:
        float = 0.95,
) -> list[Insight]:
    """Find drive metrics that are extreme relative to available drives."""
    if not (
        0.5
        < percentile
        < 1.0
    ):
        raise ValueError(
            "percentile must be "
            "greater than 0.5 "
            "and less than 1.0."
        )

    if (
        metrics.empty
        or "drive_id"
        not in metrics.columns
    ):
        return []

    target_rows = (
        metrics.loc[
            metrics[
                "drive_id"
            ]
            .astype(str)
            == str(
                drive_id
            )
        ]
    )

    if target_rows.empty:
        return []

    target = (
        target_rows
        .iloc[0]
    )

    findings: list[
        Insight
    ] = []

    for metric in metric_names:
        if (
            metric
            not in metrics.columns
        ):
            continue

        population = (
            pd.to_numeric(
                metrics[
                    metric
                ],
                errors="coerce",
            )
            .dropna()
        )

        value = _numeric(
            target.get(
                metric
            )
        )

        if (
            value is None
            or
            len(
                population
            ) < 3
        ):
            continue

        low_is_notable = (
            metric
            in LOW_IS_NOTABLE_METRICS
        )

        quantile = (
            1.0
            - percentile
            if low_is_notable
            else percentile
        )

        threshold = float(
            population.quantile(
                quantile
            )
        )

        notable = (
            value
            <= threshold
            if low_is_notable
            else value
            >= threshold
        )

        if not notable:
            continue

        percentile_rank = float(
            (
                population
                <= value
            )
            .mean()
            * 100.0
        )

        direction = (
            "low"
            if low_is_notable
            else "high"
        )

        severity = (
            "high"
            if (
                percentile_rank
                >= 99.0
                or
                percentile_rank
                <= 1.0
            )
            else "medium"
        )

        findings.append(
            Insight(
                name=(
                    f"notable_"
                    f"{metric}"
                ),

                summary=(
                    f"{metric} is "
                    f"unusually "
                    f"{direction} at "
                    f"{_format_number(value)}, "
                    "relative to the "
                    "analyzed drives."
                ),

                value=value,

                severity=
                    severity,

                metadata={
                    "metric":
                        metric,

                    "threshold":
                        threshold,

                    "percentile_rank":
                        round(
                            percentile_rank,
                            2,
                        ),

                    "comparison_percentile":
                        percentile,
                },
            )
        )

    return findings


def _event_insights(
    events: pd.DataFrame,
) -> list[Insight]:
    """Create a small set of event-oriented findings."""
    summary = summarize_events(
        events
    )

    findings: list[
        Insight
    ] = []

    if (
        summary[
            "total_events"
        ]
        == 0
    ):
        findings.append(
            Insight(
                name=(
                    "no_detected_events"
                ),

                summary=(
                    "No configured "
                    "driving events "
                    "were detected "
                    "for this scope."
                ),

                value=0,
                severity="info",
            )
        )

        return findings

    most_common = (
        summary[
            "most_common_event_type"
        ]
    )

    most_common_count = (
        summary[
            "event_counts"
        ].get(
            most_common,
            0,
        )
        if most_common
        else 0
    )

    findings.append(
        Insight(
            name=(
                "most_common_event"
            ),

            summary=(
                f"{most_common} was "
                "the most common "
                "detected event "
                f"({most_common_count})."
            ),

            value=
                most_common_count,

            severity="info",

            metadata={
                "event_type":
                    most_common
            },
        )
    )

    highest = (
        summary[
            "highest_severity_event"
        ]
    )

    if highest:
        findings.append(
            Insight(
                name=(
                    "highest_severity_event"
                ),

                summary=(
                    "The highest-severity "
                    "event was "
                    f"{highest.get('event_type')} "
                    "with severity "
                    f"{_format_number(highest.get('severity_score'))}."
                ),

                value=
                    highest.get(
                        "severity_score"
                    ),

                severity="high",
                metadata=highest,
            )
        )

    return findings


def analyze_drive(
    drive_id: str,
    sdk:
        FleetDataSDK
        | None = None,
    database_path:
        Path = DATABASE_PATH,
    percentile:
        float = 0.95,
) -> AnalysisReport:
    """Generate a standardized analysis report for one drive."""
    client = (
        sdk
        or FleetDataSDK(
            database_path=
                database_path
        )
    )

    drive_summary = (
        client.summary(
            drive_id
        )
    )

    drive_metrics = (
        client.metrics(
            drive_id=
                drive_id
        )
    )

    events = (
        client.events(
            drive_id=
                drive_id
        )
    )

    all_metrics = (
        client.metrics()
    )

    metric_summary = (
        summarize_metrics(
            drive_metrics
        )
    )

    event_summary = (
        summarize_events(
            events
        )
    )

    findings = (
        find_notable_metrics(
            all_metrics,
            drive_id=
                drive_id,
            percentile=
                percentile,
        )
    )

    findings.extend(
        _event_insights(
            events
        )
    )

    total_rate = _numeric(
        metric_summary.get(
            "events_per_100_km"
        )
    )

    if (
        total_rate
        is not None
    ):
        findings.insert(
            0,
            Insight(
                name=(
                    "event_rate"
                ),

                summary=(
                    "The drive recorded "
                    f"{_format_number(total_rate)} "
                    "detected events "
                    "per 100 km."
                ),

                value=
                    total_rate,

                severity="info",
            ),
        )

    summary = dict(
        drive_summary
    )

    summary[
        "metrics"
    ] = metric_summary

    summary[
        "events"
    ] = event_summary

    return AnalysisReport(
        title=(
            "Drive Analysis: "
            f"{drive_id}"
        ),

        scope="drive",

        summary=summary,

        insights=tuple(
            findings
        ),

        metadata={
            "drive_id":
                drive_id,

            "comparison_percentile":
                percentile,
        },
    )


def analyze_fleet(
    sdk:
        FleetDataSDK
        | None = None,
    database_path:
        Path = DATABASE_PATH,
) -> AnalysisReport:
    """Generate a fleet-level summary from persisted analytics outputs."""
    client = (
        sdk
        or FleetDataSDK(
            database_path=
                database_path
        )
    )

    drives = (
        client.drives()
    )

    metrics = (
        client.metrics()
    )

    aggregate = (
        client.aggregate_metrics()
    )

    events = (
        client.events()
    )

    if isinstance(
        aggregate,
        pd.DataFrame,
    ):
        aggregate_summary = (
            summarize_metrics(
                aggregate
            )
            if not aggregate.empty
            else {}
        )

    else:
        aggregate_summary = (
            summarize_metrics(
                aggregate
            )
        )

    event_summary = (
        summarize_events(
            events
        )
    )

    trends = analyze_trends(
        metrics,

        metric_names=[
            metric
            for metric
            in EVENT_RATE_COLUMNS
            if metric
            in metrics.columns
        ],
    )

    findings = (
        _event_insights(
            events
        )
    )

    if (
        not metrics.empty
        and
        "events_per_100_km"
        in metrics.columns
    ):
        rates = (
            pd.to_numeric(
                metrics[
                    "events_per_100_km"
                ],
                errors="coerce",
            )
        )

        if (
            rates
            .notna()
            .any()
        ):
            index = (
                rates.idxmax()
            )

            row = (
                metrics.loc[
                    index
                ]
            )

            event_rate = (
                row.get(
                    "events_per_100_km"
                )
            )

            findings.insert(
                0,
                Insight(
                    name=(
                        "highest_event_rate_drive"
                    ),

                    summary=(
                        "Drive "
                        f"{row.get('drive_id')} "
                        "had the highest "
                        "detected-event rate "
                        "at "
                        f"{_format_number(event_rate)} "
                        "per 100 km."
                    ),

                    value=
                        event_rate,

                    severity=
                        "medium",

                    metadata={
                        "drive_id":
                            row.get(
                                "drive_id"
                            )
                    },
                ),
            )

    return AnalysisReport(
        title=(
            "Fleet Analysis"
        ),

        scope="fleet",

        summary={
            "drive_count":
                int(
                    len(
                        drives
                    )
                ),

            "aggregate_metrics":
                aggregate_summary,

            "events":
                event_summary,

            "trends":
                _records(
                    trends
                ),
        },

        insights=tuple(
            findings
        ),

        metadata={
            "metric_rows":
                int(
                    len(
                        metrics
                    )
                ),

            "event_rows":
                int(
                    len(
                        events
                    )
                ),
        },
    )


def compare_drives(
    left_drive_id: str,
    right_drive_id: str,
    sdk:
        FleetDataSDK
        | None = None,
    database_path:
        Path = DATABASE_PATH,
    metric_names:
        Sequence[str]
        | None = None,
) -> AnalysisReport:
    """Compare two drives using their persisted metric rows."""
    client = (
        sdk
        or FleetDataSDK(
            database_path=
                database_path
        )
    )

    left_frame = (
        client.metrics(
            drive_id=
                left_drive_id
        )
    )

    right_frame = (
        client.metrics(
            drive_id=
                right_drive_id
        )
    )

    if left_frame.empty:
        raise ValueError(
            "No metrics found for "
            f"drive '{left_drive_id}'."
        )

    if right_frame.empty:
        raise ValueError(
            "No metrics found for "
            f"drive '{right_drive_id}'."
        )

    left = (
        left_frame
        .iloc[0]
    )

    right = (
        right_frame
        .iloc[0]
    )

    comparison = (
        compare_metrics(
            left,
            right,
            metric_names=
                metric_names,
        )
    )

    findings: list[
        Insight
    ] = []

    for (
        _,
        row,
    ) in comparison.iterrows():

        pct = (
            row[
                "pct_difference"
            ]
        )

        if (
            pd.isna(
                pct
            )
            or
            abs(
                float(
                    pct
                )
            ) < 10.0
        ):
            continue

        direction = (
            "higher"
            if (
                row[
                    "difference"
                ]
                > 0
            )
            else "lower"
        )

        absolute_pct = abs(
            float(
                pct
            )
        )

        findings.append(
            Insight(
                name=(
                    "comparison_"
                    f"{row['metric']}"
                ),

                summary=(
                    f"{row['metric']} was "
                    f"{absolute_pct:.1f}% "
                    f"{direction} in "
                    f"{right_drive_id} "
                    "than "
                    f"{left_drive_id}."
                ),

                value=
                    float(
                        pct
                    ),

                severity=(
                    "medium"
                    if absolute_pct
                    < 50.0
                    else "high"
                ),

                metadata={
                    "metric":
                        row[
                            "metric"
                        ],

                    "left_drive_id":
                        left_drive_id,

                    "right_drive_id":
                        right_drive_id,
                },
            )
        )

    return AnalysisReport(
        title=(
            "Drive Comparison: "
            f"{left_drive_id} "
            "vs "
            f"{right_drive_id}"
        ),

        scope=(
            "comparison"
        ),

        summary={
            "left_drive_id":
                left_drive_id,

            "right_drive_id":
                right_drive_id,

            "metrics":
                _records(
                    comparison
                ),
        },

        insights=tuple(
            findings
        ),

        metadata={
            "comparison_count":
                int(
                    len(
                        comparison
                    )
                )
        },
    )


def generate_analysis(
    drive_id:
        str | None = None,
    compare_to:
        str | None = None,
    sdk:
        FleetDataSDK
        | None = None,
    database_path:
        Path = DATABASE_PATH,
) -> AnalysisReport:
    """Run the appropriate reusable analysis workflow.

    - no drive_id: fleet analysis
    - drive_id only: single-drive analysis
    - drive_id + compare_to: drive comparison
    """
    if (
        compare_to is not None
        and
        drive_id is None
    ):
        raise ValueError(
            "drive_id is required "
            "when compare_to is "
            "provided."
        )

    if drive_id is None:
        return analyze_fleet(
            sdk=sdk,
            database_path=
                database_path,
        )

    if compare_to is not None:
        return compare_drives(
            drive_id,
            compare_to,
            sdk=sdk,
            database_path=
                database_path,
        )

    return analyze_drive(
        drive_id,
        sdk=sdk,
        database_path=
            database_path,
    )


__all__ = [
    "AnalysisReport",
    "Insight",
    "EVENT_RATE_COLUMNS",
    "DEFAULT_NOTABILITY_METRICS",
    "analyze_drive",
    "analyze_fleet",
    "analyze_trends",
    "compare_drives",
    "compare_metrics",
    "find_notable_metrics",
    "generate_analysis",
    "summarize_events",
    "summarize_metrics",
]
