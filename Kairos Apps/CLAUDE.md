# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

The imported `AGENTS.md` is the source of truth for layout, commands, tests, invariants, and conventions.
Update it rather than duplicating its content here. The notes below add only what it leaves out.

## Test module classification

- Frappe `FrappeTestCase` (need a migrated site, run via `bench run-tests`): `test_api`, `test_install`,
  `test_scheduler`, `test_secrets`, `test_summary`, `test_timeline`, and the DocType tests.
- Plain `unittest` (no site required, `PYTHONPATH=kairos python -m unittest kairos.<module>`):
  `test_generation`, `test_llm_context`, `test_quality`, `test_summary_output`.

## Summary generation pipeline

`summary.generate_day_report_summary(report_date, force=...)` (whitelisted as `kairos.api.generate_day_summary`)
spans several modules:

1. `timeline.generate_day_report_timeline` refreshes the `Kairos Day Report` timeline first.
2. `llm_context.build_day_context` builds the bounded `SummaryContext` from events sanitized by `quality.py`.
   The context carries an `evidence_index` (ref -> project) and a `project_order`.
3. `generation.build_generation_fingerprint` hashes date + context + settings + schema versions
   (`CONTEXT_SCHEMA_VERSION`, `SUMMARY_OUTPUT_SCHEMA_VERSION`). A matching fingerprint on the report is a cache hit
   unless `force` is set. Bump the relevant schema version when context or output shape changes.
4. The LLM (`call_openai_chat_completions`, plain `urllib`, OpenAI-compatible) must return JSON claims.
   `summary_output.parse_and_validate_summary_output` accepts only claims whose evidence refs exist in the
   context and belong to the claimed project; `render_summary_markdown` renders them deterministically.
5. Invalid output triggers one repair call; a second failure, or any `frappe.ValidationError` (missing key,
   HTTP error), falls back to `build_fallback_summary` with a non-cacheable `error_code`
   (`generation.classify_generation_error`).
6. After a successful LLM call the fingerprint is recomputed. If the inputs changed during generation, the
   report returns to `draft` and the call throws instead of saving a stale summary.

Secrets are read only through `secrets.py` (`get_llm_api_key`, `get_llm_base_url`).
