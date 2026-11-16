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
    args = parser.parse_args()
    if args.export_openapi:
        settings = Settings(register=args.register, rate_per_minute=args.rate)
        document = openapi_document(settings)
        args.export_openapi.write_text(
            json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        return
    clients = {} if args.no_model else build_clients(load_keys())  # L3 §6-7: keys never printed
    settings = Settings(register=args.register, rate_per_minute=args.rate, chat_clients=dict(clients))
    uvicorn.run(create_app(settings), host=args.host, port=args.port, workers=1, log_level="info")


if __name__ == "__main__":
    main()
