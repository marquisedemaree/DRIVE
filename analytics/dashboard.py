'''

"""Analytics Mode dashboard interface."""

from telemetry import (
    run_pipeline,
    sample_records,
    summarize_pipeline,
)


def get_dashboard_data():
    """Run the telemetry pipeline and serve dashboard-ready Analytics Mode data."""
    result = run_pipeline()
    summary = summarize_pipeline(
        result
    )

    return {
        "mode": "analytics",
        "title": "Fleet Analytics",
        "status": (
            "Telemetry pipeline ready."
            if summary[
                "files_processed"
            ]
            else "No telemetry data found."
        ),
        "pipeline": summary,
        "telemetry_sample": (
            sample_records(
                result,
                limit=100,
            )
        ),
        "sections": [
            "Telemetry Overview",
            "Performance Metrics",
            "Driving Events",
            "Scenario Analysis",
        ],
    }

'''

"""Analytics Mode dashboard interface."""


import math
from typing import Any

from analytics.insights import generate_analysis
from analytics.metrics import run_metrics_pipeline
from telemetry import run_pipeline, sample_records, summarize_pipeline


def _json_safe(value: Any) -> Any:
    """Recursively normalize pandas/numpy-style values for FastAPI JSON responses."""
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


def get_dashboard_data() -> dict[str, Any]:
    """Run Analytics Mode pipelines and return dashboard-ready overview data."""
    result = run_pipeline()
    summary = summarize_pipeline(result)

    response: dict[str, Any] = {
        "mode": "analytics",
        "title": "Fleet Analytics",
        "status": (
            "Telemetry, metrics, and automated analysis ready."
            if summary["files_processed"]
            else "No telemetry data found."
        ),
        "pipeline": summary,
        "telemetry_sample": sample_records(
            result,
            limit=100,
        ),
        "drives": [],
        "fleet_analysis": None,
        "sections": [
            "Telemetry Overview",
            "Performance Metrics",
            "Driving Events",
            "Automated Insights",
            "Scenario Analysis",
        ],
    }

    if result.data.empty:
        return response

    # Metrics are derived from the same canonical telemetry produced by this run
    # and persisted so the SDK/insights layer can serve consistent downstream reads.
    metrics_result = run_metrics_pipeline(
        result.data,
        persist=True,
    )

    if not metrics_result.drive_metrics.empty:
        response["drives"] = (
            metrics_result.drive_metrics["drive_id"]
            .astype(str)
            .drop_duplicates()
            .tolist()
        )

    response["fleet_analysis"] = (
        generate_analysis().to_dict()
    )

    return _json_safe(response)


def get_analysis_data(
    drive_id: str | None = None,
    compare_to: str | None = None,
) -> dict[str, Any]:
    """Return an on-demand automated analysis report for dashboard drill-down."""
    report = generate_analysis(
        drive_id=drive_id,
        compare_to=compare_to,
    )

    return _json_safe(
        report.to_dict()
    )
