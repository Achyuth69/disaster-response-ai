"""
agents/disaster_spread.py — Disaster Spread Simulation Engine.

Simulates how a disaster physically spreads over time:
- Flood: water rising based on rainfall, elevation, drainage
- Earthquake: aftershock probability zones (Omori's law)
- Cyclone: track prediction + wind radius expansion
- Wildfire: fire spread based on wind + fuel + terrain
- Tsunami: wave propagation from epicenter

Generates time-series frames for map animation.
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SpreadFrame:
    time_minutes: float
    zones: list[dict]   # [{lat, lon, radius_m, intensity, color, label}]
    event_description: str


def simulate_spread(
    disaster_type: str,
    center_lat: float,
    center_lon: float,
    severity: int,
    rainfall_mm_hr: float = 0.0,
    wind_speed_kmh: float = 20.0,
    wind_direction_deg: float = 180.0,
    num_frames: int = 8,
    frame_interval_min: float = 30.0,
) -> list[SpreadFrame]:
    """Generate spread simulation frames for map animation."""
    frames = []
    sev = severity / 10.0

    for i in range(num_frames):
        t = (i + 1) * frame_interval_min
        zones = []

        if disaster_type == "flood":
            frames.append(_flood_frame(center_lat, center_lon, t, sev, rainfall_mm_hr))

        elif disaster_type == "earthquake":
            frames.append(_earthquake_frame(center_lat, center_lon, t, sev))

        elif disaster_type == "cyclone":
            frames.append(_cyclone_frame(center_lat, center_lon, t, sev, wind_speed_kmh, wind_direction_deg))

        elif disaster_type == "wildfire":
            frames.append(_wildfire_frame(center_lat, center_lon, t, sev, wind_speed_kmh, wind_direction_deg))

        elif disaster_type == "tsunami":
            frames.append(_tsunami_frame(center_lat, center_lon, t, sev))

        else:
            frames.append(_generic_frame(center_lat, center_lon, t, sev, disaster_type))

    return frames


def _flood_frame(lat, lon, t_min, sev, rainfall_mm_hr) -> SpreadFrame:
    """Flood spreads outward from low-elevation areas."""
    zones = []
    # Core flood zone (deepest water)
    core_radius = 500 + (t_min / 60) * 800 * sev * (1 + rainfall_mm_hr / 50)
    zones.append({"lat": lat, "lon": lon, "radius_m": core_radius,
                  "intensity": min(1.0, sev * 1.2), "color": "#0044ff",
                  "label": f"Flood depth ~{(t_min/60*sev*0.8):.1f}m"})
    # Secondary spread zones
    for angle_deg in [0, 90, 180, 270]:
        angle = math.radians(angle_deg)
        spread = 0.003 * (t_min / 60) * sev
        z_lat = lat + math.cos(angle) * spread
        z_lon = lon + math.sin(angle) * spread
        zones.append({"lat": z_lat, "lon": z_lon,
                      "radius_m": core_radius * 0.6,
                      "intensity": sev * 0.7, "color": "#0066cc",
                      "label": f"Spreading flood"})
    return SpreadFrame(
        time_minutes=t_min,
        zones=zones,
        event_description=f"T+{t_min:.0f}min: Flood radius ~{core_radius/1000:.1f}km, depth ~{t_min/60*sev*0.8:.1f}m"
    )


def _earthquake_frame(lat, lon, t_min, sev) -> SpreadFrame:
    """Earthquake: aftershock probability zones using Omori's law."""
    # Omori's law: aftershock rate ∝ 1/(t + c)
    c = 0.1
    aftershock_prob = sev / (t_min / 60 + c)
    zones = []
    # Primary damage zone
    zones.append({"lat": lat, "lon": lon,
                  "radius_m": 2000 + sev * 3000,
                  "intensity": sev, "color": "#ff4400",
                  "label": f"Primary damage zone"})
    # Aftershock probability ring
    zones.append({"lat": lat, "lon": lon,
                  "radius_m": 5000 + sev * 8000,
                  "intensity": min(1.0, aftershock_prob),
                  "color": "#ff8800",
                  "label": f"Aftershock zone ({aftershock_prob*100:.0f}% prob)"})
    # Liquefaction risk
    if sev > 0.6:
        zones.append({"lat": lat - 0.02, "lon": lon + 0.03,
                      "radius_m": 1500, "intensity": 0.8,
                      "color": "#cc6600",
                      "label": "Liquefaction risk"})
    return SpreadFrame(
        time_minutes=t_min,
        zones=zones,
        event_description=f"T+{t_min:.0f}min: Aftershock probability {aftershock_prob*100:.0f}% (Omori's law)"
    )


