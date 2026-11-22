import { LocateFixed, MapPin, Search, Star, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ApiError, reverseGeocode, searchLocations } from "../services/api";
import { locationKey } from "../services/storage";
import type { LocationResult, SavedLocation } from "../types/weather";

interface CitySearchBarProps {
  activeLocation: SavedLocation;
  favorites: SavedLocation[];
  onSelectLocation: (location: SavedLocation) => void;
  onRemoveFavorite: (location: SavedLocation) => void;
}

export function CitySearchBar({
  activeLocation,
  favorites,
  onSelectLocation,
  onRemoveFavorite,
}: CitySearchBarProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<LocationResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [locatingGps, setLocatingGps] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleOutsideClick(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setResults([]);
      setSearching(false);
      return;
    }

    let cancelled = false;
    setSearching(true);
    setErrorMsg(null);
    const timer = window.setTimeout(async () => {
      try {
        const res = await searchLocations(trimmed, 6, "pt");
        if (!cancelled) {
          setResults(res.results);
          setDropdownOpen(true);
        }
      } catch (err) {
        if (!cancelled) {
          setErrorMsg(err instanceof ApiError ? err.detail : "Erro ao buscar cidades.");
        }
      } finally {
        if (!cancelled) {
          setSearching(false);
        }
      }
    }, 350);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  function pickResult(loc: LocationResult) {
    onSelectLocation({
      name: loc.name,
      displayName: loc.display_name,
      latitude: loc.latitude,
      longitude: loc.longitude,
      timezone: loc.timezone ?? "auto",
    });
    setQuery("");
    setResults([]);
    setDropdownOpen(false);
    setErrorMsg(null);
  }

  function handleUseGps() {
    if (!("geolocation" in navigator)) {
      setErrorMsg("Geolocalização não suportada neste dispositivo.");
      return;
    }
    setLocatingGps(true);
    setErrorMsg(null);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const rev = await reverseGeocode(pos.coords.latitude, pos.coords.longitude);
          onSelectLocation({
            name: rev.location.name,
            displayName: rev.location.display_name,
            latitude: rev.location.latitude,
            longitude: rev.location.longitude,
            timezone: "auto",
          });
          setDropdownOpen(false);
        } catch {
          onSelectLocation({
            name: "Localização GPS",
            displayName: `Lat ${pos.coords.latitude.toFixed(2)}, Lon ${pos.coords.longitude.toFixed(2)}`,
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            timezone: "auto",
          });
        } finally {
          setLocatingGps(false);
        }
      },
      () => {
        setLocatingGps(false);
        setErrorMsg("Permissão de localização negada ou indisponível.");
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
    );
  }

  const activeKey = locationKey(activeLocation.latitude, activeLocation.longitude);

  return (
    <div ref={containerRef} className="space-y-3">
      <div className="relative flex gap-2">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            aria-hidden="true"
          />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => {
              if (results.length > 0) setDropdownOpen(true);
            }}
            placeholder="Buscar cidade (ex.: Registro, Curitiba, Recife)..."
            aria-label="Buscar cidade"
            className="w-full rounded-2xl border border-slate-200 bg-white py-2.5 pl-10 pr-9 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
          />
          {query && (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                setResults([]);
                setDropdownOpen(false);
              }}
              aria-label="Limpar busca"
              className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <button
          type="button"
          onClick={handleUseGps}
          disabled={locatingGps}
          title="Usar minha localização aproximada"
          aria-label="Usar minha localização GPS"
          className="inline-flex items-center gap-1.5 rounded-2xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-sky-400 hover:text-sky-600 disabled:opacity-60 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-sky-500 dark:hover:text-sky-400"
        >
          <LocateFixed className={`h-4 w-4 ${locatingGps ? "animate-spin text-sky-500" : ""}`} />
          <span className="hidden sm:inline">{locatingGps ? "Localizando..." : "GPS"}</span>
        </button>

        {dropdownOpen && (results.length > 0 || searching) && (
          <div className="absolute left-0 right-0 top-full z-30 mt-1.5 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900">
            {searching ? (
              <p className="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">
                Buscando localidades...
              </p>
            ) : (
              <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                {results.map((item, idx) => (
                  <li key={`${item.id ?? idx}-${item.latitude}-${item.longitude}`}>
                    <button
                      type="button"
                      onClick={() => pickResult(item)}
                      className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm transition hover:bg-sky-50 dark:hover:bg-slate-800/70"
                    >
                      <span className="flex items-center gap-2 font-medium text-slate-800 dark:text-slate-100">
                        <MapPin className="h-4 w-4 shrink-0 text-sky-500" />
                        <span>{item.display_name}</span>
                      </span>
                      <span className="ml-2 shrink-0 text-xs text-slate-400">
                        {item.latitude.toFixed(2)}, {item.longitude.toFixed(2)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {errorMsg && (
        <p className="text-xs font-medium text-rose-600 dark:text-rose-400">{errorMsg}</p>
      )}

      {favorites.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 inline-flex items-center gap-1 text-xs font-medium text-slate-500 dark:text-slate-400">
            <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
            Favoritas:
          </span>
          {favorites.map((fav) => {
            const isSelected = locationKey(fav.latitude, fav.longitude) === activeKey;
            return (
              <div
                key={locationKey(fav.latitude, fav.longitude)}
                className={`inline-flex items-center rounded-full border text-xs transition ${
                  isSelected
                    ? "border-sky-500 bg-sky-500/15 text-sky-700 dark:text-sky-300"
                    : "border-slate-200 bg-white text-slate-700 hover:border-sky-300 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelectLocation(fav)}
                  className="px-3 py-1 font-medium"
                >
                  {fav.name}
                </button>
                <button
                  type="button"
                  onClick={() => onRemoveFavorite(fav)}
                  aria-label={`Remover ${fav.name} dos favoritos`}
                  className="pr-2 text-slate-400 hover:text-rose-500"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
