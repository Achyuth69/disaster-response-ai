"""
agents/triage_engine.py — AI Mass Casualty Triage System.

START Triage (Simple Triage And Rapid Treatment) implemented as AI.
Assigns RED/YELLOW/GREEN/BLACK codes to population groups.
Computes optimal rescue order to maximize survivable lives.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TriageGroup:
    group_id: str
    zone_name: str
    count: int
    code: str           # RED | YELLOW | GREEN | BLACK
    condition: str
    rescue_window_min: float
    survival_if_rescued: float
    survival_if_delayed: float
    lat: float = 0.0
    lon: float = 0.0
    priority_rank: int = 0


def run_triage(zones: list[dict], disaster_type: str, severity: int,
               time_elapsed_min: float) -> list[TriageGroup]:
    """
    Run START triage across all zones.
    Returns prioritized list of triage groups.
    """
    groups = []
    rank = 1

    for z in zones:
        pop = z.get("population_at_risk", 0)
        vuln_pct = 0.35 if z.get("has_vulnerable_populations") else 0.1
        score = z.get("priority_score", 0.5)

        # RED — immediate life threat, saveable with intervention
        red_count = int(pop * 0.08 * (severity / 10) * (1 + time_elapsed_min / 120))
        red_count = min(red_count, int(pop * 0.15))
        if red_count > 0:
            groups.append(TriageGroup(
                group_id=f"{z.get('zone_id','z')}_RED",
                zone_name=z.get("name", "Zone"),
                count=red_count,
                code="RED",
                condition=f"Critical injuries — {disaster_type} trauma, respiratory distress",
                rescue_window_min=max(5, 60 - time_elapsed_min),
                survival_if_rescued=0.85,
                survival_if_delayed=max(0.1, 0.85 - time_elapsed_min * 0.015),
                lat=z.get("lat", 0), lon=z.get("lon", 0),
                priority_rank=rank,
            ))
            rank += 1

        # YELLOW — delayed, stable but needs treatment
        yellow_count = int(pop * 0.15 * (severity / 10))
        if yellow_count > 0:
            groups.append(TriageGroup(
                group_id=f"{z.get('zone_id','z')}_YELLOW",
                zone_name=z.get("name", "Zone"),
                count=yellow_count,
                code="YELLOW",
                condition="Non-critical injuries — fractures, lacerations, moderate trauma",
                rescue_window_min=max(30, 240 - time_elapsed_min),
                survival_if_rescued=0.95,
                survival_if_delayed=max(0.6, 0.95 - time_elapsed_min * 0.003),
                lat=z.get("lat", 0), lon=z.get("lon", 0),
                priority_rank=rank,
            ))
            rank += 1

        # GREEN — walking wounded, minor injuries
        green_count = int(pop * 0.25)
        if green_count > 0:
            groups.append(TriageGroup(
                group_id=f"{z.get('zone_id','z')}_GREEN",
                zone_name=z.get("name", "Zone"),
                count=green_count,
                code="GREEN",
                condition="Minor injuries — can self-evacuate with guidance",
                rescue_window_min=480,
                survival_if_rescued=0.99,
                survival_if_delayed=0.97,
                lat=z.get("lat", 0), lon=z.get("lon", 0),
                priority_rank=rank,
            ))
            rank += 1

        # BLACK — expectant (beyond help given current resources)
        black_count = int(pop * 0.02 * (severity / 10) * max(1, time_elapsed_min / 60))
        black_count = min(black_count, int(pop * 0.05))
        if black_count > 0:
            groups.append(TriageGroup(
                group_id=f"{z.get('zone_id','z')}_BLACK",
                zone_name=z.get("name", "Zone"),
                count=black_count,
                code="BLACK",
                condition="Expectant — unsurvivable injuries given current resources",
                rescue_window_min=0,
                survival_if_rescued=0.05,
                survival_if_delayed=0.02,
                lat=z.get("lat", 0), lon=z.get("lon", 0),
                priority_rank=rank,
            ))
            rank += 1

    # Sort: RED first, then by rescue window
    order = {"RED": 0, "YELLOW": 1, "GREEN": 2, "BLACK": 3}
    groups.sort(key=lambda g: (order[g.code], g.rescue_window_min))
    for i, g in enumerate(groups):
        g.priority_rank = i + 1

    return groups
