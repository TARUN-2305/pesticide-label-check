"""python -m labelclaim.api [--register build/register.sqlite] [--port 8000] | --export-openapi FILE"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from labelclaim.api.app import Settings, create_app, openapi_document

REPO = Path(__file__).resolve().parents[3]


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m labelclaim.api")
    parser.add_argument("--register", type=Path, default=REPO / "build" / "register.sqlite")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--rate", type=int, default=60, help="requests per minute per client")
    parser.add_argument("--export-openapi", type=Path)
    args = parser.parse_args()
    settings = Settings(register=args.register, rate_per_minute=args.rate)
    if args.export_openapi:
        document = openapi_document(settings)
        args.export_openapi.write_text(
            json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        return
    uvicorn.run(create_app(settings), host=args.host, port=args.port, workers=1, log_level="info")


if __name__ == "__main__":
    main()
