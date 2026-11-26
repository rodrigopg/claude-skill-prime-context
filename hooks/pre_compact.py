"""Supply the summary policy to opted-in Claude Code sessions."""
import os
from pathlib import Path


def main():
    if os.environ.get("PRIME_CONTEXT_COMPACTION") != "1":
        return
    policy = (
        Path(__file__).resolve().parents[1]
        / "skills" / "prime-context" / "assets" / "compaction-policy.md"
    )
    try:
        content = policy.read_text(encoding="utf-8")
    except OSError:
        return
    print(content, end="")


if __name__ == "__main__":
    main()
