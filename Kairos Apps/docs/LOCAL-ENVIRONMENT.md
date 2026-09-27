# Local environment configuration

Kairos keeps development credentials outside this repository. The two files below are loaded by
different processes, so they must not be combined into a project `.env` file.

```text
~/.config/kairos/
├── collector.env  # developer machine → Frappe URL and API token
└── llm.env        # Frappe Bench process → LLM key and optional base URL
```

## Create the files in WSL

```bash
cd "/mnt/c/Projects/Kairos Apps"
bash scripts/setup_local_env.sh
```

The setup script creates only missing files and never overwrites a developer's configuration. Edit
the placeholder values using a local editor. Both files use `export`, so they can be loaded by shell
scripts safely. Do not commit either file, paste its contents into chat, or put LLM keys in a Frappe
DocType.

## Run the processes

The scheduled collector already loads `collector.env` through
`collectors/codex/scripts/run_kairos_codex_sync.sh`.

Start Frappe Bench through the wrapper so the web, worker, and scheduler processes inherit the LLM
variables:

```bash
bash "/mnt/c/Projects/Kairos Apps/scripts/run_kairos_bench.sh"
```

For a one-off API test, load only the LLM file in the current shell:

```bash
source ~/.config/kairos/llm.env
cd ~/frappe-bench
bench --site kairos.local execute kairos.api.generate_day_summary \
  --kwargs '{"report_date":"2026-09-27"}'
```

## Verify without exposing secrets

```bash
source ~/.config/kairos/llm.env
test -n "$KAIROS_LLM_API_KEY" && echo "LLM key loaded"
printf 'LLM base URL: %s\n' "${KAIROS_LLM_BASE_URL:-https://api.openai.com/v1}"
```
