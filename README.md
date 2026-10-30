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