def _cyclone_frame(lat, lon, t_min, sev, wind_kmh, wind_dir_deg) -> SpreadFrame:
    """Cyclone: track movement + expanding wind radius."""
    # Cyclone moves in wind direction
    speed_kmh = 15 + sev * 10
    dist_km = speed_kmh * (t_min / 60)
    angle = math.radians(wind_dir_deg)
    new_lat = lat + math.cos(angle) * (dist_km / 111)
    new_lon = lon + math.sin(angle) * (dist_km / (111 * math.cos(math.radians(lat))))

    eye_radius = 20000 + sev * 15000
    zones = [
        {"lat": new_lat, "lon": new_lon, "radius_m": 5000,
         "intensity": 1.0, "color": "#ffffff", "label": "Eye (calm)"},
        {"lat": new_lat, "lon": new_lon, "radius_m": eye_radius * 0.4,
         "intensity": 1.0, "color": "#ff2020", "label": f"Eyewall — {wind_kmh:.0f}km/h winds"},
        {"lat": new_lat, "lon": new_lon, "radius_m": eye_radius,
         "intensity": 0.6, "color": "#ff6600", "label": "Outer rain bands"},
        {"lat": new_lat, "lon": new_lon, "radius_m": eye_radius * 1.8,
         "intensity": 0.3, "color": "#ffcc00", "label": "Storm surge risk zone"},
    ]
    return SpreadFrame(
        time_minutes=t_min,
        zones=zones,
        event_description=f"T+{t_min:.0f}min: Cyclone moved {dist_km:.0f}km, eye at {new_lat:.3f}°N {new_lon:.3f}°E"
    )


def _wildfire_frame(lat, lon, t_min, sev, wind_kmh, wind_dir_deg) -> SpreadFrame:
    """Wildfire: spreads faster in wind direction."""
    angle = math.radians(wind_dir_deg)
    # Fire spreads faster downwind
    downwind_dist = 0.001 * (t_min / 60) * wind_kmh * sev
    crosswind_dist = downwind_dist * 0.3
    zones = [
        {"lat": lat, "lon": lon, "radius_m": 500 + sev * 300,
         "intensity": 1.0, "color": "#ff2020", "label": "Active fire core"},
        {"lat": lat + math.cos(angle) * downwind_dist,
         "lon": lon + math.sin(angle) * downwind_dist,
         "radius_m": 800 + sev * 500, "intensity": 0.9,
         "color": "#ff4400", "label": f"Fire front (downwind)"},
        {"lat": lat, "lon": lon,
         "radius_m": 2000 + sev * 1000 + t_min * 20,
         "intensity": 0.4, "color": "#ff8800", "label": "Smoke/ember zone"},
    ]
    return SpreadFrame(
        time_minutes=t_min,
        zones=zones,
        event_description=f"T+{t_min:.0f}min: Fire spread {downwind_dist*111:.1f}km downwind at {wind_kmh:.0f}km/h"
    )


def _tsunami_frame(lat, lon, t_min, sev) -> SpreadFrame:
    """Tsunami: wave propagates at ~800km/h in deep water."""
    wave_speed_kmh = 800 * (1 - sev * 0.3)  # slower in shallow water
    dist_km = wave_speed_kmh * (t_min / 60)
    zones = [
        {"lat": lat, "lon": lon, "radius_m": dist_km * 1000,
         "intensity": max(0.1, sev - t_min / 600),
         "color": "#0088ff", "label": f"Wave front — {dist_km:.0f}km from epicenter"},
        {"lat": lat, "lon": lon, "radius_m": dist_km * 1000 * 0.7,
         "intensity": sev * 0.8, "color": "#0044cc",
         "label": "Inundation risk zone"},
    ]
    return SpreadFrame(
        time_minutes=t_min,
        zones=zones,
        event_description=f"T+{t_min:.0f}min: Tsunami wave {dist_km:.0f}km from epicenter at {wave_speed_kmh:.0f}km/h"
    )


def _generic_frame(lat, lon, t_min, sev, disaster_type) -> SpreadFrame:
    radius = 1000 + sev * 2000 + t_min * 50
    return SpreadFrame(
        time_minutes=t_min,
        zones=[{"lat": lat, "lon": lon, "radius_m": radius,
                "intensity": sev, "color": "#ff6600",
                "label": f"{disaster_type} impact zone"}],
        event_description=f"T+{t_min:.0f}min: {disaster_type} impact radius {radius/1000:.1f}km"
    )
