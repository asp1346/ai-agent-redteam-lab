"""Shared test setup. pytest loads this file automatically and makes its fixtures available to every test.

Full-agent tests run a *copy* of agent.py inside a throwaway mock project (pytest's tmp_path), with Claude replaced
by FakeClaude. The mock project's only secret is a fake canary, so tests that switch G1 off can never reach a real
file, and the real audit_log.jsonl and outbox.jsonl are never touched. No API calls are made.
"""
import runpy
import shutil
import sys
from pathlib import Path

import anthropic
import pytest

from support import CANARY, FakeClaude, RunResult, read_if_exists

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def project(tmp_path):
    """A throwaway copy of the lab: agent.py, workspace/notes.txt, and a canary secret OUTSIDE the workspace."""
    shutil.copy(REPO / "agent.py", tmp_path / "agent.py")
    (tmp_path / "workspace").mkdir()
    (tmp_path / "workspace" / "notes.txt").write_text("Meeting notes\n")
    (tmp_path / "secrets.txt").write_text(f"API_KEY={CANARY}\n")
    return tmp_path


@pytest.fixture
def run_agent(project, monkeypatch, capsys):
    """Gives each test a function: run(script, flags=(), user_messages=("go",)) -> RunResult.

    It runs the mock project's agent.py exactly like `python agent.py <flags>` would, argument parsing included.
    It types each user message and then "exit", and collects what the agent printed, logged and "sent".
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key-for-tests")

    def run(script, flags=(), user_messages=("go",)):
        for name in ("audit_log.jsonl", "outbox.jsonl"):
            (project / name).unlink(missing_ok=True)

        fake = FakeClaude(script)
        monkeypatch.setattr(anthropic, "Anthropic", lambda: fake)
        typed = iter([*user_messages, "exit"])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(typed))
        monkeypatch.setattr(sys, "argv", ["agent.py", *flags])

        exit_code, agent_globals = 0, {}
        try:
            # run_name="__main__" makes the `if __name__ == "__main__":` block run, like launching it from a terminal
            agent_globals = runpy.run_path(str(project / "agent.py"), run_name="__main__")
        except SystemExit as e:
            exit_code = e.code

        printed = capsys.readouterr()
        return RunResult(
            output=printed.out,
            errors=printed.err,
            exit_code=exit_code,
            tool_choices=fake.tool_choices,
            messages=agent_globals.get("messages", []),
            raw_log=read_if_exists(project / "audit_log.jsonl"),
            raw_outbox=read_if_exists(project / "outbox.jsonl"),
        )

    return run
