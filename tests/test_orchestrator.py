"""tests/test_orchestrator.py — Unit tests for Orchestrator."""
import pytest
from unittest.mock import MagicMock, patch
from agents.models import (
    AllocationResult, ChaosEvent, CommunicationOutput, DataSummary,
    DisasterContext, OrchestratorConfig, PriorityZone, ResourceState,
    RescuePlan, ValidationError, ZoneAllocation,
)
from agents.orchestrator import Orchestrator


def make_context(severity=8, disaster_type="flood"):
    return DisasterContext(
        disaster_type=disaster_type, location="Hyderabad",
        severity=severity, time_elapsed_hours=1.0,
        weather_conditions="Heavy rain",
    )


def make_config(cycles=2, **kwargs):
    defaults = dict(
        num_cycles=cycles, rescue_teams=10, boats=5,
        medical_kits=100, food_supply_units=200,
        chaos_enabled=False, lives_saved_metric=True,
        disagreement_scoring=True, dashboard_enabled=False,
        timeout_seconds=30,
    )
    defaults.update(kwargs)
    return OrchestratorConfig(**defaults)


def make_mock_data_summary():
    return DataSummary(
        affected_zones=["Dilsukhnagar", "LB Nagar"],
        nearest_medical_facilities=["Gandhi Hospital"],
        estimated_population_at_risk=100000,
        geographic_constraints=[],
        confidence_score=0.85,
    )


def make_mock_rescue_plan():
    zones = [
        PriorityZone("z1", "Dilsukhnagar", 0.9, 50000, True),
        PriorityZone("z2", "LB Nagar", 0.8, 40000, True),
    ]
    return RescuePlan(
        priority_zones=zones,
        team_assignments={"Team-1": "z1", "Team-2": "z2"},
        estimated_travel_times={"z1": 0.5, "z2": 0.8},
        route_descriptions={"z1": "Via NH-44", "z2": "Via ORR"},
        confidence_score=0.88,
    )


def make_mock_allocation():
    remaining = ResourceState(rescue_teams=6, boats=3, medical_kits=60, food_supply_units=120)
    return AllocationResult(
        allocations=[
            ZoneAllocation("z1", 2, 1, 20, 40, "High priority"),
            ZoneAllocation("z2", 2, 1, 20, 40, "High priority"),
        ],
        remaining_resources=remaining,
        depleted_resources=[],
        trade_offs="Zones 3-5 not served due to resource constraints.",
        confidence_score=0.82,
    )


def make_mock_comms():
    return CommunicationOutput(
        public_message="ALERT: Flood in Hyderabad. Evacuate to Kukatpally Stadium.",
        internal_message="Team-1 to Dilsukhnagar via NH-44. Team-2 to LB Nagar via ORR.",
        confidence_score=0.90,
    )


def make_mock_chaos_event(cycle=1):
    return ChaosEvent(
        event_type="none",
        description="Chaos disabled",
        injected_at_cycle=cycle,
        severity_multiplier=0.0,
    )


def build_orchestrator(cycles=2, severity=8, **config_kwargs):
    ctx = make_context(severity=severity)
    cfg = make_config(cycles=cycles, **config_kwargs)

    data_agent = MagicMock()
    data_agent.invoke.return_value = make_mock_data_summary()

    rescue_planner = MagicMock()
    rescue_planner.invoke.return_value = make_mock_rescue_plan()

    resource_allocator = MagicMock()
    resource_allocator.invoke.return_value = make_mock_allocation()

    communication_agent = MagicMock()
    communication_agent.invoke.return_value = make_mock_comms()

    chaos_simulator = MagicMock()
    chaos_simulator.inject.return_value = (make_mock_chaos_event(), ctx)
    chaos_simulator.severity_multiplier = 1.0

    return Orchestrator(
        context=ctx, config=cfg,
        data_agent=data_agent,
        rescue_planner=rescue_planner,
        resource_allocator=resource_allocator,
        communication_agent=communication_agent,
        chaos_simulator=chaos_simulator,
    )


