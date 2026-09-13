# Repository Guidelines

## Project Structure & Module Organization

This workspace contains the Kairos AI Work Assistant. The deployable Frappe app is in `kairos/`:

- `kairos/pyproject.toml` defines the Python package and Ruff configuration.
- `kairos/kairos/hooks.py` holds Frappe app metadata and framework hooks.
- `kairos/kairos/kairos/doctype/` contains each DocType's Python controller and JSON definition, for example `kairos_event/kairos_event.py` and `.json`.
- `docs/` contains setup and operational notes; `KAIROS.md` is the product and architecture specification.

Keep Frappe framework code inside the app package. Add a new DocType under `kairos/kairos/kairos/doctype/<doctype_name>/` and keep its controller and schema together.

## Build, Test, and Development Commands

Use a Frappe Bench environment (outside this repository) for runtime work. From the bench directory, run:

```bash
bench get-app "/path/to/Kairos Apps/kairos"
bench --site kairos.local install-app kairos
bench --site kairos.local migrate
bench start
```

`migrate` applies DocType/schema changes; run it after editing DocType JSON. Use `bench --site kairos.local clear-cache` when Desk changes are not visible. See `docs/A1-BENCH-INSTALL.md` for setup details.

## Coding Style & Naming Conventions

Target Python 3.10+. Follow the existing Ruff settings: tabs for indentation, double-quoted strings, and a 110-character line limit. Format and lint from `kairos/` with `ruff format .` and `ruff check .` when Ruff is available. Use `snake_case` for Python modules, functions, and DocType directory names; use clear, title-cased names in Frappe-facing labels.

## Testing Guidelines

No automated test suite is currently configured. For behavior changes, add focused tests using Frappe's test conventions when practical, named `test_<feature>.py`. At minimum, run Ruff and validate the change in a local site with `bench --site kairos.local migrate`; manually exercise affected Desk forms or APIs.

## Commit & Pull Request Guidelines

Match the history: use concise imperative subjects, preferably Conventional Commit style such as `feat: add event mapper` or `fix: refresh actor context`. Scope is optional (for example, `feat(course-authoring): ...`). Keep commits focused. Pull requests should describe the user-visible change, link the relevant issue/spec section, list verification performed, and include Desk screenshots for UI or DocType form changes.

## Security & Configuration

Never commit credentials. Keep developer integration values such as `KAIROS_FRAPPE_URL` and `KAIROS_FRAPPE_TOKEN` in local environment configuration. Store server-side LLM configuration through the site's `site_config`/Bench configuration, as documented in `KAIROS.md`.
