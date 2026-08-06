import MetricBarChart from "../charts/MetricBarChart";

function firstDefined(object, keys, fallback = null) {
  for (const key of keys) {
    if (object?.[key] != null) {
      return object[key];
    }
  }
  return fallback;
}

function formatNumber(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toFixed(digits);
}

export default function EventOverview({ events }) {
  /*
  const eventCount = firstDefined(events, ["event_count", "number_of_events", "total_events"], 0);
  const averageSpeed = firstDefined(events, ["average_speed_kph", "avg_speed_kph"]);
  const averageLongitudinal = firstDefined(events, [
    "average_longitudinal_accel_g",
    "avg_longitudinal_accel_g",
  ]);
  const averageLateral = firstDefined(events, ["average_lateral_accel_g", "avg_lateral_accel_g"]);

  const speedDistribution = firstDefined(events, ["speed_distribution", "speed_bins"], []);
  const longitudinalDistribution = firstDefined(
    events,
    ["longitudinal_accel_distribution", "longitudinal_distribution", "longitudinal_accel_bins"],
    [],
  );
  const lateralDistribution = firstDefined(
    events,
    ["lateral_accel_distribution", "lateral_distribution", "lateral_accel_bins"],
    [],
  );
  */
  const summary = events?.summary ?? {};
  const distributions = events?.distributions ?? {};

  const eventCount = summary.event_count ?? 0;
  const averageSpeed = summary.average_speed_kph;
  const averageLongitudinal =
    summary.average_longitudinal_accel_g;
  const averageLateral =
    summary.average_absolute_lateral_accel_g;

  const speedDistribution =
    distributions.speed ?? [];

  const longitudinalDistribution =
    distributions.longitudinal_acceleration ?? [];

  const lateralDistribution =
    distributions.lateral_acceleration ?? [];
  
    return (
    <section className="dashboard-section" aria-labelledby="event-overview-title">
      <div className="section-heading">
        <p className="eyebrow">AP Disengagement Events</p>
        <h2 id="event-overview-title">Event Overview</h2>
        <p>Vehicle state at the instant Autopilot disengaged.</p>
      </div>

      <div className="metric-grid">
        <article className="metric-card">
          <span>Number of Events</span>
          <strong>{Number(eventCount).toLocaleString("en-US")}</strong>
        </article>
        <article className="metric-card">
          <span>Average Speed</span>
          <strong>{formatNumber(averageSpeed)} kph</strong>
        </article>
        <article className="metric-card">
          <span>Average Longitudinal Acceleration</span>
          <strong>{formatNumber(averageLongitudinal, 3)} g</strong>
        </article>
        <article className="metric-card">
          <span>Average Lateral Acceleration</span>
          <strong>{formatNumber(averageLateral, 3)} g</strong>
        </article>
      </div>

      <div className="chart-grid">
        <MetricBarChart
          title="Speed at AP Disengagement"
          data={speedDistribution}
          xKey="range"
          valueKey="count"
          xLabel="Speed"
          yLabel="Events"
          unit="kph"
        />

        <MetricBarChart
          title="Longitudinal Acceleration at AP Disengagement"
          data={longitudinalDistribution}
          xKey="range"
          valueKey="count"
          xLabel="Longitudinal Acceleration"
          yLabel="Events"
          unit="g"
        />

        <MetricBarChart
          title="Lateral Acceleration at AP Disengagement"
          data={lateralDistribution}
          xKey="range"
          valueKey="count"
          xLabel="Lateral Acceleration"
          yLabel="Events"
          unit="g"
        />
      </div>
    </section>
  );
}
