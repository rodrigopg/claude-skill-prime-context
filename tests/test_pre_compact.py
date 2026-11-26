"""Smoke tests for the opt-in automatic compaction hook."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks/pre_compact.py"
POLICY = ROOT / "skills/prime-context/assets/compaction-policy.md"


def run_hook(opt_in):
    env = os.environ.copy()
    if opt_in:
        env["PRIME_CONTEXT_COMPACTION"] = "1"
    else:
        env.pop("PRIME_CONTEXT_COMPACTION", None)
    return subprocess.run(
        [sys.executable, str(HOOK)], input=b"", capture_output=True,
        env=env, check=True, timeout=10,
    ).stdout.decode("utf-8").replace("\r\n", "\n")


if __name__ == "__main__":
    config = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
    assert [entry["matcher"] for entry in config["hooks"]["PreCompact"]] == ["auto"]
    assert run_hook(False) == ""
    assert run_hook(True) == POLICY.read_text(encoding="utf-8")
    assert 0 < len(run_hook(True)) < 10_000
    print("test_pre_compact: OK")
