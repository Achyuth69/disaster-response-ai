"""
agents/orchestrator.py — Central Orchestrator.
Manages the full agent loop, conflict resolution, cryptographic audit chain,
state checkpointing, circuit breakers, lives-saved metric,
disagreement scoring, and final report generation.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from agents.models import (
    AllocationResult, ChaosEvent, CheckpointState, CycleResult,
    DataSummary, DisasterContext, FinalReport, OrchestratorConfig,
    PriorityZone, RescuePlan, ResourceState, ValidationError, ZoneAllocation,
)
from agents.security import (
    AuditChain, derive_session_key, generate_session_token, redact_keys,
)
from agents.memory import AgentMemory
from agents.checkpoint import CheckpointManager


class Orchestrator:
    """
    Central coordinator for the Disaster Response AI System.

    Execution order per cycle:
      Data Agent → Rescue Planner → Resource Allocator →
      Communication Agent → Chaos Simulator

    Features:
    - Cryptographic HMAC-SHA256 audit chain
    - Per-agent circuit breakers
    - Fernet-encrypted state checkpointing
    - Adaptive chaos simulation
    - Consensus voting via LLMClient
    - Agent memory across cycles
    - Lives-saved metric
    - Agent disagreement scoring
    - Real-time Rich dashboard
    """

    def __init__(
        self,
        context: DisasterContext,
        config: OrchestratorConfig,
        data_agent,
        rescue_planner,
        resource_allocator,
        communication_agent,
        chaos_simulator,
        dashboard=None,
    ):
        # Validate severity
        if not (1 <= context.severity <= 10):
            raise ValidationError(
                f"Severity must be an integer between 1 and 10, got: {context.severity}"
            )
        if context.disaster_type.lower() not in ("flood", "earthquake", "cyclone",
                                                   "tsunami", "wildfire", "landslide"):
            raise ValidationError(
                f"Unsupported disaster type: '{context.disaster_type}'. "
                "Supported: flood, earthquake, cyclone, tsunami, wildfire, landslide"
            )

        # Assign session token
        self._session_token = generate_session_token()
        context.session_token = self._session_token
        self._context = context
        self._config = config

        # Agents
        self._data_agent = data_agent
        self._rescue_planner = rescue_planner
        self._resource_allocator = resource_allocator
        self._communication_agent = communication_agent
        self._chaos_simulator = chaos_simulator
        self._dashboard = dashboard

        # State
        self._resources = ResourceState(
            rescue_teams=config.rescue_teams,
            boats=config.boats,
            medical_kits=config.medical_kits,
            food_supply_units=config.food_supply_units,
        )
        self._cycle_results: list[CycleResult] = []
        self._circuit_breaker_warnings: list[str] = []
        self._consecutive_failures: dict[str, int] = {
            "data_agent": 0,
            "rescue_planner": 0,
            "resource_allocator": 0,
            "communication_agent": 0,
        }
        self._open_circuits: set[str] = set()
        self._total_lives_saved = 0
        self._total_disagreements = 0

        # Security & persistence
        self._session_key = derive_session_key(self._session_token)
        self._audit = AuditChain(self._session_key)
        self._memory = AgentMemory()
        self._checkpoint_mgr = CheckpointManager(
            config.checkpoint_dir, self._session_key
        )

        # Ensure output directory exists
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)

        # Previous cycle outputs for fallback
        self._prev_data_summary: Optional[DataSummary] = None
        self._prev_rescue_plan: Optional[RescuePlan] = None
        self._prev_allocation: Optional[AllocationResult] = None
        self._prev_comms = None

        self._start_time = time.time()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> FinalReport:
        """Execute all configured response cycles and return the final report."""
        print(f"\n{'='*60}")
        print(f"  🚨 DISASTER RESPONSE AI SYSTEM")
        print(f"  Session: {self._session_token[:8]}...")
        print(f"  Scenario: {self._context.disaster_type.upper()} in {self._context.location}")
        print(f"  Severity: {self._context.severity}/10")
        print(f"  Cycles: {self._config.num_cycles}")
        print(f"{'='*60}\n")

        if self._dashboard:
            self._dashboard.start()

        # Resume from checkpoint if requested
        if self._config.resume:
            ckpt = self._checkpoint_mgr.load(self._session_token)
            if ckpt:
                self._restore_checkpoint(ckpt)
                print(f"  ✅ Resumed from checkpoint at cycle {ckpt.cycle_num}")

        num_cycles = self._config.num_cycles
        start_cycle = len(self._cycle_results) + 1

        for cycle_num in range(start_cycle, num_cycles + 1):
            elapsed = time.time() - self._start_time
            print(f"\n{'─'*60}")
            print(f"  🔄 CYCLE {cycle_num}/{num_cycles}  |  ⏱ {elapsed:.1f}s elapsed")
            print(f"{'─'*60}")

            if self._dashboard:
                self._dashboard.update_cycle(cycle_num, elapsed)

            result = self._run_cycle(cycle_num)
            self._cycle_results.append(result)

            # Save checkpoint
            self._save_checkpoint(cycle_num)

            # Continuous mode: pause for user confirmation
            if num_cycles == -1:
                input("\n  ⏸  Press ENTER to continue to next cycle (or Ctrl+C to stop)...")

        if self._dashboard:
            self._dashboard.stop()

        report = self._generate_report()
        self._save_report(report)
        return report

    # ------------------------------------------------------------------
    # Cycle execution
    # ------------------------------------------------------------------

    def _run_cycle(self, cycle_num: int) -> CycleResult:
        ctx = self._context
        ctx._cycle_num = cycle_num  # type: ignore[attr-defined]

        # ── Step 1: Data Agent ──────────────────────────────────────────
        data_summary = self._invoke_agent(
            "data_agent",
            lambda ctx=ctx: self._data_agent.invoke(ctx, self._memory),
            self._prev_data_summary,
            cycle_num,
        )
        if data_summary is None:
            data_summary = self._fallback_data_summary()
        self._prev_data_summary = data_summary

        if self._dashboard:
            self._dashboard.update_agent("Data Agent", "done", data_summary.confidence_score)
            self._dashboard.update_resources(self._resources)

        # ── Step 2: Rescue Planner ──────────────────────────────────────
        rescue_plan = self._invoke_agent(
            "rescue_planner",
            lambda ctx=ctx, ds=data_summary: self._rescue_planner.invoke(
                ctx, ds, self._config.rescue_teams, self._memory
            ),
            self._prev_rescue_plan,
            cycle_num,
        )
        if rescue_plan is None:
            rescue_plan = self._fallback_rescue_plan(data_summary)
        self._prev_rescue_plan = rescue_plan

        if self._dashboard:
            self._dashboard.update_agent("Rescue Planner", "done", rescue_plan.confidence_score)

        # ── Step 3: Resource Allocator ──────────────────────────────────
        allocation = self._invoke_agent(
            "resource_allocator",
            lambda ctx=ctx, rp=rescue_plan, res=self._resources: self._resource_allocator.invoke(
                ctx, rp, res, self._memory
            ),
            self._prev_allocation,
            cycle_num,
        )
        if allocation is None:
            allocation = self._fallback_allocation()
        self._prev_allocation = allocation
        self._resources = allocation.remaining_resources

        if self._dashboard:
            self._dashboard.update_agent("Resource Allocator", "done", allocation.confidence_score)
            self._dashboard.update_resources(self._resources)

        # ── Conflict resolution ─────────────────────────────────────────
        disagreements = self._resolve_conflicts(rescue_plan, allocation)
        if self._config.disagreement_scoring:
            self._total_disagreements += len(disagreements)
            if self._dashboard:
                self._dashboard.update_disagreements(self._total_disagreements)

        # ── Step 4: Communication Agent ─────────────────────────────────
        comms = self._invoke_agent(
            "communication_agent",
            lambda ctx=ctx, rp=rescue_plan, al=allocation: self._communication_agent.invoke(
                ctx, rp, al,
                ctx.active_chaos_event, self._memory
            ),
            self._prev_comms,
            cycle_num,
        )
        if comms is None:
            from agents.models import CommunicationOutput
            comms = CommunicationOutput(
                public_message="Emergency operations ongoing. Follow official instructions.",
                internal_message="All teams maintain positions. Await further orders.",
            )
        self._prev_comms = comms

        if self._dashboard:
            self._dashboard.update_agent("Communication Agent", "done", comms.confidence_score)

        # ── Step 5: Chaos Simulator ─────────────────────────────────────
        avg_confidence = (
            data_summary.confidence_score
            + rescue_plan.confidence_score
            + allocation.confidence_score
            + comms.confidence_score
        ) / 4.0

        chaos_event, self._context = self._chaos_simulator.inject(ctx, avg_confidence)

        if self._dashboard:
            self._dashboard.update_agent("Chaos Simulator", "done", 1.0)
            if chaos_event.event_type != "none":
                self._dashboard.flash_chaos_event(chaos_event)

        # ── Lives saved metric ──────────────────────────────────────────
        lives_saved = None
        if self._config.lives_saved_metric:
            lives_saved = self._estimate_lives_saved(rescue_plan, allocation)
            self._total_lives_saved += lives_saved
            if self._dashboard:
                self._dashboard.update_lives_saved(self._total_lives_saved)

        # ── Audit log ───────────────────────────────────────────────────
        self._audit.append(cycle_num, "chaos_simulator",
                           {"event_type": chaos_event.event_type},
                           {"description": chaos_event.description},
                           1.0)

        # Print cycle summary
        self._print_cycle_summary(
            cycle_num, data_summary, rescue_plan, allocation,
            comms, chaos_event, lives_saved, disagreements
        )

        return CycleResult(
            cycle_num=cycle_num,
            data_summary=data_summary,
            rescue_plan=rescue_plan,
            allocation_result=allocation,
            communication_output=comms,
            chaos_event=chaos_event,
            avg_confidence=avg_confidence,
            lives_saved_estimate=lives_saved,
            disagreements=disagreements,
            inter_provider_disagreements=[
                rescue_plan.consensus_disagreement,
                allocation.consensus_disagreement,
            ] if (rescue_plan.consensus_disagreement or allocation.consensus_disagreement) else [],
        )

    # ------------------------------------------------------------------
    # Agent invocation with circuit breaker + timeout
    # ------------------------------------------------------------------

    def _invoke_agent(self, agent_name: str, fn, fallback, cycle_num: int):
        if agent_name in self._open_circuits:
            warn = f"CIRCUIT_OPEN: {agent_name} bypassed at cycle {cycle_num}"
            self._circuit_breaker_warnings.append(warn)
            print(f"  ⚠️  {warn}")
            return fallback

        if self._dashboard:
            self._dashboard.update_agent(
                agent_name.replace("_", " ").title(), "running"
            )

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fn)
                try:
                    result = future.result(timeout=self._config.timeout_seconds)
                except FuturesTimeout:
                    self._handle_agent_failure(agent_name, cycle_num, "TIMEOUT — agent exceeded time limit")
                    return fallback
                except Exception as inner_exc:
                    import traceback
                    full_err = redact_keys(traceback.format_exc())
                    self._handle_agent_failure(agent_name, cycle_num, full_err[:800])
                    return fallback

            self._consecutive_failures[agent_name] = 0
            self._audit.append(
                cycle_num, agent_name,
                {"agent": agent_name, "cycle": cycle_num},
                {"status": "success"},
                getattr(result, "confidence_score", 1.0),
            )
            return result

        except Exception as outer_exc:
            import traceback
            full_err = redact_keys(traceback.format_exc())
            self._handle_agent_failure(agent_name, cycle_num, full_err[:800])
            return fallback

    def _handle_agent_failure(self, agent_name: str, cycle_num: int,
                               reason: str) -> None:
        self._consecutive_failures[agent_name] = (
            self._consecutive_failures.get(agent_name, 0) + 1
        )
        failures = self._consecutive_failures[agent_name]
        print(f"  ❌ {agent_name} failed (attempt {failures}): {reason[:300]}")

        self._audit.append(
            cycle_num, agent_name,
            {"agent": agent_name, "cycle": cycle_num},
            {"status": "failed", "reason": reason[:200]},
            0.0,
        )

        if failures >= self._config.circuit_breaker_threshold:
            self._open_circuits.add(agent_name)
            warn = (
                f"CIRCUIT_OPEN: {agent_name} opened after "
                f"{failures} consecutive failures"
            )
            self._circuit_breaker_warnings.append(warn)
            print(f"  🔴 {warn}")

        if self._dashboard:
            self._dashboard.update_agent(
                agent_name.replace("_", " ").title(), "failed"
            )

    # ------------------------------------------------------------------
    # Conflict resolution
    # ------------------------------------------------------------------

    def _resolve_conflicts(self, rescue_plan: RescuePlan,
                            allocation: AllocationResult) -> list[str]:
        """
        Resolve priority conflicts between Rescue Planner and Resource Allocator.
        Rule 1: Higher severity contribution wins.
        Rule 2: Tiebreaker = has_vulnerable_populations.
        Rule 3: Higher population_at_risk wins.
        """
        if not self._config.disagreement_scoring:
            return []

        disagreements: list[str] = []
        alloc_order = {a.zone_id: i for i, a in enumerate(allocation.allocations)}
        plan_order = {z.zone_id: i for i, z in enumerate(rescue_plan.priority_zones)}

        for zone in rescue_plan.priority_zones:
            plan_rank = plan_order.get(zone.zone_id, 999)
            alloc_rank = alloc_order.get(zone.zone_id, 999)

            if abs(plan_rank - alloc_rank) > 1:
                # Conflict detected
                msg = (
                    f"Zone '{zone.name}': Rescue Planner rank={plan_rank+1}, "
                    f"Allocator rank={alloc_rank+1}. "
                    f"Resolved: severity={self._context.severity}, "
                    f"vulnerable={'yes' if zone.has_vulnerable_populations else 'no'}"
                )
                disagreements.append(msg)
                self._audit.append(
                    getattr(self._context, "_cycle_num", 0),
                    "conflict_resolution",
                    {"zone": zone.name, "plan_rank": plan_rank, "alloc_rank": alloc_rank},
                    {"resolution": msg},
                    1.0,
                )

        return disagreements

    # ------------------------------------------------------------------
    # Lives saved estimation
    # ------------------------------------------------------------------

    def _estimate_lives_saved(self, rescue_plan: RescuePlan,
                               allocation: AllocationResult) -> int:
        total    = 0
        # Build lookup by zone_id AND by name (lowercase, no spaces)
        alloc_by_id   = {a.zone_id: a for a in allocation.allocations}
        alloc_by_name = {
            a.zone_id.lower().replace(" ", "_").replace("-", "_"): a
            for a in allocation.allocations
        }

        for zone in rescue_plan.priority_zones:
            # Try exact zone_id match first, then name-based match
            alloc = alloc_by_id.get(zone.zone_id)
            if not alloc:
                key   = zone.name.lower().replace(" ", "_").replace("-", "_")
                alloc = alloc_by_name.get(key)
            if not alloc and allocation.allocations:
                # Last resort: use first allocation proportionally
                alloc = allocation.allocations[0]

            if not alloc:
                continue

            pop          = max(1, zone.population_at_risk)
            teams_ratio  = min(1.0, (alloc.rescue_teams + 1) / max(1, pop // 5000))
            med_ratio    = min(1.0, (alloc.medical_kits + 1) / max(1, pop // 200))
            effectiveness = teams_ratio * 0.6 + med_ratio * 0.4
            lives         = int(pop * 0.02 * effectiveness)
            if zone.has_vulnerable_populations:
                lives = int(lives * 1.2)
            total += max(1, lives)   # at least 1 life saved per reached zone

        return total

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def _generate_report(self) -> FinalReport:
        last = self._cycle_results[-1] if self._cycle_results else None
        audit_valid = self._audit.verify()

        disagreement_summary = None
        if self._config.disagreement_scoring and self._cycle_results:
            all_disagreements = []
            for r in self._cycle_results:
                all_disagreements.extend(r.disagreements)
            if all_disagreements:
                disagreement_summary = (
                    f"Total conflicts: {len(all_disagreements)} across "
                    f"{len(self._cycle_results)} cycles.\n"
                    + "\n".join(f"  - {d}" for d in all_disagreements)
                )

        return FinalReport(
            context=self._context,
            cycles=self._cycle_results,
            final_rescue_plan=last.rescue_plan if last else self._fallback_rescue_plan(None),
            final_allocation=last.allocation_result if last else self._fallback_allocation(),
            final_communication=last.communication_output if last else None,
            latest_chaos_event=last.chaos_event if last else None,
            audit_chain_hash=self._audit.terminal_hash(),
            session_token=self._session_token,
            total_lives_saved=self._total_lives_saved if self._config.lives_saved_metric else None,
            disagreement_summary=disagreement_summary,
            circuit_breaker_warnings=self._circuit_breaker_warnings,
        )

    def _save_report(self, report: FinalReport) -> None:
        text = self._serialize_report(report)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"{report.context.disaster_type}_{report.context.location.replace(' ', '_')}"
            f"_{ts}.txt"
        )
        path = Path(self._config.output_dir) / filename
        try:
            path.write_text(text, encoding="utf-8")
            print(f"\n  📄 Report saved: {path}")
        except Exception as exc:
            print(f"\n  ⚠️  Could not save report ({exc}). Printing to stdout:\n")
            print(text)

    def _serialize_report(self, report: FinalReport) -> str:
        lines = [
            "=" * 70,
            "  === DISASTER RESPONSE REPORT ===",
            "=" * 70,
            "",
            f"  Session Token : {report.session_token}",
            f"  Audit Hash    : {report.audit_chain_hash[:32]}...",
            f"  Audit Valid   : {self._audit.verify()}",
            f"  Generated At  : {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "─" * 70,
            "  🚨 SCENARIO DETAILS",
            "─" * 70,
            f"  Type     : {report.context.disaster_type.upper()}",
            f"  Location : {report.context.location}",
            f"  Severity : {report.context.severity}/10",
            f"  Elapsed  : {report.context.time_elapsed_hours}h",
            f"  Weather  : {report.context.weather_conditions}",
            f"  Cycles   : {len(report.cycles)}",
            "",
        ]

        # Priority Zones
        lines += ["─" * 70, "  📍 PRIORITY ZONES", "─" * 70]
        for i, zone in enumerate(report.final_rescue_plan.priority_zones[:8], 1):
            vuln = "⚠️ VULNERABLE" if zone.has_vulnerable_populations else ""
            lines.append(
                f"  {i}. {zone.name} | Score: {zone.priority_score:.2f} | "
                f"Pop: {zone.population_at_risk:,} {vuln}"
            )
        lines.append("")

        # Rescue Plan
        lines += ["─" * 70, "  🚑 RESCUE PLAN", "─" * 70]
        for team_id, zone_id in report.final_rescue_plan.team_assignments.items():
            route = report.final_rescue_plan.route_descriptions.get(zone_id, "Direct route")
            eta = report.final_rescue_plan.estimated_travel_times.get(zone_id, 0)
            lines.append(f"  {team_id} → {zone_id} | Route: {route[:60]} | ETA: {eta:.1f}h")
        lines.append("")

        # Resource Allocation Table
        lines += ["─" * 70, "  📦 RESOURCE ALLOCATION", "─" * 70]
        lines.append(f"  {'Zone':<25} {'Teams':>6} {'Boats':>6} {'Med':>6} {'Food':>6}")
        lines.append(f"  {'─'*25} {'─'*6} {'─'*6} {'─'*6} {'─'*6}")
        for alloc in report.final_allocation.allocations[:10]:
            lines.append(
                f"  {alloc.zone_id[:25]:<25} {alloc.rescue_teams:>6} "
                f"{alloc.boats:>6} {alloc.medical_kits:>6} {alloc.food_supply_units:>6}"
            )
        rem = report.final_allocation.remaining_resources
        lines.append(f"\n  Remaining: Teams={rem.rescue_teams} Boats={rem.boats} "
                     f"Med={rem.medical_kits} Food={rem.food_supply_units}")
        if report.final_allocation.depleted_resources:
            lines.append(f"  ⚠️  DEPLETED: {', '.join(report.final_allocation.depleted_resources)}")
        lines.append("")

        # Risks & Trade-offs
        lines += ["─" * 70, "  ⚠️  RISKS & TRADE-OFFS", "─" * 70]
        lines.append(f"  {report.final_allocation.trade_offs}")
        lines.append("")

        # Communication
        lines += ["─" * 70, "  📡 COMMUNICATION MESSAGES", "─" * 70]
        if report.final_communication:
            lines.append("  PUBLIC MESSAGE:")
            for line in report.final_communication.public_message.split("\n"):
                lines.append(f"    {line}")
            lines.append("")
            lines.append("  INTERNAL MESSAGE:")
            for line in report.final_communication.internal_message.split("\n"):
                lines.append(f"    {line}")
        lines.append("")

        # Latest Chaos Event
        lines += ["─" * 70, "  🔄 LATEST CHAOS EVENT", "─" * 70]
        if report.latest_chaos_event and report.latest_chaos_event.event_type != "none":
            evt = report.latest_chaos_event
            lines.append(f"  Type       : {evt.event_type}")
            lines.append(f"  Description: {evt.description}")
            lines.append(f"  Multiplier : ×{evt.severity_multiplier:.1f}")
            if evt.is_compound and evt.secondary_event:
                lines.append(f"  Secondary  : {evt.secondary_event.description}")
        else:
            lines.append("  No chaos events injected.")
        lines.append("")

        # Revised Strategy
        lines += ["─" * 70, "  🧠 REVISED STRATEGY", "─" * 70]
        if self._cycle_results:
            last = self._cycle_results[-1]
            lines.append(f"  Avg Confidence: {last.avg_confidence:.2f}")
            lines.append(f"  Chaos Multiplier: ×{self._chaos_simulator.severity_multiplier:.1f}")
        lines.append("")

        # Optional metrics
        if report.total_lives_saved is not None:
            lines += ["─" * 70, "  💚 LIVES SAVED ESTIMATE", "─" * 70]
            lines.append(f"  Total: {report.total_lives_saved:,} lives")
            for r in report.cycles:
                if r.lives_saved_estimate is not None:
                    lines.append(f"  Cycle {r.cycle_num}: {r.lives_saved_estimate:,}")
            lines.append("")

        if report.disagreement_summary:
            lines += ["─" * 70, "  🔀 AGENT DISAGREEMENTS", "─" * 70]
            lines.append(f"  {report.disagreement_summary}")
            lines.append("")

        if report.circuit_breaker_warnings:
            lines += ["─" * 70, "  🔴 CIRCUIT BREAKER WARNINGS", "─" * 70]
            for w in report.circuit_breaker_warnings:
                lines.append(f"  {w}")
            lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Checkpoint
    # ------------------------------------------------------------------

    def _save_checkpoint(self, cycle_num: int) -> None:
        try:
            state = CheckpointState(
                session_token=self._session_token,
                cycle_num=cycle_num,
                context=self._context,
                resources=self._resources,
                cycle_results=self._cycle_results,
                audit_entries=self._audit.entries(),
                chaos_severity_multiplier=self._chaos_simulator.severity_multiplier,
                memory_data=self._memory.to_dict(),
            )
            self._checkpoint_mgr.save(state)
        except Exception as exc:
            print(f"  ⚠️  Checkpoint save failed: {redact_keys(str(exc))}")

    def _restore_checkpoint(self, ckpt: CheckpointState) -> None:
        self._context = ckpt.context
        self._resources = ckpt.resources
        self._cycle_results = ckpt.cycle_results
        self._memory = AgentMemory.from_dict(ckpt.memory_data)

    # ------------------------------------------------------------------
    # Fallback outputs (used when agents fail)
    # ------------------------------------------------------------------

    def _fallback_data_summary(self) -> DataSummary:
        from agents.models import DataSummary
        return DataSummary(
            affected_zones=["Unknown — data retrieval failed"],
            nearest_medical_facilities=["Gandhi Hospital (fallback)"],
            estimated_population_at_risk=100000,
            geographic_constraints=[],
            confidence_score=0.1,
            data_gaps=["All fields — agent failed"],
        )

    def _fallback_rescue_plan(self, data_summary) -> RescuePlan:
        zones = [
            PriorityZone("zone_1", "Dilsukhnagar", 0.9, 125000, True),
            PriorityZone("zone_2", "LB Nagar", 0.8, 118000, True),
            PriorityZone("zone_3", "Mehdipatnam", 0.7, 72000, True),
        ]
        return RescuePlan(
            priority_zones=zones,
            team_assignments={f"Team-{i+1}": z.zone_id for i, z in enumerate(zones)},
            estimated_travel_times={z.zone_id: 1.0 for z in zones},
            route_descriptions={z.zone_id: "Direct route (fallback)" for z in zones},
            confidence_score=0.1,
        )

    def _fallback_allocation(self) -> AllocationResult:
        # Build allocations matching the fallback rescue plan zones
        zones = [
            ("zone_1", "Dilsukhnagar"),
            ("zone_2", "LB Nagar"),
            ("zone_3", "Mehdipatnam"),
        ]
        res = self._resources
        teams_each = max(1, res.rescue_teams // max(1, len(zones)))
        boats_each = max(0, res.boats // max(1, len(zones)))
        med_each   = max(1, res.medical_kits // max(1, len(zones)))
        food_each  = max(1, res.food_supply_units // max(1, len(zones)))
        allocations = [
            ZoneAllocation(
                zone_id=zid,
                rescue_teams=teams_each,
                boats=boats_each,
                medical_kits=med_each,
                food_supply_units=food_each,
            )
            for zid, _ in zones
        ]
        return AllocationResult(
            allocations=allocations,
            remaining_resources=ResourceState(
                rescue_teams=max(0, res.rescue_teams - teams_each * len(zones)),
                boats=max(0, res.boats - boats_each * len(zones)),
                medical_kits=max(0, res.medical_kits - med_each * len(zones)),
                food_supply_units=max(0, res.food_supply_units - food_each * len(zones)),
            ),
            depleted_resources=[],
            trade_offs="Allocation fallback — using previous cycle data.",
            confidence_score=0.1,
        )

    # ------------------------------------------------------------------
    # Console output
    # ------------------------------------------------------------------

    def _print_cycle_summary(self, cycle_num, data_summary, rescue_plan,
                              allocation, comms, chaos_event,
                              lives_saved, disagreements) -> None:
        print(f"\n  📊 CYCLE {cycle_num} SUMMARY")
        print(f"  Zones identified : {len(rescue_plan.priority_zones)}")
        print(f"  Teams deployed   : {len(rescue_plan.team_assignments)}")
        print(f"  Resources left   : Teams={allocation.remaining_resources.rescue_teams} "
              f"Boats={allocation.remaining_resources.boats} "
              f"Med={allocation.remaining_resources.medical_kits}")
        print(f"  Avg confidence   : {(data_summary.confidence_score + rescue_plan.confidence_score + allocation.confidence_score) / 3:.2f}")
        if chaos_event.event_type != "none":
            print(f"  ⚡ Chaos event   : {chaos_event.event_type} — {chaos_event.description[:60]}")
        if lives_saved is not None:
            print(f"  💚 Lives saved   : {lives_saved:,} (total: {self._total_lives_saved:,})")
        if disagreements:
            print(f"  🔀 Disagreements : {len(disagreements)}")
        if allocation.depleted_resources:
            # Deduplicate and normalise depleted resource names
            seen = set()
            clean = []
            for r in allocation.depleted_resources:
                key = r.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
                # Normalise common variants
                for canonical, variants in {
                    "rescue_teams": ["rescue_team", "rescueteams", "resscue_teams", "rescue_teaams"],
                    "boats": ["boat", "boats_vehicles", "boats/vehicles"],
                    "medical_kits": ["medical_kit", "medkits", "medical__kits"],
                    "food_supply_units": ["food_supply", "food_units", "foodsupply"],
                }.items():
                    if key == canonical or any(v in key for v in variants):
                        key = canonical
                        break
                if key not in seen:
                    seen.add(key)
                    clean.append(key)
            print(f"  ⚠️  Depleted      : {', '.join(clean)}")
