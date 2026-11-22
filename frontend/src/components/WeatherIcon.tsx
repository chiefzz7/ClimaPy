import {
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudLightning,
  CloudMoon,
  CloudRain,
  CloudSnow,
  CloudSun,
  Moon,
  Sun,
} from "lucide-react";

interface WeatherIconProps {
  icon: string;
  className?: string;
}

export function WeatherIcon({ icon, className = "h-6 w-6" }: WeatherIconProps) {
  switch (icon) {
    case "sun":
      return <Sun className={`${className} text-amber-400`} aria-hidden="true" />;
    case "moon":
      return <Moon className={`${className} text-indigo-300`} aria-hidden="true" />;
    case "sun-cloud":
    case "cloud-sun":
      return <CloudSun className={`${className} text-amber-400`} aria-hidden="true" />;
    case "moon-cloud":
    case "cloud-moon":
      return <CloudMoon className={`${className} text-indigo-300`} aria-hidden="true" />;
    case "fog":
      return <CloudFog className={`${className} text-slate-400`} aria-hidden="true" />;
    case "drizzle":
      return <CloudDrizzle className={`${className} text-sky-400`} aria-hidden="true" />;
    case "rain-light":
    case "rain":
    case "rain-heavy":
      return <CloudRain className={`${className} text-sky-500`} aria-hidden="true" />;
    case "sleet":
    case "snow":
      return <CloudSnow className={`${className} text-cyan-300`} aria-hidden="true" />;
    case "thunderstorm":
      return <CloudLightning className={`${className} text-amber-300`} aria-hidden="true" />;
    default:
      return <Cloud className={`${className} text-slate-400`} aria-hidden="true" />;
  }
}
