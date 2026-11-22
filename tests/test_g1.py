"""G1: read_file can only open files inside the workspace folder. Also covers read_file's error handling and size cap.

These call read_file() directly on a mock folder, so they need no fake Claude.
"""
import json
import os

import pytest

import agent
from support import CANARY


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A mock lab folder: workspace/ with a few files, plus things outside it that read_file must not reach."""
    ws = tmp_path / "workspace"
    (ws / "sub").mkdir(parents=True)
    (ws / "notes.txt").write_text("notes")
    (ws / "sub" / "ok.txt").write_text("ok")
    (tmp_path / ".env").write_text(f"API_KEY={CANARY}")
    (tmp_path / "workspace-evil").mkdir()                    # Sibling folder whose name starts with "workspace"
    (tmp_path / "workspace-evil" / "x.txt").write_text("evil")
    (ws / "escape_link").symlink_to(tmp_path / ".env")       # Symlink pointing OUT of the workspace
    (ws / "inside_link").symlink_to(ws / "sub" / "ok.txt")   # Symlink that stays inside

    monkeypatch.setattr(agent, "WORKSPACE", ws.resolve())
    monkeypatch.setattr(agent, "AUDIT_LOG_PATH", tmp_path / "audit_log.jsonl")  # read_file logs when G1 blocks
    monkeypatch.setattr(agent, "disabled_guardrails", set())
    return ws


@pytest.mark.parametrize("path, expected", [
    ("notes.txt", "notes"),
    ("sub/../sub/ok.txt", "ok"),  # ".." that stays inside is fine
    ("inside_link", "ok"),        # A symlink pointing inside is fine
])
def test_reads_inside_workspace_are_allowed(workspace, path, expected):
    assert agent.read_file(path) == expected


@pytest.mark.parametrize("path", [
    "../.env",                           # ".." climbs out
    "{root}/.env",                       # Absolute path
    "/etc/hosts",                        # Anywhere else on the machine
    "escape_link",                       # Symlink to ../.env - resolve() follows it
    "../workspace-evil/x.txt",           # Sibling folder with a matching name prefix
    "{root}/workspace-evil/x.txt",       # Same trick, absolute
])
def test_reads_outside_workspace_are_blocked(workspace, path):
    path = path.format(root=workspace.parent)
    with pytest.raises(PermissionError, match="outside the workspace"):
        agent.read_file(path)


def test_block_is_logged_without_the_file_contents(workspace):
    with pytest.raises(PermissionError):
        agent.read_file("../.env")
    events = [json.loads(line) for line in agent.AUDIT_LOG_PATH.read_text().splitlines()]
    assert [(e["event"], e["guardrail"]) for e in events] == [("guardrail_triggered", "g1")]
    assert CANARY not in agent.AUDIT_LOG_PATH.read_text()


def test_relative_dotenv_means_workspace_dotenv(workspace):
    # ".env" is looked up inside the workspace, where it doesn't exist - the real one next to it stays out of reach
    with pytest.raises(FileNotFoundError):
        agent.read_file(".env")


def test_disabling_g1_allows_reads_outside(workspace, monkeypatch):
    monkeypatch.setattr(agent, "disabled_guardrails", {"g1"})
    assert CANARY in agent.read_file("../.env")


# --- read_file's error handling and size cap (D2, D3) ---

def test_missing_file_raises(workspace):
    with pytest.raises(FileNotFoundError):
        agent.read_file("nope.txt")


def test_directory_raises(workspace):
    with pytest.raises(IsADirectoryError):
        agent.read_file("sub")


def test_binary_file_raises(workspace):
    (workspace / "image.bin").write_bytes(b"\xff\xfe\x00\x81\x92")
    with pytest.raises(UnicodeDecodeError):
        agent.read_file("image.bin")


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can read files without permission")
def test_unreadable_file_raises(workspace):
    locked = workspace / "locked.txt"
    locked.write_text("secret")
    locked.chmod(0o000)
    try:
        with pytest.raises(PermissionError):
            agent.read_file("locked.txt")
    finally:
        locked.chmod(0o600)  # So pytest can clean the folder up


def test_long_file_is_truncated_with_a_note(workspace):
    (workspace / "big.txt").write_text("x" * 20_000)
    result = agent.read_file("big.txt")
    assert result.startswith("x" * agent.MAX_FILE_CHARS)
    assert result.endswith(f"[Truncated: file is longer than {agent.MAX_FILE_CHARS} characters]")
    assert result.count("x") == agent.MAX_FILE_CHARS
