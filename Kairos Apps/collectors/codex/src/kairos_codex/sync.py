from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

from kairos_codex.client import ClientConfigurationError, FrappeClientError, load_config, post_events
from kairos_codex.mapper import map_sessions
from kairos_codex.parser import default_sessions_dir, find_session_files, parse_sessions
from kairos_codex.state import SyncStateError, changed_paths, default_state_path, load_state, save_state

logger = logging.getLogger(__name__)
DEFAULT_BATCH_SIZE = 100


def run_sync(
	*,
	dry_run: bool,
	verify_idempotency: bool = False,
	sessions_dir: Path | None = None,
	timeout: int = 30,
	batch_size: int = DEFAULT_BATCH_SIZE,
	state_path: Path | None = None,
) -> int:
	"""Incrementally parse, map, and deliver local Codex sessions to Frappe."""
	sessions_dir = sessions_dir or default_sessions_dir()
	state_path = state_path or default_state_path()
	logger.info("Kairos Codex collector started.")
	if not sessions_dir.exists():
		logger.error("Sync failed: sessions directory does not exist: %s", sessions_dir)
		return 1
	all_paths = find_session_files(sessions_dir)

	try:
		state = load_state(state_path) if not dry_run else None
	except SyncStateError as error:
		logger.error("Sync failed: %s", error)
		return 1

	paths_to_parse = all_paths if dry_run else changed_paths(all_paths, state)
	result = parse_sessions(sessions_dir, paths_to_parse)
	logger.info("Found %s session files; skipped %s unchanged.", len(all_paths), len(all_paths) - len(paths_to_parse))
	logger.info("Parsed %s sessions and %s items.", len(result.sessions), result.item_count)

	for issue in result.issues:
		location = f":{issue.line_number}" if issue.line_number else ""
		logger.warning("%s%s: %s", issue.path, location, issue.message)

	events = map_sessions(result.sessions)
	logger.info("Mapped %s canonical events.", len(events))

	if dry_run:
		print(json.dumps({"events": events}, ensure_ascii=False, indent=2))
		logger.info("Dry run: no events were sent.")
		return 0

	if not events:
		try:
			save_state(state_path, state, paths_to_parse)
		except SyncStateError as error:
			logger.error("Sync failed: %s", error)
			return 1
		logger.info("No events to send.")
		return 0

	try:
		config = load_config()
		first_result = _post_event_batches(events, config, timeout=timeout, batch_size=batch_size)
	except (ClientConfigurationError, FrappeClientError) as error:
		logger.error("Sync failed: %s", error)
		return 1

	logger.info("Frappe accepted events: created=%s updated=%s.", first_result["created"], first_result["updated"])

	if verify_idempotency:
		try:
			second_result = _post_event_batches(events, config, timeout=timeout, batch_size=batch_size)
		except FrappeClientError as error:
			logger.error("Idempotency verification failed: %s", error)
			return 1

		if not _is_idempotent(first_result, second_result, len(events)):
			logger.error(
				"Idempotency verification failed: first created=%s updated=%s; "
				"second created=%s updated=%s.",
				first_result["created"],
				first_result["updated"],
				second_result["created"],
				second_result["updated"],
			)
			return 2

		logger.info(
			"Idempotency verified: first created=%s updated=%s; second created=0 updated=%s.",
			first_result["created"],
			first_result["updated"],
			second_result["updated"],
		)

	try:
		save_state(state_path, state, paths_to_parse)
	except SyncStateError as error:
		logger.error("Sync delivered events but could not save checkpoint: %s", error)
		return 1

	logger.info("Checkpoint saved for %s changed session files.", len(paths_to_parse))
	return 0


def _is_idempotent(first_result: dict, second_result: dict, event_count: int) -> bool:
	first_count = _result_count(first_result, "created") + _result_count(first_result, "updated")
	return (
		first_count == event_count
		and _result_count(second_result, "created") == 0
		and _result_count(second_result, "updated") == event_count
	)


def _result_count(result: dict, fieldname: str) -> int:
	value = result.get(fieldname, 0)
	return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _post_event_batches(events: list[dict], config, *, timeout: int, batch_size: int) -> dict:
	if batch_size < 1:
		raise ValueError("batch_size must be a positive integer")

	created = 0
	updated = 0
	batches = tuple(_batches(events, batch_size))
	for batch_number, batch in enumerate(batches, start=1):
		result = post_events(batch, config, timeout=timeout)
		created += _result_count(result, "created")
		updated += _result_count(result, "updated")
		logger.info(
			"Frappe accepted batch %s/%s: created=%s updated=%s.",
			batch_number,
			len(batches),
			_result_count(result, "created"),
			_result_count(result, "updated"),
		)
	return {"created": created, "updated": updated}


def _batches(events: list[dict], batch_size: int) -> Iterator[list[dict]]:
	for start in range(0, len(events), batch_size):
		yield events[start : start + batch_size]
