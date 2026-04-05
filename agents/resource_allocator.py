"""
agents/resource_allocator.py — Resource Allocator Agent.
Distributes limited resources across Priority Zones using
priority-weighted allocation, tracks depletion, and uses
consensus voting for critical decisions.
"""
from __future__ import annotations

import re
from typing import Optional

from agents.models import (
    AllocationResult, DisasterContext, RescuePlan,
    ResourceState, ZoneAllocation,
)
from agents.security import sanitize_input


SYSTEM_PROMPT = """You are the Resource Allocator Agent for a disaster response system.
Your job is to distribute limited resources optimally across rescue zones.
Resources are ALWAYS insufficient — you must make hard trade-offs.
Be explicit about what is NOT being served and why.
Output ONLY the structured format requested."""


def _build_allocator_prompt(context: DisasterContext, rescue_plan: RescuePlan,
                             resources: ResourceState, memory_context: str,
                             chaos_note: str) -> str:
    zones_text = "\n".join(
        f"  {i+1}. {z.name} | Priority: {z.priority_score:.2f} | "
        f"Pop: {z.population_at_risk:,} | Vulnerable: {'YES' if z.has_vulnerable_populations else 'no'}"
        for i, z in enumerate(rescue_plan.priority_zones)
    )

    return f"""DISASTER CONTEXT:
Type: {context.disaster_type} | Location: {context.location}
Severity: {context.severity}/10
{chaos_note}

PRIORITY ZONES (ranked):
{zones_text}

AVAILABLE RESOURCES:
  Rescue Teams: {resources.rescue_teams}
  Boats/Vehicles: {resources.boats}
  Medical Kits: {resources.medical_kits}
  Food Supply Units: {resources.food_supply_units}

{memory_context}

ALLOCATION RULES:
1. Allocate proportionally to priority_score × population_at_risk
2. Higher-priority zones get resources first
3. If demand > supply, apply priority-weighted rationing
4. Flag any resource type that reaches zero
5. Document every trade-off explicitly

OUTPUT FORMAT (follow exactly):
RESOURCE ALLOCATION TABLE:
Zone | Teams | Boats | Med Kits | Food | Justification
[Zone Name] | [N] | [N] | [N] | [N] | [reason]
(one row per zone)

DEPLETED RESOURCES: [comma-separated list, or NONE]
TRADE-OFFS: [explicit explanation of what is NOT being served and why]
CONFIDENCE SCORE: [0.0-1.0]"""


