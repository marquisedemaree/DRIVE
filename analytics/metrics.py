"""Self-Driving performance and driving-event metrics for DRIVE Analytics Mode."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import sqlite3

import numpy as np
import pandas as pd

from config import (
    DATABASE_PATH,
    DRIVE_METRICS_TABLE,
    EVENTS_TABLE,
    EVENT_COOLDOWN_SECONDS,
    HARD_BRAKING_THRESHOLD_MPS2,
    HIGH_LATERAL_ACCEL_THRESHOLD_MPS2,
    MIN_EVENT_DURATION_SECONDS,
    RAPID_ACCELERATION_THRESHOLD_MPS2,
    SHARP_STEERING_RATE_THRESHOLD_DEG_S,
    SQL_CHUNK_SIZE,
    TELEMETRY_TABLE,
)


EVENT_COLUMNS = [
    "event_id",
    "drive_id",
    "source_file",
    "event_type",
    "start_time",
    "end_time",
    "duration_s",
    "severity_score",
    "severity",
    "peak_value",
    "start_speed_kph",
    "end_speed_kph",
    "distance_km",
    "autopilot_active",
    "road_class",
    "rainy",
    "snowy",
]


DRIVE_METRIC_COLUMNS = [
    "drive_id",
    "source_file",
    "start_time",
    "end_time",
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
]


AUTOPILOT_ACTIVE_STATES = {
    "ACTIVE_NOMINAL",
    "ACTIVE_RESTRICTED",
}


def _get_connection(
    database_path: Path = DATABASE_PATH,
) -> sqlite3.Connection:
    """Open the metrics SQLite database."""
    database_path = Path(database_path)

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        database_path
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def _query_sql(
    sql: str,
    params: list[object] | tuple[object, ...] | None = None,
    database_path: Path = DATABASE_PATH,
) -> pd.DataFrame:
    """Execute a read-only metrics query."""
    statement = sql.strip()

    if not statement.lower().startswith(
        (
            "select",
            "with",
        )
    ):
        raise ValueError(
            "Metrics SQL queries must be read-only "
            "SELECT or WITH statements."
        )

    with _get_connection(
        database_path
    ) as connection:
        return pd.read_sql_query(
            statement,
            connection,
            params=tuple(
                params or ()
            ),
        )


@dataclass(frozen=True)
class MetricsResult:
    """Detected events and performance metrics produced by one metrics run."""

    events: pd.DataFrame
    drive_metrics: pd.DataFrame
    aggregate_metrics: dict[str, float | int]


def _empty_events() -> pd.DataFrame:
    """Return an empty standardized event table."""
    return pd.DataFrame(
        columns=EVENT_COLUMNS
    )


def _empty_drive_metrics() -> pd.DataFrame:
    """Return an empty standardized drive-metric table."""
    return pd.DataFrame(
        columns=DRIVE_METRIC_COLUMNS
    )


def _prepare_telemetry(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Validate and normalize canonical telemetry fields used by metrics."""
    required = {
        "drive_id",
        "timestamp",
        "speed_kph",
        "distance_delta_km",
        "longitudinal_accel_mps2",
        "lateral_accel_mps2",
        "steering_rate_deg_s",
        "autopilot_state",
    }

    missing = sorted(
        required
        - set(
            data.columns
        )
    )

    if missing:
        raise ValueError(
            "Metrics require canonical telemetry columns: "
            + ", ".join(
                missing
            )
        )

    frame = data.copy()

    frame[
        "timestamp"
    ] = pd.to_datetime(
        frame[
            "timestamp"
        ],
        utc=True,
        errors="coerce",
    )

    numeric = [
        "speed_kph",
        "distance_delta_km",
        "longitudinal_accel_mps2",
        "lateral_accel_mps2",
        "steering_rate_deg_s",
    ]

    for column in numeric:
        frame[
            column
        ] = pd.to_numeric(
            frame[
                column
            ],
            errors="coerce",
        )

    frame = frame.dropna(
        subset=[
            "drive_id",
            "timestamp",
        ]
    )

    return (
        frame.sort_values(
            [
                "drive_id",
                "timestamp",
            ]
        )
        .reset_index(
            drop=True
        )
    )


def _autopilot_active(
    series: pd.Series,
) -> pd.Series:
    """Return a Boolean mask for actively engaged Autopilot states."""
    states = (
        series
        .astype(
            "string"
        )
        .str.upper()
    )

    return states.isin(
        AUTOPILOT_ACTIVE_STATES
    )


