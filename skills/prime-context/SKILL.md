---
name: prime-context
description: On-demand project context loading with a thin AGENTS.md router. Loads area-specific context files only when the task needs them, refactors bloated AGENTS.md/CLAUDE.md into the thin architecture, bootstraps new projects, and audits the context structure for drift. Commands: load (default), improve, setup, doctor.
argument-hint: "[area|improve|setup|doctor]"
allowed-tools: [Read, Glob, Grep, Edit, Write, Bash]
---

# Prime Context

Manage project context efficiently — never load everything at once.

## Core philosophy

**AGENTS.md must be thin.** It is loaded in EVERY session — every line costs tokens in every conversation.
Detailed content lives in `.claude/context/<area>.md` and is read **only when the task requires it**.
AGENTS.md contains only: overview (2 lines), routing table, non-negotiable rules, PR checklist.

This is the **read path** of project memory: it assembles the right context into a session.
It pairs naturally with write-path tools (e.g. claude-reflect) that persist learnings out of sessions —
prime-context reads the very files those tools produce.

## MEMORY.md format (specification)

`MEMORY.md` lives at `~/.claude/projects/<hash>/memory/MEMORY.md`, where `<hash>` is the
project's absolute path with every `/` replaced by `-` (Claude Code's project-folder convention,
e.g. `/home/dev/app` → `-home-dev-app`). It is a **pointer index only** — one line per memory
file, never inline content:

```markdown
- [Short title](filename.md) — one-line hook describing when this matters
```

Each referenced memory file is self-contained Markdown, optionally with frontmatter
(`name`, `description`, `type: user|feedback|project|reference`). Rules:

- MEMORY.md never holds memory content, only pointers — keeps the index cheap to scan.
- Dead pointers (file missing) are flagged by `doctor` and during `load`.
- Memory files are point-in-time — warn when the newest is older than 7 days.

---

## Command: `load` (default — no argument, or an area name)

Load context for the current project on demand.

**Flow:**
1. Read `~/.claude/projects/<hash>/memory/MEMORY.md` if it exists; then read every file it lists.
   Skip silently if there is no memory directory — memory is optional.
2. Resolve the area argument, if given:
   - Exact filename match on `.claude/context/<area>.md` wins.
   - Otherwise case-insensitive substring match against files in `.claude/context/`
     (e.g. `filament` matches `php-filament.md`).
   - Zero or multiple matches → list the available areas and ask which one.
3. No argument: read `AGENTS.md` (or `CLAUDE.md`) and present the general summary.
4. If the task at hand clearly touches several areas, read the relevant files in parallel.

**Output format:**
```
## Context loaded — <area or "general">

### Relevant now
<3-5 critical points for this session>

### Known pitfalls
<Applicable learnings from memory>

### Quick reference
<Most-used commands or configs>

### Verification
<Files actually read, one per line, with approximate size — so drift is visible>
```

The **Verification** block is mandatory: list each file that was actually read and its
approximate line count. If a routed file was missing, say so explicitly instead of omitting it.

---

## Command: `improve`

**Goal:** take a bloated AGENTS.md (any project) and refactor it into the thin + context-files architecture.

**Flow:**

1. Read the entire `AGENTS.md` (or `CLAUDE.md`) at the CWD.
2. Identify natural groupings by area (e.g. Filament, API, DB, prod, multi-tenancy).
3. For each area, create `.claude/context/<area>.md` with that area's detailed content.
4. Rewrite `AGENTS.md` following the **thin template** below.
5. Ensure `CLAUDE.md` points at `AGENTS.md` (see symlink/fallback rules in `setup`).

**Thin AGENTS.md template:**
```markdown
# <Project Name>

<1-2 line description: what it does, main stack>

## Load context before working

Before starting any task, read the matching context file:

| Area | File |
|------|------|
| <area 1> | `.claude/context/<area1>.md` |
| <area 2> | `.claude/context/<area2>.md` |

If a task touches multiple areas, read the relevant files in parallel.

## Non-negotiable rules (always apply)

<Only rules that apply to EVERY task — max 8 concise bullets>

## Checklist before opening a PR

<Full checklist — always worth keeping here>

## Essential commands

<Only the most-used day-to-day commands>

<Any tool/MCP auto-managed block goes at the end, untouched>
```

**Quality rubric — apply while restructuring** (aligned with documented CLAUDE.md best practices):

