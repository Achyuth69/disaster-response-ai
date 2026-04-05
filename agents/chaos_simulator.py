"""
agents/chaos_simulator.py — Adaptive Chaos Simulator.
Injects unexpected events between response cycles.
Difficulty scales with agent confidence scores.
Enforces no-consecutive-repeat rule.
Supports compound events at high severity multipliers.
"""
from __future__ import annotations

import copy
import random
from typing import Optional

from agents.models import ChaosEvent, DisasterContext


class ChaosSimulator:
    """
    Adaptive chaos injection engine.

    Difficulty scaling:
    - avg_confidence > 0.8 → multiplier += 0.2 (harder)
    - avg_confidence < 0.4 → multiplier -= 0.1 (easier)
    - multiplier > 1.5 → may inject compound (secondary) event
    """

    EVENTS = [
        "water_level_rise",
        "road_blockage",
        "resource_failure",
        "new_high_risk_zone",
        "communication_breakdown",
    ]

    SEVERITY_MULTIPLIER_MIN = 0.5
    SEVERITY_MULTIPLIER_MAX = 2.0

    _EVENT_DESCRIPTIONS = {
        "water_level_rise": [
            "Musi River gauge rose by {delta:.1f}m — Chaderghat Bridge now closed",
            "Sudden water level surge in Hussain Sagar — overflow imminent",
            "Flash flood warning: water level increased {delta:.1f}m in 30 minutes",
        ],
        "road_blockage": [
            "NH-44 blocked near Secunderabad due to debris and flooding",
            "Inner Ring Road underpass at Mehdipatnam submerged — impassable",
            "Attapur Bridge closed — structural damage reported",
            "Multiple road blockages reported in LB Nagar — alternate routes required",
        ],
        "resource_failure": [
            "2 rescue boats reported engine failure — out of service",
            "Medical supply truck overturned on NH-65 — 30 kits lost",
            "Backup generator at Osmania Hospital failed — patient evacuation needed",
            "Communication equipment failure in Team-3 and Team-7",
        ],
        "new_high_risk_zone": [
            "New high-risk zone identified: Vanasthalipuram — 48,000 residents at risk",
            "Boduppal industrial area flooding — chemical contamination risk",
            "Chaitanyapuri slum area inundated — 42,000 residents need immediate rescue",
            "Tarnaka railway colony flooded — 500 residents stranded on rooftops",
        ],
        "communication_breakdown": [
            "Cell tower failure in south Hyderabad — 40% of teams unreachable",
            "Radio communication disrupted — switching to satellite backup",
            "Internet outage affecting coordination systems — manual protocols activated",
        ],
    }

    def __init__(self, enabled: bool = True, seed: Optional[int] = None):
        self._enabled = enabled
        self._last_event: Optional[str] = None
        self._severity_multiplier: float = 1.0
        self._cycle_count = 0
        if seed is not None:
            random.seed(seed)

    @property
    def severity_multiplier(self) -> float:
        return self._severity_multiplier

    def inject(self, context: DisasterContext,
               avg_confidence: float = 0.7) -> tuple[ChaosEvent, DisasterContext]:
        """
        Inject a chaos event and return (ChaosEvent, updated_context).
        When disabled, returns a sentinel 'none' event and unchanged context.
        """
        self._cycle_count += 1

        if not self._enabled:
            sentinel = ChaosEvent(
                event_type="none",
                description="Chaos simulation disabled.",
                injected_at_cycle=self._cycle_count,
                severity_multiplier=0.0,
            )
            return sentinel, context

        self._adapt_difficulty(avg_confidence)
        event_type = self._select_event()
        new_context = copy.deepcopy(context)

        primary_event, new_context = self._apply_event(
            event_type, new_context, self._severity_multiplier
        )
        primary_event.injected_at_cycle = self._cycle_count

        # Compound event at high multiplier
        if self._severity_multiplier > 1.5 and random.random() < 0.4:
            secondary_type = self._select_event(exclude=event_type)
            secondary_event, new_context = self._apply_event(
                secondary_type, new_context, self._severity_multiplier * 0.5
            )
            secondary_event.injected_at_cycle = self._cycle_count
            primary_event.is_compound = True
            primary_event.secondary_event = secondary_event

        self._last_event = event_type
        new_context.active_chaos_event = primary_event
        return primary_event, new_context

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _adapt_difficulty(self, avg_confidence: float) -> None:
        if avg_confidence > 0.8:
            self._severity_multiplier = min(
                self._severity_multiplier + 0.2,
                self.SEVERITY_MULTIPLIER_MAX,
            )
        elif avg_confidence < 0.4:
            self._severity_multiplier = max(
                self._severity_multiplier - 0.1,
                self.SEVERITY_MULTIPLIER_MIN,
            )

    def _select_event(self, exclude: Optional[str] = None) -> str:
        """Select event type, enforcing no-consecutive-repeat rule."""
        excluded = set()
        if self._last_event:
            excluded.add(self._last_event)
        if exclude:
            excluded.add(exclude)

        candidates = [e for e in self.EVENTS if e not in excluded]
        if not candidates:
            candidates = [e for e in self.EVENTS if e != exclude]
        return random.choice(candidates)

    def _apply_event(self, event_type: str, context: DisasterContext,
                     multiplier: float) -> tuple[ChaosEvent, DisasterContext]:
        descriptions = self._EVENT_DESCRIPTIONS.get(event_type, ["Unknown event"])
        description = random.choice(descriptions)
        context_delta: dict = {}

        if event_type == "water_level_rise":
            delta = round(random.uniform(0.5, 2.0) * multiplier, 1)
            description = description.format(delta=delta)
            context.water_level_meters = getattr(context, "water_level_meters", 0) + delta
            new_severity = min(10, context.severity + max(1, int(multiplier)))
            context_delta = {"water_level_delta": delta, "severity_delta": new_severity - context.severity}
            context.severity = new_severity

        elif event_type == "road_blockage":
            blocked_road = description.split("—")[0].strip().replace("blocked", "").strip()
            if not hasattr(context, "blocked_roads") or context.blocked_roads is None:
                context.blocked_roads = []
            context.blocked_roads.append(blocked_road)
            context_delta = {"new_blocked_road": blocked_road}

        elif event_type == "resource_failure":
            context_delta = {"resource_failure_description": description}

        elif event_type == "new_high_risk_zone":
            zone_name = description.split(":")[1].split("—")[0].strip() if ":" in description else "Unknown Zone"
            if not hasattr(context, "new_risk_zones") or context.new_risk_zones is None:
                context.new_risk_zones = []
            context.new_risk_zones.append(zone_name)
            context_delta = {"new_risk_zone": zone_name}

        elif event_type == "communication_breakdown":
            context_delta = {"communication_breakdown": True}

        event = ChaosEvent(
            event_type=event_type,
            description=description,
            injected_at_cycle=0,  # set by caller
            severity_multiplier=multiplier,
            context_delta=context_delta,
        )
        return event, context
