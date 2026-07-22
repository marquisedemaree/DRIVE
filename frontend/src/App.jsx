import { useEffect, useState } from "react";

import AnalyticsDashboard from "./components/AnalyticsDashboard";
import ScaleDashboard from "./components/ScaleDashboard";

export default function App() {
  const [modes, setModes] = useState({});
  const [mode, setMode] = useState("analytics");
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    loadInitialState();
  }, []);

  async function loadInitialState() {
    try {
      const [
        modesResponse,
        modeResponse,
        dashboardResponse,
      ] = await Promise.all([
        fetch("/api/modes"),
        fetch("/api/mode"),
        fetch("/api/dashboard"),
      ]);

      if (
        !modesResponse.ok ||
        !modeResponse.ok ||
        !dashboardResponse.ok
      ) {
        throw new Error("Unable to load DRIVE.");
      }

      const modesData =
        await modesResponse.json();

      const modeData =
        await modeResponse.json();

      const dashboardData =
        await dashboardResponse.json();

      setModes(modesData);
      setMode(modeData.mode);
      setDashboard(dashboardData);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleModeChange(event) {
    const selectedMode =
      event.target.value;

    setMode(selectedMode);
    setError("");

    try {
      const modeResponse = await fetch(
        "/api/mode",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            mode: selectedMode,
          }),
        }
      );

      if (!modeResponse.ok) {
        throw new Error(
          "Unable to change operating mode."
        );
      }

      const dashboardResponse =
        await fetch("/api/dashboard");

      if (!dashboardResponse.ok) {
        throw new Error(
          "Unable to load dashboard."
        );
      }

      setDashboard(
        await dashboardResponse.json()
      );
    } catch (err) {
      setError(err.message);
    }
  }

  const description =
    modes[mode]?.description ?? "";

  return (
    <main className="app-shell">
      <header className="mode-panel">
        <div className="brand-row">
          <div>
            <p className="eyebrow">
              Fleet Data Engineering
            </p>

            <h1>DRIVE</h1>
          </div>

          <label className="mode-selector">
            <span>Operating Mode</span>

            <select
              value={mode}
              onChange={handleModeChange}
            >
              <option value="analytics">
                Analytics Mode
              </option>

              <option value="scale">
                Scale Mode
              </option>
            </select>
          </label>
        </div>

        <p className="mode-description">
          {description}
        </p>
      </header>

      <section className="dashboard-container">
        {error && (
          <p className="error-message">
            {error}
          </p>
        )}

        {!error &&
          mode === "analytics" && (
            <AnalyticsDashboard
              dashboard={dashboard}
            />
          )}

        {!error &&
          mode === "scale" && (
            <ScaleDashboard
              dashboard={dashboard}
            />
          )}
      </section>
    </main>
  );
}
