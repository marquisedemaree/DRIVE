export default function ScaleDashboard({
  dashboard,
}) {
  return (
    <section>
      <div className="dashboard-heading">
        <p className="eyebrow">
          Scale Mode
        </p>

        <h2>
          {dashboard?.title ??
            "Fleet Scale & Infrastructure"}
        </h2>

        <p>
          {dashboard?.status ??
            "Loading dashboard..."}
        </p>
      </div>

      <div className="card-grid">
        {(dashboard?.sections ?? []).map(
          (section) => (
            <article
              className="dashboard-card"
              key={section}
            >
              <h3>{section}</h3>

              <p>
                Placeholder for future scale
                dashboard content.
              </p>
            </article>
          )
        )}
      </div>
    </section>
  );
}
