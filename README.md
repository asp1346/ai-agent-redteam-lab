# AI Agent Lab

Framework-free agentic AI security lab, built from scratch on the raw
Anthropic API.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Store your API key in macOS Keychain (paste it at the hidden prompt)
security add-generic-password -U -a "$USER" -s anthropic-api-key -w

./run.sh
```

`run.sh` reads the key from Keychain and sets it as `ANTHROPIC_API_KEY` for that
one run. The key stays out of files on purpose: with guardrail G1 off, the
agent's `read_file` tool can open any file you can read.

Not on macOS? Set `ANTHROPIC_API_KEY` yourself and run `python agent.py`. Avoid
keeping the key in a file if you plan to disable G1.

## Guardrail switches

All guardrails are on by default. Turn them off to measure what each one stops:

```bash
./run.sh                     # All guardrails on
./run.sh --disable g1        # G1 off, everything else on
./run.sh --disable g1,g2     # G1 and G2 off
./run.sh --disable all       # Baseline: no guardrails
./run.sh --help              # List the guardrails
```

| ID | Guardrail |
|---|---|
| `g1` | Restrict `read_file` to the `workspace/` folder |
| `g2` | Cap tool calls per user message |

Switches last for one run. Each run prints what's disabled and records its
configuration in `audit_log.jsonl`.
