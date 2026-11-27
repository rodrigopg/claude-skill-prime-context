"""Keep test subprocesses inside the disposable fixture."""
import os


def isolated_env(root):
    home = root / "home"
    config = root / "config"
    return dict(
        os.environ,
        HOME=str(home),
        USERPROFILE=str(home),
        PRIME_CONTEXT_SHARED_HOME=str(home / ".config/agent-instructions"),
        CODEX_HOME=str(config / "codex"),
        XDG_CONFIG_HOME=str(config / "xdg"),
        XDG_DATA_HOME=str(config / "data"),
        XDG_STATE_HOME=str(config / "state"),
        XDG_CACHE_HOME=str(config / "cache"),
        XDG_RUNTIME_DIR=str(config / "runtime"),
        APPDATA=str(config / "appdata"),
        LOCALAPPDATA=str(config / "localappdata"),
        OPENCODE_CONFIG_DIR=str(config / "opencode"),
        CLAUDE_CONFIG_DIR=str(home / ".claude"),
        TMPDIR=str(root),
        TMP=str(root),
        TEMP=str(root),
        PYTHONIOENCODING="utf-8",
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
