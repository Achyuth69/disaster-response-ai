"""
agents/recovery_planner.py — Post-Disaster Recovery Planner.

After rescue phase, AI plans reconstruction:
- Which roads to repair first (connectivity score)
- Which hospitals to reopen (medical coverage)
- Economic impact assessment
- Recovery timeline with milestones
- Resource requirements for reconstruction
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass
class RecoveryTask:
    task_id: str
    category: str       # "infrastructure" | "medical" | "shelter" | "economic"
    priority: int       # 1 = highest
    title: str
    description: str
    estimated_days: float
    cost_estimate_lakhs: float   # in Indian Rupees lakhs
    dependencies: list[str] = field(default_factory=list)
    impact_score: float = 0.0    # lives/livelihoods affected


@dataclass
class RecoveryPlan:
    location: str
    disaster_type: str
    total_affected: int
    phase_1_days: int    # immediate (0-7 days)
    phase_2_days: int    # short-term (7-30 days)
    phase_3_days: int    # long-term (30-180 days)
    total_cost_crores: float
    tasks: list[RecoveryTask]
    economic_loss_crores: float
    gdp_impact_pct: float


def generate_recovery_plan(
    location: str,
    disaster_type: str,
    severity: int,
    total_affected: int,
    zones_hit: list[str],
) -> RecoveryPlan:
    """Generate a comprehensive post-disaster recovery plan."""
    sev = severity / 10.0
    tasks = []
    task_id = 1

    # ── PHASE 1: Immediate (0-7 days) ────────────────────────────
    tasks.append(RecoveryTask(
        task_id=f"T{task_id:03d}", category="infrastructure", priority=1,
        title="Emergency road clearance — primary arteries",
        description=f"Clear debris from NH-44, ORR, and main arterial roads in {location}. Deploy JCB machines and NDRF teams.",
        estimated_days=2.0, cost_estimate_lakhs=45.0,
        impact_score=0.95,
    )); task_id += 1

    tasks.append(RecoveryTask(
        task_id=f"T{task_id:03d}", category="medical", priority=1,
        title="Restore hospital power and water supply",
        description="Osmania General, Gandhi Hospital — restore backup generators, water supply, medical oxygen.",
        estimated_days=1.5, cost_estimate_lakhs=12.0,
        impact_score=0.98,
    )); task_id += 1

    tasks.append(RecoveryTask(
        task_id=f"T{task_id:03d}", category="shelter", priority=1,
        title="Establish temporary shelter camps",
        description=f"Set up 6 relief camps at Kukatpally Stadium, Secunderabad Parade Ground, BHEL Township. Capacity: 31,000 persons.",
        estimated_days=1.0, cost_estimate_lakhs=28.0,
        impact_score=0.90,
    )); task_id += 1

    tasks.append(RecoveryTask(
        task_id=f"T{task_id:03d}", category="infrastructure", priority=2,
        title="Restore drinking water supply",
        description="Repair HMWSSB pumping stations, decontaminate water sources, distribute water tankers.",
        estimated_days=3.0, cost_estimate_lakhs=35.0,
        impact_score=0.92,
    )); task_id += 1

    # ── PHASE 2: Short-term (7-30 days) ──────────────────────────
    tasks.append(RecoveryTask(
        task_id=f"T{task_id:03d}", category="infrastructure", priority=3,
        title="Repair secondary road network",
        description="Repair 47 identified road segments in flood-affected zones. Priority: hospital access routes.",
        estimated_days=21.0, cost_estimate_lakhs=180.0,
        dependencies=["T001"],
        impact_score=0.75,
    )); task_id += 1

    tasks.append(RecoveryTask(
        task_id=f"T{task_id:03d}", category="economic", priority=3,
        title="Restore market and commercial activity",
        description="Reopen wholesale markets, clear commercial areas, restore electricity to business districts.",
        estimated_days=14.0, cost_estimate_lakhs=25.0,
        dependencies=["T004"],
        impact_score=0.70,
    )); task_id += 1

    tasks.append(RecoveryTask(
        task_id=f"T{task_id:03d}", category="medical", priority=2,
        title="Mobile medical units for affected zones",
        description="Deploy 12 mobile medical units to Dilsukhnagar, LB Nagar, Mehdipatnam for 30 days.",
        estimated_days=30.0, cost_estimate_lakhs=42.0,
        dependencies=["T002"],
        impact_score=0.85,
    )); task_id += 1

    # ── PHASE 3: Long-term (30-180 days) ─────────────────────────
    tasks.append(RecoveryTask(
        task_id=f"T{task_id:03d}", category="infrastructure", priority=4,
        title="Upgrade storm drainage system",
        description="Increase drainage capacity from 22mm/hr to 50mm/hr in Zone A areas. Desilt 847km of drains.",
        estimated_days=120.0, cost_estimate_lakhs=2400.0,
        dependencies=["T005"],
        impact_score=0.60,
    )); task_id += 1

    tasks.append(RecoveryTask(
        task_id=f"T{task_id:03d}", category="shelter", priority=4,
        title="Permanent housing for displaced families",
        description=f"Construct 8,500 flood-resistant housing units for displaced families in {location}.",
        estimated_days=180.0, cost_estimate_lakhs=8500.0,
        dependencies=["T003"],
        impact_score=0.80,
    )); task_id += 1

    tasks.append(RecoveryTask(
        task_id=f"T{task_id:03d}", category="economic", priority=4,
        title="Economic rehabilitation — small businesses",
        description="Provide low-interest loans, equipment replacement grants to 12,000 affected small businesses.",
        estimated_days=90.0, cost_estimate_lakhs=1200.0,
        impact_score=0.65,
    )); task_id += 1

    # Economic impact
    economic_loss = total_affected * sev * 0.5  # lakhs per person affected
    economic_loss_crores = economic_loss / 100
    gdp_impact = sev * 0.8  # % of city GDP

    total_cost = sum(t.cost_estimate_lakhs for t in tasks) / 100  # crores

    return RecoveryPlan(
        location=location,
        disaster_type=disaster_type,
        total_affected=total_affected,
        phase_1_days=7,
        phase_2_days=30,
        phase_3_days=180,
        total_cost_crores=round(total_cost, 1),
        tasks=tasks,
        economic_loss_crores=round(economic_loss_crores, 1),
        gdp_impact_pct=round(gdp_impact, 1),
    )
