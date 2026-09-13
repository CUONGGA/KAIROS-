# Kairos Codex Collector

The collector reads local Codex sessions and maps meaningful user requests and completed agent runs to canonical events. B3 does not make HTTP requests.

## Development

Install the package in editable mode from this directory:

```bash
python -m pip install -e .
```

Check the available commands:

```bash
kairos-codex --help
kairos-codex sync --dry-run
kairos-codex sync --sessions-dir /path/to/sessions --dry-run
```

`--dry-run` prints canonical event JSON and may include short request/result snippets. Do not redirect that output to shared logs.

## Frappe delivery

Set the Frappe endpoint and collector token only in the developer machine environment:

```bash
export KAIROS_FRAPPE_URL="https://kairos.example.com"
export KAIROS_FRAPPE_TOKEN="<api_key>:<api_secret>"
```

Run `kairos-codex sync` without `--dry-run` to POST the canonical event batch to `/api/method/kairos.api.upsert_events`. The command logs created and updated counts, but never prints the token.

Normal sync is incremental. Its local checkpoint is
`~/.local/state/kairos/codex-sync-state.json`; only rollout files that are new or whose size or
modified time changed are parsed on the next run. Delete that state file only when deliberately
replaying the full history. Delivery is split into 100-event requests by default; use
`--batch-size 50` or `--timeout 120` when a server needs a smaller request or a longer response window.
Codex system context records (for example, `<environment_context ...>`) are skipped and are not treated as user work events.

## Idempotency verification

Use a directory containing one test rollout file, then run the explicit verification command. It sends the same batch twice; the second delivery must create zero events and update every mapped event.

```bash
kairos-codex sync --sessions-dir /tmp/kairos-test-sessions --verify-idempotency
```

Do not use this option with the full session-history directory.

## Scheduled sync (B6)

Windows Task Scheduler can launch the collector through WSL every 30 minutes. The runner loads
`~/.config/kairos/collector.env`, writes daily logs under `~/.local/state/kairos/`, batches delivery,
and does not store credentials in this repository. Follow [B6-SCHEDULED-COLLECTOR.md](../../docs/B6-SCHEDULED-COLLECTOR.md).

Run the standard-library test suite:

```bash
python -m unittest discover -s tests -v
```
