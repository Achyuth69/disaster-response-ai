"""
agents/satellite_intel.py — Satellite imagery change detection simulation.
Simulates before/after flood extent analysis using elevation + rainfall models.
World-first: real-time satellite change detection integrated into disaster response.
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class SatelliteFrame:
    timestamp: str
    hours_after_event: float
    flood_extent_sqkm: float
    flood_depth_avg_m: float
    affected_structures: int
    submerged_roads_km: float
    change_from_previous_pct: float     # % change from last frame
    color_intensity: float              # 0.0 - 1.0 for visualization
    alert_level: str
    key_changes: list[str]


@dataclass
class SatelliteZone:
    zone_name: str
    lat: float
    lon: float
    before_ndwi: float      # Normalized Difference Water Index before
    after_ndwi: float       # NDWI after (higher = more water)
    change_magnitude: float
    flood_probability: float
    area_flooded_sqkm: float
    structures_at_risk: int
    change_type: str        # "NEW_FLOOD" | "EXPANDING" | "RECEDING" | "STABLE"
    color: str


def run_satellite_analysis(
    location: str,
    disaster_type: str,
    severity: int,
    time_elapsed_hours: float,
    rainfall_mm_hr: float = 0.0,
) -> dict:
    """
    Simulate satellite change detection analysis.
    Returns before/after comparison, flood extent progression, and change detection.
    """
    # Base coordinates
    BASE_COORDS = {
        "hyderabad": (17.38, 78.47),
        "mumbai": (19.07, 72.87),
        "chennai": (13.08, 80.27),
        "delhi": (28.61, 77.21),
        "kolkata": (22.57, 88.36),
    }
    loc_key = location.lower().split(",")[0].strip()
    base = BASE_COORDS.get(loc_key, (17.38, 78.47))

    # Flood progression model
    severity_factor = severity / 10.0
    rain_factor = min(2.0, rainfall_mm_hr / 50.0) if rainfall_mm_hr > 0 else 1.0

    # Generate temporal frames (satellite passes every ~90 min)
    frames = []
    base_extent = 2.5 * severity_factor
    prev_extent = 0.0

    for i, hours in enumerate([0, 1.5, 3.0, 6.0, 12.0, 24.0]):
        if hours > time_elapsed_hours + 6:
            break
        # Flood extent grows then stabilizes
        if hours <= time_elapsed_hours:
            growth = min(1.0, hours / max(1, time_elapsed_hours))
            extent = base_extent * (1 + growth * severity_factor * rain_factor)
        else:
            extent = base_extent * (1 + severity_factor * rain_factor)

        depth = min(4.0, 0.3 + extent * 0.15 * severity_factor)
        structures = int(extent * 850 * severity_factor)
        roads = extent * 12 * severity_factor
        change_pct = ((extent - prev_extent) / max(0.1, prev_extent)) * 100 if prev_extent > 0 else 0

        if extent > base_extent * 1.5:
            alert = "CRITICAL"
        elif extent > base_extent * 1.2:
            alert = "HIGH"
        elif extent > base_extent:
            alert = "MODERATE"
        else:
            alert = "LOW"

        key_changes = []
        if i == 0:
            key_changes.append("Initial flood extent mapped")
        if change_pct > 20:
            key_changes.append(f"Rapid expansion: +{change_pct:.0f}% from previous pass")
        if depth > 2.0:
            key_changes.append(f"Deep flooding detected: avg {depth:.1f}m")
        if structures > 1000:
            key_changes.append(f"{structures:,} structures submerged")
        if roads > 20:
            key_changes.append(f"{roads:.0f}km of roads inundated")

        frame = SatelliteFrame(
            timestamp=(datetime.utcnow() - timedelta(hours=time_elapsed_hours - hours)).isoformat()[:16],
            hours_after_event=hours,
            flood_extent_sqkm=round(extent, 2),
            flood_depth_avg_m=round(depth, 2),
            affected_structures=structures,
            submerged_roads_km=round(roads, 1),
            change_from_previous_pct=round(change_pct, 1),
            color_intensity=min(1.0, extent / (base_extent * 2)),
            alert_level=alert,
            key_changes=key_changes,
        )
        frames.append(frame)
        prev_extent = extent

    # Zone-level change detection
    ZONE_DATA = {
        "hyderabad": [
            ("Musi River Corridor", base[0]-.02, base[1]+.02, 0.12, 0.78),
            ("Dilsukhnagar", base[0]-.08, base[1]+.12, 0.08, 0.65),
            ("LB Nagar", base[0]-.12, base[1]+.15, 0.10, 0.72),
            ("Mehdipatnam", base[0]-.04, base[1]-.08, 0.06, 0.45),
            ("Uppal", base[0]+.02, base[1]+.22, 0.09, 0.58),
            ("Kukatpally", base[0]+.08, base[1]-.12, 0.05, 0.32),
            ("Secunderabad", base[0]+.06, base[1]+.04, 0.04, 0.28),
        ]
    }

    zone_data = ZONE_DATA.get(loc_key, [
        (f"{location} Low Zone", base[0]-.05, base[1]+.05, 0.10, 0.70),
        (f"{location} Mid Zone", base[0]+.05, base[1]-.05, 0.07, 0.50),
        (f"{location} High Zone", base[0]-.05, base[1]-.05, 0.04, 0.25),
    ])

    sat_zones = []
    for name, lat, lon, before_ndwi, after_ndwi_base in zone_data:
        after_ndwi = min(0.95, after_ndwi_base * (1 + severity_factor * rain_factor))
        change = after_ndwi - before_ndwi
        flood_prob = min(1.0, change * 3.5)
        area = change * 15 * severity_factor
        structures = int(area * 600)

        if change > 0.4:
            change_type = "NEW_FLOOD"
            color = "#0044ff"
        elif change > 0.25:
            change_type = "EXPANDING"
            color = "#0088ff"
        elif change > 0.1:
            change_type = "STABLE"
            color = "#00ccff"
        else:
            change_type = "RECEDING"
            color = "#00ff88"

        sat_zones.append(SatelliteZone(
            zone_name=name, lat=lat, lon=lon,
            before_ndwi=round(before_ndwi, 3),
            after_ndwi=round(after_ndwi, 3),
            change_magnitude=round(change, 3),
            flood_probability=round(flood_prob, 3),
            area_flooded_sqkm=round(area, 2),
            structures_at_risk=structures,
            change_type=change_type,
            color=color,
        ))

    sat_zones.sort(key=lambda z: z.change_magnitude, reverse=True)

    latest = frames[-1] if frames else None
    total_flooded = sum(z.area_flooded_sqkm for z in sat_zones)
    total_structures = sum(z.structures_at_risk for z in sat_zones)

    return {
        "location": location,
        "disaster_type": disaster_type,
        "computed_at": datetime.utcnow().isoformat(),
        "satellite_source": "Sentinel-1 SAR / Landsat-8 (simulated)",
        "analysis_type": "NDWI Change Detection + SAR Backscatter",
        "summary": {
            "total_frames_analyzed": len(frames),
            "total_flooded_area_sqkm": round(total_flooded, 2),
            "total_structures_at_risk": total_structures,
            "max_flood_depth_m": latest.flood_depth_avg_m if latest else 0,
            "submerged_roads_km": latest.submerged_roads_km if latest else 0,
            "current_alert": latest.alert_level if latest else "UNKNOWN",
            "flood_expanding": (frames[-1].change_from_previous_pct > 5) if len(frames) > 1 else False,
        },
        "temporal_frames": [
            {
                "timestamp": f.timestamp,
                "hours_after_event": f.hours_after_event,
                "flood_extent_sqkm": f.flood_extent_sqkm,
                "flood_depth_avg_m": f.flood_depth_avg_m,
                "affected_structures": f.affected_structures,
                "submerged_roads_km": f.submerged_roads_km,
                "change_pct": f.change_from_previous_pct,
                "color_intensity": f.color_intensity,
                "alert_level": f.alert_level,
                "key_changes": f.key_changes,
                "color": (
                    "#ff0000" if f.alert_level == "CRITICAL" else
                    "#ff6600" if f.alert_level == "HIGH" else
                    "#ffcc00" if f.alert_level == "MODERATE" else "#00ff88"
                ),
            }
            for f in frames
        ],
        "zone_analysis": [
            {
                "zone_name": z.zone_name,
                "lat": z.lat, "lon": z.lon,
                "before_ndwi": z.before_ndwi,
                "after_ndwi": z.after_ndwi,
                "change_magnitude": z.change_magnitude,
                "flood_probability_pct": round(z.flood_probability * 100, 1),
                "area_flooded_sqkm": z.area_flooded_sqkm,
                "structures_at_risk": z.structures_at_risk,
                "change_type": z.change_type,
                "color": z.color,
            }
            for z in sat_zones
        ],
        "ndwi_legend": {
            "description": "NDWI > 0.3 = water present, change > 0.2 = new flooding",
            "before_avg": round(sum(z.before_ndwi for z in sat_zones) / max(1, len(sat_zones)), 3),
            "after_avg": round(sum(z.after_ndwi for z in sat_zones) / max(1, len(sat_zones)), 3),
        },
    }