- Target the thin AGENTS.md at **≤ ~2.5k tokens (~100–150 lines)**; treat 4k as a hard ceiling.
- **Static content first, dynamic last** (cache-friendly ordering): overview, routing table,
  rules and checklist are static; anything that changes often (learnings, gotchas) belongs in
  context files, not in AGENTS.md.
- Keep total imperative instructions in AGENTS.md well under 150 — merge similar rules,
  push details into context files.
- Each context file gets the header `# Context: <Area>` and must be self-contained.

**Improve rules:**
- Never invent content — only reorganize what already exists in the original file.
- Auto-managed blocks (`<laravel-boost-guidelines>`, `## graphify`, etc.) go at the end of
  AGENTS.md, byte-for-byte intact.
- **Idempotent re-runs:** if `.claude/context/` already has files, merge new content into the
  matching area file section by section — never blind-overwrite; when the same topic exists in
  both with conflicting content, keep both versions side by side under a `<!-- MERGE: review -->`
  comment and tell the user. Running `improve` on an already-thin AGENTS.md is a no-op that
  reports "already thin" with the current line/token count.
- Afterwards, report: AGENTS.md line count before and after, and the list of files created/updated.

---

## Command: `setup`

**Goal:** configure the context structure from scratch in a new project.

**Flow:**

1. Use the CWD as project root (ask if ambiguous).
2. Ask: "Describe the project in 1-2 lines (what it does, stack, for whom)."
3. Ask: "What are the main work areas? (e.g. API, database, infra, frontend)" — suggest
   candidates based on the detected stack.
4. Create `.claude/context/<area>.md` for each area with the header
   `# Context: <Area>` and a `<!-- Fill in as the project evolves -->` comment.
5. Create `AGENTS.md` from the thin template (routing table pointing at the created areas).
6. Make `CLAUDE.md` resolve to `AGENTS.md`:
   - Preferred: symlink `CLAUDE.md → AGENTS.md`.
   - **Fallback (Windows, `core.symlinks=false`, or any environment where symlinks fail):**
     create a regular `CLAUDE.md` containing only the import line `@AGENTS.md` — Claude Code's
     import syntax gives the same single-source-of-truth effect without a symlink.
7. Create `~/.claude/projects/<hash>/memory/MEMORY.md` containing the format spec header:
   ```markdown
   # Memory index — one pointer per line, content lives in the linked files
   <!-- - [Short title](filename.md) — one-line hook -->
   ```

**Setup rules:**
- If `AGENTS.md` already exists → offer `improve` instead of overwriting.
- If `CLAUDE.md` is already a symlink or an `@AGENTS.md` import → leave it alone.
- If `CLAUDE.md` is a regular file with real content → ask before replacing.

**After setup, report:** files created, how to fill context files as the project evolves,
and how to add learnings (a file in `memory/` + a pointer line in `MEMORY.md`).

---

## Command: `doctor`

**Goal:** audit the context structure for drift. Read-only — reports, never fixes silently.

**Checks:**

1. **Dangling routes** — entries in the AGENTS.md routing table whose
   `.claude/context/<area>.md` file does not exist.
2. **Orphan context files** — files in `.claude/context/` missing from the routing table.
3. **Dead memory pointers** — lines in MEMORY.md referencing files that don't exist.
4. **Stale memory** — newest memory file older than 7 days.
5. **AGENTS.md weight** — line count and approximate token estimate (~4 chars/token);
   flag over ~150 lines / 2.5k tokens, hard-flag over 4k tokens.
6. **Ordering** — dynamic-looking sections (learnings, gotchas, recent changes) sitting above
   static sections in AGENTS.md (cache-hostile).
7. **CLAUDE.md linkage** — CLAUDE.md is neither a symlink to AGENTS.md nor an `@AGENTS.md`
   import (drift risk: two diverging sources of truth).

**Output:** one line per finding with severity (HIGH/MED/LOW) and the specific fix.
End with `doctor: N findings` or `doctor: clean`. Offer to apply fixes only after reporting.

---

## General rules

- Never modify context files during `load` — read only.
- Blocks auto-managed by MCP servers are untouchable.
- Memory files are point-in-time — warn when > 7 days without updates.
- Unrecognized mode: list available commands (`load`, `improve`, `setup`, `doctor`) and ask.
