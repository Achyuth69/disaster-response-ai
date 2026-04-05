"""
agents/dashboard.py — Real-time Rich terminal dashboard.
Shows live agent status, resource meters, chaos events,
confidence scores, and lives-saved counter.
"""
from __future__ import annotations

import time
import threading
from typing import Optional

from agents.models import ChaosEvent, DisasterContext, OrchestratorConfig, ResourceState


class DisasterDashboard:
    """
    Live terminal dashboard using Rich.
    Falls back gracefully if Rich is not installed.
    """

    def __init__(self, context: DisasterContext, config: OrchestratorConfig):
        self._context = context
        self._config = config
        self._live = None
        self._layout = None
        self._lock = threading.Lock()
        self._running = False

        # State
        self._cycle = 0
        self._elapsed = 0.0
        self._agents: dict[str, dict] = {
            "Data Agent":       {"status": "pending", "confidence": 0.0},
            "Rescue Planner":   {"status": "pending", "confidence": 0.0},
            "Resource Allocator": {"status": "pending", "confidence": 0.0},
            "Communication Agent": {"status": "pending", "confidence": 0.0},
            "Chaos Simulator":  {"status": "pending", "confidence": 0.0},
        }
        self._resources: Optional[ResourceState] = None
        self._lives_saved = 0
        self._latest_chaos: Optional[str] = None
        self._chaos_flash_until = 0.0
        self._disagreements = 0

        try:
            from rich.live import Live
            from rich.layout import Layout
            from rich.console import Console
            self._rich_available = True
            self._console = Console()
        except ImportError:
            self._rich_available = False

    def start(self) -> None:
        if not self._rich_available:
            return
        self._running = True
        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._rich_available and self._live:
            try:
                self._live.stop()
            except Exception:
                pass

    def update_cycle(self, cycle_num: int, elapsed: float) -> None:
        with self._lock:
            self._cycle = cycle_num
            self._elapsed = elapsed
            # Reset agent statuses for new cycle
            for name in self._agents:
                self._agents[name] = {"status": "pending", "confidence": 0.0}

    def update_agent(self, agent_name: str, status: str,
                     confidence: float = 0.0) -> None:
        with self._lock:
            if agent_name in self._agents:
                self._agents[agent_name] = {
                    "status": status,
                    "confidence": confidence,
                }

    def update_resources(self, resources: ResourceState) -> None:
        with self._lock:
            self._resources = resources

    def flash_chaos_event(self, event: ChaosEvent) -> None:
        with self._lock:
            self._latest_chaos = f"⚡ {event.event_type.upper()}: {event.description}"
            self._chaos_flash_until = time.time() + 2.0

    def update_lives_saved(self, count: int) -> None:
        with self._lock:
            self._lives_saved = count

    def update_disagreements(self, count: int) -> None:
        with self._lock:
            self._disagreements = count

    def print_status(self, message: str) -> None:
        """Fallback plain-text status when Rich is unavailable."""
        print(f"  [{time.strftime('%H:%M:%S')}] {message}")

    # ------------------------------------------------------------------
    # Internal render loop
    # ------------------------------------------------------------------

    def _render_loop(self) -> None:
        if not self._rich_available:
            return
        from rich.live import Live
        from rich import box
        from rich.table import Table
        from rich.panel import Panel
        from rich.columns import Columns
        from rich.text import Text

        with Live(self._build_renderable(), refresh_per_second=4,
                  screen=False) as live:
            self._live = live
            while self._running:
                live.update(self._build_renderable())
                time.sleep(0.25)

    def _build_renderable(self):
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
        from rich import box
        from rich.columns import Columns

        with self._lock:
            cycle = self._cycle
            elapsed = self._elapsed
            agents = dict(self._agents)
            resources = self._resources
            lives = self._lives_saved
            chaos_msg = self._latest_chaos or "No chaos event yet"
            chaos_active = time.time() < self._chaos_flash_until
            disagreements = self._disagreements

        # Header
        header = Text(
            f"🚨 DISASTER RESPONSE AI SYSTEM  |  "
            f"{self._context.disaster_type.upper()} · "
            f"{self._context.location} · Severity {self._context.severity}/10  |  "
            f"Cycle {cycle}/{self._config.num_cycles}  |  "
            f"⏱ {int(elapsed)}s",
            style="bold white on red" if self._context.severity >= 7 else "bold white on dark_orange",
        )

        # Agent status table
        agent_table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
        agent_table.add_column("Agent", style="white", width=22)
        agent_table.add_column("Status", width=10)
        agent_table.add_column("Confidence", width=12)

        status_icons = {
            "pending": "⏳",
            "running": "🔄",
            "done": "✅",
            "failed": "❌",
        }
        for name, info in agents.items():
            icon = status_icons.get(info["status"], "❓")
            conf = info["confidence"]
            conf_bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
            agent_table.add_row(
                name,
                f"{icon} {info['status']}",
                f"{conf_bar} {conf:.2f}",
            )

        # Resource meters
        res_table = Table(box=box.SIMPLE, show_header=True, header_style="bold green")
        res_table.add_column("Resource", style="white", width=18)
        res_table.add_column("Level", width=20)

        if resources:
            cfg = self._config
            items = [
                ("Rescue Teams", resources.rescue_teams, cfg.rescue_teams),
                ("Boats", resources.boats, cfg.boats),
                ("Medical Kits", resources.medical_kits, cfg.medical_kits),
                ("Food Supply", resources.food_supply_units, cfg.food_supply_units),
            ]
            for label, current, total in items:
                if total > 0:
                    ratio = current / total
                    bar = "█" * int(ratio * 10) + "░" * (10 - int(ratio * 10))
                    res_table.add_row(label, f"{bar} {current}/{total}")
        else:
            res_table.add_row("—", "Awaiting first cycle")

        # Chaos panel
        chaos_style = "bold red on white" if chaos_active else "yellow"
        chaos_panel = Panel(
            Text(chaos_msg, style=chaos_style),
            title="⚡ CHAOS EVENT",
            border_style="red" if chaos_active else "yellow",
        )

        # Stats
        token = self._context.session_token
        token_display = (token[:8] + "...") if token else "STARTING..."
        stats = Text(
            f"💚 Lives Saved: {lives:,}  |  🔀 Disagreements: {disagreements}  |  "
            f"Session: {token_display}",
            style="bold green",
        )

        from rich.console import Group
        return Panel(
            Group(
                header,
                Columns([
                    Panel(agent_table, title="AGENT STATUS", border_style="cyan"),
                    Panel(res_table, title="RESOURCES", border_style="green"),
                ]),
                chaos_panel,
                stats,
            ),
            border_style="red" if self._context.severity >= 7 else "orange3",
        )
