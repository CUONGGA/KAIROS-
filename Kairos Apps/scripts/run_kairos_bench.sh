#!/usr/bin/env bash
# Start a local Kairos Bench after loading non-repository LLM configuration.

set -euo pipefail

readonly BENCH_DIR="${KAIROS_BENCH_DIR:-$HOME/kairos-bench}"
readonly CONFIG_FILE="${KAIROS_LLM_ENV_FILE:-$HOME/.config/kairos/llm.env}"
readonly BENCH_BIN="${KAIROS_BENCH_BIN:-$(command -v bench || true)}"

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

if [[ -z "${KAIROS_LLM_API_KEY:-}" ]]; then
	echo "Kairos LLM API key is empty in: $CONFIG_FILE" >&2
	exit 1
fi

if [[ -z "$BENCH_BIN" || ! -x "$BENCH_BIN" ]]; then
	echo "Bench CLI was not found. Set KAIROS_BENCH_BIN to its executable path." >&2
	exit 1
fi

cd "$BENCH_DIR"
echo "Starting Kairos Bench from: $BENCH_DIR"
echo "Kairos LLM API key: configured"
echo "Kairos LLM base URL: ${KAIROS_LLM_BASE_URL:-https://api.openai.com/v1}"
exec env \
	KAIROS_LLM_API_KEY="$KAIROS_LLM_API_KEY" \
	KAIROS_LLM_BASE_URL="${KAIROS_LLM_BASE_URL:-}" \
	"$BENCH_BIN" start
