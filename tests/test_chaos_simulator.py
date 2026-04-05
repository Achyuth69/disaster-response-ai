"""tests/test_chaos_simulator.py — Unit tests for ChaosSimulator."""
import pytest
from agents.chaos_simulator import ChaosSimulator
from agents.models import DisasterContext


def make_context(severity=8):
    return DisasterContext(
        disaster_type="flood", location="Hyderabad",
        severity=severity, time_elapsed_hours=1.0,
        weather_conditions="Heavy rain",
    )


class TestChaosSimulatorEnabled:
    def test_event_type_in_events(self):
        sim = ChaosSimulator(enabled=True, seed=42)
        ctx = make_context()
        event, _ = sim.inject(ctx, avg_confidence=0.7)
        assert event.event_type in ChaosSimulator.EVENTS

    def test_no_consecutive_repeat(self):
        sim = ChaosSimulator(enabled=True, seed=0)
        ctx = make_context()
        events = []
        for _ in range(10):
            event, ctx = sim.inject(ctx, avg_confidence=0.7)
            events.append(event.event_type)
        for i in range(len(events) - 1):
            assert events[i] != events[i + 1], (
                f"Consecutive repeat at index {i}: {events[i]}"
            )

    def test_context_updated(self):
        sim = ChaosSimulator(enabled=True, seed=1)
        ctx = make_context()
        event, new_ctx = sim.inject(ctx, avg_confidence=0.7)
        assert new_ctx.active_chaos_event is not None
        assert new_ctx.active_chaos_event.event_type == event.event_type

    def test_severity_multiplier_bounds(self):
        sim = ChaosSimulator(enabled=True, seed=5)
        ctx = make_context()
        for _ in range(20):
            _, ctx = sim.inject(ctx, avg_confidence=0.9)  # high confidence → harder
        assert sim.severity_multiplier <= ChaosSimulator.SEVERITY_MULTIPLIER_MAX

        sim2 = ChaosSimulator(enabled=True, seed=5)
        ctx2 = make_context()
        for _ in range(20):
            _, ctx2 = sim2.inject(ctx2, avg_confidence=0.1)  # low confidence → easier
        assert sim2.severity_multiplier >= ChaosSimulator.SEVERITY_MULTIPLIER_MIN

    def test_all_five_event_types_reachable(self):
        """Over many injections, all 5 event types should appear."""
        sim = ChaosSimulator(enabled=True, seed=99)
        ctx = make_context()
        seen = set()
        for _ in range(50):
            event, ctx = sim.inject(ctx, avg_confidence=0.7)
            seen.add(event.event_type)
        assert len(seen) == 5, f"Only saw: {seen}"


class TestChaosSimulatorDisabled:
    def test_disabled_returns_none_event(self):
        sim = ChaosSimulator(enabled=False)
        ctx = make_context()
        event, new_ctx = sim.inject(ctx, avg_confidence=0.7)
        assert event.event_type == "none"

    def test_disabled_context_unchanged(self):
        sim = ChaosSimulator(enabled=False)
        ctx = make_context(severity=8)
        original_severity = ctx.severity
        _, new_ctx = sim.inject(ctx, avg_confidence=0.7)
        assert new_ctx.severity == original_severity

    def test_disabled_no_active_chaos_event(self):
        sim = ChaosSimulator(enabled=False)
        ctx = make_context()
        _, new_ctx = sim.inject(ctx, avg_confidence=0.7)
        # active_chaos_event should be the sentinel "none" event
        assert new_ctx.active_chaos_event is None or \
               new_ctx.active_chaos_event.event_type == "none"


class TestAdaptiveDifficulty:
    def test_high_confidence_increases_multiplier(self):
        sim = ChaosSimulator(enabled=True, seed=42)
        initial = sim.severity_multiplier
        ctx = make_context()
        sim.inject(ctx, avg_confidence=0.95)
        assert sim.severity_multiplier > initial or \
               sim.severity_multiplier == ChaosSimulator.SEVERITY_MULTIPLIER_MAX

    def test_low_confidence_decreases_multiplier(self):
        sim = ChaosSimulator(enabled=True, seed=42)
        # First push multiplier up
        ctx = make_context()
        for _ in range(5):
            _, ctx = sim.inject(ctx, avg_confidence=0.95)
        high_mult = sim.severity_multiplier
        # Now decrease
        for _ in range(5):
            _, ctx = sim.inject(ctx, avg_confidence=0.1)
        assert sim.severity_multiplier < high_mult or \
               sim.severity_multiplier == ChaosSimulator.SEVERITY_MULTIPLIER_MIN
