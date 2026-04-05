"""
agents/multi_agency.py — Multi-Agency Command Center Simulator.

Simulates NDRF, Police, Fire, Hospitals, NGOs as separate agents
with their own resources, jurisdictions, and communication channels.
Detects conflicts, duplications, and coordination gaps.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Agency:
    agency_id: str
    name: str
    type: str           # "rescue" | "medical" | "law_enforcement" | "fire" | "ngo"
    icon: str
    teams: int
    vehicles: int
    jurisdiction_zones: list[str]
    radio_channel: str
    status: str = "standby"  # "standby" | "deployed" | "overwhelmed"
    assigned_zones: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class CoordinationConflict:
    conflict_id: str
    type: str           # "duplication" | "gap" | "resource_conflict" | "jurisdiction"
    agencies: list[str]
    zone: str
    description: str
    recommendation: str
    severity: str       # "low" | "medium" | "high" | "critical"


def simulate_multi_agency(
    disaster_type: str,
    severity: int,
    zones: list[dict],
    rescue_teams: int,
) -> dict:
    """
    Simulate multi-agency coordination and detect conflicts.
    """
    sev = severity / 10.0
    zone_names = [z.get("name", f"Zone {i+1}") for i, z in enumerate(zones)]

    # Define agencies
    agencies = [
        Agency("NDRF", "National Disaster Response Force", "rescue", "🪖",
               teams=min(rescue_teams, 6), vehicles=4,
               jurisdiction_zones=zone_names[:3],
               radio_channel="VHF-156.8MHz"),
        Agency("SDRF", "State Disaster Response Force", "rescue", "🚒",
               teams=max(2, rescue_teams - 6), vehicles=3,
               jurisdiction_zones=zone_names[2:5] if len(zone_names) > 2 else zone_names,
               radio_channel="VHF-155.3MHz"),
        Agency("GHMC", "Greater Hyderabad Municipal Corp", "infrastructure", "🏗️",
               teams=8, vehicles=12,
               jurisdiction_zones=zone_names,
               radio_channel="UHF-460MHz"),
        Agency("POLICE", "Hyderabad City Police", "law_enforcement", "👮",
               teams=20, vehicles=15,
               jurisdiction_zones=zone_names,
               radio_channel="TETRA-380MHz"),
        Agency("FIRE", "Hyderabad Fire & Emergency", "fire", "🚒",
               teams=6, vehicles=8,
               jurisdiction_zones=zone_names[:4] if len(zone_names) > 3 else zone_names,
               radio_channel="VHF-154.3MHz"),
        Agency("108", "Emergency Medical Services (108)", "medical", "🚑",
               teams=12, vehicles=20,
               jurisdiction_zones=zone_names,
               radio_channel="UHF-462MHz"),
        Agency("NGO_RED", "Red Cross India", "ngo", "🏥",
               teams=5, vehicles=3,
               jurisdiction_zones=zone_names[:3] if len(zone_names) > 2 else zone_names,
               radio_channel="Satellite-Phone"),
    ]

    # Detect conflicts
    conflicts = []
    conflict_id = 1

    # Check for zone duplication (multiple agencies in same zone without coordination)
    zone_agency_map: dict[str, list[str]] = {}
    for agency in agencies:
        for zone in agency.jurisdiction_zones:
            zone_agency_map.setdefault(zone, []).append(agency.name)

    for zone, agency_list in zone_agency_map.items():
        rescue_agencies = [a for a in agency_list
                           if any(ag.type in ("rescue",) for ag in agencies if ag.name == a)]
        if len(rescue_agencies) > 2:
            conflicts.append(CoordinationConflict(
                conflict_id=f"C{conflict_id:03d}",
                type="duplication",
                agencies=rescue_agencies,
                zone=zone,
                description=f"{len(rescue_agencies)} rescue agencies assigned to {zone} — risk of resource duplication",
                recommendation=f"Designate {rescue_agencies[0]} as lead agency for {zone}. Others support.",
                severity="medium",
            ))
            conflict_id += 1

    # Check for communication gaps (different radio channels)
    channels = set(a.radio_channel for a in agencies)
    if len(channels) > 3:
        conflicts.append(CoordinationConflict(
            conflict_id=f"C{conflict_id:03d}",
            type="resource_conflict",
            agencies=[a.name for a in agencies],
            zone="ALL ZONES",
            description=f"{len(channels)} different radio channels in use — inter-agency communication breakdown risk",
            recommendation="Establish unified command frequency. Assign radio bridge operators at EOC.",
            severity="high",
        ))
        conflict_id += 1

    # Check for coverage gaps
    all_zones = set(zone_names)
    covered_zones = set(zone_agency_map.keys())
    uncovered = all_zones - covered_zones
    if uncovered:
        conflicts.append(CoordinationConflict(
            conflict_id=f"C{conflict_id:03d}",
            type="gap",
            agencies=[],
            zone=", ".join(uncovered),
            description=f"Zones with NO agency assigned: {', '.join(uncovered)}",
            recommendation="Immediately assign SDRF or NGO teams to uncovered zones.",
            severity="critical",
        ))
        conflict_id += 1

    # Assign statuses
    for agency in agencies:
        if len(agency.jurisdiction_zones) > 3:
            agency.status = "overwhelmed"
        elif agency.teams > 0:
            agency.status = "deployed"

    return {
        "agencies": [
            {
                "agency_id": a.agency_id,
                "name": a.name,
                "type": a.type,
                "icon": a.icon,
                "teams": a.teams,
                "vehicles": a.vehicles,
                "jurisdiction_zones": a.jurisdiction_zones,
                "radio_channel": a.radio_channel,
                "status": a.status,
            }
            for a in agencies
        ],
        "conflicts": [
            {
                "conflict_id": c.conflict_id,
                "type": c.type,
                "agencies": c.agencies,
                "zone": c.zone,
                "description": c.description,
                "recommendation": c.recommendation,
                "severity": c.severity,
                "severity_color": {
                    "critical": "#ff2020", "high": "#ff6600",
                    "medium": "#ffcc00", "low": "#00ff88"
                }[c.severity],
            }
            for c in conflicts
        ],
        "total_agencies": len(agencies),
        "total_conflicts": len(conflicts),
        "critical_conflicts": sum(1 for c in conflicts if c.severity == "critical"),
        "coordination_score": max(0, 100 - len(conflicts) * 15),
    }
