"""
agents/evacuation_calculator.py — Evacuation Capacity Calculator.

Calculates how many people can be evacuated per hour through
each route given current road conditions, vehicle capacity,
and population density.

Also identifies bottlenecks and optimal staging points.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass
class EvacuationRoute:
    route_id: str
    name: str
    from_zone: str
    to_shelter: str
    distance_km: float
    road_capacity_vehicles_hr: int
    current_capacity_pct: float   # 0-1 (1 = fully open, 0 = blocked)
    vehicle_types: list[str]
    people_per_vehicle: int
    throughput_people_hr: int
    time_to_evacuate_zone_hr: float
    bottleneck: str
    lat_start: float = 0.0
    lon_start: float = 0.0
    lat_end: float = 0.0
    lon_end: float = 0.0


@dataclass
class EvacuationPlan:
    total_to_evacuate: int
    total_throughput_hr: int
    estimated_hours_to_complete: float
    routes: list[EvacuationRoute]
    staging_points: list[dict]
    bottlenecks: list[str]
    priority_order: list[str]


# Hyderabad evacuation routes (real roads)
HYDERABAD_ROUTES = [
    {
        "route_id": "R001", "name": "NH-44 Northbound",
        "from_zone": "Dilsukhnagar/LB Nagar", "to_shelter": "Secunderabad Parade Ground",
        "distance_km": 18.5, "base_capacity": 1200,
        "vehicle_types": ["Bus", "Truck", "Car"],
        "lat_start": 17.37, "lon_start": 78.53,
        "lat_end": 17.44, "lon_end": 78.50,
    },
    {
        "route_id": "R002", "name": "Outer Ring Road (ORR) Westbound",
        "from_zone": "Mehdipatnam/Tolichowki", "to_shelter": "BHEL Township Ground",
        "distance_km": 22.0, "base_capacity": 1800,
        "vehicle_types": ["Bus", "Car", "Motorcycle"],
        "lat_start": 17.39, "lon_start": 78.43,
        "lat_end": 17.52, "lon_end": 78.32,
    },
    {
        "route_id": "R003", "name": "NH-65 Southbound",
        "from_zone": "Uppal/Boduppal", "to_shelter": "Shamshabad Airport Relief Zone",
        "distance_km": 35.0, "base_capacity": 900,
        "vehicle_types": ["Bus", "Truck"],
        "lat_start": 17.40, "lon_start": 78.56,
        "lat_end": 17.24, "lon_end": 78.43,
    },
    {
        "route_id": "R004", "name": "Inner Ring Road (IRR) Northbound",
        "from_zone": "Amberpet/Tarnaka", "to_shelter": "Kukatpally Stadium",
        "distance_km": 14.0, "base_capacity": 600,
        "vehicle_types": ["Bus", "Car"],
        "lat_start": 17.41, "lon_start": 78.51,
        "lat_end": 17.49, "lon_end": 78.41,
    },
    {
        "route_id": "R005", "name": "Metro Rail Corridor (Pedestrian)",
        "from_zone": "Khairatabad/Masab Tank", "to_shelter": "Banjara Hills Community Hall",
        "distance_km": 5.0, "base_capacity": 3000,
        "vehicle_types": ["Foot", "Metro"],
        "lat_start": 17.42, "lon_start": 78.46,
        "lat_end": 17.43, "lon_end": 78.41,
    },
]


def calculate_evacuation(
    zones: list[dict],
    disaster_type: str,
    severity: int,
    blocked_roads: list[str],
    available_buses: int = 50,
    available_trucks: int = 20,
    base_lat: float = 17.38,
    base_lon: float = 78.47,
) -> EvacuationPlan:
    """Calculate evacuation capacity and optimal routing."""
    sev = severity / 10.0
    total_pop = sum(z.get("population_at_risk", 0) for z in zones)

    routes = []
    total_throughput = 0
    bottlenecks = []

    for r_data in HYDERABAD_ROUTES:
        # Check if route is blocked
        is_blocked = any(b.lower() in r_data["name"].lower() for b in blocked_roads)
        capacity_pct = 0.1 if is_blocked else max(0.3, 1.0 - sev * 0.4)

        # Vehicle capacity
        people_per_vehicle = 40 if "Bus" in r_data["vehicle_types"] else 15
        effective_capacity = int(r_data["base_capacity"] * capacity_pct)
        throughput = effective_capacity * people_per_vehicle

        # Time to evacuate
        zone_pop = total_pop // len(HYDERABAD_ROUTES)
        time_hr = zone_pop / max(1, throughput)

        bottleneck = ""
        if capacity_pct < 0.4:
            bottleneck = f"Road damage — {int(capacity_pct*100)}% capacity"
            bottlenecks.append(f"{r_data['name']}: {bottleneck}")
        elif effective_capacity < 300:
            bottleneck = "Insufficient vehicles"
            bottlenecks.append(f"{r_data['name']}: {bottleneck}")

        routes.append(EvacuationRoute(
            route_id=r_data["route_id"],
            name=r_data["name"],
            from_zone=r_data["from_zone"],
            to_shelter=r_data["to_shelter"],
            distance_km=r_data["distance_km"],
            road_capacity_vehicles_hr=r_data["base_capacity"],
            current_capacity_pct=round(capacity_pct, 2),
            vehicle_types=r_data["vehicle_types"],
            people_per_vehicle=people_per_vehicle,
            throughput_people_hr=throughput,
            time_to_evacuate_zone_hr=round(time_hr, 1),
            bottleneck=bottleneck,
            lat_start=r_data["lat_start"], lon_start=r_data["lon_start"],
            lat_end=r_data["lat_end"], lon_end=r_data["lon_end"],
        ))
        total_throughput += throughput

    # Staging points
    staging = [
        {"name": "Secunderabad Parade Ground", "capacity": 10000,
         "lat": 17.44, "lon": 78.50, "status": "ACTIVE"},
        {"name": "Kukatpally Stadium", "capacity": 5000,
         "lat": 17.49, "lon": 78.41, "status": "ACTIVE"},
        {"name": "BHEL Township Ground", "capacity": 6000,
         "lat": 17.52, "lon": 78.32, "status": "ACTIVE"},
        {"name": "Shamshabad Airport Zone", "capacity": 15000,
         "lat": 17.24, "lon": 78.43, "status": "STANDBY"},
        {"name": "Uppal Stadium", "capacity": 8000,
         "lat": 17.40, "lon": 78.56, "status": "ACTIVE"},
    ]

    # Priority order (most vulnerable first)
    priority = sorted(zones, key=lambda z: (
        z.get("has_vulnerable_populations", False),
        z.get("priority_score", 0)
    ), reverse=True)
    priority_order = [z.get("name", "Zone") for z in priority]

    est_hours = total_pop / max(1, total_throughput)

    return EvacuationPlan(
        total_to_evacuate=total_pop,
        total_throughput_hr=total_throughput,
        estimated_hours_to_complete=round(est_hours, 1),
        routes=routes,
        staging_points=staging,
        bottlenecks=bottlenecks,
        priority_order=priority_order,
    )
