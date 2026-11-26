# Compaction

Compaction preserves session continuity. Use `learn` for durable project knowledge.
The [summary policy](../assets/compaction-policy.md) describes what matters after a
session is compacted.

## Commands

- **`compaction status`** reports the active harness, version, settings scope,
  threshold and any custom summary prompt or hook. Identify project and managed
  overrides before claiming what applies to the session.
- **`compaction enable`** applies the appropriate settings below. Start with status.
  Preserve unrelated settings and earlier thresholds. If a competing hook or
  custom prompt exists, show the overlap and ask which should be used.
- **`compaction disable`** restores only the settings changed by this command.
  The harness can continue using its built-in compaction.

Before editing, take a timestamped local backup. Record each changed key, its
original value or absence, and its applied value in a private record beside
the affected config file, outside shared and synced directories. If the config
itself is synced, use an unsynced local state directory and key the record by
the config file's absolute path. Keep backups there too. Repeated enables
are a no-op when settings match. When disabling, restore a key only if its
current value still matches the applied value. Report intervening edits for
reconciliation. Preserve existing JSONC comments and TOML tables.

## Claude Code

Install the Claude Code plugin to register its automatic `PreCompact` hook. Merge
these keys into the existing `env` object of user settings:

```json
{
  "env": {
    "PRIME_CONTEXT_COMPACTION": "1",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "85"
  }
}
```

Keep a configured threshold below 85. The percentage refers to Claude's
auto-compact window. Claude adds the policy to the summary instructions. The
hook is silent without the opt-in flag and applies to automatic compaction.
If a DataAgile PreCompact hook already supplies a policy, coordinate the
replacement before enabling Prime Context. Preserve unrelated hooks.

## Codex

Determine whether the active model and provider use local compaction before
editing the summary prompt. Only with confirmed local compaction, set the
documented `compact_prompt` value to the shared policy, preserving an existing
custom prompt unless the user approves replacing it. Remote compaction, such
as the OpenAI Responses path, uses the provider's summary policy and bypasses
this setting. For remote or unknown compaction, leave `compact_prompt` untouched
and report that Prime Context has not applied a custom summary policy.
Codex's `PreCompact` ignores plain text on stdout.

Keep the existing timing by default. If the user asks for 85%, verify the
effective context window of the configured model and use the integer floor of
85% of that limit in `model_auto_compact_token_limit`, with scope `total`. Preserve
a lower threshold. Leave timing unchanged if the window is unknown or models
with different context windows share the configuration.

## OpenCode v2

Use its native summary. To target roughly 85%, set `compaction.buffer` to `"15%"`
in the active JSON or JSONC settings when this would preserve or improve the
current reserve. Leave the existing buffer when it already reserves at least
15%, including the built-in default. Respect an explicitly disabled
`compaction.auto`. Report an unknown threshold before changing an existing
token-based buffer. OpenCode retains its native summary format.

## Verify

Validate the config and open a fresh session. In a scratch session, give the
assistant a harmless requirement, a decision, and a pending action. Compact and
verify that the continuation can recover each. Manual compaction tests the
applicable summary settings but does not exercise Claude's auto-only hook.
Verify that hook separately with the opt-in flag and confirm the configured
threshold in a real automatic compaction before claiming a runtime result.

The Claude approach builds on the [proposal by João Vitor Ribeiro Santos](https://github.com/dataagile/claude-marketplace/pull/205).

- [Claude Code hooks](https://code.claude.com/docs/en/hooks#precompact)
- [Codex local and remote compaction paths](https://github.com/openai/codex/blob/main/codex-rs/core/src/tasks/compact.rs)
- [Codex hooks](https://learn.chatgpt.com/docs/hooks#precompact)
- [OpenCode compaction](https://opencode.ai/docs/compaction/)
