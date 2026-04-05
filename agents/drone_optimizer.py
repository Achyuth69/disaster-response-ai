"""
agents/drone_optimizer.py — Drone/UAV Coverage Optimizer.

Given N drones, computes optimal flight paths to cover
maximum population in minimum time using a greedy coverage algorithm.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass
class DroneRoute:
    drone_id: str
    waypoints: list[dict]          # [{lat, lon, zone_name, population, eta_min}]
    total_distance_km: float
    total_time_min: float
    population_covered: int
    coverage_efficiency: float     # population per km


def haversine(lat1, lon1, lat2, lon2) -> float:
    """Distance in km between two lat/lon points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def optimize_drone_coverage(
    zones: list[dict],
    num_drones: int,
    base_lat: float,
    base_lon: float,
    drone_speed_kmh: float = 80.0,
    drone_range_km: float = 50.0,
    camera_radius_km: float = 0.5,
) -> list[DroneRoute]:
    """
    Greedy nearest-neighbor TSP for drone coverage.
    Each drone gets assigned zones to maximize population coverage.
    """
    if not zones or num_drones <= 0:
        return []

    # Sort zones by population descending
    sorted_zones = sorted(zones, key=lambda z: z.get("population_at_risk", 0), reverse=True)

    # Distribute zones across drones (round-robin by priority)
    drone_assignments: list[list[dict]] = [[] for _ in range(num_drones)]
    for i, zone in enumerate(sorted_zones):
        drone_assignments[i % num_drones].append(zone)

    routes = []
    for d_idx, assigned in enumerate(drone_assignments):
        if not assigned:
            continue

        waypoints = []
        total_dist = 0.0
        cur_lat, cur_lon = base_lat, base_lon
        total_pop = 0
        elapsed_min = 0.0

        # Nearest-neighbor ordering
        remaining = list(assigned)
        while remaining:
            # Find nearest unvisited zone
            nearest = min(remaining, key=lambda z: haversine(
                cur_lat, cur_lon,
                z.get("lat", base_lat), z.get("lon", base_lon)
            ))
            dist = haversine(cur_lat, cur_lon,
                             nearest.get("lat", base_lat),
                             nearest.get("lon", base_lon))
            if total_dist + dist > drone_range_km:
                break  # out of range

            total_dist += dist
            elapsed_min += (dist / drone_speed_kmh) * 60
            pop = nearest.get("population_at_risk", 0)
            total_pop += pop

            waypoints.append({
                "lat": nearest.get("lat", base_lat),
                "lon": nearest.get("lon", base_lon),
                "zone_name": nearest.get("name", f"Zone {len(waypoints)+1}"),
                "population": pop,
                "eta_min": round(elapsed_min, 1),
                "action": "SURVEY + RELAY COORDINATES TO GROUND TEAMS",
            })

            cur_lat = nearest.get("lat", base_lat)
            cur_lon = nearest.get("lon", base_lon)
            remaining.remove(nearest)

        # Return to base
        return_dist = haversine(cur_lat, cur_lon, base_lat, base_lon)
        total_dist += return_dist
        elapsed_min += (return_dist / drone_speed_kmh) * 60

        efficiency = total_pop / max(0.1, total_dist)

        routes.append(DroneRoute(
            drone_id=f"UAV-{d_idx+1:02d}",
            waypoints=waypoints,
            total_distance_km=round(total_dist, 2),
            total_time_min=round(elapsed_min, 1),
            population_covered=total_pop,
            coverage_efficiency=round(efficiency, 1),
        ))

    return routes
