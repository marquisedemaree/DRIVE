import ScenarioLineChart from "../charts/ScenarioLineChart";

const SERIES = {
  speed: [
    {
      dataKey: "avg_speed_kph",
      name: "Average",
      stroke: "#2563eb",
      strokeWidth: 3,
    },
  ],
  longitudinal: [
    {
      dataKey: "avg_longitudinal_accel_g",
      name: "Average",
      stroke: "#2563eb",
      strokeWidth: 3,
    },
  ],
  lateral: [
    {
      dataKey: "avg_lateral_accel_g",
      name: "Average",
      stroke: "#2563eb",
      strokeWidth: 3,
    },
  ],
};

const RANGES = {
  speed: {
    minKey: "min_speed_kph",
    maxKey: "max_speed_kph",
    name: "Minimum–Maximum Range",
    fill: "#93c5fd",
    fillOpacity: 0.35,
    showInLegend: true,
  },
  longitudinal: {
    minKey: "min_longitudinal_accel_g",
    maxKey: "max_longitudinal_accel_g",
    name: "Minimum–Maximum Range",
    fill: "#93c5fd",
    fillOpacity: 0.35,
    showInLegend: true,
  },
  lateral: {
    minKey: "min_lateral_accel_g",
    maxKey: "max_lateral_accel_g",
    name: "Minimum–Maximum Range",
    fill: "#93c5fd",
    fillOpacity: 0.35,
    showInLegend: true,
  },
};

export default function AggregateAnalysis({ aggregate }) {
  const temporal = aggregate?.temporal ?? [];
  const disengagementTime =
    aggregate?.disengagement_time_s ?? 0;

  return (
    <section
      className="dashboard-section"
      aria-labelledby="aggregate-analysis-title"
    >
      <div className="section-heading">
        <p className="eyebrow">All Scenarios</p>
        <h2 id="aggregate-analysis-title">
          Aggregate Scenario Analysis
        </h2>
        <p>
          Average behavior with the minimum-to-maximum range
          around AP disengagements.
        </p>
      </div>

      <div className="chart-grid">
        <ScenarioLineChart
          title="Speed Around AP Disengagement"
          data={temporal}
          xKey="relative_time_s"
          series={SERIES.speed}
          range={RANGES.speed}
          unit="kph"
          yLabel="Speed"
          disengagementTime={disengagementTime}
        />

        <ScenarioLineChart
          title="Longitudinal Acceleration"
          data={temporal}
          xKey="relative_time_s"
          series={SERIES.longitudinal}
          range={RANGES.longitudinal}
          unit="g"
          yLabel="Longitudinal Acceleration"
          disengagementTime={disengagementTime}
        />

        <ScenarioLineChart
          title="Absolute Lateral Acceleration"
          data={temporal}
          xKey="relative_time_s"
          series={SERIES.lateral}
          range={RANGES.lateral}
          unit="g"
          yLabel="Lateral Acceleration"
          disengagementTime={disengagementTime}
        />
      </div>
    </section>
  );
}
