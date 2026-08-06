import CriticalFindingsTable from "./CriticalFindingsTable";
import ScenarioDrillDown from "./ScenarioDrillDown";

function formatPercent(value) {
  return value == null ? "—" : `${Number(value).toFixed(1)}%`;
}

function formatThreshold(value) {
  return value == null ? "—" : Number(value).toFixed(1);
}

export default function CriticalInsights({
  criticalAnalysis,
  selectedScenarioId,
  onSelectScenario,
  scenarioInsight,
  scenarioLoading = false,
}) {
  const summary = criticalAnalysis?.summary ?? {};
  const findings = criticalAnalysis?.findings ?? [];

  return (
    <section className="dashboard-section" aria-labelledby="critical-insights-title">
      <div className="section-heading">
        <p className="eyebrow">Post-Disengagement Response</p>
        <h2 id="critical-insights-title">Critical Insights</h2>
        <p>Scenarios that crossed configured driving-response thresholds after AP disengagement.</p>
      </div>

      <div className="threshold-definitions">
        <article className="threshold-card">
          <h3>Harsh Braking</h3>
          <p>
            Longitudinal acceleration ≤ −{formatThreshold(summary.hard_braking_threshold_g)} g.
          </p>
        </article>
        <article className="threshold-card">
          <h3>Hard Turning</h3>
          <p>
            Absolute lateral acceleration ≥ {formatThreshold(summary.hard_turning_threshold_g)} g.
          </p>
        </article>
      </div>

      <div className="metric-grid">
        <article className="metric-card">
          <span>Critical Findings</span>
          <strong>{Number(summary.critical_findings ?? 0).toLocaleString("en-US")}</strong>
        </article>
        <article className="metric-card">
          <span>Scenarios with Harsh Braking</span>
          <strong>{formatPercent(summary.harsh_braking_pct)}</strong>
        </article>
        <article className="metric-card">
          <span>Scenarios with Hard Turning</span>
          <strong>{formatPercent(summary.hard_turning_pct)}</strong>
        </article>
      </div>

      <div className="subsection-heading">
        <h3>Critical Findings</h3>
        <p>Sort the table and select a scenario for synchronized telemetry drill-down.</p>
      </div>

      <CriticalFindingsTable
        findings={findings}
        selectedScenarioId={selectedScenarioId}
        onSelectScenario={onSelectScenario}
      />

      <ScenarioDrillDown
        scenarioInsight={scenarioInsight}
        loading={scenarioLoading}
      />
    </section>
  );
}
