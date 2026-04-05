"""
agents/asset_tracker.py — Real-Time Asset Tracker.

Tracks every rescue team, boat, and vehicle in real-time.
Simulates GPS positions, ETAs, route conflicts, and bottlenecks.
Shows live movement on the map.
"""
from __future__ import annotations
import math
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Asset:
    asset_id: str
    asset_type: str      # "rescue_team" | "boat" | "ambulance" | "fire_truck" | "helicopter"
    icon: str
    name: str
    status: str          # "en_route" | "on_scene" | "returning" | "standby" | "unavailable"
    current_lat: float
    current_lon: float
    destination_lat: float
    destination_lon: float
    destination_name: str
    speed_kmh: float
    eta_minutes: float
    assigned_zone: str
    team_size: int
    last_update: str


def simulate_asset_positions(
    zones: list[dict],
    rescue_teams: int,
    boats: int,
    base_lat: float,
    base_lon: float,
    time_elapsed_min: float = 30.0,
) -> list[Asset]:
    """Simulate real-time positions of all assets."""
    assets = []
    asset_id = 1

    for i in range(min(rescue_teams, len(zones))):
        zone = zones[i % len(zones)]
        z_lat = zone.get("lat", base_lat + (i * 0.02))
        z_lon = zone.get("lon", base_lon + (i * 0.02))

        # Calculate progress along route
        h = int(hashlib.md5(f"team{i}".encode()).hexdigest(), 16) % 100
        progress = min(1.0, time_elapsed_min / (20 + h % 20))

        cur_lat = base_lat + (z_lat - base_lat) * progress
        cur_lon = base_lon + (z_lon - base_lon) * progress

        dist_remaining = _haversine(cur_lat, cur_lon, z_lat, z_lon)
        speed = 25.0  # km/h in disaster conditions
        eta = (dist_remaining / speed) * 60 if progress < 1.0 else 0

        status = "on_scene" if progress >= 0.95 else "en_route"

        assets.append(Asset(
            asset_id=f"TEAM-{asset_id:02d}",
            asset_type="rescue_team",
            icon="🚒",
            name=f"Rescue Team {asset_id}",
            status=status,
            current_lat=cur_lat,
            current_lon=cur_lon,
            destination_lat=z_lat,
            destination_lon=z_lon,
            destination_name=zone.get("name", f"Zone {i+1}"),
            speed_kmh=speed,
            eta_minutes=round(eta, 1),
            assigned_zone=zone.get("name", ""),
            team_size=5,
            last_update=f"{int(time_elapsed_min)}min ago",
        ))
        asset_id += 1

    # Boats
    for i in range(min(boats, 3)):
        zone = zones[i % len(zones)] if zones else {"name": "Zone", "lat": base_lat, "lon": base_lon}
        z_lat = zone.get("lat", base_lat) + 0.01
        z_lon = zone.get("lon", base_lon) + 0.01
        h = int(hashlib.md5(f"boat{i}".encode()).hexdigest(), 16) % 100
        progress = min(1.0, time_elapsed_min / (15 + h % 15))
        cur_lat = base_lat + (z_lat - base_lat) * progress
        cur_lon = base_lon + (z_lon - base_lon) * progress
        dist_remaining = _haversine(cur_lat, cur_lon, z_lat, z_lon)
        eta = (dist_remaining / 15.0) * 60 if progress < 1.0 else 0

        assets.append(Asset(
            asset_id=f"BOAT-{i+1:02d}",
            asset_type="boat",
            icon="⛵",
            name=f"Rescue Boat {i+1}",
            status="on_scene" if progress >= 0.95 else "en_route",
            current_lat=cur_lat,
            current_lon=cur_lon,
            destination_lat=z_lat,
            destination_lon=z_lon,
            destination_name=zone.get("name", ""),
            speed_kmh=15.0,
            eta_minutes=round(eta, 1),
            assigned_zone=zone.get("name", ""),
            team_size=3,
            last_update=f"{int(time_elapsed_min)}min ago",
        ))

    # Ambulances
    for i in range(3):
        h = int(hashlib.md5(f"amb{i}".encode()).hexdigest(), 16) % 100
        offset_lat = (h % 20 - 10) / 1000
        offset_lon = ((h >> 4) % 20 - 10) / 1000
        assets.append(Asset(
            asset_id=f"AMB-{i+1:02d}",
            asset_type="ambulance",
            icon="🚑",
            name=f"Ambulance {i+1}",
            status="en_route" if i < 2 else "on_scene",
            current_lat=base_lat + offset_lat,
            current_lon=base_lon + offset_lon,
            destination_lat=base_lat + offset_lat * 2,
            destination_lon=base_lon + offset_lon * 2,
            destination_name="Osmania Hospital",
            speed_kmh=40.0,
            eta_minutes=round(5 + i * 3, 1),
            assigned_zone="Medical",
            team_size=2,
            last_update="Live",
        ))

    return assets


def detect_route_conflicts(assets: list[Asset]) -> list[dict]:
    """Detect when multiple assets are heading to the same zone."""
    zone_assets: dict[str, list[str]] = {}
    for a in assets:
        if a.destination_name:
            zone_assets.setdefault(a.destination_name, []).append(a.asset_id)

    conflicts = []
    for zone, asset_ids in zone_assets.items():
        if len(asset_ids) > 2:
            conflicts.append({
                "zone": zone,
                "assets": asset_ids,
                "type": "overcrowding",
                "recommendation": f"Redirect {asset_ids[-1]} to nearest unserved zone",
                "severity": "warning",
            })
    return conflicts


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(max(0, a)))
