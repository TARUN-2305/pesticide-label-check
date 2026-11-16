"""API keys (L3 §7). Read from the environment, else from an owner-only file; never logged or echoed."""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from pathlib import Path

from labelclaim.errors import LabelClaimError

DEFAULT_FILE = Path.home() / ".config" / "labelclaim" / "env"
NAMES = ("GROQ_API_KEY", "GEMINI_API_KEY")


class SecretsError(LabelClaimError):
    """The key file is unsafe or malformed. The message never contains a key."""


def load_keys(path: Path = DEFAULT_FILE, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """{name: key} for every known key that is set. Environment variables win over the file."""
    environ = os.environ if environ is None else environ
    keys: dict[str, str] = {}
    if path.exists():
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise SecretsError(f"{path} has mode {mode:o}; run: chmod 600 {path}")
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            name, sep, value = line.removeprefix("export ").partition("=")
            if not sep:
                raise SecretsError(f"{path} line {number}: expected NAME=value")
            if name.strip() in NAMES and value.strip().strip("'\""):
                keys[name.strip()] = value.strip().strip("'\"")
    for name in NAMES:
        if environ.get(name):
            keys[name] = environ[name]
    return keys
