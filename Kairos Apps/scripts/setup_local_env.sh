#!/usr/bin/env bash
# Create per-machine Kairos environment files from tracked templates.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
readonly WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
readonly CONFIG_DIR="${KAIROS_CONFIG_DIR:-$HOME/.config/kairos}"

create_if_missing() {
	local source_file="$1"
	local destination_file="$2"

	if [[ -e "$destination_file" ]]; then
		echo "Kept existing: $destination_file"
		return
	fi

	cp "$source_file" "$destination_file"
	chmod 600 "$destination_file"
	echo "Created: $destination_file"
}

mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

create_if_missing "$WORKSPACE_ROOT/docs/templates/collector.env.example" "$CONFIG_DIR/collector.env"
create_if_missing "$WORKSPACE_ROOT/docs/templates/llm.env.example" "$CONFIG_DIR/llm.env"

cat <<EOF

Next steps:
1. Edit $CONFIG_DIR/collector.env and $CONFIG_DIR/llm.env with credentials from your secret vault.
2. Start Bench with: bash "$WORKSPACE_ROOT/scripts/run_kairos_bench.sh"
3. Do not commit either local environment file.
EOF
