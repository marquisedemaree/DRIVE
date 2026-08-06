import { useMemo, useState } from "react";

const SORT_FIELDS = {
  scenario_id: "string",
  drive_id: "string",
  disengagement_timestamp: "date",
  speed_kph: "number",
  finding_type: "string",
  peak_braking_g: "number",
  peak_lateral_g: "number",
};

function compareValues(left, right, type) {
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;

  if (type === "number") return Number(left) - Number(right);
  if (type === "date") return new Date(left).getTime() - new Date(right).getTime();
  return String(left).localeCompare(String(right));
}

function formatNumber(value, digits = 2) {
  return value == null ? "—" : Number(value).toFixed(digits);
}

function formatTimestamp(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export default function CriticalFindingsTable({ findings = [], selectedScenarioId, onSelectScenario }) {
  const [sort, setSort] = useState({ field: "disengagement_timestamp", direction: "asc" });

  const sortedFindings = useMemo(() => {
    const rows = [...findings];
    rows.sort((left, right) => {
      const result = compareValues(
        left[sort.field],
        right[sort.field],
        SORT_FIELDS[sort.field],
      );
      return sort.direction === "asc" ? result : -result;
    });
    return rows;
  }, [findings, sort]);

  function handleSort(field) {
    setSort((current) => ({
      field,
      direction: current.field === field && current.direction === "asc" ? "desc" : "asc",
    }));
  }

  function sortLabel(field, label) {
    if (sort.field !== field) return label;
    return `${label} ${sort.direction === "asc" ? "▲" : "▼"}`;
  }

  if (findings.length === 0) {
    return <p className="empty-state">No critical findings were detected.</p>;
  }

  return (
    <div className="table-container">
      <table className="findings-table">
        <thead>
          <tr>
            <th><button type="button" onClick={() => handleSort("scenario_id")}>{sortLabel("scenario_id", "Scenario")}</button></th>
            <th><button type="button" onClick={() => handleSort("drive_id")}>{sortLabel("drive_id", "Drive")}</button></th>
            <th><button type="button" onClick={() => handleSort("disengagement_timestamp")}>{sortLabel("disengagement_timestamp", "Disengagement")}</button></th>
            <th><button type="button" onClick={() => handleSort("speed_kph")}>{sortLabel("speed_kph", "Speed")}</button></th>
            <th><button type="button" onClick={() => handleSort("finding_type")}>{sortLabel("finding_type", "Finding")}</button></th>
            <th><button type="button" onClick={() => handleSort("peak_braking_g")}>{sortLabel("peak_braking_g", "Peak Braking")}</button></th>
            <th><button type="button" onClick={() => handleSort("peak_lateral_g")}>{sortLabel("peak_lateral_g", "Peak Lateral")}</button></th>
          </tr>
        </thead>
        <tbody>
          {sortedFindings.map((finding) => {
            const selected = finding.scenario_id === selectedScenarioId;
            return (
              <tr
                key={finding.scenario_id}
                className={selected ? "selected-row" : undefined}
                onClick={() => onSelectScenario?.(finding.scenario_id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectScenario?.(finding.scenario_id);
                  }
                }}
                tabIndex={0}
                aria-selected={selected}
              >
                <td>{finding.scenario_id}</td>
                <td>{finding.drive_id}</td>
                <td>{formatTimestamp(finding.disengagement_timestamp)}</td>
                <td>{formatNumber(finding.speed_kph)} kph</td>
                <td>{finding.finding_type}</td>
                <td>{formatNumber(finding.peak_braking_g, 3)} g</td>
                <td>{formatNumber(finding.peak_lateral_g, 3)} g</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
