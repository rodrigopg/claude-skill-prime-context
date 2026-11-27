"""Smoke-test the command Claude Code uses for automatic compaction."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from isolated_env import isolated_env

ROOT = Path(__file__).resolve().parents[1]
HOOK = Path("hooks/pre_compact.py")
POLICY = Path("skills/prime-context/assets/compaction-policy.md")


def run_hook(command, plugin_root, opt_in):
    env = isolated_env(plugin_root.parent)
    if opt_in:
        env["PRIME_CONTEXT_COMPACTION"] = "1"
    else:
        env.pop("PRIME_CONTEXT_COMPACTION", None)

    # Claude expands the plugin path before handing the command to the shell.
    launcher, path = command.split(maxsplit=1)
    assert launcher == "python3" and path.startswith('"') and path.endswith('"')
    path = path[1:-1].replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
    return subprocess.run(
        [sys.executable, path], input="", capture_output=True, encoding="utf-8",
        env=env, check=True, timeout=10,
    ).stdout


if __name__ == "__main__":
    config = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
    [entry] = config["hooks"]["PreCompact"]
    assert entry["matcher"] == "auto"
    [hook] = entry["hooks"]
    assert hook["type"] == "command"

    with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temporary:
        plugin = Path(temporary) / "plugin path with spaces"
        for relative in (HOOK, POLICY):
            target = plugin / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        assert run_hook(hook["command"], plugin, False) == ""
        output = run_hook(hook["command"], plugin, True)
        assert output == (plugin / POLICY).read_text(encoding="utf-8")
        assert 0 < len(output) < 10_000

    print("test_pre_compact: OK")
