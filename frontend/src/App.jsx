import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  getAnalysis,
  getScenarioInsight,
} from "./api";

import PipelineOverview from "./components/PipelineOverview";
import EventOverview from "./components/EventOverview";
import AggregateAnalysis from "./components/AggregateAnalysis";
import CriticalInsights from "./components/CriticalInsights";


function App() {
  const [analysis, setAnalysis] = useState(null);

  const [
    selectedScenarioId,
    setSelectedScenarioId,
  ] = useState(null);

  const [
    scenarioInsight,
    setScenarioInsight,
  ] = useState(null);

  const [loading, setLoading] = useState(true);

  const [
    scenarioLoading,
    setScenarioLoading,
  ] = useState(false);

  const [error, setError] = useState(null);

  const [
    scenarioError,
    setScenarioError,
  ] = useState(null);


  useEffect(() => {
    let cancelled = false;

    async function loadAnalysis() {
      try {
        setLoading(true);
        setError(null);

        const data = await getAnalysis();

        if (!cancelled) {
          setAnalysis(data);
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Unable to load fleet analysis.",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadAnalysis();

    return () => {
      cancelled = true;
    };
  }, []);


  const handleSelectScenario = useCallback(
    async (scenarioId) => {
      if (!scenarioId) {
        return;
      }

      setSelectedScenarioId(scenarioId);
      setScenarioInsight(null);
      setScenarioError(null);
      setScenarioLoading(true);

      try {
        const data = await getScenarioInsight(
          scenarioId,
        );

        setScenarioInsight(data);
      } catch (requestError) {
        setScenarioError(
          requestError instanceof Error
            ? requestError.message
            : "Unable to load scenario details.",
        );
      } finally {
        setScenarioLoading(false);
      }
    },
    [],
  );


  if (loading) {
    return (
      <main className="app">
        <div className="loading-state">
          <h1>DRIVE</h1>
          <p>Loading fleet analysis...</p>
        </div>
      </main>
    );
  }


  if (error) {
    return (
      <main className="app">
        <div className="error-state">
          <h1>DRIVE</h1>
          <h2>Unable to load dashboard</h2>
          <p>{error}</p>
        </div>
      </main>
    );
  }


  if (!analysis) {
    return (
      <main className="app">
        <div className="error-state">
          <h1>DRIVE</h1>
          <p>No analysis data is available.</p>
        </div>
      </main>
    );
  }


  return (
    <main className="app">
      <header className="dashboard-header">
        <div>
          <p className="dashboard-eyebrow">
            DRIVE
          </p>

          <h1>
            {analysis.title ||
              "Fleet Data Analysis"}
          </h1>

          <p>
            Analyze Autopilot disengagements from vehicle
            telemetry.
          </p>
        </div>

        {analysis.status && (
          <div className="dashboard-status">
            {analysis.status}
          </div>
        )}
      </header>


      <PipelineOverview
        pipeline={analysis.pipeline}
      />


      <EventOverview
        events={analysis.events}
      />


      <AggregateAnalysis
        aggregate={analysis.aggregate}
      />


      <CriticalInsights
        criticalAnalysis={
          analysis.critical_analysis
        }
        selectedScenarioId={
          selectedScenarioId
        }
        scenarioInsight={
          scenarioInsight
        }
        scenarioLoading={
          scenarioLoading
        }
        scenarioError={
          scenarioError
        }
        onSelectScenario={
          handleSelectScenario
        }
      />
    </main>
  );
}


export default App;
