"""
agents/crowd_density.py — Real-time crowd density & crush risk prediction.
Simulates mobile signal density patterns to detect dangerous crowd concentrations.
World-first: predicts crowd crush events before they happen during disasters.
"""
from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CrowdZone:
    zone_id: str
    zone_name: str
    lat: float
    lon: float
    estimated_crowd: int
    area_sqm: float             # area in square meters
    density_per_sqm: float      # people per square meter
    crush_risk: str             # "EXTREME" | "HIGH" | "MODERATE" | "LOW" | "SAFE"
    crush_risk_score: float     # 0.0 - 1.0
    flow_direction: str         # "CONVERGING" | "DISPERSING" | "STATIC" | "CHAOTIC"
    bottlenecks: list[str]
    recommended_action: str
    color: str
    signal_strength: float      # simulated mobile signal density (proxy for crowd)
    evacuation_routes_open: int
    estimated_crush_minutes: Optional[float]  # None if no crush risk


def compute_crowd_density(
    location: str,
    disaster_type: str,
    severity: int,
    zones: list[dict],
    time_elapsed_hours: float,
) -> dict:
    """
    Compute crowd density and crush risk for all zones.
    Uses simulated mobile signal density as proxy for real crowd data.
    """
    # Crowd behavior multipliers by disaster type
    PANIC_FACTOR = {
        "flood": 1.8,
        "earthquake": 2.5,
        "cyclone": 2.0,
        "tsunami": 3.0,
        "wildfire": 2.2,
        "landslide": 1.6,
    }.get(disaster_type, 1.8)

    # Evacuation convergence points (where crowds gather)
    CONVERGENCE_POINTS = {
        "hyderabad": [
            ("Secunderabad Railway Station", 17.434, 78.500, 8500),
            ("Hyderabad Airport Road", 17.240, 78.429, 6200),
            ("Charminar Area", 17.361, 78.474, 12000),
            ("Hitech City Junction", 17.447, 78.376, 7800),
            ("LB Nagar Bus Stand", 17.346, 78.554, 9500),
            ("Dilsukhnagar Metro", 17.369, 78.526, 11000),
            ("Ameerpet Junction", 17.435, 78.449, 8900),
        ],
        "mumbai": [
            ("CST Station", 18.940, 72.835, 15000),
            ("Dadar Junction", 19.018, 72.843, 12000),
            ("Bandra Station", 19.054, 72.840, 9000),
        ],
        "chennai": [
            ("Chennai Central", 13.083, 80.275, 11000),
            ("Koyambedu Bus Stand", 13.069, 80.194, 8500),
        ],
    }

    loc_key = location.lower().split(",")[0].strip()
    convergence = CONVERGENCE_POINTS.get(loc_key, [
        (f"{location} Main Junction", 0.0, 0.0, 8000),
        (f"{location} Bus Terminal", 0.0, 0.0, 6000),
    ])

    # Get base coords
    BASE_COORDS = {
        "hyderabad": (17.38, 78.47), "mumbai": (19.07, 72.87),
        "chennai": (13.08, 80.27), "delhi": (28.61, 77.21),
    }
    base = BASE_COORDS.get(loc_key, (17.38, 78.47))

    crowd_zones = []
    total_at_risk = 0

    for i, (name, lat, lon, base_crowd) in enumerate(convergence):
        if lat == 0.0:
            # Generate offset from base
            angle = (i / len(convergence)) * 2 * math.pi
            lat = base[0] + math.sin(angle) * 0.05
            lon = base[1] + math.cos(angle) * 0.05

        # Simulate crowd growth based on time elapsed and panic
        time_factor = min(3.0, 1.0 + time_elapsed_hours * 0.8)
        severity_factor = 1.0 + (severity - 5) * 0.15
        crowd = int(base_crowd * PANIC_FACTOR * time_factor * severity_factor)

        # Area of the convergence point (sq meters)
        area = random.uniform(2000, 8000)
        density = crowd / area

        # Crush risk thresholds (based on real crowd safety research):
        # > 4 people/sqm = extreme crush risk
        # > 2.5 = high risk
        # > 1.5 = moderate
        # > 0.8 = low
        if density > 4.0:
            crush_risk = "EXTREME"
            crush_score = min(1.0, density / 5.0)
            color = "#ff0000"
            action = f"IMMEDIATE EVACUATION — crowd crush imminent at {name}"
            crush_min = max(1.0, (5.0 - density) * 8)
        elif density > 2.5:
            crush_risk = "HIGH"
            crush_score = density / 5.0
            color = "#ff4400"
            action = f"Deploy crowd control to {name} — open additional exit routes"
            crush_min = max(5.0, (5.0 - density) * 15)
        elif density > 1.5:
            crush_risk = "MODERATE"
            crush_score = density / 5.0
            color = "#ff8800"
            action = f"Monitor {name} — prepare crowd dispersal teams"
            crush_min = None
        elif density > 0.8:
            crush_risk = "LOW"
            crush_score = density / 5.0
            color = "#ffcc00"
            action = f"Normal monitoring at {name}"
            crush_min = None
        else:
            crush_risk = "SAFE"
            crush_score = density / 5.0
            color = "#00ff88"
            action = "No action required"
            crush_min = None

        # Flow direction based on time and disaster phase
        if time_elapsed_hours < 1.0:
            flow = "CONVERGING"  # early phase: people rushing to safety points
        elif time_elapsed_hours < 3.0:
            flow = "CHAOTIC" if severity > 7 else "CONVERGING"
        else:
            flow = "DISPERSING"  # later phase: evacuation underway

        # Bottlenecks
        bottlenecks = []
        if density > 2.0:
            bottlenecks.append("Main entrance/exit too narrow")
        if density > 3.0:
            bottlenecks.append("Secondary exits blocked by crowd")
        if disaster_type == "flood" and density > 1.5:
            bottlenecks.append("Water on approach roads reducing exit capacity")

        # Signal strength (proxy for crowd density — more people = stronger aggregate signal)
        signal = min(1.0, density / 4.0 + random.uniform(-0.05, 0.05))

        # Open evacuation routes (decreases as crowd grows)
        open_routes = max(1, 4 - int(density))

        zone = CrowdZone(
            zone_id=f"crowd_{i}",
            zone_name=name,
            lat=lat, lon=lon,
            estimated_crowd=crowd,
            area_sqm=area,
            density_per_sqm=round(density, 2),
            crush_risk=crush_risk,
            crush_risk_score=round(crush_score, 3),
            flow_direction=flow,
            bottlenecks=bottlenecks,
            recommended_action=action,
            color=color,
            signal_strength=round(signal, 3),
            evacuation_routes_open=open_routes,
            estimated_crush_minutes=round(crush_min, 1) if crush_min else None,
        )
        crowd_zones.append(zone)
        if crush_risk in ("EXTREME", "HIGH"):
            total_at_risk += crowd

    # Sort by crush risk
    risk_order = {"EXTREME": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3, "SAFE": 4}
    crowd_zones.sort(key=lambda z: risk_order.get(z.crush_risk, 5))

    extreme_count = sum(1 for z in crowd_zones if z.crush_risk == "EXTREME")
    high_count = sum(1 for z in crowd_zones if z.crush_risk == "HIGH")

    return {
        "location": location,
        "disaster_type": disaster_type,
        "computed_at": datetime.utcnow().isoformat(),
        "time_elapsed_hours": time_elapsed_hours,
        "panic_factor": PANIC_FACTOR,
        "summary": {
            "total_zones_monitored": len(crowd_zones),
            "extreme_risk_zones": extreme_count,
            "high_risk_zones": high_count,
            "total_people_at_crush_risk": total_at_risk,
            "overall_risk": "EXTREME" if extreme_count > 0 else "HIGH" if high_count > 0 else "MODERATE",
        },
        "zones": [
            {
                "zone_id": z.zone_id,
                "zone_name": z.zone_name,
                "lat": z.lat, "lon": z.lon,
                "estimated_crowd": z.estimated_crowd,
                "density_per_sqm": z.density_per_sqm,
                "crush_risk": z.crush_risk,
                "crush_risk_score": z.crush_risk_score,
                "flow_direction": z.flow_direction,
                "bottlenecks": z.bottlenecks,
                "recommended_action": z.recommended_action,
                "color": z.color,
                "signal_strength": z.signal_strength,
                "evacuation_routes_open": z.evacuation_routes_open,
                "estimated_crush_minutes": z.estimated_crush_minutes,
            }
            for z in crowd_zones
        ],
        "critical_alert": extreme_count > 0,
        "alert_message": (
            f"🚨 CROWD CRUSH IMMINENT: {extreme_count} location(s) at EXTREME density. "
            f"Deploy crowd control immediately." if extreme_count > 0 else None
        ),
    }
