export interface WeatherCondition {
  code: number;
  key: string;
  label_pt: string;
  icon: string;
}

export interface ProviderAttribution {
  provider: string;
  provider_label: string;
  license: string;
  url: string;
  fallback_used: boolean;
  air_quality_provider: string | null;
}

export interface CurrentWeather {
  time: string;
  is_day: boolean;
  temperature_c: number | null;
  apparent_temperature_c: number | null;
  dew_point_c: number | null;
  relative_humidity_percent: number | null;
  pressure_msl_hpa: number | null;
  surface_pressure_hpa: number | null;
  visibility_km: number | null;
  precipitation_probability_percent: number | null;
  precipitation_mm: number | null;
  rain_mm: number | null;
  showers_mm: number | null;
  cloud_cover_percent: number | null;
  wind_speed_kmh: number | null;
  wind_gusts_kmh: number | null;
  wind_direction_deg: number | null;
  wind_direction_cardinal: string | null;
  uv_index: number | null;
  condition: WeatherCondition;
}

export interface HourlyForecastItem {
  time: string;
  is_day: boolean;
  temperature_c: number | null;
  apparent_temperature_c: number | null;
  dew_point_c: number | null;
  relative_humidity_percent: number | null;
  pressure_msl_hpa: number | null;
  surface_pressure_hpa: number | null;
  visibility_km: number | null;
  precipitation_probability_percent: number | null;
  precipitation_mm: number | null;
  rain_mm: number | null;
  showers_mm: number | null;
  cloud_cover_percent: number | null;
  wind_speed_kmh: number | null;
  wind_gusts_kmh: number | null;
  wind_direction_deg: number | null;
  wind_direction_cardinal: string | null;
  uv_index: number | null;
  condition: WeatherCondition;
}

export interface DailyForecastItem {
  date: string;
  temperature_max_c: number | null;
  temperature_min_c: number | null;
  apparent_temperature_max_c: number | null;
  apparent_temperature_min_c: number | null;
  precipitation_probability_max_percent: number | null;
  precipitation_sum_mm: number | null;
  precipitation_hours: number | null;
  wind_speed_max_kmh: number | null;
  wind_gusts_max_kmh: number | null;
  wind_direction_dominant_deg: number | null;
  wind_direction_dominant_cardinal: string | null;
  uv_index_max: number | null;
  daylight_duration_hours: number | null;
  sunshine_duration_hours: number | null;
  sunrise: string | null;
  sunset: string | null;
  condition: WeatherCondition;
}

export interface AirQualityCurrent {
  time: string | null;
  european_aqi: number | null;
  us_aqi: number | null;
  category_pt: string | null;
  pm2_5: number | null;
  pm10: number | null;
  carbon_monoxide: number | null;
  nitrogen_dioxide: number | null;
  sulphur_dioxide: number | null;
  ozone: number | null;
  dust: number | null;
}

export interface WeatherForecastResponse {
  latitude: number;
  longitude: number;
  timezone: string;
  timezone_abbreviation: string;
  utc_offset_seconds: number;
  requested_days: number;
  available_days: number;
  generated_at: string;
  cached: boolean;
  current: CurrentWeather;
  hourly_72h: HourlyForecastItem[];
  hourly: HourlyForecastItem[];
  daily: DailyForecastItem[];
  air_quality: AirQualityCurrent | null;
  attribution: ProviderAttribution;
}

export interface LocationResult {
  id: number | null;
  name: string;
  display_name: string;
  admin1: string | null;
  country: string | null;
  country_code: string | null;
  latitude: number;
  longitude: number;
  timezone: string | null;
}

export interface GeocodingSearchResponse {
  query: string;
  cached: boolean;
  results: LocationResult[];
  attribution: ProviderAttribution;
}

export interface ReverseGeocodingResponse {
  cached: boolean;
  location: LocationResult;
  attribution: ProviderAttribution;
}

export type ScheduleType = "daily" | "weekly" | "once";
export type ForecastWindow = "today" | "tomorrow" | "next_3_days";

export interface PushSubscriptionPayload {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
}

export interface ReminderCreateRequest {
  label: string;
  location_name: string;
  latitude: number;
  longitude: number;
  timezone: string;
  schedule_type: ScheduleType;
  time_of_day: string;
  days_of_week: number[];
  once_date: string | null;
  forecast_window: ForecastWindow;
  min_rain_probability: number | null;
  subscription: PushSubscriptionPayload;
}

export interface ReminderUpdateRequest {
  label?: string;
  location_name?: string;
  latitude?: number;
  longitude?: number;
  timezone?: string;
  schedule_type?: ScheduleType;
  time_of_day?: string;
  days_of_week?: number[];
  once_date?: string | null;
  forecast_window?: ForecastWindow;
  min_rain_probability?: number | null;
  enabled?: boolean;
  subscription?: PushSubscriptionPayload;
}

export interface ReminderResponse {
  id: string;
  label: string;
  location_name: string;
  latitude: number;
  longitude: number;
  timezone: string;
  schedule_type: ScheduleType;
  time_of_day: string;
  days_of_week: number[];
  once_date: string | null;
  forecast_window: ForecastWindow;
  min_rain_probability: number | null;
  enabled: boolean;
  last_sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReminderCreateResponse {
  reminder: ReminderResponse;
  reminder_token: string;
}

export interface VapidPublicKeyResponse {
  configured: boolean;
  public_key: string | null;
}

export interface PushTestResponse {
  delivered: boolean;
  title: string;
  body: string;
}

export type TemperatureUnit = "c" | "f";
export type ThemeMode = "light" | "dark";

export interface SavedLocation {
  name: string;
  displayName: string;
  latitude: number;
  longitude: number;
  timezone: string;
}

export interface StoredReminderRef {
  id: string;
  token: string;
  cached?: ReminderResponse;
}

export interface CachedForecastSnapshot {
  savedAt: string;
  location: SavedLocation;
  forecast: WeatherForecastResponse;
}
