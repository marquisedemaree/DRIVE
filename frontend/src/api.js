async function requestJson(path) {
  const response = await fetch(path);

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    try {
      const errorData = await response.json();

      if (errorData.detail) {
        message = errorData.detail;
      }
    } catch {
      // Keep the default status-based message.
    }

    throw new Error(message);
  }

  return response.json();
}


export function getAnalysis() {
  return requestJson("/api/analysis");
}


export function getScenarioInsight(scenarioId) {
  if (!scenarioId) {
    throw new Error("scenarioId is required.");
  }

  return requestJson(
    `/api/scenarios/${encodeURIComponent(scenarioId)}`
  );
}
