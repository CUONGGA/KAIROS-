from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParseIssue:
	path: Path
	message: str
	line_number: int | None = None


@dataclass(frozen=True)
class SessionItem:
	line_number: int
	record_type: str
	timestamp: str | None
	payload: dict[str, Any]


@dataclass(frozen=True)
class CodexSession:
	session_id: str
	path: Path
	started_at: str | None
	cwd: str | None
	originator: str | None
	items: tuple[SessionItem, ...]


@dataclass(frozen=True)
class ParseResult:
	sessions: tuple[CodexSession, ...]
	issues: tuple[ParseIssue, ...]

	@property
	def item_count(self) -> int:
		return sum(len(session.items) for session in self.sessions)


def default_sessions_dir() -> Path:
	return Path.home() / ".codex" / "sessions"


def find_session_files(sessions_dir: Path) -> tuple[Path, ...]:
	"""Find every Codex rollout JSONL file below ``sessions_dir``."""
	if not sessions_dir.exists():
		return ()
	return tuple(sorted(sessions_dir.rglob("rollout-*.jsonl")))


def parse_sessions(sessions_dir: Path, paths: tuple[Path, ...] | None = None) -> ParseResult:
	"""Parse every rollout file, or only the explicitly selected files."""
	if not sessions_dir.exists():
		return ParseResult(
			sessions=(),
			issues=(ParseIssue(sessions_dir, "Sessions directory does not exist."),),
		)

	sessions = []
	issues = []
	for path in paths if paths is not None else find_session_files(sessions_dir):
		result = parse_session_file(path)
		sessions.append(result.sessions[0])
		issues.extend(result.issues)

	return ParseResult(sessions=tuple(sessions), issues=tuple(issues))


def parse_session_file(path: Path) -> ParseResult:
	"""Parse one rollout JSONL file, retaining valid records after malformed lines."""
	session_id = path.stem.removeprefix("rollout-")
	started_at = None
	cwd = None
	originator = None
	items = []
	issues = []

	try:
		with path.open(encoding="utf-8", errors="replace") as source:
			for line_number, line in enumerate(source, start=1):
				if not line.strip():
					continue
				try:
					record = json.loads(line)
				except json.JSONDecodeError as error:
					issues.append(ParseIssue(path, f"Invalid JSON: {error.msg}", line_number))
					continue

				if not isinstance(record, Mapping):
					issues.append(ParseIssue(path, "Record must be a JSON object.", line_number))
					continue

				record_type = record.get("type")
				if not isinstance(record_type, str) or not record_type:
					issues.append(ParseIssue(path, "Record is missing type.", line_number))
					continue

				payload = record.get("payload")
				if not isinstance(payload, Mapping):
					issues.append(ParseIssue(path, "Record payload must be a JSON object.", line_number))
					continue

				if record_type == "session_meta":
					session_id = str(payload.get("id") or payload.get("session_id") or session_id)
					started_at = _string_or_none(record.get("timestamp"))
					cwd = _string_or_none(payload.get("cwd"))
					originator = _string_or_none(payload.get("originator"))
					continue

				if record_type == "turn_context" and not cwd:
					cwd = _string_or_none(payload.get("cwd"))

				items.append(
					SessionItem(
						line_number=line_number,
						record_type=record_type,
						timestamp=_string_or_none(record.get("timestamp")),
						payload=dict(payload),
					)
				)
	except OSError as error:
		issues.append(ParseIssue(path, f"Could not read file: {error}"))

	session = CodexSession(
		session_id=session_id,
		path=path,
		started_at=started_at,
		cwd=cwd,
		originator=originator,
		items=tuple(items),
	)
	return ParseResult(sessions=(session,), issues=tuple(issues))


def _string_or_none(value: object) -> str | None:
	return value if isinstance(value, str) and value else None
