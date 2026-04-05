"""
agents/models.py — All data models, dataclasses, and custom exceptions
for the Disaster Response AI System.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when input data fails validation (e.g. severity out of range)."""


class ConfigurationError(Exception):
    """Raised when required configuration (API keys, env vars) is missing."""


class SecurityWarning(Exception):
    """Raised when a security concern is detected (prompt injection, key exposure)."""


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open and the agent is bypassed."""


# ---------------------------------------------------------------------------
# Core Context & Resources
# ---------------------------------------------------------------------------

@dataclass
class DisasterContext:
    disaster_type: str          # "flood" | "earthquake" | "cyclone"
    location: str
    severity: int               # 1–10
    time_elapsed_hours: float
    weather_conditions: str
    session_token: str = ""
    active_chaos_event: Optional[ChaosEvent] = None
    water_level_meters: float = 0.0
    blocked_roads: list[str] = field(default_factory=list)
    new_risk_zones: list[str] = field(default_factory=list)


@dataclass
class ResourceState:
    rescue_teams: int
    boats: int
    medical_kits: int
    food_supply_units: int

    def is_depleted(self, resource: str) -> bool:
        return getattr(self, resource, 1) <= 0

    def to_dict(self) -> dict:
        return {
            "rescue_teams": self.rescue_teams,
            "boats": self.boats,
            "medical_kits": self.medical_kits,
            "food_supply_units": self.food_supply_units,
        }


# ---------------------------------------------------------------------------
# Agent Output Models
# ---------------------------------------------------------------------------

@dataclass
class PriorityZone:
    zone_id: str
    name: str
    priority_score: float       # composite: population × severity × vulnerability
    population_at_risk: int
    has_vulnerable_populations: bool
    geographic_constraints: list[str] = field(default_factory=list)
    cleared: bool = False       # True once confirmed cleared via agent memory


@dataclass
class DataSummary:
    affected_zones: list[str]
    nearest_medical_facilities: list[str]
    estimated_population_at_risk: int
    geographic_constraints: list[str]
    confidence_score: float = 1.0
    data_gaps: list[str] = field(default_factory=list)


@dataclass
class RescuePlan:
    priority_zones: list[PriorityZone]           # sorted descending by priority_score
    team_assignments: dict[str, str]              # team_id → zone_id (injective)
    estimated_travel_times: dict[str, float]      # zone_id → hours
    route_descriptions: dict[str, str]            # zone_id → route text
    confidence_score: float = 1.0
    consensus_disagreement: str = ""


@dataclass
class ZoneAllocation:
    zone_id: str
    rescue_teams: int
    boats: int
    medical_kits: int
    food_supply_units: int
    justification: str


@dataclass
class AllocationResult:
    allocations: list[ZoneAllocation]
    remaining_resources: ResourceState
    depleted_resources: list[str]                 # resource names at zero
    trade_offs: str
    confidence_score: float = 1.0
    consensus_disagreement: str = ""


@dataclass
class CommunicationOutput:
    public_message: str
    internal_message: str
    is_fallback: bool = False                     # True when communication_breakdown active
    confidence_score: float = 1.0


# ---------------------------------------------------------------------------
# Chaos & Audit Models
# ---------------------------------------------------------------------------

@dataclass
class ChaosEvent:
    event_type: str             # one of ChaosSimulator.EVENTS or "none"
    description: str
    injected_at_cycle: int
    severity_multiplier: float = 1.0
    context_delta: dict = field(default_factory=dict)
    is_compound: bool = False
    secondary_event: Optional[ChaosEvent] = None


@dataclass
class AuditEntry:
    cycle: int
    agent: str
    timestamp: str
    input_hash: str
    output_hash: str
    confidence: float
    prev_hash: str
    hmac_sig: str


# ---------------------------------------------------------------------------
# Cycle & Report Models
# ---------------------------------------------------------------------------

@dataclass
class CycleResult:
    cycle_num: int
    data_summary: DataSummary
    rescue_plan: RescuePlan
    allocation_result: AllocationResult
    communication_output: CommunicationOutput
    chaos_event: ChaosEvent
    avg_confidence: float = 1.0
    lives_saved_estimate: Optional[int] = None
    disagreements: list[str] = field(default_factory=list)
    inter_provider_disagreements: list[str] = field(default_factory=list)


@dataclass
class OrchestratorConfig:
    num_cycles: int                               # -1 = unlimited (continuous mode)
    rescue_teams: int = 10
    boats: int = 5
    medical_kits: int = 100
    food_supply_units: int = 200
    chaos_enabled: bool = True
    lives_saved_metric: bool = True
    disagreement_scoring: bool = True
    dashboard_enabled: bool = True
    resume: bool = False
    output_dir: str = "output"
    checkpoint_dir: str = "checkpoints"
    timeout_seconds: int = 60
    circuit_breaker_threshold: int = 3


@dataclass
class FinalReport:
    context: DisasterContext
    cycles: list[CycleResult]
    final_rescue_plan: RescuePlan
    final_allocation: AllocationResult
    final_communication: CommunicationOutput
    latest_chaos_event: Optional[ChaosEvent]
    audit_chain_hash: str
    session_token: str
    total_lives_saved: Optional[int] = None
    disagreement_summary: Optional[str] = None
    circuit_breaker_warnings: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Consensus & Memory Support Models
# ---------------------------------------------------------------------------

@dataclass
class ConsensusResult:
    primary_response: str
    secondary_response: str
    agreed: bool
    final_response: str
    disagreement_note: str = ""


@dataclass
class AgentMemoryEntry:
    cycle_num: int
    agent_name: str
    key: str
    value: Any


@dataclass
class CheckpointState:
    session_token: str
    cycle_num: int
    context: DisasterContext
    resources: ResourceState
    cycle_results: list[CycleResult]
    audit_entries: list[AuditEntry]
    chaos_severity_multiplier: float
    memory_data: dict = field(default_factory=dict)
