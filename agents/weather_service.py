"""
agents/weather_service.py — Real-time weather data via Open-Meteo API.
Free, no API key required. Fetches current conditions for any location.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import Optional


# Location → (lat, lon) lookup
LOCATION_COORDS: dict[str, tuple[float, float]] = {
    "hyderabad":    (17.38, 78.47),
    "mumbai":       (19.07, 72.87),
    "chennai":      (13.08, 80.27),
    "delhi":        (28.61, 77.21),
    "kolkata":      (22.57, 88.36),
    "bangalore":    (12.97, 77.59),
    "ahmedabad":    (23.02, 72.57),
    "pune":         (18.52, 73.86),
    "jaipur":       (26.91, 75.79),
    "lucknow":      (26.85, 80.95),
    "bhopal":       (23.26, 77.41),
    "patna":        (25.59, 85.14),
    "bhubaneswar":  (20.30, 85.82),
    "guwahati":     (26.18, 91.74),
    "tokyo":        (35.68, 139.69),
    "london":       (51.51, -0.13),
    "new york":     (40.71, -74.01),
    "los angeles":  (34.05, -118.24),
    "sydney":       (-33.87, 151.21),
    "jakarta":      (-6.21, 106.85),
    "manila":       (14.60, 120.98),
    "dhaka":        (23.81, 90.41),
    "karachi":      (24.86, 67.01),
    "kathmandu":    (27.70, 85.32),
    "colombo":      (6.93, 79.85),
}


@dataclass
class WeatherData:
    location: str
    lat: float
    lon: float
    temperature_c: float
    rainfall_mm: float          # last hour
    wind_speed_kmh: float
    wind_direction_deg: float
    humidity_pct: float
    cloud_cover_pct: float
    visibility_km: float
    weather_code: int
    weather_description: str
    is_day: bool
    data_source: str = "Open-Meteo (live)"

    def to_context_string(self) -> str:
        return (
            f"Temperature: {self.temperature_c:.1f}°C | "
            f"Rainfall: {self.rainfall_mm:.1f}mm/hr | "
            f"Wind: {self.wind_speed_kmh:.0f}km/h | "
            f"Humidity: {self.humidity_pct:.0f}% | "
            f"Cloud cover: {self.cloud_cover_pct:.0f}% | "
            f"Visibility: {self.visibility_km:.1f}km | "
            f"Conditions: {self.weather_description}"
        )


# WMO weather code → description
WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


def get_coords(location: str) -> Optional[tuple[float, float]]:
    """Get coordinates for a location name."""
    key = location.lower().strip().split(",")[0].strip()
    if key in LOCATION_COORDS:
        return LOCATION_COORDS[key]
    # Try partial match
    for k, v in LOCATION_COORDS.items():
        if k in key or key in k:
            return v
    return None


def fetch_weather(location: str) -> Optional[WeatherData]:
    """
    Fetch real-time weather from Open-Meteo API.
    Returns None if location unknown or network unavailable.
    """
    coords = get_coords(location)
    if not coords:
        return None

    lat, lon = coords
    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "rain",
            "weather_code",
            "cloud_cover",
            "wind_speed_10m",
            "wind_direction_10m",
            "visibility",
            "is_day",
        ]),
        "wind_speed_unit": "kmh",
        "timezone": "auto",
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DisasterResponseAI/2.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        cur = data.get("current", {})
        code = cur.get("weather_code", 0)
        vis_m = cur.get("visibility", 10000)

        return WeatherData(
            location=location,
            lat=lat,
            lon=lon,
            temperature_c=cur.get("temperature_2m", 25.0),
            rainfall_mm=cur.get("rain", 0.0),
            wind_speed_kmh=cur.get("wind_speed_10m", 0.0),
            wind_direction_deg=cur.get("wind_direction_10m", 0.0),
            humidity_pct=cur.get("relative_humidity_2m", 60.0),
            cloud_cover_pct=cur.get("cloud_cover", 0.0),
            visibility_km=vis_m / 1000.0,
            weather_code=code,
            weather_description=WMO_CODES.get(code, f"Code {code}"),
            is_day=bool(cur.get("is_day", 1)),
        )
    except Exception as exc:
        print(f"  [Weather] Could not fetch weather for {location}: {exc.__class__.__name__}")
        return None
