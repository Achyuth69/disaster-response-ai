"""
demo.py — Pre-configured Hyderabad Flood Demo.

Runs the full Disaster Response AI System with:
  - Disaster: Severe Flood in Hyderabad
  - Severity: 8/10
  - Resources: 10 rescue teams, 5 boats, 100 medical kits, 200 food units
  - Cycles: 3 (with chaos simulation enabled)
  - All optional features enabled (lives-saved, disagreement scoring, dashboard)

Usage:
  python demo.py
  python demo.py --no-dashboard   (disable Rich dashboard)
  python demo.py --seed 42        (deterministic chaos for reproducible demos)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure AGENT directory is on sys.path
_here = Path(__file__).parent.resolve()
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

# Change working directory so relative paths work
os.chdir(_here)

from dotenv import load_dotenv
load_dotenv(_here / ".env")


def run_demo(dashboard: bool = True, seed: int = None) -> None:
    from agents.models import (
        ConfigurationError, DisasterContext, OrchestratorConfig,
    )
    from agents.llm_client import LLMClient
    from agents.data_agent import DataAgent
    from agents.rescue_planner import RescuePlanner
    from agents.resource_allocator import ResourceAllocator
    from agents.communication_agent import CommunicationAgent
    from agents.chaos_simulator import ChaosSimulator
    from agents.orchestrator import Orchestrator
    from agents.dashboard import DisasterDashboard
    from agents.security import redact_keys

    print("\n" + "🔥" * 35)
    print("  DISASTER RESPONSE AI SYSTEM — DEMO")
    print("  Scenario: Severe Flood · Hyderabad · Severity 8/10")
    print("  Cycles: 3 | Chaos: ENABLED | All features ON")
    print("🔥" * 35 + "\n")

    primary_key   = os.getenv("GROQ_API_KEY", "")

    if not primary_key:
        print("  ❌ GROQ_API_KEY not set in .env file.")
        print("  Get your free key at: https://console.groq.com")
        print("  Then add to AGENT/.env: GROQ_API_KEY=your_key_here")
        sys.exit(1)

    try:
        llm = LLMClient(
            primary_provider="groq",
            primary_model=os.getenv("PRIMARY_MODEL", "llama-3.3-70b-versatile"),
            primary_key=primary_key,
            secondary_model=os.getenv("SECONDARY_MODEL", "llama-3.1-8b-instant"),
        )
    except ConfigurationError as e:
        print(f"  ❌ Configuration error: {redact_keys(str(e))}")
        sys.exit(1)

    # ── Demo scenario parameters ────────────────────────────────────────
    context = DisasterContext(
        disaster_type="flood",
        location="Hyderabad",
        severity=8,
        time_elapsed_hours=0.5,
        weather_conditions="Heavy monsoon rainfall 180mm/hr, strong winds 60km/h, visibility poor",
    )

    config = OrchestratorConfig(
        num_cycles=3,
        rescue_teams=10,
        boats=5,
        medical_kits=100,
        food_supply_units=200,
        chaos_enabled=True,
        lives_saved_metric=True,
        disagreement_scoring=True,
        dashboard_enabled=dashboard,
        output_dir="output",
        checkpoint_dir="checkpoints",
        timeout_seconds=120,
        circuit_breaker_threshold=3,
    )

    # ── Instantiate agents ──────────────────────────────────────────────
    index_dir = os.getenv("FAISS_INDEX_DIR", "faiss_index")
    kb_dir = os.getenv("KNOWLEDGE_BASE_DIR", "knowledge_base")

    data_agent = DataAgent(index_dir, kb_dir, llm)
    rescue_planner = RescuePlanner(llm)
    resource_allocator = ResourceAllocator(llm)
    communication_agent = CommunicationAgent(llm)
    chaos_simulator = ChaosSimulator(enabled=True, seed=seed)

    dash = DisasterDashboard(context, config) if dashboard else None

    orchestrator = Orchestrator(
        context=context,
        config=config,
        data_agent=data_agent,
        rescue_planner=rescue_planner,
        resource_allocator=resource_allocator,
        communication_agent=communication_agent,
        chaos_simulator=chaos_simulator,
        dashboard=dash,
    )

    # ── Run ─────────────────────────────────────────────────────────────
    try:
        report = orchestrator.run()

        print("\n" + "=" * 60)
        print("  ✅ DEMO COMPLETE")
        print(f"  Session : {report.session_token[:8]}...")
        print(f"  Cycles  : {len(report.cycles)}")
        if report.total_lives_saved:
            print(f"  💚 Lives Saved: {report.total_lives_saved:,}")
        if report.disagreement_summary:
            print(f"  🔀 Disagreements tracked")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\n  ⏹  Demo interrupted.")
    except Exception as exc:
        from agents.security import redact_keys
        print(f"\n  ❌ Demo error: {redact_keys(str(exc))}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Disaster Response AI System — Demo")
    parser.add_argument("--dashboard", dest="dashboard", action="store_true",
                        default=False, help="Enable Rich terminal dashboard")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for deterministic chaos (good for demos)")
    args = parser.parse_args()
    run_demo(dashboard=args.dashboard, seed=args.seed)
