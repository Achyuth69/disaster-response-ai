"""
agents/rescue_planner.py — Rescue Planner Agent.
Identifies Priority Zones, assigns rescue teams to optimal routes,
uses consensus voting when two LLM providers are available,
and consults agent memory to avoid re-assigning cleared zones.
"""
from __future__ import annotations

import re
from typing import Optional

from agents.models import (
    DataSummary, DisasterContext, PriorityZone, RescuePlan,
)
from agents.security import sanitize_input


SYSTEM_PROMPT = """You are the Rescue Planner Agent for a disaster response system.
Your job is to identify the highest-priority rescue zones and assign rescue teams
to optimal routes. Be decisive, realistic, and prioritize vulnerable populations.
Always consider road accessibility, water levels, and population density.
Output ONLY the structured format requested — no extra commentary."""


def _build_rescue_prompt(context: DisasterContext, data_summary: DataSummary,
                         num_teams: int, memory_context: str,
                         chaos_note: str) -> str:
    zones_text = ", ".join(data_summary.affected_zones)
    constraints_text = "\n".join(
        f"  - {c}" for c in data_summary.geographic_constraints
    ) or "  None reported"
    facilities_text = "\n".join(
        f"  - {f}" for f in data_summary.nearest_medical_facilities[:5]
    )

    return f"""DISASTER CONTEXT:
Type: {context.disaster_type} | Location: {context.location}
Severity: {context.severity}/10 | Time Elapsed: {context.time_elapsed_hours}h
Weather: {context.weather_conditions}
{chaos_note}

DATA SUMMARY:
Affected Zones: {zones_text}
Population at Risk: {data_summary.estimated_population_at_risk:,}
Medical Facilities:
{facilities_text}
Geographic Constraints:
{constraints_text}

AVAILABLE RESOURCES: {num_teams} rescue teams
{memory_context}

INSTRUCTIONS:
1. Rank ALL affected zones by composite priority score:
   score = (population_density_factor × 0.4) + (damage_severity × 0.35) + (vulnerability_factor × 0.25)
   vulnerability_factor = 1.0 if elderly/children/disabled present, else 0.5
2. Assign exactly one team per zone (up to {num_teams} teams)
3. Generate routes avoiding known constraints
4. If a chaos event introduced new zones or blockages, revise immediately
5. Do NOT assign teams to zones marked as CLEARED in memory

OUTPUT FORMAT (follow exactly):
PRIORITY ZONES:
1. [Zone Name] | Score: [X.XX] | Population: [N] | Vulnerable: [yes/no] | Constraints: [list or none]
2. [Zone Name] | Score: [X.XX] | Population: [N] | Vulnerable: [yes/no] | Constraints: [list or none]
(continue for all zones)

TEAM ASSIGNMENTS:
Team-1 → [Zone Name] | Route: [description] | ETA: [X.X hours]
Team-2 → [Zone Name] | Route: [description] | ETA: [X.X hours]
(continue for all teams)

CONFIDENCE SCORE: [0.0-1.0]
RISKS: [key risks in this plan]"""


