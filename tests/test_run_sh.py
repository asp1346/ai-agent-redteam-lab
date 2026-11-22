"""run.sh: reads the key from Keychain, then starts the agent with any flags passed on.

A fake `security` command is put first on PATH, so these tests never touch the real Keychain.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FAKE_KEY = "dummy-key-from-fake-keychain"


@pytest.fixture
def launch(project, tmp_path_factory):
    """Gives each test a function: launch(*flags, keychain_has_key=True) -> CompletedProcess."""
    shutil.copy(REPO / "run.sh", project / "run.sh")
    (project / "run.sh").chmod(0o755)
    (project / "venv").symlink_to(sys.prefix)  # run.sh runs venv/bin/python next to itself
    fake_bin = tmp_path_factory.mktemp("fake_bin")

    def launch(*flags, keychain_has_key=True):
        security = fake_bin / "security"
        if keychain_has_key:
            security.write_text(f"#!/bin/sh\necho {FAKE_KEY}\n")
        else:
            security.write_text("#!/bin/sh\necho 'The specified item could not be found.' >&2\nexit 44\n")
        security.chmod(0o755)
        env = {"PATH": f"{fake_bin}:/usr/bin:/bin", "USER": os.environ.get("USER", "tester"), "HOME": str(project)}
        # Started from "/" with no venv active and no API key set, to show run.sh doesn't depend on either
        return subprocess.run([str(project / "run.sh"), *flags], input="exit\n", capture_output=True,
                              text=True, env=env, cwd="/", timeout=60)

    return launch


def test_starts_the_agent_and_passes_flags_on(launch, project):
    result = launch("--disable", "g1")
    assert result.returncode == 0, result.stderr
    assert "GUARDRAILS DISABLED" in result.stdout and "G1:" in result.stdout
    log = (project / "audit_log.jsonl").read_text()
    assert json.loads(log.splitlines()[0])["guardrails_disabled"] == ["g1"]
    assert FAKE_KEY not in log


def test_help_is_passed_on(launch):
    result = launch("--help")
    assert result.returncode == 0
    assert "usage: agent.py" in result.stdout


def test_missing_keychain_entry_stops_before_the_agent_starts(launch, project):
    result = launch(keychain_has_key=False)
    assert result.returncode == 1
    assert "Couldn't read the API key from Keychain" in result.stderr
    assert not (project / "audit_log.jsonl").exists()
