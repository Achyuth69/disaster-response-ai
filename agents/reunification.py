"""
agents/reunification.py — Survivor Reunification System.

Tracks displaced families and helps reunite them.
Creates a registry of:
- People registered at relief camps
- Missing persons reported
- Last known locations
- Family unit matching

No disaster system currently does this at scale.
"""
from __future__ import annotations
import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class SurvivorRecord:
    record_id: str
    name: str           # anonymized for demo
    age: int
    gender: str
    zone_origin: str
    current_location: str  # camp name or "MISSING"
    family_id: str
    family_members_total: int
    family_members_found: int
    status: str         # "safe_at_camp" | "missing" | "hospitalized" | "reunited"
    last_seen: str
    contact_number: str
    special_needs: str
    lat: float = 0.0
    lon: float = 0.0


# Relief camp locations
RELIEF_CAMPS = [
    {"name": "Kukatpally Stadium", "lat": 17.494, "lon": 78.408, "capacity": 5000, "current": 3240},
    {"name": "Secunderabad Parade Ground", "lat": 17.440, "lon": 78.498, "capacity": 10000, "current": 7850},
    {"name": "BHEL Township Ground", "lat": 17.517, "lon": 78.317, "capacity": 6000, "current": 4120},
    {"name": "Uppal Stadium", "lat": 17.399, "lon": 78.559, "capacity": 8000, "current": 5670},
    {"name": "Banjara Hills Community Hall", "lat": 17.424, "lon": 78.407, "capacity": 2000, "current": 1890},
]

FIRST_NAMES = ["Ravi", "Priya", "Suresh", "Lakshmi", "Venkat", "Anitha", "Krishna", "Padma",
               "Ramesh", "Sunita", "Arun", "Kavitha", "Srinivas", "Meena", "Rajesh", "Usha"]
LAST_NAMES = ["Kumar", "Reddy", "Sharma", "Rao", "Naidu", "Patel", "Singh", "Verma"]


def generate_registry(
    zones: list[dict],
    total_displaced: int,
    num_records: int = 30,
) -> dict:
    """Generate a survivor registry for demonstration."""
    records = []
    missing_count = 0
    reunited_count = 0
    family_id = 1

    for i in range(num_records):
        h = int(hashlib.md5(f"survivor{i}".encode()).hexdigest(), 16)
        zone = zones[i % len(zones)] if zones else {"name": "Unknown Zone"}
        zone_name = zone.get("name", "Unknown")

        # Family unit
        family_size = 2 + (h % 4)
        members_found = min(family_size, 1 + (h >> 4) % family_size)

        # Status distribution: 60% safe, 25% missing, 10% hospitalized, 5% reunited
        status_roll = h % 100
        if status_roll < 60:
            status = "safe_at_camp"
            camp = RELIEF_CAMPS[h % len(RELIEF_CAMPS)]
            current_loc = camp["name"]
            lat = camp["lat"] + ((h % 20) - 10) / 10000
            lon = camp["lon"] + ((h % 30) - 15) / 10000
        elif status_roll < 85:
            status = "missing"
            current_loc = "MISSING"
            lat = zone.get("lat", 17.38) + ((h % 20) - 10) / 1000
            lon = zone.get("lon", 78.47) + ((h % 30) - 15) / 1000
            missing_count += 1
        elif status_roll < 95:
            status = "hospitalized"
            current_loc = "Gandhi Hospital / Osmania General"
            lat = 17.440
            lon = 78.498
        else:
            status = "reunited"
            current_loc = "Reunited with family"
            lat = zone.get("lat", 17.38)
            lon = zone.get("lon", 78.47)
            reunited_count += 1

        # Generate anonymized name
        fname = FIRST_NAMES[h % len(FIRST_NAMES)]
        lname = LAST_NAMES[(h >> 4) % len(LAST_NAMES)]
        age = 5 + (h % 70)
        gender = "M" if h % 2 == 0 else "F"

        # Last seen time
        mins_ago = (h % 180)
        last_seen = (datetime.utcnow() - timedelta(minutes=mins_ago)).strftime("%H:%M UTC")

        # Special needs
        needs = ""
        if age > 65:
            needs = "Elderly — mobility assistance"
        elif age < 5:
            needs = "Infant — formula milk needed"
        elif h % 20 == 0:
            needs = "Diabetic — insulin required"

        records.append(SurvivorRecord(
            record_id=f"REG-{i+1:05d}",
            name=f"{fname} {lname}",
            age=age,
            gender=gender,
            zone_origin=zone_name,
            current_location=current_loc,
            family_id=f"FAM-{(i // 3) + 1:04d}",
            family_members_total=family_size,
            family_members_found=members_found,
            status=status,
            last_seen=last_seen,
            contact_number=f"+91-9{h % 10}{(h>>4)%10}{(h>>8)%10}XXXXXXX",
            special_needs=needs,
            lat=lat, lon=lon,
        ))
        if i % 3 == 2:
            family_id += 1

    # Compute family reunification status
    family_status = {}
    for r in records:
        fid = r.family_id
        if fid not in family_status:
            family_status[fid] = {"total": r.family_members_total, "found": 0, "missing": 0}
        if r.status != "missing":
            family_status[fid]["found"] += 1
        else:
            family_status[fid]["missing"] += 1

    incomplete_families = [
        {"family_id": fid, "total": v["total"], "found": v["found"], "missing": v["missing"]}
        for fid, v in family_status.items()
        if v["missing"] > 0
    ]

    return {
        "total_registered": len(records),
        "safe_at_camp": sum(1 for r in records if r.status == "safe_at_camp"),
        "missing": missing_count,
        "hospitalized": sum(1 for r in records if r.status == "hospitalized"),
        "reunited": reunited_count,
        "incomplete_families": len(incomplete_families),
        "total_displaced_estimate": total_displaced,
        "registration_rate_pct": round(len(records) / max(1, total_displaced) * 100, 2),
        "camps": [
            {"name": c["name"], "capacity": c["capacity"],
             "current": c["current"], "occupancy_pct": round(c["current"]/c["capacity"]*100)}
            for c in RELIEF_CAMPS
        ],
        "records": [
            {
                "record_id": r.record_id,
                "name": r.name,
                "age": r.age,
                "gender": r.gender,
                "zone_origin": r.zone_origin,
                "current_location": r.current_location,
                "family_id": r.family_id,
                "family_members_total": r.family_members_total,
                "family_members_found": r.family_members_found,
                "status": r.status,
                "status_color": {
                    "safe_at_camp": "#00ff88",
                    "missing": "#ff2020",
                    "hospitalized": "#ffcc00",
                    "reunited": "#00ccff",
                }[r.status],
                "last_seen": r.last_seen,
                "special_needs": r.special_needs,
                "lat": r.lat, "lon": r.lon,
            }
            for r in records
        ],
        "incomplete_families": incomplete_families[:10],
    }
