import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";


function MetricTooltip({
  active,
  payload,
  label,
}) {
  if (
    !active ||
    !Array.isArray(payload) ||
    payload.length === 0
  ) {
    return null;
  }

  const currentValue = payload[0]?.value;

  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>

      <span>
        {currentValue}{" "}
        {currentValue === 1
          ? "event"
          : "events"}
      </span>
    </div>
  );
}


export default function MetricBarChart({
  title,
  data = [],
  xKey = "range",
  valueKey = "count",
  xLabel,
  yLabel = "Events",
  unit = "",
}) {
  const chartData = Array.isArray(data)
    ? data.map((item) => ({
        ...item,
        [xKey]: String(
          item?.[xKey] ?? ""
        ),
        [valueKey]:
          Number(item?.[valueKey]) || 0,
      }))
    : [];

  const formattedXLabel = unit
    ? `${xLabel} (${unit})`
    : xLabel;

  return (
    <article className="chart-card">
      <div className="chart-header">
        <h3>{title}</h3>
      </div>

      <div
        className="chart-container"
        style={{
          width: "100%",
          height: "340px",
        }}
      >
        <ResponsiveContainer
          width="100%"
          height="100%"
        >
          <BarChart
            data={chartData}
            margin={{
              top: 20,
              right: 20,
              bottom: 70,
              left: 35,
            }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
            />

            <XAxis
              dataKey={xKey}
              interval={0}
              height={100}
              tick={{
                fontSize: 11,
              }}
              angle={-90}
              textAnchor="middle"
              dy={25}
              label={{
                value: formattedXLabel,
                position: "insideBottom",
                offset: -10,
              }}
            />

            <YAxis
              allowDecimals={false}
              domain={[0, "auto"]}
              tick={{
                fontSize: 11,
              }}
              tickCount={6}
              width={65}
              label={{
                value: yLabel,
                angle: -90,
                position: "insideLeft",
                style: {
                  textAnchor: "middle",
                },
              }}
            />

            <Tooltip
              content={<MetricTooltip />}
            />

            <Bar
              dataKey={valueKey}
              fill="#3b82f6"
              name={yLabel}
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </article>
  );
}
