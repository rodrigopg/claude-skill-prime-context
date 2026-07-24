# prime-context

A Claude Code plugin for efficient project context: a **thin AGENTS.md router** plus
**area context files loaded on demand** — never everything at once.

## Philosophy

`AGENTS.md` must be **thin**. It is loaded in every session — every line costs tokens in
every conversation. Detailed content lives in `.claude/context/<area>.md` and is read
**only when the task requires it**.

prime-context is the **read path** of project memory: it assembles the right context into a
session. It pairs naturally with write-path tools like
[claude-reflect](https://github.com/BayramAnnakov/claude-reflect) (which persists learnings
out of sessions) and with audit tools like
[claude-docu-optimizer](https://github.com/kojott/claude-docu-optimizer) (whose CLAUDE.md
rubric this plugin's `improve`/`doctor` commands apply at restructure time).

## Commands

| Command | What it does |
|---------|--------------|
| `/prime-context` | Load general context for the current project (memory + AGENTS.md) |
| `/prime-context <area>` | Load one area's context (e.g. `filament`, `api`, `prod`); fuzzy-matches file names |
| `/prime-context improve` | Refactor a bloated `AGENTS.md` → thin router + `.claude/context/` files |
| `/prime-context setup` | Bootstrap the context structure in a new project from scratch |
| `/prime-context doctor` | Audit the structure: dangling routes, orphan files, dead memory pointers, staleness, weight |

Every `load` ends with a **Verification** block listing the files actually read — so silent
drift is impossible.

## Installation

As a plugin (recommended — enables the session-start drift warnings):

```bash
claude plugin marketplace add rodrigopg/claude-plugins
claude plugin install prime-context@rodrigopg
```

Or from this repo's own marketplace:

```bash
claude plugin marketplace add rodrigopg/claude-skill-prime-context
claude plugin install prime-context@prime-context-marketplace
```

Or manually as a bare skill (no hooks):

```bash
git clone https://github.com/rodrigopg/claude-skill-prime-context /tmp/prime-context
cp -r /tmp/prime-context/skills/prime-context ~/.claude/skills/
```

## Structure managed by the plugin

```
project/
├── AGENTS.md               # Thin: overview + routing table + rules + PR checklist
├── CLAUDE.md               # Symlink → AGENTS.md (or a file containing @AGENTS.md on Windows)
└── .claude/
    └── context/
        ├── filament.md     # Loaded only when working with Filament
        ├── api.md          # Loaded only when working on the API
        ├── db.md           # Loaded only when the schema is needed
        └── <area>.md       # One per work domain

~/.claude/projects/<hash>/memory/
├── MEMORY.md               # Pointer index: one line per memory file, never inline content
└── *.md                    # Self-contained learnings, referenced from MEMORY.md
```

`<hash>` is the project's absolute path with `/` replaced by `-`
(e.g. `/home/dev/app` → `-home-dev-app`) — Claude Code's project-folder convention.

### MEMORY.md format

```markdown
- [Short title](filename.md) — one-line hook describing when this matters
```

One pointer per line. Content lives in the linked files. `doctor` flags dead pointers and
memory older than 7 days.

## Session-start hook

When installed as a plugin, a zero-cost hook (no LLM calls) runs at session start:

- announces the available context areas (`/prime-context <area>` discoverability), and
- warns when the AGENTS.md routing table points at missing files, or context files exist
  that no route mentions.

It is completely silent on projects without a prime-context structure.

## Windows / no-symlink environments

Where symlinks are unavailable (Windows without admin rights, `core.symlinks=false`),
`setup` creates a regular `CLAUDE.md` containing just `@AGENTS.md` — Claude Code's import
syntax — giving the same single source of truth without a symlink.

## Development

```bash
python3 tests/test_session_start.py
```

## License

MIT
