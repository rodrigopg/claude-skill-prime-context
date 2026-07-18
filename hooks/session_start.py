#!/usr/bin/env python3
"""SessionStart hook: surface available context areas and flag routing drift.

Zero-cost (no LLM calls). Silent on projects without a prime-context structure.
Cross-platform (macOS, Linux, Windows).
"""
import re
import sys
from pathlib import Path


def main() -> int:
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
        try:
            text = agents.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return 0
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
        sys.exit(0)
