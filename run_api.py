"""
run_api.py — Start the FastAPI server for the Disaster Response AI System.

Usage:
  python run_api.py                        # dev mode (localhost only)
  python run_api.py --host 0.0.0.0         # accessible on network / mobile
  python run_api.py --prod                 # production mode (no reload)
  python run_api.py --host 0.0.0.0 --prod  # production + network access
  python run_api.py --port 8080            # custom port
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path

_here = Path(__file__).parent.resolve()
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from dotenv import load_dotenv
load_dotenv(_here / ".env")


def get_local_ip() -> str:
    """Get the machine's local network IP for mobile access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    parser = argparse.ArgumentParser(
        description="Disaster Response AI System — API Server"
    )
    parser.add_argument("--host", default="0.0.0.0",
                        help="Bind host (default: 0.0.0.0 — accessible on network)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8000)),
                        help="Port (default: $PORT env var or 8000)")
    parser.add_argument("--prod", action="store_true",
                        help="Production mode (no auto-reload, optimized)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of worker processes (prod only)")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn not installed. Run: pip install uvicorn[standard]")
        sys.exit(1)

    os.chdir(_here)
    local_ip = get_local_ip()

    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║       🚨 DISASTER RESPONSE AI SYSTEM — API SERVER               ║
╠══════════════════════════════════════════════════════════════════╣
║  Local     : http://127.0.0.1:{args.port}/ui/index.html          ║
║  Network   : http://{local_ip}:{args.port}/ui/index.html         ║
║  Mobile    : http://{local_ip}:{args.port}/ui/index.html         ║
║  API Docs  : http://127.0.0.1:{args.port}/api/docs               ║
║  Health    : http://127.0.0.1:{args.port}/api/health             ║
║  Mode      : {'PRODUCTION ✓' if args.prod else 'DEVELOPMENT'}                                ║
╚══════════════════════════════════════════════════════════════════╝

  📱 To access from your phone:
     Make sure phone is on the same WiFi network, then open:
     http://{local_ip}:{args.port}/ui/index.html
""")

    uvicorn_kwargs = dict(
        app="api.server:app",
        host=args.host,
        port=args.port,
        log_level="warning" if args.prod else "info",
        access_log=not args.prod,
    )

    if args.prod:
        uvicorn_kwargs["reload"] = False
        if args.workers > 1:
            uvicorn_kwargs["workers"] = args.workers
    else:
        uvicorn_kwargs["reload"] = True
        uvicorn_kwargs["reload_dirs"] = [str(_here / "agents"), str(_here / "api")]

    uvicorn.run(**uvicorn_kwargs)


if __name__ == "__main__":
    main()