class TestValidation:
    def test_severity_too_low_raises(self):
        with pytest.raises(ValidationError):
            build_orchestrator(severity=0)

    def test_severity_too_high_raises(self):
        with pytest.raises(ValidationError):
            build_orchestrator(severity=11)

    def test_valid_severity_ok(self):
        orch = build_orchestrator(severity=5)
        assert orch is not None

    def test_invalid_disaster_type_raises(self):
        with pytest.raises(ValidationError):
            ctx = make_context()
            ctx.disaster_type = "volcano"
            cfg = make_config()
            Orchestrator(ctx, cfg, MagicMock(), MagicMock(),
                         MagicMock(), MagicMock(), MagicMock())


class TestCycleCount:
    def test_runs_exact_cycles(self):
        orch = build_orchestrator(cycles=3)
        report = orch.run()
        assert len(report.cycles) == 3

    def test_runs_one_cycle(self):
        orch = build_orchestrator(cycles=1)
        report = orch.run()
        assert len(report.cycles) == 1


class TestAgentExecutionOrder:
    def test_agent_order_enforced(self):
        ctx = make_context()
        cfg = make_config(cycles=1)
        call_order = []

        data_agent = MagicMock()
        data_agent.invoke.side_effect = lambda *a, **kw: (
            call_order.append("data_agent") or make_mock_data_summary()
        )
        rescue_planner = MagicMock()
        rescue_planner.invoke.side_effect = lambda *a, **kw: (
            call_order.append("rescue_planner") or make_mock_rescue_plan()
        )
        resource_allocator = MagicMock()
        resource_allocator.invoke.side_effect = lambda *a, **kw: (
            call_order.append("resource_allocator") or make_mock_allocation()
        )
        communication_agent = MagicMock()
        communication_agent.invoke.side_effect = lambda *a, **kw: (
            call_order.append("communication_agent") or make_mock_comms()
        )
        chaos_simulator = MagicMock()
        chaos_simulator.inject.side_effect = lambda *a, **kw: (
            call_order.append("chaos_simulator") or (make_mock_chaos_event(), ctx)
        )
        chaos_simulator.severity_multiplier = 1.0

        orch = Orchestrator(ctx, cfg, data_agent, rescue_planner,
                            resource_allocator, communication_agent, chaos_simulator)
        orch.run()

        assert call_order == [
            "data_agent", "rescue_planner", "resource_allocator",
            "communication_agent", "chaos_simulator",
        ]


class TestAuditLog:
    def test_audit_chain_valid_after_run(self):
        orch = build_orchestrator(cycles=2)
        orch.run()
        assert orch._audit.verify() is True

    def test_audit_entries_count(self):
        """Each cycle: 4 agents + 1 chaos = 5 entries per cycle."""
        orch = build_orchestrator(cycles=3)
        orch.run()
        # 3 cycles × 5 entries = 15 (plus conflict resolution entries)
        assert len(orch._audit.entries()) >= 3 * 5


class TestLivesSavedMetric:
    def test_lives_saved_non_none_when_enabled(self):
        orch = build_orchestrator(cycles=2, lives_saved_metric=True)
        report = orch.run()
        for cycle in report.cycles:
            assert cycle.lives_saved_estimate is not None

    def test_total_lives_saved_equals_sum(self):
        orch = build_orchestrator(cycles=3, lives_saved_metric=True)
        report = orch.run()
        expected = sum(r.lives_saved_estimate for r in report.cycles
                       if r.lives_saved_estimate is not None)
        assert report.total_lives_saved == expected


class TestFinalReport:
    def test_report_has_required_fields(self):
        orch = build_orchestrator(cycles=2)
        report = orch.run()
        assert report.context is not None
        assert report.final_rescue_plan is not None
        assert report.final_allocation is not None
        assert report.audit_chain_hash != ""
        assert report.session_token != ""

    def test_report_serialization_has_sections(self):
        orch = build_orchestrator(cycles=1)
        report = orch.run()
        text = orch._serialize_report(report)
        required_sections = [
            "SCENARIO DETAILS",
            "PRIORITY ZONES",
            "RESCUE PLAN",
            "RESOURCE ALLOCATION",
            "RISKS",
            "COMMUNICATION",
            "CHAOS EVENT",
            "REVISED STRATEGY",
        ]
        for section in required_sections:
            assert section in text.upper(), f"Missing section: {section}"
