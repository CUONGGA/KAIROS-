from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from kairos_codex.sync import run_sync


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		prog="kairos-codex",
		description="Collect Codex session activity for Kairos.",
	)
	subcommands = parser.add_subparsers(dest="command", title="commands")

	sync_parser = subcommands.add_parser("sync", help="collect and synchronize Codex activity")
	delivery_mode = sync_parser.add_mutually_exclusive_group()
	delivery_mode.add_argument(
		"--dry-run",
		action="store_true",
		help="parse and map sessions without sending events",
	)
	delivery_mode.add_argument(
		"--verify-idempotency",
		action="store_true",
		help="send the same mapped batch twice and verify the second send creates no events",
	)
	sync_parser.add_argument(
		"--verbose",
		action="store_true",
		help="show debug logging",
	)
	sync_parser.add_argument(
		"--sessions-dir",
		type=Path,
		help="override the default ~/.codex/sessions directory",
	)
	sync_parser.add_argument(
		"--timeout",
		type=int,
		default=30,
		help="HTTP timeout in seconds when sending events (default: 30)",
	)
	sync_parser.add_argument(
		"--batch-size",
		type=_positive_integer,
		default=100,
		help="maximum events per Frappe request (default: 100)",
	)
	sync_parser.add_argument(
		"--state-file",
		type=Path,
		help="override the local incremental-sync state file",
	)
	return parser


def main(argv: Sequence[str] | None = None) -> int:
	parser = build_parser()
	args = parser.parse_args(argv)

	if args.command != "sync":
		parser.print_help()
		return 0

	logging.basicConfig(
		level=logging.DEBUG if args.verbose else logging.INFO,
		format="%(levelname)s %(message)s",
	)
	return run_sync(
		dry_run=args.dry_run,
		verify_idempotency=args.verify_idempotency,
		sessions_dir=args.sessions_dir,
		timeout=args.timeout,
		batch_size=args.batch_size,
		state_path=args.state_file,
	)


def _positive_integer(value: str) -> int:
	parsed_value = int(value)
	if parsed_value < 1:
		raise argparse.ArgumentTypeError("must be a positive integer")
	return parsed_value
