import {
  useEffect,
  useState,
} from "react";


function formatNumber(
  value,
  digits = 2
) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  return Number(
    value
  ).toLocaleString(
    undefined,
    {
      maximumFractionDigits:
        digits,
    }
  );
}


function humanize(value) {
  return String(
    value ?? ""
  )
    .replaceAll(
      "_",
      " "
    )
    .replace(
      /\b\w/g,
      (letter) =>
        letter.toUpperCase()
    );
}


function InsightList({
  insights = [],
}) {
  if (
    insights.length === 0
  ) {
    return (
      <p className="empty-state">
        No notable findings for
        this analysis.
      </p>
    );
  }

  return (
    <div className="insight-list">
      {insights.map(
        (
          insight,
          index
        ) => (
          <article
            className={
              `insight-card ` +
              `severity-${
                insight.severity ??
                "info"
              }`
            }
            key={
              `${insight.name}-` +
              `${index}`
            }
          >
            <div className="insight-header">
              <h3>
                {humanize(
                  insight.name
                )}
              </h3>

              <span className="severity-badge">
                {
                  insight.severity ??
                  "info"
                }
              </span>
            </div>

            <p>
              {
                insight.summary
              }
            </p>
          </article>
        )
      )}
    </div>
  );
}


function MetricCards({
  report,
}) {
  const metrics =
    report?.summary
      ?.aggregate_metrics ??
    report?.summary
      ?.metrics ??
    {};

  const events =
    report?.summary
      ?.events ??
    {};

  const cards = [
    [
      "Distance",
      `${formatNumber(
        metrics.distance_km
      )} km`,
    ],
    [
      "Average Speed",
      `${formatNumber(
        metrics.average_speed_kph
      )} kph`,
    ],
    [
      "Max Speed",
      `${formatNumber(
        metrics.max_speed_kph
      )} kph`,
    ],
    [
      "Autopilot Active",
      `${formatNumber(
        metrics.autopilot_active_pct
      )}%`,
    ],
    [
      "Detected Events",
      formatNumber(
        events.total_events ??
          metrics.total_events,
        0
      ),
    ],
    [
      "Events / 100 km",
      formatNumber(
        metrics
          .total_events_per_100_km ??
          metrics
            .events_per_100_km
      ),
    ],
  ];

  return (
    <div className="analysis-metric-grid">
      {cards.map(
        ([
          label,
          value,
        ]) => (
          <article
            className="analysis-metric-card"
            key={label}
          >
            <span>
              {label}
            </span>

            <strong>
              {value}
            </strong>
          </article>
        )
      )}
    </div>
  );
}


