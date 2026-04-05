"""tests/test_models.py — Unit tests for data models and exceptions."""
import pytest
from agents.models import (
    AllocationResult, ChaosEvent, CommunicationOutput, ConfigurationError,
    CycleResult, DataSummary, DisasterContext, FinalReport, OrchestratorConfig,
    PriorityZone, ResourceState, RescuePlan, ValidationError, ZoneAllocation,
)


def make_context(**kwargs):
    defaults = dict(
        disaster_type="flood", location="Hyderabad", severity=8,
        time_elapsed_hours=1.0, weather_conditions="Heavy rain",
    )
    defaults.update(kwargs)
    return DisasterContext(**defaults)


def make_resources(**kwargs):
    defaults = dict(rescue_teams=10, boats=5, medical_kits=100, food_supply_units=200)
    defaults.update(kwargs)
    return ResourceState(**defaults)


class TestDisasterContext:
    def test_defaults(self):
        ctx = make_context()
        assert ctx.session_token == ""
        assert ctx.active_chaos_event is None
        assert ctx.blocked_roads == []

    def test_fields(self):
        ctx = make_context(severity=5, location="Mumbai")
        assert ctx.severity == 5
        assert ctx.location == "Mumbai"


class TestResourceState:
    def test_is_depleted_true(self):
        r = make_resources(boats=0)
        assert r.is_depleted("boats") is True

    def test_is_depleted_false(self):
        r = make_resources(boats=3)
        assert r.is_depleted("boats") is False

    def test_to_dict(self):
        r = make_resources()
        d = r.to_dict()
        assert d["rescue_teams"] == 10
        assert d["boats"] == 5


class TestPriorityZone:
    def test_defaults(self):
        z = PriorityZone("z1", "Dilsukhnagar", 0.9, 50000, True)
        assert z.cleared is False
        assert z.geographic_constraints == []


class TestDataSummary:
    def test_defaults(self):
        ds = DataSummary(
            affected_zones=["Zone A"],
            nearest_medical_facilities=["Hospital X"],
            estimated_population_at_risk=10000,
            geographic_constraints=[],
        )
        assert ds.confidence_score == 1.0
        assert ds.data_gaps == []


class TestRescuePlan:
    def test_defaults(self):
        plan = RescuePlan(
            priority_zones=[],
            team_assignments={},
            estimated_travel_times={},
            route_descriptions={},
        )
        assert plan.confidence_score == 1.0
        assert plan.consensus_disagreement == ""


class TestAllocationResult:
    def test_depleted_resources_default(self):
        r = make_resources()
        result = AllocationResult(
            allocations=[],
            remaining_resources=r,
            depleted_resources=[],
            trade_offs="none",
        )
        assert result.depleted_resources == []


class TestChaosEvent:
    def test_sentinel(self):
        evt = ChaosEvent(
            event_type="none",
            description="disabled",
            injected_at_cycle=1,
        )
        assert evt.is_compound is False
        assert evt.secondary_event is None


class TestOrchestratorConfig:
    def test_defaults(self):
        cfg = OrchestratorConfig(num_cycles=3)
        assert cfg.chaos_enabled is True
        assert cfg.lives_saved_metric is True
        assert cfg.timeout_seconds == 60


class TestCustomExceptions:
    def test_validation_error(self):
        with pytest.raises(ValidationError):
            raise ValidationError("severity out of range")

    def test_configuration_error(self):
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("missing API key")
