# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [2.0.0] - 2026-07-17

### Added
- **Plugin packaging** — `.claude-plugin/plugin.json` + `marketplace.json`; installable via
  `claude plugin marketplace add rodrigopg/claude-skill-prime-context`.
- **`doctor` command** — read-only structure audit: dangling routes, orphan context files,
  dead memory pointers, stale memory (>7 days), AGENTS.md weight (2.5k-token target /
  4k ceiling), cache-hostile section ordering, CLAUDE.md linkage drift.
- **SessionStart hook** (`hooks/session_start.py`) — zero-LLM-cost: announces available
  context areas and warns about routing drift at session start; silent on projects without
  a prime-context structure; always exits 0 (never blocks a session).
- **MEMORY.md format specification** — pointer-index format is now defined in SKILL.md and
  README (it was previously referenced but never specified).
- **Verification block** — every `load` now reports which files were actually read.
- **Fuzzy area resolution** — `load <area>` falls back to case-insensitive substring match;
  lists available areas on zero/multiple matches.
- **Windows fallback** — where symlinks are unavailable, `CLAUDE.md` is created as a regular
  file containing the `@AGENTS.md` import.
- **Quality rubric in `improve`** — token targets (~2.5k ideal / 4k max), static-first
  cache-friendly ordering, instruction-count ceiling.
- **Idempotency contract for `improve`** — section-by-section merge, `<!-- MERGE: review -->`
  conflict markers, no-op with report on already-thin files.
- **LICENSE** (MIT), CHANGELOG, hook self-check test (`tests/test_session_start.py`).

### Changed
- **SKILL.md rewritten in English** (was Portuguese) and moved to `skills/prime-context/SKILL.md`
  (plugin layout).
- README now documents the memory machinery (`MEMORY.md`, `~/.claude/projects/<hash>/memory/`)
  that `load` depends on — previously omitted.

### Removed
- Undocumented `bd remember` external-tool reference — learnings are added as a file in
  `memory/` plus a pointer line in `MEMORY.md`.

## [1.0.0] - 2026-04-22

### Added
- Initial release: `load`/`improve`/`setup` as a prose-only skill (SKILL.md + README).
