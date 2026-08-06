function formatInteger(value) {
  return value == null ? "—" : Number(value).toLocaleString("en-US");
}

export default function PipelineOverview({ pipeline }) {
  const metrics = [
    ["Files Processed", pipeline?.files_processed],
    ["Rows Ingested", pipeline?.rows_ingested],
    ["Rows Served", pipeline?.rows_served],
    ["Rows Dropped", pipeline?.rows_dropped],
  ];

  return (
    <section className="dashboard-section" aria-labelledby="pipeline-overview-title">
      <div className="section-heading">
        <p className="eyebrow">Data Processing</p>
        <h2 id="pipeline-overview-title">Pipeline Overview</h2>
        <p>Persisted telemetry ingestion statistics.</p>
      </div>

      <div className="metric-grid">
        {metrics.map(([label, value]) => (
          <article className="metric-card" key={label}>
            <span>{label}</span>
            <strong>{formatInteger(value)}</strong>
          </article>
        ))}
      </div>
    </section>
  );
}
