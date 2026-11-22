import type { HourlyForecastItem, TemperatureUnit } from "../types/weather";
import { convertTemp, formatHour, formatMm, formatTemp } from "../utils/format";

interface HourlyChartsProps {
  items: HourlyForecastItem[];
  unit: TemperatureUnit;
  selectedIndex: number;
  onSelectIndex: (index: number) => void;
}

export function HourlyCharts({
  items,
  unit,
  selectedIndex,
  onSelectIndex,
}: HourlyChartsProps) {
  if (items.length === 0) {
    return null;
  }

  const width = Math.max(640, items.length * 42);
  const height = 220;
  const padX = 26;
  const tempTop = 26;
  const tempBottom = 112;
  const rainTop = 136;
  const rainBottom = 186;

  const tempValues = items.map((item) =>
    item.temperature_c !== null ? convertTemp(item.temperature_c, unit) : 20
  );
  const feelsValues = items.map((item) =>
    item.apparent_temperature_c !== null
      ? convertTemp(item.apparent_temperature_c, unit)
      : item.temperature_c !== null
        ? convertTemp(item.temperature_c, unit)
        : 20
  );

  const minTemp = Math.min(...tempValues, ...feelsValues);
  const maxTemp = Math.max(...tempValues, ...feelsValues);
  const tempSpan = Math.max(2, maxTemp - minTemp);

  const xAt = (idx: number): number => {
    if (items.length === 1) return width / 2;
    return padX + (idx / (items.length - 1)) * (width - padX * 2);
  };

  const yTempAt = (val: number): number => {
    const ratio = (val - minTemp) / tempSpan;
    return tempBottom - ratio * (tempBottom - tempTop);
  };

  const tempPoints = items.map((_, idx) => `${xAt(idx).toFixed(1)},${yTempAt(tempValues[idx]).toFixed(1)}`);
  const feelsPoints = items.map(
    (_, idx) => `${xAt(idx).toFixed(1)},${yTempAt(feelsValues[idx]).toFixed(1)}`
  );

  const areaPoints = [
    `${xAt(0).toFixed(1)},${tempBottom}`,
    ...tempPoints,
    `${xAt(items.length - 1).toFixed(1)},${tempBottom}`,
  ].join(" ");

  const labelStep = items.length > 36 ? 4 : items.length > 18 ? 3 : 2;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 dark:text-slate-400">
        <div className="flex flex-wrap items-center gap-4">
          <span className="inline-flex items-center gap-1.5 font-medium text-slate-700 dark:text-slate-200">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
            Temperatura
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-3.5 border-t-2 border-dashed border-orange-400" />
            Sensação térmica
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-sky-500/80" />
            Chance de chuva (%)
          </span>
        </div>
        <span>Toque em um horário para inspecionar</span>
      </div>

      <div className="overflow-x-auto pb-2">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: `${width}px`, height: `${height}px` }}
          className="select-none"
          role="img"
          aria-label="Gráfico horário de temperatura e probabilidade de chuva"
        >
          <defs>
            <linearGradient id="tempAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.32" />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.02" />
            </linearGradient>
          </defs>

          <line
            x1={padX}
            y1={tempBottom}
            x2={width - padX}
            y2={tempBottom}
            stroke="currentColor"
            className="text-slate-200 dark:text-slate-800"
            strokeWidth="1"
          />

          <polygon points={areaPoints} fill="url(#tempAreaGrad)" />

          <polyline
            fill="none"
            stroke="#fb923c"
            strokeWidth="2"
            strokeDasharray="4 4"
            points={feelsPoints.join(" ")}
          />

          <polyline
            fill="none"
            stroke="#f59e0b"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={tempPoints.join(" ")}
          />

          {items.map((item, idx) => {
            const x = xAt(idx);
            const y = yTempAt(tempValues[idx]);
            const prob = Math.max(0, Math.min(100, item.precipitation_probability_percent ?? 0));
            const barHeight = (prob / 100) * (rainBottom - rainTop);
            const barY = rainBottom - barHeight;
            const isSelected = idx === selectedIndex;

            return (
              <g
                key={item.time}
                onClick={() => onSelectIndex(idx)}
                className="cursor-pointer"
              >
                <rect
                  x={x - 16}
                  y={0}
                  width={32}
                  height={height}
                  fill="transparent"
                />
                {isSelected && (
                  <line
                    x1={x}
                    y1={12}
                    x2={x}
                    y2={rainBottom}
                    stroke="#0ea5e9"
                    strokeWidth="1.5"
                    strokeDasharray="3 3"
                  />
                )}

                <rect
                  x={x - 7}
                  y={barY}
                  width={14}
                  height={Math.max(2, barHeight)}
                  rx={4}
                  fill={isSelected ? "#0284c7" : "#38bdf8"}
                  opacity={prob > 0 ? 0.85 : 0.22}
                />

                {(idx % labelStep === 0 || isSelected) && (
                  <text
                    x={x}
                    y={y - 9}
                    textAnchor="middle"
                    className="fill-slate-700 text-[11px] font-semibold dark:fill-slate-200"
                  >
                    {formatTemp(item.temperature_c, unit)}
                  </text>
                )}

                <circle
                  cx={x}
                  cy={y}
                  r={isSelected ? 5 : 3}
                  fill={isSelected ? "#0ea5e9" : "#f59e0b"}
                  stroke="#ffffff"
                  strokeWidth="1.5"
                />

                {(idx % labelStep === 0 || isSelected) && (
                  <>
                    <text
                      x={x}
                      y={rainTop - 4}
                      textAnchor="middle"
                      className="fill-sky-600 text-[10px] font-medium dark:fill-sky-400"
                    >
                      {prob}%
                    </text>
                    <text
                      x={x}
                      y={206}
                      textAnchor="middle"
                      className={`text-[10px] ${
                        isSelected
                          ? "fill-sky-600 font-bold dark:fill-sky-400"
                          : "fill-slate-500 dark:fill-slate-400"
                      }`}
                    >
                      {formatHour(item.time)}
                    </text>
                  </>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {items[selectedIndex] && (
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-800/70 dark:text-slate-300">
          <span>
            <strong>{formatHour(items[selectedIndex].time)}</strong> •{" "}
            {items[selectedIndex].condition.label_pt}
          </span>
          <span>
            Temp: <strong>{formatTemp(items[selectedIndex].temperature_c, unit)}</strong> |
            Chuva:{" "}
            <strong>{items[selectedIndex].precipitation_probability_percent ?? 0}%</strong> (
            {formatMm(items[selectedIndex].precipitation_mm)})
          </span>
        </div>
      )}
    </div>
  );
}
