"""python -m labelclaim.api [--register build/register.sqlite] [--port 8000] | --export-openapi FILE"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from labelclaim.api.app import Settings, create_app, openapi_document
from labelclaim.assistant.providers import build_clients
from labelclaim.assistant.secrets import load_keys

REPO = Path(__file__).resolve().parents[3]


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m labelclaim.api")
    parser.add_argument("--register", type=Path, default=REPO / "build" / "register.sqlite")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--rate", type=int, default=60, help="requests per minute per client")
    parser.add_argument("--export-openapi", type=Path)
    parser.add_argument("--no-model", action="store_true", help="serve without /v1/ask models (L3)")
    parser.add_argument("--web", type=Path, default=REPO / "web", help="static web app (L4); 'none' to omit")
    parser.add_argument("--ask-per-day", type=int, default=800, help="daily cap on /v1/ask (L4 §3)")
    parser.add_argument("--behind-proxy", action="store_true", help="trust X-Forwarded-For (behind a proxy)")
    args = parser.parse_args()
    if args.export_openapi:
        settings = Settings(register=args.register, rate_per_minute=args.rate)
        document = openapi_document(settings)
        args.export_openapi.write_text(
            json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        return
    clients = {} if args.no_model else build_clients(load_keys())  # L3 §6-7: keys never printed
    web = None if str(args.web) == "none" or not args.web.is_dir() else args.web
    settings = Settings(register=args.register, rate_per_minute=args.rate, chat_clients=dict(clients),
                        web_dir=web, ask_per_day=args.ask_per_day)  # fmt: skip
    # Behind a hosting proxy the client address is in X-Forwarded-For; trusted only when asked, since a direct
    # client could forge it to dodge the per-client bucket (the daily cap on /v1/ask is global either way).
    trusted = "*" if args.behind_proxy else None
    uvicorn.run(create_app(settings), host=args.host, port=args.port, workers=1, log_level="info",
                proxy_headers=args.behind_proxy, forwarded_allow_ips=trusted)  # fmt: skip


if __name__ == "__main__":
    main()
