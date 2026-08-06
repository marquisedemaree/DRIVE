import ScenarioLineChart from "../charts/ScenarioLineChart";

function formatNumber(value, digits = 2) {
  return value == null ? "—" : Number(value).toFixed(digits);
}

function formatCrossing(value) {
  return value == null ? "Not crossed" : `${Number(value).toFixed(2)} s`;
}

export default function ScenarioDrillDown({ scenarioInsight, loading = false }) {
  if (loading) {
    return <p className="loading-state">Loading selected scenario…</p>;
  }

  if (!scenarioInsight) {
    return (
      <section className="scenario-drill-down" aria-labelledby="scenario-drill-down-title">
        <h3 id="scenario-drill-down-title">Scenario Drill-Down</h3>
        <p className="empty-state">Select a critical finding to inspect its telemetry.</p>
      </section>
    );
  }

  const scenario = scenarioInsight.scenario ?? {};
  const thresholds = scenarioInsight.thresholds ?? {};
  const telemetry = scenarioInsight.telemetry ?? [];
  const disengagementTime = thresholds.disengagement_time_s ?? 0;

  return (
    <section className="scenario-drill-down" aria-labelledby="scenario-drill-down-title">
      <div className="section-heading">
        <p className="eyebrow">Selected Critical Scenario</p>
        <h3 id="scenario-drill-down-title">Scenario Drill-Down</h3>
      </div>

      <div className="scenario-header">
        <div><span>Scenario</span><strong>{scenario.scenario_id ?? "—"}</strong></div>
        <div><span>Drive</span><strong>{scenario.drive_id ?? "—"}</strong></div>
        <div><span>Disengagement</span><strong>{scenario.disengagement_timestamp ?? "—"}</strong></div>
        <div><span>Finding</span><strong>{scenario.finding_type ?? "—"}</strong></div>
        <div><span>Speed</span><strong>{formatNumber(scenario.speed_kph)} kph</strong></div>
        <div><span>Peak Braking</span><strong>{formatNumber(scenario.peak_braking_g, 3)} g</strong></div>
        <div><span>Peak Lateral</span><strong>{formatNumber(scenario.peak_lateral_g, 3)} g</strong></div>
        <div><span>Braking Crossing</span><strong>{formatCrossing(scenario.braking_threshold_crossing_time_s)}</strong></div>
        <div><span>Turning Crossing</span><strong>{formatCrossing(scenario.turning_threshold_crossing_time_s)}</strong></div>
      </div>

      <div className="chart-grid">
        <ScenarioLineChart
          title="Speed"
          data={telemetry}
          xKey="relative_time_s"
          series={[{ dataKey: "speed_kph", name: "Speed" }]}
          unit="kph"
          yLabel="Speed"
          disengagementTime={disengagementTime}
        />
        <ScenarioLineChart
          title="Longitudinal Acceleration"
          data={telemetry}
          xKey="relative_time_s"
          series={[{ dataKey: "longitudinal_accel_g", name: "Longitudinal Acceleration" }]}
          unit="g"
          yLabel="Longitudinal Acceleration"
          disengagementTime={disengagementTime}
          thresholds={[
            { value: thresholds.hard_braking_g, label: "Harsh Braking Threshold" },
          ]}
        />
        <ScenarioLineChart
          title="Lateral Acceleration"
          data={telemetry}
          xKey="relative_time_s"
          series={[{ dataKey: "lateral_accel_g", name: "Lateral Acceleration" }]}
          unit="g"
          yLabel="Lateral Acceleration"
          disengagementTime={disengagementTime}
          thresholds={[
            { value: thresholds.hard_turning_positive_g, label: "+ Hard Turning Threshold" },
            { value: thresholds.hard_turning_negative_g, label: "− Hard Turning Threshold" },
          ]}
        />
      </div>
    </section>
  );
}
