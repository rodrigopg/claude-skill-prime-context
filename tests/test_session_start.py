#!/usr/bin/env python3
"""Self-check for hooks/session_start.py — run: python3 tests/test_session_start.py"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "session_start.py"


def run_in(tmp: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(HOOK)], cwd=tmp, capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, f"hook must always exit 0, got {result.returncode}"
    return result.stdout


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # 1. No structure → silent
        assert run_in(tmp) == "", "must be silent without .claude/context"

        # 2. Areas present → announced
        ctx = tmp / ".claude" / "context"
        ctx.mkdir(parents=True)
        (ctx / "api.md").write_text("# Context: API\n")
        (ctx / "db.md").write_text("# Context: DB\n")
        out = run_in(tmp)
        assert "2 area(s)" in out and "api" in out and "db" in out, out

        # 3. Dangling route + orphan detected
        (tmp / "AGENTS.md").write_text(
            "| api | `.claude/context/api.md` |\n| infra | `.claude/context/infra.md` |\n"
        )
        out = run_in(tmp)
        assert "missing file(s): infra" in out, out
        assert "unrouted context file(s): db" in out, out

    print("test_session_start: OK")


if __name__ == "__main__":
    main()
