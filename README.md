# Kairos

Kairos is a personal AI work assistant built on Frappe. It turns local AI-tool activity into a
clear daily work report: collect events, build a timeline, and generate an AI summary suitable for
sharing with a manager or team.

> MVP scope: one user, timezone `Asia/Ho_Chi_Minh`, and Codex as the first collector.

## How it works

```text
Codex sessions on developer machine
  → Codex collector
  → Frappe API
  → Kairos Event
  → Kairos Day Report (timeline + AI summary)
```

Every collector maps its source data to the same canonical `Kairos Event` model. Adding Git,
Cursor, or ChatGPT collectors later does not require a new reporting schema.

## Repository layout

| Path | Purpose |
| --- | --- |
| `kairos/` | Frappe custom app: DocTypes, APIs, timeline, and LLM summary service. |
| `collectors/codex/` | Python CLI that reads Codex sessions and synchronizes canonical events. |
| `docs/` | Installation, authentication, and scheduler runbooks. |
| `KAIROS.md` | Product specification, architecture decisions, and delivery roadmap. |

## Current capabilities

- Idempotent event ingestion through `kairos.api.upsert_events`.
- Incremental Codex session synchronization, batching, and scheduled-run scripts.
- Daily timeline generation from `Kairos Event` records.
- OpenAI-compatible daily summaries using prompts and model settings from Frappe Desk.
- Server-side secrets: API keys never belong in DocTypes, source code, or Git.

Copy-to-clipboard and fallback summaries when the LLM is unavailable are planned next.

## Quick start

Run these commands from your Frappe Bench directory, not this repository:

```bash
git clone https://github.com/CUONGGA/KAIROS-.git
bench get-app "/path/to/KAIROS-/Kairos Apps/kairos"
bench --site kairos.local install-app kairos
bench --site kairos.local migrate
bench start
```

Open Desk, configure **Kairos Settings**, then open **Kairos Day Report** and use **Generate
Timeline** followed by **Generate Summary**.

To enable a real LLM, configure its key on the site server:

```bash
bench --site kairos.local set-config kairos_llm_api_key "YOUR_API_KEY"
# Optional for another OpenAI-compatible provider:
bench --site kairos.local set-config kairos_llm_base_url "https://provider.example/v1"
```

## Collector setup

The collector runs on the developer machine and reads configuration from local environment values:

```bash
export KAIROS_FRAPPE_URL="http://127.0.0.1:8001"
export KAIROS_FRAPPE_TOKEN="<frappe-api-token>"
PYTHONPATH="collectors/codex/src" python3 -m kairos_codex sync --dry-run
```

See [the Codex collector guide](collectors/codex/README.md) and
[the scheduler runbook](docs/B6-SCHEDULED-COLLECTOR.md) for production scheduling.

## Documentation and security

Read [KAIROS.md](KAIROS.md) for the complete specification and [AGENTS.md](AGENTS.md) for
contributor conventions. Never commit API keys, Frappe tokens, session exports, or local `.env`
files.
