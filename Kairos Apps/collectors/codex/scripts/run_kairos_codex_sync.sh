#!/usr/bin/env bash
# Run by Windows Task Scheduler through WSL. Secrets remain in the WSL home directory.

set -u

readonly COLLECTOR_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly CONFIG_FILE="${KAIROS_COLLECTOR_ENV_FILE:-$HOME/.config/kairos/collector.env}"

if [[ ! -r "$CONFIG_FILE" ]]; then
	echo "Kairos collector configuration is missing: $CONFIG_FILE" >&2
	exit 1
fi

# The configuration must export KAIROS_FRAPPE_URL and KAIROS_FRAPPE_TOKEN.
source "$CONFIG_FILE"
export KAIROS_FRAPPE_URL KAIROS_FRAPPE_TOKEN

readonly SESSIONS_DIR="${KAIROS_CODEX_SESSIONS_DIR:-$HOME/.codex/sessions}"
readonly LOG_DIR="${KAIROS_COLLECTOR_LOG_DIR:-$HOME/.local/state/kairos}"
readonly HTTP_TIMEOUT="${KAIROS_CODEX_TIMEOUT:-120}"
readonly BATCH_SIZE="${KAIROS_CODEX_BATCH_SIZE:-100}"
mkdir -p "$LOG_DIR"

readonly LOG_FILE="$LOG_DIR/codex-sync-$(date +%F).log"
readonly STARTED_AT="$(date -Is)"

{
	echo "[$STARTED_AT] Kairos Codex scheduled sync started."
	echo "Sessions directory: $SESSIONS_DIR"

	PYTHONPATH="$COLLECTOR_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
		python3 -m kairos_codex sync --sessions-dir "$SESSIONS_DIR" --timeout "$HTTP_TIMEOUT" --batch-size "$BATCH_SIZE"
	sync_status=$?

	echo "[$(date -Is)] Kairos Codex scheduled sync finished with exit code $sync_status."
	exit "$sync_status"
} >>"$LOG_FILE" 2>&1
