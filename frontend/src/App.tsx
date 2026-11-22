import {
  Bell,
  CalendarDays,
  Clock,
  CloudSun,
  Loader2,
  Moon,
  RefreshCw,
  Sun,
  Wind,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AirQualitySection } from "./components/AirQualitySection";
import { CitySearchBar } from "./components/CitySearchBar";
import { CurrentWeatherHero } from "./components/CurrentWeatherHero";
import { DailyForecastSection } from "./components/DailyForecastSection";
import { HourlySection } from "./components/HourlySection";
import { RemindersSection } from "./components/RemindersSection";
import { ApiError, fetchForecast } from "./services/api";
import { registerAppServiceWorker } from "./services/push";
import {
  isFavoriteLocation,
  loadActiveLocation,
  loadFavorites,
  loadForecastSnapshot,
  loadTheme,
  loadUnit,
  saveActiveLocation,
  saveForecastSnapshot,
  saveTheme,
  saveUnit,
  toggleFavoriteLocation,
} from "./services/storage";
import type {
  SavedLocation,
  TemperatureUnit,
  ThemeMode,
  WeatherForecastResponse,
} from "./types/weather";
import { extractDatePrefix } from "./utils/format";

type ActiveTab = "hourly" | "daily" | "air" | "reminders";

export function App() {
  const [theme, setTheme] = useState<ThemeMode>(() => loadTheme());
  const [unit, setUnit] = useState<TemperatureUnit>(() => loadUnit());
  const [activeLocation, setActiveLocation] = useState<SavedLocation>(() => loadActiveLocation());
  const [favorites, setFavorites] = useState<SavedLocation[]>(() => loadFavorites());
  const [activeTab, setActiveTab] = useState<ActiveTab>("hourly");

  const [forecast, setForecast] = useState<WeatherForecastResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingFullHourly, setLoadingFullHourly] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isOfflineSnapshot, setIsOfflineSnapshot] = useState<boolean>(false);
  const [snapshotSavedAt, setSnapshotSavedAt] = useState<string | null>(null);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    saveTheme(theme);
  }, [theme]);

  useEffect(() => {
    saveUnit(unit);
  }, [unit]);

  useEffect(() => {
    void registerAppServiceWorker();
  }, []);

  const loadWeather = useCallback(
    async (loc: SavedLocation, fullHourly = false) => {
      if (fullHourly) {
        setLoadingFullHourly(true);
      } else {
        setLoading(true);
      }
      setErrorMsg(null);

      try {
        const data = await fetchForecast({
          lat: loc.latitude,
          lon: loc.longitude,
          days: 16,
          tz: loc.timezone || "auto",
          includeAirQuality: true,
          includeFullHourly: fullHourly,
        });
        setForecast(data);
        setIsOfflineSnapshot(false);
        setSnapshotSavedAt(null);
        saveForecastSnapshot(loc, data);
      } catch (err) {
        const fallback = loadForecastSnapshot(loc);
        if (fallback) {
          setForecast(fallback.forecast);
          setIsOfflineSnapshot(true);
          setSnapshotSavedAt(fallback.savedAt);
        } else {
          setForecast(null);
          setErrorMsg(
            err instanceof ApiError
              ? err.detail
              : "Não foi possível carregar a previsão do tempo."
          );
        }
      } finally {
        setLoading(false);
        setLoadingFullHourly(false);
      }
    },
    []
  );

  useEffect(() => {
    saveActiveLocation(activeLocation);
    void loadWeather(activeLocation, false);
  }, [activeLocation, loadWeather]);

  function handleSelectLocation(loc: SavedLocation) {
    setActiveLocation(loc);
  }

  function handleToggleFavorite(loc: SavedLocation) {
    setFavorites(toggleFavoriteLocation(loc));
  }

  const referenceToday = forecast
    ? extractDatePrefix(forecast.current.time)
    : new Date().toISOString().slice(0, 10);

  const navItems: { id: ActiveTab; label: string; icon: typeof Clock }[] = [
    { id: "hourly", label: "72 Horas", icon: Clock },
    { id: "daily", label: "16 Dias", icon: CalendarDays },
    { id: "air", label: "Qualidade do Ar", icon: Wind },
    { id: "reminders", label: "Lembretes", icon: Bell },
  ];

  return (
    <div className="min-h-screen bg-slate-50 pb-24 text-slate-900 transition-colors dark:bg-slate-950 dark:text-slate-100 sm:pb-10">
      <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/85 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-950/85">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-blue-700 text-white shadow-sm">
              <CloudSun className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-base font-extrabold tracking-tight">ClimaPy</h1>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Previsão horária segura e sem login
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setUnit((u) => (u === "c" ? "f" : "c"))}
              aria-label="Alternar unidade de temperatura"
              className="rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-bold text-slate-700 shadow-sm hover:border-sky-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
            >
              °{unit.toUpperCase()}
            </button>

            <button
              type="button"
              onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
              aria-label="Alternar tema claro e escuro"
              className="rounded-xl border border-slate-200 bg-white p-2 text-slate-700 shadow-sm hover:border-sky-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
            >
              {theme === "dark" ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4" />}
            </button>

            <button
              type="button"
              onClick={() => void loadWeather(activeLocation, false)}
              disabled={loading}
              aria-label="Atualizar previsão"
              className="rounded-xl border border-slate-200 bg-white p-2 text-slate-700 shadow-sm hover:border-sky-400 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin text-sky-500" : ""}`} />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-5 px-4 pt-5">
        <CitySearchBar
          activeLocation={activeLocation}
          favorites={favorites}
          onSelectLocation={handleSelectLocation}
          onRemoveFavorite={handleToggleFavorite}
        />

        {loading && !forecast ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-3xl border border-slate-200 bg-white py-16 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            <Loader2 className="h-7 w-7 animate-spin text-sky-500" />
            <span>Carregando previsão para {activeLocation.name}...</span>
          </div>
        ) : errorMsg && !forecast ? (
          <div className="rounded-3xl border border-rose-200 bg-rose-50 p-6 text-center text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-200">
            <p className="font-semibold">{errorMsg}</p>
            <button
              type="button"
              onClick={() => void loadWeather(activeLocation, false)}
              className="mt-3 rounded-xl bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-700"
            >
              Tentar novamente
            </button>
          </div>
        ) : forecast ? (
          <CurrentWeatherHero
            location={activeLocation}
            forecast={forecast}
            unit={unit}
            isFavorite={isFavoriteLocation(favorites, activeLocation)}
            isOfflineSnapshot={isOfflineSnapshot}
            snapshotSavedAt={snapshotSavedAt}
            onToggleFavorite={() => handleToggleFavorite(activeLocation)}
          />
        ) : null}

        <nav
          aria-label="Navegação principal"
          className="hidden gap-2 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:grid sm:grid-cols-4"
        >
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveTab(item.id)}
                className={`flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-xs font-bold transition ${
                  active
                    ? "bg-sky-600 text-white shadow-sm"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {activeTab === "hourly" && forecast && (
          <HourlySection
            hourly72h={forecast.hourly_72h}
            referenceToday={referenceToday}
            unit={unit}
          />
        )}

        {activeTab === "daily" && forecast && (
          <DailyForecastSection
            daily={forecast.daily}
            hourlyFull={forecast.hourly}
            hourly72h={forecast.hourly_72h}
            referenceToday={referenceToday}
            unit={unit}
            loadingFullHourly={loadingFullHourly}
            onRequestFullHourly={() => loadWeather(activeLocation, true)}
          />
        )}

        {activeTab === "air" && forecast && (
          <AirQualitySection airQuality={forecast.air_quality} />
        )}

        {activeTab === "reminders" && <RemindersSection activeLocation={activeLocation} />}

        <footer className="border-t border-slate-200 pt-5 text-center text-[11px] leading-relaxed text-slate-500 dark:border-slate-800 dark:text-slate-400">
          <p>
            Dados meteorológicos gratuitos:{" "}
            <a
              href="https://open-meteo.com/"
              target="_blank"
              rel="noreferrer"
              className="font-semibold underline hover:text-sky-600"
            >
              Open-Meteo (CC BY 4.0)
            </a>
            {" • "}
            <a
              href="https://api.met.no/"
              target="_blank"
              rel="noreferrer"
              className="font-semibold underline hover:text-sky-600"
            >
              MET Norway (CC BY 4.0)
            </a>
            {" • "}
            <a
              href="https://www.openstreetmap.org/copyright"
              target="_blank"
              rel="noreferrer"
              className="font-semibold underline hover:text-sky-600"
            >
              OpenStreetMap Nominatim (ODbL)
            </a>
          </p>
          {forecast && (
            <p className="mt-1">
              Fonte ativa nesta consulta: <strong>{forecast.attribution.provider_label}</strong>
              {forecast.attribution.fallback_used ? " (fallback automático)" : ""}
            </p>
          )}
        </footer>
      </main>

      <nav
        aria-label="Navegação inferior mobile"
        className="fixed bottom-0 left-0 right-0 z-30 grid grid-cols-4 border-t border-slate-200 bg-white/95 px-2 py-1.5 backdrop-blur-md dark:border-slate-800 dark:bg-slate-950/95 sm:hidden"
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveTab(item.id)}
              className={`flex flex-col items-center gap-0.5 rounded-xl py-1 text-[11px] font-semibold transition ${
                active ? "text-sky-600 dark:text-sky-400" : "text-slate-500 dark:text-slate-400"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
export default App;
