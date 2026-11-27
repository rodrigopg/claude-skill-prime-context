#!/usr/bin/env python3
"""SessionStart hook: surface available context areas and flag routing drift.

No LLM calls. Shared memory quarantine has a two-second timeout.
Cross-platform (macOS, Linux, Windows).
"""
import os
import re
import subprocess
import sys
from pathlib import Path


def quarantine_memory():
    shared = Path(os.environ.get("PRIME_CONTEXT_SHARED_HOME", str(Path.home() / ".config/agent-instructions")))
    marker = shared.expanduser() / ".prime-context-shared"
    try:
        if not marker.is_file():
            return
        lines = marker.read_bytes().splitlines()
    except FileNotFoundError:
        return
    except OSError:
        print("prime-context WARNING: shared memory marker could not be read")
        return
    if [line for line in lines if line.startswith(b"format=")] != [b"format=1"]:
        print("prime-context WARNING: unsupported shared memory format")
        return
    script = Path(__file__).resolve().parents[1] / "scripts/shared_sync.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script), "quarantine", "--apply", "--budget", "1.35"],
            capture_output=True, timeout=2, encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired):
        print("prime-context WARNING: shared memory quarantine did not finish")
        return
    count = re.search(r"^Quarantined (\d+) note\(s\)$", result.stdout, re.MULTILINE)
    if count and int(count[1]):
        print(f"prime-context: quarantined {count[1]} shared memory note(s)")
    if result.returncode:
        print("prime-context WARNING: shared memory quarantine needs attention")


def main() -> int:
    quarantine_memory()
    root = Path.cwd()
    context_dir = root / ".claude" / "context"
    if not context_dir.is_dir():
        return 0

    areas = sorted(p.stem for p in context_dir.glob("*.md"))
    if not areas:
        return 0

    print(f"prime-context: {len(areas)} area(s) available ({', '.join(areas)}) — /prime-context <area> to load")

    agents = root / "AGENTS.md"
    if not agents.is_file():
        agents = root / "CLAUDE.md"
    if agents.is_file():
        text = agents.read_text(encoding="utf-8", errors="replace")
        routed = set(re.findall(r"\.claude/context/([\w.-]+)\.md", text))
        dangling = sorted(r for r in routed if r not in areas)
        orphans = sorted(a for a in areas if a not in routed)
        if dangling:
            print(f"prime-context WARNING: routing table points at missing file(s): {', '.join(dangling)} — run /prime-context doctor")
        if orphans:
            print(f"prime-context: unrouted context file(s): {', '.join(orphans)} — consider adding to the AGENTS.md routing table")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Never block session start on a hook error.
        print("prime-context WARNING: session start checks did not finish")
        sys.exit(0)
