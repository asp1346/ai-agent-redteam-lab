"""The tool loop itself: error handling (D2), audit log events (D5) and the fake send_message channel (D6)."""
from support import asks_for, reply, tool_call, tool_history_is_valid, use


def then_done(first_response):
    """Script: Claude sends `first_response`, then answers."""
    return lambda n, request: first_response if n == 1 else reply("Done.")


def test_unknown_tool_gets_an_error_result(run_agent):
    r = run_agent(then_done(tool_call("delete_everything")))
    [event] = r.events("tool_call")
    assert event["is_error"] is True
    assert "Unknown tool 'delete_everything'" in event["result_preview"]
    assert "Done." in r.output  # The agent carried on


def test_tool_exception_becomes_an_error_result(run_agent):
    r = run_agent(then_done(tool_call("read_file", path="nope.txt")))
    [event] = r.events("tool_call")
    assert event["is_error"] is True
    assert "FileNotFoundError" in event["result_preview"]
    assert r.exit_code == 0


def test_missing_tool_input_becomes_an_error_result(run_agent):
    r = run_agent(then_done(tool_call("get_weather")))  # No "location"
    [event] = r.events("tool_call")
    assert event["is_error"] is True
    assert "KeyError" in event["result_preview"]


def test_one_failure_doesnt_mark_other_calls_as_errors(run_agent):
    r = run_agent(then_done(asks_for(use("read_file", path="nope.txt"), use("get_time"))))
    assert [e["is_error"] for e in r.events("tool_call")] == [True, False]
    assert tool_history_is_valid(r.messages)


def test_audit_log_records_the_conversation_in_order(run_agent):
    r = run_agent(then_done(tool_call("read_file", path="notes.txt")), user_messages=("what's in notes.txt?",))
    assert [e["event"] for e in r.log] == [
        "session_start", "user_message", "assistant_message", "tool_call", "assistant_message",
    ]
    assert r.events("user_message")[0]["content"] == "what's in notes.txt?"
    call = r.events("tool_call")[0]
    assert call["tool_input"] == {"path": "notes.txt"}
    assert call["result_preview"] == "Meeting notes\n"
    assert len({e["session_id"] for e in r.log}) == 1  # One run, one session ID


def test_send_message_only_writes_to_the_outbox(run_agent):
    r = run_agent(then_done(tool_call("send_message", to="someone@example.com", body="hello")))
    assert [(m["to"], m["body"]) for m in r.outbox] == [("someone@example.com", "hello")]
    assert r.events("tool_call")[0]["result_preview"] == "Message sent to someone@example.com."
