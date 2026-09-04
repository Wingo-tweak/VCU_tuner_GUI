"""Best-effort, non-systemwide installation of the small GUI dependency set."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys


PROJECT = Path(__file__).resolve().parents[1]
REQUIREMENTS = PROJECT / "requirements.txt"


def _state_directory() -> Path:
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "NinebotVCUTuner"
    if os.environ.get("XDG_STATE_HOME"):
        return Path(os.environ["XDG_STATE_HOME"]) / "NinebotVCUTuner"
    return Path.home() / ".local" / "state" / "NinebotVCUTuner"


def _dependency_available() -> bool:
    return importlib.util.find_spec("tkinterdnd2") is not None


def _write_marker(marker: Path, fingerprint: str) -> None:
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        temporary = marker.with_suffix(".tmp")
        temporary.write_text(fingerprint + "\n", encoding="ascii")
        temporary.replace(marker)
    except OSError:
        pass


def ensure_runtime_dependencies(
    requirements: Path = REQUIREMENTS,
    state_directory: Path | None = None,
) -> bool:
    """Install requirements once and continue safely if installation is unavailable."""
    try:
        content = requirements.read_bytes()
    except OSError:
        return False
    fingerprint = hashlib.sha256(content).hexdigest()
    state = state_directory or _state_directory()
    marker = state / "requirements.sha256"
    try:
        recorded = marker.read_text(encoding="ascii").strip()
    except OSError:
        recorded = None

    available = _dependency_available()
    if available and recorded in (None, fingerprint):
        _write_marker(marker, fingerprint)
        return True

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--quiet",
    ]
    # A virtual environment is already isolated; --user is invalid there.
    if sys.prefix == getattr(sys, "base_prefix", sys.prefix):
        command.append("--user")
    command.extend(("-r", str(requirements)))

    log_handle = None
    output = subprocess.DEVNULL
    try:
        state.mkdir(parents=True, exist_ok=True)
        log_handle = (state / "dependency-install.log").open("wb")
        output = log_handle
    except OSError:
        pass
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        if log_handle is not None:
            log_handle.close()
    if completed.returncode != 0:
        return False
    importlib.invalidate_caches()
    if not _dependency_available():
        return False
    _write_marker(marker, fingerprint)
    return True
