"""Guardrail switches (--disable), the startup banner, session_start logging, and API key handling at startup."""
import pytest

import agent
from support import answers, rejects_key

ALL = sorted(agent.GUARDRAILS)


def test_everything_is_on_by_default(run_agent):
    r = run_agent(answers("hi"))
    assert "All guardrails enabled." in r.output
    assert "DISABLED" not in r.output
    assert r.session_start["guardrails_enabled"] == ALL
    assert r.session_start["guardrails_disabled"] == []


@pytest.mark.parametrize("name", ALL)
def test_disabling_one_guardrail_names_only_that_one(run_agent, name):
    r = run_agent(answers("hi"), flags=("--disable", name))
    assert "GUARDRAILS DISABLED" in r.output
    assert f"{name.upper()}:" in r.output
    assert not any(f"{other.upper()}:" in r.output for other in ALL if other != name)
    assert r.session_start["guardrails_disabled"] == [name]
    assert r.session_start["guardrails_enabled"] == [g for g in ALL if g != name]


def test_disable_all(run_agent):
    r = run_agent(answers("hi"), flags=("--disable", "all"))
    assert r.session_start["guardrails_disabled"] == ALL
    assert r.session_start["guardrails_enabled"] == []


def test_flag_ignores_case_and_spaces(run_agent):
    r = run_agent(answers("hi"), flags=("--disable", "G1, g2"))
    assert r.session_start["guardrails_disabled"] == ["g1", "g2"]


def test_unknown_guardrail_stops_the_program(run_agent):
    r = run_agent(answers("hi"), flags=("--disable", "g7"))
    assert r.exit_code == 2
    assert "unknown guardrail(s): g7" in r.errors
    assert r.raw_log == ""  # The agent never started


def test_typo_in_the_code_counts_as_on():
    assert agent.guardrail_on("g7") is True


def test_help_lists_every_guardrail(run_agent):
    r = run_agent(answers("hi"), flags=("--help",))
    assert r.exit_code == 0
    assert all(f"{name} =" in r.output for name in ALL)


def test_session_start_is_logged_first_with_the_model(run_agent):
    r = run_agent(answers("hi"))
    assert r.log[0]["event"] == "session_start"
    assert r.session_start["model"] == agent.MODEL


# --- API key handling at startup ---

@pytest.mark.parametrize("key", [None, ""])
def test_missing_or_empty_key_exits_cleanly(run_agent, monkeypatch, key):
    if key is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY")
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    r = run_agent(answers("hi"))
    assert r.exit_code == 1
    assert "No API key found" in r.output
    assert [e["error_type"] for e in r.events("api_error")] == ["MissingAPIKey"]
    assert r.tool_choices == []  # Claude was never called


def test_rejected_key_exits_and_is_logged(run_agent):
    r = run_agent(rejects_key)
    assert r.exit_code == 1
    assert "Anthropic rejected the API key" in r.output
    assert [e["error_type"] for e in r.events("api_error")] == ["AuthenticationError"]