class ResourceAllocator:
    """
    Resource Allocator Agent with consensus voting and depletion tracking.
    """

    def __init__(self, llm_client):
        self._llm = llm_client

    def invoke(self, context: DisasterContext, rescue_plan: RescuePlan,
               resources: ResourceState, memory=None) -> AllocationResult:
        """Allocate resources and return AllocationResult."""
        chaos_note = ""
        if context.active_chaos_event and context.active_chaos_event.event_type != "none":
            chaos_note = (
                f"⚡ CHAOS EVENT: {context.active_chaos_event.event_type} — "
                f"{context.active_chaos_event.description}"
            )

        memory_context = self._build_memory_context(memory, resources)
        prompt = _build_allocator_prompt(
            context, rescue_plan, resources, memory_context, chaos_note
        )

        consensus = self._llm.complete_consensus(prompt, SYSTEM_PROMPT)
        raw = consensus.final_response

        result = self._parse_response(raw, resources)
        result = self._enforce_constraints(result, resources)
        result.consensus_disagreement = consensus.disagreement_note

        # Store consumption rates to memory
        if memory:
            consumption = {
                "rescue_teams": resources.rescue_teams - result.remaining_resources.rescue_teams,
                "boats": resources.boats - result.remaining_resources.boats,
                "medical_kits": resources.medical_kits - result.remaining_resources.medical_kits,
                "food_supply_units": resources.food_supply_units - result.remaining_resources.food_supply_units,
            }
            memory.store("resource_allocator", "consumption_rates", consumption,
                         getattr(context, "_cycle_num", 0))

        return result

    def _build_memory_context(self, memory, resources: ResourceState) -> str:
        if not memory:
            return ""
        rates_history = memory.recall("resource_allocator", "consumption_rates")
        if not rates_history:
            return ""
        last_rate = rates_history[-1].value
        lines = ["PREVIOUS CYCLE CONSUMPTION RATES:"]
        for k, v in last_rate.items():
            lines.append(f"  {k}: {v} units consumed")
        return "\n".join(lines)

    def _parse_response(self, raw: str, resources: ResourceState) -> AllocationResult:
        allocations: list[ZoneAllocation] = []
        depleted: list[str] = []
        trade_offs = ""
        confidence = 0.8

        # Parse allocation table
        table_section = re.search(
            r"RESOURCE ALLOCATION TABLE:(.*?)(?:DEPLETED RESOURCES:|TRADE-OFFS:|CONFIDENCE SCORE:|$)",
            raw, re.DOTALL | re.IGNORECASE
        )
        if table_section:
            lines = table_section.group(1).strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line or "|" not in line:
                    continue
                # Skip header row
                if re.match(r"zone\s*\|", line, re.IGNORECASE):
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 5:
                    continue
                try:
                    zone_name = parts[0]
                    teams = int(re.sub(r"[^\d]", "", parts[1]) or "0")
                    boats = int(re.sub(r"[^\d]", "", parts[2]) or "0")
                    med = int(re.sub(r"[^\d]", "", parts[3]) or "0")
                    food = int(re.sub(r"[^\d]", "", parts[4]) or "0")
                    justification = parts[5] if len(parts) > 5 else ""
                    allocations.append(ZoneAllocation(
                        zone_id=zone_name.lower().replace(" ", "_"),
                        rescue_teams=teams,
                        boats=boats,
                        medical_kits=med,
                        food_supply_units=food,
                        justification=justification,
                    ))
                except (ValueError, IndexError):
                    continue

        # Parse depleted resources
        dep_m = re.search(r"DEPLETED RESOURCES:\s*(.+?)(?:\n|$)", raw, re.IGNORECASE)
        if dep_m:
            dep_text = dep_m.group(1).strip()
            if dep_text.upper() != "NONE":
                depleted = [d.strip() for d in dep_text.split(",") if d.strip()]

        # Parse trade-offs
        to_m = re.search(
            r"TRADE-OFFS:\s*(.+?)(?:CONFIDENCE SCORE:|$)", raw,
            re.DOTALL | re.IGNORECASE
        )
        if to_m:
            trade_offs = to_m.group(1).strip()

        # Parse confidence
        conf_m = re.search(r"CONFIDENCE SCORE:\s*([\d.]+)", raw, re.IGNORECASE)
        if conf_m:
            try:
                confidence = max(0.0, min(1.0, float(conf_m.group(1))))
            except ValueError:
                pass

        # Calculate remaining resources
        used_teams = sum(a.rescue_teams for a in allocations)
        used_boats = sum(a.boats for a in allocations)
        used_med = sum(a.medical_kits for a in allocations)
        used_food = sum(a.food_supply_units for a in allocations)

        remaining = ResourceState(
            rescue_teams=max(0, resources.rescue_teams - used_teams),
            boats=max(0, resources.boats - used_boats),
            medical_kits=max(0, resources.medical_kits - used_med),
            food_supply_units=max(0, resources.food_supply_units - used_food),
        )

        return AllocationResult(
            allocations=allocations,
            remaining_resources=remaining,
            depleted_resources=depleted,
            trade_offs=trade_offs or "No explicit trade-offs documented.",
            confidence_score=confidence,
        )

    def _enforce_constraints(self, result: AllocationResult,
                              original: ResourceState) -> AllocationResult:
        """
        Clamp allocations so totals never exceed available supply.
        Also flag depleted resources.
        """
        resource_fields = ["rescue_teams", "boats", "medical_kits", "food_supply_units"]
        totals = {f: sum(getattr(a, f) for a in result.allocations)
                  for f in resource_fields}
        available = original.to_dict()

        for field in resource_fields:
            if totals[field] > available[field] and available[field] > 0:
                # Scale down proportionally
                scale = available[field] / totals[field]
                for alloc in result.allocations:
                    setattr(alloc, field, int(getattr(alloc, field) * scale))

        # Recompute remaining
        used = {f: sum(getattr(a, f) for a in result.allocations)
                for f in resource_fields}
        result.remaining_resources = ResourceState(
            rescue_teams=max(0, original.rescue_teams - used["rescue_teams"]),
            boats=max(0, original.boats - used["boats"]),
            medical_kits=max(0, original.medical_kits - used["medical_kits"]),
            food_supply_units=max(0, original.food_supply_units - used["food_supply_units"]),
        )

        # Flag depleted
        depleted = set(result.depleted_resources)
        for field in resource_fields:
            if result.remaining_resources.is_depleted(field):
                depleted.add(field)
        result.depleted_resources = list(depleted)

        return result
