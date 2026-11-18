"""Pilot logging for private tests (L4 §9, NFR-5). Off unless the operator starts the server with --pilot-log;
when on, the page tells testers that their questions, the answers and their ratings are saved, and not to type
personal details. Records hold no IP address and no request headers. The file is created readable by its owner
only."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class PilotLog:
    def __init__(self, path: Path, clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self.clock = clock
        self._lock = threading.Lock()

    def write(self, kind: str, request_id: str, **fields: Any) -> None:
        at = datetime.fromtimestamp(self.clock(), UTC).strftime("%Y-%m-%dT%H:%MZ")  # to the minute is enough
        line = json.dumps({"at": at, "kind": kind, "request_id": request_id, **fields}, ensure_ascii=False)
        with self._lock:
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as f:
                f.write(line + "\n")
