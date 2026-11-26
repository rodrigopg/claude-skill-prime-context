# Shared setup

## Inventory and scope

Inspect active versions, configuration homes, existing instruction files and symlinks, and project memory indexes. Record which rules are personal, machine-specific, harness-specific, or intended for the repository. Keep the most recent authoritative wording when versions conflict and surface material ambiguity. Back up existing entrypoints before replacing them.

## Configure shared rules

1. Choose a private directory independent of the harnesses, for example `~/.config/agent-instructions`. Keep an `AGENTS.md` there for cross-harness global guidance. Keep long or scoped rules in separate Markdown files and state precisely when to read them. Include required reading in plain language so every harness understands it.
2. In Claude Code, import the shared file from `~/.claude/CLAUDE.md` with `@~/.config/agent-instructions/AGENTS.md`. Keep Claude-only additions below it. Claude also loads `~/.claude/rules/`. For rules migrated to the shared directory, keep a compatibility symlink there when needed and avoid loading the same content twice.
3. Point the Codex global `AGENTS.md` in the active Codex home and OpenCode's global `AGENTS.md` in the active OpenCode config directory to the shared file. Typical paths are `~/.codex/AGENTS.md` and `~/.config/opencode/AGENTS.md`. Use a symlink when all global content is shared. For harness-specific additions, generate the entrypoint from the shared file plus the local additions or use a documented extra-instructions setting. Codex's project filename fallback applies only when no higher-priority file exists in that directory.
4. Use the repository's `AGENTS.md` as the project source. Keep a `CLAUDE.md` symlink or `@AGENTS.md` import where needed by Claude Code. Preserve existing `CLAUDE.md` content and path-scoped rules during migration. Convert a scoped rule to nested `AGENTS.md` only when directory scope matches its original scope.

## Share curated memory

- Keep a global `memory/MEMORY.md` index and a separate index for each private project. Identify a project by its Git origin so checkout and worktree names can differ. Record an explicit mapping from origin to its private index in `projects/INDEX.md`. Use a normalized host/owner/repository identity without credentials, the transport, or a trailing `.git`. If no origin exists, register an explicit local identity and document it. Link the global memory index and the project lookup from the shared rules.
- Migrate useful notes with their relative links intact. Put team decisions in tracked project Markdown and personal notes in the private directory. Keep harness-generated histories and memory stores separate. Keep credential values in their vaults.
- Across hosts, sync the shared directory through the team's private channel. Set up entrypoints per host to resolve local paths. Choose an authoritative writer or a sync mechanism that preserves concurrent edits. Preserve machine-specific guidance in local adapters or clearly labeled host sections.

## Use the shared store

`learn` writes durable personal notes to the appropriate shared global or project index. `load` reads the relevant notes through those indexes. `doctor` verifies the pointers and entrypoints. Keep the pre-existing Claude project memory as a migration source. For an unregistered repository, use the existing project-memory behavior.

## Verify

Confirm that each configured entrypoint resolves to the expected global content and that the existing project entrypoint still resolves. Validate relative links inside curated memory. Start fresh sessions for runtime checks. Ask each harness to identify a harmless rule from the global file, the repository instructions, and the project's memory index. Use Claude Code's `/context all` and OpenCode's configuration diagnostics where supported. Confirm that a project-memory check in an unrelated repository does not select the pilot project's notes. Report filesystem verification separately from runtime checks.

## References

- [Claude Code instructions and memory](https://code.claude.com/docs/en/memory)
- [Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [OpenCode instructions](https://opencode.ai/docs/instructions/)
- [OpenCode skills](https://opencode.ai/docs/skills/)