export default function AnalyticsDashboard({
  dashboard,
}) {
  const [
    selectedDrive,
    setSelectedDrive,
  ] = useState("");

  const [
    compareDrive,
    setCompareDrive,
  ] = useState("");

  const [
    analysis,
    setAnalysis,
  ] = useState(null);

  const [
    analysisError,
    setAnalysisError,
  ] = useState("");

  const [
    loadingAnalysis,
    setLoadingAnalysis,
  ] = useState(false);

  const drives =
    dashboard?.drives ??
    [];

  useEffect(
    () => {
      if (
        drives.length > 0 &&
        !selectedDrive
      ) {
        setSelectedDrive(
          drives[0]
        );
      }
    },
    [
      drives,
      selectedDrive,
    ]
  );

  useEffect(
    () => {
      if (
        compareDrive &&
        compareDrive === selectedDrive
      ) {
        setCompareDrive("");
      }
    },
    [
      selectedDrive,
      compareDrive,
    ]
  );

  if (!dashboard) {
    return (
      <p>
        Loading analytics
        dashboard...
      </p>
    );
  }

  const pipeline =
    dashboard.pipeline ??
    {};

  const sample =
    dashboard.telemetry_sample ??
    [];

  const fleetAnalysis =
    dashboard.fleet_analysis;


  async function loadDriveAnalysis() {
    if (!selectedDrive) {
      return;
    }

    setLoadingAnalysis(
      true
    );

    setAnalysisError("");

    try {
      const params =
        new URLSearchParams({
          drive_id:
            selectedDrive,
        });

      if (compareDrive) {
        params.set(
          "compare_to",
          compareDrive
        );
      }

      const response =
        await fetch(
          `/api/analysis?${params.toString()}`
        );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ??
          "Unable to generate analysis."
        );
      }

      setAnalysis(data);

    } catch (error) {
      setAnalysisError(
        error instanceof Error
          ? error.message
          : "Unable to generate analysis."
      );

    } finally {
      setLoadingAnalysis(
        false
      );
    }
  }


  return (
    <>
      <div className="dashboard-heading">
        <p className="eyebrow">
          Analytics Mode
        </p>

        <h2>
          {dashboard.title}
        </h2>

        <p>
          {dashboard.status}
        </p>
      </div>

      <div className="card-grid">
        <article className="dashboard-card">
          <h3>
            Source Files
          </h3>

          <p>
            {
              pipeline
                .files_processed ??
              0
            }{" "}
            CSV files processed
          </p>
        </article>

        <article className="dashboard-card">
          <h3>
            Telemetry Rows
          </h3>

          <p>
            {(
              pipeline
                .rows_served ??
              0
            ).toLocaleString()}{" "}
            analysis-ready samples
          </p>
        </article>

        <article className="dashboard-card">
          <h3>
            Drive Coverage
          </h3>

          <p>
            {
              pipeline.drives ??
              0
            }{" "}
            drives ·{" "}
            {
              pipeline
                .duration_minutes ??
              0
            }{" "}
            minutes
          </p>
        </article>

        <article className="dashboard-card">
          <h3>
            Distance
          </h3>

          <p>
            {
              pipeline
                .distance_km ??
              0
            }{" "}
            km represented
          </p>
        </article>

        <article className="dashboard-card">
          <h3>
            Speed
          </h3>

          <p>
            Avg{" "}
            {
              pipeline
                .average_speed_kph ??
              0
            }{" "}
            kph · Max{" "}
            {
              pipeline
                .max_speed_kph ??
              0
            }{" "}
            kph
          </p>
        </article>

        <article className="dashboard-card">
          <h3>
            Data Quality
          </h3>

          <p>
            {
              pipeline
                .rows_dropped ??
              0
            }{" "}
            invalid rows dropped ·{" "}
            {
              pipeline
                .duplicate_rows_removed ??
              0
            }{" "}
            duplicates removed
          </p>
        </article>
      </div>

      {fleetAnalysis && (
        <section className="analysis-section">
          <div className="dashboard-heading">
            <p className="eyebrow">
              Automated Workflow
            </p>

            <h2>
              Fleet Insights
            </h2>

            <p>
              Metrics, events,
              trends, and notable
              behaviors generated
              automatically from the
              current analytical
              dataset.
            </p>
          </div>

          <MetricCards
            report={
              fleetAnalysis
            }
          />

          <InsightList
            insights={
              fleetAnalysis
                .insights ??
              []
            }
          />

          {(
            fleetAnalysis
              .summary?.trends ??
            []
          ).length > 0 && (
            <div className="table-scroll analysis-table">
              <table className="telemetry-table">
                <thead>
                  <tr>
                    <th>
                      Metric
                    </th>

                    <th>
                      First
                    </th>

                    <th>
                      Last
                    </th>

                    <th>
                      Change
                    </th>

                    <th>
                      Direction
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {
                    fleetAnalysis
                      .summary
                      .trends
                      .map(
                        (
                          trend
                        ) => (
                          <tr
                            key={
                              trend.metric
                            }
                          >
                            <td>
                              {
                                humanize(
                                  trend.metric
                                )
                              }
                            </td>

                            <td>
                              {
                                formatNumber(
                                  trend
                                    .first_value
                                )
                              }
                            </td>

                            <td>
                              {
                                formatNumber(
                                  trend
                                    .last_value
                                )
                              }
                            </td>

                            <td>
                              {
                                trend
                                  .change_pct ===
                                null
                                  ? "—"
                                  : `${formatNumber(
                                      trend
                                        .change_pct
                                    )}%`
                              }
                            </td>

                            <td>
                              {
                                humanize(
                                  trend
                                    .direction
                                )
                              }
                            </td>
                          </tr>
                        )
                      )
                  }
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {drives.length > 0 && (
        <section className="analysis-section">
          <div className="dashboard-heading">
            <p className="eyebrow">
              Interactive Analysis
            </p>

            <h2>
              Drive Drill-Down
            </h2>

            <p>
              Generate a standardized
              analysis for one drive
              or compare two drives
              using the reusable
              insights workflow.
            </p>
          </div>

          <div className="analysis-controls">
            <label>
              <span>
                Primary Drive
              </span>

              <select
                value={
                  selectedDrive
                }
                onChange={(
                  event
                ) => {
                  setSelectedDrive(
                    event.target
                      .value
                  );

                  setAnalysis(
                    null
                  );

                  setAnalysisError(
                    ""
                  );
                }}
              >
                {drives.map(
                  (
                    drive
                  ) => (
                    <option
                      value={
                        drive
                      }
                      key={
                        drive
                      }
                    >
                      {drive}
                    </option>
                  )
                )}
              </select>
            </label>

            <label>
              <span>
                Compare To
              </span>

              <select
                value={
                  compareDrive
                }
                onChange={(
                  event
                ) => {
                  setCompareDrive(
                    event.target
                      .value
                  );

                  setAnalysis(
                    null
                  );

                  setAnalysisError(
                    ""
                  );
                }}
              >
                <option value="">
                  No comparison
                </option>

                {drives
                  .filter(
                    (
                      drive
                    ) =>
                      drive !==
                      selectedDrive
                  )
                  .map(
                    (
                      drive
                    ) => (
                      <option
                        value={
                          drive
                        }
                        key={
                          drive
                        }
                      >
                        {drive}
                      </option>
                    )
                  )}
              </select>
            </label>

            <button
              className="analysis-button"
              type="button"
              onClick={
                loadDriveAnalysis
              }
              disabled={
                loadingAnalysis ||
                !selectedDrive
              }
            >
              {
                loadingAnalysis
                  ? "Analyzing..."
                  : "Run Analysis"
              }
            </button>
          </div>

          {analysisError && (
            <p className="error-message">
              {analysisError}
            </p>
          )}

          {analysis && (
            <div className="analysis-result">
              <h3>
                {
                  analysis.title
                }
              </h3>

              {
                analysis.scope ===
                "comparison"
                  ? (
                    <div className="table-scroll analysis-table">
                      <table className="telemetry-table">
                        <thead>
                          <tr>
                            <th>
                              Metric
                            </th>

                            <th>
                              {
                                analysis
                                  .summary
                                  .left_drive_id
                              }
                            </th>

                            <th>
                              {
                                analysis
                                  .summary
                                  .right_drive_id
                              }
                            </th>

                            <th>
                              Difference
                            </th>

                            <th>
                              % Change
                            </th>
                          </tr>
                        </thead>

                        <tbody>
                          {(
                            analysis
                              .summary
                              .metrics ??
                            []
                          ).map(
                            (
                              row
                            ) => (
                              <tr
                                key={
                                  row.metric
                                }
                              >
                                <td>
                                  {
                                    humanize(
                                      row.metric
                                    )
                                  }
                                </td>

                                <td>
                                  {
                                    formatNumber(
                                      row
                                        .left_value
                                    )
                                  }
                                </td>

                                <td>
                                  {
                                    formatNumber(
                                      row
                                        .right_value
                                    )
                                  }
                                </td>

                                <td>
                                  {
                                    formatNumber(
                                      row
                                        .difference
                                    )
                                  }
                                </td>

                                <td>
                                  {
                                    row
                                      .pct_difference ===
                                    null
                                      ? "—"
                                      : `${formatNumber(
                                          row
                                            .pct_difference
                                        )}%`
                                  }
                                </td>
                              </tr>
                            )
                          )}
                        </tbody>
                      </table>
                    </div>
                  )
                  : (
                    <MetricCards
                      report={
                        analysis
                      }
                    />
                  )
              }

              <InsightList
                insights={
                  analysis
                    .insights ??
                  []
                }
              />
            </div>
          )}
        </section>
      )}

      <section className="telemetry-preview">
        <div className="dashboard-heading">
          <p className="eyebrow">
            Served Dataset
          </p>

          <h2>
            Telemetry Preview
          </h2>

          <p>
            Canonical fields produced
            by the shared telemetry
            pipeline.
          </p>
        </div>

        {sample.length === 0
          ? (
            <p>
              No CSV files were found
              in the configured Tesla
              Model 3 data folder.
            </p>
          )
          : (
            <div className="table-scroll">
              <table className="telemetry-table">
                <thead>
                  <tr>
                    <th>
                      Timestamp
                    </th>

                    <th>
                      Drive
                    </th>

                    <th>
                      Speed
                    </th>

                    <th>
                      Long. Accel
                    </th>

                    <th>
                      Steering
                    </th>

                    <th>
                      Autopilot
                    </th>

                    <th>
                      Battery
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {sample
                    .slice(
                      0,
                      20
                    )
                    .map(
                      (
                        row,
                        index
                      ) => (
                        <tr
                          key={
                            `${row.drive_id}-` +
                            `${row.timestamp}-` +
                            `${index}`
                          }
                        >
                          <td>
                            {
                              row.timestamp
                            }
                          </td>

                          <td>
                            {
                              row.drive_id
                            }
                          </td>

                          <td>
                            {
                              row.speed_kph ??
                              "—"
                            }{" "}
                            kph
                          </td>

                          <td>
                            {
                              row
                                .longitudinal_accel_mps2 ??
                              "—"
                            }{" "}
                            m/s²
                          </td>

                          <td>
                            {
                              row
                                .steering_angle_deg ??
                              "—"
                            }
                            °
                          </td>

                          <td>
                            {
                              row
                                .autopilot_state ??
                              "—"
                            }
                          </td>

                          <td>
                            {
                              row
                                .battery_soc_pct ??
                              "—"
                            }
                            %
                          </td>
                        </tr>
                      )
                    )}
                </tbody>
              </table>
            </div>
          )}
      </section>
    </>
  );
}
