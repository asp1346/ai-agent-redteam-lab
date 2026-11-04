# AI Agent Lab

Framework-free agentic AI security lab, built from scratch on the raw
Anthropic API.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
python agent.py
```

`agent.py` loads the API key from `.env` via `python-dotenv`. `.env` is
gitignored, so the key never gets committed.

## Guardrail switches

All guardrails are on by default. Turn them off to measure what each one stops:

```bash
python agent.py                     # All guardrails on
python agent.py --disable g1        # G1 off, everything else on
python agent.py --disable g1,g2     # G1 and G2 off
python agent.py --disable all       # Baseline: no guardrails
python agent.py --help              # List the guardrails
```

| ID | Guardrail |
|---|---|
| `g1` | Restrict `read_file` to the `workspace/` folder |
| `g2` | Cap tool calls per user message |

Switches last for one run. Each run prints what's disabled and records its
configuration in `audit_log.jsonl`.