def _severity_label(
    score: float,
) -> str:
    """Map normalized event severity to a label."""
    if score >= 0.67:
        return "high"

    if score >= 0.34:
        return "moderate"

    return "low"


def _normalized_severity(
    peak: float,
    threshold: float,
    severe_reference: float,
) -> float:
    """Map event magnitude from threshold crossing to bounded severity."""
    magnitude = abs(
        float(
            peak
        )
    )

    threshold = abs(
        float(
            threshold
        )
    )

    severe_reference = max(
        abs(
            float(
                severe_reference
            )
        ),
        threshold + 1e-9,
    )

    score = (
        magnitude
        - threshold
    ) / (
        severe_reference
        - threshold
    )

    return float(
        np.clip(
            score,
            0.0,
            1.0,
        )
    )


def _event_groups(
    drive: pd.DataFrame,
    mask: pd.Series,
    min_duration_s: float,
    cooldown_s: float,
) -> list[pd.DataFrame]:
    """Group threshold-crossing samples into discrete events."""
    candidates = (
        drive.loc[
            mask.fillna(
                False
            )
        ]
        .copy()
    )

    if candidates.empty:
        return []

    gaps = (
        candidates[
            "timestamp"
        ]
        .diff()
        .dt
        .total_seconds()
    )

    group_ids = (
        gaps
        .gt(
            cooldown_s
        )
        .fillna(
            True
        )
        .cumsum()
    )

    groups: list[pd.DataFrame] = []

    for (
        _,
        group,
    ) in candidates.groupby(
        group_ids,
        sort=False,
    ):
        start = (
            group[
                "timestamp"
            ]
            .iloc[0]
        )

        end = (
            group[
                "timestamp"
            ]
            .iloc[-1]
        )

        duration = max(
            float(
                (
                    end
                    - start
                )
                .total_seconds()
            ),
            0.0,
        )

        if len(group) == 1:
            sample_interval = (
                drive[
                    "timestamp"
                ]
                .diff()
                .dt
                .total_seconds()
                .median()
            )

            if (
                pd.notna(
                    sample_interval
                )
                and sample_interval > 0
            ):
                duration = float(
                    sample_interval
                )

        if duration >= min_duration_s:
            groups.append(
                group
            )

    return groups


def _safe_float(
    value,
) -> float | None:
    """Convert a non-missing value to float."""
    return (
        None
        if pd.isna(
            value
        )
        else float(
            value
        )
    )


def _build_event(
    group: pd.DataFrame,
    event_type: str,
    value_column: str,
    threshold: float,
    severe_reference: float,
    peak_mode: str,
    ordinal: int,
) -> dict:
    """Build one standardized event record."""
    if peak_mode == "min":
        peak = float(
            group[
                value_column
            ].min()
        )

    elif peak_mode == "max_abs":
        values = (
            group[
                value_column
            ]
            .dropna()
        )

        peak = (
            float(
                values.loc[
                    values
                    .abs()
                    .idxmax()
                ]
            )
            if not values.empty
            else 0.0
        )

    else:
        peak = float(
            group[
                value_column
            ].max()
        )

    start = (
        group[
            "timestamp"
        ]
        .iloc[0]
    )

    end = (
        group[
            "timestamp"
        ]
        .iloc[-1]
    )

    duration = max(
        float(
            (
                end
                - start
            )
            .total_seconds()
        ),
        0.0,
    )

    score = (
        _normalized_severity(
            peak,
            threshold,
            severe_reference,
        )
    )

    autopilot = (
        _autopilot_active(
            group[
                "autopilot_state"
            ]
        )
    )

    source_file = (
        group[
            "source_file"
        ].iloc[0]
        if "source_file"
        in group.columns
        else None
    )

    distance = (
        pd.to_numeric(
            group[
                "distance_delta_km"
            ],
            errors="coerce",
        )
        .sum(
            min_count=1
        )
    )

    def first_optional(
        name: str,
    ):
        return (
            group[
                name
            ].iloc[0]
            if name
            in group.columns
            else None
        )

    return {
        "event_id": (
            f"{group['drive_id'].iloc[0]}:"
            f"{event_type}:"
            f"{ordinal:05d}"
        ),

        "drive_id":
            group[
                "drive_id"
            ].iloc[0],

        "source_file":
            source_file,

        "event_type":
            event_type,

        "start_time":
            start,

        "end_time":
            end,

        "duration_s":
            round(
                duration,
                3,
            ),

        "severity_score":
            round(
                score,
                4,
            ),

        "severity":
            _severity_label(
                score
            ),

        "peak_value":
            round(
                peak,
                4,
            ),

        "start_speed_kph":
            _safe_float(
                group[
                    "speed_kph"
                ].iloc[0]
            ),

        "end_speed_kph":
            _safe_float(
                group[
                    "speed_kph"
                ].iloc[-1]
            ),

        "distance_km": (
            round(
                float(
                    distance
                ),
                6,
            )
            if pd.notna(
                distance
            )
            else 0.0
        ),

        "autopilot_active":
            bool(
                autopilot.mean()
                >= 0.5
            ),

        "road_class":
            first_optional(
                "road_class"
            ),

        "rainy": (
            bool(
                first_optional(
                    "rainy"
                )
            )
            if "rainy"
            in group.columns
            else False
        ),

        "snowy": (
            bool(
                first_optional(
                    "snowy"
                )
            )
            if "snowy"
            in group.columns
            else False
        ),
    }


