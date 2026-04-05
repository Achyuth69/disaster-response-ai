"""
agents/vulnerable_tracker.py — Vulnerable Population Tracker.

Identifies people who CANNOT self-evacuate:
- Elderly (60+) with mobility issues
- Disabled individuals
- Hospitalized patients
- Infants and young children
- Pregnant women
- Prison inmates in flood zones

Creates targeted rescue missions for each group.
No disaster system tracks this at individual-group level.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass
class VulnerableGroup:
    group_id: str
    zone_name: str
    category: str        # "elderly" | "disabled" | "hospitalized" | "children" | "pregnant" | "inmates"
    icon: str
    count: int
    cannot_self_evacuate: bool
    special_needs: list[str]
    rescue_priority: int  # 1 = highest
    lat: float = 0.0
    lon: float = 0.0
    rescue_vehicle_needed: str = "ambulance"
    estimated_rescue_time_min: float = 30.0


# Hyderabad-specific vulnerable population data (from knowledge base)
HYDERABAD_VULNERABLE = {
    "dilsukhnagar": {
        "elderly": 6750, "disabled": 1350, "children_under5": 4500,
        "hospitals_patients": 0, "pregnant": 450,
    },
    "lb nagar": {
        "elderly": 9100, "disabled": 1950, "children_under5": 6500,
        "hospitals_patients": 300, "pregnant": 650,
    },
    "mehdipatnam": {
        "elderly": 10800, "disabled": 2160, "children_under5": 7200,
        "hospitals_patients": 1200, "pregnant": 720,
    },
    "uppal": {
        "elderly": 10200, "disabled": 2550, "children_under5": 8500,
        "hospitals_patients": 0, "pregnant": 850,
    },
    "malkajgiri": {
        "elderly": 6600, "disabled": 1650, "children_under5": 5500,
        "hospitals_patients": 200, "pregnant": 550,
    },
}

SPECIAL_FACILITIES = [
    {"name": "Chanchalguda Central Jail", "type": "prison",
     "count": 2500, "lat": 17.378, "lon": 78.487,
     "zone": "Mehdipatnam", "priority": 1},
    {"name": "Osmania General Hospital", "type": "hospital",
     "count": 1200, "lat": 17.385, "lon": 78.474,
     "zone": "Khairatabad", "priority": 1},
    {"name": "Niloufer Children's Hospital", "type": "hospital",
     "count": 900, "lat": 17.405, "lon": 78.474,
     "zone": "Khairatabad", "priority": 1},
    {"name": "Old Age Home — Dilsukhnagar", "type": "elderly_home",
     "count": 180, "lat": 17.369, "lon": 78.526,
     "zone": "Dilsukhnagar", "priority": 1},
    {"name": "Orphanage — LB Nagar", "type": "orphanage",
     "count": 120, "lat": 17.346, "lon": 78.554,
     "zone": "LB Nagar", "priority": 1},
]


def identify_vulnerable_populations(
    zones: list[dict],
    disaster_type: str,
    severity: int,
    base_lat: float = 17.38,
    base_lon: float = 78.47,
) -> dict:
    """Identify and prioritize vulnerable populations across all zones."""
    sev = severity / 10.0
    groups = []
    total_vulnerable = 0
    cannot_self_evacuate_total = 0

    for z in zones:
        zone_name = z.get("name", "Unknown").lower()
        pop = z.get("population_at_risk", 0)
        z_lat = z.get("lat", base_lat)
        z_lon = z.get("lon", base_lon)

        # Get zone-specific data or estimate from population
        vdata = None
        for k, v in HYDERABAD_VULNERABLE.items():
            if k in zone_name or zone_name.split()[0] in k:
                vdata = v
                break

        if not vdata:
            # Estimate from population demographics
            vdata = {
                "elderly": int(pop * 0.14),
                "disabled": int(pop * 0.03),
                "children_under5": int(pop * 0.10),
                "hospitals_patients": int(pop * 0.005),
                "pregnant": int(pop * 0.015),
            }

        # Elderly
        if vdata["elderly"] > 0:
            groups.append(VulnerableGroup(
                group_id=f"{zone_name[:8]}_ELD",
                zone_name=z.get("name", "Zone"),
                category="elderly",
                icon="👴",
                count=vdata["elderly"],
                cannot_self_evacuate=True,
                special_needs=["wheelchair_accessible_vehicle", "medical_monitoring", "slow_movement"],
                rescue_priority=2,
                lat=z_lat + 0.002, lon=z_lon + 0.002,
                rescue_vehicle_needed="accessible_bus",
                estimated_rescue_time_min=45.0,
            ))
            cannot_self_evacuate_total += vdata["elderly"]

        # Disabled
        if vdata["disabled"] > 0:
            groups.append(VulnerableGroup(
                group_id=f"{zone_name[:8]}_DIS",
                zone_name=z.get("name", "Zone"),
                category="disabled",
                icon="♿",
                count=vdata["disabled"],
                cannot_self_evacuate=True,
                special_needs=["wheelchair_lift", "personal_assistant", "medical_equipment"],
                rescue_priority=1,
                lat=z_lat - 0.002, lon=z_lon + 0.003,
                rescue_vehicle_needed="ambulance",
                estimated_rescue_time_min=30.0,
            ))
            cannot_self_evacuate_total += vdata["disabled"]

        # Children under 5
        if vdata["children_under5"] > 0:
            groups.append(VulnerableGroup(
                group_id=f"{zone_name[:8]}_CHD",
                zone_name=z.get("name", "Zone"),
                category="children",
                icon="👶",
                count=vdata["children_under5"],
                cannot_self_evacuate=True,
                special_needs=["child_seats", "pediatric_medical", "formula_milk", "diapers"],
                rescue_priority=1,
                lat=z_lat + 0.003, lon=z_lon - 0.002,
                rescue_vehicle_needed="bus",
                estimated_rescue_time_min=25.0,
            ))
            cannot_self_evacuate_total += vdata["children_under5"]

        # Hospitalized patients
        if vdata.get("hospitals_patients", 0) > 0:
            groups.append(VulnerableGroup(
                group_id=f"{zone_name[:8]}_HOS",
                zone_name=z.get("name", "Zone"),
                category="hospitalized",
                icon="🏥",
                count=vdata["hospitals_patients"],
                cannot_self_evacuate=True,
                special_needs=["ICU_transport", "oxygen_supply", "IV_lines", "medical_staff"],
                rescue_priority=1,
                lat=z_lat - 0.003, lon=z_lon - 0.002,
                rescue_vehicle_needed="medical_ambulance",
                estimated_rescue_time_min=60.0,
            ))
            cannot_self_evacuate_total += vdata["hospitals_patients"]

        # Pregnant women
        if vdata.get("pregnant", 0) > 0:
            groups.append(VulnerableGroup(
                group_id=f"{zone_name[:8]}_PRG",
                zone_name=z.get("name", "Zone"),
                category="pregnant",
                icon="🤰",
                count=vdata["pregnant"],
                cannot_self_evacuate=False,
                special_needs=["obstetric_care", "clean_water", "maternity_kit"],
                rescue_priority=2,
                lat=z_lat + 0.001, lon=z_lon - 0.003,
                rescue_vehicle_needed="ambulance",
                estimated_rescue_time_min=20.0,
            ))

        total_vulnerable += sum(vdata.values())

    # Add special facilities
    facility_groups = []
    for f in SPECIAL_FACILITIES:
        facility_groups.append({
            "facility_name": f["name"],
            "type": f["type"],
            "count": f["count"],
            "lat": f["lat"],
            "lon": f["lon"],
            "zone": f["zone"],
            "priority": f["priority"],
            "special_needs": _facility_needs(f["type"]),
            "rescue_vehicle": "bus" if f["type"] == "prison" else "ambulance",
        })

    # Sort by priority
    groups.sort(key=lambda g: g.rescue_priority)

    return {
        "total_vulnerable": total_vulnerable,
        "cannot_self_evacuate": cannot_self_evacuate_total,
        "groups": [
            {
                "group_id": g.group_id,
                "zone_name": g.zone_name,
                "category": g.category,
                "icon": g.icon,
                "count": g.count,
                "cannot_self_evacuate": g.cannot_self_evacuate,
                "special_needs": g.special_needs,
                "rescue_priority": g.rescue_priority,
                "lat": g.lat, "lon": g.lon,
                "rescue_vehicle_needed": g.rescue_vehicle_needed,
                "estimated_rescue_time_min": g.estimated_rescue_time_min,
            }
            for g in groups
        ],
        "special_facilities": facility_groups,
        "rescue_missions_needed": len([g for g in groups if g.cannot_self_evacuate]),
    }


def _facility_needs(facility_type: str) -> list[str]:
    return {
        "prison": ["security_escort", "transport_buses", "police_coordination"],
        "hospital": ["medical_transport", "oxygen", "ICU_ambulances", "generator"],
        "elderly_home": ["wheelchair_transport", "medical_staff", "slow_evacuation"],
        "orphanage": ["child_transport", "social_workers", "food_formula"],
    }.get(facility_type, ["standard_evacuation"])
