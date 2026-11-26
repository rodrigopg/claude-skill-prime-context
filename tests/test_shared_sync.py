"""Exercise the shared format with disposable local repositories."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from isolated_env import isolated_env

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/shared_sync.py"
PHONE = "+00 00 0000-0000"
SECRET = "token=abcdefghijk"
NOTE = "---\nname: example\ndescription: Example note\nmetadata:\n  type: project\n---\n"
POINTER = "- [Example](note.md) — example"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def read(path):
    return path.read_text(encoding="utf-8")


def fixture(root):
    home = root / "home"
    config = root / "config"
    shared = home / ".config/agent-instructions"
    home.mkdir(parents=True)
    config.mkdir()
    env = isolated_env(root)
    for key in list(env):
        if key.startswith("GIT_") or key == "PRIME_CONTEXT_COMPACTION":
            del env[key]
    env.update(
        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(config / "gitconfig"),
        GIT_CEILING_DIRECTORIES=str(root.parent), GIT_TEMPLATE_DIR=str(config),
    )

    def run(*args, code=0, cwd=root, script=SCRIPT):
        result = subprocess.run(
            [sys.executable, str(script), *map(str, args)], cwd=cwd,
            env=env, capture_output=True, encoding="utf-8", timeout=30,
        )
        assert result.returncode == code, (args, result.returncode, result.stdout, result.stderr)
        return result

    return home, shared, env, run


def legacy_memory(home, path, text):
    name = re.sub(r"[^A-Za-z0-9]", "-", str(path))
    directory = home / ".claude/projects" / name
    with_cwd(directory, path)
    memory = directory / "memory"
    write(memory / "note.md", text)
    write(memory / "MEMORY.md", POINTER + "\n")
    return memory


def with_cwd(directory, *paths):
    write(directory / "session.jsonl", "".join(json.dumps({"cwd": str(path)}) + "\n" for path in paths))


def git_repo(path, env, origin):
    path.mkdir(parents=True, exist_ok=True)
    for args in (["init", "-q"], ["remote", "add", "origin", origin]):
        subprocess.run(["git", "-C", str(path), *args], env=env, check=True, timeout=10)


def check_migrate(root):
    home, shared, env, run = fixture(root)
    claude = home / ".claude"
    write(claude / "CLAUDE.md", "Global rules\n")
    write(claude / "rules/extra.md", "Extra rules\n")
    global_memory = legacy_memory(home, home, NOTE + "Global\n")
    (global_memory.parent / "session.jsonl").unlink()
    originals = [root / "check-outs/one", root / "check-outs/two", root / "unmapped"]
    for path in originals:
        path.mkdir(parents=True)
    for path, origin in zip(originals, ("git@example.com:Group/Repo.git", "https://example.com/group/repo")):
        git_repo(path, env, origin)
    first = legacy_memory(home, originals[0], NOTE + "First\n")
    second = legacy_memory(home, originals[1], NOTE + "Second\n")
    write(second / "MEMORY.md", POINTER.replace("note.md", "./note.md") + "\n")
    unmapped = legacy_memory(home, originals[2], NOTE + "Unmapped\n")
    for ambiguous in (root / "a-b/c", root / "a/b-c"):
        ambiguous.mkdir(parents=True)
    ambiguous_memory = legacy_memory(home, ambiguous, NOTE + "Ambiguous\n")

    run("resolve", code=5)
    run("init")
    assert not shared.exists()
    run("init", "--apply")
    marker = shared / ".prime-context-shared"
    initial_marker = marker.read_bytes()
    assert initial_marker.startswith(b"format=1\ncreated=")
    run("init", "--apply")
    assert marker.read_bytes() == initial_marker
    plan = run("migrate")
    assert "3 mapped, 2 UNMAPPED" in plan.stdout and "Collision" in plan.stdout, plan.stdout
    assert "2 folder(s): no supported Git origin or local ID" in plan.stdout
    assert "migrate --map <folder>=<path>" in plan.stdout and "register --local-id" in plan.stdout
    assert not read(shared / "memory/MEMORY.md") and not (shared / "memory/note.md").exists()
    assert read(claude / "CLAUDE.md") == "Global rules\n"
    assert not list(claude.glob("*.bak-*"))
    assert not list((shared / "projects").glob("*/MEMORY.md"))
    assert not first.is_symlink()

    with_cwd(global_memory.parent, root / "olduser")
    applied = run("migrate", "--apply")
    assert "3 mapped, 2 UNMAPPED" in applied.stdout and "Collision" in applied.stdout
    assert "Global rules" not in applied.stdout and "description: Example note" not in applied.stdout
    assert read(shared / "rules/AGENTS.md") == "Global rules\n"
    assert read(shared / "rules/extra.md") == "Extra rules\n"
    assert read(claude / "CLAUDE.md").splitlines()[0] == "@~/.config/agent-instructions/rules/AGENTS.md"
    [backup] = claude.glob("CLAUDE.md.bak-*")
    assert read(backup) == "Global rules\n"
    project = shared / "projects/example.com__group__repo"
    assert read(project.parent / "INDEX.md").splitlines() == [
        "- example.com/group/repo → example.com__group__repo/MEMORY.md"
    ]
    suffix = hashlib.sha256((NOTE + "Second\n").encode()).hexdigest()[:8]
    assert read(project / "note.md") == NOTE + "First\n"
    assert read(project / ("note-" + suffix + ".md")) == NOTE + "Second\n"
    assert read(project / "MEMORY.md").splitlines() == [
        POINTER, POINTER.replace("note.md", "note-" + suffix + ".md")
    ]
    assert read(shared / "memory/note.md") == NOTE + "Global\n"
    assert read(shared / "memory/MEMORY.md").splitlines() == [POINTER]
    for path in (first, second, global_memory, claude / "rules/extra.md"):
        if path.is_symlink():
            assert list(path.parent.glob(path.name + ".bak-*"))
        else:
            assert "WARNING" in applied.stderr and str(path) in applied.stderr
    assert not unmapped.is_symlink()
    assert not ambiguous_memory.is_symlink()
    assert Path(run("resolve", originals[0]).stdout.strip()) == project / "MEMORY.md"
    run("resolve", originals[2], code=4)
    run("migrate", "--apply")
    assert len(list(project.glob("note*.md"))) == 2
    assert len(list(claude.glob("CLAUDE.md.bak-*"))) == 1
    run("register", originals[2], "--local-id", "example", "--apply")
    local = shared / "projects/local__example/MEMORY.md"
    assert Path(run("resolve", originals[2]).stdout.strip()) == local
    run("migrate", "--apply")
    assert read(local.with_name("note.md")) == NOTE + "Unmapped\n"
    run("sync", "--apply")
    assert "1 UNMAPPED Claude memory folder(s)" in run("doctor", cwd=originals[0]).stdout
    write(claude / "rules/independent.md", "Independent rule\n")
    findings = json.loads(run("doctor", "--json", cwd=originals[0]).stdout)
    assert any(f["severity"] == "MED" and "independent.md" in f["message"] for f in findings)


def check_sync(root):
    home, shared, env, run = fixture(root)
    run("init", "--apply")
    rules = shared / "rules/AGENTS.md"
    write(rules, "Rules " + PHONE + " 1234\n")
    write(shared / "rules/extra.md", "Extra rules (000) 000-0000\n")
    write(home / ".claude/CLAUDE.md", "@~/.config/agent-instructions/rules/AGENTS.md\n")
    sources = shared / "sources.list"
    write(sources, read(sources) + "cmd echo Hook output\ncmd exit 7\n")
    target = Path(env["CODEX_HOME"]) / "AGENTS.md"
    write(target, "Previous entrypoint\n")
    strict = run("sync", "--strict", "--apply", code=2)
    assert "sources.list:6" in strict.stderr and "exit 7" not in strict.stderr
    assert read(target) == "Previous entrypoint\n"
    run("sync")
    assert not (shared / "AGENTS.md").exists() or not (shared / "AGENTS.md").read_bytes()
    synced = run("sync", "--apply")
    assert "WARNING" in synced.stderr and "sources.list:6" in synced.stderr
    previous = read(shared / "AGENTS.md")
    assert PHONE not in previous and "[phone removed]" in previous
    assert "Rules [phone removed] 1234" in previous
    assert "Extra rules [phone removed]" in previous
    assert previous.count("Rules [phone removed]") == 1
    assert previous.index("Extra rules") < previous.index("Hook output") < previous.index("Shared memory")
    assert "metadata.share: claude-only" in previous
    assert read(target) == previous
    [backup] = target.parent.glob("AGENTS.md.bak-*")
    assert read(backup) == "Previous entrypoint\n"
    run("sync", "--check")
    write(rules, "Changed rules\n")
    run("sync", "--check", code=1)
    write(rules, SECRET + "\n")
    rejected = run("sync", "--apply", code=3)
    assert SECRET not in rejected.stderr + rejected.stdout
    assert "rules/AGENTS.md:1" in rejected.stderr.replace("\\", "/")
    assert read(target) == read(shared / "AGENTS.md") == previous
    write(rules, '{"token": "abcdefghijk"}\n')
    run("sync", "--apply", code=3)
    write(rules, "token=${ENV_TOKEN}\npassword=<vault reference>\n")
    custom = root / "custom/AGENTS.md"
    run("sync", "--apply", "--target", custom)
    assert read(target) == previous and "token=${ENV_TOKEN}" in read(custom)

    # The skill-only copy works with its bundled patterns and no plugin wrapper.
    skill = root / "skill"
    shutil.copytree(ROOT / "skills/prime-context", skill)
    run("sync", "--check", "--target", custom, script=skill / "scripts/shared_sync.py")
    note = root / "note.md"
    write(note, NOTE + PHONE + "\n")
    assert "phone" in run("check-note", note, code=1).stdout
    private = NOTE.replace("  type: project\n", "  type: project\n  share: claude-only\n")
    write(note, private + PHONE + "\n")
    run("check-note", note)
    write(note, private + PHONE + "\n" + SECRET + "\n")
    out = run("check-note", note, code=1).stdout
    assert "secret" in out and "phone" not in out and SECRET not in out
    write(note, NOTE.replace("  type: project", "  nested:\n    share: claude-only") + PHONE)
    run("check-note", note, code=1)
    write(note, NOTE.replace("metadata:", "metadata").replace("type: project", "share: claude-only") + PHONE)
    run("check-note", note, code=1)


def check_index_and_doctor(root):
    home, shared, env, run = fixture(root)
    missing = run("doctor", "--json", code=1)
    findings = json.loads(missing.stdout)
    assert any(f["severity"] == "HIGH" and "marker" in f["message"] for f in findings)
    assert not any("target" in f["message"] for f in findings)
    marker = shared / ".prime-context-shared"
    write(marker, "format=2\n")
    run("resolve", code=5)
    run("init", "--apply")
    assert read(marker) == "format=2\n"
    marker.unlink()
    run("init", "--apply")
    index = shared / "memory/MEMORY.md"
    lock = index.with_suffix(".md.lock")
    write(lock, "")
    os.utime(lock, (1, 1))
    run("append-index", index, POINTER)
    assert not read(index) and lock.exists()
    run("append-index", index, POINTER, "--apply")
    run("append-index", index, "- [Another title](./note.md)", "--apply")
    assert read(index).splitlines() == [POINTER]
    assert not lock.exists()
    assert not list(index.parent.glob("*.lock-reap"))
    assert not list(index.parent.glob("MEMORY.md.bak-*"))
    run("append-index", index, "- [Missing](missing.md)", "--apply")
    write(index.with_name("note.md"), NOTE + PHONE + "\n")
    write(index.with_name("legacy.md"), NOTE.replace("metadata:\n", "").replace("  type:", "type:"))
    write(home / ".claude/CLAUDE.md", "@~/.config/agent-instructions/rules/AGENTS.md\n")
    write(home / ".claude/settings.json", '{"env":{"PRIME_CONTEXT_COMPACTION":"1"}}')
    hook = '{"hooks":{"PreCompact":[{"hooks":[{"type":"command","command":"synthetic"}]}]}}'
    write(root / ".claude/settings.json", hook)
    write(root / ".claude/settings.local.json", hook)
    write(shared / "projects/INDEX.md", "- example.com/demo/repo → missing/MEMORY.md\n")
    findings = json.loads(run("doctor", "--json", code=1).stdout)
    high = [f["message"] for f in findings if f["severity"] == "HIGH"]
    assert any(f["severity"] == "LOW" and "Legacy top-level type" in f["message"] for f in findings)
    for expected in ("target", "missing.md", "missing/MEMORY.md", "phone", "PreCompact"):
        assert any(expected in item for item in high), high
    assert all(PHONE not in item for item in high)
    write(root / ".claude/settings.local.json", "{")
    findings = json.loads(run("doctor", "--json", code=1).stdout)
    assert any(f["severity"] == "MED" and "settings.local.json" in f["message"] for f in findings)
    write(root / ".claude/settings.local.json", hook.replace('"synthetic"', "1"))
    findings = json.loads(run("doctor", "--json", code=1).stdout)
    assert any(f["severity"] == "MED" and "settings.local.json" in f["message"] for f in findings)


def check_concurrent_index(root):
    _, shared, env, _ = fixture(root)
    index = shared / "memory/MEMORY.md"
    lock = index.with_suffix(".md.lock")
    write(lock, "")
    os.utime(lock, (1, 1))
    lines = ["- [One](one.md)", "- [Two](two.md)", "- [One again](one.md)"]
    workers = [
        subprocess.Popen(
            [sys.executable, str(SCRIPT), "append-index", str(index), line, "--apply"], cwd=root, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        for line in lines
    ]
    for worker in workers:
        output = worker.communicate(timeout=15)
        assert worker.returncode == 0, output
    result = read(index).splitlines()
    assert len(result) == 2 and any("(one.md)" in line for line in result) and lines[1] in result
    assert not lock.exists()
    assert not list(index.parent.glob("*.lock-reap"))
    assert not list(index.parent.glob("MEMORY.md.bak-*"))


def check_global_override(root):
    home, shared, _, run = fixture(root)
    cwd = root / "custom-global"
    cwd.mkdir()
    original = legacy_memory(home, cwd, NOTE + "Original\n")
    (original.parent / "session.jsonl").unlink()
    try:
        (original.parent.parent / "-global-alias").symlink_to(original.parent, target_is_directory=True)
    except OSError:
        alias_available = False
    else:
        alias_available = True
    write(home / ".claude/CLAUDE.md", "Global rules\n")
    run("init", "--apply")
    assert "1 mapped, 0 UNMAPPED" in run("migrate", f"--global-project={original.parent.name}", "--apply").stdout
    assert read(shared / "memory/note.md") == NOTE + "Original\n"
    if original.is_symlink():
        if os.name == "nt":
            original.rmdir()
        else:
            original.unlink()
    write(original / "note.md", NOTE + "Diverging legacy copy\n")
    run("sync", "--apply")
    findings = json.loads(run("doctor", "--json").stdout)
    divergences = [f for f in findings if f["severity"] == "MED" and "Claude memory diverges" in f["message"]]
    assert len(divergences) == 1 and "custom-global" in divergences[0]["message"]
    if alias_available:
        assert all("-global-alias" not in f["message"] for f in findings)


def check_transcript_mapping(root):
    home, shared, env, run = fixture(root)
    actual = root / "my_app"
    other = root / "my-app"
    git_repo(actual, env, "https://example.com/group/right.git")
    git_repo(other, env, "https://example.com/group/wrong.git")
    source = legacy_memory(home, actual, NOTE + "Authoritative project\n")
    run("init", "--apply")
    write(source.parent / "session.jsonl", "{}\n")
    assert "no matching existing cwd" in run("migrate", "--apply").stdout
    assert not list((shared / "projects").glob("*/MEMORY.md"))
    (source.parent / "session.jsonl").unlink()
    assert "no transcripts" in run("migrate").stdout
    with_cwd(source.parent, actual)
    write(source.parent / "incomplete.jsonl", "{}\n")
    assert "1 mapped, 0 UNMAPPED" in run("migrate").stdout
    (source.parent / "incomplete.jsonl").unlink()
    write(source.parent / "second.jsonl", json.dumps({"cwd": str(other)}) + "\n")
    assert "1 folder(s): several origins or local IDs" in run("migrate").stdout
    (source.parent / "second.jsonl").unlink()
    with_cwd(source.parent, root)
    assert "no matching existing cwd" in run("migrate").stdout
    gone = root / "my.app"
    with_cwd(source.parent, actual)
    write(source.parent / "second.jsonl", json.dumps({"cwd": str(gone)}) + "\n")
    report = run("migrate")
    assert "1 mapped, 0 UNMAPPED" in report.stdout
    assert "1 historical transcript cwd(s)" in report.stderr
    same_origin = root / "my.app"
    git_repo(same_origin, env, "git@example.com:group/right.git")
    nested = actual / "nested"
    nested.mkdir()
    with_cwd(source.parent, actual, nested, other)
    transcript = source.parent / "second.jsonl"
    write(transcript, "{incomplete\n" + json.dumps({"cwd": str(same_origin)}) + "\n{truncated")
    write(source.parent / "aborted.jsonl", "{unfinished")
    assert "2 invalid JSONL line(s) skipped" in run("migrate", "--apply").stderr
    assert read(shared / "projects/example.com__group__right/note.md").endswith("Authoritative project\n")
    assert not (shared / "projects/example.com__group__wrong").exists()
    unknown = home / ".claude/projects/-manual-example/memory"
    write(unknown / "note.md", NOTE + "Manual repository\n")
    with_cwd(unknown.parent, actual)
    local = root / "local-no-origin"
    local.mkdir()
    extra = home / ".claude/projects/-manual-local/memory"
    write(extra / "note.md", NOTE + "Manual local project\n")
    run("register", local, "--local-id", "manual", "--apply")
    findings = json.loads(run("doctor", "--json", code=1).stdout)
    assert any(f["severity"] == "MED" and "2 UNMAPPED" in f["message"]
               and unknown.parent.name in f["message"] and "migrate --map" in f["fix"] for f in findings)
    args = ("--map", f"{unknown.parent.name}={other}", f"--map={extra.parent.name}={local}")
    assert "Map Claude folder" in run("migrate", *args).stdout
    assert not (shared / ".claude-project-maps.json").exists()
    run("migrate", *args, "--apply")
    assert (shared / "projects/example.com__group__wrong/note.md").is_file()
    assert (shared / "projects/local__manual/note.md").is_file()
    assert "UNMAPPED Claude memory folder" not in run("doctor", code=1).stdout
    if unknown.is_symlink():
        saved = (shared / ".claude-project-maps.json").read_bytes()
        assert "existing memory link" in run(
            "migrate", f"--map={unknown.parent.name}={actual}", "--apply", code=2
        ).stderr
        assert (shared / ".claude-project-maps.json").read_bytes() == saved


def check_transcript_history(root):
    home, shared, env, run = fixture(root)
    alice = root / "alice/data_agile"
    olduser = root / "olduser/data_agile"
    git_repo(alice, env, "https://example.com/team/current.git")
    git_repo(olduser, env, "https://example.com/team/old.git")
    memory = legacy_memory(home, alice, NOTE + "Current project\n")
    for name in ("old-one", "old-two"):
        write(memory.parent / (name + ".jsonl"), json.dumps({"cwd": str(olduser)}) + "\n")
    no_transcripts = home / ".claude/projects/-no-transcripts"
    write(no_transcripts / "memory/note.md", NOTE)
    historical_only = home / ".claude/projects/-historical-only"
    write(historical_only / "memory/note.md", NOTE)
    with_cwd(historical_only, olduser)
    run("init", "--apply")

    plan = run("migrate")
    assert "1 mapped, 2 UNMAPPED" in plan.stdout
    assert "1 folder(s): no transcripts" in plan.stdout
    assert "1 folder(s): no matching existing cwd" in plan.stdout
    assert "2 historical transcript cwd(s)" in plan.stderr
    assert not list((shared / "projects").glob("*/MEMORY.md"))
    assert not memory.is_symlink()
    applied = run("migrate", "--apply")
    assert "1 mapped, 2 UNMAPPED" in applied.stdout
    assert read(shared / "projects/example.com__team__current/note.md").endswith("Current project\n")
    assert not (shared / "projects/example.com__team__old").exists()


def check_upgrade(root):
    home, shared, _, run = fixture(root)
    legacy = shared / "AGENTS.md"
    authored = shared / "rules/AGENTS.md"
    claude = home / ".claude/CLAUDE.md"
    old_import = "@~/.config/agent-instructions/AGENTS.md"
    extra = "@~/.config/agent-instructions/extra.md"
    write(legacy, "Existing shared rules\n")
    write(shared / "extra.md", "Additional shared guidance\n")
    write(claude, old_import + "\n\n" + extra + "\n")
    run("init")
    assert legacy.is_file() and not authored.exists()
    write(authored, "Different authored rules\n")
    assert "merge" in run("init", "--apply", code=2).stderr
    assert read(legacy) == "Existing shared rules\n" and read(authored) == "Different authored rules\n"
    authored.unlink()
    run("init", "--apply")
    [backup] = shared.glob("AGENTS.md.bak-*")
    assert read(backup) == read(authored) == "Existing shared rules\n"
    findings = json.loads(run("doctor", "--json", code=1).stdout)
    assert any(f["severity"] == "HIGH" and "generated AGENTS.md" in f["message"] for f in findings)
    assert any(f["severity"] == "HIGH" and "import target" in f["message"] for f in findings)
    assert "Add file source for retained Claude import" in run("migrate", "--apply").stdout
    assert read(authored) == "Existing shared rules\n"
    assert "/rules/AGENTS.md" in read(claude)
    assert extra in read(claude)
    assert read(shared / "sources.list").count("file extra.md") == 1
    run("sync", "--apply")
    assert "Additional shared guidance" in read(legacy)
    write(claude, old_import + "\n\nPrivate Claude additions\n")
    run("migrate", "--apply")
    assert read(authored) == "Existing shared rules\n"
    assert "Private Claude additions" in read(claude)
    run("sync", "--apply")
    write(legacy, "Manual shared entrypoint\n")
    write(authored, "")
    findings = json.loads(run("doctor", "--json", code=1).stdout)
    high = [f["message"] for f in findings if f["severity"] == "HIGH"]
    assert any("authored rules" in item for item in high)
    assert any("GENERATED header" in item for item in high)


def check_patterns_and_sources(root):
    home, shared, _, run = fixture(root)
    run("init", "--apply")
    rules = shared / "rules/AGENTS.md"
    target = shared / "AGENTS.md"
    source_list = shared / "sources.list"
    unaffected = ("Deploy 2026-11-26 10:30", "build 20261126.1530", "Pedido 1234567890",
                  "build 2026 1126 0001", "token=valid-format checks",
                  "Open ports 80 443 8080 on the firewall.", "ports: 22 3306 5432", "sizes 64 128 2048 4096")
    phones = ("+55 11 91234-5678", "(11) 91234-5678", "+1 415 555 0100", "(+55 21 90000-0000)",
              "phone 11900000000", "tel: 1100000000", "telefone 11900000000", "celular 11900000000",
              "whatsapp 11900000000", "zap 11900000000", "+11900000000",
              "celular 21 9 8765-4321", "ligar 21 98765432", "21987654321", "tel 2198765-4321",
              "fone 0000.0000")
    placeholders = ("$VAR", "${VAR}", "<...>", "CHANGE_ME", "xxx", "***")
    write(rules, "\n".join((*unaffected, *phones, *(f"DB_PASSWORD={value}" for value in placeholders))))
    run("migrate", "--apply")
    assert (home / ".claude/CLAUDE.md").is_file()
    run("sync", "--apply")
    safe = target.read_bytes()
    generated = safe.decode()
    assert all(value in generated for value in (*unaffected, *placeholders))
    assert all(phone not in generated for phone in phones)
    assert "phone [phone removed]" in generated
    assert generated.count("[phone removed]") == len(phones)
    secrets = (
        "DB_PASSWORD=hunter2hunter2",
        'DB_PASSWORD="a synthetic passphrase"',
        "export GITHUB_TOKEN=synthetic-example",
        "client_secret: synthetic-example",
        "Authorization: Bearer synthetic-example",
        "https://user:SuperSecret99@example.com",
        "glpat-synthetic-example",
        "AWS_SECRET_ACCESS_KEY=fixture-only-000",
        "secret_key_base: fixture-only-000",
        "PGPASSWORD=fixture-only-000",
        "Bearer eyJfixture.fake_payload.fake_signature",
        "Authorization: Basic Zml4dHVyZTpvbmx5",
        "password: hunter2",
        "passwd: demo",
        "senha: demo",
        "API key: 7f3a9c2e8b1d4f6a",
        "secret key: fixture-only-000",
        "access key: fixture-only-000",
        "senha do banco: demo",
        "senha de teste: demo",
        'private_key: "synthetic key only"',
        "https://hooks.slack.com/services/FIXTURE/TEST/example-only",
        *(prefix + "synthetic_fixture_only" for prefix in
          ("ghs_", "gho_", "ghu_", "ghr_", "sk_live_", "rk_live_", "AIza", "xoxa-", "xoxe-")),
    )
    original = read(rules)
    for secret in secrets:
        write(rules, secret + "\n")
        rejected = run("sync", "--apply", code=3)
        assert secret not in rejected.stdout + rejected.stderr
        assert target.read_bytes() == safe
        assert "secret" in run("check-note", rules, code=1).stdout
    write(rules, original)
    sources = read(source_list)
    for unavailable in ("missing.md", "rules"):
        write(source_list, sources + f"file {unavailable}\n")
        run("sync", "--apply", code=2)
        run("sync", "--check", code=1)
        assert target.read_bytes() == safe
        findings = json.loads(run("doctor", "--json", code=1).stdout)
        assert any(f["severity"] == "HIGH" and unavailable in f["message"] for f in findings)
    write(source_list, sources + "cmd exit 7\n")
    findings = json.loads(run("doctor", "--json").stdout)
    assert any(f["severity"] == "MED" and "command source" in f["message"] for f in findings)
    assert not any(f["severity"] == "HIGH" for f in findings)


def check_tree_and_privacy(root):
    home, shared, env, run = fixture(root)
    repos = [root / "a", root / "b"]
    for repo in repos:
        git_repo(repo, env, "example.com:team/project.git")
    first = legacy_memory(home, repos[0], NOTE + "Original\n")
    first_index = b"# First index\r\n\r\n- [Example](note.md)\r\nFirst prose"
    (first / "MEMORY.md").write_bytes(first_index)
    (first / "empty").mkdir()
    (first / "attachments").mkdir()
    payload = b"\x00\xff"
    (first / "attachments/asset.bin").write_bytes(payload)
    internal_link = first / "attachments/alias.bin"
    try:
        internal_link.symlink_to("asset.bin")
    except OSError:
        has_links = False
    else:
        has_links = True
    run("init", "--apply")
    plan = run("migrate").stdout
    assert f"{1 + int(has_links)} non-.md" in plan and "2 subdir" in plan
    run("migrate", "--apply")
    project = shared / "projects/example.com__team__project"
    assert (project / "MEMORY.md").read_bytes() == first_index
    assert (project / "empty").is_dir() and (project / "attachments/asset.bin").read_bytes() == payload
    if has_links:
        assert (project / "attachments/alias.bin").read_bytes() == payload

    second = legacy_memory(home, repos[1], NOTE + "Different note\n")
    write(second / "MEMORY.md", POINTER + "\n- [Blocked](blocked.md)\n\nSecond prose " + PHONE + "\n")
    write(second / "blocked.md", NOTE + SECRET + "\n")
    write(second / "nested/phone.md", NOTE + PHONE + "\n")
    plan = run("migrate").stdout
    assert "1 BLOCKED" in plan and "1 claude-only" in plan
    assert "blocked.md:7" in plan and SECRET not in plan
    assert not (project / "nested/phone.md").exists()
    run("migrate", "--apply")
    assert "## Migrated from " + second.parent.name in read(project / "MEMORY.md")
    assert read(project / "MEMORY.md").count("Second prose") == 1
    assert PHONE not in read(project / "MEMORY.md")
    assert "blocked.md" not in read(project / "MEMORY.md")
    assert not (project / "blocked.md").exists() and not second.is_symlink()
    assert "  share: claude-only" in read(project / "nested/phone.md")
    previous = set(project.glob("note*.md"))
    second_target = next(path for path in previous if "Different note" in read(path))
    write(second_target, NOTE + "Edited in the shared store\n")
    run("migrate", "--apply")
    assert "Edited in the shared store" in read(second_target)
    write(second / "note.md", NOTE + "Updated note\n")
    run("migrate", "--apply")
    assert set(project.glob("note*.md")) == previous
    assert any("Updated note" in read(path) for path in previous)
    assert read(project / "MEMORY.md").count("Second prose") == 1


def check_claude_home_and_rules(root):
    home, shared, env, run = fixture(root)
    configured = root / "custom-claude"
    selected = home / "explicit-claude"
    env["CLAUDE_CONFIG_DIR"] = str(configured)
    run("init", "--apply")
    write(shared / "rules/example.md", "Keep shared rule\n")
    write(configured / "CLAUDE.md", "Authored rules\n@RTK.md\n@./x.md\n")
    write(configured / "rules/example.md", "Legacy rule\n")
    write(configured / "settings.json", "{")
    write(configured / "RTK.md", "First import\n")
    write(configured / "x.md", "Second import\n")
    plan = run("migrate", code=2)
    assert plan.stdout.count("Rewrite import") == 2 and "merge rule by hand" in plan.stderr
    run("migrate", "--apply", code=2)
    assert f"@{(configured / 'RTK.md').as_posix()}" in read(shared / "rules/AGENTS.md")
    assert f"@{(configured / 'x.md').as_posix()}" in read(shared / "rules/AGENTS.md")
    assert read(shared / "rules/example.md") == "Keep shared rule\n"
    original = configured / "rules/example.md"
    assert read(original) == "Legacy rule\n" and not original.is_symlink()
    assert not (shared / "rules/example-claude.md").exists()
    run("sync", "--apply", code=2)
    write(original, "Keep shared rule\n")
    write(shared / "rules/new.md", "New shared rule\n")
    run("sync", "--apply")
    new_rule = configured / "rules/new.md"
    assert new_rule.is_symlink() or "rules/new.md" in read(configured / "CLAUDE.md")
    findings = json.loads(run("doctor", "--json").stdout)
    assert any(f["severity"] == "MED" and str(configured) in f["message"] for f in findings)
    write(selected / "CLAUDE.md", "Explicit rules\n@./extra.md\n")
    write(selected / "extra.md", "Under home\n")
    run("doctor", "--claude-home", selected, code=1)
    run("migrate", "--claude-home", selected, "--apply")
    assert "@~/explicit-claude/extra.md" in read(shared / "rules/AGENTS.md")
    run("sync", "--apply")
    assert run("doctor", "--claude-home", selected).stdout == "doctor: clean\n"


def check_local_origin(root):
    _, shared, env, run = fixture(root)
    repo = root / "repo"
    git_repo(repo, env, "./not-a-parseable-origin")
    run("init", "--apply")
    run("register", repo, "--local-id", "standalone", "--apply")
    assert Path(run("resolve", repo).stdout.strip()) == shared / "projects/local__standalone/MEMORY.md"
    valid = root / "valid-origin"
    git_repo(valid, env, "git://example.com/team/repo.git")
    assert "cannot override a valid Git origin" in run("register", valid, "--local-id", "wrong", "--apply", code=2).stderr
    run("register", valid, "--apply")
    assert Path(run("resolve", valid).stdout.strip()) == shared / "projects/example.com__team__repo/MEMORY.md"


def check_lost_lock(root, api):
    _, shared, _, _ = fixture(root)
    index = shared / "memory/MEMORY.md"
    lock = index.with_suffix(".md.lock")
    write(index, POINTER + "\n")
    atomic_write = api["atomic_write"]

    def replace_lock_before_commit(*args, verify, **kwargs):
        def lose_lock(action=None):
            owner = read(lock)
            assert len(owner) == 32 and owner != "replacement"
            write(lock, "replacement")
            verify(action)

        return atomic_write(*args, verify=lose_lock, **kwargs)

    runtime = api["append_index"].__globals__
    runtime["atomic_write"] = replace_lock_before_commit
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as warnings:
        try:
            api["append_index"](index, "- [Another](another.md)", True)
        except ValueError as error:
            assert "lost index lock ownership" in str(error)
        else:
            raise AssertionError("index write proceeded after losing the lock")
        finally:
            runtime["atomic_write"] = atomic_write
    assert "lock changed before release" in warnings.getvalue()
    assert read(index) == POINTER + "\n"
    assert read(lock) == "replacement"


def check_quarantine_and_hook(root):
    _, shared, env, run = fixture(root)
    run("init", "--apply")
    write(shared / "rules/AGENTS.md", "Shared rules\n")
    run("sync", "--apply")
    note = shared / "memory/fresh.md"
    explicit = shared / "projects/example.com__demo/explicit.md"
    originally = "Unscanned note\n" + SECRET + "\n"
    write(note, originally)
    write(explicit, NOTE.replace("  type: project", "    # fixture comment\n    type: project\n    share: all") + PHONE + "\n")
    checked = run("sync", "--check", code=1)
    assert "fresh.md:2: secret" in checked.stderr and SECRET not in checked.stderr
    run("sync", "--apply", code=1)
    dry = run("quarantine")
    assert "Would quarantine 2 note(s)" in dry.stdout
    assert read(note) == originally and not list(note.parent.glob("fresh.md.bak-*"))
    hook = ROOT / "hooks/session_start.py"
    result = subprocess.run(
        [sys.executable, str(hook)], cwd=root, env=env, capture_output=True, encoding="utf-8", timeout=10,
    )
    assert result.returncode == 0 and result.stdout == "prime-context: quarantined 2 shared memory note(s)\n"
    assert not list(note.parent.glob("*.bak-*"))
    [backup] = (shared / ".state/backups").rglob("fresh.md.*.bak-*")
    assert read(backup) == originally
    assert "share: claude-only" in read(note)
    assert read(explicit).count("share:") == 1
    assert "\n    share: claude-only\n" in read(explicit)
    run("sync", "--check")
    write(shared / ".prime-context-shared", "format=invalid\n")
    result = subprocess.run(
        [sys.executable, str(hook)], cwd=root, env=env, capture_output=True, encoding="utf-8", timeout=10,
    )
    assert result.returncode == 0 and result.stdout.count("WARNING") == 1
    assert result.stdout == "prime-context WARNING: unsupported shared memory format\n"


def check_incremental_hook(root, api):
    _, shared, env, run = fixture(root)
    run("init", "--apply")
    notes = shared / "memory"
    for number in range(800):
        write(notes / f"note-{number:04d}.md", NOTE + "Fixture only.\n")
    temporary = notes / ".prime-context-fixture"
    write(temporary, SECRET + "\n")
    hook = ROOT / "hooks/session_start.py"

    def start_hook():
        start = time.monotonic()
        result = subprocess.run(
            [sys.executable, str(hook)], cwd=root, env=env, capture_output=True, encoding="utf-8", timeout=10,
        )
        assert result.returncode == 0 and "did not finish" not in result.stdout
        return result.stdout, time.monotonic() - start

    assert start_hook()[0] == ""
    cache = shared / ".state/scan-cache.json"
    assert len(json.loads(read(cache))["entries"]) >= 800
    output, elapsed = start_hook()
    assert output == ""
    if sys.platform.startswith("linux"):
        assert elapsed < 0.5, elapsed
    print(f"Cached SessionStart with 800 notes: {elapsed:.3f}s")
    changed = notes / "note-0799.md"
    write(changed, NOTE + PHONE + "\n")
    assert start_hook()[0] == "prime-context: quarantined 1 shared memory note(s)\n"
    assert "share: claude-only" in read(changed) and read(temporary) == SECRET + "\n"

    preserved_mtime = notes / "note-0798.md"
    write(preserved_mtime, NOTE + "x" * len(SECRET) + "\n")
    assert start_hook()[0] == ""
    previous = preserved_mtime.stat()
    replacement = notes / ".prime-context-replacement"
    write(replacement, NOTE + SECRET + "\n")
    os.utime(replacement, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    replacement.replace(preserved_mtime)
    assert start_hook()[0] == "prime-context: quarantined 1 shared memory note(s)\n"

    for name in ("note-0000.md", "note-0001.md"):
        write(notes / name, NOTE + PHONE + "\n")
    runtime = api["quarantine"].__globals__
    original = runtime["quarantine_note"]

    def delay_after_quarantine(*args):
        result = original(*args)
        time.sleep(0.30)
        return result

    with patch.dict(runtime, {"quarantine_note": delay_after_quarantine}), redirect_stdout(StringIO()) as partial:
        assert api["quarantine"](shared, True, budget=0.20) == 0
    assert "Quarantined 1 note(s)" in partial.getvalue() and "Quarantine paused" in partial.getvalue()
    assert "share: claude-only" in read(notes / "note-0000.md")
    assert "share: claude-only" not in read(notes / "note-0001.md")
    assert start_hook()[0] == "prime-context: quarantined 1 shared memory note(s)\n"
    write(notes / "a-large.txt", "fixture only\n" * 24000)
    write(changed, NOTE + PHONE + "\n")
    output, _ = start_hook()
    assert "quarantined 1 shared memory note(s)" in output and output.count("WARNING") == 1
    assert "share: claude-only" in read(changed)
    assert json.loads(read(cache))["entries"]["memory/a-large.txt"][-1] == "deferred"
    run("quarantine", "--apply")
    assert json.loads(read(cache))["entries"]["memory/a-large.txt"][-1] == []


def check_transcript_fast_path(root, api):
    home, shared, env, run = fixture(root)
    repo = root / "repo"
    git_repo(repo, env, "https://example.com/project.git")
    legacy = legacy_memory(home, repo, NOTE + "Fixture only\n")
    path = legacy.parent / "session.jsonl"
    with path.open("ab") as stream:
        for _ in range(8192):
            stream.write(b'{"message":"' + b"x" * 2048 + b'"}\n')
    calls = []
    original_loads = json.loads

    def counted_load(raw):
        calls.append(len(raw))
        return original_loads(raw)

    with patch.object(json, "loads", side_effect=counted_load):
        assert api["transcript_cwds"](legacy.parent)[0] == {repo.resolve()}
    assert len(calls) == 1 and path.stat().st_size > 16_000_000
    write(home / ".claude/CLAUDE.md", "Shared rule\n")
    run("init", "--apply")
    run("migrate", "--apply")
    run("sync", "--apply")
    with patch.dict(os.environ, env, clear=True), patch.dict(
        api["doctor"].__globals__, {"transcript_cwds": lambda path: (_ for _ in ()).throw(AssertionError(path))}
    ), redirect_stdout(StringIO()) as findings:
        assert api["doctor"](shared, home / ".claude", False) == 0
    assert "UNMAPPED" not in findings.getvalue()


def check_import_expansion(root):
    home, shared, _, run = fixture(root)
    run("init", "--apply")
    main = shared / "rules/AGENTS.md"
    imported = shared / "extra/guide.md"
    secret_file = home / "nested rules.md"
    write(main, "Top @../extra/guide.md afterward.\n`@missing.md` stays literal.\n> ~~~\n> @quote.md\n> ~~~\n")
    write(imported, "Middle\n@~/nested\\ rules.md\n@../rules/AGENTS.md\n")
    write(secret_file, "Nested " + PHONE + "\n")
    run("sync", "--apply")
    generated = read(shared / "AGENTS.md")
    assert generated.count("Top ") == 1 and "Middle" in generated and "afterward." in generated
    assert "Nested [phone removed]" in generated and "`@missing.md`" in generated and "> @quote.md" in generated
    assert "skill's resolve mode" in generated and "shared_sync.py" not in generated
    write(secret_file, SECRET + "\n")
    assert "nested rules.md:1: secret" in run("sync", "--apply", code=3).stderr
    assert read(shared / "AGENTS.md") == generated
    secret_file.unlink()
    assert "cannot read imported file" in run("sync", "--apply", code=2).stderr
    assert read(shared / "AGENTS.md") == generated
    findings = json.loads(run("doctor", "--json", code=1).stdout)
    assert any(f["severity"] == "HIGH" and "cannot read imported file" in f["message"] for f in findings)
    for number in range(1, 7):
        body = f"Depth {number}\n"
        if number < 6:
            body += f"@level-{number + 1}.md\n"
        write(shared / f"extra/level-{number}.md", body)
    write(main, "@../extra/level-1.md\n")
    run("sync", "--apply")
    assert "Depth 5" in read(shared / "AGENTS.md") and "Depth 6" not in read(shared / "AGENTS.md")


def check_migration_rescan(root, api):
    home, shared, _, _ = fixture(root)
    source = home / "memory"
    write(source / "note.md", NOTE + "Original\n")
    index = shared / "memory/MEMORY.md"
    migration = api["Migration"](shared, True)
    original = migration.memory_index
    changed = False

    def write_during_copy(*args):
        nonlocal changed
        original(*args)
        if not changed:
            changed = True
            write(source / "note.md", NOTE + "Changed after the first scan\n")
            write(source / "late.md", NOTE + "Added after the first scan\n")

    migration.memory_index = write_during_copy
    runtime = api["Migration"].memory.__globals__
    actual_link = runtime["migrated_link"]
    attempted = False

    def write_before_link(original, target, directory, check):
        nonlocal attempted
        if not attempted:
            attempted = True
            write(original / "just-before-link.md", NOTE + "Added before directory rename\n")
        return actual_link(original, target, directory, check)

    with patch.dict(runtime, {"migrated_link": write_before_link}), redirect_stdout(StringIO()) as plan, redirect_stderr(StringIO()):
        migration.memory(source, index)
    assert "Rescan changed Claude memory" in plan.getvalue()
    assert read(index.with_name("note.md")).endswith("Changed after the first scan\n")
    assert read(index.with_name("late.md")).endswith("Added after the first scan\n")
    if attempted:
        destination = index.parent if source.is_symlink() else source
        assert read(destination / "just-before-link.md").endswith("Added before directory rename\n")
    assert not list(index.parent.glob("*.bak-*"))
    assert list((shared / ".state/backups").rglob("note.md.*.bak-*"))


def check_url_matching_cost(api):
    url = api["secret_on"].__globals__["SECRET_URL"]
    assert url.pattern.startswith("://")
    assert not url.search(("example." * 10000) + "://example.com/path")
    assert url.search("https://demo:fixture-only-000@example.com")


def check_text_assets(root):
    home, shared, _, run = fixture(root)
    legacy = legacy_memory(home, home, NOTE + "Global memory\n")
    write(home / ".claude/CLAUDE.md", "Shared rules\n")
    write(legacy / "contacts.txt", "phone 11900000000\n")
    write(legacy / "team.json", '{"client_secret": "fixture-only-000"}\n')
    binary = legacy / "binary.bin"
    binary.write_bytes(b"\0token=fixture-only-000")
    run("init", "--apply")
    plan = run("migrate").stdout
    assert "contacts.txt:1 (phone)" in plan and "team.json:1 (secret)" in plan
    run("migrate", "--apply")
    assert not legacy.is_symlink() and (shared / "memory/binary.bin").read_bytes() == binary.read_bytes()
    assert not (shared / "memory/contacts.txt").exists() and not (shared / "memory/team.json").exists()
    run("sync", "--apply")
    write(shared / "memory/team.json", '{"client_secret": "fixture-only-000"}\n')
    findings = json.loads(run("doctor", "--json", code=1).stdout)
    assert any(f["severity"] == "HIGH" and "team.json:1: secret" in f["message"] for f in findings)
    assert not any("binary.bin" in f["message"] for f in findings)
    run("sync", "--check", code=1)


def check_import_grammar_and_symlink(root, api):
    home, shared, env, run = fixture(root)
    claude = home / ".claude"
    main = claude / "CLAUDE.md"
    original_dir = home / "rules-location"
    target = original_dir / "original.md"
    original_dir.mkdir()
    main.parent.mkdir()
    try:
        main.symlink_to(target)
    except OSError:
        target = main
        original_dir = main.parent
    sample = (
        "Read @RTK.md before continuing.\n"
        "Use @./spaced\\ name.md after setup.\n"
        "@JV prefers short answers.\n"
        "Code `@RTK.md` stays literal.\n"
        "Code `begins\n@RTK.md stays literal` too.\n"
        "~~~markdown\n@RTK.md\n~~~\n"
        "\n    @RTK.md\n"
    )
    write(original_dir / "RTK.md", "First imported rule\n")
    write(original_dir / "spaced name.md", "Second imported rule\n")
    write(target, sample)
    run("init", "--apply")
    run("migrate", "--apply")
    prefix = original_dir.relative_to(home).as_posix()
    rewritten = read(shared / "rules/AGENTS.md")
    assert rewritten == sample.replace(
        "Read @RTK.md", f"Read @~/{prefix}/RTK.md"
    ).replace("Use @./spaced\\ name.md", f"Use @~/{prefix}/spaced\\ name.md")
    assert target == main or (main.is_symlink() and main.resolve() == target)
    [backup] = target.parent.glob(target.name + ".bak-*")
    assert read(backup) == sample

    # Force a no-symlink environment on every platform, including Linux CI.
    fallback = shared / "rules/fallback.md"
    write(fallback, "Additional shared rule\n")
    with patch.dict(os.environ, env, clear=True), patch.object(Path, "symlink_to", side_effect=OSError):
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as warnings:
            assert not api["deliver_rules"](shared, claude, True)
        assert "using an import" in warnings.getvalue()
    assert read(main).count("@~/.config/agent-instructions/rules/fallback.md") == 1
    assert target == main or main.is_symlink()
    if main.is_symlink():
        main.unlink()
        authored = shared / "rules/AGENTS.md"
        main.symlink_to(authored)
        prior = authored.read_bytes()
        run("migrate", "--apply")
        assert main.is_symlink() and authored.read_bytes() == prior
        main.unlink()
        main.symlink_to(shared / "AGENTS.md")
        run("migrate", "--apply")
        assert main.is_symlink() and main.resolve() == authored and authored.read_bytes() == prior


def test_shared_sync():
    api = runpy.run_path(str(ROOT / "skills/prime-context/scripts/shared_sync.py"))
    origin_key = api["origin_key"]
    for origin in (
        "git@EXAMPLE.COM:GROUP/Sub/REPO.git",
        "ssh://git@EXAMPLE.COM:2222/group/sub/REPO.git/",
        "https://demo:fake@EXAMPLE.COM:8443/Group/Sub/Repo.GIT",
    ):
        assert origin_key(origin) == "example.com/group/sub/repo"
    for origin, expected in (
        ("server.example:repo.git", "server.example/repo"),
        ("http://example.com/Repo.git", "example.com/repo"),
        ("corp@example.com:Owner/Repo.git", "example.com/owner/repo"),
    ):
        assert origin_key(origin) == expected
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
        root = Path(temporary).resolve()
        check_migrate(root / "migrate")
        check_sync(root / "sync")
        check_index_and_doctor(root / "doctor")
        check_concurrent_index(root / "index")
        check_global_override(root / "global")
        check_transcript_mapping(root / "transcripts")
        check_transcript_history(root / "transcript-history")
        check_upgrade(root / "upgrade")
        check_patterns_and_sources(root / "patterns")
        check_tree_and_privacy(root / "tree")
        check_claude_home_and_rules(root / "claude-home")
        check_local_origin(root / "local-origin")
        check_lost_lock(root / "lost-lock", api)
        check_quarantine_and_hook(root / "quarantine")
        check_incremental_hook(root / "incremental", api)
        check_transcript_fast_path(root / "transcript-fast", api)
        check_import_expansion(root / "expanded-imports")
        check_migration_rescan(root / "rescan", api)
        check_url_matching_cost(api)
        check_text_assets(root / "text-assets")
        check_import_grammar_and_symlink(root / "imports", api)


if __name__ == "__main__":
    test_shared_sync()
    print("test_shared_sync: OK")
