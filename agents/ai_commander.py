"""
agents/ai_commander.py — Autonomous AI Commander.
World-first: AI that makes autonomous operational decisions when confidence > 95%.
Overrides, escalates, or defers human decisions based on real-time analysis.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CommandDecision:
    decision_id: str
    decision_type: str          # "override" | "escalate" | "defer" | "autonomous"
    action: str
    rationale: str
    confidence: float           # 0.0 - 1.0
    authority_level: str        # "AI_AUTONOMOUS" | "AI_RECOMMEND" | "HUMAN_REQUIRED"
    affected_zones: list[str]
    resource_delta: dict        # changes to resources
    lives_impact_estimate: int
    timestamp: str
    overrides_human: bool = False
    urgency: str = "NORMAL"     # "CRITICAL" | "HIGH" | "NORMAL"


@dataclass
class CommanderState:
    session_token: str
    total_decisions: int = 0
    autonomous_decisions: int = 0
    overrides: int = 0
    lives_saved_by_ai: int = 0
    avg_confidence: float = 0.0
    decisions: list[CommandDecision] = field(default_factory=list)


# In-memory commander states
_commander_states: dict[str, CommanderState] = {}


def get_or_create_state(session_token: str) -> CommanderState:
    if session_token not in _commander_states:
        _commander_states[session_token] = CommanderState(session_token=session_token)
    return _commander_states[session_token]


def run_ai_commander(
    session_token: str,
    disaster_type: str,
    severity: int,
    location: str,
    cycle_num: int,
    zones: list[dict],
    resources: dict,
    avg_confidence: float,
    chaos_event: Optional[dict] = None,
    survival_data: Optional[dict] = None,
) -> dict:
    """
    Autonomous AI Commander — analyzes situation and makes decisions.
    At confidence > 0.95: autonomous action (no human needed)
    At confidence 0.80-0.95: strong recommendation
    Below 0.80: defer to human
    """
    import uuid
    import random

    state = get_or_create_state(session_token)
    decisions = []
    timestamp = datetime.utcnow().isoformat()

    # ── Decision 1: Resource Reallocation ────────────────────────────────────
    critical_zones = [z for z in zones if z.get("score", 0) > 0.8]
    depleted = [k for k, v in resources.items() if v <= 0]

    if critical_zones and depleted:
        conf = min(0.98, avg_confidence + 0.15)
        d = CommandDecision(
            decision_id=str(uuid.uuid4())[:8],
            decision_type="autonomous" if conf > 0.95 else "escalate",
            action=f"Emergency reallocation: redirect all available teams to {critical_zones[0].get('name','Zone 1')}",
            rationale=f"Critical zone detected with score {critical_zones[0].get('score',0):.2f}. Resources {depleted} depleted. AI confidence {conf:.0%}.",
            confidence=conf,
            authority_level="AI_AUTONOMOUS" if conf > 0.95 else "AI_RECOMMEND",
            affected_zones=[z.get("name","") for z in critical_zones[:3]],
            resource_delta={"rescue_teams": -2, "medical_kits": -20},
            lives_impact_estimate=int(critical_zones[0].get("population", 10000) * 0.02),
            timestamp=timestamp,
            overrides_human=conf > 0.95,
            urgency="CRITICAL",
        )
        decisions.append(d)

    # ── Decision 2: Chaos Response ────────────────────────────────────────────
    if chaos_event and chaos_event.get("type") not in ("none", None):
        chaos_type = chaos_event.get("type", "")
        conf = 0.97 if severity >= 8 else 0.88
        action_map = {
            "water_level_rise": "Activate elevated rescue protocol — switch to boat-only operations in flooded sectors",
            "road_blockage": "Reroute all ground teams via alternate corridors — activate aerial support",
            "resource_failure": "Emergency procurement order triggered — contact backup suppliers",
            "communication_breakdown": "Switch to radio mesh network — deploy signal relay drones",
            "new_high_risk_zone": "Immediate zone priority upgrade — reallocate 3 teams",
        }
        action = action_map.get(chaos_type, f"Adaptive response to {chaos_type} event")
        d = CommandDecision(
            decision_id=str(uuid.uuid4())[:8],
            decision_type="autonomous" if conf > 0.95 else "override",
            action=action,
            rationale=f"Chaos event '{chaos_type}' detected at cycle {cycle_num}. Severity multiplier ×{chaos_event.get('multiplier',1.0):.1f}. Autonomous response triggered.",
            confidence=conf,
            authority_level="AI_AUTONOMOUS" if conf > 0.95 else "AI_RECOMMEND",
            affected_zones=[z.get("name","") for z in zones[:2]],
            resource_delta={},
            lives_impact_estimate=int(sum(z.get("population",0) for z in zones[:2]) * 0.015),
            timestamp=timestamp,
            overrides_human=conf > 0.95,
            urgency="CRITICAL" if conf > 0.95 else "HIGH",
        )
        decisions.append(d)

    # ── Decision 3: Survival-based prioritization ─────────────────────────────
    if survival_data:
        critical_surv = [z for z in survival_data.get("zones", []) if z.get("minutes_to_critical", 999) < 20]
        if critical_surv:
            conf = 0.99  # near-certain when survival data shows imminent death
            d = CommandDecision(
                decision_id=str(uuid.uuid4())[:8],
                decision_type="autonomous",
                action=f"OVERRIDE: Immediate deployment to {critical_surv[0].get('zone_name','critical zone')} — survival window {critical_surv[0].get('minutes_to_critical',0):.0f} minutes",
                rationale=f"Survival engine shows {len(critical_surv)} zone(s) will reach critical threshold in <20 minutes. AI override of current deployment plan.",
                confidence=conf,
                authority_level="AI_AUTONOMOUS",
                affected_zones=[z.get("zone_name","") for z in critical_surv],
                resource_delta={"rescue_teams": -3},
                lives_impact_estimate=sum(z.get("estimated_saveable", 0) for z in critical_surv),
                timestamp=timestamp,
                overrides_human=True,
                urgency="CRITICAL",
            )
            decisions.append(d)

    # ── Decision 4: Proactive resupply ────────────────────────────────────────
    low_resources = {k: v for k, v in resources.items() if 0 < v < 20}
    if low_resources:
        conf = 0.93
        res_list = ", ".join(f"{k}={v}" for k, v in low_resources.items())
        d = CommandDecision(
            decision_id=str(uuid.uuid4())[:8],
            decision_type="autonomous",
            action=f"Proactive resupply order placed: {res_list} — estimated arrival 45 minutes",
            rationale=f"Predictive depletion model shows {res_list} will reach zero within 1 cycle. Ordering now prevents critical gap.",
            confidence=conf,
            authority_level="AI_AUTONOMOUS",
            affected_zones=[],
            resource_delta={k: 50 for k in low_resources},
            lives_impact_estimate=int(sum(low_resources.values()) * 8),
            timestamp=timestamp,
            overrides_human=False,
            urgency="HIGH",
        )
        decisions.append(d)

    # ── Decision 5: Cycle strategy ────────────────────────────────────────────
    if cycle_num > 1 and avg_confidence < 0.5:
        conf = 0.91
        d = CommandDecision(
            decision_id=str(uuid.uuid4())[:8],
            decision_type="escalate",
            action="Request additional intelligence — deploy reconnaissance teams before next cycle",
            rationale=f"Average agent confidence dropped to {avg_confidence:.0%}. Insufficient data for reliable decisions. Recommend intelligence gathering pause.",
            confidence=conf,
            authority_level="AI_RECOMMEND",
            affected_zones=[],
            resource_delta={},
            lives_impact_estimate=0,
            timestamp=timestamp,
            overrides_human=False,
            urgency="NORMAL",
        )
        decisions.append(d)

    # Update state
    state.total_decisions += len(decisions)
    state.autonomous_decisions += sum(1 for d in decisions if d.authority_level == "AI_AUTONOMOUS")
    state.overrides += sum(1 for d in decisions if d.overrides_human)
    state.lives_saved_by_ai += sum(d.lives_impact_estimate for d in decisions)
    state.decisions.extend(decisions)
    if decisions:
        state.avg_confidence = sum(d.confidence for d in decisions) / len(decisions)

    return {
        "session_token": session_token,
        "cycle_num": cycle_num,
        "computed_at": timestamp,
        "ai_authority_level": "AUTONOMOUS" if avg_confidence > 0.95 else "ADVISORY",
        "overall_confidence": avg_confidence,
        "decisions": [
            {
                "decision_id": d.decision_id,
                "type": d.decision_type,
                "action": d.action,
                "rationale": d.rationale,
                "confidence": round(d.confidence * 100, 1),
                "authority": d.authority_level,
                "urgency": d.urgency,
                "affected_zones": d.affected_zones,
                "lives_impact": d.lives_impact_estimate,
                "overrides_human": d.overrides_human,
                "timestamp": d.timestamp,
                "color": "#ff2020" if d.urgency == "CRITICAL" else "#ff6600" if d.urgency == "HIGH" else "#00ccff",
            }
            for d in decisions
        ],
        "summary": {
            "total_decisions": len(decisions),
            "autonomous": sum(1 for d in decisions if d.authority_level == "AI_AUTONOMOUS"),
            "overrides": sum(1 for d in decisions if d.overrides_human),
            "total_lives_impact": sum(d.lives_impact_estimate for d in decisions),
            "critical_actions": sum(1 for d in decisions if d.urgency == "CRITICAL"),
        },
        "session_totals": {
            "total_decisions": state.total_decisions,
            "autonomous_decisions": state.autonomous_decisions,
            "overrides": state.overrides,
            "lives_saved_by_ai": state.lives_saved_by_ai,
        },
    }
