# Repository Guidelines

## Scope and layout

- Kairos is a Frappe app (`kairos/`) plus a standalone Codex collector (`collectors/codex/`).
- Frappe product code lives in `kairos/kairos/`; DocTypes are under `kairos/kairos/kairos/doctype/<name>/`.
  `hooks.py` wires install/migrate hooks and the daily scheduler. `KAIROS.md` is the Vietnamese product spec.
- `collectors/codex/` has its own `pyproject.toml`, package, and tests. Do not import it from the Frappe app.
- The git root is `C:\Projects`, not this directory. `git status` shows unrelated sibling projects, so stage
  only paths under `Kairos Apps/`. No CI workflow covers Kairos; verification is manual.

## Setup and commands

Run Frappe/Bench commands from the Bench directory, not this repo:

```bash
bench get-app --soft-link "/path/to/Kairos Apps/kairos"
bench --site kairos.local install-app kairos
bench --site kairos.local migrate
```

Use `--soft-link`: `kairos/` is a subdirectory of the monorepo, not its own git repo, so plain
`get-app` tries to clone it and fails.

See `docs/NEW-MACHINE-SETUP.md` for the complete new-machine runbook (WSL, env files, collector,
verification, troubleshooting).

- Run `bench --site kairos.local migrate` after editing any DocType JSON. `after_migrate` recreates the
  `Kairos Collector` role and seeds `Kairos Settings` defaults. Use `clear-cache` if Desk is stale.
- `bash scripts/setup_local_env.sh` creates `~/.config/kairos/collector.env` and `llm.env` only if missing.
  Start Bench with `bash scripts/run_kairos_bench.sh` so web, worker, and scheduler inherit `KAIROS_LLM_*`.
- Collector: from `collectors/codex`, either `python -m pip install -e .` or set `PYTHONPATH=src`; then run
  `python -m kairos_codex sync --dry-run` (or `--sessions-dir ... --dry-run`). The Windows scheduled runner
  launches the bash runner through WSL; its checkpoint is `~/.local/state/kairos/codex-sync-state.json`.

## Tests and verification

- Collector suite: from `collectors/codex`, `PYTHONPATH=src python -m unittest discover -s tests -v`;
  focus one module with `PYTHONPATH=src python -m unittest tests.test_mapper`. Use WSL/Linux, or install
  `tzdata` first: native Windows Python lacks the IANA data needed by `ZoneInfo("Asia/Ho_Chi_Minh")`. In
  PowerShell set `$env:PYTHONPATH="src"`.
- Frappe `FrappeTestCase` modules need a migrated development site:
  `bench --site kairos.local run-tests --app kairos --module kairos.test_api`. Substitute the module, for
  example `kairos.test_summary`, `kairos.test_timeline`, or
  `kairos.kairos.doctype.kairos_day_report.test_kairos_day_report`. Never point tests at production.
- Plain `unittest` modules (`kairos.test_generation`, `kairos.test_quality`, `kairos.test_llm_context`) run from
  the repo root inside the Bench virtualenv: `PYTHONPATH=kairos python -m unittest kairos.test_quality`.
- Before finishing, run `ruff format .` and `ruff check .` from each changed package. Python 3.10+, tabs,
  double quotes, 110 columns.

## Architecture and invariants

- Ingest flow: Codex collector -> `POST /api/method/kairos.api.upsert_events` -> `Kairos Event` ->
  `timeline.py` -> `Kairos Day Report` -> `summary.py`.
- `event_id` is always `{source}:{external_id}`. `upsert_events` is idempotent by `event_id`, validates the
  whole batch before writing, rejects duplicate ids, and refuses all events when `collection_enabled` is off.
- The scheduler hook `30 18 * * *` only refreshes today's timeline draft; it does not call the LLM. Timezone
  is fixed to `Asia/Ho_Chi_Minh`, and `Kairos Settings` rejects any other value.
- Summary generation is quality-gated: `quality.py` redacts secrets/paths and excludes ineligible events;
  `llm_context.py` builds a deterministic, bounded envelope without `raw_payload` or `event_id`. Keep that
  boundary when changing prompts or fields, and update the corresponding tests.
- Only successful summaries are cached, keyed by the generation fingerprint; failures or a missing API key use
  the local fallback. `force` bypasses the cache.
- Secret precedence is environment over `site_config`: `KAIROS_LLM_API_KEY` / `KAIROS_LLM_BASE_URL` override
  `kairos_llm_api_key` / `kairos_llm_base_url`. Never put secrets in DocTypes, source, logs, or Git.

## Conventions

- Add a DocType under `kairos/kairos/kairos/doctype/<name>/`, keeping its controller and JSON together; add a
  `test_<feature>.py` when behavior changes.
- Use concise Conventional Commit subjects, usually scoped such as `feat(kairos): add ...` or
  `fix(kairos): ...`. Keep commits focused.
- PRs should state the user-visible change, link the relevant spec section, list verification performed, and
  include Desk screenshots for UI or DocType changes.
