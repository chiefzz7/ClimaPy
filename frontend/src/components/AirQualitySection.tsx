import { Activity, Sparkles, Wind } from "lucide-react";
import type { AirQualityCurrent } from "../types/weather";
import { getAqiStyle } from "../utils/format";

interface AirQualitySectionProps {
  airQuality: AirQualityCurrent | null;
}

export function AirQualitySection({ airQuality }: AirQualitySectionProps) {
  if (!airQuality) {
    return (
      <section aria-label="Qualidade do ar" className="space-y-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
          Indicadores de qualidade do ar temporariamente indisponíveis para esta consulta.
        </div>
      </section>
    );
  }

  const style = getAqiStyle(airQuality.european_aqi);
  const progressPct = Math.min(100, Math.max(8, airQuality.european_aqi ?? 0));

  const metrics = [
    { label: "PM2.5 (Partículas finas)", value: airQuality.pm2_5, unit: "µg/m³" },
    { label: "PM10 (Partículas inaláveis)", value: airQuality.pm10, unit: "µg/m³" },
    { label: "Ozônio (O₃)", value: airQuality.ozone, unit: "µg/m³" },
    { label: "Dióxido de Nitrogênio (NO₂)", value: airQuality.nitrogen_dioxide, unit: "µg/m³" },
    { label: "Dióxido de Enxofre (SO₂)", value: airQuality.sulphur_dioxide, unit: "µg/m³" },
    { label: "Monóxido de Carbono (CO)", value: airQuality.carbon_monoxide, unit: "µg/m³" },
    { label: "Poeira em suspensão", value: airQuality.dust, unit: "µg/m³" },
  ];

  return (
    <section aria-label="Qualidade do ar" className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-bold text-slate-900 dark:text-slate-100">
              <Wind className="h-5 w-5 text-sky-500" />
              Qualidade do Ar (Copernicus / CAMS)
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Índices atmosféricos atualizados — base também usada na futura análise de IA.
            </p>
          </div>

          <span className={`rounded-full px-3.5 py-1 text-xs font-bold ${style.badgeClass}`}>
            {airQuality.category_pt ?? style.label}
          </span>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl bg-slate-50 p-4 dark:bg-slate-800/60">
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
              Índice Europeu (EAQI)
            </p>
            <p className="mt-1 text-3xl font-extrabold text-slate-900 dark:text-slate-100">
              {airQuality.european_aqi ?? "--"}
            </p>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
              <div
                className={`h-full rounded-full ${style.barClass}`}
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>

          <div className="rounded-xl bg-slate-50 p-4 dark:bg-slate-800/60">
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
              Índice Padrão EPA (US AQI)
            </p>
            <p className="mt-1 text-3xl font-extrabold text-slate-900 dark:text-slate-100">
              {airQuality.us_aqi ?? "--"}
            </p>
            <p className="mt-2 flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <Activity className="h-3.5 w-3.5 text-sky-500" />
              Referência internacional de 0 a 500
            </p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4">
          {metrics.map((metric) => (
            <div
              key={metric.label}
              className="rounded-xl border border-slate-100 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-950/50"
            >
              <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                {metric.label}
              </p>
              <p className="mt-1 text-base font-bold text-slate-900 dark:text-slate-100">
                {metric.value !== null && metric.value !== undefined
                  ? `${metric.value.toFixed(1)} `
                  : "-- "}
                <span className="text-xs font-normal text-slate-400">{metric.unit}</span>
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-start gap-3 rounded-2xl border border-indigo-200/70 bg-indigo-50/70 p-4 text-xs text-indigo-900 dark:border-indigo-900/50 dark:bg-indigo-950/40 dark:text-indigo-200">
        <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
        <div>
          <p className="font-bold">Preparado para IA Climática (Etapa 6)</p>
          <p className="mt-0.5 leading-relaxed opacity-90">
            Na próxima etapa final, o backend Python combinará temperatura, pressão, umidade,
            chuva horária e qualidade do ar para gerar recomendações inteligentes e alertas de
            mudanças bruscas do tempo.
          </p>
        </div>
      </div>
    </section>
  );
}
