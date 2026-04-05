"""
run_api.py — Start the FastAPI server for the Disaster Response AI System.

Usage:
  python run_api.py                    # dev (localhost:8000)
  python run_api.py --prod             # production mode
  python run_api.py --host 0.0.0.0     # network accessible
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

_here = Path(__file__).parent.resolve()
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from dotenv import load_dotenv
load_dotenv(_here / ".env")

# ── Port: always read from PORT env var first, fallback 8000 ─────────────────
# This works on Railway, Render, Fly.io, local — everywhere
PORT = int(os.environ.get("PORT", 8000))
HOST = os.environ.get("HOST", "0.0.0.0")
PROD = os.environ.get("APP_ENV", "development").lower() == "production"


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    # Allow --prod flag and --host override but NEVER --port (use $PORT env var)
    import argparse
    parser = argparse.ArgumentParser(description="Disaster Response AI System")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--prod", action="store_true", default=PROD)
    parser.add_argument("--workers", type=int, default=1)
    # --port is accepted but IGNORED — always use $PORT env var
    parser.add_argument("--port", default=None,
                        help="Ignored — use PORT environment variable instead")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn not installed.")
        sys.exit(1)

    os.chdir(_here)
    local_ip = get_local_ip()
    prod = args.prod

    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║       🚨 DISASTER RESPONSE AI SYSTEM — API SERVER               ║
╠══════════════════════════════════════════════════════════════════╣
║  URL       : http://{local_ip}:{PORT}/ui/index.html
║  API Docs  : http://{local_ip}:{PORT}/api/docs
║  Health    : http://{local_ip}:{PORT}/api/health
║  Mode      : {'PRODUCTION ✓' if prod else 'DEVELOPMENT'}
╚══════════════════════════════════════════════════════════════════╝
""")

    uvicorn_kwargs = dict(
        app="api.server:app",
        host=args.host,
        port=PORT,
        log_level="warning" if prod else "info",
        access_log=not prod,
        reload=not prod,
    )
    if prod:
        uvicorn_kwargs.pop("reload")
        uvicorn_kwargs["reload"] = False

    uvicorn.run(**uvicorn_kwargs)


if __name__ == "__main__":
    main()
