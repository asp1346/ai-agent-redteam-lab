"""G2: at most MAX_TOOL_CALLS_PER_TURN tool calls per user message, without breaking the conversation history."""
import agent
from support import asks_for, reply, runaway, tool_history_is_valid, use

CAP = agent.MAX_TOOL_CALLS_PER_TURN


def test_runaway_loop_is_stopped_at_the_cap(run_agent):
    r = run_agent(runaway())
    assert r.tools_run == CAP
    assert r.tool_choices == ["auto"] * CAP + ["none"]  # The request after the cap forbids tools
    assert "Forced final answer." in r.output
    assert "[Guardrail] Tool call limit" in r.output
    assert r.guardrails_triggered == ["g2"]
    assert tool_history_is_valid(r.messages)


def test_calls_over_the_cap_in_one_response_get_error_results(run_agent):
    # 9 calls, then one response asking for 3 more when only 1 slot is left
    def script(n, request):
        return asks_for(*[use("get_time") for _ in range(9 if n == 1 else 3)])

    r = run_agent(script)
    blocked = [e for e in r.events("tool_call") if e["is_error"]]
    assert r.tools_run == CAP
    assert len(blocked) == 2
    assert all("Tool call limit" in e["result_preview"] for e in blocked)
    assert r.tool_choices == ["auto", "auto", "none"]
    assert tool_history_is_valid(r.messages)  # The 2 blocked calls still got matching tool_results


def test_counter_resets_for_each_user_message(run_agent):
    # Two user messages, each using 2 tools - neither should get near the cap
    def script(n, request):
        return asks_for(use("get_time"), use("get_time")) if n in (1, 3) else reply("Done.")

    r = run_agent(script, user_messages=("first", "second"))
    assert r.tools_run == 4
    assert "none" not in r.tool_choices
    assert "g2" not in r.guardrails_triggered


def test_disabling_g2_removes_the_cap(run_agent):
    r = run_agent(runaway(give_up_after=15), flags=("--disable", "g2"))
    assert r.tools_run == 15
    assert "none" not in r.tool_choices
    assert "Gave up on my own." in r.output
