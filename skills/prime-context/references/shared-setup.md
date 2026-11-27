# Shared setup contract

Prime Context uses format 1 at `$PRIME_CONTEXT_SHARED_HOME`, with
`~/.config/agent-instructions` as the default on Linux, macOS, and Windows.
The store is configured when `.prime-context-shared` contains `format=1`. The
marker also records `created=<ISO8601>`. Doctor reports a missing or unsupported
format as HIGH.

~~~
<shared>/
├── .prime-context-shared
├── .migration-state.json    # Local source-to-copy bindings after migration
├── .state/                  # Local scan cache, audit mappings, and private backups
├── rules/
│   ├── AGENTS.md            # Authored global rules
│   └── *.md                # Other authored rules
├── sources.list            # Ordered inputs to the generated file
├── AGENTS.md                # Generated for Codex and OpenCode
├── memory/
│   ├── MEMORY.md            # Global pointers
│   └── …                   # Global notes and attachments
└── projects/
    ├── INDEX.md
    └── <host>__<owner>__<repo>/
        ├── MEMORY.md        # Project pointers
        └── …               # Project notes and attachments
~~~

Edit global rules in `rules/AGENTS.md` and `rules/*.md`. Each entry in `sources.list`
uses `file`, `glob`, or `cmd` followed by its value. Paths are relative to the
shared store and support `~` expansion. The default glob excludes the
`rules/AGENTS.md` already listed as a file. Command sources run in the shared
directory with a 20-second timeout. Include only commands you trust to produce
rules on stdout. Sync redacts phone numbers and rejects secrets before updating
any generated entrypoint. Rule-file `@imports` are inlined from the importing
file's directory or home for `~` paths, up to five levels. Expansion stops at
cycles and leaves code examples literal. Missing or unreadable imported files or file sources block generation
with exit 2 and make `sync --check` return 1. Failing commands produce warnings
and become fatal with `sync --strict`. Doctor reports file failures as HIGH and
command failures as MED.

## Project identity and memory

Git origins are lowercased and stripped of transport, credentials, port, trailing
slash, and trailing `.git`. Each directory replaces every slash in its key with
two underscores. Nested groups keep every segment.

| Origin | Key | Directory |
| --- | --- | --- |
| https://example.com:8443/Group/Sub/Repo.git | example.com/group/sub/repo | example.com__group__sub__repo |
| ssh://git@example.com:2222/Group/Repo.git/ | example.com/group/repo | example.com__group__repo |
| git@example.com:Group/Repo.git | example.com/group/repo | example.com__group__repo |
| example.com:Repo.git | example.com/repo | example.com__repo |

HTTP, HTTPS, SSH, Git protocol, and scp-style origins are supported. The scp-style
user is optional.

`projects/INDEX.md` records one entry per line as
`- <origin-key> → <dir>/MEMORY.md`. Use `resolve [PATH]` to find the absolute
project index. Run `register [PATH] --apply` for a repository with an origin.
For a project without a usable origin, pass `--local-id ID`. Its key is `local/ID`
and a private `.local-path` file beside its index binds it to the registered
path so `resolve` can look it up later. A valid origin takes precedence and
registering that repository with `--local-id` is an error.

Add one Markdown pointer per line with `append-index INDEXFILE LINE --apply`.
Rapid parallel appends to the same index are serialized and replaced atomically
without per-append backups. Migration preserves prose from older indexes. Each note has frontmatter
in this format:

~~~yaml
---
name: <slug>
description: <one line>
metadata:
  type: user|feedback|project|reference
  share: all|claude-only
---
~~~

An absent `metadata.share` means `all`. Other harnesses must skip notes marked
`claude-only`. Doctor accepts legacy top-level
`type` and reports it as LOW. Store credential values in a vault and only
record where to find them in memory.

`sync --check` exits 1 if a shared note contains a phone number or secret.
`quarantine` previews the affected notes. `quarantine --apply` backs them up
under `.state/backups/` and sets `metadata.share: claude-only`. It prints paths,
line numbers, pattern names, and a count. For format 1, SessionStart caches file
verdicts by file identity, modification time, and size, reports changes already made when the
scan pauses, and resumes on the next run. Unsupported marker formats produce
one warning and skip quarantine. Run `quarantine --apply` for text files over
256 KiB, which are deferred by the session hook. Sensitive text attachments or index entries must be corrected in place
because they do not use note frontmatter. Binaries with a NUL byte in their first
8 KiB are skipped by the scanner.

