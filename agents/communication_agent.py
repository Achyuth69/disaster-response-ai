"""
agents/communication_agent.py — Communication Agent.
Generates public alerts and internal tactical messages.
Switches to ≤50-word fallback during communication breakdown events.
"""
from __future__ import annotations

import re
from typing import Optional

from agents.models import (
    AllocationResult, ChaosEvent, CommunicationOutput,
    DisasterContext, RescuePlan,
)


SYSTEM_PROMPT = """You are the Communication Agent for a disaster response system.
Your job is to generate clear, calm, and authoritative communications.
Public messages must be actionable and panic-free.
Internal messages must be precise and tactical.
Never speculate — only state confirmed information."""

FALLBACK_SYSTEM_PROMPT = """You are the Communication Agent operating under
COMMUNICATION BREAKDOWN conditions. Generate ULTRA-SHORT emergency messages.
Each message MUST be 50 words or fewer. Be direct and critical-info-only."""


def _build_comms_prompt(context: DisasterContext, rescue_plan: RescuePlan,
                         allocation: AllocationResult,
                         chaos_event: Optional[ChaosEvent],
                         memory_context: str) -> str:
    top_zones = rescue_plan.priority_zones[:3]
    zones_text = ", ".join(z.name for z in top_zones)

    alloc_summary = "\n".join(
        f"  {a.zone_id}: {a.rescue_teams} teams, {a.boats} boats, "
        f"{a.medical_kits} med kits, {a.food_supply_units} food units"
        for a in allocation.allocations[:5]
    ) or "  Allocation pending"

    chaos_text = ""
    if chaos_event and chaos_event.event_type != "none":
        chaos_text = (
            f"\n⚡ CHAOS EVENT: {chaos_event.event_type.upper()} — "
            f"{chaos_event.description}\nRevise messages to reflect this update."
        )

    return f"""DISASTER CONTEXT:
Type: {context.disaster_type} | Location: {context.location}
Severity: {context.severity}/10 | Time Elapsed: {context.time_elapsed_hours}h
Weather: {context.weather_conditions}
{chaos_text}

RESCUE PLAN SUMMARY:
Priority Zones: {zones_text}
Teams Deployed: {len(rescue_plan.team_assignments)}

RESOURCE ALLOCATION:
{alloc_summary}

{memory_context}

GENERATE TWO MESSAGES:

1. PUBLIC MESSAGE — calm, clear, actionable. Include:
   - Which areas are affected
   - Evacuation instructions (where to go, which routes)
   - Nearest shelter locations
   - Emergency contact numbers (use 100 for police, 108 for ambulance, 101 for fire)
   - What NOT to do

2. INTERNAL MESSAGE — tactical, precise. Include:
   - Team assignments and zone coordinates
   - Resource loadouts per team
   - Priority order of operations
   - Communication protocols
   - Contingency if primary route blocked

OUTPUT FORMAT:
PUBLIC MESSAGE:
[message text]

INTERNAL MESSAGE:
[message text]

CONFIDENCE SCORE: [0.0-1.0]"""


def _build_fallback_prompt(context: DisasterContext) -> str:
    return f"""EMERGENCY — COMMUNICATION BREAKDOWN ACTIVE.
Disaster: {context.disaster_type} in {context.location}. Severity: {context.severity}/10.

Generate TWO ultra-short messages (≤50 words each):

PUBLIC MESSAGE:
[≤50 words: most critical evacuation instruction only]

INTERNAL MESSAGE:
[≤50 words: most critical tactical instruction only]"""


class CommunicationAgent:
    """
    Communication Agent — generates public and internal messages.
    """

    def __init__(self, llm_client):
        self._llm = llm_client

    def invoke(self, context: DisasterContext, rescue_plan: RescuePlan,
               allocation: AllocationResult,
               chaos_event: Optional[ChaosEvent] = None,
               memory=None) -> CommunicationOutput:
        """Generate communication messages."""
        is_breakdown = (
            chaos_event is not None
            and chaos_event.event_type == "communication_breakdown"
        )

        if is_breakdown:
            prompt = _build_fallback_prompt(context)
            raw = self._llm.complete(prompt, FALLBACK_SYSTEM_PROMPT)
            output = self._parse_response(raw)
            output.is_fallback = True
            # Enforce 50-word limit
            output.public_message = self._truncate_to_words(
                output.public_message, 50
            )
            output.internal_message = self._truncate_to_words(
                output.internal_message, 50
            )
        else:
            memory_context = self._build_memory_context(memory)
            prompt = _build_comms_prompt(
                context, rescue_plan, allocation, chaos_event, memory_context
            )
            raw = self._llm.complete(prompt, SYSTEM_PROMPT)
            output = self._parse_response(raw)

        # Store to memory for continuity
        if memory:
            memory.store("communication_agent", "last_public_message",
                         output.public_message,
                         getattr(context, "_cycle_num", 0))

        return output

    def _build_memory_context(self, memory) -> str:
        if not memory:
            return ""
        prev = memory.recall_latest("communication_agent", "last_public_message")
        if not prev:
            return ""
        return f"\nPREVIOUS PUBLIC MESSAGE (avoid repetition):\n{prev[:200]}..."

    def _parse_response(self, raw: str) -> CommunicationOutput:
        public_m = re.search(
            r"PUBLIC MESSAGE:\s*(.+?)(?:INTERNAL MESSAGE:|CONFIDENCE SCORE:|$)",
            raw, re.DOTALL | re.IGNORECASE
        )
        internal_m = re.search(
            r"INTERNAL MESSAGE:\s*(.+?)(?:CONFIDENCE SCORE:|$)",
            raw, re.DOTALL | re.IGNORECASE
        )
        conf_m = re.search(r"CONFIDENCE SCORE:\s*([\d.]+)", raw, re.IGNORECASE)

        public_msg = public_m.group(1).strip() if public_m else (
            "ALERT: Disaster response operations are underway. "
            "Follow official instructions. Call 108 for emergencies."
        )
        internal_msg = internal_m.group(1).strip() if internal_m else (
            "All teams: proceed to assigned zones per rescue plan. "
            "Maintain radio contact every 30 minutes."
        )

        confidence = 0.8
        if conf_m:
            try:
                confidence = max(0.0, min(1.0, float(conf_m.group(1))))
            except ValueError:
                pass

        return CommunicationOutput(
            public_message=public_msg,
            internal_message=internal_msg,
            is_fallback=False,
            confidence_score=confidence,
        )

    def _truncate_to_words(self, text: str, max_words: int) -> str:
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]) + "..."
