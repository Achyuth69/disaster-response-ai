"""
agents/schemas.py — Pydantic v2 schemas for the REST API.
Separate from internal dataclasses — these are the public contract.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


# ── Request Schemas ──────────────────────────────────────────────────────────

class DisasterScenarioRequest(BaseModel):
    disaster_type: str = Field(
        default="flood",
        description="Type of disaster",
        examples=["flood", "earthquake", "cyclone", "tsunami", "wildfire", "landslide"],
    )
    location: str = Field(
        default="Hyderabad",
        description="City or region name",
        examples=["Hyderabad", "Mumbai", "Chennai"],
    )
    severity: int = Field(
        default=8,
        ge=1, le=10,
        description="Severity level 1-10",
    )
    time_elapsed_hours: float = Field(
        default=0.5,
        ge=0.0,
        description="Hours since disaster started",
    )
    weather_conditions: str = Field(
        default="Heavy rainfall",
        description="Current weather description",
    )
    num_cycles: int = Field(
        default=3,
        ge=1, le=10,
        description="Number of response cycles to run",
    )
    rescue_teams: int = Field(default=10, ge=1, le=100)
    boats: int = Field(default=5, ge=0, le=50)
    medical_kits: int = Field(default=100, ge=0, le=10000)
    food_supply_units: int = Field(default=200, ge=0, le=50000)
    chaos_enabled: bool = Field(default=True)
    lives_saved_metric: bool = Field(default=True)
    disagreement_scoring: bool = Field(default=True)

    @field_validator("disaster_type")
    @classmethod
    def validate_disaster_type(cls, v: str) -> str:
        allowed = {"flood", "earthquake", "cyclone", "tsunami", "wildfire", "landslide"}
        if v.lower() not in allowed:
            raise ValueError(f"disaster_type must be one of: {', '.join(sorted(allowed))}")
        return v.lower()


# ── Response Schemas ─────────────────────────────────────────────────────────

class ResourceStateResponse(BaseModel):
    rescue_teams: int
    boats: int
    medical_kits: int
    food_supply_units: int


class PriorityZoneResponse(BaseModel):
    zone_id: str
    name: str
    priority_score: float
    population_at_risk: int
    has_vulnerable_populations: bool
    geographic_constraints: list[str] = []


class ZoneAllocationResponse(BaseModel):
    zone_id: str
    rescue_teams: int
    boats: int
    medical_kits: int
    food_supply_units: int
    justification: str


class ChaosEventResponse(BaseModel):
    event_type: str
    description: str
    injected_at_cycle: int
    severity_multiplier: float
    is_compound: bool = False


class CycleResultResponse(BaseModel):
    cycle_num: int
    priority_zones: list[PriorityZoneResponse]
    team_assignments: dict[str, str]
    allocations: list[ZoneAllocationResponse]
    remaining_resources: ResourceStateResponse
    depleted_resources: list[str]
    public_message: str
    internal_message: str
    chaos_event: ChaosEventResponse
    avg_confidence: float
    lives_saved_estimate: Optional[int] = None
    disagreements: list[str] = []


class FinalReportResponse(BaseModel):
    session_token: str
    disaster_type: str
    location: str
    severity: int
    total_cycles: int
    audit_chain_hash: str
    audit_chain_valid: bool
    cycles: list[CycleResultResponse]
    total_lives_saved: Optional[int] = None
    disagreement_summary: Optional[str] = None
    circuit_breaker_warnings: list[str] = []
    generated_at: str


class RunStatusResponse(BaseModel):
    session_token: str
    status: str  # "running" | "completed" | "failed"
    current_cycle: int
    total_cycles: int
    elapsed_seconds: float
    lives_saved_so_far: int = 0
    message: str = ""


class HealthResponse(BaseModel):
    status: str
    version: str
    groq_configured: bool
    gemini_configured: bool
    knowledge_base_docs: int
    faiss_index_ready: bool
    uptime_seconds: float


class ErrorResponse(BaseModel):
    error: str
    detail: str
    session_token: Optional[str] = None


# ── WebSocket Message Schemas ─────────────────────────────────────────────────

class WSMessage(BaseModel):
    type: str  # "cycle_start" | "agent_update" | "chaos_event" | "cycle_complete" | "run_complete" | "error"
    session_token: str
    cycle_num: int = 0
    data: dict[str, Any] = {}
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
