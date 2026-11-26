# prime-context

A Claude Code plugin for efficient project context: a **thin AGENTS.md router** plus
**area context files loaded on demand** — never everything at once.

## Quick start

| Want to | Run Prime Context with |
| --- | --- |
| Share rules and curated memory across assistants | `setup shared` |
| Load context for an area | The area name, such as `api` |
| Record a durable learning | `learn` |
| Check instructions and memory links | `doctor` |
| Inspect or enable session compaction | `compaction status` or `compaction enable` |

In Claude Code, invoke `/prime-context:prime-context <mode>`. In Codex and
OpenCode, ask the assistant to use the Prime Context skill with that mode.

## Philosophy

`AGENTS.md` must be **thin**. It is loaded in every session — every line costs tokens in
every conversation. Detailed content lives in `.claude/context/<area>.md` and is read
**only when the task requires it**.

prime-context covers both directions of project memory: `<area>` is the **read path**
(assemble the right context into a session) and the bare call is the **write path**
(`learn` — persist the session's learnings into those same files). Audit tools like
[claude-docu-optimizer](https://github.com/kojott/claude-docu-optimizer) inspired the
CLAUDE.md rubric that `improve`/`doctor` apply.

## Commands

| Command | What it does |
|---------|--------------|
| `/prime-context` | **Learn**: capture this session's corrections, decisions and pitfalls into the context files |
| `/prime-context <area>` | Load one area's context (e.g. `filament`, `api`, `prod`); fuzzy-matches file names |
| `/prime-context improve` | Refactor a bloated `AGENTS.md` → thin router + `.claude/context/` files |
| `/prime-context setup` | Bootstrap the context structure in a new project from scratch |
| `/prime-context setup shared` | Share rules and curated memory across Claude Code, Codex, and OpenCode |
| `/prime-context doctor` | Audit the structure: dangling routes, orphan files, dead memory pointers, staleness, weight |

Every `/prime-context <area>` load ends with a **Verification** block listing the files
actually read — so silent drift is impossible.

## Installation

As a plugin (recommended — enables the session-start drift warnings):

```bash
claude plugin marketplace add rodrigopg/claude-plugins
claude plugin install prime-context@rodrigopg
```

Or manually as a bare skill (no hooks):

```bash
git clone https://github.com/rodrigopg/claude-skill-prime-context /tmp/prime-context
cp -r /tmp/prime-context/skills/prime-context ~/.claude/skills/
```

### Codex and OpenCode

For a fresh install, run the following after the release reaches the default branch:

```sh
git clone https://github.com/rodrigopg/claude-skill-prime-context ~/prime-context
mkdir -p ~/.agents/skills
cp -R ~/prime-context/skills/prime-context ~/.agents/skills/
```

Open a new session and ask it to use the `prime-context` skill. To update, pull
the checkout and copy the skill folder again. The portable skill includes all
references and assets. Your project and personal memory files remain outside it.

## Shared context across harnesses

Run `/prime-context setup shared` in Claude Code. For Codex and OpenCode, copy
`skills/prime-context/` into `~/.agents/skills/prime-context/` and ask the
assistant to use Prime Context in `setup shared` mode. See the
[shared setup guide](skills/prime-context/references/shared-setup.md).

Retain the existing standalone setup for projects whose context is local to Claude Code.

## Session compaction

Use `compaction status` to inspect current behavior, `compaction enable` to
opt in, and `compaction disable` to restore the previous settings. Claude Code
uses the bundled hook, Codex can apply a custom prompt with local compaction,
and OpenCode v2 uses its own summary and buffer. Codex remote compaction keeps
the provider's summary policy. See the [compaction guide](skills/prime-context/references/compaction.md).

If you installed `share-harness-instructions`, use `setup shared` to check your
existing Markdown paths. Once Prime Context is available in a new session,
remove the older skill or plugin. Your existing rules and memories stay in place.

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