def _detect_threshold_events(
    data: pd.DataFrame,
    *,
    event_type: str,
    value_column: str,
    predicate: Callable[
        [
            pd.Series
        ],
        pd.Series,
    ],
    threshold: float,
    severe_reference: float,
    peak_mode: str,
) -> pd.DataFrame:
    """Detect one configured event type."""
    frame = (
        _prepare_telemetry(
            data
        )
    )

    events = []
    ordinal = 1

    for (
        _,
        drive,
    ) in frame.groupby(
        "drive_id",
        sort=False,
    ):
        mask = predicate(
            drive[
                value_column
            ]
        )

        for group in _event_groups(
            drive,
            mask,
            MIN_EVENT_DURATION_SECONDS,
            EVENT_COOLDOWN_SECONDS,
        ):
            events.append(
                _build_event(
                    group,
                    event_type,
                    value_column,
                    threshold,
                    severe_reference,
                    peak_mode,
                    ordinal,
                )
            )

            ordinal += 1

    if not events:
        return _empty_events()

    return pd.DataFrame(
        events,
        columns=EVENT_COLUMNS,
    )


def detect_hard_braking(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Detect sustained high-deceleration events."""
    return _detect_threshold_events(
        data,

        event_type=
            "hard_braking",

        value_column=
            "longitudinal_accel_mps2",

        predicate=lambda series:
            series
            <= HARD_BRAKING_THRESHOLD_MPS2,

        threshold=
            HARD_BRAKING_THRESHOLD_MPS2,

        severe_reference=
            -5.5,

        peak_mode=
            "min",
    )


def detect_rapid_acceleration(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Detect sustained high positive longitudinal acceleration."""
    return _detect_threshold_events(
        data,

        event_type=
            "rapid_acceleration",

        value_column=
            "longitudinal_accel_mps2",

        predicate=lambda series:
            series
            >= RAPID_ACCELERATION_THRESHOLD_MPS2,

        threshold=
            RAPID_ACCELERATION_THRESHOLD_MPS2,

        severe_reference=
            3.6,

        peak_mode=
            "max",
    )


def detect_sharp_steering(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Detect abrupt steering-rate events in either direction."""
    return _detect_threshold_events(
        data,

        event_type=
            "sharp_steering",

        value_column=
            "steering_rate_deg_s",

        predicate=lambda series:
            series.abs()
            >= SHARP_STEERING_RATE_THRESHOLD_DEG_S,

        threshold=
            SHARP_STEERING_RATE_THRESHOLD_DEG_S,

        severe_reference=
            500.0,

        peak_mode=
            "max_abs",
    )


def detect_high_lateral_acceleration(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Detect unusually high lateral-acceleration events."""
    return _detect_threshold_events(
        data,

        event_type=
            "high_lateral_accel",

        value_column=
            "lateral_accel_mps2",

        predicate=lambda series:
            series.abs()
            >= HIGH_LATERAL_ACCEL_THRESHOLD_MPS2,

        threshold=
            HIGH_LATERAL_ACCEL_THRESHOLD_MPS2,

        severe_reference=
            4.0,

        peak_mode=
            "max_abs",
    )


EVENT_DETECTORS: tuple[
    Callable[
        [
            pd.DataFrame
        ],
        pd.DataFrame,
    ],
    ...,
] = (
    detect_hard_braking,
    detect_rapid_acceleration,
    detect_sharp_steering,
    detect_high_lateral_acceleration,
)


def detect_events(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Run all configured event detectors."""
    if data.empty:
        return _empty_events()

    detected = [
        detector(
            data
        )
        for detector
        in EVENT_DETECTORS
    ]

    non_empty = [
        events
        for events
        in detected
        if not events.empty
    ]

    if not non_empty:
        return _empty_events()

    result = pd.concat(
        non_empty,
        ignore_index=True,
    )

    return (
        result.sort_values(
            [
                "drive_id",
                "start_time",
                "event_type",
            ]
        )
        .reset_index(
            drop=True
        )
    )


def _duration_weights(
    drive: pd.DataFrame,
) -> pd.Series:
    """Return seconds represented by each sample."""
    delta = (
        drive[
            "timestamp"
        ]
        .shift(-1)
        .sub(
            drive[
                "timestamp"
            ]
        )
        .dt
        .total_seconds()
    )

    median = (
        delta[
            (
                delta > 0
            )
            &
            (
                delta <= 5
            )
        ]
        .median()
    )

    fallback = (
        float(
            median
        )
        if pd.notna(
            median
        )
        else 0.0
    )

    return (
        delta
        .where(
            (
                delta > 0
            )
            &
            (
                delta <= 5
            ),
            fallback,
        )
        .fillna(
            fallback
        )
    )


def _rate_per_100_km(
    count: int,
    distance_km: float,
) -> float:
    """Calculate a distance-normalized event rate."""
    return (
        round(
            (
                count
                / distance_km
            )
            * 100.0,
            4,
        )
        if distance_km > 0
        else 0.0
    )


def calculate_drive_metrics(
    data: pd.DataFrame,
    events: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Calculate normalized performance metrics for each drive."""
    if data.empty:
        return (
            _empty_drive_metrics()
        )

    frame = (
        _prepare_telemetry(
            data
        )
    )

    if events is None:
        events = (
            detect_events(
                frame
            )
        )

    rows = []

    for (
        drive_id,
        drive,
    ) in frame.groupby(
        "drive_id",
        sort=False,
    ):
        start = (
            drive[
                "timestamp"
            ].min()
        )

        end = (
            drive[
                "timestamp"
            ].max()
        )

        duration_s = max(
            float(
                (
                    end
                    - start
                )
                .total_seconds()
            ),
            0.0,
        )

        distance_km = float(
            drive[
                "distance_delta_km"
            ]
            .clip(
                lower=0
            )
            .sum(
                skipna=True
            )
        )

        weights = (
            _duration_weights(
                drive
            )
        )

        ap_mask = (
            _autopilot_active(
                drive[
                    "autopilot_state"
                ]
            )
        )

        ap_time_s = float(
            weights.where(
                ap_mask,
                0.0,
            ).sum()
        )

        ap_distance_km = float(
            drive[
                "distance_delta_km"
            ]
            .clip(
                lower=0
            )
            .where(
                ap_mask,
                0.0,
            )
            .sum()
        )

        drive_events = (
            events.loc[
                events[
                    "drive_id"
                ]
                == drive_id
            ]
            if not events.empty
            else events
        )

        counts = (
            drive_events[
                "event_type"
            ]
            .value_counts()
            if not drive_events.empty
            else pd.Series(
                dtype=int
            )
        )

        hard = int(
            counts.get(
                "hard_braking",
                0,
            )
        )

        rapid = int(
            counts.get(
                "rapid_acceleration",
                0,
            )
        )

        steering = int(
            counts.get(
                "sharp_steering",
                0,
            )
        )

        lateral = int(
            counts.get(
                "high_lateral_accel",
                0,
            )
        )

        total = (
            hard
            + rapid
            + steering
            + lateral
        )

        average_speed = (
            pd.to_numeric(
                drive[
                    "speed_kph"
                ],
                errors="coerce",
            )
            .mean()
        )

        max_speed = (
            pd.to_numeric(
                drive[
                    "speed_kph"
                ],
                errors="coerce",
            )
            .max()
        )

        rows.append(
            {
                "drive_id":
                    drive_id,

                "source_file": (
                    drive[
                        "source_file"
                    ].iloc[0]
                    if "source_file"
                    in drive.columns
                    else None
                ),

                "start_time":
                    start,

                "end_time":
                    end,

                "duration_s":
                    round(
                        duration_s,
                        3,
                    ),

                "distance_km":
                    round(
                        distance_km,
                        6,
                    ),

                "average_speed_kph": (
                    round(
                        float(
                            average_speed
                        ),
                        3,
                    )
                    if pd.notna(
                        average_speed
                    )
                    else 0.0
                ),

                "max_speed_kph": (
                    round(
                        float(
                            max_speed
                        ),
                        3,
                    )
                    if pd.notna(
                        max_speed
                    )
                    else 0.0
                ),

                "autopilot_active_time_s":
                    round(
                        ap_time_s,
                        3,
                    ),

                "autopilot_active_distance_km":
                    round(
                        ap_distance_km,
                        6,
                    ),

                "autopilot_active_pct": (
                    round(
                        (
                            ap_time_s
                            / duration_s
                        )
                        * 100.0,
                        3,
                    )
                    if duration_s > 0
                    else 0.0
                ),

                "hard_braking_count":
                    hard,

                "hard_braking_per_100_km":
                    _rate_per_100_km(
                        hard,
                        distance_km,
                    ),

                "rapid_acceleration_count":
                    rapid,

                "rapid_acceleration_per_100_km":
                    _rate_per_100_km(
                        rapid,
                        distance_km,
                    ),

                "sharp_steering_count":
                    steering,

                "sharp_steering_per_100_km":
                    _rate_per_100_km(
                        steering,
                        distance_km,
                    ),

                "high_lateral_accel_count":
                    lateral,

                "high_lateral_accel_per_100_km":
                    _rate_per_100_km(
                        lateral,
                        distance_km,
                    ),

                "total_events":
                    total,

                "events_per_100_km":
                    _rate_per_100_km(
                        total,
                        distance_km,
                    ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=DRIVE_METRIC_COLUMNS,
    )


def calculate_aggregate_metrics(
    drive_metrics: pd.DataFrame,
) -> dict[str, float | int]:
    """Aggregate drive-level metrics without averaging normalized rates."""
    if drive_metrics.empty:
        return {
            "drives": 0,
            "distance_km": 0.0,
            "duration_s": 0.0,
            "average_speed_kph":
                0.0,
            "max_speed_kph":
                0.0,
            "autopilot_active_distance_km":
                0.0,
            "autopilot_active_time_s":
                0.0,
            "autopilot_active_pct":
                0.0,
            "hard_braking_count":
                0,
            "hard_braking_per_100_km":
                0.0,
            "rapid_acceleration_count":
                0,
            "rapid_acceleration_per_100_km":
                0.0,
            "sharp_steering_count":
                0,
            "sharp_steering_per_100_km":
                0.0,
            "high_lateral_accel_count":
                0,
            "high_lateral_accel_per_100_km":
                0.0,
            "total_events":
                0,
            "events_per_100_km":
                0.0,
        }

    distance = float(
        pd.to_numeric(
            drive_metrics[
                "distance_km"
            ],
            errors="coerce",
        )
        .fillna(
            0.0
        )
        .sum()
    )

    durations = (
        pd.to_numeric(
            drive_metrics[
                "duration_s"
            ],
            errors="coerce",
        )
        .fillna(
            0.0
        )
        .clip(
            lower=0.0
        )
    )

    duration = float(
        durations.sum()
    )

    average_speeds = (
        pd.to_numeric(
            drive_metrics[
                "average_speed_kph"
            ],
            errors="coerce",
        )
        .fillna(
            0.0
        )
    )

    if duration > 0:
        average_speed = float(
            (
                average_speeds
                * durations
            ).sum()
            / duration
        )

    else:
        average_speed = float(
            average_speeds.mean()
        )

    max_speeds = (
        pd.to_numeric(
            drive_metrics[
                "max_speed_kph"
            ],
            errors="coerce",
        )
    )

    max_speed = (
        float(
            max_speeds.max()
        )
        if max_speeds
        .notna()
        .any()
        else 0.0
    )

    ap_distance = float(
        pd.to_numeric(
            drive_metrics[
                "autopilot_active_distance_km"
            ],
            errors="coerce",
        )
        .fillna(
            0.0
        )
        .sum()
    )

    ap_time = float(
        pd.to_numeric(
            drive_metrics[
                "autopilot_active_time_s"
            ],
            errors="coerce",
        )
        .fillna(
            0.0
        )
        .sum()
    )

    counts = {
        "hard_braking":
            int(
                pd.to_numeric(
                    drive_metrics[
                        "hard_braking_count"
                    ],
                    errors="coerce",
                )
                .fillna(
                    0
                )
                .sum()
            ),

        "rapid_acceleration":
            int(
                pd.to_numeric(
                    drive_metrics[
                        "rapid_acceleration_count"
                    ],
                    errors="coerce",
                )
                .fillna(
                    0
                )
                .sum()
            ),

        "sharp_steering":
            int(
                pd.to_numeric(
                    drive_metrics[
                        "sharp_steering_count"
                    ],
                    errors="coerce",
                )
                .fillna(
                    0
                )
                .sum()
            ),

        "high_lateral_accel":
            int(
                pd.to_numeric(
                    drive_metrics[
                        "high_lateral_accel_count"
                    ],
                    errors="coerce",
                )
                .fillna(
                    0
                )
                .sum()
            ),
    }

    total = sum(
        counts.values()
    )

    return {
        "drives":
            int(
                drive_metrics[
                    "drive_id"
                ]
                .nunique()
            ),

        "distance_km":
            round(
                distance,
                6,
            ),

        "duration_s":
            round(
                duration,
                3,
            ),

        "average_speed_kph":
            round(
                average_speed,
                3,
            ),

        "max_speed_kph":
            round(
                max_speed,
                3,
            ),

        "autopilot_active_distance_km":
            round(
                ap_distance,
                6,
            ),

        "autopilot_active_time_s":
            round(
                ap_time,
                3,
            ),

        "autopilot_active_pct": (
            round(
                (
                    ap_time
                    / duration
                )
                * 100.0,
                3,
            )
            if duration > 0
            else 0.0
        ),

        "hard_braking_count":
            counts[
                "hard_braking"
            ],

        "hard_braking_per_100_km":
            _rate_per_100_km(
                counts[
                    "hard_braking"
                ],
                distance,
            ),

        "rapid_acceleration_count":
            counts[
                "rapid_acceleration"
            ],

        "rapid_acceleration_per_100_km":
            _rate_per_100_km(
                counts[
                    "rapid_acceleration"
                ],
                distance,
            ),

        "sharp_steering_count":
            counts[
                "sharp_steering"
            ],

        "sharp_steering_per_100_km":
            _rate_per_100_km(
                counts[
                    "sharp_steering"
                ],
                distance,
            ),

        "high_lateral_accel_count":
            counts[
                "high_lateral_accel"
            ],

        "high_lateral_accel_per_100_km":
            _rate_per_100_km(
                counts[
                    "high_lateral_accel"
                ],
                distance,
            ),

        "total_events":
            total,

        "events_per_100_km":
            _rate_per_100_km(
                total,
                distance,
            ),
    }


def persist_metrics(
    result: MetricsResult,
    database_path: Path = DATABASE_PATH,
) -> tuple[int, int]:
    """Replace SQL event and drive-metric serving tables."""
    events = (
        result.events.copy()
    )

    drive_metrics = (
        result
        .drive_metrics
        .copy()
    )

    for (
        frame,
        columns,
    ) in (
        (
            events,
            [
                "start_time",
                "end_time",
            ],
        ),
        (
            drive_metrics,
            [
                "start_time",
                "end_time",
            ],
        ),
    ):
        for column in columns:
            if column in frame.columns:
                frame[
                    column
                ] = (
                    frame[
                        column
                    ]
                    .astype(
                        "string"
                    )
                )

    with _get_connection(
        database_path
    ) as connection:

        events.to_sql(
            EVENTS_TABLE,
            connection,
            if_exists=
                "replace",
            index=False,
            chunksize=
                SQL_CHUNK_SIZE,
        )

        drive_metrics.to_sql(
            DRIVE_METRICS_TABLE,
            connection,
            if_exists=
                "replace",
            index=False,
            chunksize=
                SQL_CHUNK_SIZE,
        )

        connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS
            idx_{EVENTS_TABLE}_drive
            ON {EVENTS_TABLE}(drive_id)
            """
        )

        connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS
            idx_{EVENTS_TABLE}_type
            ON {EVENTS_TABLE}(event_type)
            """
        )

        connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS
            idx_{EVENTS_TABLE}_start
            ON {EVENTS_TABLE}(start_time)
            """
        )

        connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS
            idx_{DRIVE_METRICS_TABLE}_drive
            ON {DRIVE_METRICS_TABLE}(drive_id)
            """
        )

    return (
        len(
            events
        ),
        len(
            drive_metrics
        ),
    )


def get_events(
    event_type: str | None = None,
    drive_id: str | None = None,
    min_severity_score: float | None = None,
    limit: int = 1000,
    database_path: Path = DATABASE_PATH,
) -> pd.DataFrame:
    """Retrieve filtered detected events from SQLite."""
    if limit <= 0:
        raise ValueError(
            "limit must be greater than zero."
        )

    conditions: list[str] = []
    params: list[object] = []

    if event_type is not None:
        conditions.append(
            "event_type = ?"
        )

        params.append(
            event_type
        )

    if drive_id is not None:
        conditions.append(
            "drive_id = ?"
        )

        params.append(
            drive_id
        )

    if min_severity_score is not None:
        conditions.append(
            "severity_score >= ?"
        )

        params.append(
            min_severity_score
        )

    where = (
        "WHERE "
        + " AND ".join(
            conditions
        )
        if conditions
        else ""
    )

    params.append(
        limit
    )

    return _query_sql(
        f"""
        SELECT *
        FROM {EVENTS_TABLE}
        {where}
        ORDER BY start_time
        LIMIT ?
        """,

        params=
            params,

        database_path=
            database_path,
    )


def get_drive_metrics(
    drive_id: str | None = None,
    database_path: Path = DATABASE_PATH,
) -> pd.DataFrame:
    """Retrieve persisted drive metrics from SQLite."""
    if drive_id is None:
        sql = f"""
            SELECT *
            FROM {DRIVE_METRICS_TABLE}
            ORDER BY start_time
        """

        params = None

    else:
        sql = f"""
            SELECT *
            FROM {DRIVE_METRICS_TABLE}
            WHERE drive_id = ?
            ORDER BY start_time
        """

        params = [
            drive_id
        ]

    return _query_sql(
        sql,

        params=
            params,

        database_path=
            database_path,
    )


def load_telemetry_from_sql(
    database_path: Path = DATABASE_PATH,
) -> pd.DataFrame:
    """Load canonical telemetry from SQLite for metric calculation."""
    return _query_sql(
        f"""
        SELECT *
        FROM {TELEMETRY_TABLE}
        ORDER BY
            drive_id,
            timestamp
        """,

        database_path=
            database_path,
    )


def run_metrics_pipeline(
    data: pd.DataFrame | None = None,
    *,
    database_path: Path = DATABASE_PATH,
    persist: bool = True,
) -> MetricsResult:
    """Run event detection, metric calculation, and optional persistence."""
    telemetry = (
        load_telemetry_from_sql(
            database_path
        )
        if data is None
        else data
    )

    if telemetry.empty:
        result = MetricsResult(
            events=
                _empty_events(),

            drive_metrics=
                _empty_drive_metrics(),

            aggregate_metrics=
                calculate_aggregate_metrics(
                    _empty_drive_metrics()
                ),
        )

        if persist:
            persist_metrics(
                result,
                database_path=
                    database_path,
            )

        return result

    events = (
        detect_events(
            telemetry
        )
    )

    drive_metrics = (
        calculate_drive_metrics(
            telemetry,
            events,
        )
    )

    aggregate_metrics = (
        calculate_aggregate_metrics(
            drive_metrics
        )
    )

    result = MetricsResult(
        events=
            events,

        drive_metrics=
            drive_metrics,

        aggregate_metrics=
            aggregate_metrics,
    )

    if persist:
        persist_metrics(
            result,
            database_path=
                database_path,
        )

    return result


__all__ = [
    "AUTOPILOT_ACTIVE_STATES",
    "DRIVE_METRIC_COLUMNS",
    "EVENT_COLUMNS",
    "EVENT_DETECTORS",
    "MetricsResult",
    "calculate_aggregate_metrics",
    "calculate_drive_metrics",
    "detect_events",
    "detect_hard_braking",
    "detect_high_lateral_acceleration",
    "detect_rapid_acceleration",
    "detect_sharp_steering",
    "get_drive_metrics",
    "get_events",
    "load_telemetry_from_sql",
    "persist_metrics",
    "run_metrics_pipeline",
]
