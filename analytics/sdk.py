"""Reusable Fleet Data SDK for DRIVE Analytics Mode."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd

from config import DATABASE_PATH, TELEMETRY_TABLE
from telemetry import CANONICAL_COLUMNS, get_drive_summary, query_telemetry
from analytics.metrics import (
    DRIVE_METRIC_COLUMNS,
    calculate_aggregate_metrics,
    get_drive_metrics,
    get_events,
)


class FleetDataSDKError(Exception):
    """Base exception for Fleet Data SDK errors."""


class DriveNotFoundError(FleetDataSDKError):
    """Raised when a requested drive does not exist."""


class InvalidTelemetryColumnError(FleetDataSDKError):
    """Raised when a telemetry query requests an unknown canonical column."""


class UnknownMetricError(FleetDataSDKError):
    """Raised when a requested metric is not available."""


class UnsupportedExportFormatError(FleetDataSDKError):
    """Raised when export() receives an unsupported file extension."""


class FleetDataSDK:
    """High-level, reusable interface for querying DRIVE Analytics Mode data."""

    def __init__(self, database_path: Path = DATABASE_PATH) -> None:
        self.database_path = Path(database_path)

    def drives(self) -> pd.DataFrame:
        """Return one summary row per available drive."""
        return get_drive_summary(database_path=self.database_path)

    def drive(self, drive_id: str) -> pd.Series:
        """Return the summary row for one drive."""
        drives = self.drives()
        match = drives.loc[drives["drive_id"] == drive_id]

        if match.empty:
            raise DriveNotFoundError(
                f"No telemetry found for drive '{drive_id}'."
            )

        return match.iloc[0]

    def telemetry(
        self,
        *,
        drive_id: str | None = None,
        columns: Sequence[str] | None = None,
        start_time: str | pd.Timestamp | None = None,
        end_time: str | pd.Timestamp | None = None,
        autopilot_state: str | None = None,
        min_speed_kph: float | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Query canonical telemetry without requiring callers to write SQL."""
        if limit is not None and limit <= 0:
            raise ValueError(
                "limit must be greater than zero when provided."
            )

        selected = (
            list(columns)
            if columns is not None
            else list(CANONICAL_COLUMNS)
        )

        invalid = sorted(set(selected) - set(CANONICAL_COLUMNS))

        if invalid:
            raise InvalidTelemetryColumnError(
                "Unknown telemetry columns: " + ", ".join(invalid)
            )

        # Retain drive_id when filtering so results remain self-identifying.
        if drive_id is not None and "drive_id" not in selected:
            selected.insert(0, "drive_id")

        conditions: list[str] = []
        params: list[object] = []

        if drive_id is not None:
            conditions.append("drive_id = ?")
            params.append(drive_id)

        if start_time is not None:
            conditions.append("timestamp >= ?")
            params.append(self._sql_timestamp(start_time))

        if end_time is not None:
            conditions.append("timestamp <= ?")
            params.append(self._sql_timestamp(end_time))

        if autopilot_state is not None:
            conditions.append("autopilot_state = ?")
            params.append(autopilot_state)

        if min_speed_kph is not None:
            conditions.append("speed_kph >= ?")
            params.append(float(min_speed_kph))

        where = (
            "WHERE " + " AND ".join(conditions)
            if conditions
            else ""
        )

        limit_clause = ""

        if limit is not None:
            limit_clause = "LIMIT ?"
            params.append(limit)

        column_sql = ", ".join(
            f'"{column}"'
            for column in selected
        )

        data = query_telemetry(
            f"""
            SELECT {column_sql}
            FROM {TELEMETRY_TABLE}
            {where}
            ORDER BY timestamp
            {limit_clause}
            """,
            params=params,
            database_path=self.database_path,
        )

        if drive_id is not None and data.empty:
            raise DriveNotFoundError(
                f"No telemetry found for drive '{drive_id}'."
            )

        return data

    def metrics(
        self,
        drive_id: str | None = None,
    ) -> pd.DataFrame:
        """Return persisted per-drive performance metrics."""
        data = get_drive_metrics(
            drive_id=drive_id,
            database_path=self.database_path,
        )

        if drive_id is not None and data.empty:
            raise DriveNotFoundError(
                f"No metrics found for drive '{drive_id}'."
            )

        return data

    def metric(
        self,
        name: str,
        drive_id: str | None = None,
    ):
        """Return one drive-level or aggregate metric."""
        if drive_id is not None:
            metrics = self.metrics(drive_id)

            if name not in metrics.columns:
                raise UnknownMetricError(
                    f"Unknown metric '{name}'."
                )

            return metrics.iloc[0][name]

        drive_metrics = self.metrics()
        aggregate = calculate_aggregate_metrics(drive_metrics)

        if name not in aggregate:
            raise UnknownMetricError(
                f"Unknown metric '{name}'."
            )

        return aggregate[name]

    def aggregate_metrics(
        self,
    ) -> dict[str, float | int]:
        """Return aggregate metrics from persisted drive metrics."""
        return calculate_aggregate_metrics(
            self.metrics()
        )

    def events(
        self,
        *,
        drive_id: str | None = None,
        event_type: str | None = None,
        min_severity_score: float | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Return detected driving events using common filters."""
        data = get_events(
            event_type=event_type,
            drive_id=drive_id,
            min_severity_score=min_severity_score,
            limit=limit,
            database_path=self.database_path,
        )

        if (
            drive_id is not None
            and data.empty
            and not self._drive_exists(drive_id)
        ):
            raise DriveNotFoundError(
                f"No telemetry found for drive '{drive_id}'."
            )

        return data

    def summary(
        self,
        drive_id: str,
    ) -> dict[str, object]:
        """Return telemetry and metric summary data for one drive."""
        drive_summary = self.drive(drive_id).to_dict()
        metric_rows = self.metrics(drive_id)

        summary: dict[str, object] = dict(drive_summary)

        if not metric_rows.empty:
            metric_row = metric_rows.iloc[0]

            for column in DRIVE_METRIC_COLUMNS:
                if (
                    column in metric_rows.columns
                    and column
                    not in {
                        "drive_id",
                        "source_file",
                        "start_time",
                        "end_time",
                    }
                ):
                    summary[column] = metric_row[column]

        return summary

    def export(
        self,
        data: pd.DataFrame,
        path: str | Path,
    ) -> Path:
        """Export a derived dataset to CSV or Parquet."""
        if not isinstance(data, pd.DataFrame):
            raise TypeError(
                "data must be a pandas DataFrame."
            )

        output = Path(path)
        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        suffix = output.suffix.lower()

        if suffix == ".csv":
            data.to_csv(
                output,
                index=False,
            )

        elif suffix in {".parquet", ".pq"}:
            try:
                data.to_parquet(
                    output,
                    index=False,
                )

            except ImportError as exc:
                raise ImportError(
                    "Parquet export requires pyarrow or "
                    "fastparquet. Use CSV or install a "
                    "Parquet engine."
                ) from exc

        else:
            raise UnsupportedExportFormatError(
                "Unsupported export format. "
                "Use .csv, .parquet, or .pq."
            )

        return output

    def export_events(
        self,
        path: str | Path,
        *,
        drive_id: str | None = None,
        event_type: str | None = None,
        min_severity_score: float | None = None,
        limit: int = 1000,
    ) -> Path:
        """Query and export an event dataset."""
        return self.export(
            self.events(
                drive_id=drive_id,
                event_type=event_type,
                min_severity_score=min_severity_score,
                limit=limit,
            ),
            path,
        )

    def _drive_exists(
        self,
        drive_id: str,
    ) -> bool:
        result = query_telemetry(
            f"""
            SELECT 1
            FROM {TELEMETRY_TABLE}
            WHERE drive_id = ?
            LIMIT 1
            """,
            params=[drive_id],
            database_path=self.database_path,
        )

        return not result.empty

    @staticmethod
    def _sql_timestamp(
        value: str | pd.Timestamp,
    ) -> str:
        timestamp = pd.Timestamp(value)

        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")

        return timestamp.isoformat()


__all__ = [
    "DriveNotFoundError",
    "FleetDataSDK",
    "FleetDataSDKError",
    "InvalidTelemetryColumnError",
    "UnknownMetricError",
    "UnsupportedExportFormatError",
]