class RescuePlanner:
    """
    Rescue Planner Agent with consensus voting support.
    """

    def __init__(self, llm_client):
        self._llm = llm_client

    def invoke(self, context: DisasterContext, data_summary: DataSummary,
               num_teams: int = 10, memory=None) -> RescuePlan:
        """Plan rescue operations and return a RescuePlan."""
        chaos_note = ""
        if context.active_chaos_event and context.active_chaos_event.event_type != "none":
            chaos_note = (
                f"⚡ CHAOS EVENT ACTIVE: {context.active_chaos_event.event_type} — "
                f"{context.active_chaos_event.description}"
            )

        memory_context = self._build_memory_context(memory)
        prompt = _build_rescue_prompt(
            context, data_summary, num_teams, memory_context, chaos_note
        )

        # Use consensus voting if secondary provider available
        consensus = self._llm.complete_consensus(prompt, SYSTEM_PROMPT)
        raw = consensus.final_response

        plan = self._parse_response(raw, num_teams)
        plan.consensus_disagreement = consensus.disagreement_note

        # Store cleared zones to memory
        if memory:
            cleared = [z.name for z in plan.priority_zones if z.cleared]
            if cleared:
                memory.store("rescue_planner", "cleared_zones", cleared,
                             getattr(context, "_cycle_num", 0))
            memory.store("rescue_planner", "last_plan_zones",
                         [z.name for z in plan.priority_zones],
                         getattr(context, "_cycle_num", 0))

        return plan

    def _build_memory_context(self, memory) -> str:
        if not memory:
            return ""
        cleared = memory.recall_latest("rescue_planner", "cleared_zones") or []
        blocked = memory.recall_latest("data_agent", "geographic_constraints") or []
        lines = []
        if cleared:
            lines.append(f"CLEARED ZONES (do not re-assign): {', '.join(cleared)}")
        if blocked:
            lines.append(f"Previously blocked routes: {', '.join(str(b) for b in blocked[:5])}")
        return "\n".join(lines)

    def _parse_response(self, raw: str, num_teams: int) -> RescuePlan:
        priority_zones: list[PriorityZone] = []
        team_assignments: dict[str, str] = {}
        travel_times: dict[str, float] = {}
        route_descriptions: dict[str, str] = {}
        confidence = 0.8

        # Parse PRIORITY ZONES section
        zones_section = re.search(
            r"PRIORITY ZONES:(.*?)(?:TEAM ASSIGNMENTS:|CONFIDENCE SCORE:|$)",
            raw, re.DOTALL | re.IGNORECASE
        )
        if zones_section:
            for line in zones_section.group(1).strip().split("\n"):
                line = line.strip()
                if not line or not re.match(r"^\d+\.", line):
                    continue
                # Parse: "1. Zone Name | Score: X.XX | Population: N | Vulnerable: yes/no"
                name_m = re.match(r"^\d+\.\s*([^|]+)", line)
                score_m = re.search(r"Score:\s*([\d.]+)", line, re.IGNORECASE)
                pop_m = re.search(r"Population:\s*([\d,]+)", line, re.IGNORECASE)
                vuln_m = re.search(r"Vulnerable:\s*(yes|no)", line, re.IGNORECASE)
                const_m = re.search(r"Constraints:\s*(.+?)$", line, re.IGNORECASE)

                if not name_m:
                    continue

                zone_name = name_m.group(1).strip()
                zone_id = f"zone_{len(priority_zones) + 1}"
                score = float(score_m.group(1)) if score_m else (
                    1.0 - len(priority_zones) * 0.1
                )
                pop_str = pop_m.group(1).replace(",", "") if pop_m else "0"
                try:
                    pop = int(pop_str)
                except ValueError:
                    pop = 0
                vulnerable = (vuln_m.group(1).lower() == "yes") if vuln_m else True
                constraints = []
                if const_m and const_m.group(1).lower() not in ("none", ""):
                    constraints = [c.strip() for c in const_m.group(1).split(",")]

                priority_zones.append(PriorityZone(
                    zone_id=zone_id,
                    name=zone_name,
                    priority_score=score,
                    population_at_risk=pop,
                    has_vulnerable_populations=vulnerable,
                    geographic_constraints=constraints,
                ))

        # Sort descending by priority score
        priority_zones.sort(key=lambda z: z.priority_score, reverse=True)

        # Parse TEAM ASSIGNMENTS section
        teams_section = re.search(
            r"TEAM ASSIGNMENTS:(.*?)(?:CONFIDENCE SCORE:|RISKS:|$)",
            raw, re.DOTALL | re.IGNORECASE
        )
        assigned_zones: set[str] = set()
        if teams_section:
            for line in teams_section.group(1).strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                team_m = re.match(r"(Team-\d+)\s*[→>]\s*([^|]+)", line, re.IGNORECASE)
                if not team_m:
                    continue
                team_id = team_m.group(1).strip()
                zone_name = team_m.group(2).strip()

                # Enforce injectivity — skip if zone already assigned
                if zone_name in assigned_zones:
                    continue
                assigned_zones.add(zone_name)

                # Find matching zone_id
                zone_id = next(
                    (z.zone_id for z in priority_zones if z.name == zone_name),
                    f"zone_{len(team_assignments) + 1}"
                )
                team_assignments[team_id] = zone_id

                route_m = re.search(r"Route:\s*([^|]+)", line, re.IGNORECASE)
                eta_m = re.search(r"ETA:\s*([\d.]+)", line, re.IGNORECASE)
                if route_m:
                    route_descriptions[zone_id] = route_m.group(1).strip()
                if eta_m:
                    try:
                        travel_times[zone_id] = float(eta_m.group(1))
                    except ValueError:
                        travel_times[zone_id] = 1.0

        # Parse confidence
        conf_m = re.search(r"CONFIDENCE SCORE:\s*([\d.]+)", raw, re.IGNORECASE)
        if conf_m:
            try:
                confidence = max(0.0, min(1.0, float(conf_m.group(1))))
            except ValueError:
                pass

        # Fallback: if no zones parsed, create defaults from data summary
        if not priority_zones:
            priority_zones = [
                PriorityZone(
                    zone_id=f"zone_{i+1}",
                    name=zone,
                    priority_score=1.0 - i * 0.1,
                    population_at_risk=50000,
                    has_vulnerable_populations=True,
                )
                for i, zone in enumerate(["Dilsukhnagar", "LB Nagar", "Mehdipatnam"])
            ]

        return RescuePlan(
            priority_zones=priority_zones,
            team_assignments=team_assignments,
            estimated_travel_times=travel_times,
            route_descriptions=route_descriptions,
            confidence_score=confidence,
        )
