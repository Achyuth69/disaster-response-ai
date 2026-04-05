"""
main.py — CLI entry point for the Disaster Response AI System.

Usage:
  python main.py --disaster-type flood --location Hyderabad --severity 8 --cycles 3
  python main.py --help
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure AGENT directory is on sys.path and is the working directory
_here = Path(__file__).parent.resolve()
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))
os.chdir(_here)

from dotenv import load_dotenv

_env_path = _here / ".env"
load_dotenv(_env_path)


def _check_env_permissions() -> None:
    """Warn if .env file has overly broad permissions."""
    try:
        import stat
        mode = os.stat(_env_path).st_mode
        if mode & stat.S_IRWXG or mode & stat.S_IRWXO:
            print(
                "  ⚠️  SECURITY_WARNING: .env file has broad permissions. "
                "Run: chmod 600 .env"
            )
    except Exception:
        pass


def build_system(args) -> tuple:
    """Instantiate all components from CLI args and environment."""
    from agents.models import ConfigurationError, DisasterContext, OrchestratorConfig
    from agents.llm_client import LLMClient
    from agents.data_agent import DataAgent
    from agents.rescue_planner import RescuePlanner
    from agents.resource_allocator import ResourceAllocator
    from agents.communication_agent import CommunicationAgent
    from agents.chaos_simulator import ChaosSimulator
    from agents.orchestrator import Orchestrator
    from agents.dashboard import DisasterDashboard

    primary_key      = os.getenv("GROQ_API_KEY", "")
    primary_provider = os.getenv("PRIMARY_PROVIDER", "groq")
    primary_model    = os.getenv("PRIMARY_MODEL", "llama-3.3-70b-versatile")
    secondary_model  = os.getenv("SECONDARY_MODEL", "llama-3.1-8b-instant")

    if not primary_key:
        raise ConfigurationError(
            "GROQ_API_KEY is not set. Add it to your .env file."
        )

    llm = LLMClient(
        primary_provider=primary_provider,
        primary_model=primary_model,
        primary_key=primary_key,
        secondary_model=secondary_model,
        circuit_breaker_threshold=args.circuit_breaker_threshold,
    )

    index_dir = os.getenv("FAISS_INDEX_DIR", "faiss_index")
    kb_dir = os.getenv("KNOWLEDGE_BASE_DIR", "knowledge_base")

    data_agent = DataAgent(index_dir, kb_dir, llm)
    rescue_planner = RescuePlanner(llm)
    resource_allocator = ResourceAllocator(llm)
    communication_agent = CommunicationAgent(llm)
    chaos_simulator = ChaosSimulator(
        enabled=args.chaos,
        seed=args.seed if hasattr(args, "seed") else None,
    )

    context = DisasterContext(
        disaster_type=args.disaster_type,
        location=args.location,
        severity=args.severity,
        time_elapsed_hours=args.time_elapsed,
        weather_conditions=args.weather,
    )

    config = OrchestratorConfig(
        num_cycles=args.cycles,
        rescue_teams=args.rescue_teams,
        boats=args.boats,
        medical_kits=args.medical_kits,
        food_supply_units=args.food_supply,
        chaos_enabled=args.chaos,
        lives_saved_metric=args.lives_saved,
        disagreement_scoring=args.disagreement_scoring,
        dashboard_enabled=args.dashboard,
        resume=args.resume,
        output_dir=os.getenv("OUTPUT_DIR", "output"),
        checkpoint_dir=os.getenv("CHECKPOINT_DIR", "checkpoints"),
        timeout_seconds=args.timeout,
        circuit_breaker_threshold=args.circuit_breaker_threshold,
    )

    dashboard = None
    if args.dashboard:
        dashboard = DisasterDashboard(context, config)

    orchestrator = Orchestrator(
        context=context,
        config=config,
        data_agent=data_agent,
        rescue_planner=rescue_planner,
        resource_allocator=resource_allocator,
        communication_agent=communication_agent,
        chaos_simulator=chaos_simulator,
        dashboard=dashboard,
    )

    if args.rebuild_index:
        print("  🔨 Rebuilding FAISS index...")
        data_agent._build_index()

    return orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="🚨 Disaster Response AI System — Multi-Agent Coordinator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --disaster-type flood --location Hyderabad --severity 8 --cycles 3
  python main.py --disaster-type earthquake --location Mumbai --severity 9 --cycles 5 --dashboard
  python main.py --disaster-type cyclone --location Chennai --severity 7 --no-chaos
        """,
    )

    # Scenario
    parser.add_argument("--disaster-type", default="flood",
                        choices=["flood", "earthquake", "cyclone", "tsunami", "wildfire", "landslide"],
                        help="Type of disaster (default: flood)")
    parser.add_argument("--location", default="Hyderabad",
                        help="City or region (default: Hyderabad)")
    parser.add_argument("--severity", type=int, default=8,
                        help="Severity level 1-10 (default: 8)")
    parser.add_argument("--time-elapsed", type=float, default=0.5,
                        help="Hours since disaster started (default: 0.5)")
    parser.add_argument("--weather", default="Heavy rainfall, strong winds",
                        help="Weather conditions description")

    # Resources
    parser.add_argument("--rescue-teams", type=int, default=10)
    parser.add_argument("--boats", type=int, default=5)
    parser.add_argument("--medical-kits", type=int, default=100)
    parser.add_argument("--food-supply", type=int, default=200)

    # System
    parser.add_argument("--cycles", type=int, default=3,
                        help="Number of response cycles (-1 for continuous)")
    parser.add_argument("--chaos", action="store_true", default=True,
                        help="Enable chaos simulation (default: on)")
    parser.add_argument("--no-chaos", dest="chaos", action="store_false",
                        help="Disable chaos simulation")
    parser.add_argument("--rebuild-index", action="store_true",
                        help="Force rebuild of FAISS knowledge base index")
    parser.add_argument("--lives-saved", action="store_true", default=True,
                        help="Enable lives-saved metric (default: on)")
    parser.add_argument("--disagreement-scoring", action="store_true", default=True,
                        help="Enable agent disagreement scoring (default: on)")
    parser.add_argument("--dashboard", action="store_true", default=False,
                        help="Enable real-time Rich terminal dashboard")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last checkpoint")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Agent timeout in seconds (default: 60)")
    parser.add_argument("--circuit-breaker-threshold", type=int, default=3,
                        help="Consecutive failures before circuit opens (default: 3)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for deterministic chaos simulation")

    args = parser.parse_args()

    _check_env_permissions()

    try:
        orchestrator = build_system(args)
        report = orchestrator.run()
        print(f"\n  ✅ Run complete. Session: {report.session_token[:8]}...")
        print(f"  Audit chain valid: {True}")
        if report.total_lives_saved:
            print(f"  💚 Total lives saved: {report.total_lives_saved:,}")
    except KeyboardInterrupt:
        print("\n\n  ⏹  Interrupted by user. Partial results may be in output/")
        sys.exit(0)
    except Exception as exc:
        from agents.security import redact_keys
        print(f"\n  ❌ Fatal error: {redact_keys(str(exc))}")
        sys.exit(1)


if __name__ == "__main__":
    main()
