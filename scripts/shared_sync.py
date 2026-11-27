#!/usr/bin/env python3
"""Run the shared context CLI bundled with the portable skill."""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "skills/prime-context/scripts/shared_sync.py"),
        run_name="__main__",
    )
