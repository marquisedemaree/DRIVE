import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const SERIES_STYLES = [
  { stroke: "#2563eb", dash: undefined },
  { stroke: "#111827", dash: undefined },
  { stroke: "#dc2626", dash: undefined },
];

function formatNumber(value, unit) {
  if (value == null || Number.isNaN(Number(value))) {
    return "—";
  }

  const numericValue = Number(value);
  const digits = Math.abs(numericValue) < 10 ? 3 : 2;
  const formatted = numericValue.toFixed(digits);

  return unit ? `${formatted} ${unit}` : formatted;
}

function ScenarioTooltip({
  active,
  payload,
  label,
  unit,
  range,
}) {
  if (!active || !payload?.length) {
    return null;
  }

  const visibleEntries = payload.filter(
    (entry) =>
      entry.dataKey !== "__rangeBase" &&
      entry.dataKey !== "__rangeHeight",
  );

  const sourcePoint = payload[0]?.payload;

  return (
    <div className="chart-tooltip">
      <strong>{Number(label).toFixed(2)} s</strong>

      {visibleEntries.map((entry) => (
        <span key={entry.dataKey}>
          {entry.name}: {formatNumber(entry.value, unit)}
        </span>
      ))}

      {range && sourcePoint ? (
        <>
          <span>
            Minimum:{" "}
            {formatNumber(sourcePoint[range.minKey], unit)}
          </span>
          <span>
            Maximum:{" "}
            {formatNumber(sourcePoint[range.maxKey], unit)}
          </span>
        </>
      ) : null}
    </div>
  );
}

export default function ScenarioLineChart({
  title,
  data = [],
  xKey = "relative_time_s",
  series = [],
  range = null,
  unit = "",
  yLabel = "",
  disengagementTime = 0,
  thresholds = [],
}) {
  const hasData = Array.isArray(data) && data.length > 0;

  const validSeries = Array.isArray(series)
    ? series.filter((item) => item?.dataKey)
    : [];

  const validThresholds = Array.isArray(thresholds)
    ? thresholds.filter(
        (threshold) =>
          threshold?.value != null &&
          !Number.isNaN(Number(threshold.value)),
      )
    : [];

  const hasRange =
    range?.minKey &&
    range?.maxKey;

  const chartData = hasRange
    ? data.map((point) => {
        const minimum = Number(point[range.minKey]);
        const maximum = Number(point[range.maxKey]);

        const hasValidRange =
          !Number.isNaN(minimum) &&
          !Number.isNaN(maximum);

        return {
          ...point,
          __rangeBase: hasValidRange ? minimum : null,
          __rangeHeight: hasValidRange
            ? maximum - minimum
            : null,
        };
      })
    : data;

  const showLegend =
    validSeries.length > 1 ||
    Boolean(range?.showInLegend);

  return (
    <article className="chart-card" aria-label={title}>
      <div className="chart-header">
        <h3>{title}</h3>
      </div>

      {!hasData || validSeries.length === 0 ? (
        <div className="chart-empty-state">
          <p>No chart data available.</p>
        </div>
      ) : (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={340}>
            <ComposedChart
              data={chartData}
              margin={{
                top: 12,
                right: 24,
                bottom: 18,
                left: 16,
              }}
            >
              <CartesianGrid strokeDasharray="3 3" />

              <XAxis
                dataKey={xKey}
                type="number"
                domain={["dataMin", "dataMax"]}
                tick={{ fontSize: 12 }}
                tickFormatter={(value) =>
                  Number(value).toFixed(1)
                }
                label={{
                  value: "Time from AP disengagement (s)",
                  position: "insideBottom",
                  offset: -18,
                }}
              />

              <YAxis
                tick={{ fontSize: 12 }}
                label={{
                  value: unit
                    ? `${yLabel} (${unit})`
                    : yLabel,
                  angle: -90,
                  position: "insideLeft",
                  style: {
                    textAnchor: "middle",
                  },
                }}
              />

              <Tooltip
                content={
                  <ScenarioTooltip
                    unit={unit}
                    range={hasRange ? range : null}
                  />
                }
              />

              {showLegend ? (
                <Legend
                  verticalAlign="bottom"
                  align="center"
                  wrapperStyle={{
                    bottom: -12,
                  }}
                />
              ) : null}

              <ReferenceLine
                x={Number(disengagementTime)}
                stroke="#6b7280"
                strokeDasharray="5 5"
                label={{
                  value: "AP disengagement",
                  position: "insideTopRight",
                  fill: "#6b7280",
                  fontSize: 11,
                }}
              />

              {validThresholds.map((threshold, index) => (
                <ReferenceLine
                  key={`${threshold.label ?? "threshold"}-${threshold.value}-${index}`}
                  y={Number(threshold.value)}
                  stroke="#b91c1c"
                  strokeDasharray="6 4"
                  label={{
                    value:
                      threshold.label ?? "Threshold",
                    position: "insideTopRight",
                    fill: "#b91c1c",
                    fontSize: 11,
                  }}
                />
              ))}

              {hasRange ? (
                <>
                  <Area
                    type="monotone"
                    dataKey="__rangeBase"
                    stackId="aggregateRange"
                    stroke="none"
                    fill="transparent"
                    legendType="none"
                    tooltipType="none"
                    connectNulls
                    isAnimationActive={false}
                  />

                  <Area
                    type="monotone"
                    dataKey="__rangeHeight"
                    stackId="aggregateRange"
                    name={range.name ?? "Range"}
                    stroke="none"
                    fill={range.fill ?? "#93c5fd"}
                    fillOpacity={
                      range.fillOpacity ?? 0.35
                    }
                    legendType={
                      range.showInLegend
                        ? "rect"
                        : "none"
                    }
                    tooltipType="none"
                    connectNulls
                    isAnimationActive={false}
                  />
                </>
              ) : null}

              {validSeries.map((item, index) => {
                const style =
                  SERIES_STYLES[
                    index % SERIES_STYLES.length
                  ];

                return (
                  <Line
                    key={item.dataKey}
                    type="monotone"
                    dataKey={item.dataKey}
                    name={item.name ?? item.dataKey}
                    stroke={
                      item.stroke ?? style.stroke
                    }
                    strokeWidth={
                      item.strokeWidth ?? 2
                    }
                    strokeDasharray={
                      item.strokeDasharray ??
                      style.dash
                    }
                    dot={false}
                    activeDot={{ r: 4 }}
                    connectNulls
                    isAnimationActive={false}
                  />
                );
              })}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </article>
  );
}