## Procedure

Use the bundled `shared_sync.py`. In a Claude Code plugin installation it is
available at `${CLAUDE_PLUGIN_ROOT}/scripts/shared_sync.py`. In a standalone
skill installation use `<skill dir>/scripts/shared_sync.py`. Run these commands
with Python 3.8 or newer, substituting the installed script path:

~~~text
python shared_sync.py init --apply
python shared_sync.py migrate
python shared_sync.py migrate --apply
python shared_sync.py sync --apply
python shared_sync.py doctor
~~~

During a 3.1.0 upgrade, `init` backs up and moves a hand-authored top-level
`AGENTS.md` to `rules/AGENTS.md`. If both already contain different rules, merge
them before retrying.

Review the migration plan and close Claude Code sessions before running
`migrate --apply`. The migration copies Claude's
global rules into `rules/AGENTS.md`, then backs up Claude's entrypoint and
replaces its main import with the authored-rules import. If Claude's entrypoint is
a symlink, the backup and edit apply to its resolved target. A legacy link
to the generated `AGENTS.md` is backed up and redirected to the authored file.
Relative imports
to existing files are rewritten to their original locations while surrounding
prose and code examples are preserved. Additional imports inside the shared home
stay in the Claude file and are added as file entries in `sources.list`.
`migrate` and `sync` link shared rules into Claude's rules directory. When
symlinks fail, the commands add imports to Claude's entrypoint. A same-name rule
with different content stays in place in both locations and requires a manual merge.

`migrate`, `sync`, and `doctor` use `$CLAUDE_CONFIG_DIR` or `~/.claude`. Pass
`--claude-home DIR` to override it. The folder named after the current home
directory supplies global memory by default and needs no transcripts.
Use `--global-project=DIR` to select a different source by project folder name
or absolute folder path.
The store records that selection for doctor separately for each Claude home.

Claude replaces each character outside `[A-Za-z0-9]` in the project path with
`-` to form the folder name. Migration checks the first `cwd` in each `*.jsonl`
transcript and stops reading there. It counts malformed records before that
point and counts and ignores starts
whose paths are missing or do not reproduce the folder name, including history
copied from another machine. At least one matching path must remain. All
distinct matching paths must resolve to the same Git origin or registered
local ID. The migration summary gives the mapped count and groups unmapped
folders by reason. Use repeatable `migrate --map=CLAUDE-FOLDER=PATH` for an
explicit mapping to a valid Git origin or to a project already registered with
`--local-id`. Doctor lists the names and count of remaining UNMAPPED folders as MED
and reuses project mappings recorded during migration when available.

Migration preserves subdirectories, attachments, and internal links it can
recreate safely. It copies the first safe index byte-for-byte and merges later
indexes by pointer target, preserving additional prose under
`## Migrated from <folder name>`. It redacts phone numbers from index prose
and link labels. Notes with the same filename and different contents get separate
filenames. Text files with secrets and text attachments with phone numbers are
blocked and reported by path and line. Markdown notes with phone numbers and
unspecified sharing are copied as `claude-only`.

After copying, migration re-scans each source immediately before linking and
copies late additions and edits. A source that keeps changing stays in place.
Claude's mapped memory directories become symlinks to the shared store, with
backups. A blocked file or failed symlink keeps the original directory
in place. The local migration state lets a later run update existing shared copies
when the source changes and preserve edits made only to the shared copy. Doctor
checks for divergence.

Sync generates the shared `AGENTS.md`, plus the entrypoints in `$CODEX_HOME`
(default `~/.codex`) and `$XDG_CONFIG_HOME/opencode` (default `~/.config/opencode`).
The generated file points to the skill's `resolve` mode and the project index.
It backs up existing entrypoints before replacing them the first time.
Keep repository instructions in the repository's `AGENTS.md` and connect Claude
through a `CLAUDE.md` symlink or `@AGENTS.md` import. Preserve repository path-scoped
rules when configuring project entrypoints. Codex's fallback filenames apply
when no higher-priority instruction file exists in that directory.

Start a fresh session in each harness and verify the global rules, repository
instructions, and expected project memory. For Claude Code use `/context all`.
Use OpenCode's configuration diagnostics where available.

## References

- [Claude Code instructions and memory](https://code.claude.com/docs/en/memory)
- [Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [OpenCode instructions](https://opencode.ai/docs/instructions/)
- [OpenCode skills](https://opencode.ai/docs/skills/)
