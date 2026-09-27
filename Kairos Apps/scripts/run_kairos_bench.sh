#!/usr/bin/env bash
# Start a local Kairos Bench after loading non-repository LLM configuration.

set -euo pipefail

readonly BENCH_DIR="${KAIROS_BENCH_DIR:-$HOME/frappe-bench}"
readonly CONFIG_FILE="${KAIROS_LLM_ENV_FILE:-$HOME/.config/kairos/llm.env}"

if [[ ! -d "$BENCH_DIR" ]]; then
	echo "Kairos Bench directory was not found. Set KAIROS_BENCH_DIR." >&2
	exit 1
fi

if [[ ! -r "$CONFIG_FILE" ]]; then
	echo "Kairos LLM configuration is missing: $CONFIG_FILE" >&2
	echo "Copy docs/templates/llm.env.example to that path and set KAIROS_LLM_API_KEY." >&2
	exit 1
fi

source "$CONFIG_FILE"
export KAIROS_LLM_API_KEY
if [[ -n "${KAIROS_LLM_BASE_URL:-}" ]]; then
	export KAIROS_LLM_BASE_URL
fi

cd "$BENCH_DIR"
exec bench start
